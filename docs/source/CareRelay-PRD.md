# Product Requirements Document (PRD): CareRelay

## 1. Executive Summary
**CareRelay** is an uncertainty-aware clinical documentation and patient triage copilot. It leverages a multi-agent orchestration layer to provide clinicians with editable, traceable SOAP notes while simultaneously offering patients citation-grounded urgency guidance.

**One-Sentence Value Proposition:** Bridging the gap between patient urgency and clinical documentation through transparent, uncertainty-aware agentic orchestration.

## 2. Problem Statement
### Current Workflow & Failure Modes
*   **Documentation Burden:** Clinicians spend significant time manually transcribing encounters into SOAP (Subjective, Objective, Assessment, Plan) formats.
*   **Fragmented Triage:** Patient symptom checkers often operate in a vacuum, disconnected from the clinician’s record.
*   **The "Black Box" Problem:** Existing AI tools often hide uncertainty or contradictions, leading to potential safety risks or clinician distrust.
*   **Lack of Provenance:** Standard LLM outputs rarely distinguish between what a patient said, what a clinician observed, and what the model inferred.

## 3. Target Users / Stakeholders
| User Role | Job-to-be-Done | Pain Points |
| :--- | :--- | :--- |
| **Clinicians** | Generate accurate SOAP drafts and review patient urgency. | Documentation fatigue; lack of structured data from patient pre-interviews. |
| **Patients / Caregivers** | Understand the urgency of symptoms and safe next steps. | Anxiety; confusing medical jargon; "Dr. Google" hallucinations. |
| **Clinical Reviewers** | Handle escalated cases where AI uncertainty is high. | High volume of low-risk cases; lack of context for escalations. |
| **Healthcare Admins** | Monitor safety, quality, and maintain audit trails. | Compliance risks; lack of transparency in AI decision-making. |

## 4. Product Principles & Design Constraints
*   **Decision Support, Not Diagnosis:** The system provides "urgency guidance" and "drafts." It never diagnoses or prescribes.
*   **Transparency First:** If the system is unsure, it must surface that uncertainty via the **Uncertainty Map**.
*   **Deterministic Safety:** Hard safety rules (red flags) override generative logic.
*   **Two-Key Safety Gate:** No low-risk guidance is issued without an independent "Safety Critic" failing to disprove it.

## 5. Goals & Non-Goals
### Goals
*   Reduce clinician documentation time via automated SOAP drafting.
*   Provide patients with safe, evidence-based urgency guidance.
*   Surface "Longitudinal Clinical Deltas" (changes over time).
*   Ensure 100% citation faithfulness for medical guidance.

### Non-Goals (MVP)
*   Autonomous diagnosis or prescribing.
*   Replacement of emergency services (911/A&E).
*   Autonomous EHR write-back (requires human sign-off).
*   Broad open-web medical retrieval (restricted to curated corpus).

## 6. User Journeys
### 6.1 Patient Journey
1.  **Intake:** Patient enters symptoms via text or voice.
2.  **Adaptive Interview:** Triage Agent asks minimum high-value follow-up questions.
3.  **Safety Check:** System checks for red flags and runs the Safety Critic.
4.  **Guidance:** Patient receives urgency class and plain-language instructions.
5.  **Teach-back:** Patient confirms understanding of safety-net instructions.

### 6.2 Clinician Journey
1.  **Review:** Clinician opens the "Escalation Inbox" or patient record.
2.  **Analysis:** Views the Uncertainty Map and SOAP draft with provenance markers.
3.  **Edit/Sign-off:** Clinician modifies the SOAP note and approves the record.

## 7. Functional Requirements
| ID | Feature | Description | Priority |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Transcript Intake** | Support for text or transcript intake from clinician-patient encounters. | P0 |
| **FR-02** | **Adaptive Triage** | Multi-turn interview logic to gather "minimum high-value" facts. | P0 |
| **FR-03** | **Structured SOAP** | Generation of editable SOAP notes with evidence markers. | P0 |
| **FR-04** | **Urgency Classification** | 4 Classes: Emergency, Same-Day, Routine, Self-Care. | P0 |
| **FR-05** | **Uncertainty Map** | UI component showing missing facts, contradictions, and red flags. | P0 |
| **FR-06** | **Safety Critic** | Independent agent to audit and attempt to disprove low-risk results. | P0 |
| **FR-07** | **Mandatory Escalation** | Logic to push cases to humans if red flags or high uncertainty exist. | P0 |
| **FR-08** | **Longitudinal Delta** | Comparison of current symptoms against prior Qdrant-stored encounters. | P1 |
| **FR-09** | **Teach-back Check** | Interactive confirmation that the patient understands instructions. | P1 |

