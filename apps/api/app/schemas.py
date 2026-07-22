from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    PATIENT = "patient"
    CLINICIAN = "clinician"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class Urgency(str, Enum):
    EMERGENCY = "Emergency"
    SAME_DAY = "Same-Day"
    ROUTINE = "Routine"
    SELF_CARE = "Self-Care"


URGENCY_RANK = {
    Urgency.SELF_CARE: 0,
    Urgency.ROUTINE: 1,
    Urgency.SAME_DAY: 2,
    Urgency.EMERGENCY: 3,
}


class ReasonCode(str, Enum):
    DETERMINISTIC_RED_FLAG = "DETERMINISTIC_RED_FLAG"
    AGENT_DISAGREEMENT = "AGENT_DISAGREEMENT"
    CRITIC_DISPROVED_LOW_RISK = "CRITIC_DISPROVED_LOW_RISK"
    MISSING_CRITICAL_FACT = "MISSING_CRITICAL_FACT"
    LOW_RETRIEVAL_QUALITY = "LOW_RETRIEVAL_QUALITY"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    TWO_KEY_APPROVED = "TWO_KEY_APPROVED"


class User(BaseModel):
    id: str
    tenant_id: str
    email: str
    name: str
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class LoginRequest(BaseModel):
    email: str
    password: str


class ProvenanceLink(BaseModel):
    schema_version: str = "1.0"
    source_id: str
    source_type: Literal["patient", "clinician", "retrieval", "inference"]
    label: str
    quote: str | None = None


class EvidenceCitation(BaseModel):
    schema_version: str = "1.0"
    source_id: str
    title: str
    version: str
    excerpt: str
    jurisdiction: str = "demo"
    retrieval_score: float = Field(ge=0, le=1)


class TriageProposal(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str
    urgency: Urgency
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    rationale_summary: str
    missing_critical_facts: list[str] = []
    citations: list[EvidenceCitation] = []


class SafetyCritique(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str
    proposed_urgency: Urgency
    risk_found: bool
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[ReasonCode] = []
    summary: str


class RedFlagMatch(BaseModel):
    rule_id: str
    rule_version: str
    severity: Urgency
    matched_evidence: str
    recommended_action: str


class GateDecision(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str = "deterministic-safety-gate"
    confidence: float = Field(default=1.0, ge=0, le=1)
    uncertainty: float = Field(default=0.0, ge=0, le=1)
    citations: list[EvidenceCitation] = []
    urgency: Urgency
    approved_low_risk: bool
    escalated: bool
    reason_codes: list[ReasonCode]
    summary: str


class UncertaintyMap(BaseModel):
    schema_version: str = "1.0"
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str = "deterministic-intake"
    confidence: float = Field(default=1.0, ge=0, le=1)
    citations: list[EvidenceCitation] = []
    known_facts: list[str]
    missing_facts: list[str]
    contradictions: list[str]
    red_flags: list[RedFlagMatch]
    retrieval_quality: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)


class SoapSentence(BaseModel):
    schema_version: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    confidence: float = Field(ge=0, le=1)
    provenance: list[ProvenanceLink]

    @field_validator("provenance")
    @classmethod
    def provenance_required(cls, value: list[ProvenanceLink]) -> list[ProvenanceLink]:
        if not value:
            raise ValueError("Every SOAP sentence requires provenance")
        return value


class SoapDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["draft", "signed"] = "draft"
    sections: dict[str, list[SoapSentence]]
    updated_at: datetime = Field(default_factory=utcnow)
    signed_at: datetime | None = None


class OrchestrationRun(BaseModel):
    schema_version: str = "1.0"
    provider: str
    workflow_id: str | None = None
    execution_id: str | None = None
    status: Literal["completed", "failed", "bypassed"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    error_code: str | None = None


class EncounterCreate(BaseModel):
    scenario_id: str | None = None


class ConsentRequest(BaseModel):
    accepted: bool
    version: str = "demo-v1"


class IngestRequest(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    input_type: Literal["text", "voice-transcript"] = "text"


class AnswerRequest(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=1000)


class TeachBackRequest(BaseModel):
    answer: str


class SoapPatchRequest(BaseModel):
    sections: dict[str, list[str]]


class ResolutionRequest(BaseModel):
    note: str = Field(min_length=5, max_length=2000)


class EncounterView(BaseModel):
    id: str
    tenant_id: str
    patient_id: str
    patient_name: str
    scenario_id: str | None
    status: str
    created_at: datetime
    consent: dict[str, Any]
    transcript: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    answers: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    triage: TriageProposal | None = None
    critic: SafetyCritique | None = None
    gate: GateDecision | None = None
    uncertainty_map: UncertaintyMap | None = None
    soap: SoapDraft | None = None
    orchestration: OrchestrationRun | None = None
    guidance: dict[str, Any] | None = None
    teach_back: dict[str, Any] | None = None


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    encounter_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    payload: dict[str, Any] = {}
