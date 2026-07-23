# CareRelay architecture

The refined source has exactly 19 logical nodes. They remain explicit boundaries in one SPA and one FastAPI process for the MVP:

| Source node | MVP boundary |
|---|---|
| Clinician Workspace | `/clinician`, `ClinicianPage`, `SoapEditor` |
| Clinician Reports | `/clinician/reports`, list/detail/export, versioned SOAP |
| Patient Experience | `/patient`, `PatientPage` |
| Clinical Escalation Console | `/reviewer`, `ReviewerPage` |
| Safety Dashboard | `/admin`, `AdminPage` |
| API Gateway | Nginx container + FastAPI middleware/RBAC |
| Encounter API & Stream | `/api/v1/encounters`, scoped WebSockets |
| Encounter Supervisor | `EncounterService` with live Lyzr SuperFlow execute/poll adapter and explicit local demo fallback |
| Intake & Triage Agent | typed `AgentProvider.triage` |
| Independent Safety Critic | typed `AgentProvider.critique` |
| Red-Flag Rules Engine | `RedFlagEngine` + versioned YAML |
| Qdrant Guidelines | tenant-specific named dense/sparse collection |
| Qdrant Encounter Memory | separate tenant-specific named dense/sparse collection |
| PostgreSQL Operational Store | SQLAlchemy repositories + Alembic |
| Two-Key Safety Gate | deterministic `safety_gate` |
| Scribe & SOAP Agent | typed `AgentProvider.document` + sentence provenance |
| Observability & Evaluation | audit/admin metrics + operations MCP adapter |
| Consent & Privacy Service | consent route + `mask_phi` boundary |
| Escalation Queue (DLQ) | durable PostgreSQL escalation records; Redis event fan-out |
| Evidence Retrieval Agent | `QdrantRetrievalProvider` with in-memory fallback |
| Clinician Reports | `/clinician/reports*` APIs + UI; versioned SOAP; HTML export |

### Clinician reports

Denormalized encounter columns (`urgency`, `report_status`, `assigned_clinician_id`, `updated_at`) enable SQL filter/pagination. Table `soap_revisions` stores immutable signed versions; edits after sign create a new draft revision. Report list/detail/export endpoints are tenant-scoped and audit-logged. Redis short-TTL cache invalidates on encounter save. Escalations are priority-sorted with SLA age/breach and resolution categories.

```mermaid
flowchart LR
  subgraph Experience
    P[Patient Experience]
    C[Clinician Workspace]
    R[Reviewer Console]
    A[Safety Dashboard]
  end
  subgraph Application
    API[FastAPI Encounter API]
    Consent[Consent and PHI Masking]
    Supervisor[Lyzr SuperFlow supervisor]
  end
  subgraph Agents
    Triage[Triage Agent]
    Critic[Independent Safety Critic]
    Scribe[SOAP Agent]
    Retrieval[Evidence Retrieval]
  end
  subgraph Safety
    Rules[Deterministic Red-Flag Rules]
    Gate[Two-Key Gate]
    Queue[Durable Escalation Queue]
  end
  subgraph Data
    PG[(PostgreSQL)]
    QG[(Qdrant Guidelines)]
    QM[(Qdrant Memory)]
    Redis[(Redis Pub/Sub)]
  end
  P & C & R & A --> API
  API --> Consent --> Rules
  Rules --> Supervisor
  Supervisor --> Triage & Critic & Scribe & Retrieval
  Triage & Critic --> Gate
  Gate --> Queue
  Retrieval --> QG
  Supervisor --> QM & PG & Redis
  Queue --> R
```

```mermaid
sequenceDiagram
  actor Patient
  participant API
  participant Rules as Red-Flag Rules
  participant Triage
  participant Critic
  participant Gate
  participant Reviewer
  Patient->>API: consent + symptom transcript
  API->>Rules: deterministic scan
  alt Emergency signal
    Rules-->>API: Emergency override
    API-->>Reviewer: durable escalation
    API-->>Patient: seek local emergency help now
  else No immediate override
    API->>Triage: masked facts + evidence
    API->>Critic: independent masked review
    Triage-->>Gate: urgency proposal
    Critic-->>Gate: adversarial audit
    Gate-->>API: gated result + reason codes
    opt gate fails closed
      API-->>Reviewer: durable escalation
    end
    API-->>Patient: cited urgency guidance
  end
```