## 8. Multi-Agent Design (Google ADK + Lyzr)
| Agent | Responsibility | Tools / Memory | Failure Behavior |
| :--- | :--- | :--- | :--- |
| **Lyzr Orchestrator** | State management, parallel execution, guardrails. | Session State, Escalation Queue. | Escalate on logic timeout. |
| **Triage Agent (ADK)** | Conducts interview, proposes urgency. | Qdrant (RAG), Patient History. | Escalate if >3 turns without clarity. |
| **Safety Critic (ADK)** | Adversarial audit of Triage results. | Red-flag Rulebook (Deterministic). | Default to "High Risk" on doubt. |
| **Documentation Agent** | Generates SOAP and Provenance Map. | Transcript, ADK Reasoning. | Mark sections as "Incomplete." |

## 9. Uncertainty Map & Safety Gate Logic
*   **The Map:** Tracks (1) Known Facts, (2) Missing Facts, (3) Contradictions, (4) Retrieval Quality Score.
*   **The Gate:** 
    1. Triage Agent proposes "Self-Care."
    2. Safety Critic receives the proposal + full transcript.
    3. Safety Critic searches for any evidence of "Red Flags" or "Insufficient Evidence."
    4. If Critic finds a risk, the case is escalated to "Same-Day Review" or "Emergency."

## 10. Data Requirements (Qdrant)
*   **Hybrid Retrieval:** Dense semantic matching (embeddings) + Sparse/Exact matching (BM25) for medical terms.
*   **Metadata Filters:** Age band, pregnancy status, jurisdiction, specialty, and document version.
*   **Longitudinal Memory:** Encounters stored as vectors; queries compare current vector against historical centroids to find "Deltas."
*   **Tenant Isolation:** Strict namespace/collection separation per healthcare provider.

## 11. Tech Stack (from Architecture)
*   **Frontend:** React, Tailwind CSS, WebSockets (for real-time agent updates).
*   **Orchestration:** Lyzr SDK, Python, FastAPI.
*   **Agents:** Google ADK (utilizing Med-PaLM 2 or Gemini Pro).
*   **Memory/Vector DB:** Qdrant.
*   **Queue/State:** Redis / RabbitMQ.

## 12. Security & Infrastructure
*   **Auditability:** Every agent decision, RAG source, and human edit is logged with a timestamp and UserID.
*   **Privacy:** PII/PHI masking before processing (simulated for MVP).
*   **Deployment:** Containerized (Docker), orchestrated via Kubernetes or Cloud Run.

## 13. Success Metrics (Engineering Gates)
*   **Red-Flag Recall:** 100% (System must never miss a deterministic red flag in test datasets).
*   **Citation Faithfulness:** >95% of generated instructions must map to a curated RAG source.
*   **SOAP Accuracy:** Clinician "Acceptance Rate" of drafts >80% without major edits.
*   **Latency:** End-to-end parallel agent response < 5 seconds.

## 14. Build Sprint Plan (MVP)
*   **Phase 1 (Foundation):** Setup Qdrant with curated medical corpus; Lyzr-ADK connectivity.
*   **Phase 2 (Agent Logic):** Implement Triage and Safety Critic prompts; define red-flag rules.
*   **Phase 3 (UI/UX):** Build the Uncertainty Map and Clinician Escalation Inbox.
*   **Phase 4 (Testing):** Run "Adversarial Clinical Scenarios" to test escalation triggers.

## 15. Open Questions & Risks
*   **Risk:** Latency of multi-agent loops affecting patient experience. *Mitigation: Parallel execution via Lyzr.*
*   **Risk:** LLM "hallucinating" provenance markers. *Mitigation: Structured JSON output forcing source-ID mapping.*
*   **Open Question:** How to handle conflicting medical guidelines in the RAG corpus? *Decision: Use versioned, jurisdiction-specific metadata filters.*

---
**Disclaimer:** *CareRelay is a clinical decision support tool. It does not provide medical diagnoses or treatment plans. All outputs must be reviewed and signed off by a qualified healthcare professional.*