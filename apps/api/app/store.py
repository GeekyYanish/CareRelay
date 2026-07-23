from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from .auth import hash_password
from .database import session_scope
from .db.models import AuditRecord, EncounterRecord, EscalationRecord, UserRecord
from .schemas import EncounterView, Role, User


class Store:
    tenant_id = "care-relay"

    def find_user(self, email: str) -> UserRecord | None:
        with session_scope() as session:
            return session.scalar(select(UserRecord).where(UserRecord.email == email))

    def create_user(
        self,
        *,
        email: str,
        password: str,
        name: str,
        role: Role = Role.PATIENT,
        tenant_id: str | None = None,
    ) -> User:
        normalized = email.strip().lower()
        with session_scope() as session:
            if session.scalar(select(UserRecord).where(UserRecord.email == normalized)):
                raise ValueError("EMAIL_TAKEN")
            record = UserRecord(
                id=str(uuid4()),
                tenant_id=tenant_id or self.tenant_id,
                email=normalized,
                name=name.strip(),
                role=role.value,
                password_hash=hash_password(password),
            )
            session.add(record)
            session.flush()
            return self.user_view(record)

    @staticmethod
    def user_view(record: UserRecord) -> User:
        return User(id=record.id, tenant_id=record.tenant_id, email=record.email, name=record.name, role=Role(record.role))

    def create_encounter(self, user: User) -> EncounterView:
        encounter_id = str(uuid4())
        payload = {
            "id": encounter_id,
            "tenant_id": user.tenant_id,
            "patient_id": user.id,
            "patient_name": user.name,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "consent": {"accepted": False},
            "transcript": [],
            "questions": [],
            "answers": [],
            "timeline": [],
        }
        with session_scope() as session:
            session.add(
                EncounterRecord(
                    id=encounter_id,
                    tenant_id=user.tenant_id,
                    patient_id=payload["patient_id"],
                    status="created",
                    payload=payload,
                )
            )
        self.audit(user.tenant_id, encounter_id, user.id, "encounter.created", {})
        return EncounterView.model_validate(payload)

    def get_encounter(self, tenant_id: str, encounter_id: str) -> EncounterView | None:
        with session_scope() as session:
            record = session.scalar(
                select(EncounterRecord).where(
                    EncounterRecord.id == encounter_id, EncounterRecord.tenant_id == tenant_id
                )
            )
            return EncounterView.model_validate(record.payload) if record else None

    def list_encounters(self, user: User) -> list[EncounterView]:
        with session_scope() as session:
            query = select(EncounterRecord).where(EncounterRecord.tenant_id == user.tenant_id)
            if user.role == Role.PATIENT:
                query = query.where(EncounterRecord.patient_id == user.id)
            records = session.scalars(query.order_by(EncounterRecord.created_at.desc())).all()
            return [EncounterView.model_validate(record.payload) for record in records]

    def save_encounter(self, encounter: EncounterView) -> EncounterView:
        with session_scope() as session:
            record = session.scalar(
                select(EncounterRecord).where(
                    EncounterRecord.id == encounter.id, EncounterRecord.tenant_id == encounter.tenant_id
                )
            )
            if not record:
                raise KeyError(encounter.id)
            record.status = encounter.status
            record.payload = encounter.model_dump(mode="json")
        return encounter

    def create_escalation(self, encounter: EncounterView, reason: str) -> dict[str, Any]:
        with session_scope() as session:
            existing = session.scalar(
                select(EscalationRecord).where(
                    EscalationRecord.encounter_id == encounter.id,
                    EscalationRecord.status.in_(["open", "claimed"]),
                )
            )
            if existing:
                return self.escalation_view(existing)
            record = EscalationRecord(
                id=str(uuid4()),
                tenant_id=encounter.tenant_id,
                encounter_id=encounter.id,
                status="open",
                urgency=encounter.gate.urgency.value if encounter.gate else "Same-Day",
                reason=reason,
                payload={"patient_name": encounter.patient_name, "created_at": datetime.now(timezone.utc).isoformat()},
            )
            session.add(record)
            session.flush()
            return self.escalation_view(record)

    def list_escalations(self, tenant_id: str) -> list[dict[str, Any]]:
        with session_scope() as session:
            records = session.scalars(
                select(EscalationRecord).where(EscalationRecord.tenant_id == tenant_id)
            ).all()
            return [self.escalation_view(record) for record in records]

    def update_escalation(self, tenant_id: str, escalation_id: str, status: str, user_id: str, note: str | None = None) -> dict[str, Any]:
        with session_scope() as session:
            record = session.scalar(
                select(EscalationRecord).where(
                    EscalationRecord.id == escalation_id, EscalationRecord.tenant_id == tenant_id
                )
            )
            if not record:
                raise KeyError(escalation_id)
            record.status = status
            record.assigned_to = user_id
            record.resolution_note = note
            session.flush()
            return self.escalation_view(record)

    @staticmethod
    def escalation_view(record: EscalationRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "encounter_id": record.encounter_id,
            "status": record.status,
            "urgency": record.urgency,
            "reason": record.reason,
            "assigned_to": record.assigned_to,
            "resolution_note": record.resolution_note,
            **(record.payload or {}),
        }

    def audit(self, tenant_id: str, encounter_id: str | None, actor_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with session_scope() as session:
            previous = session.scalar(
                select(AuditRecord).where(AuditRecord.tenant_id == tenant_id).order_by(AuditRecord.timestamp.desc())
            )
            previous_hash = previous.event_hash if previous else "0" * 64
            timestamp = datetime.now(timezone.utc)
            canonical = json.dumps(
                {"tenant_id": tenant_id, "encounter_id": encounter_id, "actor_id": actor_id, "event_type": event_type, "timestamp": timestamp.isoformat(), "payload": payload, "previous_hash": previous_hash},
                sort_keys=True,
            )
            session.add(
                AuditRecord(
                    id=str(uuid4()), tenant_id=tenant_id, encounter_id=encounter_id,
                    actor_id=actor_id, event_type=event_type, timestamp=timestamp, payload=payload,
                    previous_hash=previous_hash, event_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                )
            )

    def audit_events(self, tenant_id: str, encounter_id: str) -> list[dict[str, Any]]:
        with session_scope() as session:
            records = session.scalars(
                select(AuditRecord).where(
                    AuditRecord.tenant_id == tenant_id, AuditRecord.encounter_id == encounter_id
                ).order_by(AuditRecord.timestamp)
            ).all()
            return [
                {"id": record.id, "event_type": record.event_type, "actor_id": record.actor_id,
                 "timestamp": record.timestamp, "payload": record.payload, "previous_hash": record.previous_hash,
                 "event_hash": record.event_hash}
                for record in records
            ]
