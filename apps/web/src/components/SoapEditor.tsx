import { useState } from 'react'
import { Check, FileSignature, Link2, Save } from 'lucide-react'
import type { Encounter } from '../types'

interface SoapEditorProps {
  encounter: Encounter
  onSave: (sections: Record<string, string[]>) => Promise<void>
  onSign: () => Promise<void>
}

export function SoapEditor({ encounter, onSave, onSign }: SoapEditorProps) {
  const [sections, setSections] = useState<Record<string,string[]>>(() => Object.fromEntries(Object.entries(encounter.soap?.sections || {}).map(([name, lines]) => [name, lines.map((line) => line.text)])))
  const [busy, setBusy] = useState(false)
  if (!encounter.soap) return null
  async function act(callback: () => Promise<void>) { setBusy(true); try { await callback() } finally { setBusy(false) } }
  return (
    <section className="instrument-card soap" aria-labelledby="soap-title">
      <div className="section-heading"><div><span className="eyebrow">Editable draft</span><h2 id="soap-title">SOAP with sentence provenance</h2></div><span className={`draft-state ${encounter.soap.status}`}>{encounter.soap.status === 'signed' ? <Check size={14} /> : <FileSignature size={14} />}{encounter.soap.status}</span></div>
      {Object.entries(encounter.soap.sections).map(([name, originalLines]) => (
        <fieldset key={name} disabled={encounter.soap?.status === 'signed'}>
          <legend>{name}</legend>
          {originalLines.map((line, index) => <div className="soap-line" key={line.id}>
            <textarea aria-label={`${name} sentence ${index + 1}`} value={sections[name]?.[index] || ''} onChange={(event) => setSections((current) => ({...current, [name]: current[name].map((value, lineIndex) => lineIndex === index ? event.target.value : value)}))} />
            <div className="provenance"><Link2 size={13} aria-hidden="true" />{line.provenance.map((source) => <span key={`${source.source_id}-${source.source_type}`}>{source.source_type}: {source.label}</span>)}</div>
          </div>)}
        </fieldset>
      ))}
      {encounter.soap.status !== 'signed' && <div className="action-row"><button className="button secondary" disabled={busy} onClick={() => act(() => onSave(sections))}><Save size={17} />Save edits</button><button className="button primary" disabled={busy} onClick={() => act(onSign)}><FileSignature size={17} />Sign draft</button></div>}
    </section>
  )
}

