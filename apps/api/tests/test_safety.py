import asyncio

import pytest

from app.agents.providers import MockAgentProvider, RetrievalProvider
from app.privacy import mask_phi
from app.rules import RedFlagEngine
from app.schemas import SafetyCritique, TriageProposal, URGENCY_RANK, UncertaintyMap, Urgency
from app.services import safety_gate


def proposal(urgency: Urgency, uncertainty: float = 0.1, missing: list[str] | None = None):
    return TriageProposal(provider="test", urgency=urgency, confidence=1-uncertainty, uncertainty=uncertainty, rationale_summary="test", missing_critical_facts=missing or [])


def critique(urgency: Urgency):
    return SafetyCritique(provider="critic", proposed_urgency=urgency, risk_found=False, confidence=.9, summary="test")


def uncertainty_map(quality=.9, uncertainty=.1, red_flags=None):
    return UncertaintyMap(known_facts=["fact"], missing_facts=[], contradictions=[], red_flags=red_flags or [], retrieval_quality=quality, uncertainty=uncertainty)


def test_red_flag_fixture_recall():
    engine = RedFlagEngine()
    fixtures = ["chest pressure", "I cannot breathe", "face droop", "slurred speech", "uncontrolled bleeding", "vomiting blood", "passing out", "unable to keep fluids down"]
    assert all(engine.scan(item) for item in fixtures)


def test_self_care_requires_two_keys():
    approved = safety_gate(proposal(Urgency.SELF_CARE), critique(Urgency.SELF_CARE), uncertainty_map())
    assert approved.approved_low_risk is True
    assert approved.urgency == Urgency.SELF_CARE
    disagreement = safety_gate(proposal(Urgency.SELF_CARE), critique(Urgency.SAME_DAY), uncertainty_map())
    assert disagreement.escalated is True
    assert disagreement.urgency == Urgency.SAME_DAY


def test_thresholds_fail_closed():
    low_retrieval = safety_gate(proposal(Urgency.ROUTINE), critique(Urgency.ROUTINE), uncertainty_map(quality=.69))
    assert low_retrieval.urgency == Urgency.SAME_DAY
    high_uncertainty = safety_gate(proposal(Urgency.ROUTINE, uncertainty=.26), critique(Urgency.ROUTINE), uncertainty_map(uncertainty=.26))
    assert high_uncertainty.escalated is True
    missing = safety_gate(proposal(Urgency.ROUTINE, missing=["onset"]), critique(Urgency.ROUTINE), uncertainty_map())
    assert missing.urgency == Urgency.SAME_DAY


def test_threshold_boundaries_are_inclusive():
    result = safety_gate(
        proposal(Urgency.ROUTINE, uncertainty=.25),
        critique(Urgency.ROUTINE),
        uncertainty_map(quality=.70, uncertainty=.25),
    )
    assert result.urgency == Urgency.ROUTINE
    assert result.approved_low_risk is True


def test_deterministic_same_day_is_a_floor_not_a_ceiling():
    red_flags = RedFlagEngine().scan("unable to keep fluids down")
    result = safety_gate(
        proposal(Urgency.EMERGENCY),
        critique(Urgency.SAME_DAY),
        uncertainty_map(red_flags=red_flags),
    )
    assert result.urgency == Urgency.EMERGENCY


@pytest.mark.parametrize("triage", list(Urgency))
@pytest.mark.parametrize("critic_result", list(Urgency))
def test_every_agent_urgency_combination_is_fail_safe(triage, critic_result):
    result = safety_gate(proposal(triage), critique(critic_result), uncertainty_map())
    if triage == critic_result and triage in {Urgency.ROUTINE, Urgency.SELF_CARE}:
        assert result.urgency == triage
        assert result.approved_low_risk
    elif triage == critic_result:
        assert result.urgency == triage
        assert result.escalated
    else:
        expected_rank = max(URGENCY_RANK[triage], URGENCY_RANK[critic_result], URGENCY_RANK[Urgency.SAME_DAY])
        assert URGENCY_RANK[result.urgency] == expected_rank
        assert result.escalated


def test_provider_timeout_fails_closed():
    result = safety_gate(proposal(Urgency.ROUTINE), critique(Urgency.ROUTINE), uncertainty_map(), provider_failed=True)
    assert result.urgency == Urgency.SAME_DAY
    assert result.escalated


def test_deterministic_hash_embedding_is_repeatable():
    left = RetrievalProvider.dense_vector("same clinical text")
    right = RetrievalProvider.dense_vector("same clinical text")
    assert left == right
    assert round(sum(value * value for value in left), 5) == 1


def test_phi_masking_covers_demo_identifiers():
    masked = mask_phi(
        "Jane Patient jane@example.com +1 (415) 555-0199 MRN: ABCD-1234"
    )
    assert masked == "[NAME] [EMAIL] [PHONE] [RECORD_ID]"


def test_mock_soap_every_sentence_has_provenance():
    provider = MockAgentProvider()
    triage = proposal(Urgency.ROUTINE)
    citations, _ = RetrievalProvider().retrieve("mild symptom")
    soap = asyncio.run(provider.document("mild symptom", triage, citations))
    assert all(sentence.provenance for section in soap.sections.values() for sentence in section)
