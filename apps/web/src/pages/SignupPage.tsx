import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { api } from '../api/client'
import { Disclaimer } from '../components/Disclaimer'
import { useAuth } from '../stores/auth'

const schema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
  email: z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Use at least 8 characters').max(128),
  confirmPassword: z.string().min(8),
}).refine((values) => values.password === values.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
})

type SignupForm = z.infer<typeof schema>

export function SignupPage() {
  const navigate = useNavigate()
  const setSession = useAuth((state) => state.setSession)
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<SignupForm>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '' },
  })

  async function submit(values: SignupForm) {
    setServerError('')
    try {
      const result = await api.signup(values.name, values.email, values.password)
      setSession(result.access_token, result.user)
      navigate(`/${result.user.role}`)
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Unable to create account')
    }
  }

  return (
    <main className="login-page" id="main-content">
      <section className="login-story">
        <div className="brand brand--large">
          <span className="brand-mark"><UserPlus size={26} /></span>
          <span>CareRelay<small>safety in the handoff</small></span>
        </div>
        <div className="story-copy">
          <span className="eyebrow light">Patient access</span>
          <h1>Create an account<br />to start a safer<br />care handoff.</h1>
          <p>Sign up as a patient to report symptoms, receive urgency guidance, and keep a clear trail for clinician review.</p>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <div>
            <span className="eyebrow">Create account</span>
            <h2>Patient sign up</h2>
            <p>Public registration creates a patient role. Clinician, reviewer, and admin accounts stay provisioned separately.</p>
          </div>
          <form onSubmit={handleSubmit(submit)} noValidate>
            <label>Full name<input type="text" autoComplete="name" {...register('name')} /></label>
            {errors.name && <p role="alert" className="field-error">{errors.name.message}</p>}
            <label>Email<input type="email" autoComplete="email" {...register('email')} /></label>
            {errors.email && <p role="alert" className="field-error">{errors.email.message}</p>}
            <label>Password<input type="password" autoComplete="new-password" {...register('password')} /></label>
            {errors.password && <p role="alert" className="field-error">{errors.password.message}</p>}
            <label>Confirm password<input type="password" autoComplete="new-password" {...register('confirmPassword')} /></label>
            {errors.confirmPassword && <p role="alert" className="field-error">{errors.confirmPassword.message}</p>}
            {serverError && <p role="alert" className="form-error">{serverError}</p>}
            <button className="button primary full" disabled={isSubmitting}>
              <UserPlus size={17} />
              {isSubmitting ? 'Creating…' : 'Create account'}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
          <Disclaimer compact />
        </div>
      </section>
    </main>
  )
}
