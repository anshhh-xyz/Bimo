from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import User, ProjectMember
from app.schemas import MemberAdd
from app.services.events import log_event


def _out(m: ProjectMember, u: User) -> dict:
    return {"user_id": u.id, "email": u.email, "display_name": u.display_name,
            "role": m.role, "created_at": m.created_at}


def _lock_owners(session, project_id: int) -> list[ProjectMember]:
    """Lock the owner rows so two concurrent demotions can't both pass
    the 'last owner' check."""
    return list(session.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id,
               ProjectMember.role == "owner")
        .with_for_update()))


def list_members(session, project_id: int) -> list[dict]:
    rows = session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at, User.id)).all()
    return [_out(m, u) for m, u in rows]


def add_member(session, ctx, data: MemberAdd) -> dict:
    email = data.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(404, f"No Bimo user with email {email}. "
                                 "They must have an account first.")
    if session.get(ProjectMember, (ctx.project_id, user.id)):
        raise HTTPException(409, "Already a member; use PATCH to change role")

    m = ProjectMember(project_id=ctx.project_id, user_id=user.id, role=data.role)
    session.add(m)
    try:
        session.flush()
    except IntegrityError:  # concurrent add of the same user
        session.rollback()
        raise HTTPException(409, "Already a member")
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="member_added",
              payload={"user_id": user.id, "email": email, "role": data.role})
    session.commit()
    session.refresh(m)
    return _out(m, user)


def change_role(session, ctx, user_id: int, new_role: str) -> dict:
    owners = _lock_owners(session, ctx.project_id)
    m = session.get(ProjectMember, (ctx.project_id, user_id))
    if m is None:
        raise HTTPException(404, "Not a member of this project")
    user = session.get(User, user_id)
    if m.role == new_role:
        return _out(m, user)
    if m.role == "owner" and new_role != "owner" and len(owners) <= 1:
        raise HTTPException(409, "Cannot demote the last owner")

    old = m.role
    m.role = new_role
    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="member_role_changed",
              payload={"user_id": user_id, "old_role": old, "new_role": new_role})
    session.commit()
    session.refresh(m)
    return _out(m, user)


def remove_member(session, ctx, user_id: int) -> None:
    owners = _lock_owners(session, ctx.project_id)
    m = session.get(ProjectMember, (ctx.project_id, user_id))
    if m is None:
        raise HTTPException(404, "Not a member of this project")
    if m.role == "owner" and len(owners) <= 1:
        raise HTTPException(409, "Cannot remove the last owner")

    log_event(session, project_id=ctx.project_id, user_id=ctx.user.id,
              surface=ctx.surface, type="member_removed",
              payload={"user_id": user_id, "role": m.role})
    session.delete(m)
    session.commit()