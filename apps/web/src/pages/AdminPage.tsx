import { useMutation, useQuery } from '@tanstack/react-query'
import { Activity, Cable, CloudCog, DatabaseZap, ShieldCheck } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'

export function AdminPage() {
  const metrics = useQuery({queryKey:['metrics'], queryFn:api.metrics})
  const integrations = useQuery({queryKey:['integrations'], queryFn:api.integrations})
  const ops = useQuery({queryKey:['ops'], queryFn:api.ops})
  const verifyLyzr = useMutation({
    mutationFn: api.verifyLyzr,
    onSuccess: () => integrations.refetch(),
  })
  const mix = (metrics.data?.urgency_mix || {}) as Record<string,number>
  const chartData = Object.entries(mix).map(([name,value])=>({name,value}))
  return <div className="page-wrap"><header className="page-hero compact"><div><span className="eyebrow">Safety operations</span><h1>System evidence, not theatre.</h1><p>Safety metrics, provider posture, and read-only operations context in one audit surface.</p></div><div className="hero-seal"><ShieldCheck/><strong>{String(metrics.data?.rule_version||'demo-v1')}</strong><span>active rule pack</span></div></header>
    <div className="metric-strip"><article><Activity/><span>Encounters</span><strong>{String(metrics.data?.encounters||0)}</strong></article><article><ShieldCheck/><span>Open escalations</span><strong>{String(metrics.data?.open_escalations||0)}</strong></article><article><DatabaseZap/><span>Critic disagreement</span><strong>{Math.round(Number(metrics.data?.critic_disagreement_rate||0)*100)}%</strong></article><article><CloudCog/><span>Provider timeout</span><strong>{Math.round(Number(metrics.data?.provider_timeout_rate||0)*100)}%</strong></article></div>
    <div className="admin-grid"><section className="instrument-card chart-card"><div className="section-heading"><div><span className="eyebrow">Urgency mix</span><h2>Gated outcomes</h2></div></div><div className="chart" aria-label="Bar chart of urgency outcomes"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" fill="#1b7463" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div><table><thead><tr><th>Urgency</th><th>Count</th></tr></thead><tbody>{chartData.map((row)=><tr key={row.name}><td>{row.name}</td><td>{row.value}</td></tr>)}</tbody></table></section><section className="instrument-card connector-card"><div className="section-heading"><div><span className="eyebrow">Integration posture</span><h2>Credential-aware adapters</h2></div><Cable/></div><button className="button secondary" type="button" disabled={verifyLyzr.isPending} onClick={()=>verifyLyzr.mutate()}>{verifyLyzr.isPending?'Checking Lyzr…':'Verify Lyzr workflow'}</button><div aria-live="polite">{verifyLyzr.isSuccess&&<p className="resolved-note"><ShieldCheck/>Lyzr workflow is reachable.</p>}{verifyLyzr.isError&&<p role="alert">{verifyLyzr.error.message}</p>}</div>{Object.entries(integrations.data||{}).map(([name,value])=><article key={name}><span className="connector-dot"/><div><strong>{name}</strong><pre>{JSON.stringify(value,null,2)}</pre></div></article>)}<div className="mcp-snapshot"><span className="eyebrow">Read-only MCP snapshot</span><pre>{JSON.stringify(ops.data||{status:'loading'},null,2)}</pre></div></section></div>
  </div>
}
