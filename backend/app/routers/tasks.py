from fastapi import APIRouter, Depends
from app.auth import require_member
from app.db import get_session
from app.schemas import TaskCreate, TaskUpdate, TaskOut
from app.services import tasks as svc

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])

@router.post("", response_model=TaskOut, status_code=201)
def create(project_id: int, body: TaskCreate,
           ctx=Depends(require_member("editor")), session=Depends(get_session)):
    return svc.create_task(session, ctx, body)

@router.patch("/{task_id}", response_model=TaskOut)
def update(project_id: int, task_id: int, body: TaskUpdate,
           ctx=Depends(require_member("editor")), session=Depends(get_session)):
    return svc.update_task(session, ctx, task_id, body)