from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.auth import require_member
from app.db import get_session
from app.schemas import EventOut
from app.services import events as svc

router = APIRouter(prefix="/projects/{project_id}/changes", tags=["changes"])


@router.get("", response_model=list[EventOut])
def list_changes(project_id: int, since: datetime | None = None,
                 limit: int = Query(50, ge=1, le=200),
                 ctx=Depends(require_member("viewer")),
                 session=Depends(get_session)):
    return svc.list_changes(session, project_id, since, limit)