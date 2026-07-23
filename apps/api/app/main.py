from __future__ import annotations

import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agents.providers import get_agent_provider, get_retrieval_provider
from .auth import create_token, current_user, require_roles, verify_password
from .core import configure_logging, get_settings
from .database import database_ready, initialize_database
from .event_bus import get_event_transport
from .mcp_ops import OpsMcpAdapter
from .orchestration import LyzrSuperFlowOrchestrator, OrchestrationError
from .rules import RedFlagEngine
from .schemas import (
    AnswerRequest,
    ConsentRequest,
    EncounterCreate,
    EncounterView,
    IngestRequest,
    LoginRequest,
    ResolutionRequest,
    Role,
    SignupRequest,
    SoapPatchRequest,
    TeachBackRequest,
    TokenResponse,
    TriageProposal,
    Urgency,
    User,
)
from .services import EncounterService
from .store import Store


settings = get_settings()
configure_logging()
store = Store()
rules = RedFlagEngine()
encounters = EncounterService(store, rules)
ops_mcp = OpsMcpAdapter()
ws_tickets: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="CareRelay API",
    version="0.1.0",
    description="Clinical decision-support prototype: urgency guidance and documentation drafts only.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail), "request_id": request.headers.get("x-request-id", "local"), "details": {}}},
    )


def encounter_for(user: User, encounter_id: str) -> EncounterView:
    encounter = store.get_encounter(user.tenant_id, encounter_id)
    if not encounter:
        raise HTTPException(404, "Encounter not found")
    if user.role == Role.PATIENT and encounter.patient_id != user.id:
        raise HTTPException(403, "Encounter belongs to another patient")
    return encounter


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "carerelay-api"}


@app.get("/api/v1/ready")
def ready():
    database = database_ready()
    orchestration = encounters.orchestrator.status()
    orchestrator_ready = bool(orchestration.get("ready"))
    return {
        "ready": database and (orchestrator_ready or not settings.require_live_orchestration),
        "database": database,
        "event_transport": get_event_transport().status(),
        "retrieval": {"configured": settings.retrieval_provider, "fallback": "in-memory-hybrid"},
        "orchestration": orchestration,
    }


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    record = store.find_user(payload.email.lower())
    if not record or not verify_password(payload.password, record.password_hash):
        raise HTTPException(401, "Invalid email or password")
    user = store.user_view(record)
    return TokenResponse(access_token=create_token(user), user=user)


@app.post("/api/v1/auth/signup", response_model=TokenResponse, status_code=201)
def signup(payload: SignupRequest):
    """Public registration creates a patient account only; staff roles stay provisioned."""
    try:
        user = store.create_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
            role=Role.PATIENT,
        )
    except ValueError as exc:
        if str(exc) == "EMAIL_TAKEN":
            raise HTTPException(409, "An account with this email already exists") from exc
        raise
    return TokenResponse(access_token=create_token(user), user=user)


@app.get("/api/v1/auth/me", response_model=User)
def me(user: User = Depends(current_user)):
    return user


@app.post("/api/v1/auth/ws-ticket")
def create_ws_ticket(user: User = Depends(current_user)):
    ticket = secrets.token_urlsafe(24)
    ws_tickets[ticket] = {
        "user": user.model_dump(mode="json"),
        "used": False,
        "issued_at": time.monotonic(),
    }
    return {"ticket": ticket, "expires_in": 60}


@app.post("/api/v1/encounters", response_model=EncounterView)
async def create_encounter(payload: EncounterCreate, user: User = Depends(require_roles(Role.PATIENT, Role.CLINICIAN))):
    encounter = store.create_encounter(user)
    return encounter


@app.get("/api/v1/encounters", response_model=list[EncounterView])
def list_encounters(user: User = Depends(current_user)):
    return store.list_encounters(user)


@app.get("/api/v1/encounters/{encounter_id}", response_model=EncounterView)
def get_encounter(encounter_id: str, user: User = Depends(current_user)):
    return encounter_for(user, encounter_id)


