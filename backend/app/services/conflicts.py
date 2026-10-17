from collections import defaultdict

from sqlalchemy import select

from app.models import Decision, Event, Task
from app.services.errors import InvalidInput, NotFound
from app.services.events import log_event

SCAN_LIMIT = 1000  # how many recent events to look at


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


# ---- 7.1 concurrent edits -------------------------------------------------
def task_conflicts(session, project_id: int) -> list[dict]:
    """A task conflict is OPEN from a rejected stale write until the rejected
    user successfully edits that task again, or an owner resolves it.
    Only the latest rejection per task is tracked."""
    events = session.scalars(
        select(Event).where(
            Event.project_id == project_id,
            Event.type.in_(("conflict_rejected", "task_updated", "task_conflict_resolved")))
        .order_by(Event.id.desc()).limit(SCAN_LIMIT)).all()

    open_: dict[int, Event] = {}
    for e in reversed(events):  # oldest first
        tid = (e.payload or {}).get("task_id")
        if tid is None:
            continue
        if e.type == "conflict_rejected":
            open_[tid] = e
        elif e.type == "task_conflict_resolved":
            open_.pop(tid, None)
        elif e.type == "task_updated" and tid in open_ and e.user_id == open_[tid].user_id:
            open_.pop(tid)  # the loser retried successfully

    if not open_:
        return []
    titles = {t.id: t.title for t in session.scalars(
        select(Task).where(Task.project_id == project_id, Task.id.in_(list(open_))))}
    return [{
        "kind": "task",
        "label": titles.get(tid, f"task {tid}"),
        "detail": {"task_id": tid,
                   "rejected_user_id": e.user_id,
                   "sent_version": e.payload.get("sent_version"),
                   "current_version_at_rejection": e.payload.get("current_version"),
                   "at": e.created_at.isoformat() if e.created_at else None},
    } for tid, e in open_.items() if tid in titles]


# ---- 7.2 contradictory decisions -----------------------------------------
def _active_decisions(session, project_id: int) -> list[Decision]:
    return list(session.scalars(
        select(Decision).where(Decision.project_id == project_id,
                               Decision.superseded_by.is_(None))
        .order_by(Decision.id)).all())


def decision_conflicts(session, project_id: int) -> list[dict]:
    """Same topic (case/space-insensitive), 2+ active decisions with different text."""
    groups = defaultdict(list)
    for d in _active_decisions(session, project_id):
        groups[_norm(d.topic)].append(d)
    out = []
    for ds in groups.values():
        if len({_norm(d.decision) for d in ds}) < 2:
            continue
        out.append({
            "kind": "decision_topic",
            "label": ds[-1].topic,
            "detail": {"decision_ids": [d.id for d in ds],
                       "positions": [{"decision_id": d.id, "decision": d.decision,
                                      "created_by": d.created_by, "surface": d.surface,
                                      "agent": d.agent,
                                      "created_at": d.created_at.isoformat() if d.created_at else None}
                                     for d in ds]},
        })
    return out


def list_conflicts(session, project_id: int) -> list[dict]:
    return task_conflicts(session, project_id) + decision_conflicts(session, project_id)


# ---- 7.3 resolve actions (ctx must be owner) -----------------------------
def resolve_task_conflict(session, ctx, task_id: int, note: str | None = None) -> dict:
    task = session.scalar(select(Task).where(Task.id == task_id,
                                             Task.project_id == ctx.project_id))
    if task is None:
        raise NotFound("Task not found")
    if not any(c["detail"]["task_id"] == task_id for c in task_conflicts(session, ctx.project_id)):
        raise InvalidInput("No open conflict on this task")
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="task_conflict_resolved",
              payload={"task_id": task_id, "note": note})
    session.commit()
    return {"resolved": "task", "task_id": task_id}


def resolve_decision_conflict(session, ctx, keep_decision_id: int,
                              note: str | None = None) -> dict:
    keep = session.scalar(select(Decision).where(Decision.id == keep_decision_id,
                                                 Decision.project_id == ctx.project_id))
    if keep is None:
        raise NotFound("Decision not found")
    if keep.superseded_by is not None:
        raise InvalidInput("That decision is already superseded; pick an active one")
    key = _norm(keep.topic)
    others = [d for d in _active_decisions(session, ctx.project_id)
              if d.id != keep.id and _norm(d.topic) == key]
    if not others:
        raise InvalidInput("No competing decisions on this topic")
    for d in others:
        d.superseded_by = keep.id
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="decision_conflict_resolved",
              payload={"topic": keep.topic, "kept": keep.id,
                       "superseded": [d.id for d in others], "note": note})
    session.commit()
    return {"resolved": "decision_topic", "kept": keep.id,
            "superseded": [d.id for d in others]}