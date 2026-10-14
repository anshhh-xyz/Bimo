from fastapi import APIRouter, Depends
from app.auth import require_member
from app.db import get_session
from app.schemas import DecisionCreate, DecisionOut
from app.services import decisions as svc

router = APIRouter(prefix="/projects/{project_id}/decisions", tags=["decisions"])

@router.post("", response_model=DecisionOut, status_code=201)
def create(project_id: int, body: DecisionCreate,
           ctx=Depends(require_member("editor")), session=Depends(get_session)):
    return svc.create_decision(session, ctx, body)