@app.post("/api/v1/encounters/{encounter_id}/consent", response_model=EncounterView)
def consent(encounter_id: str, payload: ConsentRequest, user: User = Depends(require_roles(Role.PATIENT))):
    encounter = encounter_for(user, encounter_id)
    if not payload.accepted:
        raise HTTPException(400, "Consent must be accepted before processing")
    encounter.consent = {"accepted": True, "version": payload.version, "accepted_at": datetime.now(timezone.utc).isoformat()}
    encounter.status = "consented"
    store.audit(user.tenant_id, encounter.id, user.id, "consent.accepted", {"version": payload.version})
    return store.save_encounter(encounter)


@app.post("/api/v1/encounters/{encounter_id}/ingest", response_model=EncounterView)
async def ingest(encounter_id: str, payload: IngestRequest, user: User = Depends(require_roles(Role.PATIENT))):
    encounter = encounter_for(user, encounter_id)
    if not encounter.consent.get("accepted"):
        raise HTTPException(409, "Consent is required")
    encounter = encounters.ingest(encounter, payload.text, payload.input_type, user)
    if encounter.status == "processing":
        return await encounters.finalize(encounter, encounters.case_context(encounter), user)
    return encounter


@app.post("/api/v1/encounters/{encounter_id}/answers", response_model=EncounterView)
async def answer(encounter_id: str, payload: AnswerRequest, user: User = Depends(require_roles(Role.PATIENT))):
    try:
        return await encounters.answer(encounter_for(user, encounter_id), payload.question_id, payload.answer, user)
    except KeyError as exc:
        raise HTTPException(404, "Question not found") from exc


@app.get("/api/v1/encounters/{encounter_id}/triage")
def triage(encounter_id: str, user: User = Depends(current_user)):
    encounter = encounter_for(user, encounter_id)
    return {"triage": encounter.triage, "critic": encounter.critic, "gate": encounter.gate, "guidance": encounter.guidance}


@app.get("/api/v1/encounters/{encounter_id}/uncertainty")
def uncertainty(encounter_id: str, user: User = Depends(current_user)):
    return encounter_for(user, encounter_id).uncertainty_map


@app.get("/api/v1/encounters/{encounter_id}/delta")
def delta(encounter_id: str, user: User = Depends(current_user)):
    current = encounter_for(user, encounter_id)
    previous = [item for item in store.list_encounters(user) if item.id != encounter_id and item.patient_id == current.patient_id]
    return {
        "has_history": bool(previous),
        "summary": "No previous encounter is available." if not previous else f"Compared with {len(previous)} prior encounter(s); current urgency is {current.gate.urgency.value if current.gate else 'pending'}.",
        "changes": [] if not previous else ["Current report and urgency were compared with the previous encounter."],
    }


@app.get("/api/v1/encounters/{encounter_id}/soap")
def get_soap(encounter_id: str, user: User = Depends(require_roles(Role.CLINICIAN, Role.REVIEWER, Role.ADMIN))):
    return encounter_for(user, encounter_id).soap


@app.patch("/api/v1/encounters/{encounter_id}/soap", response_model=EncounterView)
def patch_soap(encounter_id: str, payload: SoapPatchRequest, user: User = Depends(require_roles(Role.CLINICIAN))):
    return encounters.patch_soap(encounter_for(user, encounter_id), payload.sections, user)


@app.post("/api/v1/encounters/{encounter_id}/soap/sign-off", response_model=EncounterView)
def sign_soap(encounter_id: str, user: User = Depends(require_roles(Role.CLINICIAN))):
    return encounters.sign_soap(encounter_for(user, encounter_id), user)


@app.post("/api/v1/encounters/{encounter_id}/teach-back", response_model=EncounterView)
def teach_back(encounter_id: str, payload: TeachBackRequest, user: User = Depends(require_roles(Role.PATIENT))):
    encounter = encounter_for(user, encounter_id)
    if not encounter.gate:
        raise HTTPException(409, "Guidance is not ready")
    normalized = payload.answer.lower()
    expected = "emergency" if encounter.gate.urgency == Urgency.EMERGENCY else "today" if encounter.gate.urgency == Urgency.SAME_DAY else "worse"
    understood = expected in normalized
    attempts = int((encounter.teach_back or {}).get("attempts", 0)) + 1
    encounter.teach_back = {
        "understood": understood,
        "attempts": attempts,
        "message": "Understanding confirmed." if understood else "Please review the safety-net instruction and try again; a failed check does not change the guidance.",
    }
    store.audit(user.tenant_id, encounter.id, user.id, "teach_back.completed", {"understood": understood, "attempts": attempts})
    return store.save_encounter(encounter)


