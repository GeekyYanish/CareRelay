import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, FileSearch, History } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { SoapEditor } from '../components/SoapEditor'
import { StatusPill } from '../components/StatusPill'
import { UncertaintyMap } from '../components/UncertaintyMap'
import type { Encounter } from '../types'

export function ClinicianPage() {
  const queryClient = useQueryClient()
  const query = useQuery({queryKey:['encounters'], queryFn:api.encounters})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = query.data?.find((item) => item.id === selectedId) || query.data?.[0]
  async function save(sections: Record<string,string[]>) { if (!selected) return; await api.patchSoap(selected.id, sections); await queryClient.invalidateQueries({queryKey:['encounters']}) }
  async function sign() { if (!selected) return; await api.signSoap(selected.id); await queryClient.invalidateQueries({queryKey:['encounters']}) }
  return <div className="workspace-layout">
    <aside className="record-rail"><div><span className="eyebrow">Clinical workspace</span><h1>Encounter relay</h1><p>Drafts require qualified sign-off.</p></div><div className="record-list">{query.data?.map((encounter) => <button key={encounter.id} className={selected?.id===encounter.id?'active':''} onClick={() => setSelectedId(encounter.id)}><span className="avatar">{encounter.patient_name.slice(0,1)}</span><div><strong>{encounter.patient_name}</strong><small>{new Date(encounter.created_at).toLocaleString()}</small></div>{encounter.gate&&<StatusPill urgency={encounter.gate.urgency}/>}<ChevronRight size={16}/></button>)}</div></aside>
    <div className="workspace-content">{selected ? <><header className="record-header"><div><span className="eyebrow">Encounter · <code>{selected.id.slice(0,8)}</code></span><h1>{selected.patient_name}</h1><p>{selected.triage?.rationale_summary}</p></div>{selected.gate&&<StatusPill urgency={selected.gate.urgency} large/>}</header><div className="clinical-grid"><div>{selected.uncertainty_map&&<UncertaintyMap map={selected.uncertainty_map}/>}<section className="instrument-card delta-card"><History/><div><span className="eyebrow">Longitudinal delta</span><h2>Current report is the baseline</h2><p>Future encounters will be compared against this patient-scoped record.</p></div></section></div><SoapEditor key={`${selected.id}-${selected.soap?.updated_at}`} encounter={selected} onSave={save} onSign={sign}/></div></> : <div className="empty-state"><FileSearch/><h2>No encounters yet</h2><p>Complete a patient demo scenario, then return here.</p></div>}</div>
  </div>
}

