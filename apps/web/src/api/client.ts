import type {
  Encounter,
  Escalation,
  ReportDetail,
  ReportListResponse,
  Scenario,
  User,
} from '../types'

const base = import.meta.env.VITE_API_BASE || '/api/v1'

export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('carerelay-token')
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    })
  } catch {
    throw new ApiError('Network error — check that the API is awake and reachable', 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({} as Record<string, unknown>))
    const err = body.error as { message?: string } | undefined
    const detail = body.detail
    const message =
      err?.message ||
      (typeof detail === 'string' ? detail : undefined) ||
      `Request failed (${response.status})`
    throw new ApiError(message, response.status)
  }
  return response.json()
}

export const api = {
  login: (email: string, password: string) => request<{access_token:string; user:User}>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  signup: (name: string, email: string, password: string) =>
    request<{access_token:string; user:User}>('/auth/signup', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
  scenarios: () => request<Scenario[]>('/demo/scenarios'),
  encounters: () => request<Encounter[]>('/encounters'),
  encounter: (id: string) => request<Encounter>(`/encounters/${id}`),
  createEncounter: () => request<Encounter>('/encounters', { method: 'POST', body: JSON.stringify({}) }),
  consent: (id: string) => request<Encounter>(`/encounters/${id}/consent`, { method: 'POST', body: JSON.stringify({ accepted: true, version: 'care-relay-v1' }) }),
  loadScenario: (id: string, scenario_id: string) => request<Encounter>(`/encounters/${id}/demo-scenario`, { method: 'POST', body: JSON.stringify({ scenario_id }) }),
  ingest: (id: string, text: string, input_type: 'text' | 'voice-transcript') => request<Encounter>(`/encounters/${id}/ingest`, { method: 'POST', body: JSON.stringify({ text, input_type }) }),
  answer: (id: string, question_id: string, answer: string) => request<Encounter>(`/encounters/${id}/answers`, { method: 'POST', body: JSON.stringify({ question_id, answer }) }),
  teachBack: (id: string, answer: string) => request<Encounter>(`/encounters/${id}/teach-back`, { method: 'POST', body: JSON.stringify({ answer }) }),
  patchSoap: (id: string, sections: Record<string,string[]>) => request<Encounter>(`/encounters/${id}/soap`, { method: 'PATCH', body: JSON.stringify({ sections }) }),
  signSoap: (id: string) => request<Encounter>(`/encounters/${id}/soap/sign-off`, { method: 'POST' }),
  listReports: (params: {
    q?: string
    urgency?: string
    status?: string
    assigned_to?: string
    page?: number
    page_size?: number
  } = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    const suffix = query.toString() ? `?${query}` : ''
    return request<ReportListResponse>(`/clinician/reports${suffix}`)
  },
  getReport: (id: string) => request<ReportDetail>(`/clinician/reports/${id}`),
  assignReport: (id: string, clinician_id: string | null) =>
    request<Encounter>(`/clinician/reports/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ clinician_id }),
    }),
  audit: (id: string) => request<Array<Record<string, unknown>>>(`/audit/encounters/${id}`),
  escalations: () => request<Escalation[]>('/escalations'),
  claim: (id: string) => request<Escalation>(`/escalations/${id}/claim`, { method: 'POST' }),
  resolve: (id: string, note: string, category = 'clinical_handoff') =>
    request<Escalation>(`/escalations/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ note, category }),
    }),
  metrics: () => request<Record<string, unknown>>('/admin/metrics'),
  integrations: () => request<Record<string, unknown>>('/admin/integrations'),
  verifyLyzr: () => request<Record<string, unknown>>('/admin/integrations/lyzr/verify', { method: 'POST' }),
  ops: () => request<Record<string, unknown>>('/admin/ops/snapshot'),
}
