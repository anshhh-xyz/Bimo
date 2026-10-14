from sqlalchemy import select
from app.models import Task, Decision
from app.services.handoffs import latest_handoff

def build_state(session, project_id: int) -> dict:
    open_tasks = session.scalars(
        select(Task).where(Task.project_id == project_id, Task.state != "done")
        .order_by(Task.updated_at.desc())).all()
    decisions = session.scalars(
        select(Decision).where(Decision.project_id == project_id)
        .order_by(Decision.created_at.desc()).limit(10)).all()

    unverified = []
    for t in session.scalars(select(Task).where(
            Task.project_id == project_id, Task.provenance != "verified")):
        unverified.append({"kind": "task", "id": t.id,
                           "label": t.title, "provenance": t.provenance})
    for d in session.scalars(select(Decision).where(
            Decision.project_id == project_id, Decision.provenance != "verified")):
        unverified.append({"kind": "decision", "id": d.id,
                           "label": d.topic, "provenance": d.provenance})

    return {"open_tasks": open_tasks, "recent_decisions": decisions,
            "latest_handoff": latest_handoff(session, project_id),
            "unverified": unverified}