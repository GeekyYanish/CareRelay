import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.auth import create_token
from app.database import session_scope
from app.db.models import AuditRecord
from app.main import app
from app.schemas import Role, User


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_full_emergency_scenario_and_audit():
    with TestClient(app) as client:
        headers = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=headers, json={}).json()
        assert client.post(f"/api/v1/encounters/{encounter['id']}/consent", headers=headers, json={"accepted": True}).status_code == 200
        result = client.post(f"/api/v1/encounters/{encounter['id']}/demo-scenario", headers=headers, json={"scenario_id": "emergency"})
        assert result.status_code == 200, result.text
        assert result.json()["gate"]["urgency"] == "Emergency"
        assert result.json()["gate"]["escalated"] is True
        reviewer = login(client, "reviewer@demo.carerelay.local", "demo-reviewer")
        queue = client.get("/api/v1/escalations", headers=reviewer).json()
        assert any(item["encounter_id"] == encounter["id"] for item in queue)
        audit = client.get(f"/api/v1/audit/encounters/{encounter['id']}", headers=reviewer).json()
        assert any(item["event_type"] == "safety.gate_decided" for item in audit)
        assert len(audit[0]["previous_hash"]) == 64
        assert all(
            current["previous_hash"] == previous["event_hash"]
            for previous, current in zip(audit, audit[1:])
        )


def test_self_care_has_two_key_approval_and_citations():
    with TestClient(app) as client:
        headers = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=headers, json={}).json()
        client.post(f"/api/v1/encounters/{encounter['id']}/consent", headers=headers, json={"accepted": True})
        result = client.post(f"/api/v1/encounters/{encounter['id']}/demo-scenario", headers=headers, json={"scenario_id":"self-care"}).json()
        assert result["gate"]["urgency"] == "Self-Care"
        assert result["gate"]["approved_low_risk"] is True
        assert result["guidance"]["citations"]


def test_a2a_requires_token_and_returns_typed_data():
    with TestClient(app) as client:
        assert client.post("/a2a/triage", json={}).status_code == 401
        card = client.get("/a2a/triage/.well-known/agent-card.json")
        assert card.status_code == 200
        payload = {"jsonrpc":"2.0", "id":"1", "method":"message/send", "params":{"message":{"parts":[{"data":{"text":"mild stable symptom", "scenario":{"triage":"Routine"}}}]}}}
        response = client.post("/a2a/triage", headers={"Authorization":"Bearer demo-a2a-token"}, json=payload)
        assert response.status_code == 200
        assert response.json()["result"]["parts"][0]["data"]["urgency"] == "Routine"


def test_mock_mcp_rejects_unallowlisted_tool():
    with TestClient(app) as client:
        response = client.post("/mcp", json={"jsonrpc":"2.0", "id":1, "method":"tools/call", "params":{"name":"delete_everything"}})
        assert response.json()["error"]["code"] == -32601


def test_tenant_repository_filter_hides_encounter():
    with TestClient(app) as client:
        patient = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=patient, json={}).json()
        outsider = User(
            id="outside-patient",
            tenant_id="outside-tenant",
            email="outside@example.test",
            name="Outside Patient",
            role=Role.PATIENT,
        )
        headers = {"Authorization": f"Bearer {create_token(outsider)}"}
        assert client.get(f"/api/v1/encounters/{encounter['id']}", headers=headers).status_code == 404


def test_teach_back_records_failure_then_success():
    with TestClient(app) as client:
        headers = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=headers, json={}).json()
        client.post(
            f"/api/v1/encounters/{encounter['id']}/consent",
            headers=headers,
            json={"accepted": True},
        )
        client.post(
            f"/api/v1/encounters/{encounter['id']}/demo-scenario",
            headers=headers,
            json={"scenario_id": "routine"},
        )
        failed = client.post(
            f"/api/v1/encounters/{encounter['id']}/teach-back",
            headers=headers,
            json={"answer": "I am not sure"},
        ).json()
        assert failed["teach_back"]["understood"] is False
        assert failed["teach_back"]["attempts"] == 1
        passed = client.post(
            f"/api/v1/encounters/{encounter['id']}/teach-back",
            headers=headers,
            json={"answer": "I will seek help sooner if I get worse"},
        ).json()
        assert passed["teach_back"]["understood"] is True
        assert passed["teach_back"]["attempts"] == 2


def test_websocket_ticket_is_authenticated_and_single_use():
    with TestClient(app) as client:
        headers = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=headers, json={}).json()
        ticket = client.post("/api/v1/auth/ws-ticket", headers=headers).json()["ticket"]
        with client.websocket_connect(
            f"/api/v1/ws/encounters/{encounter['id']}?ticket={ticket}"
        ):
            pass
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect(
                f"/api/v1/ws/encounters/{encounter['id']}?ticket={ticket}"
            ):
                pass
        assert closed.value.code == 4401


def test_adaptive_interview_stops_at_three_and_escalates_unknowns():
    with TestClient(app) as client:
        headers = login(client, "patient@demo.carerelay.local", "demo-patient")
        encounter = client.post("/api/v1/encounters", headers=headers, json={}).json()
        client.post(
            f"/api/v1/encounters/{encounter['id']}/consent",
            headers=headers,
            json={"accepted": True},
        )
        current = client.post(
            f"/api/v1/encounters/{encounter['id']}/ingest",
            headers=headers,
            json={"text": "I feel generally unwell.", "input_type": "text"},
        ).json()
        for _ in range(3):
            question = next(item for item in current["questions"] if not item["answered"])
            current = client.post(
                f"/api/v1/encounters/{encounter['id']}/answers",
                headers=headers,
                json={"question_id": question["id"], "answer": "I do not know"},
            ).json()
        assert len(current["questions"]) == 3
        assert current["gate"]["urgency"] == "Same-Day"
        assert "MISSING_CRITICAL_FACT" in current["gate"]["reason_codes"]


def test_audit_rows_reject_mutation():
    with TestClient(app):
        with pytest.raises(RuntimeError, match="append-only"):
            with session_scope() as session:
                record = session.scalar(select(AuditRecord).limit(1))
                assert record is not None
                session.delete(record)
