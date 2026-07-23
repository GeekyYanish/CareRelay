import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, FileAudio, Keyboard, LoaderCircle, Mic, MicOff, RotateCcw, ShieldCheck, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import type { Encounter, Scenario } from '../types'

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: { resultIndex: number; results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }> }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const scope = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return scope.SpeechRecognition || scope.webkitSpeechRecognition || null
}

export function PatientPage() {
  const scenarios = useQuery({ queryKey: ['scenarios'], queryFn: api.scenarios })
  const [encounter, setEncounter] = useState<Encounter | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [inputType, setInputType] = useState<'text' | 'voice-transcript'>('text')
  const [answer, setAnswer] = useState('')
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [speechSupported, setSpeechSupported] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const baseTranscriptRef = useRef('')

  useEffect(() => {
    setSpeechSupported(Boolean(getSpeechRecognition()))
    return () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
    }
  }, [])

  useEffect(() => {
    if (inputType === 'text') stopListening()
  }, [inputType])

  function stopListening() {
    recognitionRef.current?.stop()
    recognitionRef.current = null
    setListening(false)
    setInterim('')
  }

  function startListening() {
    const Recognition = getSpeechRecognition()
    if (!Recognition) {
      setError('Voice capture is not supported in this browser. Paste a transcript instead, or use Chrome/Edge.')
      return
    }
    setError('')
    stopListening()
    baseTranscriptRef.current = text.trim()
    const recognition = new Recognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = 'en-US'
    recognition.onresult = (event) => {
      let finalChunk = ''
      let interimChunk = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finalChunk += result[0].transcript
        else interimChunk += result[0].transcript
      }
      if (finalChunk) {
        const prefix = baseTranscriptRef.current
        const next = `${prefix}${prefix ? ' ' : ''}${finalChunk.trim()}`.trim()
        baseTranscriptRef.current = next
        setText(next)
      }
      setInterim(interimChunk.trim())
    }
    recognition.onerror = (event) => {
      setListening(false)
      setInterim('')
      if (event.error === 'not-allowed') {
        setError('Microphone permission was blocked. Allow mic access, or paste a transcript.')
      } else if (event.error !== 'aborted') {
        setError(`Voice capture stopped (${event.error}). You can paste a transcript and continue.`)
      }
    }
    recognition.onend = () => {
      setListening(false)
      setInterim('')
      recognitionRef.current = null
    }
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }

  async function withBusy(label: string, action: () => Promise<void>) {
    setBusy(label)
    setError('')
    try {
      await action()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Something went wrong')
    } finally {
      setBusy('')
    }
  }

  async function begin(): Promise<Encounter> {
    const created = await api.createEncounter()
    return api.consent(created.id)
  }

  function runScenario(scenario: Scenario) {
    stopListening()
    void withBusy(scenario.id, async () => {
      const consented = await begin()
      setEncounter(await api.loadScenario(consented.id, scenario.id))
    })
  }

  function runManual() {
    stopListening()
    void withBusy('manual', async () => {
      const consented = await begin()
      setEncounter(await api.ingest(consented.id, text.trim(), inputType))
    })
  }

  function answerQuestion(questionId: string) {
    if (!encounter) return
    void withBusy('answer', async () => {
      setEncounter(await api.answer(encounter.id, questionId, answer))
      setAnswer('')
    })
  }

  function teachBack(response: string) {
    if (!encounter) return
    void withBusy('teachback', async () => setEncounter(await api.teachBack(encounter.id, response)))
  }

  if (encounter?.guidance && encounter.gate) {
    const emergency = encounter.gate.urgency === 'Emergency'
    const teachBackText = emergency
      ? 'I will contact local emergency services now'
      : encounter.gate.urgency === 'Same-Day'
        ? 'I will contact a qualified professional today'
        : 'I will seek help sooner if I get worse'
    return (
      <div className="page-wrap patient-result">
        <header className="page-hero compact">
          <div>
            <span className="eyebrow">Guidance ready</span>
            <h1>Your next step is clear.<br />The uncertainty is not hidden.</h1>
          </div>
          <button className="button ghost" onClick={() => setEncounter(null)}>
            <RotateCcw size={16} />New intake
          </button>
        </header>
        <Disclaimer />
        <div className="result-grid">
          <section className={`guidance-card ${emergency ? 'emergency' : ''}`} aria-live="polite">
            <span className="eyebrow">Gated urgency result</span>
            <StatusPill urgency={encounter.gate.urgency} large />
            <h2>{encounter.guidance.title}</h2>
            <p>{encounter.guidance.instruction}</p>
            <div className="gate-stamp">
              <CheckCircle2 size={20} />
              <span>
                <strong>{encounter.gate.approved_low_risk ? 'Two-key gate passed' : 'Human review required'}</strong>
                <small>{encounter.gate.summary}</small>
              </span>
            </div>
            <div className="reason-list">{encounter.gate.reason_codes.map((reason) => <code key={reason}>{reason}</code>)}</div>
          </section>
          <Timeline events={encounter.timeline} />
        </div>
        <section className="instrument-card teachback">
          <div>
            <span className="eyebrow">Teach-back check</span>
            <h2>What will you do next?</h2>
            <p>Confirm the safety-net instruction in your own action.</p>
          </div>
          {encounter.teach_back?.understood ? (
            <div className="confirmed"><CheckCircle2 />{encounter.teach_back.message}</div>
          ) : (
            <button className="button primary" disabled={busy === 'teachback'} onClick={() => teachBack(teachBackText)}>
              {busy === 'teachback' ? <LoaderCircle className="spin" /> : <ArrowRight />} {teachBackText}
            </button>
          )}
        </section>
        <section className="citations">
          <span className="eyebrow">Evidence used</span>
          {encounter.guidance.citations.map((citation) => (
            <article key={citation.source_id}>
              <code>{citation.source_id}</code>
              <div><strong>{citation.title}</strong><p>{citation.excerpt}</p></div>
              <span>{Math.round(citation.retrieval_score * 100)}%</span>
            </article>
          ))}
        </section>
      </div>
    )
  }

  const openQuestion = encounter?.questions.find((question) => !question.answered)
  if (encounter && openQuestion) {
    return (
      <div className="page-wrap narrow">
        <header className="page-hero compact">
          <div>
            <span className="eyebrow">Adaptive interview · turn {openQuestion.turn} of 3</span>
            <h1>One high-value question at a time.</h1>
            <p>Deterministic safety rules run again after every answer.</p>
          </div>
        </header>
        <Disclaimer />
        <section className="question-card">
          <span>{String(openQuestion.turn).padStart(2, '0')}</span>
          <h2>{openQuestion.prompt}</h2>
          <label>Your answer<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} /></label>
          <button className="button primary" disabled={!answer.trim() || busy === 'answer'} onClick={() => answerQuestion(openQuestion.id)}>
            {busy === 'answer' ? <LoaderCircle className="spin" /> : <ChevronRight />}Continue safely
          </button>
        </section>
      </div>
    )
  }

  const displayValue = interim ? `${text}${text ? ' ' : ''}${interim}` : text

  return (
    <div className="page-wrap">
      <header className="page-hero">
        <div>
          <span className="eyebrow">Patient intake</span>
          <h1>Tell us what’s happening.<br /><em>We’ll help route the next step.</em></h1>
          <p>CareRelay asks only for the details that matter, checks warning signs first, and never provides a diagnosis or treatment plan.</p>
        </div>
        <div className="hero-seal"><ShieldCheck size={22} /><strong>Safety first</strong><span>Urgency, not diagnosis</span></div>
      </header>
      <Disclaimer />
      {error && <p role="alert" className="form-error"><AlertTriangle size={17} />{error}</p>}
      <section className="intake-grid intake-grid--focused">
        <div className="instrument-card manual-intake">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Start from your words</span>
              <h2>Symptom intake</h2>
            </div>
            <div className="segmented" role="tablist" aria-label="Intake mode">
              <button type="button" className={inputType === 'text' ? 'active' : ''} onClick={() => setInputType('text')}>
                <Keyboard size={15} />Text
              </button>
              <button type="button" className={inputType === 'voice-transcript' ? 'active' : ''} onClick={() => setInputType('voice-transcript')}>
                <FileAudio size={15} />Voice transcript
              </button>
            </div>
          </div>

          {inputType === 'voice-transcript' && (
            <div className={`voice-panel ${listening ? 'listening' : ''}`}>
              <div>
                <strong>{listening ? 'Listening…' : 'Capture a spoken report'}</strong>
                <p>
                  {speechSupported
                    ? 'Uses your browser microphone, turns speech into text, then sends it as a voice transcript (not a diagnosis).'
                    : 'This browser cannot capture speech. Paste a spoken report transcript below instead.'}
                </p>
              </div>
              <div className="voice-actions">
                {speechSupported && (
                  listening ? (
                    <button type="button" className="button secondary" onClick={stopListening}>
                      <Square size={16} />Stop
                    </button>
                  ) : (
                    <button type="button" className="button secondary" onClick={startListening}>
                      <Mic size={16} />Start mic
                    </button>
                  )
                )}
                {!speechSupported && (
                  <span className="voice-badge"><MicOff size={14} />Paste mode</span>
                )}
              </div>
            </div>
          )}

          <label>
            {inputType === 'voice-transcript' ? 'Voice transcript' : 'What are you experiencing?'}
            <textarea
              value={displayValue}
              onChange={(event) => {
                if (listening) return
                setText(event.target.value)
              }}
              readOnly={listening}
              placeholder={
                inputType === 'voice-transcript'
                  ? 'Press Start mic, or paste a transcript of what was said…'
                  : 'Describe your symptoms in your own words…'
              }
            />
          </label>
          <p className="helper">
            {inputType === 'voice-transcript'
              ? 'Tagged as voice-transcript for audit. Names and contact details are masked before external processing.'
              : 'Names, contact details, and record identifiers are masked before external processing.'}
          </p>
          <button className="button primary" disabled={busy === 'manual' || text.trim().length < 3} onClick={runManual}>
            {busy === 'manual' ? <LoaderCircle className="spin" /> : <ArrowRight />}
            Begin safe intake
          </button>
        </div>
        <div className="scenario-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">One-click judge demo</span>
              <h2>Seeded safety scenarios</h2>
            </div>
            <span className="count">{String(scenarios.data?.length || 0).padStart(2, '0')}</span>
          </div>
          <div className="scenario-list">
            {scenarios.data?.map((scenario, index) => (
              <button key={scenario.id} type="button" disabled={Boolean(busy)} onClick={() => runScenario(scenario)}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{scenario.name}</strong>
                  <small>{scenario.summary}</small>
                </div>
                {busy === scenario.id ? <LoaderCircle className="spin" /> : <ChevronRight />}
              </button>
            ))}
          </div>
          {scenarios.isError && (
            <p className="helper" role="alert" style={{ padding: '0 20px 16px' }}>
              Demo scenarios unavailable. Free-text intake still works.
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
