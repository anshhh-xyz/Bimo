from contextlib import nullcontext

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.services import access
from app.services import members as member_svc
from mcp_server import tools
from mcp_server.auth import Caller

OWNER, EDITOR, VIEWER, OUTSIDER = (Caller(1, "web"), Caller(2, "code"),
                                   Caller(3, "web"), Caller(4, "web"))


def run(session, fn, caller, **kw):
    return tools._execute(fn, caller, kw, session_factory=lambda: nullcontext(session))


ALL_OPS = [
    (tools.op_get_project_state, {}),
    (tools.op_list_changes, {}),
    (tools.op_create_task, {"title": "x"}),
    (tools.op_update_task, {"task_id": 1, "version": 1, "title": "x"}),
    (tools.op_record_decision, {"topic": "t", "decision": "d"}),
    (tools.op_save_handoff, {"summary": "s"}),
]
WRITE_OPS = ALL_OPS[2:]


@pytest.mark.parametrize("fn,kw", ALL_OPS)
def test_non_member_denied_on_every_tool(session, fn, kw):
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, fn, OUTSIDER, project_id=1, **kw)


@pytest.mark.parametrize("fn,kw", WRITE_OPS)
def test_viewer_denied_on_every_write_tool(session, fn, kw):
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, fn, VIEWER, project_id=1, **kw)


def test_list_projects_shows_only_own_projects(session):
    assert "demo" in run(session, tools.op_list_projects, VIEWER)
    assert "demo" not in run(session, tools.op_list_projects, OUTSIDER)


def test_removed_member_loses_mcp_access(session):
    run(session, tools.op_get_project_state, VIEWER, project_id=1)  # allowed
    owner_ctx = access.get_ctx(session, 1, 1, "web", "owner")
    member_svc.remove_member(session, owner_ctx, 3)
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_get_project_state, VIEWER, project_id=1)


def test_role_change_applies_to_mcp_immediately(session):
    with pytest.raises(ToolError, match="Forbidden"):
        run(session, tools.op_create_task, VIEWER, project_id=1, title="x")
    owner_ctx = access.get_ctx(session, 1, 1, "web", "owner")
    member_svc.change_role(session, owner_ctx, 3, "editor")
    assert "x" in run(session, tools.op_create_task, VIEWER, project_id=1, title="x")