from datetime import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import JSONB
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        sa.String(50), nullable=False, server_default="member"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")

class Event(Base):
    """It’s the append-only log of everything that happens in a project: 
    a decision recorded, a task changed, a commit pushed.
    """
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"), 
        nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=True
    )
    surface: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    agent: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, 
        nullable=False, 
        server_default=sa.text("'{}'::jsonb")
    )
    type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    __table_args__ = (
        sa.CheckConstraint(
            "surface IN ('web', 'code', 'github')", 
            name="ck_events_surface"
        ),
        sa.Index("ix_events_project_created", "project_id", "created_at"),
    )


"""We chose this structure because it is the industry-standard relational database design for handling user-to-workspace 
permissions. Instead of packing user lists into a single text column or project lists into a user column (which violates database 
normalization rules), using a dedicated junction table (ProjectMember) allows you to query permissions cleanly, scale efficiently,
 and store relational metadata like roles."""

"""Mapped[str] handles the Python type side of things
mapped_column(unique=True, nullable=False) handles the database column constraints."""