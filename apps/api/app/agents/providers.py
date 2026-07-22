from __future__ import annotations

import asyncio
import json
import math
import re
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from qdrant_client import QdrantClient, models

from ..core import Settings, get_settings
from ..privacy import mask_phi
from ..schemas import (
    EvidenceCitation,
    ReasonCode,
    SafetyCritique,
    SoapDraft,
    SoapSentence,
    TriageProposal,
    Urgency,
)


CORPUS = [
    EvidenceCitation(
        source_id="DEMO-GUIDE-001",
        title="CareRelay Demonstration Urgency Rulebook",
        version="demo-v1",
        excerpt="Emergency warning patterns require immediate local emergency-service guidance.",
        retrieval_score=0.96,
    ),
    EvidenceCitation(
        source_id="DEMO-GUIDE-002",
        title="CareRelay Demonstration Same-Day Review Guide",
        version="demo-v1",
        excerpt="Potentially concerning or incomplete reports require qualified same-day review.",
        retrieval_score=0.90,
    ),
    EvidenceCitation(
        source_id="DEMO-GUIDE-003",
        title="CareRelay Demonstration Low-Risk Guidance",
        version="demo-v1",
        excerpt="Low-risk guidance requires agreement, adequate facts, and explicit safety-net instructions.",
        retrieval_score=0.88,
    ),
]


class AgentProvider(ABC):
    name: str

    @abstractmethod
    async def triage(self, text: str, scenario: dict[str, Any], citations: list[EvidenceCitation]) -> TriageProposal:
        raise NotImplementedError

    @abstractmethod
    async def critique(self, proposal: TriageProposal, text: str, scenario: dict[str, Any]) -> SafetyCritique:
        raise NotImplementedError

    @abstractmethod
    async def document(self, text: str, proposal: TriageProposal, citations: list[EvidenceCitation]) -> SoapDraft:
        raise NotImplementedError


class MockAgentProvider(AgentProvider):
    name = "deterministic-mock"

    async def triage(self, text: str, scenario: dict[str, Any], citations: list[EvidenceCitation]) -> TriageProposal:
        if scenario.get("provider_timeout"):
            await asyncio.sleep(get_settings().provider_timeout_seconds + 0.2)
        urgency = Urgency(scenario.get("triage", "Routine"))
        uncertainty = float(scenario.get("uncertainty", 0.18))
        return TriageProposal(
            provider=self.name,
            urgency=urgency,
            confidence=round(1 - uncertainty, 2),
            uncertainty=uncertainty,
            rationale_summary="Structured urgency proposal based on reported facts and curated demo evidence; no diagnosis was generated.",
            missing_critical_facts=scenario.get("missing", []),
            citations=citations,
        )

    async def critique(self, proposal: TriageProposal, text: str, scenario: dict[str, Any]) -> SafetyCritique:
        proposed = Urgency(scenario.get("critic", proposal.urgency.value))
        risk_found = proposed != proposal.urgency or proposed in (Urgency.EMERGENCY, Urgency.SAME_DAY)
        reasons = [ReasonCode.CRITIC_DISPROVED_LOW_RISK] if proposed != proposal.urgency else []
        return SafetyCritique(
            provider=self.name,
            proposed_urgency=proposed,
            risk_found=risk_found,
            confidence=0.94,
            reason_codes=reasons,
            summary="Independent deterministic critic checked whether the proposed urgency could be safely disproved.",
        )

    async def document(self, text: str, proposal: TriageProposal, citations: list[EvidenceCitation]) -> SoapDraft:
        patient_source = {"source_id": "TRANSCRIPT-1", "source_type": "patient", "label": "Patient report", "quote": text}
        retrieval_source = {
            "source_id": citations[0].source_id if citations else "NO-SOURCE",
            "source_type": "retrieval",
            "label": citations[0].title if citations else "No evidence retrieved",
            "quote": citations[0].excerpt if citations else None,
        }
        return SoapDraft(
            sections={
                "subjective": [SoapSentence(text=f"Patient reports: {text}", confidence=0.99, provenance=[patient_source])],
                "objective": [SoapSentence(text="No clinician-observed measurements were supplied; section remains incomplete.", confidence=1.0, provenance=[{"source_id":"SYSTEM","source_type":"inference","label":"Completeness check"}])],
                "assessment": [SoapSentence(text=f"Urgency-support draft: {proposal.urgency.value}; this is not a diagnosis.", confidence=proposal.confidence, provenance=[patient_source, retrieval_source])],
                "plan": [SoapSentence(text="Review the cited urgency guidance and safety-net instructions with a qualified professional.", confidence=0.92, provenance=[retrieval_source])],
            }
        )


class GeminiAgentProvider(MockAgentProvider):
    name = "gemini-adapter"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def _generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0},
        }
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.post(url, params={"key": self.settings.gemini_api_key}, json=payload)
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    async def triage(self, text: str, scenario: dict[str, Any], citations: list[EvidenceCitation]) -> TriageProposal:
        schema = TriageProposal.model_json_schema()
        data = await self._generate(
            "Return urgency guidance only, never a diagnosis or prescription. Analyze this masked report: " + mask_phi(text),
            schema,
        )
        result = TriageProposal.model_validate(data)
        result.provider = self.name
        result.citations = citations
        return result

    async def critique(self, proposal: TriageProposal, text: str, scenario: dict[str, Any]) -> SafetyCritique:
        data = await self._generate(
            "Adversarially audit this urgency proposal. Fail safe on doubt. Report: " + mask_phi(text) + " Proposal: " + proposal.model_dump_json(),
            SafetyCritique.model_json_schema(),
        )
        result = SafetyCritique.model_validate(data)
        result.provider = self.name
        return result


