from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .agents.providers import DeterministicBaselineProvider, get_retrieval_provider
from .core import get_settings
from .event_bus import get_event_transport
from .orchestration import LocalOrchestrator, OrchestrationError, make_orchestrator, opaque_run_ref
from .privacy import mask_phi
from .rules import RedFlagEngine
from .schemas import (
    EncounterView,
    EventEnvelope,
    GateDecision,
    OrchestrationRun,
    ReasonCode,
    SafetyCritique,
    SoapSentence,
    TriageProposal,
    URGENCY_RANK,
    UncertaintyMap,
    Urgency,
    User,
)
from .store import Store


QUESTION_BANK = [
    ("onset", "When did this begin, and has it changed since then?"),
    ("severity", "How much is this affecting your usual activities right now?"),
    ("safety", "Are you having trouble breathing, chest pressure, new weakness, fainting, or uncontrolled bleeding?"),
    ("risk_modifier", "Are there important risk factors we should include, such as pregnancy, immune suppression, recent surgery, or a major long-term condition?"),
]


def inferred_facts(encounter: EncounterView) -> set[str]:
    text = " ".join(item.get("text", "") for item in encounter.transcript).lower()
    facts = {item.get("fact", "") for item in encounter.answers}
    if any(token in text for token in ("today", "yesterday", "hour", "day", "week", "began", "started")):
        facts.add("onset")
    if any(token in text for token in ("mild", "moderate", "severe", "activity", "activities", "function")):
        facts.add("severity")
    if any(token in text for token in ("breath", "chest", "weakness", "faint", "bleeding")):
        facts.add("safety")
    return facts


def event(encounter: EncounterView, event_type: str, payload: dict[str, Any]) -> None:
    envelope = EventEnvelope(
        event_type=event_type, encounter_id=encounter.id, payload=payload
    ).model_dump(mode="json")
    encounter.timeline.append(envelope)
    get_event_transport().publish(encounter.tenant_id, envelope)


def highest_urgency(left: Urgency, right: Urgency) -> Urgency:
    return left if URGENCY_RANK[left] >= URGENCY_RANK[right] else right


def safety_gate(
    triage: TriageProposal,
    critic: SafetyCritique,
    uncertainty: UncertaintyMap,
    provider_failed: bool = False,
) -> GateDecision:
    settings = get_settings()
    reasons: list[ReasonCode] = []
    def decide(**values: Any) -> GateDecision:
        return GateDecision(
            confidence=min(triage.confidence, critic.confidence),
            uncertainty=uncertainty.uncertainty,
            citations=triage.citations,
            **values,
        )

    deterministic = None
    for match in uncertainty.red_flags:
        deterministic = match.severity if deterministic is None else highest_urgency(deterministic, match.severity)
    if deterministic:
        deterministic = highest_urgency(deterministic, triage.urgency)
        deterministic = highest_urgency(deterministic, critic.proposed_urgency)
        return decide(
            urgency=deterministic,
            approved_low_risk=False,
            escalated=True,
            reason_codes=[ReasonCode.DETERMINISTIC_RED_FLAG],
            summary="Deterministic safety rule overrides agent output.",
        )
    if provider_failed:
        return decide(
            urgency=Urgency.SAME_DAY,
            approved_low_risk=False,
            escalated=True,
            reason_codes=[ReasonCode.PROCESSING_TIMEOUT],
            summary="An agent did not complete safely; the case failed closed to human review.",
        )
    if triage.missing_critical_facts:
        reasons.append(ReasonCode.MISSING_CRITICAL_FACT)
    if uncertainty.retrieval_quality < settings.retrieval_threshold:
        reasons.append(ReasonCode.LOW_RETRIEVAL_QUALITY)
    if uncertainty.uncertainty > settings.low_risk_uncertainty_max:
        reasons.append(ReasonCode.HIGH_UNCERTAINTY)
    if triage.urgency != critic.proposed_urgency:
        reasons.append(ReasonCode.AGENT_DISAGREEMENT)
        urgency = highest_urgency(triage.urgency, critic.proposed_urgency)
        return decide(
            urgency=urgency if URGENCY_RANK[urgency] >= URGENCY_RANK[Urgency.SAME_DAY] else Urgency.SAME_DAY,
            approved_low_risk=False,
            escalated=True,
            reason_codes=reasons,
            summary="Independent agents disagreed; the more urgent result was selected for review.",
        )
    if reasons:
        return decide(
            urgency=Urgency.SAME_DAY,
            approved_low_risk=False,
            escalated=True,
            reason_codes=reasons,
            summary="Low-risk guidance was blocked because evidence or certainty requirements were not met.",
        )
    if triage.urgency in (Urgency.EMERGENCY, Urgency.SAME_DAY):
        return decide(
            urgency=triage.urgency,
            approved_low_risk=False,
            escalated=True,
            reason_codes=critic.reason_codes or [ReasonCode.INSUFFICIENT_EVIDENCE],
            summary="Higher-urgency guidance requires human follow-up.",
        )
    return decide(
        urgency=triage.urgency,
        approved_low_risk=True,
        escalated=False,
        reason_codes=[ReasonCode.TWO_KEY_APPROVED],
        summary="Triage and critic agreed, with adequate facts, retrieval quality, and certainty.",
    )


