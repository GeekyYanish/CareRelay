import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { useAuth } from '../stores/auth'

const schema = z.object({ email: z.string().email(), password: z.string().min(4) })
type LoginForm = z.infer<typeof schema>

export function LoginPage() {
  const navigate = useNavigate()
  const setSession = useAuth((state) => state.setSession)
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  })

  async function submit(values: LoginForm) {
    setServerError('')
    try {
      const result = await api.login(values.email, values.password)
      setSession(result.access_token, result.user)
      navigate(`/${result.user.role}`)
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Unable to sign in')
    }
  }

  return (
    <main className="login-page" id="main-content">
      <section className="login-story">
        <div className="brand brand--large"><span className="brand-mark"><ShieldCheck size={26} /></span><span>CareRelay<small>safety in the handoff</small></span></div>
        <div className="story-copy"><span className="eyebrow light">Uncertainty-aware care coordination</span><h1>Make the unknowns<br />visible <em>before</em><br />they become risk.</h1><p>One patient story becomes a safer urgency handoff, a traceable clinical draft, and an auditable human decision.</p></div>
        <div className="signal-strip"><div><strong>4</strong><span>urgency paths</span></div><div><strong>2</strong><span>independent safety checks</span></div><div><strong>1</strong><span>traceable care record</span></div></div>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <div><span className="eyebrow">Secure access</span><h2>Sign in to CareRelay</h2><p>Patients can create an account. Staff roles use provisioned credentials.</p></div>
          <form onSubmit={handleSubmit(submit)} noValidate>
            <label>Email<input type="email" autoComplete="username" {...register('email')} /></label>
            {errors.email && <p role="alert" className="field-error">Enter a valid email.</p>}
            <label>Password<input type="password" autoComplete="current-password" {...register('password')} /></label>
            {errors.password && <p role="alert" className="field-error">Password is required.</p>}
            {serverError && <p role="alert" className="form-error">{serverError}</p>}
            <button className="button primary full" disabled={isSubmitting}>
              <LockKeyhole size={17} />
              {isSubmitting ? 'Checking…' : 'Sign in'}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="auth-switch">New patient? <Link to="/signup">Create an account</Link></p>
          <Disclaimer compact />
        </div>
      </section>
    </main>
  )
}
