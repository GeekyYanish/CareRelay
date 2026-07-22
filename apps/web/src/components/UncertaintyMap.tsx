import { AlertOctagon, CircleHelp, FileCheck2, GitCompareArrows } from 'lucide-react'
import type { UncertaintyMap as UncertaintyMapType } from '../types'

interface UncertaintyMapProps { map: UncertaintyMapType }

export function UncertaintyMap({ map }: UncertaintyMapProps) {
  const quality = Math.round(map.retrieval_quality * 100)
  const cards = [
    { title: 'Known facts', value: map.known_facts.length, icon: FileCheck2, items: map.known_facts },
    { title: 'Missing facts', value: map.missing_facts.length, icon: CircleHelp, items: map.missing_facts },
    { title: 'Contradictions', value: map.contradictions.length, icon: GitCompareArrows, items: map.contradictions },
    { title: 'Red flags', value: map.red_flags.length, icon: AlertOctagon, items: map.red_flags.map((flag) => `${flag.rule_id}: ${flag.matched_evidence}`) },
  ]
  return (
    <section className="instrument-card" aria-labelledby="uncertainty-title">
      <div className="section-heading"><div><span className="eyebrow">Uncertainty map</span><h2 id="uncertainty-title">Evidence at a glance</h2></div><span className="score">{quality}% evidence quality</span></div>
      <div className="evidence-meter" aria-label={`Retrieval quality ${quality} percent`}><span style={{width:`${quality}%`}} /></div>
      <div className="uncertainty-grid">
        {cards.map(({ title, value, icon: Icon, items }) => <article key={title} className={title === 'Red flags' && value ? 'danger-cell' : ''}><Icon size={19} aria-hidden="true" /><strong>{value}</strong><span>{title}</span>{items[0] && <small title={items[0]}>{items[0]}</small>}</article>)}
      </div>
      <p className="map-note">Model uncertainty: <strong>{Math.round(map.uncertainty * 100)}%</strong>. Color is always paired with a label and count.</p>
    </section>
  )
}

