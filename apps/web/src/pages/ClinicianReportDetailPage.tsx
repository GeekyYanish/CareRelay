import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileDown, LoaderCircle, UserCheck } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import { UncertaintyMap } from '../components/UncertaintyMap'
import { useAuth } from '../stores/auth'

export function ClinicianReportDetailPage() {
  const { encounterId = '' } = useParams()
  const user = useAuth((state) => state.user)
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['clinician-report', encounterId],
    queryFn: () => api.getReport(encounterId),
    enabled: Boolean(encounterId),
  })
  const assign = useMutation({
    mutationFn: () => api.assignReport(encounterId, user?.id || null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clinician-report', encounterId] }),
  })

  if (query.isLoading) {
    return <div className="page-wrap"><div className="empty-state"><LoaderCircle className="spin" /><h2>Loading report…</h2></div></div>
  }
  if (query.isError || !query.data) {
    return (
      <div className="page-wrap">
        <p role="alert" className="form-error">Report not found or not authorized for your tenant.</p>
        <Link className="button secondary" to="/clinician/reports"><ArrowLeft size={16} /> Back to reports</Link>
      </div>
    )
  }

  const detail = query.data
  const encounter = detail.encounter
  const token = localStorage.getItem('carerelay-token')

  return (
    <div className="page-wrap">
      <header className="record-header">
        <div>
          <Link className="button ghost" to="/clinician/reports"><ArrowLeft size={16} /> Reports</Link>
          <span className="eyebrow">Report · <code>{encounter.id.slice(0, 8)}</code></span>
          <h1>{encounter.patient_name}</h1>
          <p>{encounter.triage?.rationale_summary || 'Clinical encounter report'}</p>
        </div>
        <div className="report-actions">
          {encounter.gate && <StatusPill urgency={encounter.gate.urgency} large />}
          <button className="button secondary" type="button" disabled={assign.isPending} onClick={() => assign.mutate()}>
            <UserCheck size={16} /> {assign.isPending ? 'Assigning…' : 'Assign to me'}
          </button>
          <a
            className="button primary"
            href={`/api/v1/clinician/reports/${encounter.id}/export`}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => {
              event.preventDefault()
              void fetch(`/api/v1/clinician/reports/${encounter.id}/export`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              })
                .then(async (response) => {
                  const html = await response.text()
                  const popup = window.open('', '_blank')
                  if (popup) {
                    popup.document.write(html)
                    popup.document.close()
                  }
                })
            }}
          >
            <FileDown size={16} /> Export / Print PDF
          </a>
        </div>
      </header>

      <div className="clinical-grid">
        <div>
          {encounter.uncertainty_map && <UncertaintyMap map={encounter.uncertainty_map} />}
          <section className="instrument-card">
            <div className="section-heading"><div><span className="eyebrow">Assignment</span><h2>Ownership</h2></div></div>
            <p>Assigned clinician: <code>{detail.assigned_clinician_id || 'unassigned'}</code></p>
            <p>Report status: <code>{detail.report_status}</code></p>
            <p>Teach-back: {encounter.teach_back?.understood ? 'Confirmed' : encounter.teach_back ? 'Incomplete' : 'Not started'}</p>
          </section>
          <section className="instrument-card">
            <div className="section-heading"><div><span className="eyebrow">Citations</span><h2>Evidence</h2></div></div>
            {detail.citations.length ? detail.citations.map((citation) => (
              <article key={citation.source_id} className="citation-row">
                <strong>{citation.title}</strong>
                <p>{citation.excerpt}</p>
              </article>
            )) : <p>No citations attached.</p>}
          </section>
        </div>
        <div>
          <section className="instrument-card soap">
            <div className="section-heading">
              <div><span className="eyebrow">SOAP</span><h2>Current draft / signed note</h2></div>
              <span className={`draft-state ${encounter.soap?.status || 'none'}`}>{encounter.soap?.status || 'none'}</span>
            </div>
            {encounter.soap ? Object.entries(encounter.soap.sections).map(([name, lines]) => (
              <div key={name} className="soap-readonly">
                <h3>{name}</h3>
                <ul>{lines.map((line) => (
                  <li key={line.id}>
                    {line.text}
                    <div className="provenance">{line.provenance.map((item) => (
                      <span key={`${item.source_id}-${item.source_type}`}>{item.source_type}: {item.label}</span>
                    ))}</div>
                  </li>
                ))}</ul>
              </div>
            )) : <p>No SOAP content yet.</p>}
          </section>

          <section className="instrument-card">
            <div className="section-heading"><div><span className="eyebrow">Version history</span><h2>SOAP revisions</h2></div></div>
            {detail.soap_revisions.length ? (
              <table className="report-table">
                <thead><tr><th>Ver</th><th>Status</th><th>Summary</th><th>At</th></tr></thead>
                <tbody>
                  {detail.soap_revisions.map((rev) => (
                    <tr key={rev.id}>
                      <td>{rev.version}</td>
                      <td><code>{rev.status}</code></td>
                      <td>{rev.change_summary}</td>
                      <td>{new Date(rev.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p>No revisions recorded.</p>}
          </section>

          <section className="instrument-card">
            <div className="section-heading"><div><span className="eyebrow">Escalations</span><h2>Reviewer history</h2></div></div>
            {detail.escalations.length ? detail.escalations.map((item) => (
              <article key={String(item.id)} className="escalation-mini">
                <code>{String(item.status)}</code> · {String(item.urgency)} · {String(item.reason)}
                {item.resolution_category ? <div>Category: {String(item.resolution_category)}</div> : null}
                {item.resolution_note ? <p>{String(item.resolution_note)}</p> : null}
              </article>
            )) : <p>No escalations for this encounter.</p>}
          </section>

          <Timeline events={encounter.timeline} />
        </div>
      </div>
    </div>
  )
}
