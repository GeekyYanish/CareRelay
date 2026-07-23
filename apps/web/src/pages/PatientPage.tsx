import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, FileAudio, Keyboard, LoaderCircle, RotateCcw, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import type { Encounter } from '../types'

export function PatientPage() {
  const [encounter, setEncounter] = useState<Encounter | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [inputType, setInputType] = useState<'text'|'voice-transcript'>('text')
  const [answer, setAnswer] = useState('')

  async function withBusy(label: string, action: () => Promise<void>) { setBusy(label); setError(''); try { await action() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Something went wrong') } finally { setBusy('') } }
  async function begin(): Promise<Encounter> { const created = await api.createEncounter(); return api.consent(created.id) }
  function runManual() { void withBusy('manual', async () => { const consented = await begin(); setEncounter(await api.ingest(consented.id, text, inputType)) }) }
  function answerQuestion(questionId: string) { if (!encounter) return; void withBusy('answer', async () => { setEncounter(await api.answer(encounter.id, questionId, answer)); setAnswer('') }) }
  function teachBack(response: string) { if (!encounter) return; void withBusy('teachback', async () => setEncounter(await api.teachBack(encounter.id, response))) }

  if (encounter?.guidance && encounter.gate) {
    const emergency = encounter.gate.urgency === 'Emergency'
    const teachBackText = emergency ? 'I will contact local emergency services now' : encounter.gate.urgency === 'Same-Day' ? 'I will contact a qualified professional today' : 'I will seek help sooner if I get worse'
    return <div className="page-wrap patient-result">
      <header className="page-hero compact"><div><span className="eyebrow">Guidance ready</span><h1>Your next step is clear.<br />The uncertainty is not hidden.</h1></div><button className="button ghost" onClick={() => setEncounter(null)}><RotateCcw size={16} />New intake</button></header>
      <Disclaimer />
      <div className="result-grid">
        <section className={`guidance-card ${emergency ? 'emergency' : ''}`} aria-live="polite">
          <span className="eyebrow">Gated urgency result</span><StatusPill urgency={encounter.gate.urgency} large /><h2>{encounter.guidance.title}</h2><p>{encounter.guidance.instruction}</p>
          <div className="gate-stamp"><CheckCircle2 size={20} /><span><strong>{encounter.gate.approved_low_risk ? 'Two-key gate passed' : 'Human review required'}</strong><small>{encounter.gate.summary}</small></span></div>
          <div className="reason-list">{encounter.gate.reason_codes.map((reason) => <code key={reason}>{reason}</code>)}</div>
        </section>
        <Timeline events={encounter.timeline} />
      </div>
      <section className="instrument-card teachback"><div><span className="eyebrow">Teach-back check</span><h2>What will you do next?</h2><p>Confirm the safety-net instruction in your own action.</p></div>{encounter.teach_back?.understood ? <div className="confirmed"><CheckCircle2 />{encounter.teach_back.message}</div> : <button className="button primary" disabled={busy === 'teachback'} onClick={() => teachBack(teachBackText)}>{busy === 'teachback' ? <LoaderCircle className="spin" /> : <ArrowRight />} {teachBackText}</button>}</section>
      <section className="citations"><span className="eyebrow">Evidence used</span>{encounter.guidance.citations.map((citation) => <article key={citation.source_id}><code>{citation.source_id}</code><div><strong>{citation.title}</strong><p>{citation.excerpt}</p></div><span>{Math.round(citation.retrieval_score*100)}%</span></article>)}</section>
    </div>
  }

  const openQuestion = encounter?.questions.find((question) => !question.answered)
  if (encounter && openQuestion) return <div className="page-wrap narrow"><header className="page-hero compact"><div><span className="eyebrow">Adaptive interview · turn {openQuestion.turn} of 3</span><h1>One high-value question at a time.</h1><p>Deterministic safety rules run again after every answer.</p></div></header><Disclaimer /><section className="question-card"><span>{String(openQuestion.turn).padStart(2,'0')}</span><h2>{openQuestion.prompt}</h2><label>Your answer<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} /></label><button className="button primary" disabled={!answer.trim() || busy === 'answer'} onClick={() => answerQuestion(openQuestion.id)}>{busy === 'answer' ? <LoaderCircle className="spin" /> : <ChevronRight />}Continue safely</button></section></div>

  return (
    <div className="page-wrap">
      <header className="page-hero"><div><span className="eyebrow">Patient intake</span><h1>Tell us what’s happening.<br /><em>We’ll help route the next step.</em></h1><p>CareRelay asks only for the details that matter, checks warning signs first, and never provides a diagnosis or treatment plan.</p></div><div className="hero-seal"><ShieldCheck size={22} /><strong>Safety first</strong><span>Urgency, not diagnosis</span></div></header>
      <Disclaimer />
      {error && <p role="alert" className="form-error"><AlertTriangle size={17} />{error}</p>}
      <section className="intake-grid intake-grid--focused">
        <div className="instrument-card manual-intake"><div className="section-heading"><div><span className="eyebrow">Start from your words</span><h2>Symptom intake</h2></div><div className="segmented"><button className={inputType==='text'?'active':''} onClick={() => setInputType('text')}><Keyboard size={15}/>Text</button><button className={inputType==='voice-transcript'?'active':''} onClick={() => setInputType('voice-transcript')}><FileAudio size={15}/>Voice transcript</button></div></div><label>What are you experiencing?<textarea value={text} onChange={(event) => setText(event.target.value)} /></label><p className="helper">Names, contact details, and record identifiers are masked before external processing.</p><button className="button primary" disabled={busy==='manual' || text.trim().length<3} onClick={runManual}>{busy==='manual'?<LoaderCircle className="spin"/>:<ArrowRight/>}Begin safe intake</button></div>
        <aside className="intake-aside"><span className="eyebrow">What happens next</span><h2>A clear, careful handoff.</h2><ol><li><span>01</span><div><strong>Safety screen</strong><p>Warning signs are checked before any automated review.</p></div></li><li><span>02</span><div><strong>Focused questions</strong><p>We only ask for details needed to clarify urgency.</p></div></li><li><span>03</span><div><strong>Next-step guidance</strong><p>You get a transparent recommendation and safety net.</p></div></li></ol><p className="intake-aside__note">Please do not include passwords, financial details, or record numbers.</p></aside>
      </section>
    </div>
  )
}
