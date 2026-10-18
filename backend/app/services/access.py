from dataclasses import dataclass
from sqlalchemy import select
from app.models import Project, ProjectMember, User
from app.services.errors import Forbidden, InvalidInput, Unauthorized

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
SURFACES = {"web", "code", "github"}


@dataclass
class Ctx:
    user: User
    project_id: int
    role: str
    surface: str
    agent: str | None = None   # which client wrote this (derived server-side)

@dataclass
class Actor:
    """Who is acting when there is no project yet, so there is no role to check."""
    user: User
    surface: str
    agent: str | None = None

def get_user(session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise Unauthorized("Unknown user")
    return user


def get_ctx(session, user_id: int, project_id: int,
            surface: str = "web", min_role: str = "viewer",
            agent: str | None = None) -> Ctx:
    """The one permission check. Same order as before: 401, then 403, then 422."""
    user = get_user(session, user_id)
    member = session.scalar(
        select(ProjectMember)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(ProjectMember.project_id == project_id,
               ProjectMember.user_id == user.id,
               Project.deleted_at.is_(None)))
    if member is None or ROLE_RANK.get(member.role, 0) < ROLE_RANK[min_role]:
        raise Forbidden("Not allowed on this project")
    if surface not in SURFACES:
        raise InvalidInput("surface must be web, code or github")
    return Ctx(user=user, project_id=project_id,
               role=member.role, surface=surface, agent=agent)

def get_actor(session, user_id: int, surface: str = "web",
              agent: str | None = None) -> Actor:
    """Identity check for actions that are not tied to an existing project
    (creating one). Same order as get_ctx: 401, then 422."""
    user = get_user(session, user_id)
    if surface not in SURFACES:
        raise InvalidInput("surface must be web, code or github")
    return Actor(user=user, surface=surface, agent=agent)

def list_projects(session, user_id: int) -> list[dict]:
    rows = session.execute(
        select(Project.id, Project.name, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id,
               Project.deleted_at.is_(None))
        .order_by(Project.id)).all()
    return [{"id": r.id, "name": r.name, "role": r.role} for r in rows]

"""The permission logic used to live inside a FastAPI dependency,
 where MCP couldn’t reach it. Now it’s a plain function. 
 list_projects lets Claude discover which project ids it may use."""
