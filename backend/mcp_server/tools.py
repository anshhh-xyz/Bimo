from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.db import SessionLocal
from mcp_server.auth import Caller, caller_from_headers
from mcp_server.formatting import format_error, format_validation_error, wrap_memory
from app.schemas import (DecisionCreate, DecisionOut, EventOut, HandoffCreate,
                         HandoffOut, StateOut, TaskCreate, TaskOut, TaskUpdate)
from app.services import access
from app.services import decisions as decision_svc
from app.services import events as event_svc
from app.services import handoffs as handoff_svc
from app.services import state as state_svc
from app.services import tasks as task_svc
from app.services.errors import InvalidInput, ServiceError


# ---------- pure operations: (session, caller, **args) -> JSON-able data ----------
# No MCP types in here, so they are unit-testable without any HTTP.

def _ctx(session, caller: Caller, project_id: int, role: str):
    return access.get_ctx(session, caller.user_id, project_id, caller.surface, role,
                          agent=caller.agent)


def op_list_projects(session, caller):
    access.get_user(session, caller.user_id)
    return access.list_projects(session, caller.user_id)


def op_get_project_state(session, caller, project_id):
    _ctx(session, caller, project_id, "viewer")
    return StateOut.model_validate(
        state_svc.build_state(session, project_id)).model_dump(mode="json")


def op_create_task(session, caller, project_id, title, description=None,
                   agent=None, commit_sha=None):
    ctx = _ctx(session, caller, project_id, "editor")
    t = task_svc.create_task(session, ctx, TaskCreate(
        title=title, description=description, agent=agent, commit_sha=commit_sha))
    return TaskOut.model_validate(t).model_dump(mode="json")


def op_update_task(session, caller, project_id, task_id, version, title=None,
                   description=None, state=None, agent=None, commit_sha=None):
    ctx = _ctx(session, caller, project_id, "editor")
    fields = {"title": title, "description": description, "state": state,
              "agent": agent, "commit_sha": commit_sha}
    data = TaskUpdate(version=version, **{k: v for k, v in fields.items() if v is not None})
    t = task_svc.update_task(session, ctx, task_id, data)
    return TaskOut.model_validate(t).model_dump(mode="json")


def op_record_decision(session, caller, project_id, topic, decision,
                       rationale=None, agent=None, commit_sha=None):
    ctx = _ctx(session, caller, project_id, "editor")
    d = decision_svc.create_decision(session, ctx, DecisionCreate(
        topic=topic, decision=decision, rationale=rationale,
        agent=agent, commit_sha=commit_sha))
    return DecisionOut.model_validate(d).model_dump(mode="json")


def op_save_handoff(session, caller, project_id, summary, completed=None, blockers=None,
                    open_questions=None, files_touched=None, last_commit_sha=None,
                    verification_status="unverified", next_action=None, agent=None):
    ctx = _ctx(session, caller, project_id, "editor")
    h = handoff_svc.create_handoff(session, ctx, HandoffCreate(
        summary=summary, completed=completed or [], blockers=blockers or [],
        open_questions=open_questions or [], files_touched=files_touched or [],
        last_commit_sha=last_commit_sha, verification_status=verification_status,
        next_action=next_action, agent=agent))
    return HandoffOut.model_validate(h).model_dump(mode="json")


def op_list_changes(session, caller, project_id, since=None, limit=20):
    _ctx(session, caller, project_id, "viewer")
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise InvalidInput("since must be an ISO-8601 timestamp")
    rows = event_svc.list_changes(session, project_id, since_dt, limit)
    return [EventOut.model_validate(e).model_dump(mode="json") for e in rows]


# ---------- execution wrapper ----------

def _execute(fn: Callable, caller: Caller, kwargs: dict,
             session_factory: Callable[[], AbstractContextManager] | None = None) -> str:
    """Open a session, run one operation, wrap the result as delimited data,
    translate domain errors into MCP tool errors."""
    factory = session_factory or SessionLocal
    try:
        with factory() as session:
            data = fn(session, caller, **kwargs)
        return wrap_memory(data)
    except ServiceError as e:
        raise ToolError(format_error(e)) from e
    except ValidationError as e:
        raise ToolError(format_validation_error(e)) from e


