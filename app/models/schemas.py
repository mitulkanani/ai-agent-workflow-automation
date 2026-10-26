from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class Decision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=5, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    comment: str | None = Field(default=None, max_length=500)


class PlannedStep(BaseModel):
    step_id: str
    tool_name: str
    description: str
    input: dict[str, Any]
    requires_approval: bool = False
    status: StepStatus = StepStatus.PENDING


class TraceEvent(BaseModel):
    timestamp: datetime
    event: str
    message: str
    step_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(BaseModel):
    run_id: UUID
    goal: str
    context: dict[str, Any]
    status: RunStatus
    plan: list[PlannedStep]
    trace: list[TraceEvent] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    pending_approval_step_id: str | None = None
    error: str | None = None


class WorkflowCreated(BaseModel):
    run_id: UUID
    status: RunStatus
    message: str
