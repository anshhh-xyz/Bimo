import pytest
from app.schemas import TaskCreate, TaskUpdate
from app.services import access, events, tasks
from app.services.errors import (ConflictError, Forbidden, InvalidInput,
                                 NotFound, Unauthorized)


def test_get_ctx_for_member(session):
    ctx = access.get_ctx(session, 3, 1, "web", "viewer")
    assert (ctx.role, ctx.surface, ctx.project_id) == ("viewer", "web", 1)


def test_viewer_cannot_get_editor_ctx(session):
    with pytest.raises(Forbidden):
        access.get_ctx(session, 3, 1, "web", "editor")


def test_non_member_forbidden(session):
    with pytest.raises(Forbidden):
        access.get_ctx(session, 4, 1, "web", "viewer")


def test_unknown_user_unauthorized(session):
    with pytest.raises(Unauthorized):
        access.get_ctx(session, 99, 1, "web", "viewer")


def test_bad_surface_rejected(session):
    with pytest.raises(InvalidInput):
        access.get_ctx(session, 1, 1, "phone", "viewer")


def test_list_projects(session):
    assert access.list_projects(session, 2) == [{"id": 1, "name": "demo", "role": "editor"}]
    assert access.list_projects(session, 4) == []


def _editor(session):
    return access.get_ctx(session, 2, 1, "code", "editor")


def test_stale_update_raises_conflict_with_current(session):
    ctx = _editor(session)
    t = tasks.create_task(session, ctx, TaskCreate(title="x"))
    tasks.update_task(session, ctx, t.id, TaskUpdate(version=1, title="A"))
    with pytest.raises(ConflictError) as e:
        tasks.update_task(session, ctx, t.id, TaskUpdate(version=1, title="B"))
    assert e.value.current["version"] == 2 and e.value.current["title"] == "A"


def test_update_unknown_task_not_found(session):
    with pytest.raises(NotFound):
        tasks.update_task(session, _editor(session), 999, TaskUpdate(version=1, title="x"))


def test_empty_update_rejected(session):
    ctx = _editor(session)
    t = tasks.create_task(session, ctx, TaskCreate(title="x"))
    with pytest.raises(InvalidInput):
        tasks.update_task(session, ctx, t.id, TaskUpdate(version=1))


def test_list_changes_newest_first_and_limit(session):
    ctx = _editor(session)
    tasks.create_task(session, ctx, TaskCreate(title="a"))
    tasks.create_task(session, ctx, TaskCreate(title="b"))
    rows = events.list_changes(session, 1)
    assert rows[0].payload["title"] == "b"
    assert len(events.list_changes(session, 1, limit=1)) == 1