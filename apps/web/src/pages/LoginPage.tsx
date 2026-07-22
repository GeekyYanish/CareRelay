import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { useAuth } from '../stores/auth'
import type { Role } from '../types'

const schema = z.object({ email: z.string().email(), password: z.string().min(4) })
type LoginForm = z.infer<typeof schema>

const demoAccounts: Array<{role: Role; email:string; password:string; label:string}> = [
  {role:'patient', email:'patient@demo.carerelay.local', password:'demo-patient', label:'Patient journey'},
  {role:'clinician', email:'clinician@demo.carerelay.local', password:'demo-clinician', label:'Clinical workspace'},
  {role:'reviewer', email:'reviewer@demo.carerelay.local', password:'demo-reviewer', label:'Review escalations'},
  {role:'admin', email:'admin@demo.carerelay.local', password:'demo-admin', label:'Safety operations'},
]

export function LoginPage() {
  const navigate = useNavigate()
  const setSession = useAuth((state) => state.setSession)
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<LoginForm>({ resolver: zodResolver(schema), defaultValues: { email: demoAccounts[0].email, password: demoAccounts[0].password } })
  async function submit(values: LoginForm) {
    setServerError('')
    try {
      const result = await api.login(values.email, values.password)
      setSession(result.access_token, result.user)
      navigate(`/${result.user.role}`)
    } catch (error) { setServerError(error instanceof Error ? error.message : 'Unable to sign in') }
  }
  return (
    <main className="login-page" id="main-content">
      <section className="login-story">
        <div className="brand brand--large"><span className="brand-mark"><ShieldCheck size={26} /></span><span>CareRelay<small>safety in the handoff</small></span></div>
        <div className="story-copy"><span className="eyebrow light">Uncertainty-aware care coordination</span><h1>Make the unknowns<br />visible <em>before</em><br />they become risk.</h1><p>One patient story becomes a safer urgency handoff, a traceable clinical draft, and an auditable human decision.</p></div>
        <div className="signal-strip"><div><strong>4</strong><span>urgency classes</span></div><div><strong>2</strong><span>independent safety keys</span></div><div><strong>100%</strong><span>demo citation coverage</span></div></div>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <div><span className="eyebrow">Secure demo access</span><h2>Choose a seat at the handoff</h2><p>All accounts are synthetic and pre-seeded.</p></div>
          <div className="account-grid" aria-label="Demo account shortcuts">
            {demoAccounts.map((account) => <button key={account.role} type="button" onClick={() => { setValue('email', account.email); setValue('password', account.password) }}><span>{account.role.slice(0,1).toUpperCase()}</span><strong>{account.label}</strong><small>{account.role}</small></button>)}
          </div>
          <form onSubmit={handleSubmit(submit)} noValidate>
            <label>Email<input type="email" autoComplete="username" {...register('email')} /></label>{errors.email && <p role="alert" className="field-error">Enter a valid email.</p>}
            <label>Password<input type="password" autoComplete="current-password" {...register('password')} /></label>{errors.password && <p role="alert" className="field-error">Password is required.</p>}
            {serverError && <p role="alert" className="form-error">{serverError}</p>}
            <button className="button primary full" disabled={isSubmitting}><LockKeyhole size={17} />{isSubmitting ? 'Checking…' : 'Enter CareRelay'}<ArrowRight size={17} /></button>
          </form>
          <Disclaimer compact />
        </div>
      </section>
    </main>
  )
}

