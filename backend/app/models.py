from datetime import datetime
from typing import Optional , Any
from sqlalchemy.dialects.postgresql import JSONB
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from db import Base

#describes how data is stored

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

class Task(Base):
    """Represents a discrete task item within a project."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(
        sa.Integer, server_default="1", nullable=False
    )
    provenance: Mapped[str] = mapped_column(
        sa.String(50), server_default="asserted", nullable=False
    )
    surface: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    agent: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Task specific columns
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    state: Mapped[str] = mapped_column(
        sa.String(50), server_default="todo", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint(
            "provenance IN ('verified', 'asserted', 'unverified')",
            name="ck_tasks_provenance",
        ),
        sa.CheckConstraint(
            "surface IN ('web', 'code', 'github')",
            name="ck_tasks_surface",
        ),
        sa.CheckConstraint(
            "state IN ('todo', 'in_progress', 'done')",
            name="ck_tasks_state",
        ),
        sa.Index("ix_tasks_project_state", "project_id", "state"),
    )


class Decision(Base):
    """Represents a recorded architectural or project decision."""
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(
        sa.Integer, server_default="1", nullable=False
    )
    provenance: Mapped[str] = mapped_column(
        sa.String(50), server_default="asserted", nullable=False
    )
    surface: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    agent: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Decision specific columns
    topic: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    decision: Mapped[str] = mapped_column(sa.Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "provenance IN ('verified', 'asserted', 'unverified')",
            name="ck_decisions_provenance",
        ),
        sa.CheckConstraint(
            "surface IN ('web', 'code', 'github')",
            name="ck_decisions_surface",
        ),
        sa.Index("ix_decisions_project_topic", "project_id", "topic"),
    )


class Handoff(Base):
    """Represents a periodic project state handoff summary."""
    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(
        sa.Integer, server_default="1", nullable=False
    )
    provenance: Mapped[str] = mapped_column(
        sa.String(50), server_default="asserted", nullable=False
    )
    surface: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    agent: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Handoff specific columns
    summary: Mapped[str] = mapped_column(sa.Text, nullable=False)
    completed: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
    )
    blockers: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
    )
    open_questions: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
    )
    files_touched: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
    )
    last_commit_sha: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        sa.String(50), server_default="unverified", nullable=False
    )
    next_action: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "provenance IN ('verified', 'asserted', 'unverified')",
            name="ck_handoffs_provenance",
        ),
        sa.CheckConstraint(
            "surface IN ('web', 'code', 'github')",
            name="ck_handoffs_surface",
        ),
        sa.CheckConstraint(
            "verification_status IN ('verified', 'partial', 'unverified')",
            name="ck_handoffs_verification_status",
        ),
        sa.Index("ix_handoffs_project_created", "project_id", "created_at"),
    )

class OAuthClient(Base):
    """A client (e.g. Claude web) that registered itself via /register."""
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    client_name: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    redirect_uris: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OAuthCode(Base):
    """Short-lived, single-use authorization code. Only its hash is stored."""
    __tablename__ = "oauth_codes"

    code_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    redirect_uri: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code_challenge: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class OAuthToken(Base):
    """Access and refresh tokens. Only SHA-256 hashes are stored."""
    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    client_id: Mapped[str] = mapped_column(
        sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint("kind IN ('access', 'refresh')", name="ck_oauth_tokens_kind"),
        sa.Index("ix_oauth_tokens_user", "user_id"),
    )

"""OAuth needs three things remembered: which clients registered, which login codes are pending, and which tokens are live. 
Storing hashes means a leaked database dump doesn’t hand out working tokens."""

"""We chose this structure because it is the industry-standard relational database design for handling user-to-workspace 
permissions. Instead of packing user lists into a single text column or project lists into a user column (which violates database 
normalization rules), using a dedicated junction table (ProjectMember) allows you to query permissions cleanly, scale efficiently,
 and store relational metadata like roles."""

"""Mapped[str] handles the Python type side of things
mapped_column(unique=True, nullable=False) handles the database column constraints."""