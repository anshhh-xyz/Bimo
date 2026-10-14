from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import User, ProjectMember

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
                   user: User = Depends(get_current_user),
                   session: Session = Depends(get_session),
                   x_surface: str = Header("web")) -> Ctx:
        member = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id))
        if member is None or ROLE_RANK.get(member.role, 0) < ROLE_RANK[min_role]:
            raise HTTPException(403, "Not allowed on this project")
        if x_surface not in SURFACES:
            raise HTTPException(422, "X-Surface must be web, code or github")
        return Ctx(user=user, project_id=project_id,
                   role=member.role, surface=x_surface)
    return dependency