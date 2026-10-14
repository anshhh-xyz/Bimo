from fastapi import APIRouter, Depends
from app.auth import require_member
from app.db import get_session
from app.schemas import StateOut
from app.services.state import build_state

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("/{project_id}/state", response_model=StateOut)
def get_state(project_id: int, ctx=Depends(require_member("viewer")),
              session=Depends(get_session)):
    return build_state(session, project_id)