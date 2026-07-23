import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, FileAudio, Keyboard, LoaderCircle, Mic, MicOff, RotateCcw, ShieldCheck, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import type { Encounter, Scenario } from '../types'

function pickRecorderMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return candidates.find((type) => MediaRecorder.isTypeSupported(type))
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
  const [transcribing, setTranscribing] = useState(false)
  const [micSupported, setMicSupported] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  useEffect(() => {
    setMicSupported(typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== 'undefined')
    return () => {
      stopListening(false)
    }
  }, [])

  useEffect(() => {
    if (inputType === 'text') stopListening(false)
  }, [inputType])

  function releaseMic() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    mediaRecorderRef.current = null
    chunksRef.current = []
  }

  function stopListening(finalize = true) {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      if (!finalize) {
        recorder.ondataavailable = null
        recorder.onstop = null
        recorder.stop()
        releaseMic()
        setListening(false)
        setTranscribing(false)
        return
      }
      recorder.stop()
      return
    }
    releaseMic()
    setListening(false)
  }

  async function startListening() {
    if (!micSupported) {
      setError('Voice capture is not supported in this browser. Paste a transcript instead.')
      return
    }
    setError('')
    stopListening(false)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      const mimeType = pickRecorderMime()
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setError('Microphone recording failed. Paste a transcript and continue.')
        setListening(false)
        setTranscribing(false)
        releaseMic()
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        releaseMic()
        setListening(false)
        if (blob.size < 256) {
          setError('Recording was too short. Hold the mic a moment longer, or paste a transcript.')
          return
        }
        setTranscribing(true)
        void api
          .transcribe(blob)
          .then((result) => {
            setText((prev) => `${prev.trim()}${prev.trim() ? ' ' : ''}${result.transcript}`.trim())
            setError('')
          })
          .catch((reason) => {
            setError(reason instanceof Error ? reason.message : 'Transcription failed. Paste a transcript and continue.')
          })
          .finally(() => setTranscribing(false))
      }
      mediaRecorderRef.current = recorder
      recorder.start(250)
      setListening(true)
    } catch (reason) {
      releaseMic()
      setListening(false)
      const name = reason instanceof DOMException ? reason.name : ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setError('Microphone permission was blocked. Allow mic access, or paste a transcript.')
      } else {
        setError('Could not open the microphone. Paste a transcript and continue.')
      }
    }
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
    stopListening(false)
    void withBusy(scenario.id, async () => {
      const consented = await begin()
      setEncounter(await api.loadScenario(consented.id, scenario.id))
    })
  }

  function runManual() {
    stopListening(false)
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

  const micBusy = listening || transcribing

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
                <strong>
                  {transcribing ? 'Transcribing…' : listening ? 'Recording…' : 'Capture a spoken report'}
                </strong>
                <p>
                  {micSupported
                    ? 'Records on your device, then turns speech into text on the server (not a diagnosis). Paste still works anytime.'
                    : 'This browser cannot record audio. Paste a spoken report transcript below instead.'}
                </p>
              </div>
              <div className="voice-actions">
                {micSupported && !transcribing && (
                  listening ? (
                    <button type="button" className="button secondary" onClick={() => stopListening(true)}>
                      <Square size={16} />Stop &amp; transcribe
                    </button>
                  ) : (
                    <button type="button" className="button secondary" onClick={() => void startListening()}>
                      <Mic size={16} />Start mic
                    </button>
                  )
                )}
                {transcribing && (
                  <span className="voice-badge"><LoaderCircle size={14} className="spin" />Working</span>
                )}
                {!micSupported && (
                  <span className="voice-badge"><MicOff size={14} />Paste mode</span>
                )}
              </div>
            </div>
          )}

          <label>
            {inputType === 'voice-transcript' ? 'Voice transcript' : 'What are you experiencing?'}
            <textarea
              value={text}
              onChange={(event) => {
                if (micBusy) return
                setText(event.target.value)
              }}
              readOnly={micBusy}
              placeholder={
                inputType === 'voice-transcript'
                  ? 'Press Start mic, then Stop & transcribe — or paste a transcript…'
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
