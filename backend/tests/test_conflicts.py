import pytest

from app.schemas import DecisionCreate, StateOut, TaskCreate, TaskUpdate
from app.services import access, conflicts, decisions, state, tasks, verification
from app.services.errors import ConflictError, Forbidden, InvalidInput
from tests.conftest import H

OWNER, EDITOR, VIEWER = 1, 2, 3


def ctx(session, uid, min_role="viewer"):
    return access.get_ctx(session, uid, 1, "web", min_role)


def new_task(session, uid=EDITOR, title="t"):
    return tasks.create_task(session, ctx(session, uid, "editor"), TaskCreate(title=title))


def new_decision(session, uid, topic, text):
    return decisions.create_decision(session, ctx(session, uid, "editor"),
                                     DecisionCreate(topic=topic, decision=text))


def edit(session, uid, task_id, version, title):
    return tasks.update_task(session, ctx(session, uid, "editor"), task_id,
                             TaskUpdate(version=version, title=title))


# ---- 7.4 verify
def test_owner_verifies_editors_task(session):
    t = new_task(session)
    row = verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 1)
    assert row.provenance == "verified" and row.verified_by == OWNER and row.verified_at


def test_editor_cannot_verify(session):
    with pytest.raises(Forbidden):
        ctx(session, EDITOR, "owner")


def test_cannot_verify_own_work_unless_flag(session, monkeypatch):
    t = new_task(session, OWNER)
    with pytest.raises(Forbidden):
        verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 1)
    monkeypatch.setenv("ALLOW_SELF_VERIFY", "1")
    row = verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 1)
    assert row.provenance == "verified"


def test_owner_can_verify_after_someone_else_edited_their_task(session):
    t = new_task(session, OWNER)
    edit(session, EDITOR, t.id, 1, "edited by editor")
    row = verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 2)
    assert row.provenance == "verified"


def test_verify_stale_version_conflicts(session):
    t = new_task(session)
    edit(session, EDITOR, t.id, 1, "B")
    with pytest.raises(ConflictError) as e:
        verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 1)
    assert e.value.current["version"] == 2


def test_edit_demotes_verified(session):
    t = new_task(session)
    verification.verify_item(session, ctx(session, OWNER, "owner"), "task", t.id, 1)
    row = edit(session, EDITOR, t.id, 1, "changed after verify")
    assert row.provenance == "asserted" and row.verified_by is None and row.updated_by == EDITOR


# ---- 7.1 concurrent edits
def _stale_conflict(session):
    t = new_task(session, EDITOR)
    edit(session, OWNER, t.id, 1, "A")
    with pytest.raises(ConflictError):
        edit(session, EDITOR, t.id, 1, "B")
    return t


def test_task_conflict_open_then_resolved(session):
    t = _stale_conflict(session)
    found = conflicts.list_conflicts(session, 1)
    assert [c["kind"] for c in found] == ["task"] and found[0]["detail"]["task_id"] == t.id
    conflicts.resolve_task_conflict(session, ctx(session, OWNER, "owner"), t.id, "ok")
    assert conflicts.list_conflicts(session, 1) == []


def test_loser_retry_clears_conflict(session):
    t = _stale_conflict(session)
    edit(session, EDITOR, t.id, 2, "B retried")
    assert conflicts.list_conflicts(session, 1) == []


def test_resolve_without_conflict_rejected(session):
    t = new_task(session)
    with pytest.raises(InvalidInput):
        conflicts.resolve_task_conflict(session, ctx(session, OWNER, "owner"), t.id)


def test_viewer_cannot_resolve(session):
    with pytest.raises(Forbidden):
        ctx(session, VIEWER, "owner")


# ---- 7.2 contradictory decisions
def test_decision_conflict_flagged_and_resolved(session):
    a = new_decision(session, OWNER, "Database", "Use Postgres")
    b = new_decision(session, EDITOR, " database ", "Use SQLite")
    new_decision(session, EDITOR, "Auth", "Use OAuth")
    new_decision(session, OWNER, "auth", "use  oauth")  # same text: not a contradiction

    found = conflicts.list_conflicts(session, 1)
    assert len(found) == 1 and found[0]["kind"] == "decision_topic"
    assert set(found[0]["detail"]["decision_ids"]) == {a.id, b.id}

    conflicts.resolve_decision_conflict(session, ctx(session, OWNER, "owner"), a.id, "pg wins")
    session.refresh(b)
    assert b.superseded_by == a.id
    assert conflicts.list_conflicts(session, 1) == []

    s = state.build_state(session, 1)
    assert not any(u["kind"] == "decision" and u["id"] == b.id for u in s["unverified"])
    with pytest.raises(InvalidInput):
        verification.verify_item(session, ctx(session, OWNER, "owner"), "decision", b.id, 1)


# ---- 7.5 state output
def test_state_lists_conflicts(session):
    new_decision(session, OWNER, "Hosting", "Render")
    new_decision(session, EDITOR, "Hosting", "Fly.io")
    s = state.build_state(session, 1)
    assert StateOut.model_validate(s).conflicts[0].kind == "decision_topic"


# ---- REST
def test_rest_verify_flow(client):
    t = client.post("/projects/1/tasks", json={"title": "x"}, headers=H(2)).json()
    body = {"kind": "task", "item_id": t["id"], "version": 1}
    assert client.post("/projects/1/verify", json=body, headers=H(3)).status_code == 403
    assert client.post("/projects/1/verify", json=body, headers=H(2)).status_code == 403
    r = client.post("/projects/1/verify", json=body, headers=H(1))
    assert r.status_code == 200 and r.json()["provenance"] == "verified"
    stale = client.post("/projects/1/verify", json={**body, "version": 9}, headers=H(1))
    assert stale.status_code in (409,)  # already verified rows still check version first


def test_rest_conflicts_readable_by_viewer(client):
    assert client.get("/projects/1/conflicts", headers=H(3)).json() == []