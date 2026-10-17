from datetime import datetime, timezone

from sqlalchemy import select

from app.config import allow_self_verify
from app.models import Decision, Task
from app.schemas import DecisionOut, TaskOut
from app.services.errors import ConflictError, Forbidden, InvalidInput, NotFound
from app.services.events import log_event

MODELS = {"task": Task, "decision": Decision}
OUT = {"task": TaskOut, "decision": DecisionOut}


def item_out(kind: str, row) -> dict:
    return OUT[kind].model_validate(row).model_dump(mode="json")


def _fail(session, exc: Exception):
    """Release the row lock before raising."""
    session.rollback()
    raise exc


def verify_item(session, ctx, kind: str, item_id: int, version: int):
    """Owner marks an asserted task/decision as verified.
    ctx must come from get_ctx(..., min_role='owner').
    Rules: version must match what the owner read; the verifier cannot be the
    person who wrote or last edited the item (unless ALLOW_SELF_VERIFY=1)."""
    model = MODELS.get(kind)
    if model is None:
        raise InvalidInput("kind must be 'task' or 'decision'")

    row = session.scalar(
        select(model)
        .where(model.id == item_id, model.project_id == ctx.project_id)
        .with_for_update()
        .execution_options(populate_existing=True))
    if row is None:
        _fail(session, NotFound(f"{kind} not found"))

    if getattr(row, "superseded_by", None) is not None:
        _fail(session, InvalidInput("Decision is superseded; verify the active one"))

    if row.version != version:
        current = item_out(kind, row)
        _fail(session, ConflictError(current))

    if row.provenance == "verified":
        session.rollback()
        return row  # idempotent, no new event

    author = getattr(row, "updated_by", None) or row.created_by
    self_verified = author == ctx.user.id
    if self_verified and not allow_self_verify():
        _fail(session, Forbidden(
            "You cannot verify an item you wrote or last edited. Ask another owner "
            "(single-owner setups: set ALLOW_SELF_VERIFY=1)."))

    row.provenance = "verified"
    row.verified_by = ctx.user.id
    row.verified_at = datetime.now(timezone.utc)
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="item_verified",
              payload={"kind": kind, "id": item_id, "version": version,
                       "self_verified": self_verified})
    session.commit()
    session.refresh(row)
    return row