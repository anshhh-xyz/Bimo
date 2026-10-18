from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from app.models import Project, ProjectMember
from app.schemas import ProjectCreate, SummaryUpdate, SummaryOut
from app.services.errors import ConflictError, InvalidInput, NotFound, StateConflict
from app.services.events import log_event

# Must match the index name in models.py and the migration.
NAME_INDEX = "uq_projects_active_name"


def _name_taken(name: str) -> StateConflict:
    return StateConflict(f'A project named "{name}" already exists. Choose a different name.')


def _name_in_use(session, name: str) -> bool:
    """Case-insensitive match against live (not deleted) projects.
    Both sides go through Postgres lower() so it agrees with the unique index."""
    return session.scalar(
        select(Project.id)
        .where(func.lower(Project.name) == func.lower(name),
               Project.deleted_at.is_(None))
        .limit(1)) is not None


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

def create_project(session, actor, data: ProjectCreate) -> dict:
    """Create a project, make the caller its owner, and log it, as ONE transaction.
    If any step fails nothing is saved, so a project can never exist without an owner.
    The owner comes from the authenticated actor, never from the request body.
    Names are unique (ignoring case) among live projects."""
    # Friendly early check. The unique index below is the real guarantee.
    if _name_in_use(session, data.name):
        raise _name_taken(data.name)
    try:
        project = Project(name=data.name, summary=data.summary)
        session.add(project)
        session.flush()  # assigns project.id; the transaction stays open

        session.add(ProjectMember(project_id=project.id, user_id=actor.user.id,
                                  role="owner"))
        log_event(session, project_id=project.id, user_id=actor.user.id,
                  surface=actor.surface, agent=actor.agent, type="project_created",
                  payload={"name": project.name})
        session.commit()  # project + owner + event, or nothing
    except IntegrityError as e:
        session.rollback()
        # Two creates with the same name raced past the check above;
        # the database let only one through.
        if NAME_INDEX in str(e.orig):
            raise _name_taken(data.name) from e
        raise
    except Exception:
        session.rollback()
        raise

    session.refresh(project)  # loads server defaults (created_at, summary_version)
    return {"id": project.id, "name": project.name, "role": "owner",
            "summary": project.summary, "summary_version": project.summary_version,
            "created_at": project.created_at}


def delete_project(session, ctx, confirm_name: str) -> dict:
    """Soft delete: hide the project, keep every row and the event history.
    The caller must already be an owner (checked by get_ctx before we get here).
    confirm_name must equal the project name so a wrong id or a stray call
    cannot delete the wrong project. Deleting frees the name for reuse."""
    project = session.get(Project, ctx.project_id)
    if project is None or project.deleted_at is not None:
        raise NotFound("Project not found")
    if confirm_name.strip() != project.name:
        raise InvalidInput("confirm_name must exactly match the project name. "
                           "Nothing was deleted.")

    result = {"id": project.id, "name": project.name, "deleted": True}
    project.deleted_at = func.now()
    log_event(session, project_id=project.id, user_id=ctx.user.id,
              surface=ctx.surface, agent=ctx.agent, type="project_deleted",
              payload={"name": project.name})
    session.commit()
    return result