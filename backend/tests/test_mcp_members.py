from contextlib import nullcontext

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select

from app.models import Event
from mcp_server import tools
from mcp_server.auth import Caller

# seeded in conftest: user 1 owner, user 2 editor, user 3 viewer, user 4 not a member
OWNER = Caller(1, "web", "claude")
EDITOR = Caller(2, "web", "claude")
VIEWER = Caller(3, "web", "claude")
OUTSIDER = Caller(4, "web", "claude")


def run(session, fn, caller, **kw):
    return tools._execute(fn, caller, kw, session_factory=lambda: nullcontext(session))


# ---- listing
def test_viewer_can_list_members(session):
    out = run(session, tools.op_list_members, VIEWER, project_id=1)
    assert "user1@test.dev" in out and "user3@test.dev" in out


def test_outsider_cannot_list_members(session):
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_list_members, OUTSIDER, project_id=1)


# ---- adding
def test_owner_adds_member_as_editor_by_default(session):
    out = run(session, tools.op_add_member, OWNER, project_id=1, email="user4@test.dev")
    assert '"role": "editor"' in out
    # the new member can now write
    run(session, tools.op_create_task, OUTSIDER, project_id=1, title="hello")


def test_owner_can_add_a_viewer(session):
    out = run(session, tools.op_add_member, OWNER, project_id=1,
              email="user4@test.dev", role="viewer")
    assert '"role": "viewer"' in out
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_create_task, OUTSIDER, project_id=1, title="no")


def test_add_member_is_audited_with_the_agent(session):
    run(session, tools.op_add_member, OWNER, project_id=1, email="user4@test.dev")
    ev = session.scalar(select(Event).where(Event.type == "member_added"))
    assert ev.agent == "claude" and ev.surface == "web" and ev.user_id == 1


def test_unknown_email_is_not_found(session):
    with pytest.raises(ToolError, match="No Bimo user"):
        run(session, tools.op_add_member, OWNER, project_id=1, email="nobody@test.dev")


def test_adding_an_existing_member_is_refused(session):
    with pytest.raises(ToolError, match="Already a member"):
        run(session, tools.op_add_member, OWNER, project_id=1, email="user2@test.dev")


def test_invalid_role_is_rejected(session):
    with pytest.raises(ToolError, match="Invalid input"):
        run(session, tools.op_add_member, OWNER, project_id=1,
            email="user4@test.dev", role="admin")
    with pytest.raises(ToolError, match="Invalid input"):
        run(session, tools.op_change_member_role, OWNER, project_id=1,
            user_id=3, role="admin")


# ---- owner-only
@pytest.mark.parametrize("who", [EDITOR, VIEWER, OUTSIDER])
def test_only_an_owner_can_change_membership(session, who):
    attempts = ((tools.op_add_member, {"email": "user4@test.dev"}),
                (tools.op_change_member_role, {"user_id": 3, "role": "editor"}),
                (tools.op_remove_member, {"user_id": 3}))
    for fn, kw in attempts:
        with pytest.raises(ToolError, match="Forbidden"):
            run(session, fn, who, project_id=1, **kw)


# ---- changing roles
def test_role_change_takes_effect_immediately(session):
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_create_task, VIEWER, project_id=1, title="x")
    run(session, tools.op_change_member_role, OWNER, project_id=1, user_id=3, role="editor")
    run(session, tools.op_create_task, VIEWER, project_id=1, title="x")


def test_last_owner_cannot_be_demoted_or_removed(session):
    with pytest.raises(ToolError, match="last owner"):
        run(session, tools.op_change_member_role, OWNER, project_id=1,
            user_id=1, role="viewer")
    with pytest.raises(ToolError, match="last owner"):
        run(session, tools.op_remove_member, OWNER, project_id=1, user_id=1)


# ---- removing
def test_removed_member_loses_access(session):
    out = run(session, tools.op_remove_member, OWNER, project_id=1, user_id=2)
    assert '"removed": true' in out
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_get_project_state, EDITOR, project_id=1)