@app.post("/api/v1/encounters/{encounter_id}/escalate")
def manual_escalate(encounter_id: str, user: User = Depends(current_user)):
    encounter = encounter_for(user, encounter_id)
    return store.create_escalation(encounter, "MANUAL_ESCALATION")


@app.get("/api/v1/escalations")
def list_escalations(user: User = Depends(require_roles(Role.REVIEWER, Role.CLINICIAN, Role.ADMIN))):
    return store.list_escalations(user.tenant_id)


@app.post("/api/v1/escalations/{escalation_id}/claim")
def claim(escalation_id: str, user: User = Depends(require_roles(Role.REVIEWER))):
    try:
        result = store.update_escalation(user.tenant_id, escalation_id, "claimed", user.id)
        store.audit(user.tenant_id, result["encounter_id"], user.id, "escalation.claimed", {"escalation_id": escalation_id})
        return result
    except KeyError as exc:
        raise HTTPException(404, "Escalation not found") from exc


@app.post("/api/v1/escalations/{escalation_id}/resolve")
def resolve(escalation_id: str, payload: ResolutionRequest, user: User = Depends(require_roles(Role.REVIEWER))):
    try:
        result = store.update_escalation(user.tenant_id, escalation_id, "resolved", user.id, payload.note)
        store.audit(user.tenant_id, result["encounter_id"], user.id, "escalation.resolved", {"escalation_id": escalation_id, "note": payload.note})
        return result
    except KeyError as exc:
        raise HTTPException(404, "Escalation not found") from exc


@app.get("/api/v1/audit/encounters/{encounter_id}")
def audit(encounter_id: str, user: User = Depends(require_roles(Role.CLINICIAN, Role.REVIEWER, Role.ADMIN))):
    encounter_for(user, encounter_id)
    return store.audit_events(user.tenant_id, encounter_id)


@app.get("/api/v1/admin/metrics")
def metrics(user: User = Depends(require_roles(Role.ADMIN))):
    items = store.list_encounters(user)
    escalations = store.list_escalations(user.tenant_id)
    urgency_mix = {urgency.value: sum(1 for item in items if item.gate and item.gate.urgency == urgency) for urgency in Urgency}
    disagreements = sum(1 for item in items if item.gate and any(code.value == "AGENT_DISAGREEMENT" for code in item.gate.reason_codes))
    timeouts = sum(
        1
        for item in items
        if item.gate
        and any(code.value == "PROCESSING_TIMEOUT" for code in item.gate.reason_codes)
    )
    cited = sum(1 for item in items if item.guidance and item.guidance.get("citations"))
    return {
        "encounters": len(items),
        "open_escalations": sum(1 for item in escalations if item["status"] != "resolved"),
        "escalation_rate": round(len(escalations) / max(1, len(items)), 2),
        "urgency_mix": urgency_mix,
        "critic_disagreement_rate": round(disagreements / max(1, len(items)), 2),
        "provider_timeout_rate": round(timeouts / max(1, len(items)), 2),
        "citation_coverage": round(cited / max(1, len(items)), 2),
        "rule_version": rules.version,
        "rule_version_coverage": 1.0 if items else 0.0,
    }


@app.get("/api/v1/admin/integrations")
def integrations(user: User = Depends(require_roles(Role.ADMIN))):
    return {
        "fallback_agent": {"provider": settings.agent_provider, "ready": bool(settings.gemini_api_key)},
        "orchestrator": encounters.orchestrator.status(),
        "mcp": ops_mcp.status(),
        "a2a": {"enabled": settings.a2a_enabled, "agents": ["triage", "critic", "documentation"]},
    }


@app.post("/api/v1/admin/integrations/lyzr/verify")
async def verify_lyzr(user: User = Depends(require_roles(Role.ADMIN))):
    if not isinstance(encounters.orchestrator, LyzrSuperFlowOrchestrator):
        raise HTTPException(409, "ORCHESTRATOR_PROVIDER must be set to lyzr")
    try:
        result = await encounters.orchestrator.verify()
        store.audit(
            user.tenant_id,
            None,
            user.id,
            "integration.lyzr_verified",
            {"workflow_id": settings.lyzr_workflow_id, "connected": True},
        )
        return result
    except OrchestrationError as exc:
        raise HTTPException(503, f"{exc.code}: {exc}") from exc


