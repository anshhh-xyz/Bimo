from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
#what api accepts and returns
Provenance = Literal["verified", "asserted", "unverified"]
TaskState = Literal["todo", "in_progress", "done"]
VerificationStatus = Literal["verified", "partial", "unverified"]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- tasks
class TaskCreate(In):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    agent: str | None = None
    commit_sha: str | None = None


class TaskUpdate(In):
    version: int
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    state: TaskState | None = None
    agent: str | None = None
    commit_sha: str | None = None


class TaskOut(Out):
    id: int
    project_id: int
    title: str
    description: str | None
    state: str
    provenance: Provenance
    created_by: int
    surface: str | None
    agent: str | None
    commit_sha: str | None
    verified_by: int | None
    verified_at: datetime | None
    version: int
    updated_at: datetime | None

#--- summary
class SummaryUpdate(In):
    summary: str = Field(min_length=1, max_length=4000)
    version: int


class SummaryOut(Out):
    summary: str | None
    summary_version: int

# ---- decisions
class DecisionCreate(In):
    topic: str = Field(min_length=1, max_length=255)
    decision: str = Field(min_length=1)
    rationale: str | None = None
    agent: str | None = None
    commit_sha: str | None = None


class DecisionOut(Out):
    id: int
    project_id: int
    topic: str
    decision: str
    rationale: str | None
    provenance: Provenance
    created_by: int
    surface: str | None
    agent: str | None
    commit_sha: str | None
    verified_by: int | None
    verified_at: datetime | None
    version: int
    created_at: datetime
    superseded_by: int | None = None

class ConflictItem(BaseModel):
    kind: Literal["task", "decision_topic"]
    label: str
    detail: dict[str, Any]

# ---- handoffs
class HandoffCreate(In):
    summary: str = Field(min_length=1)
    completed: list[str] = []
    blockers: list[str] = []
    open_questions: list[str] = []
    files_touched: list[str] = []
    last_commit_sha: str | None = None
    verification_status: VerificationStatus = "unverified"
    next_action: str | None = None
    agent: str | None = None


class HandoffOut(Out):
    id: int
    project_id: int
    created_by: int
    surface: str | None
    agent: str | None
    provenance: Provenance
    summary: str
    completed: list[Any]
    blockers: list[Any]
    open_questions: list[Any]
    files_touched: list[Any]
    last_commit_sha: str | None
    verification_status: str
    next_action: str | None
    created_at: datetime


# ---- events / state
class EventOut(Out):
    id: int
    user_id: int | None
    surface: str | None
    agent: str | None = None
    type: str
    payload: dict[str, Any]
    created_at: datetime


class UnverifiedItem(BaseModel):
    kind: Literal["task", "decision"]
    id: int
    label: str
    provenance: Provenance


class StateOut(BaseModel):
    conflicts: list[ConflictItem] = []
    summary: str | None = None
    summary_version: int = 1
    open_tasks: list[TaskOut]
    recent_decisions: list[DecisionOut]
    latest_handoff: HandoffOut | None
    unverified: list[UnverifiedItem]

# ---- members
MemberRole = Literal["viewer", "editor", "owner"]


class MemberAdd(In):
    email: str = Field(min_length=3, max_length=255)
    role: MemberRole = "viewer"


class MemberRoleUpdate(In):
    role: MemberRole


class MemberOut(Out):
    user_id: int
    email: str
    display_name: str | None
    role: str
    created_at: datetime

"""Why separate schemas from models? 
The database may contain internal fields that you don't want to accept from a client or expose in a response. 
Schemas let you control that boundary."""