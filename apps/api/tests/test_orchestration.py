from __future__ import annotations

import json

import httpx
import pytest

from app.core import Settings
from app.orchestration import LyzrSuperFlowOrchestrator, OrchestrationError
from app.schemas import EvidenceCitation


def settings(**updates):
    values = {
        "orchestrator_provider": "lyzr",
        "lyzr_api_key": "test-secret",
        "lyzr_workflow_id": "wf_care_relay",
        "lyzr_api_base": "https://inference.studio.lyzr.ai/api",
        "lyzr_timeout_seconds": 1,
        "lyzr_poll_interval_seconds": 0,
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


def citation():
    return EvidenceCitation(
        source_id="DEMO-GUIDE-003",
        title="Approved guidance",
        version="1",
        excerpt="Use explicit safety-net instructions.",
        retrieval_score=0.9,
    )


def contract_result():
    return {
        "triage": {
            "provider": "remote",
            "urgency": "Routine",
            "confidence": 0.9,
            "uncertainty": 0.1,
            "rationale_summary": "Appropriate for routine review based on supplied facts.",
            "missing_critical_facts": [],
            "citations": [],
        },
        "critic": {
            "provider": "remote",
            "proposed_urgency": "Routine",
            "risk_found": False,
            "confidence": 0.9,
            "reason_codes": [],
            "summary": "No reason to raise urgency was found in the supplied evidence.",
        },
        "soap": {
            "sections": {
                "subjective": [
                    {
                        "text": "Patient reports a masked concern.",
                        "confidence": 0.9,
                        "provenance": [
                            {
                                "source_id": "TRANSCRIPT-1",
                                "source_type": "patient",
                                "label": "Patient report",
                            }
                        ],
                    }
                ],
                "plan": [
                    {
                        "text": "Use the cited safety net.",
                        "confidence": 0.9,
                        "provenance": [
                            {
                                "source_id": "DEMO-GUIDE-003",
                                "source_type": "retrieval",
                                "label": "Approved guidance",
                            }
                        ],
                    }
                ],
            }
        },
    }


@pytest.mark.asyncio
async def test_superflow_executes_polls_and_validates_contract():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        assert request.headers["x-api-key"] == "test-secret"
        if request.url.path.endswith("/workflows/execute"):
            body = json.loads(request.content)
            assert body["workflow_id"] == "wf_care_relay"
            assert body["input"][0]["reported_facts"] == "[NAME] has a mild concern"
            assert "test-secret" not in request.content.decode()
            return httpx.Response(202, json={"execution_id": "exec_123", "status": "running"})
        if request.url.path.endswith("/executions/exec_123"):
            calls += 1
            if calls == 1:
                return httpx.Response(200, json={"execution_id": "exec_123", "status": "running"})
            return httpx.Response(
                200,
                json={
                    "execution_id": "exec_123",
                    "status": "completed",
                    "outputs": {"care_relay_result": json.dumps(contract_result())},
                },
            )
        raise AssertionError(request.url)

    orchestrator = LyzrSuperFlowOrchestrator(
        settings(), transport=httpx.MockTransport(handler)
    )
    outcome = await orchestrator.run(
        "[NAME] has a mild concern", {}, [citation()], "opaque-ref"
    )

    assert outcome.run.execution_id == "exec_123"
    assert outcome.run.status == "completed"
    assert outcome.triage.provider == "lyzr-superflow"
    assert outcome.triage.citations[0].source_id == "DEMO-GUIDE-003"
    assert outcome.soap.sections["subjective"][0].provenance[0].quote == "[NAME] has a mild concern"


@pytest.mark.asyncio
async def test_superflow_rejects_untyped_output():
    def handler(request: httpx.Request):
        if request.url.path.endswith("/workflows/execute"):
            return httpx.Response(202, json={"execution_id": "exec_bad"})
        return httpx.Response(
            200,
            json={"execution_id": "exec_bad", "status": "completed", "outputs": {"text": "looks fine"}},
        )

    orchestrator = LyzrSuperFlowOrchestrator(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(OrchestrationError) as error:
        await orchestrator.run("masked", {}, [citation()], "opaque-ref")
    assert error.value.code == "LYZR_INVALID_OUTPUT"


@pytest.mark.asyncio
async def test_superflow_paused_approval_fails_closed():
    def handler(request: httpx.Request):
        if request.url.path.endswith("/workflows/execute"):
            return httpx.Response(202, json={"execution_id": "exec_paused"})
        return httpx.Response(200, json={"execution_id": "exec_paused", "status": "paused"})

    orchestrator = LyzrSuperFlowOrchestrator(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(OrchestrationError) as error:
        await orchestrator.run("masked", {}, [citation()], "opaque-ref")
    assert error.value.code == "LYZR_APPROVAL_PENDING"


@pytest.mark.asyncio
async def test_verify_reads_configured_workflow_without_exposing_key():
    def handler(request: httpx.Request):
        assert request.url.path.endswith("/workflows/wf_care_relay")
        return httpx.Response(200, json={"id": "wf_care_relay", "name": "CareRelay", "version": 3})

    orchestrator = LyzrSuperFlowOrchestrator(
        settings(), transport=httpx.MockTransport(handler)
    )
    result = await orchestrator.verify()
    assert result["connected"] is True
    assert result["workflow"]["name"] == "CareRelay"
    assert "test-secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_superflow_requires_both_credentials():
    orchestrator = LyzrSuperFlowOrchestrator(settings(lyzr_api_key=""))
    with pytest.raises(OrchestrationError) as error:
        await orchestrator.run("masked", {}, [citation()], "opaque-ref")
    assert error.value.code == "LYZR_NOT_CONFIGURED"


def test_production_settings_reject_blank_secrets_and_demo_storage():
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(_env_file=None, demo_mode=False)


def test_production_settings_accept_hosted_live_configuration():
    configured = Settings(
        _env_file=None,
        demo_mode=False,
        seed_demo_data=False,
        database_url="postgresql+psycopg://service@postgres/carerelay",
        jwt_secret="j" * 48,
        a2a_shared_token="a" * 48,
        orchestrator_provider="lyzr",
        lyzr_api_key="secret",
        lyzr_workflow_id="wf_live",
        require_live_orchestration=True,
        cors_origins="https://care-relay.example.com",
        public_api_base_url="https://api.care-relay.example.com",
    )
    assert configured.demo_mode is False