@app.get("/api/v1/admin/ops/snapshot")
async def ops_snapshot(user: User = Depends(require_roles(Role.ADMIN))):
    try:
        return await ops_mcp.snapshot()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.websocket("/api/v1/ws/encounters/{encounter_id}")
async def encounter_ws(websocket: WebSocket, encounter_id: str, ticket: str = Query(...)):
    entry = ws_tickets.pop(ticket, None)
    if not entry or entry["used"] or time.monotonic() - entry["issued_at"] > 60:
        await websocket.close(code=4401)
        return
    user = User.model_validate(entry["user"])
    encounter = store.get_encounter(user.tenant_id, encounter_id)
    if not encounter:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    for item in encounter.timeline:
        await websocket.send_json(item)
    await websocket.close(code=1000)


@app.websocket("/api/v1/ws/escalations")
async def escalation_ws(websocket: WebSocket, ticket: str = Query(...)):
    entry = ws_tickets.pop(ticket, None)
    if not entry or entry["used"] or time.monotonic() - entry["issued_at"] > 60:
        await websocket.close(code=4401)
        return
    user = User.model_validate(entry["user"])
    if user.role not in {Role.REVIEWER, Role.CLINICIAN, Role.ADMIN}:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    for escalation in store.list_escalations(user.tenant_id):
        await websocket.send_json(
            {
                "schema_version": "1.0",
                "event_id": secrets.token_hex(12),
                "event_type": "escalation.snapshot",
                "encounter_id": escalation["encounter_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": escalation,
            }
        )
    await websocket.close(code=1000)


@app.get("/a2a/{agent_name}/.well-known/agent-card.json")
def agent_card(agent_name: str):
    if agent_name not in {"triage", "critic", "documentation"} or not settings.a2a_enabled:
        raise HTTPException(404, "Agent not found")
    return {
        "name": f"CareRelay {agent_name.title()} Agent",
        "description": "Typed clinical decision-support sub-agent. It cannot issue final patient guidance.",
        "url": f"{settings.public_api_base_url.rstrip('/')}/a2a/{agent_name}",
        "version": "0.1.0",
        "protocolVersion": "0.3.0",
        "capabilities": {"streaming": False},
        "skills": [{"id": agent_name, "name": agent_name.title(), "description": "Returns typed JSON for CareRelay's gated workflow."}],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
    }


@app.post("/a2a/{agent_name}")
async def a2a_call(agent_name: str, payload: dict[str, Any], authorization: str | None = Header(default=None)):
    if authorization != f"Bearer {settings.a2a_shared_token}":
        raise HTTPException(401, "A2A service token required")
    if agent_name not in {"triage", "critic", "documentation"}:
        raise HTTPException(404, "Agent not found")
    request_id = payload.get("id")
    data = payload.get("params", {}).get("message", {}).get("parts", [{}])[0].get("data")
    if not isinstance(data, dict):
        return {"jsonrpc":"2.0", "id":request_id, "error":{"code":-32602, "message":"A typed JSON data part is required"}}
    provider = get_agent_provider()
    retrieval = get_retrieval_provider()
    citations, _ = retrieval.retrieve(data.get("text", ""), tenant_id=store.tenant_id)
    if agent_name == "triage":
        result = await provider.triage(data.get("text", ""), data.get("context", {}), citations)
    elif agent_name == "critic":
        proposal = TriageProposal.model_validate(data["proposal"])
        result = await provider.critique(proposal, data.get("text", ""), data.get("context", {}))
    else:
        proposal = TriageProposal.model_validate(data["proposal"])
        result = await provider.document(data.get("text", ""), proposal, citations)
    store.audit(store.tenant_id, data.get("encounter_id"), f"a2a:{agent_name}", "a2a.task_completed", {"agent": agent_name, "run_id": getattr(result, "run_id", None)})
    return {"jsonrpc":"2.0", "id":request_id, "result":{"kind":"message", "role":"agent", "parts":[{"kind":"data", "data":result.model_dump(mode="json")} ]}}
