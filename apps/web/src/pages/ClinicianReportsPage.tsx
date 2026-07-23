import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, FileSearch, Filter, LoaderCircle, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { StatusPill } from '../components/StatusPill'
import type { Urgency } from '../types'

export function ClinicianReportsPage() {
  const [q, setQ] = useState('')
  const [urgency, setUrgency] = useState('')
  const [status, setStatus] = useState('')
  const [assignedTo, setAssignedTo] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 10

  const query = useQuery({
    queryKey: ['clinician-reports', q, urgency, status, assignedTo, page],
    queryFn: () =>
      api.listReports({
        q: q || undefined,
        urgency: urgency || undefined,
        status: status || undefined,
        assigned_to: assignedTo || undefined,
        page,
        page_size: pageSize,
      }),
  })

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((query.data?.total || 0) / pageSize)),
    [query.data?.total],
  )

  return (
    <div className="page-wrap">
      <header className="page-hero compact">
        <div>
          <span className="eyebrow">Clinician reports</span>
          <h1>Authorized encounter archive</h1>
          <p>Search and filter tenant-scoped clinical reports. Signed notes stay immutable; exports are audited.</p>
        </div>
        <Link className="button secondary" to="/clinician">Workspace</Link>
      </header>

      <section className="instrument-card report-filters" aria-label="Report filters">
        <div className="section-heading">
          <div><span className="eyebrow">Filters</span><h2><Filter size={18} /> Find reports</h2></div>
        </div>
        <div className="filter-grid">
          <label>
            Search
            <span className="input-with-icon">
              <Search size={15} />
              <input value={q} onChange={(event) => { setPage(1); setQ(event.target.value) }} placeholder="Patient name or encounter id" />
            </span>
          </label>
          <label>
            Urgency
            <select value={urgency} onChange={(event) => { setPage(1); setUrgency(event.target.value) }}>
              <option value="">All</option>
              {(['Emergency', 'Same-Day', 'Routine', 'Self-Care'] as Urgency[]).map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Report status
            <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value) }}>
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="signed">Signed</option>
              <option value="none">None</option>
            </select>
          </label>
          <label>
            Assignment
            <select value={assignedTo} onChange={(event) => { setPage(1); setAssignedTo(event.target.value) }}>
              <option value="">All</option>
              <option value="me">Assigned to me</option>
              <option value="unassigned">Unassigned</option>
            </select>
          </label>
        </div>
      </section>

      {query.isLoading && (
        <div className="empty-state"><LoaderCircle className="spin" /><h2>Loading reports…</h2></div>
      )}
      {query.isError && (
        <p role="alert" className="form-error">Unable to load reports. Confirm you are signed in as a clinician.</p>
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <div className="empty-state"><FileSearch /><h2>No matching reports</h2><p>Adjust filters or complete a patient intake first.</p></div>
      )}

      {query.data && query.data.items.length > 0 && (
        <div className="report-table-wrap">
          <table className="report-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Urgency</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Assigned</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((item) => (
                <tr key={item.encounter_id}>
                  <td>
                    <strong>{item.patient_name}</strong>
                    <small className="mono">{item.encounter_id.slice(0, 8)}</small>
                  </td>
                  <td>{item.urgency ? <StatusPill urgency={item.urgency} /> : '—'}</td>
                  <td><code>{item.report_status}</code></td>
                  <td>{new Date(item.updated_at).toLocaleString()}</td>
                  <td>{item.assigned_clinician_id ? item.assigned_clinician_id.slice(0, 8) : 'Unassigned'}</td>
                  <td>
                    <Link className="button ghost" to={`/clinician/reports/${item.encounter_id}`}>
                      Open <ChevronRight size={15} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button className="button secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
              <ChevronLeft size={16} /> Previous
            </button>
            <span>Page {page} of {totalPages} · {query.data.total} total</span>
            <button className="button secondary" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
