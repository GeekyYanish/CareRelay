"""Clinician reports: RBAC, tenant isolation, and signed SOAP immutability."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.schemas import (
    EncounterView,
    Role,
    SoapDraft,
    SoapSentence,
    Urgency,
    User,
)
from app.services import EncounterService


class MemoryStore:
    def __init__(self) -> None:
        self.encounters: dict[str, EncounterView] = {}
        self.revisions: list[dict] = []
        self.audits: list[dict] = []
        self.scenarios: dict = {}

    def get_encounter(self, tenant_id: str, encounter_id: str) -> EncounterView | None:
        encounter = self.encounters.get(encounter_id)
        if not encounter or encounter.tenant_id != tenant_id:
            return None
        return encounter

    def save_encounter(self, encounter: EncounterView) -> EncounterView:
        self.encounters[encounter.id] = encounter
        return encounter

    def next_soap_version(self, encounter_id: str) -> int:
        versions = [item["version"] for item in self.revisions if item["encounter_id"] == encounter_id]
        return (max(versions) if versions else 0) + 1

    def add_soap_revision(self, **kwargs):
        self.revisions.append(kwargs)
        return kwargs

    def audit(self, tenant_id, encounter_id, actor_id, event_type, payload):
        self.audits.append(
            {
                "tenant_id": tenant_id,
                "encounter_id": encounter_id,
                "actor_id": actor_id,
                "event_type": event_type,
                "payload": payload,
            }
        )


def _soap() -> SoapDraft:
    return SoapDraft(
        sections={
            "Subjective": [
                SoapSentence(
                    text="Patient reports mild symptoms",
                    confidence=0.9,
                    provenance=[
                        {
                            "source_id": "TRANSCRIPT-1",
                            "source_type": "patient",
                            "label": "Patient report",
                        }
                    ],
                )
            ]
        }
    )


def test_signed_soap_edit_creates_new_draft_revision():
    store = MemoryStore()
    service = EncounterService(store, rules=None)  # type: ignore[arg-type]
    service.rules = type("R", (), {"scan": lambda self, text: [], "version": "test"})()
    clinician = User(
        id="clin-1",
        tenant_id="tenant-a",
        email="c@x",
        name="Clinician",
        role=Role.CLINICIAN,
    )
    encounter = EncounterView(
        id="enc-1",
        tenant_id="tenant-a",
        patient_id="pat-1",
        patient_name="Maya",
        status="guidance-ready",
        created_at=datetime.now(timezone.utc),
        consent={"accepted": True},
        transcript=[],
        questions=[],
        answers=[],
        timeline=[],
        soap=_soap(),
    )
    encounter.soap.status = "signed"
    encounter.soap.signed_at = datetime.now(timezone.utc)
    store.save_encounter(encounter)

    updated = service.patch_soap(
        encounter,
        {"Subjective": ["Clinician clarified mild improving symptoms"]},
        clinician,
    )
    assert updated.soap is not None
    assert updated.soap.status == "draft"
    assert updated.soap.signed_at is None
    assert any(item["status"] == "draft" for item in store.revisions)
    assert any(item["event_type"] == "soap.edited" for item in store.audits)


def test_sign_soap_rejects_already_signed():
    store = MemoryStore()
    service = EncounterService(store, rules=None)  # type: ignore[arg-type]
    clinician = User(
        id="clin-1",
        tenant_id="tenant-a",
        email="c@x",
        name="Clinician",
        role=Role.CLINICIAN,
    )
    encounter = EncounterView(
        id="enc-2",
        tenant_id="tenant-a",
        patient_id="pat-1",
        patient_name="Maya",
        status="guidance-ready",
        created_at=datetime.now(timezone.utc),
        consent={"accepted": True},
        transcript=[],
        questions=[],
        answers=[],
        timeline=[],
        soap=_soap(),
    )
    encounter.soap.status = "signed"
    with pytest.raises(ValueError, match="already signed"):
        service.sign_soap(encounter, clinician)


@pytest.fixture
def api_client(monkeypatch):
    """HTTP client against the live app settings; skip if database is unavailable."""
    from app.core import get_settings
    from app.database import database_ready

    get_settings.cache_clear()
    if not database_ready():
        pytest.skip("PostgreSQL is not available for API report tests")
    from app.main import app

    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        pytest.skip(f"Demo user {email} not provisioned")
    return response.json()["access_token"]


def test_patient_cannot_list_clinician_reports(api_client: TestClient):
    token = _login(api_client, "patient@demo.carerelay.local", "demo-patient")
    response = api_client.get(
        "/api/v1/clinician/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_clinician_reports_are_tenant_scoped(api_client: TestClient):
    token = _login(api_client, "clinician@demo.carerelay.local", "demo-clinician")
    headers = {"Authorization": f"Bearer {token}"}
    listed = api_client.get("/api/v1/clinician/reports?page=1&page_size=5", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert "items" in body and "total" in body
    foreign = api_client.get(
        f"/api/v1/clinician/reports/{uuid4()}",
        headers=headers,
    )
    assert foreign.status_code == 404


def test_clinician_export_is_html_and_authorized(api_client: TestClient):
    clinician = _login(api_client, "clinician@demo.carerelay.local", "demo-clinician")
    patient = _login(api_client, "patient@demo.carerelay.local", "demo-patient")
    created = api_client.post(
        "/api/v1/encounters",
        headers={"Authorization": f"Bearer {patient}"},
        json={},
    )
    if created.status_code != 200:
        pytest.skip("Unable to create encounter for export test")
    encounter_id = created.json()["id"]
    api_client.post(
        f"/api/v1/encounters/{encounter_id}/consent",
        headers={"Authorization": f"Bearer {patient}"},
        json={"accepted": True, "version": "care-relay-v1"},
    )
    api_client.post(
        f"/api/v1/encounters/{encounter_id}/demo-scenario",
        headers={"Authorization": f"Bearer {patient}"},
        json={"scenario_id": "self-care"},
    )
    export = api_client.get(
        f"/api/v1/clinician/reports/{encounter_id}/export",
        headers={"Authorization": f"Bearer {clinician}"},
    )
    assert export.status_code == 200
    assert "text/html" in export.headers.get("content-type", "")
    assert "Decision support only" in export.text

    patient_export = api_client.get(
        f"/api/v1/clinician/reports/{encounter_id}/export",
        headers={"Authorization": f"Bearer {patient}"},
    )
    assert patient_export.status_code == 403
