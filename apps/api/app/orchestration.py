from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import httpx
from pydantic import BaseModel

from .agents.providers import AgentProvider, get_agent_provider
from .core import Settings, get_settings
from .schemas import (
    EvidenceCitation,
    OrchestrationRun,
    ProvenanceLink,
    SafetyCritique,
    SoapDraft,
    SoapSentence,
    TriageProposal,
)


class OrchestrationError(RuntimeError):
    """Sanitized orchestration failure safe to persist and expose."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class OrchestrationOutcome(BaseModel):
    triage: TriageProposal
    critic: SafetyCritique
    soap: SoapDraft
    run: OrchestrationRun


class OrchestrationProvider(ABC):
    name: str

    @abstractmethod
    async def run(
        self,
        masked_text: str,
        context: dict[str, Any],
        citations: list[EvidenceCitation],
        run_ref: str,
    ) -> OrchestrationOutcome:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> dict[str, Any]:
        raise NotImplementedError

    async def verify(self) -> dict[str, Any]:
        return self.status()


class LocalOrchestrator(OrchestrationProvider):
    name = "local-supervisor"

    def __init__(self, settings: Settings, provider: AgentProvider | None = None):
        self.settings = settings
        self.provider = provider or get_agent_provider()

    async def run(
        self,
        masked_text: str,
        context: dict[str, Any],
        citations: list[EvidenceCitation],
        run_ref: str,
    ) -> OrchestrationOutcome:
        started = datetime.now(timezone.utc)
        start = time.monotonic()
        triage = await asyncio.wait_for(
            self.provider.triage(masked_text, context, citations),
            timeout=self.settings.provider_timeout_seconds,
        )
        critic, soap = await asyncio.gather(
            asyncio.wait_for(
                self.provider.critique(triage, masked_text, context),
                timeout=self.settings.provider_timeout_seconds,
            ),
            asyncio.wait_for(
                self.provider.document(masked_text, triage, citations),
                timeout=self.settings.provider_timeout_seconds,
            ),
        )
        completed = datetime.now(timezone.utc)
        return OrchestrationOutcome(
            triage=triage,
            critic=critic,
            soap=soap,
            run=OrchestrationRun(
                provider=self.name,
                execution_id=run_ref,
                status="completed",
                started_at=started,
                completed_at=completed,
                duration_ms=max(0, int((time.monotonic() - start) * 1000)),
            ),
        )

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": True,
            "ready": not self.settings.require_live_orchestration,
            "mode": "local-fallback",
        }


class LyzrSuperFlowOrchestrator(OrchestrationProvider):
    """Official Lyzr SuperFlow execute/poll adapter with typed output enforcement."""

    name = "lyzr-superflow"
    terminal_statuses = {"completed", "failed", "cancelled", "paused"}

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        self.transport = transport
        self.last_execution_id: str | None = None
        self.last_status: str = "not-run"
        self.last_duration_ms: int | None = None
        self.last_error_code: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.lyzr_api_key and self.settings.lyzr_workflow_id)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.lyzr_api_base.rstrip("/"),
            headers={
                "x-api-key": self.settings.lyzr_api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            timeout=httpx.Timeout(self.settings.lyzr_timeout_seconds),
            transport=self.transport,
        )

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.configured,
            "ready": self.configured,
            "workflow_id": self.settings.lyzr_workflow_id or None,
            "api_base": self.settings.lyzr_api_base,
            "last_execution_id": self.last_execution_id,
            "last_status": self.last_status,
            "last_duration_ms": self.last_duration_ms,
            "last_error_code": self.last_error_code,
            "credential_present": bool(self.settings.lyzr_api_key),
        }

    async def verify(self) -> dict[str, Any]:
        self._require_configuration()
        try:
            async with self._client() as client:
                response = await client.get(f"/workflows/{self.settings.lyzr_workflow_id}")
                response.raise_for_status()
                workflow = response.json()
        except httpx.HTTPStatusError as exc:
            raise OrchestrationError(
                "LYZR_WORKFLOW_UNAVAILABLE",
                f"Lyzr rejected the workflow verification request (HTTP {exc.response.status_code}).",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise OrchestrationError(
                "LYZR_CONNECTION_FAILED", "Lyzr workflow verification could not complete."
            ) from exc
        return {
            **self.status(),
            "connected": True,
            "workflow": {
                "id": workflow.get("id") or workflow.get("workflow_id") or self.settings.lyzr_workflow_id,
                "name": workflow.get("name"),
                "version": workflow.get("version"),
                "status": workflow.get("status"),
            },
        }

    async def run(
        self,
        masked_text: str,
        context: dict[str, Any],
        citations: list[EvidenceCitation],
        run_ref: str,
    ) -> OrchestrationOutcome:
        del context  # Encounter context never steers a live workflow.
        self._require_configuration()
        started = datetime.now(timezone.utc)
        start = time.monotonic()
        payload = {
            "workflow_id": self.settings.lyzr_workflow_id,
            "input": [
                {
                    "schema_version": "1.0",
                    "contract": "care_relay_orchestration_v1",
                    "run_ref": run_ref,
                    "reported_facts": masked_text,
                    "evidence": [item.model_dump(mode="json") for item in citations],
                    "constraints": {
                        "allowed_urgency": ["Emergency", "Same-Day", "Routine", "Self-Care"],
                        "no_diagnosis": True,
                        "no_treatment": True,
                        "one_final_json_object": True,
                    },
                }
            ],
        }
        try:
            async with self._client() as client:
                response = await client.post("/workflows/execute", json=payload)
                response.raise_for_status()
                initial = response.json()
                execution_id = initial.get("execution_id") or initial.get("id")
                if not execution_id:
                    raise OrchestrationError(
                        "LYZR_INVALID_EXECUTION", "Lyzr did not return an execution identifier."
                    )
                self.last_execution_id = str(execution_id)
                execution = await self._poll(client, str(execution_id), start)
        except OrchestrationError:
            raise
        except httpx.HTTPStatusError as exc:
            self.last_error_code = "LYZR_HTTP_ERROR"
            raise OrchestrationError(
                "LYZR_HTTP_ERROR",
                f"Lyzr rejected the orchestration request (HTTP {exc.response.status_code}).",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            self.last_error_code = "LYZR_CONNECTION_FAILED"
            raise OrchestrationError(
                "LYZR_CONNECTION_FAILED", "The Lyzr orchestration request could not complete."
            ) from exc

        status = str(execution.get("status", "")).lower()
        self.last_status = status
        if status != "completed":
            code = "LYZR_APPROVAL_PENDING" if status == "paused" else "LYZR_EXECUTION_FAILED"
            self.last_error_code = code
            raise OrchestrationError(code, f"Lyzr execution ended with status '{status}'.")

        try:
            raw_result = self._find_contract_result(execution)
            triage = TriageProposal.model_validate(raw_result["triage"])
            critic = SafetyCritique.model_validate(raw_result["critic"])
            soap = SoapDraft.model_validate(raw_result["soap"])
            self._semantic_validate(triage, critic)
            triage.provider = self.name
            triage.run_id = str(execution_id)
            triage.citations = citations
            critic.provider = self.name
            critic.run_id = str(execution_id)
            soap = self._sanitize_soap(soap, masked_text, citations)
        except (KeyError, TypeError, ValueError) as exc:
            self.last_error_code = "LYZR_INVALID_OUTPUT"
            raise OrchestrationError(
                "LYZR_INVALID_OUTPUT", "Lyzr completed but returned an invalid CareRelay contract."
            ) from exc

        completed = datetime.now(timezone.utc)
        duration_ms = max(0, int((time.monotonic() - start) * 1000))
        self.last_duration_ms = duration_ms
        self.last_error_code = None
        return OrchestrationOutcome(
            triage=triage,
            critic=critic,
            soap=soap,
            run=OrchestrationRun(
                provider=self.name,
                workflow_id=self.settings.lyzr_workflow_id,
                execution_id=str(execution_id),
                status="completed",
                started_at=started,
                completed_at=completed,
                duration_ms=duration_ms,
            ),
        )

    async def _poll(
        self, client: httpx.AsyncClient, execution_id: str, start: float
    ) -> dict[str, Any]:
        while True:
            if time.monotonic() - start >= self.settings.lyzr_timeout_seconds:
                self.last_status = "timeout"
                self.last_error_code = "LYZR_TIMEOUT"
                raise OrchestrationError("LYZR_TIMEOUT", "Lyzr orchestration timed out.")
            response = await client.get(f"/executions/{execution_id}")
            response.raise_for_status()
            execution = response.json()
            status = str(execution.get("status", "")).lower()
            self.last_status = status or "unknown"
            if status in self.terminal_statuses:
                return execution
            await asyncio.sleep(self.settings.lyzr_poll_interval_seconds)

    def _require_configuration(self) -> None:
        if not self.configured:
            self.last_error_code = "LYZR_NOT_CONFIGURED"
            raise OrchestrationError(
                "LYZR_NOT_CONFIGURED", "LYZR_API_KEY and LYZR_WORKFLOW_ID are required."
            )

    @classmethod
    def _find_contract_result(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                return cls._find_contract_result(json.loads(value))
            except json.JSONDecodeError as exc:
                raise ValueError("String output is not JSON") from exc
        if isinstance(value, dict):
            if {"triage", "critic", "soap"}.issubset(value):
                return value
            preferred = (
                "care_relay_result",
                "outputs",
                "output",
                "result",
                "data",
                "node_outputs",
            )
            for key in preferred:
                if key in value:
                    try:
                        return cls._find_contract_result(value[key])
                    except (KeyError, TypeError, ValueError):
                        pass
            for nested in value.values():
                if isinstance(nested, (dict, list, str)):
                    try:
                        return cls._find_contract_result(nested)
                    except (KeyError, TypeError, ValueError):
                        pass
        if isinstance(value, list):
            for nested in reversed(value):
                try:
                    return cls._find_contract_result(nested)
                except (KeyError, TypeError, ValueError):
                    pass
        raise ValueError("CareRelay result not found")

    @staticmethod
    def _semantic_validate(triage: TriageProposal, critic: SafetyCritique) -> None:
        if not triage.rationale_summary.strip() or not critic.summary.strip():
            raise ValueError("Summaries must not be empty")
        if triage.urgency.value != critic.proposed_urgency.value and not critic.risk_found:
            raise ValueError("A disagreement must be marked as a risk")

    @staticmethod
    def _sanitize_soap(
        soap: SoapDraft,
        masked_text: str,
        citations: list[EvidenceCitation],
    ) -> SoapDraft:
        allowed = {"TRANSCRIPT-1", "SYSTEM", *(item.source_id for item in citations)}
        replacement = SoapSentence(
            text="Incomplete—this generated sentence lacked approved source provenance.",
            confidence=1.0,
            provenance=[
                ProvenanceLink(
                    source_id="SYSTEM",
                    source_type="inference",
                    label="Provenance validation",
                )
            ],
        )
        sections: dict[str, list[SoapSentence]] = {}
        for section, sentences in soap.sections.items():
            sections[section] = []
            for sentence in sentences:
                if all(link.source_id in allowed for link in sentence.provenance):
                    safe_links = []
                    for link in sentence.provenance:
                        if link.source_id == "TRANSCRIPT-1":
                            link = link.model_copy(update={"quote": masked_text})
                        safe_links.append(link)
                    sections[section].append(sentence.model_copy(update={"provenance": safe_links}))
                else:
                    sections[section].append(replacement.model_copy(deep=True))
        return soap.model_copy(update={"sections": sections})


def make_orchestrator(settings: Settings | None = None) -> OrchestrationProvider:
    resolved = settings or get_settings()
    if resolved.orchestrator_provider.lower() == "lyzr":
        return LyzrSuperFlowOrchestrator(resolved)
    return LocalOrchestrator(resolved)


def opaque_run_ref(tenant_id: str, encounter_id: str) -> str:
    return sha256(f"{tenant_id}:{encounter_id}".encode()).hexdigest()
