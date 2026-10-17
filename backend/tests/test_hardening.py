"""Role cleanup, client labelling, /authorize throttling, domain errors."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import ProjectMember
from app.schemas import TaskCreate
from app.services import access, events, ratelimit, tasks
from app.services import members as member_svc
from app.services.errors import NotFound, StateConflict
from mcp_server import tools
from mcp_server.auth import Caller, caller_from_headers, classify_client
from tests.conftest import H
from tests.test_oauth import REDIRECT, get_code, pkce, register, token_request
from urllib.parse import parse_qs, urlsplit


@pytest.fixture(autouse=True)
def _reset_limiter():
    ratelimit.clear_all()


# ---- roles
def test_legacy_member_role_is_rejected_by_database(session):
    session.add(ProjectMember(project_id=1, user_id=4, role="member"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_member_role_no_longer_grants_access():
    assert "member" not in access.ROLE_RANK


# ---- domain errors (so MCP tools can reuse the service)
def test_member_service_raises_domain_errors(session):
    owner = access.get_ctx(session, 1, 1, "web", "owner")
    with pytest.raises(NotFound):
        member_svc.remove_member(session, owner, 4)
    with pytest.raises(StateConflict):
        member_svc.remove_member(session, owner, 1)   # last owner


# ---- client labelling
@pytest.mark.parametrize("name,expected", [
    ("Claude", ("claude", "web")),
    ("Claude Code", ("claude-code", "code")),
    ("claude-code", ("claude-code", "code")),
    ("ChatGPT", ("chatgpt", "web")),
    ("OpenAI MCP Client", ("chatgpt", "web")),
    ("Cursor IDE", ("cursor-ide", None)),
    ("", (None, None)),
    (None, (None, None)),
])
def test_classify_client(name, expected):
    assert classify_client(name) == expected


def test_dev_token_has_no_agent(monkeypatch):
    monkeypatch.setenv("DEV_TOKENS", "t1:1")
    assert caller_from_headers({"authorization": "Bearer t1"}) == Caller(1, "web", None)


def test_agent_is_recorded_on_events_and_records(session):
    caller = Caller(2, "web", "chatgpt")
    out = tools._execute(tools.op_create_task, caller,
                         {"project_id": 1, "title": "from chatgpt"},
                         session_factory=lambda: __import__("contextlib").nullcontext(session))
    assert '"agent": "chatgpt"' in out
    assert events.list_changes(session, 1)[0].agent == "chatgpt"


def test_client_supplied_agent_wins_on_record_but_event_keeps_server_label(session):
    ctx = access.get_ctx(session, 2, 1, "web", "editor", agent="claude")
    t = tasks.create_task(session, ctx, TaskCreate(title="x", agent="claude-opus"))
    assert t.agent == "claude-opus"
    assert events.list_changes(session, 1)[0].agent == "claude"


def test_oauth_token_resolves_to_client_name(client, session, monkeypatch):
    from app.services import oauth
    monkeypatch.setenv("USER_PASSPHRASES", "user1@test.dev:pw1")
    r = client.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT"})
    cid = r.json()["client_id"]
    verifier, challenge = pkce()
    code = parse_qs(urlsplit(get_code(client, cid, challenge).headers["location"]).query)["code"][0]
    tok = token_request(client, cid, code, verifier).json()["access_token"]
    assert oauth.identity_for_access_token(session, tok) == (1, "ChatGPT")
    assert classify_client("ChatGPT")[0] == "chatgpt"


# ---- /authorize throttling
def test_authorize_locks_after_repeated_failures(client, monkeypatch):
    monkeypatch.setenv("USER_PASSPHRASES", "user1@test.dev:pw1")
    cid = register(client)
    _, challenge = pkce()
    for _ in range(5):
        assert get_code(client, cid, challenge, passphrase="nope").status_code == 401
    # even the correct passphrase is refused while locked
    r = get_code(client, cid, challenge, passphrase="pw1")
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_successful_login_resets_the_counter(client, monkeypatch):
    monkeypatch.setenv("USER_PASSPHRASES", "user1@test.dev:pw1")
    cid = register(client)
    _, challenge = pkce()
    for _ in range(4):
        get_code(client, cid, challenge, passphrase="nope")
    assert get_code(client, cid, challenge, passphrase="pw1").status_code == 302
    for _ in range(4):
        assert get_code(client, cid, challenge, passphrase="nope").status_code == 401


def test_limiter_window_expires():
    now = [0.0]
    lim = ratelimit.AttemptLimiter(2, 60, clock=lambda: now[0])
    lim.record_failure("k"); lim.record_failure("k")
    assert lim.blocked("k")
    now[0] = 61
    assert not lim.blocked("k")


# ---- REST members still map domain errors to the same status codes
def test_rest_status_codes_unchanged(client):
    assert client.delete("/projects/1/members/4", headers=H(1)).status_code == 404
    assert client.delete("/projects/1/members/1", headers=H(1)).status_code == 409
    assert client.post("/projects/1/members", json={"email": "user2@test.dev"},
                       headers=H(1)).status_code == 409
