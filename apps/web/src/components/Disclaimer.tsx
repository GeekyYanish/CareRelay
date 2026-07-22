import { ShieldAlert } from 'lucide-react'

interface DisclaimerProps { compact?: boolean }

export function Disclaimer({ compact = false }: DisclaimerProps) {
  return (
    <aside className={`disclaimer ${compact ? 'disclaimer--compact' : ''}`} aria-label="Clinical decision support disclaimer">
      <ShieldAlert aria-hidden="true" size={18} />
      <p><strong>Decision support prototype.</strong> CareRelay gives urgency guidance and documentation drafts—not diagnoses or treatment plans. Professional review is required.</p>
    </aside>
  )
}

