from fastapi import APIRouter, Depends
from app.auth import current_actor, require_member
from app.db import get_session
from app.schemas import ProjectCreate, ProjectOut, StateOut, SummaryOut, SummaryUpdate
from app.services import projects as project_svc
from app.services.state import build_state

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, actor=Depends(current_actor),
                   session=Depends(get_session)):
    return project_svc.create_project(session, actor, body)


@router.patch("/{project_id}/summary", response_model=SummaryOut)
def update_summary(project_id: int, body: SummaryUpdate,
                   ctx=Depends(require_member("editor")), session=Depends(get_session)):
    return project_svc.update_summary(session, ctx, body)


@router.get("/{project_id}/state", response_model=StateOut)
def get_state(project_id: int, ctx=Depends(require_member("viewer")),
              session=Depends(get_session)):
    return build_state(session, project_id)