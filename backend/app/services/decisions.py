from app.models import Decision
from app.schemas import DecisionCreate
from app.services.events import log_event


def create_decision(session, ctx, data: DecisionCreate) -> Decision:
    d = Decision(project_id=ctx.project_id, topic=data.topic,
                 decision=data.decision, rationale=data.rationale,
                 agent=data.agent or ctx.agent, commit_sha=data.commit_sha,
                 provenance="asserted", created_by=ctx.user.id,
                 surface=ctx.surface, version=1)
    session.add(d)
    session.flush()
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, agent=ctx.agent, type="decision_recorded",
              payload={"decision_id": d.id, "topic": d.topic})
    session.commit()
    session.refresh(d)
    return d