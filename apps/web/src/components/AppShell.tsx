import type { PropsWithChildren } from 'react'
import { Activity, ClipboardList, HeartPulse, LogOut, ShieldCheck, UserRoundSearch } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../stores/auth'
import type { Role } from '../types'
import { Disclaimer } from './Disclaimer'

const destinations: Record<Role, Array<{to:string; label:string; icon: typeof HeartPulse}>> = {
  patient: [{to:'/patient', label:'My CareRelay', icon:HeartPulse}],
  clinician: [{to:'/clinician', label:'Clinical workspace', icon:ClipboardList}],
  reviewer: [{to:'/reviewer', label:'Escalation console', icon:UserRoundSearch}],
  admin: [{to:'/admin', label:'Safety dashboard', icon:Activity}],
}

export function AppShell({ children }: PropsWithChildren) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to={`/${user.role}`} className="brand" aria-label="CareRelay home"><span className="brand-mark"><ShieldCheck size={22} /></span><span>CareRelay<small>safety in the handoff</small></span></NavLink>
        <nav aria-label="Primary navigation">{destinations[user.role].map(({to,label,icon:Icon}) => <NavLink key={to} to={to}><Icon size={17} />{label}</NavLink>)}</nav>
        <div className="user-block"><span><strong>{user.name}</strong><small>{user.role}</small></span><button className="icon-button" aria-label="Sign out" onClick={() => { logout(); navigate('/login') }}><LogOut size={18} /></button></div>
      </header>
      <main id="main-content">{children}</main>
      <footer><Disclaimer compact /><span className="mono">DEMO_MODE · v0.1</span></footer>
    </div>
  )
}

