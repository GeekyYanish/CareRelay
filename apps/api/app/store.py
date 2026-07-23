from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import String, and_, cast, func, or_, select

from .auth import hash_password
from .core import get_settings
from .database import session_scope
from .db.models import AuditRecord, EncounterRecord, EscalationRecord, SoapRevisionRecord, UserRecord
from .report_cache import get_report_list_cache
from .schemas import (
    EncounterView,
    ReportListResponse,
    ReportSummary,
    Role,
    SoapRevisionView,
    Urgency,
    User,
)


class Store:
    tenant_id = "care-relay"

    def __init__(self) -> None:
        path = Path(get_settings().demo_data_path)
        if not path.is_absolute():
            path = (Path(__file__).parent / path).resolve()
        if path.exists():
            self.scenarios = {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))}
        else:
            self.scenarios = {}

    def find_user(self, email: str) -> UserRecord | None:
        with session_scope() as session:
            return session.scalar(select(UserRecord).where(UserRecord.email == email))

    def get_user(self, tenant_id: str, user_id: str) -> User | None:
        with session_scope() as session:
            record = session.scalar(
                select(UserRecord).where(UserRecord.id == user_id, UserRecord.tenant_id == tenant_id)
            )
            return self.user_view(record) if record else None

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
        return User(
            id=record.id,
            tenant_id=record.tenant_id,
            email=record.email,
            name=record.name,
            role=Role(record.role),
        )

    @staticmethod
    def _report_fields(encounter: EncounterView) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        report_status = "none"
        if encounter.soap:
            report_status = encounter.soap.status
        return {
            "status": encounter.status,
            "urgency": encounter.gate.urgency.value if encounter.gate else None,
            "report_status": report_status,
            "assigned_clinician_id": encounter.assigned_clinician_id,
            "updated_at": now,
            "payload": encounter.model_dump(mode="json"),
        }

    def create_encounter(self, user: User) -> EncounterView:
        encounter_id = str(uuid4())
        now = datetime.now(timezone.utc)
        payload = {
            "id": encounter_id,
            "tenant_id": user.tenant_id,
            "patient_id": user.id,
            "patient_name": user.name,
            "status": "created",
            "created_at": now.isoformat(),
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
                    created_at=now,
                    updated_at=now,
                    report_status="none",
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
            if not record:
                return None
            view = EncounterView.model_validate(record.payload)
            view.assigned_clinician_id = record.assigned_clinician_id
            return view

    def list_encounters(self, user: User) -> list[EncounterView]:
        with session_scope() as session:
            query = select(EncounterRecord).where(EncounterRecord.tenant_id == user.tenant_id)
            if user.role == Role.PATIENT:
                query = query.where(EncounterRecord.patient_id == user.id)
            records = session.scalars(query.order_by(EncounterRecord.created_at.desc())).all()
            results: list[EncounterView] = []
            for record in records:
                view = EncounterView.model_validate(record.payload)
                view.assigned_clinician_id = record.assigned_clinician_id
                results.append(view)
            return results

    def save_encounter(self, encounter: EncounterView) -> EncounterView:
        fields = self._report_fields(encounter)
        with session_scope() as session:
            record = session.scalar(
                select(EncounterRecord).where(
                    EncounterRecord.id == encounter.id, EncounterRecord.tenant_id == encounter.tenant_id
                )
            )
            if not record:
                raise KeyError(encounter.id)
            record.status = fields["status"]
            record.urgency = fields["urgency"]
            record.report_status = fields["report_status"]
            record.assigned_clinician_id = fields["assigned_clinician_id"]
            record.updated_at = fields["updated_at"]
            record.payload = fields["payload"]
        get_report_list_cache().invalidate_tenant(encounter.tenant_id)
        return encounter

    def assign_clinician(
        self, tenant_id: str, encounter_id: str, clinician_id: str | None, actor: User
    ) -> EncounterView:
        encounter = self.get_encounter(tenant_id, encounter_id)
        if not encounter:
            raise KeyError(encounter_id)
        if clinician_id:
            clinician = self.get_user(tenant_id, clinician_id)
            if not clinician or clinician.role != Role.CLINICIAN:
                raise ValueError("CLINICIAN_NOT_FOUND")
        encounter.assigned_clinician_id = clinician_id
        self.save_encounter(encounter)
        self.audit(
            tenant_id,
            encounter_id,
            actor.id,
            "report.assigned",
            {"assigned_clinician_id": clinician_id},
        )
        return encounter

    def list_reports(
        self,
        user: User,
        *,
        q: str | None = None,
        urgency: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ReportListResponse:
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        fingerprint = json.dumps(
            {
                "q": q or "",
                "urgency": urgency or "",
                "status": status or "",
                "assigned_to": assigned_to or "",
                "page": page,
                "page_size": page_size,
                "role": user.role.value,
                "uid": user.id,
            },
            sort_keys=True,
        )
        cache = get_report_list_cache()
        cached = cache.get(user.tenant_id, fingerprint)
        if cached:
            return ReportListResponse.model_validate(cached)
        with session_scope() as session:
            filters = [EncounterRecord.tenant_id == user.tenant_id]
            if user.role == Role.PATIENT:
                filters.append(EncounterRecord.patient_id == user.id)
            if urgency:
                filters.append(EncounterRecord.urgency == urgency)
            if status:
                filters.append(EncounterRecord.report_status == status)
            if assigned_to == "me" and user.role == Role.CLINICIAN:
                filters.append(EncounterRecord.assigned_clinician_id == user.id)
            elif assigned_to == "unassigned":
                filters.append(EncounterRecord.assigned_clinician_id.is_(None))
            elif assigned_to:
                filters.append(EncounterRecord.assigned_clinician_id == assigned_to)
            if q:
                like = f"%{q}%"
                filters.append(
                    or_(
                        EncounterRecord.id.ilike(like),
                        cast(EncounterRecord.payload["patient_name"], String).ilike(like),
                    )
                )
            where = and_(*filters)
            total = session.scalar(select(func.count()).select_from(EncounterRecord).where(where)) or 0
            records = session.scalars(
                select(EncounterRecord)
                .where(where)
                .order_by(EncounterRecord.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            items: list[ReportSummary] = []
            for record in records:
                payload = record.payload or {}
                teach = payload.get("teach_back") or {}
                gate = payload.get("gate") or {}
                soap = payload.get("soap") or {}
                urgency_value = record.urgency or gate.get("urgency")
                items.append(
                    ReportSummary(
                        encounter_id=record.id,
                        patient_id=record.patient_id,
                        patient_name=str(payload.get("patient_name") or "Patient"),
                        status=record.status,
                        report_status=record.report_status or "none",  # type: ignore[arg-type]
                        urgency=Urgency(urgency_value) if urgency_value else None,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                        assigned_clinician_id=record.assigned_clinician_id,
                        soap_signed=soap.get("status") == "signed",
                        escalated=bool(gate.get("escalated")),
                        teach_back_understood=teach.get("understood") if teach else None,
                    )
                )
            result = ReportListResponse(items=items, page=page, page_size=page_size, total=total)
            cache.set(user.tenant_id, fingerprint, result.model_dump(mode="json"))
            return result

    def next_soap_version(self, encounter_id: str) -> int:
        with session_scope() as session:
            current = session.scalar(
                select(func.max(SoapRevisionRecord.version)).where(
                    SoapRevisionRecord.encounter_id == encounter_id
                )
            )
            return int(current or 0) + 1

    def add_soap_revision(
        self,
        *,
        tenant_id: str,
        encounter_id: str,
        version: int,
        status: str,
        sections: dict[str, Any],
        author_id: str,
        change_summary: str,
        signed_at: datetime | None = None,
    ) -> SoapRevisionView:
        record = SoapRevisionRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            encounter_id=encounter_id,
            version=version,
            status=status,
            sections=sections,
            author_id=author_id,
            change_summary=change_summary[:500],
            created_at=datetime.now(timezone.utc),
            signed_at=signed_at,
        )
        with session_scope() as session:
            session.add(record)
            session.flush()
            return self.soap_revision_view(record)

    def list_soap_revisions(self, tenant_id: str, encounter_id: str) -> list[SoapRevisionView]:
        with session_scope() as session:
            records = session.scalars(
                select(SoapRevisionRecord)
                .where(
                    SoapRevisionRecord.tenant_id == tenant_id,
                    SoapRevisionRecord.encounter_id == encounter_id,
                )
                .order_by(SoapRevisionRecord.version.asc())
            ).all()
            return [self.soap_revision_view(record) for record in records]

    @staticmethod
    def soap_revision_view(record: SoapRevisionRecord) -> SoapRevisionView:
        return SoapRevisionView(
            id=record.id,
            encounter_id=record.encounter_id,
            version=record.version,
            status=record.status,  # type: ignore[arg-type]
            sections=record.sections,
            author_id=record.author_id,
            change_summary=record.change_summary or "",
            created_at=record.created_at,
            signed_at=record.signed_at,
        )

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
            now = datetime.now(timezone.utc)
            record = EscalationRecord(
                id=str(uuid4()),
                tenant_id=encounter.tenant_id,
                encounter_id=encounter.id,
                status="open",
                urgency=encounter.gate.urgency.value if encounter.gate else "Same-Day",
                reason=reason,
                created_at=now,
                payload={
                    "patient_name": encounter.patient_name,
                    "created_at": now.isoformat(),
                },
            )
            session.add(record)
            session.flush()
            return self.escalation_view(record)

    def list_escalations(self, tenant_id: str) -> list[dict[str, Any]]:
        urgency_rank = {"Emergency": 3, "Same-Day": 2, "Routine": 1, "Self-Care": 0}
        with session_scope() as session:
            records = list(
                session.scalars(
                    select(EscalationRecord).where(EscalationRecord.tenant_id == tenant_id)
                ).all()
            )
            records.sort(
                key=lambda item: (
                    0 if item.status != "resolved" else 1,
                    -urgency_rank.get(item.urgency, 0),
                    item.created_at or datetime.now(timezone.utc),
                )
            )
            return [self.escalation_view(record) for record in records]

    def list_escalations_for_encounter(self, tenant_id: str, encounter_id: str) -> list[dict[str, Any]]:
        with session_scope() as session:
            records = session.scalars(
                select(EscalationRecord).where(
                    EscalationRecord.tenant_id == tenant_id,
                    EscalationRecord.encounter_id == encounter_id,
                )
            ).all()
            return [self.escalation_view(record) for record in records]

    def update_escalation(
        self,
        tenant_id: str,
        escalation_id: str,
        status: str,
        user_id: str,
        note: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
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
            if note is not None:
                record.resolution_note = note
            if category is not None:
                record.resolution_category = category
            session.flush()
            return self.escalation_view(record)

    @staticmethod
    def escalation_view(record: EscalationRecord) -> dict[str, Any]:
        created = record.created_at or datetime.now(timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 3600)
        sla_hours = {"Emergency": 1.0, "Same-Day": 4.0, "Routine": 24.0, "Self-Care": 48.0}.get(
            record.urgency, 24.0
        )
        return {
            "id": record.id,
            "encounter_id": record.encounter_id,
            "status": record.status,
            "urgency": record.urgency,
            "reason": record.reason,
            "assigned_to": record.assigned_to,
            "resolution_note": record.resolution_note,
            "resolution_category": record.resolution_category,
            "created_at": created.isoformat(),
            "age_hours": round(age_hours, 2),
            "sla_hours": sla_hours,
            "sla_breached": record.status != "resolved" and age_hours > sla_hours,
            **(record.payload or {}),
        }

    def audit(
        self,
        tenant_id: str,
        encounter_id: str | None,
        actor_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        with session_scope() as session:
            previous = session.scalar(
                select(AuditRecord)
                .where(AuditRecord.tenant_id == tenant_id)
                .order_by(AuditRecord.timestamp.desc())
            )
            previous_hash = previous.event_hash if previous else "0" * 64
            timestamp = datetime.now(timezone.utc)
            canonical = json.dumps(
                {
                    "tenant_id": tenant_id,
                    "encounter_id": encounter_id,
                    "actor_id": actor_id,
                    "event_type": event_type,
                    "timestamp": timestamp.isoformat(),
                    "payload": payload,
                    "previous_hash": previous_hash,
                },
                sort_keys=True,
            )
            session.add(
                AuditRecord(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    encounter_id=encounter_id,
                    actor_id=actor_id,
                    event_type=event_type,
                    timestamp=timestamp,
                    payload=payload,
                    previous_hash=previous_hash,
                    event_hash=hashlib.sha256(canonical.encode()).hexdigest(),
                )
            )

    def audit_events(self, tenant_id: str, encounter_id: str) -> list[dict[str, Any]]:
        with session_scope() as session:
            records = session.scalars(
                select(AuditRecord)
                .where(
                    AuditRecord.tenant_id == tenant_id,
                    AuditRecord.encounter_id == encounter_id,
                )
                .order_by(AuditRecord.timestamp)
            ).all()
            return [
                {
                    "id": record.id,
                    "event_type": record.event_type,
                    "actor_id": record.actor_id,
                    "timestamp": record.timestamp,
                    "payload": record.payload,
                    "previous_hash": record.previous_hash,
                    "event_hash": record.event_hash,
                }
                for record in records
            ]
