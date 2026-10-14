from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_member
from app.db import get_session
from app.schemas import HandoffCreate, HandoffOut
from app.services import handoffs as svc

router = APIRouter(prefix="/projects/{project_id}/handoffs", tags=["handoffs"])

@router.post("", response_model=HandoffOut, status_code=201)
def save(project_id: int, body: HandoffCreate,
         ctx=Depends(require_member("editor")), session=Depends(get_session)):
    return svc.create_handoff(session, ctx, body)

@router.get("/latest", response_model=HandoffOut)
def latest(project_id: int, ctx=Depends(require_member("viewer")),
           session=Depends(get_session)):
    h = svc.latest_handoff(session, project_id)
    if h is None:
        raise HTTPException(404, "No handoff yet")
    return h