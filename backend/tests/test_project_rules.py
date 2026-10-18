import re
from contextlib import nullcontext

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Event, Project
from app.services import access
from mcp_server import tools
from mcp_server.auth import Caller
from tests.conftest import H


def create(client, uid=4, name="My app"):
    return client.post("/projects", json={"name": name}, headers=H(uid))


def delete(client, pid, uid, confirm):
    return client.delete(f"/projects/{pid}", params={"confirm_name": confirm},
                         headers=H(uid))


def run(session, fn, caller, **kw):
    return tools._execute(fn, caller, kw, session_factory=lambda: nullcontext(session))


# ---- unique names
def test_duplicate_name_is_409(client):
    assert create(client, name="Alpha").status_code == 201
    r = create(client, name="Alpha")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_duplicate_ignores_case_and_spaces(client):
    create(client, name="Alpha")
    assert create(client, name="  aLPHA ").status_code == 409


def test_duplicate_is_blocked_across_users(client):
    create(client, uid=4, name="Alpha")
    assert create(client, uid=1, name="Alpha").status_code == 409


def test_seeded_project_name_is_taken(client):
    assert create(client, name="DEMO").status_code == 409


def test_database_enforces_unique_names_on_its_own(session):
    session.add(Project(name="Dup"))
    session.commit()
    session.add(Project(name="dup"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ---- editor is the default role for added members
def test_added_member_defaults_to_editor(client):
    r = client.post("/projects/1/members", json={"email": "user4@test.dev"},
                    headers=H(1))
    assert r.status_code == 201 and r.json()["role"] == "editor"
    assert client.post("/projects/1/tasks", json={"title": "x"},
                       headers=H(4)).status_code == 201


# ---- deletion (REST)
def test_owner_deletes_project(client, session):
    pid = create(client).json()["id"]
    assert delete(client, pid, 4, "My app").status_code == 204
    assert client.get(f"/projects/{pid}/state", headers=H(4)).status_code == 403
    assert access.list_projects(session, 4) == []
    # soft delete: the row and its history are still there
    assert session.get(Project, pid).deleted_at is not None
    ev = session.scalar(select(Event).where(Event.project_id == pid,
                                            Event.type == "project_deleted"))
    assert ev is not None and ev.user_id == 4


def test_only_owner_can_delete(client):
    for uid in (2, 3, 4):  # editor, viewer, not a member
        assert delete(client, 1, uid, "demo").status_code == 403
    assert client.get("/projects/1/state", headers=H(1)).status_code == 200


def test_wrong_confirmation_deletes_nothing(client):
    pid = create(client).json()["id"]
    assert delete(client, pid, 4, "wrong name").status_code == 422
    assert client.get(f"/projects/{pid}/state", headers=H(4)).status_code == 200


def test_confirm_name_is_required(client):
    assert client.delete("/projects/1", headers=H(1)).status_code == 422


def test_name_can_be_reused_after_delete(client):
    pid = create(client, name="Reuse").json()["id"]
    assert delete(client, pid, 4, "Reuse").status_code == 204
    assert create(client, uid=1, name="Reuse").status_code == 201


def test_deleted_project_is_locked_for_everyone(client):
    pid = create(client).json()["id"]
    delete(client, pid, 4, "My app")
    assert client.get(f"/projects/{pid}/members", headers=H(4)).status_code == 403
    assert delete(client, pid, 4, "My app").status_code == 403  # no second delete


# ---- deletion (MCP)
def test_mcp_delete_round_trip(session):
    caller = Caller(4, "web", "claude")
    out = run(session, tools.op_create_project, caller, name="Temp")
    pid = int(re.search(r'"id": (\d+)', out).group(1))
    assert "Temp" in run(session, tools.op_list_projects, caller)
    run(session, tools.op_delete_project, caller, project_id=pid, confirm_name="Temp")
    assert "Temp" not in run(session, tools.op_list_projects, caller)


def test_mcp_delete_needs_the_exact_name(session):
    caller = Caller(1, "web", "claude")
    with pytest.raises(ToolError, match="confirm_name"):
        run(session, tools.op_delete_project, caller, project_id=1, confirm_name="Demo")


def test_mcp_editor_cannot_delete(session):
    caller = Caller(2, "web", "claude")
    with pytest.raises(ToolError):
        run(session, tools.op_delete_project, caller, project_id=1, confirm_name="demo")