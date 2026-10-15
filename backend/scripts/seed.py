import os
import sys
from sqlalchemy import select, func

# Add parent directory to sys.path so backend modules can be imported directly when running as a script
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from db import SessionLocal
from app.models import User, Project, ProjectMember, Task, Decision, Event, Handoff

def seed():
    with SessionLocal() as session:
        print("Starting database seeding...")

        # 1. Users (3 users with lowercase emails to satisfy check constraints)
        user_data = [
            {"email": "alice@example.com", "display_name": "Alice Owner"},
            {"email": "bob@example.com", "display_name": "Bob Member"},
            {"email": "charlie@example.com", "display_name": "Charlie Member"},
        ]
        
        users = {}
        for u_info in user_data:
            existing_user = session.scalars(
                select(User).where(User.email == u_info["email"])
            ).one_or_none()
            
            if existing_user:
                users[u_info["email"]] = existing_user
            else:
                new_user = User(email=u_info["email"], display_name=u_info["display_name"])
                session.add(new_user)
                session.flush()  # Flush to generate the auto-incremented ID
                users[u_info["email"]] = new_user

        # 2. Project (1 project)
        project_name = "Bimo Core"
        project = session.scalars(
            select(Project).where(Project.name == project_name)
        ).one_or_none()
        
        if not project:
            project = Project(name=project_name)
            session.add(project)
            session.flush()

        # 3. Project Members (All 3 users: 1 owner, 2 members)
        members_data = [
            {"email": "alice@example.com", "role": "owner"},
            {"email": "bob@example.com", "role": "member"},
            {"email": "charlie@example.com", "role": "member"},
        ]
        
        for m_info in members_data:
            user = users[m_info["email"]]
            existing_member = session.scalars(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id, 
                    ProjectMember.user_id == user.id
                )
            ).one_or_none()
            
            if not existing_member:
                member = ProjectMember(
                    project_id=project.id, 
                    user_id=user.id, 
                    role=m_info["role"]
                )
                session.add(member)

        # 4. Sample records for Tasks, Decisions, Events, and Handoffs
        alice_id = users["alice@example.com"].id

        if not session.scalars(select(Task).where(Task.project_id == project.id)).first():
            session.add(Task(
                project_id=project.id,
                created_by=alice_id,
                title="Initialize database schema",
                description="Set up SQLAlchemy 2.0 and Alembic migrations.",
                state="done",
                provenance="asserted",
                surface="web"
            ))

        if not session.scalars(select(Decision).where(Decision.project_id == project.id)).first():
            session.add(Decision(
                project_id=project.id,
                created_by=alice_id,
                topic="Database ORM",
                decision="Use SQLAlchemy 2.0 with Mapped annotations.",
                rationale="Provides type safety and explicit failure modes.",
                provenance="asserted",
                surface="code"
            ))

        if not session.scalars(select(Event).where(Event.project_id == project.id)).first():
            session.add(Event(
                project_id=project.id,
                user_id=alice_id,
                surface="web",
                type="project_initialized",
                payload={"status": "success"}
            ))

        if not session.scalars(select(Handoff).where(Handoff.project_id == project.id)).first():
            session.add(Handoff(
                project_id=project.id,
                created_by=alice_id,
                summary="Initial database schema, core models, and seed script successfully established.",
                completed=["Database models defined", "Alembic migrations configured", "Seed script written"],
                blockers=[],
                open_questions=["How to handle concurrent version updates in Phase 2?"],
                files_touched=["backend/models.py", "backend/scripts/seed.py"],
                verification_status="verified",
                next_action="Implement Phase 2 conflict detection logic."
            ))

        # Commit everything as an all-or-nothing transaction
        session.commit()

        # Print a short summary using SQLAlchemy 2.0 scalar counts
        total_users = session.scalar(select(func.count()).select_from(User))
        total_members = session.scalar(select(func.count()).select_from(ProjectMember))
        
        print("Seeding complete successfully!")
        print(f"Summary -> Users in DB: {total_users} | Project Memberships: {total_members}")

if __name__ == "__main__":
    seed()