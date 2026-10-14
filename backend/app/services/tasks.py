from fastapi import HTTPException
from sqlalchemy import select, update, func
from app.errors import ConflictError
from app.models import Task
from app.schemas import TaskCreate, TaskUpdate, TaskOut
from app.services.events import log_event


def create_task(session, ctx, data: TaskCreate) -> Task:
    task = Task(project_id=ctx.project_id, title=data.title,
                description=data.description, state="todo",
                agent=data.agent, commit_sha=data.commit_sha,
                provenance="asserted", created_by=ctx.user.id,
                surface=ctx.surface, version=1)
    session.add(task)
    session.flush()  # get task.id
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="task_created",
              payload={"task_id": task.id, "title": task.title})
    session.commit()
    session.refresh(task)  # load server defaults (updated_at, etc.)
    return task


def update_task(session, ctx, task_id: int, data: TaskUpdate) -> Task:
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if not changes:
        raise HTTPException(422, "Nothing to update")

    # Atomic: only succeeds if the version still matches.
    stmt = (
        update(Task)
        .where(Task.id == task_id,
               Task.project_id == ctx.project_id,
               Task.version == data.version)
        .values(**changes,
                version=Task.version + 1,
                provenance="asserted",      # any edit demotes to asserted
                verified_by=None,
                verified_at=None,
                surface=ctx.surface,
                updated_at=func.now())
        .returning(Task)
        .execution_options(populate_existing=True)
    )
    task = session.execute(stmt).scalar_one_or_none()

    if task is None:
        current = session.scalar(
            select(Task).where(Task.id == task_id,
                               Task.project_id == ctx.project_id)
            .execution_options(populate_existing=True))
        if current is None:
            raise HTTPException(404, "Task not found")
        log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
                  surface=ctx.surface, type="conflict_rejected",
                  payload={"task_id": task_id,
                           "sent_version": data.version,
                           "current_version": current.version})
        session.commit()
        raise ConflictError(
            TaskOut.model_validate(current).model_dump(mode="json"))

    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="task_updated",
              payload={"task_id": task_id, "fields": list(changes),
                       "new_version": task.version})
    session.commit()
    return task