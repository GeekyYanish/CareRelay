import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Inbox, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { StatusPill } from '../components/StatusPill'

const categories = [
  { value: 'clinical_handoff', label: 'Clinical handoff' },
  { value: 'patient_advised', label: 'Patient advised' },
  { value: 'false_alarm', label: 'False alarm' },
  { value: 'needs_follow_up', label: 'Needs follow-up' },
  { value: 'other', label: 'Other' },
] as const

export function ReviewerPage() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['escalations'], queryFn: api.escalations })
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [categoriesById, setCategoriesById] = useState<Record<string, string>>({})
  async function refresh(action: Promise<unknown>) {
    await action
    await client.invalidateQueries({ queryKey: ['escalations'] })
  }
  const open = query.data?.filter((item) => item.status !== 'resolved') || []
  return (
    <div className="page-wrap">
      <header className="page-hero compact">
        <div>
          <span className="eyebrow">Human safety net</span>
          <h1>Escalation console</h1>
          <p>Priority-sorted queue with SLA age. Resolve only with a category and audit note.</p>
        </div>
        <div className="hero-seal danger">
          <ShieldAlert />
          <strong>{open.length} open</strong>
          <span>requires attention</span>
        </div>
      </header>
      {query.data?.length ? (
        <div className="escalation-list">
          {query.data.map((item) => (
            <article key={item.id} className={item.status === 'resolved' ? 'resolved' : ''}>
              <div className="escalation-top">
                <span className="avatar">{item.patient_name?.slice(0, 1) || 'P'}</span>
                <div>
                  <span className="eyebrow">Case {item.id.slice(0, 8)}</span>
                  <h2>{item.patient_name}</h2>
                </div>
                <StatusPill urgency={item.urgency} />
                <span className="case-state">{item.status}</span>
              </div>
              <div className="sla-row">
                <span>Age: {item.age_hours ?? 0}h</span>
                <span>SLA: {item.sla_hours ?? 24}h</span>
                {item.sla_breached ? <strong className="sla-breach">SLA breached</strong> : <span>Within SLA</span>}
              </div>
              <div className="reason-box">
                <code>{item.reason}</code>
                <p>Safety gate created this case automatically. Review the encounter evidence before resolving.</p>
              </div>
              {item.status === 'open' && (
                <button className="button secondary" onClick={() => refresh(api.claim(item.id))}>
                  Claim case
                </button>
              )}
              {item.status === 'claimed' && (
                <div className="resolution">
                  <label>
                    Resolution category
                    <select
                      value={categoriesById[item.id] || 'clinical_handoff'}
                      onChange={(event) =>
                        setCategoriesById((current) => ({ ...current, [item.id]: event.target.value }))
                      }
                    >
                      {categories.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Resolution note
                    <textarea
                      value={notes[item.id] || ''}
                      onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))}
                    />
                  </label>
                  <button
                    className="button primary"
                    disabled={(notes[item.id] || '').length < 5}
                    onClick={() =>
                      refresh(
                        api.resolve(
                          item.id,
                          notes[item.id],
                          categoriesById[item.id] || 'clinical_handoff',
                        ),
                      )
                    }
                  >
                    <CheckCircle2 />Resolve with audit note
                  </button>
                </div>
              )}
              {item.status === 'resolved' && (
                <p className="resolved-note">
                  <CheckCircle2 />
                  [{item.resolution_category || 'clinical_handoff'}] {item.resolution_note}
                </p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Inbox />
          <h2>The queue is clear</h2>
          <p>New escalations will appear here when an intake needs human review.</p>
        </div>
      )}
    </div>
  )
}
