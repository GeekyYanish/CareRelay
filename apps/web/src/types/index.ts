export type Role = 'patient' | 'clinician' | 'reviewer' | 'admin'
export type Urgency = 'Emergency' | 'Same-Day' | 'Routine' | 'Self-Care'

export interface User { id: string; tenant_id: string; email: string; name: string; role: Role }
export interface Citation { source_id: string; title: string; version: string; excerpt: string; jurisdiction: string; retrieval_score: number }
export interface Provenance { source_id: string; source_type: 'patient' | 'clinician' | 'retrieval' | 'inference'; label: string; quote?: string }
export interface SoapSentence { id: string; text: string; confidence: number; provenance: Provenance[] }
export interface SoapDraft { id: string; status: 'draft' | 'signed'; sections: Record<string, SoapSentence[]>; updated_at: string; signed_at?: string }
export interface RedFlag { rule_id: string; rule_version: string; severity: Urgency; matched_evidence: string; recommended_action: string }
export interface UncertaintyMap { known_facts: string[]; missing_facts: string[]; contradictions: string[]; red_flags: RedFlag[]; retrieval_quality: number; uncertainty: number }
export interface Triage { urgency: Urgency; confidence: number; uncertainty: number; rationale_summary: string; missing_critical_facts: string[]; citations: Citation[]; provider: string }
export interface Critic { proposed_urgency: Urgency; risk_found: boolean; confidence: number; summary: string; provider: string }
export interface Gate { urgency: Urgency; approved_low_risk: boolean; escalated: boolean; reason_codes: string[]; summary: string }
export interface Guidance { title: string; instruction: string; citations: Citation[]; disclaimer: string }
export interface Question { id: string; fact: string; prompt: string; turn: number; answered: boolean }
export interface TimelineEvent { event_id: string; event_type: string; encounter_id: string; timestamp: string; payload: Record<string, unknown> }
export interface OrchestrationRun { provider: string; workflow_id?: string; execution_id?: string; status: 'completed' | 'failed' | 'bypassed'; started_at: string; completed_at: string; duration_ms: number; error_code?: string }
export interface Encounter {
  id: string; tenant_id: string; patient_id: string; patient_name: string; scenario_id?: string; status: string; created_at: string;
  consent: Record<string, unknown>; transcript: Array<{id:string; text:string; input_type:string}>; questions: Question[]; answers: unknown[];
  timeline: TimelineEvent[]; triage?: Triage; critic?: Critic; gate?: Gate; uncertainty_map?: UncertaintyMap; soap?: SoapDraft; orchestration?: OrchestrationRun; guidance?: Guidance;
  teach_back?: { understood: boolean; attempts: number; message: string };
}
export interface Scenario { id: string; name: string; summary: string; retrieval_quality: number; uncertainty: number; missing?: string[]; provider_timeout?: boolean }
export interface Escalation { id: string; encounter_id: string; status: string; urgency: Urgency; reason: string; patient_name: string; assigned_to?: string; resolution_note?: string }
