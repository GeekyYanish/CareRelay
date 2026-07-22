import { AlertTriangle, CheckCircle2, Clock3, Siren } from 'lucide-react'
import type { Urgency } from '../types'

const icons = { Emergency: Siren, 'Same-Day': AlertTriangle, Routine: Clock3, 'Self-Care': CheckCircle2 }

interface StatusPillProps { urgency: Urgency; large?: boolean }

export function StatusPill({ urgency, large = false }: StatusPillProps) {
  const Icon = icons[urgency]
  return <span className={`status-pill status-pill--${urgency.toLowerCase().replaceAll('-', '')} ${large ? 'status-pill--large' : ''}`}><Icon size={large ? 22 : 15} aria-hidden="true" />{urgency}</span>
}