class RetrievalProvider:
    name = "in-memory-hybrid"

    def retrieve(
        self, text: str, forced_quality: float | None = None, tenant_id: str = "demo"
    ) -> tuple[list[EvidenceCitation], float]:
        tokens = set(re.findall(r"[a-z]+", text.lower()))
        scored: list[tuple[float, EvidenceCitation]] = []
        for citation in CORPUS:
            doc_tokens = set(re.findall(r"[a-z]+", (citation.title + " " + citation.excerpt).lower()))
            overlap = len(tokens & doc_tokens) / max(1, math.sqrt(len(tokens) * len(doc_tokens)))
            score = max(0.72, min(0.97, 0.72 + overlap))
            scored.append((score, citation.model_copy(update={"retrieval_score": score})))
        scored.sort(key=lambda item: item[0], reverse=True)
        quality = forced_quality if forced_quality is not None else scored[0][0]
        results = [item[1].model_copy(update={"retrieval_score": quality}) for item in scored[:2]]
        return results, round(quality, 2)

    @staticmethod
    def dense_vector(text: str, dimensions: int = 64) -> list[float]:
        vector = [0.0] * dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += 1 if digest[4] % 2 else -1
        norm = math.sqrt(sum(value * value for value in vector)) or 1
        return [value / norm for value in vector]

    @staticmethod
    def sparse_vector(text: str, dimensions: int = 100_003) -> models.SparseVector:
        counts: dict[int, float] = {}
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int.from_bytes(sha256(token.encode()).digest()[:8], "big") % dimensions
            counts[index] = counts.get(index, 0.0) + 1.0
        ordered = sorted(counts.items())
        return models.SparseVector(
            indices=[item[0] for item in ordered], values=[item[1] for item in ordered]
        )


class QdrantRetrievalProvider(RetrievalProvider):
    """Tenant-separated hybrid retrieval with transparent in-memory fallback."""

    name = "qdrant-hybrid"

    def __init__(self, settings: Settings):
        self.client = QdrantClient(
            url=settings.qdrant_url, timeout=0.35, check_compatibility=False
        )
        self.fallback = RetrievalProvider()

    @staticmethod
    def _collection(tenant_id: str, kind: str) -> str:
        tenant = sha256(tenant_id.encode()).hexdigest()[:16]
        return f"carerelay_{kind}_{tenant}"

    def _ensure_collection(self, collection: str) -> None:
        if self.client.collection_exists(collection):
            return
        self.client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": models.VectorParams(size=64, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )

    def _seed_guidelines(self, collection: str) -> None:
        self.client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, citation.source_id)),
                    vector={
                        "dense": self.dense_vector(citation.title + " " + citation.excerpt),
                        "sparse": self.sparse_vector(citation.title + " " + citation.excerpt),
                    },
                    payload=citation.model_dump(mode="json"),
                )
                for citation in CORPUS
            ],
            wait=True,
        )

    def _remember(self, tenant_id: str, text: str) -> None:
        collection = self._collection(tenant_id, "encounter_memory")
        self._ensure_collection(collection)
        masked = mask_phi(text)
        self.client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, tenant_id + masked)),
                    vector={
                        "dense": self.dense_vector(masked),
                        "sparse": self.sparse_vector(masked),
                    },
                    payload={"masked_summary": masked[:500], "tenant_id": tenant_id},
                )
            ],
            wait=False,
        )

    def retrieve(
        self, text: str, forced_quality: float | None = None, tenant_id: str = "demo"
    ) -> tuple[list[EvidenceCitation], float]:
        try:
            collection = self._collection(tenant_id, "guidelines")
            self._ensure_collection(collection)
            self._seed_guidelines(collection)
            query = mask_phi(text)
            dense = self.client.query_points(
                collection_name=collection,
                query=self.dense_vector(query),
                using="dense",
                limit=3,
                with_payload=True,
            ).points
            sparse = self.client.query_points(
                collection_name=collection,
                query=self.sparse_vector(query),
                using="sparse",
                limit=3,
                with_payload=True,
            ).points
            merged: dict[str, tuple[float, dict[str, Any]]] = {}
            for point in [*dense, *sparse]:
                payload = point.payload or {}
                source_id = str(payload.get("source_id", point.id))
                current = merged.get(source_id, (0.0, payload))
                merged[source_id] = (current[0] + max(0.0, float(point.score)), payload)
            ranked = sorted(merged.values(), key=lambda item: item[0], reverse=True)[:2]
            quality = forced_quality if forced_quality is not None else min(0.97, ranked[0][0] / 2)
            citations = [
                EvidenceCitation.model_validate(payload).model_copy(
                    update={"retrieval_score": round(quality, 2)}
                )
                for _, payload in ranked
            ]
            self._remember(tenant_id, query)
            return citations, round(quality, 2)
        except Exception:
            return self.fallback.retrieve(text, forced_quality, tenant_id)


def get_agent_provider() -> AgentProvider:
    settings = get_settings()
    if settings.agent_provider in {"gemini", "adk"}:
        return GeminiAgentProvider(settings)
    return MockAgentProvider()


def get_retrieval_provider() -> RetrievalProvider:
    settings = get_settings()
    if settings.retrieval_provider == "qdrant":
        return QdrantRetrievalProvider(settings)
    return RetrievalProvider()
