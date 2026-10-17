from typing import Literal

from fastapi import APIRouter, Depends

from app.auth import require_member
from app.db import get_session
from app.schemas import In
from app.services import conflicts as conflict_svc
from app.services import verification as verify_svc

router = APIRouter(prefix="/projects/{project_id}", tags=["verification"])


class VerifyIn(In):
    kind: Literal["task", "decision"]
    item_id: int
    version: int


class ResolveIn(In):
    note: str | None = None


@router.get("/conflicts")
def list_conflicts(project_id: int, ctx=Depends(require_member("viewer")),
                   session=Depends(get_session)):
    return conflict_svc.list_conflicts(session, project_id)


@router.post("/verify")
def verify(project_id: int, body: VerifyIn, ctx=Depends(require_member("owner")),
           session=Depends(get_session)):
    row = verify_svc.verify_item(session, ctx, body.kind, body.item_id, body.version)
    return verify_svc.item_out(body.kind, row)


@router.post("/conflicts/tasks/{task_id}/resolve")
def resolve_task(project_id: int, task_id: int, body: ResolveIn,
                 ctx=Depends(require_member("owner")), session=Depends(get_session)):
    return conflict_svc.resolve_task_conflict(session, ctx, task_id, body.note)


@router.post("/conflicts/decisions/{keep_decision_id}/resolve")
def resolve_decision(project_id: int, keep_decision_id: int, body: ResolveIn,
                     ctx=Depends(require_member("owner")), session=Depends(get_session)):
    return conflict_svc.resolve_decision_conflict(session, ctx, keep_decision_id, body.note)