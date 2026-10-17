from sqlalchemy import select, update, func
from app.models import Project
from app.schemas import SummaryUpdate, SummaryOut
from app.services.errors import ConflictError, NotFound
from app.services.events import log_event


def update_summary(session, ctx, data: SummaryUpdate) -> Project:
    old_len = session.scalar(
        select(func.char_length(Project.summary)).where(Project.id == ctx.project_id)) or 0

    # Atomic: only succeeds if the version still matches.
    stmt = (
        update(Project)
        .where(Project.id == ctx.project_id,
               Project.summary_version == data.version)
        .values(summary=data.summary,
                summary_version=Project.summary_version + 1)
        .returning(Project)
        .execution_options(populate_existing=True)
    )
    project = session.execute(stmt).scalar_one_or_none()

    if project is None:
        current = session.scalar(
            select(Project).where(Project.id == ctx.project_id)
            .execution_options(populate_existing=True))
        if current is None:
            raise NotFound("Project not found")
        log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
                  surface=ctx.surface, agent=ctx.agent, type="conflict_rejected",
                  payload={"what": "summary", "sent_version": data.version,
                           "current_version": current.summary_version})
        session.commit()
        raise ConflictError(
            SummaryOut.model_validate(current).model_dump(mode="json"))

    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, agent=ctx.agent, type="summary_updated",
              payload={"old_length": old_len, "new_length": len(data.summary),
                       "new_version": project.summary_version})
    session.commit()
    return project