import re
from contextlib import nullcontext

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import func, select

from app.models import Event, Project, ProjectMember
from app.schemas import ProjectCreate
from app.services import access
from app.services import projects as project_svc
from mcp_server import tools
from mcp_server.auth import Caller
from tests.conftest import H


def count_projects(session) -> int:
    return session.scalar(select(func.count()).select_from(Project))


def create(client, uid=4, name="My app"):
    return client.post("/projects", json={"name": name}, headers=H(uid))


# ---- REST
def test_creator_becomes_owner(client, session):
    r = create(client, name="  My app  ")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My app" and body["role"] == "owner"
    assert body["summary_version"] == 1
    m = session.get(ProjectMember, (body["id"], 4))
    assert m is not None and m.role == "owner"


def test_new_project_is_private_to_its_creator(client):
    pid = create(client, name="Secret").json()["id"]
    assert client.get(f"/projects/{pid}/state", headers=H(4)).status_code == 200
    for uid in (1, 2, 3):  # members of the seeded project, not of this one
        assert client.get(f"/projects/{pid}/state", headers=H(uid)).status_code == 403


def test_creating_a_project_grants_nothing_on_other_projects(client):
    create(client, uid=4)
    assert client.get("/projects/1/state", headers=H(4)).status_code == 403


def test_creator_can_manage_members_of_new_project(client):
    pid = create(client).json()["id"]
    r = client.post(f"/projects/{pid}/members",
                    json={"email": "user1@test.dev", "role": "editor"}, headers=H(4))
    assert r.status_code == 201
    assert client.get(f"/projects/{pid}/state", headers=H(1)).status_code == 200


def test_creator_cannot_abandon_new_project(client):
    pid = create(client).json()["id"]
    assert client.delete(f"/projects/{pid}/members/4", headers=H(4)).status_code == 409
    assert client.patch(f"/projects/{pid}/members/4", json={"role": "viewer"},
                        headers=H(4)).status_code == 409


def test_creation_is_logged(client):
    pid = create(client).json()["id"]
    events = client.get(f"/projects/{pid}/changes", headers=H(4)).json()
    assert [e["type"] for e in events] == ["project_created"]
    assert events[0]["user_id"] == 4 and events[0]["surface"] == "code"


@pytest.mark.parametrize("body", [
    {"name": ""},
    {"name": "   "},
    {"name": "x" * 151},
    {},
    {"name": "ok", "role": "viewer"},   # clients cannot choose a role
    {"name": "ok", "owner_id": 1},      # or an owner
])
def test_invalid_body_is_422_and_saves_nothing(client, session, body):
    before = count_projects(session)
    assert client.post("/projects", json=body, headers=H(4)).status_code == 422
    assert count_projects(session) == before


def test_unknown_user_is_401(client):
    assert create(client, uid=99).status_code == 401


def test_bad_surface_is_422(client):
    r = client.post("/projects", json={"name": "x"},
                    headers={"X-User-Id": "4", "X-Surface": "nope"})
    assert r.status_code == 422


def test_every_project_has_an_owner(client, session):
    for uid in (1, 2, 3, 4):
        assert create(client, uid=uid, name=f"p{uid}").status_code == 201
    owned = select(ProjectMember.project_id).where(ProjectMember.role == "owner")
    ownerless = session.scalar(
        select(func.count()).select_from(Project).where(Project.id.not_in(owned)))
    assert ownerless == 0


# ---- the transaction
def test_failure_midway_leaves_nothing_behind(session, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("event write failed")

    monkeypatch.setattr(project_svc, "log_event", boom)
    actor = access.get_actor(session, 4, "code")
    before = count_projects(session)
    with pytest.raises(RuntimeError):
        project_svc.create_project(session, actor, ProjectCreate(name="Ghost"))
    assert count_projects(session) == before
    assert session.scalar(select(func.count()).select_from(ProjectMember)
                          .where(ProjectMember.user_id == 4)) == 0


# ---- MCP
def run(session, fn, caller, **kw):
    return tools._execute(fn, caller, kw, session_factory=lambda: nullcontext(session))


def test_mcp_create_project_round_trip(session):
    caller = Caller(4, "web", "claude")
    out = run(session, tools.op_create_project, caller, name="From Claude", summary="hi")
    pid = int(re.search(r'"id": (\d+)', out).group(1))
    assert "From Claude" in out and "owner" in out
    assert "From Claude" in run(session, tools.op_list_projects, caller)
    # the server-derived agent and surface are recorded, not model-supplied
    ev = session.scalar(select(Event).where(Event.project_id == pid,
                                            Event.type == "project_created"))
    assert ev.agent == "claude" and ev.surface == "web" and ev.user_id == 4


def test_mcp_create_project_rejects_blank_name(session):
    with pytest.raises(ToolError, match="name"):
        run(session, tools.op_create_project, Caller(4, "web"), name="   ")