def guidance_for(urgency: Urgency, citations: list[dict[str, Any]]) -> dict[str, Any]:
    content = {
        Urgency.EMERGENCY: (
            "Seek emergency help now",
            "Contact your local emergency service now. CareRelay cannot provide emergency response.",
        ),
        Urgency.SAME_DAY: (
            "Qualified review is needed today",
            "Contact a qualified healthcare professional today. If severe warning signs develop, use local emergency services.",
        ),
        Urgency.ROUTINE: (
            "Arrange routine professional review",
            "Arrange a routine review with a qualified healthcare professional and seek earlier help if symptoms worsen.",
        ),
        Urgency.SELF_CARE: (
            "Monitor and use the safety net",
            "Monitor how you feel and seek qualified review if symptoms persist, worsen, or new warning signs appear.",
        ),
    }
    title, instruction = content[urgency]
    return {"title": title, "instruction": instruction, "citations": citations, "disclaimer": "Urgency guidance only; not a diagnosis or treatment plan."}


class EncounterService:
    def __init__(self, store: Store, rules: RedFlagEngine):
        self.store = store
        self.rules = rules
        self.retrieval = get_retrieval_provider()
        self.orchestrator = make_orchestrator()

    def ingest(self, encounter: EncounterView, text: str, input_type: str, user: User) -> EncounterView:
        encounter.transcript.append({"id": str(uuid4()), "speaker": "patient", "input_type": input_type, "text": text, "created_at": datetime.now(timezone.utc).isoformat()})
        event(encounter, "intake.received", {"mode": input_type})
        matches = self.rules.scan(text)
        event(encounter, "safety.red_flags_checked", {"matches": len(matches), "rule_version": self.rules.version})
        if matches:
            encounter.status = "processing"
        else:
            self.add_next_question(encounter)
            encounter.status = "interviewing"
        self.store.audit(user.tenant_id, encounter.id, user.id, "intake.ingested", {"masked_text": mask_phi(text), "input_type": input_type})
        return self.store.save_encounter(encounter)

    def case_context(self, encounter: EncounterView) -> dict[str, Any]:
        """Create a conservative, encounter-derived context for deterministic agents."""
        known = inferred_facts(encounter)
        # Only treat unanswered interview slots as missing; risk_modifier is optional.
        critical = {"onset", "severity", "safety"}
        missing = [fact for fact in critical if fact not in known]
        text = " ".join(item.get("text", "") for item in encounter.transcript).lower()
        answers = " ".join(item.get("answer", "") for item in encounter.answers).lower()
        blob = f"{text} {answers}"
        high_concern = any(
            term in blob for term in ("severe", "worsening", "unable", "sudden", "high fever")
        )
        mild_self_care = any(
            term in blob
            for term in ("mild", "improving", "getting better", "normal activities", "can do normal")
        ) and not high_concern
        if high_concern:
            triage = critic = "Same-Day"
            uncertainty = 0.22
        elif mild_self_care and not missing:
            triage = critic = "Self-Care"
            uncertainty = 0.12
        else:
            triage = critic = "Routine"
            uncertainty = 0.38 if missing else 0.16
        return {
            "triage": triage,
            "critic": critic,
            "retrieval_quality": 0.86 if not missing else None,
            "uncertainty": uncertainty,
            "missing": missing,
        }

    def scenario_context(self, encounter: EncounterView) -> dict[str, Any]:
        if encounter.scenario_id and encounter.scenario_id in self.store.scenarios:
            return dict(self.store.scenarios[encounter.scenario_id])
        return self.case_context(encounter)

    async def load_scenario(self, encounter: EncounterView, scenario_id: str, user: User) -> EncounterView:
        scenario = self.store.scenarios.get(scenario_id)
        if not scenario:
            raise KeyError(scenario_id)
        encounter.scenario_id = scenario_id
        encounter.transcript = [
            {
                "id": "TRANSCRIPT-1",
                "speaker": "patient",
                "input_type": "demo",
                "text": scenario["transcript"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        encounter.status = "processing"
        event(encounter, "intake.received", {"mode": "demo-scenario", "scenario": scenario_id})
        self.store.save_encounter(encounter)
        return await self.finalize(encounter, scenario, user)

    def add_next_question(self, encounter: EncounterView) -> bool:
        turn = len(encounter.questions)
        if turn >= 3:
            return False
        asked = {item["fact"] for item in encounter.questions}
        known = inferred_facts(encounter)
        next_item = next(
            (item for item in QUESTION_BANK if item[0] not in asked and item[0] not in known),
            None,
        )
        if not next_item:
            return False
        fact, prompt = next_item
        question = {"id": str(uuid4()), "fact": fact, "prompt": prompt, "turn": turn + 1, "answered": False}
        encounter.questions.append(question)
        event(
            encounter,
            "triage.question_created",
            {"question_id": question["id"], "turn": turn + 1, "prompt": prompt},
        )
        return True

    async def answer(self, encounter: EncounterView, question_id: str, answer: str, user: User) -> EncounterView:
        question = next((item for item in encounter.questions if item["id"] == question_id), None)
        if not question:
            raise KeyError(question_id)
        question["answered"] = True
        encounter.answers.append({"question_id": question_id, "fact": question["fact"], "answer": answer})
        event(encounter, "triage.answer_received", {"question_id": question_id})
        text = " ".join([item["text"] for item in encounter.transcript] + [item["answer"] for item in encounter.answers])
        if self.rules.scan(text) or len(encounter.answers) >= 3:
            encounter.status = "processing"
            self.store.save_encounter(encounter)
            return await self.finalize(encounter, self.scenario_context(encounter), user)
        if self.add_next_question(encounter):
            return self.store.save_encounter(encounter)
        encounter.status = "processing"
        self.store.save_encounter(encounter)
        return await self.finalize(encounter, self.scenario_context(encounter), user)

    async def finalize(self, encounter: EncounterView, context: dict[str, Any], user: User) -> EncounterView:
        settings = get_settings()
        unknown_facts = [
            item["fact"]
            for item in encounter.answers
            if any(
                phrase in item["answer"].lower()
                for phrase in ("not sure", "don't know", "do not know", "unknown", "cannot say")
            )
        ]
        if unknown_facts:
            context = {
                **context,
                "missing": sorted(set(context.get("missing", [])) | set(unknown_facts)),
                "uncertainty": max(0.5, float(context.get("uncertainty", 0.5))),
            }
        text = " ".join([item["text"] for item in encounter.transcript] + [item["answer"] for item in encounter.answers])
        red_flags = self.rules.scan(text)
        event(
            encounter,
            "safety.red_flags_checked",
            {"stage": "pre-agent", "matches": len(red_flags), "rule_version": self.rules.version},
        )
        citations, quality = self.retrieval.retrieve(
            text, context.get("retrieval_quality"), encounter.tenant_id
        )
        event(encounter, "retrieval.completed", {"quality": quality, "source_ids": [item.source_id for item in citations]})
        provider_failed = False
        emergency_match = next(
            (match for match in red_flags if match.severity == Urgency.EMERGENCY), None
        )
        if emergency_match:
            started = datetime.now(timezone.utc)
            triage = TriageProposal(
                provider="deterministic-red-flag",
                urgency=Urgency.EMERGENCY,
                confidence=1.0,
                uncertainty=0.0,
                rationale_summary="A deterministic safety rule requires immediate emergency guidance.",
                citations=citations,
            )
            critic = SafetyCritique(
                provider="deterministic-red-flag",
                proposed_urgency=Urgency.EMERGENCY,
                risk_found=True,
                confidence=1.0,
                summary="Generative agents were bypassed because a deterministic Emergency rule matched.",
            )
            soap = await DeterministicBaselineProvider().document(text, triage, citations)
            encounter.orchestration = OrchestrationRun(
                provider="deterministic-red-flag",
                status="bypassed",
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0,
            )
            event(
                encounter,
                "orchestration.bypassed",
                {"reason": "deterministic-emergency-red-flag"},
            )
        else:
            orchestration_started = datetime.now(timezone.utc)
            # Seeded demo scenarios (and local orchestrator mode) use the deterministic
            # baseline so Routine / Self-Care stay reachable even when Lyzr times out.
            if encounter.scenario_id or settings.orchestrator_provider.lower() != "lyzr":
                orchestrator = LocalOrchestrator(settings, DeterministicBaselineProvider())
            else:
                orchestrator = self.orchestrator
            try:
                outcome = await orchestrator.run(
                    mask_phi(text),
                    context,
                    citations,
                    opaque_run_ref(encounter.tenant_id, encounter.id),
                )
                triage, critic, soap = outcome.triage, outcome.critic, outcome.soap
                encounter.orchestration = outcome.run
                event(
                    encounter,
                    "orchestration.completed",
                    {
                        "provider": outcome.run.provider,
                        "workflow_id": outcome.run.workflow_id,
                        "execution_id": outcome.run.execution_id,
                        "duration_ms": outcome.run.duration_ms,
                        "scenario_id": encounter.scenario_id,
                    },
                )
            except (TimeoutError, asyncio.TimeoutError, ValueError, RuntimeError) as exc:
                provider_failed = True
                error_code = (
                    exc.code if isinstance(exc, OrchestrationError) else "PROVIDER_EXECUTION_FAILED"
                )
                completed = datetime.now(timezone.utc)
                encounter.orchestration = OrchestrationRun(
                    provider=orchestrator.name,
                    workflow_id=(
                        None
                        if encounter.scenario_id or settings.orchestrator_provider.lower() != "lyzr"
                        else (settings.lyzr_workflow_id or None)
                    ),
                    execution_id=getattr(orchestrator, "last_execution_id", None),
                    status="failed",
                    started_at=orchestration_started,
                    completed_at=completed,
                    duration_ms=max(
                        0, int((completed - orchestration_started).total_seconds() * 1000)
                    ),
                    error_code=error_code,
                )
                event(
                    encounter,
                    "orchestration.failed_closed",
                    {
                        "provider": orchestrator.name,
                        "execution_id": encounter.orchestration.execution_id,
                        "error_code": error_code,
                    },
                )
                fallback = DeterministicBaselineProvider()
                safe_context = {
                    **context,
                    "triage": "Routine",
                    "critic": "Routine",
                    "uncertainty": max(0.5, context.get("uncertainty", 0.5)),
                    "provider_timeout": False,
                }
                triage = await fallback.triage(mask_phi(text), safe_context, citations)
                critic, soap = await asyncio.gather(
                    fallback.critique(triage, mask_phi(text), safe_context),
                    fallback.document(text, triage, citations),
                )
        post_critic_flags = self.rules.scan(text)
        event(
            encounter,
            "safety.red_flags_checked",
            {
                "stage": "post-critic",
                "matches": len(post_critic_flags),
                "rule_version": self.rules.version,
            },
        )
        event(encounter, "triage.proposed", {"urgency": triage.urgency.value, "provider": triage.provider})
        event(encounter, "critic.completed", {"proposed_urgency": critic.proposed_urgency.value, "risk_found": critic.risk_found})
        uncertainty = UncertaintyMap(
            provider="deterministic-intake",
            confidence=round(1 - triage.uncertainty, 2),
            citations=citations,
            known_facts=[text] if text else [],
            missing_facts=triage.missing_critical_facts,
            contradictions=["Triage and critic urgency differ"] if triage.urgency != critic.proposed_urgency else [],
            red_flags=red_flags,
            retrieval_quality=quality,
            uncertainty=triage.uncertainty,
        )
        gate = safety_gate(triage, critic, uncertainty, provider_failed)
        pre_guidance_flags = self.rules.scan(text)
        event(
            encounter,
            "safety.red_flags_checked",
            {
                "stage": "pre-guidance",
                "matches": len(pre_guidance_flags),
                "rule_version": self.rules.version,
            },
        )
        event(encounter, "safety.gate_decided", {"urgency": gate.urgency.value, "reason_codes": [code.value for code in gate.reason_codes], "approved_low_risk": gate.approved_low_risk})
        event(encounter, "documentation.draft_created", {"soap_id": soap.id})
        encounter.triage = triage
        encounter.critic = critic
        encounter.gate = gate
        encounter.uncertainty_map = uncertainty
        encounter.soap = soap
        encounter.guidance = guidance_for(gate.urgency, [item.model_dump(mode="json") for item in citations])
        encounter.status = "escalated" if gate.escalated else "guidance-ready"
        self.store.save_encounter(encounter)
        if gate.escalated:
            escalation = self.store.create_escalation(encounter, gate.reason_codes[0].value)
            event(encounter, "escalation.created", {"escalation_id": escalation["id"], "reason": escalation["reason"]})
            self.store.save_encounter(encounter)
        self.store.audit(user.tenant_id, encounter.id, user.id, "safety.gate_decided", gate.model_dump(mode="json"))
        self.store.audit(
            user.tenant_id,
            encounter.id,
            user.id,
            "orchestration.finished",
            encounter.orchestration.model_dump(mode="json") if encounter.orchestration else {},
        )
        return encounter

    def patch_soap(self, encounter: EncounterView, sections: dict[str, list[str]], user: User) -> EncounterView:
        if not encounter.soap:
            raise ValueError("SOAP draft not available")
        encounter.soap.sections = {
            name: [
                SoapSentence(text=text, confidence=1.0, provenance=[{"source_id": user.id, "source_type": "clinician", "label": "Clinician edit"}])
                for text in sentences
            ]
            for name, sentences in sections.items()
        }
        encounter.soap.updated_at = datetime.now(timezone.utc)
        self.store.audit(user.tenant_id, encounter.id, user.id, "soap.edited", {"sections": list(sections)})
        return self.store.save_encounter(encounter)

    def sign_soap(self, encounter: EncounterView, user: User) -> EncounterView:
        if not encounter.soap:
            raise ValueError("SOAP draft not available")
        encounter.soap.status = "signed"
        encounter.soap.signed_at = datetime.now(timezone.utc)
        self.store.audit(user.tenant_id, encounter.id, user.id, "soap.signed", {"soap_id": encounter.soap.id})
        return self.store.save_encounter(encounter)
