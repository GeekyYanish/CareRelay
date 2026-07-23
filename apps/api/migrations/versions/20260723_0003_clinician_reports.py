"""Clinician reports: denormalized encounter columns, SOAP revisions, escalation SLA fields."""

from __future__ import annotations

import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260723_0003"
down_revision = "20260723_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "encounters",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column("encounters", sa.Column("urgency", sa.String(32), nullable=True))
    op.add_column(
        "encounters",
        sa.Column("report_status", sa.String(16), nullable=False, server_default="none"),
    )
    op.add_column("encounters", sa.Column("assigned_clinician_id", sa.String(36), nullable=True))
    op.create_index("ix_encounters_urgency", "encounters", ["urgency"])
    op.create_index("ix_encounters_report_status", "encounters", ["report_status"])
    op.create_index("ix_encounters_assigned_clinician_id", "encounters", ["assigned_clinician_id"])
    op.create_index("ix_encounters_tenant_updated", "encounters", ["tenant_id", "updated_at"])
    op.create_index(
        "ix_encounters_tenant_urgency_status",
        "encounters",
        ["tenant_id", "urgency", "report_status"],
    )

    op.create_table(
        "soap_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("change_summary", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("encounter_id", "version", name="uq_soap_revision_version"),
    )
    op.create_index("ix_soap_revisions_tenant_id", "soap_revisions", ["tenant_id"])
    op.create_index("ix_soap_revisions_encounter_id", "soap_revisions", ["encounter_id"])
    op.create_index("ix_soap_revisions_status", "soap_revisions", ["status"])

    op.add_column("escalations", sa.Column("resolution_category", sa.String(64), nullable=True))
    op.add_column(
        "escalations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_escalations_created_at", "escalations", ["created_at"])
    op.create_index(
        "ix_escalations_tenant_urgency_status",
        "escalations",
        ["tenant_id", "urgency", "status"],
    )

    soap_revisions = sa.table(
        "soap_revisions",
        sa.column("id", sa.String),
        sa.column("tenant_id", sa.String),
        sa.column("encounter_id", sa.String),
        sa.column("version", sa.Integer),
        sa.column("status", sa.String),
        sa.column("sections", sa.JSON),
        sa.column("author_id", sa.String),
        sa.column("change_summary", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("signed_at", sa.DateTime(timezone=True)),
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, tenant_id, patient_id, payload FROM encounters")).mappings().all()
    now = sa.func.now()
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        if not isinstance(payload, dict):
            continue
        soap = payload.get("soap") or {}
        gate = payload.get("gate") or {}
        urgency = gate.get("urgency")
        report_status = soap.get("status") if soap else "none"
        if not report_status:
            report_status = "draft" if soap else "none"
        assigned = payload.get("assigned_clinician_id")
        conn.execute(
            sa.text(
                """
                UPDATE encounters
                SET urgency = :urgency,
                    report_status = :report_status,
                    assigned_clinician_id = :assigned
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "urgency": urgency,
                "report_status": report_status,
                "assigned": assigned,
            },
        )
        sections = soap.get("sections") if isinstance(soap, dict) else None
        if sections:
            from datetime import datetime, timezone

            signed_raw = soap.get("signed_at")
            signed_at = None
            if isinstance(signed_raw, str):
                try:
                    signed_at = datetime.fromisoformat(signed_raw.replace("Z", "+00:00"))
                except ValueError:
                    signed_at = None
            conn.execute(
                sa.insert(soap_revisions).values(
                    id=str(uuid4()),
                    tenant_id=row["tenant_id"],
                    encounter_id=row["id"],
                    version=1,
                    status=soap.get("status") or "draft",
                    sections=sections,
                    author_id=row["patient_id"],
                    change_summary="Backfilled from encounter payload",
                    created_at=datetime.now(timezone.utc),
                    signed_at=signed_at,
                )
            )


def downgrade() -> None:
    op.drop_index("ix_escalations_tenant_urgency_status", table_name="escalations")
    op.drop_index("ix_escalations_created_at", table_name="escalations")
    op.drop_column("escalations", "created_at")
    op.drop_column("escalations", "resolution_category")
    op.drop_index("ix_soap_revisions_status", table_name="soap_revisions")
    op.drop_index("ix_soap_revisions_encounter_id", table_name="soap_revisions")
    op.drop_index("ix_soap_revisions_tenant_id", table_name="soap_revisions")
    op.drop_table("soap_revisions")
    op.drop_index("ix_encounters_tenant_urgency_status", table_name="encounters")
    op.drop_index("ix_encounters_tenant_updated", table_name="encounters")
    op.drop_index("ix_encounters_assigned_clinician_id", table_name="encounters")
    op.drop_index("ix_encounters_report_status", table_name="encounters")
    op.drop_index("ix_encounters_urgency", table_name="encounters")
    op.drop_column("encounters", "assigned_clinician_id")
    op.drop_column("encounters", "report_status")
    op.drop_column("encounters", "urgency")
    op.drop_column("encounters", "updated_at")
