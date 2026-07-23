import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { useAuth } from './stores/auth'
import type { Role } from './types'

const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({default:module.LoginPage})))
const SignupPage = lazy(() => import('./pages/SignupPage').then((module) => ({default:module.SignupPage})))
const PatientPage = lazy(() => import('./pages/PatientPage').then((module) => ({default:module.PatientPage})))
const ClinicianPage = lazy(() => import('./pages/ClinicianPage').then((module) => ({default:module.ClinicianPage})))
const ClinicianReportsPage = lazy(() => import('./pages/ClinicianReportsPage').then((module) => ({default:module.ClinicianReportsPage})))
const ClinicianReportDetailPage = lazy(() => import('./pages/ClinicianReportDetailPage').then((module) => ({default:module.ClinicianReportDetailPage})))
const ReviewerPage = lazy(() => import('./pages/ReviewerPage').then((module) => ({default:module.ReviewerPage})))
const AdminPage = lazy(() => import('./pages/AdminPage').then((module) => ({default:module.AdminPage})))

function ProtectedRoute({ role, children }: { role: Role; children: React.ReactNode }) {
  const user = useAuth((state) => state.user)
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={`/${user.role}`} replace />
  return <AppShell>{children}</AppShell>
}

export function App() {
  const user = useAuth((state) => state.user)
  return <Suspense fallback={<div className="loading-screen"><span/><p>Preparing the safe handoff…</p></div>}><Routes>
    <Route path="/login" element={user ? <Navigate to={`/${user.role}`} replace /> : <LoginPage />} />
    <Route path="/signup" element={user ? <Navigate to={`/${user.role}`} replace /> : <SignupPage />} />
    <Route path="/patient" element={<ProtectedRoute role="patient"><PatientPage /></ProtectedRoute>} />
    <Route path="/clinician" element={<ProtectedRoute role="clinician"><ClinicianPage /></ProtectedRoute>} />
    <Route path="/clinician/reports" element={<ProtectedRoute role="clinician"><ClinicianReportsPage /></ProtectedRoute>} />
    <Route path="/clinician/reports/:encounterId" element={<ProtectedRoute role="clinician"><ClinicianReportDetailPage /></ProtectedRoute>} />
    <Route path="/reviewer" element={<ProtectedRoute role="reviewer"><ReviewerPage /></ProtectedRoute>} />
    <Route path="/admin" element={<ProtectedRoute role="admin"><AdminPage /></ProtectedRoute>} />
    <Route path="*" element={<Navigate to={user ? `/${user.role}` : '/login'} replace />} />
  </Routes></Suspense>
}

