from sqlalchemy import select
from app.models import Handoff
from app.schemas import HandoffCreate
from app.services.events import log_event


def create_handoff(session, ctx, data: HandoffCreate) -> Handoff:
    fields = data.model_dump()
    fields["agent"] = fields["agent"] or ctx.agent
    h = Handoff(project_id=ctx.project_id, created_by=ctx.user.id,
                surface=ctx.surface, provenance="asserted", **fields)
    session.add(h)
    session.flush()
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, agent=ctx.agent, type="handoff_saved",
              payload={"handoff_id": h.id,
                       "last_commit_sha": h.last_commit_sha})
    session.commit()
    session.refresh(h)
    return h


def latest_handoff(session, project_id: int) -> Handoff | None:
    return session.scalar(
        select(Handoff).where(Handoff.project_id == project_id)
        .order_by(Handoff.created_at.desc(), Handoff.id.desc()).limit(1))