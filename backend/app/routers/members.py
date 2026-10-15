from fastapi import APIRouter, Depends, Response
from app.auth import require_member
from app.db import get_session
from app.schemas import MemberAdd, MemberRoleUpdate, MemberOut
from app.services import members as svc

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
def list_(project_id: int, ctx=Depends(require_member("viewer")),
          session=Depends(get_session)):
    return svc.list_members(session, project_id)


@router.post("", response_model=MemberOut, status_code=201)
def add(project_id: int, body: MemberAdd,
        ctx=Depends(require_member("owner")), session=Depends(get_session)):
    return svc.add_member(session, ctx, body)


@router.patch("/{user_id}", response_model=MemberOut)
def change_role(project_id: int, user_id: int, body: MemberRoleUpdate,
                ctx=Depends(require_member("owner")), session=Depends(get_session)):
    return svc.change_role(session, ctx, user_id, body.role)


@router.delete("/{user_id}", status_code=204)
def remove(project_id: int, user_id: int,
           ctx=Depends(require_member("owner")), session=Depends(get_session)):
    svc.remove_member(session, ctx, user_id)
    return Response(status_code=204)