from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from app.auth import require_member
from app.db import get_session
from app.models import Event
from app.schemas import EventOut

router = APIRouter(prefix="/projects/{project_id}/changes", tags=["changes"])

@router.get("", response_model=list[EventOut])
def list_changes(project_id: int, since: datetime | None = None,
                 limit: int = Query(50, ge=1, le=200),
                 ctx=Depends(require_member("viewer")),
                 session=Depends(get_session)):
    q = select(Event).where(Event.project_id == project_id)
    if since:
        q = q.where(Event.created_at > since)
    return session.scalars(q.order_by(Event.created_at.desc()).limit(limit)).all()