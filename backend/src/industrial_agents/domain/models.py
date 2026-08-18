from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(StrEnum):
    CUSTOMER = "customer"
    ENGINEER = "engineer"
    ADMIN = "admin"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(StrEnum):
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"


class Evidence(BaseModel):
    document_id: str
    title: str
    section: str | None = None
    snippet: str
    score: float = Field(ge=0, le=1)
    version: str = "unknown"
    source_url: str | None = None
    access_scope: str = "internal"


class RagQuery(BaseModel):
    query: str
    knowledge_domain: Literal["diagnosis", "process", "quality", "maintenance"]
    machine_model: str | None = None
    alarm_codes: list[str] = Field(default_factory=list)
    tenant_id: str
    permission_labels: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    request_id: str
    run_id: str


class RagResult(BaseModel):
    status: Literal["success", "no_evidence", "input_required", "failed"]
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    title: str
    detail: str
    verification: str
    requires_confirmation: bool = True


class AgentFinding(BaseModel):
    agent: Literal[
        "fault_diagnosis",
        "process_optimization",
        "quality_analysis",
        "predictive_maintenance",
    ]
    status: AgentStatus
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    diagnosis: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TelemetryPoint(BaseModel):
    timestamp: datetime
    oil_temperature_c: float
    injection_pressure_mpa: float
    injection_speed_mm_s: float
    cycle_time_s: float
    servo_load_pct: float
    quality_score: float


class MachineContext(BaseModel):
    machine_id: str
    model: str
    status: Literal["running", "warning", "stopped", "maintenance"]
    alarm_codes: list[str] = Field(default_factory=list)
    mold_cycles: int
    active_batch: str
    telemetry: list[TelemetryPoint] = Field(default_factory=list)


class GraphRequest(BaseModel):
    request_id: str
    run_id: str
    thread_id: str
    tenant_id: str
    user_id: str
    role: Role
    machine_id: str
    query: str = Field(min_length=2, max_length=4000)


class GraphResponse(BaseModel):
    run_id: str
    status: RunStatus
    answer: str
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    findings: list[AgentFinding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_decision: Literal["allow", "restricted", "deny"] = Field(default="allow", exclude=True)
    safety_reason_codes: list[str] = Field(default_factory=list, exclude=True)


class RunEvent(BaseModel):
    id: str
    run_id: str
    type: Literal[
        "run.started",
        "node.started",
        "node.completed",
        "node.failed",
        "agent.completed",
        "citation",
        "run.input_required",
        "run.completed",
        "run.failed",
    ]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    node: str | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
