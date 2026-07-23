from __future__ import annotations

from html import escape
from typing import Any

from .schemas import EvidenceCitation, ReportDetail, ReportListResponse, User
from .store import Store


class ReportService:
    def __init__(self, store: Store):
        self.store = store

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
        return self.store.list_reports(
            user,
            q=q,
            urgency=urgency,
            status=status,
            assigned_to=assigned_to,
            page=page,
            page_size=page_size,
        )

    def get_report(self, user: User, encounter_id: str) -> ReportDetail:
        encounter = self.store.get_encounter(user.tenant_id, encounter_id)
        if not encounter:
            raise KeyError(encounter_id)
        revisions = self.store.list_soap_revisions(user.tenant_id, encounter_id)
        escalations = self.store.list_escalations_for_encounter(user.tenant_id, encounter_id)
        audit_timeline = self.store.audit_events(user.tenant_id, encounter_id)
        citations: list[EvidenceCitation] = []
        if encounter.guidance and encounter.guidance.get("citations"):
            citations = [EvidenceCitation.model_validate(item) for item in encounter.guidance["citations"]]
        elif encounter.triage:
            citations = encounter.triage.citations
        report_status = encounter.soap.status if encounter.soap else "none"
        self.store.audit(
            user.tenant_id,
            encounter_id,
            user.id,
            "report.viewed",
            {"report_status": report_status},
        )
        return ReportDetail(
            encounter=encounter,
            report_status=report_status,  # type: ignore[arg-type]
            assigned_clinician_id=encounter.assigned_clinician_id,
            soap_revisions=revisions,
            escalations=escalations,
            audit_timeline=audit_timeline,
            citations=citations,
        )

    def export_html(self, user: User, encounter_id: str) -> str:
        detail = self.get_report(user, encounter_id)
        encounter = detail.encounter
        self.store.audit(
            user.tenant_id,
            encounter_id,
            user.id,
            "report.exported",
            {"format": "html"},
        )
        urgency = encounter.gate.urgency.value if encounter.gate else "—"
        teach = encounter.teach_back or {}
        soap_blocks = ""
        if encounter.soap:
            for section, sentences in encounter.soap.sections.items():
                lines = "".join(
                    f"<li>{escape(sentence.text)} "
                    f"<small>({escape(', '.join(p.label for p in sentence.provenance))})</small></li>"
                    for sentence in sentences
                )
                soap_blocks += f"<h3>{escape(section)}</h3><ol>{lines}</ol>"
        revision_rows = "".join(
            f"<tr><td>{rev.version}</td><td>{escape(rev.status)}</td>"
            f"<td>{escape(rev.author_id[:8])}</td><td>{escape(rev.change_summary)}</td>"
            f"<td>{rev.created_at.isoformat()}</td></tr>"
            for rev in detail.soap_revisions
        )
        escalation_rows = "".join(
            f"<tr><td>{escape(str(item.get('status')))}</td>"
            f"<td>{escape(str(item.get('urgency')))}</td>"
            f"<td>{escape(str(item.get('reason')))}</td>"
            f"<td>{escape(str(item.get('resolution_category') or '—'))}</td>"
            f"<td>{escape(str(item.get('resolution_note') or '—'))}</td></tr>"
            for item in detail.escalations
        )
        citations = "".join(
            f"<li><strong>{escape(c.title)}</strong> — {escape(c.excerpt)}</li>"
            for c in detail.citations
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>CareRelay report {escape(encounter.id[:8])}</title>
  <style>
    body {{ font-family: Georgia, serif; color: #102018; margin: 32px; }}
    h1,h2,h3 {{ font-family: system-ui, sans-serif; }}
    .meta {{ color: #52635c; margin-bottom: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #c9d5cf; padding: 8px; text-align: left; font-size: 14px; }}
    .disclaimer {{ border-left: 4px solid #c48a2a; background: #fff8e9; padding: 12px; }}
    @media print {{ button {{ display: none; }} }}
  </style>
</head>
<body>
  <button onclick="window.print()">Print / Save as PDF</button>
  <p class="disclaimer"><strong>Decision support only.</strong> Not a diagnosis, prescription, or EHR record.</p>
  <h1>Clinical encounter report</h1>
  <div class="meta">
    <div>Encounter: <code>{escape(encounter.id)}</code></div>
    <div>Patient: {escape(encounter.patient_name)}</div>
    <div>Urgency (gated): {escape(urgency)}</div>
    <div>Report status: {escape(detail.report_status)}</div>
    <div>Assigned clinician: {escape(detail.assigned_clinician_id or "unassigned")}</div>
    <div>Created: {escape(encounter.created_at.isoformat())}</div>
  </div>
  <h2>SOAP</h2>
  {soap_blocks or "<p>No SOAP draft.</p>"}
  <h2>Uncertainty</h2>
  <pre>{escape(encounter.uncertainty_map.model_dump_json(indent=2) if encounter.uncertainty_map else "{{}}")}</pre>
  <h2>Citations</h2>
  <ul>{citations or "<li>None</li>"}</ul>
  <h2>Teach-back</h2>
  <p>{escape(str(teach.get("message") or teach.get("understood") or "Not completed"))}</p>
  <h2>SOAP revisions</h2>
  <table><thead><tr><th>Ver</th><th>Status</th><th>Author</th><th>Summary</th><th>At</th></tr></thead>
  <tbody>{revision_rows or "<tr><td colspan='5'>None</td></tr>"}</tbody></table>
  <h2>Escalations</h2>
  <table><thead><tr><th>Status</th><th>Urgency</th><th>Reason</th><th>Category</th><th>Note</th></tr></thead>
  <tbody>{escalation_rows or "<tr><td colspan='5'>None</td></tr>"}</tbody></table>
</body>
</html>"""
