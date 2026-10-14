from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import User, ProjectMember
from app.services.access import Ctx
from app.services import access

ROLE_RANK = {"viewer": 1, "member": 2, "editor": 2, "owner": 3}
SURFACES = {"web", "code", "github"}


@dataclass
class Ctx:
    user: User
    project_id: int
    role: str
    surface: str


def get_current_user(x_user_id: int = Header(...),
                     session: Session = Depends(get_session)) -> User:
    user = session.get(User, x_user_id)
    if user is None:
        raise HTTPException(401, "Unknown user")
    return user


def require_member(min_role: str = "viewer"):
    def dependency(project_id: int,
                   x_user_id: int = Header(...),
                   x_surface: str = Header("web"),
                   session=Depends(get_session)) -> Ctx:
        return access.get_ctx(session, x_user_id, project_id, x_surface, min_role)
    return dependency