async def _run(ctx: Context, fn: Callable, **kwargs) -> str:
    request = ctx.request_context.request
    if request is None:
        raise ToolError("No HTTP request context; this server needs the HTTP transport.")
    try:
        caller = await run_in_threadpool(caller_from_headers, request.headers)
    except ServiceError as e:
        raise ToolError(format_error(e)) from e
    # The DB layer is synchronous; run it in a worker thread so one slow query
    # doesn't freeze every other MCP request on the event loop.
    return await run_in_threadpool(_execute, fn, caller, kwargs)


# ---------- registration (docstrings are what Claude reads to pick a tool) ----------

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_projects(ctx: Context) -> str:
        """List the projects you belong to, with project_id and your role.
        Call this first if you don't know the project_id."""
        return await _run(ctx, op_list_projects)

    @mcp.tool()
    async def get_project_state(project_id: int, ctx: Context) -> str:
        """Get open tasks, recent decisions, the latest handoff and the list of
        unverified items. Call at the start of every session."""
        return await _run(ctx, op_get_project_state, project_id=project_id)

    @mcp.tool()
    async def create_task(project_id: int, title: str, ctx: Context,
                          description: str | None = None, agent: str | None = None,
                          commit_sha: str | None = None) -> str:
        """Create a new task (starts as 'todo', provenance 'asserted')."""
        return await _run(ctx, op_create_task, project_id=project_id, title=title,
                          description=description, agent=agent, commit_sha=commit_sha)

    @mcp.tool()
    async def update_task(project_id: int, task_id: int, version: int, ctx: Context,
                          title: str | None = None, description: str | None = None,
                          state: Literal["todo", "in_progress", "done"] | None = None,
                          agent: str | None = None, commit_sha: str | None = None) -> str:
        """Update a task. `version` must be the version you last read; if someone
        else changed the task meanwhile you get a VERSION CONFLICT and nothing is
        written. Any edit resets provenance to 'asserted'."""
        return await _run(ctx, op_update_task, project_id=project_id, task_id=task_id,
                          version=version, title=title, description=description,
                          state=state, agent=agent, commit_sha=commit_sha)

    @mcp.tool()
    async def record_decision(project_id: int, topic: str, decision: str, ctx: Context,
                              rationale: str | None = None, agent: str | None = None,
                              commit_sha: str | None = None) -> str:
        """Record a decision with its topic and rationale so other accounts can find it."""
        return await _run(ctx, op_record_decision, project_id=project_id, topic=topic,
                          decision=decision, rationale=rationale, agent=agent,
                          commit_sha=commit_sha)

    @mcp.tool()
    async def save_handoff(project_id: int, summary: str, ctx: Context,
                           completed: list[str] | None = None,
                           blockers: list[str] | None = None,
                           open_questions: list[str] | None = None,
                           files_touched: list[str] | None = None,
                           last_commit_sha: str | None = None,
                           verification_status: Literal["verified", "partial", "unverified"] = "unverified",
                           next_action: str | None = None,
                           agent: str | None = None) -> str:
        """Save an end-of-session handoff. Be honest in verification_status: use
        'verified' only if the work was actually tested or committed."""
        return await _run(ctx, op_save_handoff, project_id=project_id, summary=summary,
                          completed=completed, blockers=blockers,
                          open_questions=open_questions, files_touched=files_touched,
                          last_commit_sha=last_commit_sha,
                          verification_status=verification_status,
                          next_action=next_action, agent=agent)

    @mcp.tool()
    async def list_changes(project_id: int, ctx: Context, since: str | None = None,
                           limit: int = 20) -> str:
        """List recent change events, newest first. `since` is an ISO-8601
        timestamp with timezone, e.g. 2026-10-14T00:00:00+00:00."""
        return await _run(ctx, op_list_changes, project_id=project_id,
                          since=since, limit=limit)


"""Why: Each tool follows the same recipe. It checks identity, then permission through access.get_ctx, then calls the same service function the REST route calls, then wraps the output. The permission checks are the same code REST uses.
I split tools into two layers on purpose. The op_* functions are plain Python, so tests need no HTTP. The register() wrappers only handle MCP plumbing. Your Phase 4 “does web see what Code saved” tests will mostly exercise the op_* path.
The ctx: Context parameter sits before the optional ones because Python requires non-default parameters first. FastMCP injects it and hides it from Claude."""