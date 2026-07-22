import { Bot, Check, Database, FileText, ShieldCheck } from 'lucide-react'
import type { TimelineEvent } from '../types'

const labels: Record<string, string> = {
  'intake.received': 'Intake secured',
  'safety.red_flags_checked': 'Deterministic rules checked',
  'retrieval.completed': 'Curated evidence retrieved',
  'triage.proposed': 'Triage proposal ready',
  'critic.completed': 'Independent critic complete',
  'safety.gate_decided': 'Two-key gate decided',
  'documentation.draft_created': 'SOAP draft assembled',
  'escalation.created': 'Reviewer alerted',
}

function iconFor(type: string) {
  if (type.includes('retrieval')) return Database
  if (type.includes('documentation')) return FileText
  if (type.includes('safety') || type.includes('critic')) return ShieldCheck
  if (type.includes('triage')) return Bot
  return Check
}

interface TimelineProps { events: TimelineEvent[] }

export function Timeline({ events }: TimelineProps) {
  return (
    <section className="instrument-card" aria-labelledby="timeline-title">
      <div className="section-heading"><div><span className="eyebrow">Agent trajectory</span><h2 id="timeline-title">What happened, in order</h2></div><span className="live-chip"><i /> complete</span></div>
      <ol className="timeline">
        {events.map((item) => {
          const Icon = iconFor(item.event_type)
          return <li key={item.event_id}><span className="timeline__icon"><Icon size={16} aria-hidden="true" /></span><div><strong>{labels[item.event_type] || item.event_type}</strong><time>{new Date(item.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'})}</time></div></li>
        })}
      </ol>
    </section>
  )
}

