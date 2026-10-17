import os
import sys
from dotenv import load_dotenv
from sqlalchemy import select, func

# Allow running as a script: make backend modules importable
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

load_dotenv(os.path.join(parent_dir, ".env"))

from db import SessionLocal
from app.models import User, Project, ProjectMember, Task, Decision, Event, Handoff

ROLES = ("owner", "editor", "viewer")


def load_seed_users() -> list[dict]:
    """SEED_USERS='email:name:role,email:name:role' read from backend/.env."""
    users = []
    for pair in (p.strip() for p in os.environ.get("SEED_USERS", "").split(",")):
        if not pair:
            continue
        parts = [x.strip() for x in pair.split(":")]
        if len(parts) != 3 or not parts[0] or not parts[1] or parts[2] not in ROLES:
            raise ValueError("SEED_USERS must look like 'email:name:role,email:name:role' "
                             f"with role in {ROLES}")
        users.append({"email": parts[0].lower(), "display_name": parts[1], "role": parts[2]})
    if not users:
        raise ValueError("SEED_USERS is empty - set it in backend/.env")
    if not any(u["role"] == "owner" for u in users):
        raise ValueError("SEED_USERS needs at least one owner")
    return users


def seed():
    seed_users = load_seed_users()
    owner_email = next(u["email"] for u in seed_users if u["role"] == "owner")

    with SessionLocal() as session:
        print("Starting database seeding...")

        # 1. Users (emails are stored lowercase to satisfy the check constraint)
        users = {}
        for u in seed_users:
            user = session.scalars(select(User).where(User.email == u["email"])).one_or_none()
            if not user:
                user = User(email=u["email"], display_name=u["display_name"])
                session.add(user)
                session.flush()
            users[u["email"]] = user

        # 2. Project
        project_name = "Bimo Core"
        project = session.scalars(select(Project).where(Project.name == project_name)).one_or_none()
        if not project:
            project = Project(name=project_name)
            session.add(project)
            session.flush()

        # 3. Memberships (role comes from SEED_USERS)
        for u in seed_users:
            user = users[u["email"]]
            member = session.scalars(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == user.id,
                )
            ).one_or_none()
            if not member:
                session.add(ProjectMember(project_id=project.id, user_id=user.id, role=u["role"]))

        # 4. Sample records, attributed to the owner
        owner_id = users[owner_email].id

        if not session.scalars(select(Task).where(Task.project_id == project.id)).first():
            session.add(Task(
                project_id=project.id,
                created_by=owner_id,
                title="Initialize database schema",
                description="Set up SQLAlchemy 2.0 and Alembic migrations.",
                state="done",
                provenance="asserted",
                surface="web",
            ))

        if not session.scalars(select(Decision).where(Decision.project_id == project.id)).first():
            session.add(Decision(
                project_id=project.id,
                created_by=owner_id,
                topic="Database ORM",
                decision="Use SQLAlchemy 2.0 with Mapped annotations.",
                rationale="Provides type safety and explicit failure modes.",
                provenance="asserted",
                surface="code",
            ))

        if not session.scalars(select(Event).where(Event.project_id == project.id)).first():
            session.add(Event(
                project_id=project.id,
                user_id=owner_id,
                surface="web",
                type="project_initialized",
                payload={"status": "success"},
            ))

        if not session.scalars(select(Handoff).where(Handoff.project_id == project.id)).first():
            session.add(Handoff(
                project_id=project.id,
                created_by=owner_id,
                summary="Initial database schema, core models, and seed script successfully established.",
                completed=["Database models defined", "Alembic migrations configured", "Seed script written"],
                blockers=[],
                open_questions=["How to handle concurrent version updates in Phase 2?"],
                files_touched=["backend/models.py", "backend/scripts/seed.py"],
                verification_status="verified",
                next_action="Implement Phase 2 conflict detection logic.",
            ))

        session.commit()

        total_users = session.scalar(select(func.count()).select_from(User))
        total_members = session.scalar(select(func.count()).select_from(ProjectMember))
        print("Seeding complete successfully!")
        print(f"Summary -> Users in DB: {total_users} | Project Memberships: {total_members}")

if __name__ == "__main__":
    seed()