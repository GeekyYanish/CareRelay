import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Inbox, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { StatusPill } from '../components/StatusPill'

export function ReviewerPage() {
  const client = useQueryClient()
  const query = useQuery({queryKey:['escalations'], queryFn:api.escalations})
  const [notes, setNotes] = useState<Record<string,string>>({})
  async function refresh(action: Promise<unknown>) { await action; await client.invalidateQueries({queryKey:['escalations']}) }
  const open = query.data?.filter((item) => item.status !== 'resolved') || []
  return <div className="page-wrap"><header className="page-hero compact"><div><span className="eyebrow">Human safety net</span><h1>Escalation console</h1><p>Every unresolved case remains durable until a reviewer documents the handoff.</p></div><div className="hero-seal danger"><ShieldAlert/><strong>{open.length} open</strong><span>requires attention</span></div></header>
    {query.data?.length ? <div className="escalation-list">{query.data.map((item) => <article key={item.id} className={item.status==='resolved'?'resolved':''}><div className="escalation-top"><span className="avatar">{item.patient_name?.slice(0,1)||'P'}</span><div><span className="eyebrow">Case {item.id.slice(0,8)}</span><h2>{item.patient_name}</h2></div><StatusPill urgency={item.urgency}/><span className="case-state">{item.status}</span></div><div className="reason-box"><code>{item.reason}</code><p>Safety gate created this case automatically. Review the encounter evidence before resolving.</p></div>{item.status==='open'&&<button className="button secondary" onClick={() => refresh(api.claim(item.id))}>Claim case</button>}{item.status==='claimed'&&<div className="resolution"><label>Resolution note<textarea value={notes[item.id]||''} onChange={(event)=>setNotes((current)=>({...current,[item.id]:event.target.value}))}/></label><button className="button primary" disabled={(notes[item.id]||'').length<5} onClick={() => refresh(api.resolve(item.id,notes[item.id]))}><CheckCircle2/>Resolve with audit note</button></div>}{item.status==='resolved'&&<p className="resolved-note"><CheckCircle2/>{item.resolution_note}</p>}</article>)}</div>:<div className="empty-state"><Inbox/><h2>The queue is clear</h2><p>Run an emergency or disagreement scenario from the patient view.</p></div>}
  </div>
}

