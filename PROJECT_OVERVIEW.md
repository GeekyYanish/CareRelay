# CareRelay — Project Overview & Guide

**Purpose of this document:** one place to understand what CareRelay is, how it works end-to-end, where code lives, how to run it, how to deploy it, and what you must not claim about it.

**Status:** Hackathon clinical decision-support **prototype** with production-oriented controls.  
**Not clinically validated.** Do not use for real care decisions without formal clinical governance.

Related deeper docs:

| Doc | Use when |
|---|---|
| [README.md](README.md) | Day-one run commands |
| [HANDOVER.md](HANDOVER.md) | Ownership transfer & ops tips |
| [docs/architecture.md](docs/architecture.md) | Node map & diagrams |
| [docs/safety-model.md](docs/safety-model.md) | Gate rules |
| [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md) | Lyzr I/O contract |
| [docs/integration-setup.md](docs/integration-setup.md) | Lyzr / Gemini / MCP / hosting |
| [docs/demo-script.md](docs/demo-script.md) | Live demo walkthrough |
| [docs/security/limitations.md](docs/security/limitations.md) | What must not be claimed |

---

## 1. What CareRelay is

CareRelay bridges **patient urgency guidance** and **clinician documentation**:

1. A patient (or caregiver) reports symptoms.
2. The system runs deterministic safety rules + multi-agent triage/critique/SOAP drafting.
3. A **deterministic safety gate** decides final urgency: `Emergency` | `Same-Day` | `Routine` | `Self-Care`.
4. The patient gets plain-language guidance, citations, and teach-back.
5. A clinician gets an editable SOAP draft with sentence-level provenance and an uncertainty map.
6. Risky / uncertain cases go to a durable **reviewer escalation queue**.

### One-sentence value

> Make clinical unknowns visible before they become risk — with fail-closed urgency gating and provenance-rich drafts.

### Hard non-goals (by design)

- No diagnosis, prescribing, or treatment plans  
- No autonomous EHR write-back  
- No replacement of emergency services (911 / A&E)  
- No open-web medical retrieval (curated corpus only)  
- Agents **cannot** override the final safety gate  

---

## 2. Who uses it (roles)

| Role | Route | Job |
|---|---|---|
| **Patient** | `/patient` | Consent → intake → questions → urgency guidance → teach-back |
| **Clinician** | `/clinician` | Review encounters, uncertainty map, edit/sign SOAP |
| **Reviewer** | `/reviewer` | Claim & resolve escalations with a required note |
| **Admin** | `/admin` | Metrics, integration readiness, Lyzr verify, ops snapshot |

### Auth

| Action | Endpoint / page | Notes |
|---|---|---|
| Sign in | `POST /api/v1/auth/login` · `/login` | Email + password → JWT |
| Sign up | `POST /api/v1/auth/signup` · `/signup` | Creates a **patient** only |
| Session | Bearer JWT (HS256), ~8h | Stored in browser `localStorage` |

- Passwords: PBKDF2-HMAC-SHA256  
- Public signup **never** creates clinician / reviewer / admin (those stay provisioned or seeded)  
- Demo accounts (when `SEED_DEMO_DATA=true`):

| Email | Password | Role |
|---|---|---|
| `patient@demo.carerelay.local` | `demo-patient` | patient |
| `clinician@demo.carerelay.local` | `demo-clinician` | clinician |
| `reviewer@demo.carerelay.local` | `demo-reviewer` | reviewer |
| `admin@demo.carerelay.local` | `demo-admin` | admin |

---

## 3. System architecture (big picture)

```text
Browser (React SPA)
        │
        ▼
   Nginx (web image)
   proxies /api /a2a /mcp  ──────►  FastAPI (apps/api)
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 ▼                      ▼                      ▼
            PostgreSQL                Redis                 Qdrant
         users, encounters,        event fan-out         guidelines +
         escalations, audit        (or in-memory)        encounter memory
                                                         (or in-memory)
                                        │
                                        ▼
                              Lyzr SuperFlow (optional)
                         triage → critic → SOAP (typed JSON)
                                        │
                                        ▼
                         CareRelay deterministic safety gate
                              (always owns final urgency)
```

### Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, Zustand, TanStack Query |
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Data | PostgreSQL 16, Redis 7, Qdrant 1.15 |
| Agents | Lyzr SuperFlow (+ mock/local fallback); optional Gemini |
| Edge | Nginx in web Docker image |
| Tooling | pnpm workspace, Docker Compose, pytest, Vitest, Playwright |

### Logical nodes (MVP mapping)

| Concern | Where it lives |
|---|---|
| Patient / Clinician / Reviewer / Admin UI | `apps/web/src/pages/*` |
| API + RBAC + WS + A2A + MCP | `apps/api/app/main.py` |
| Encounter lifecycle + safety gate | `apps/api/app/services.py` |
| Lyzr SuperFlow adapter | `apps/api/app/orchestration.py` |
| Agents / retrieval | `apps/api/app/agents/providers.py` |
| Red-flag YAML engine | `apps/api/app/rules.py` + `packages/clinical-rules/` |
| Auth | `apps/api/app/auth.py`, signup/login in `main.py` |
| Persistence + audit hash chain | `apps/api/app/store.py` |
| Settings | `apps/api/app/core.py` |
| Demo scenarios | `packages/demo-data/scenarios.json` |

---

## 4. End-to-end workflow (runtime)

```mermaid
sequenceDiagram
  actor Patient
  participant Web
  participant API
  participant Rules as Red-Flag Rules
  participant Qdrant
  participant Lyzr as Lyzr SuperFlow
  participant Gate as Safety Gate
  actor Reviewer
  actor Clinician

  Patient->>Web: Sign up / login
  Patient->>Web: Create encounter + consent
  Patient->>API: Ingest symptoms (text / voice transcript / demo scenario)
  API->>API: Mask PHI patterns
  API->>Rules: Deterministic scan
  alt Emergency red flag
    Rules-->>API: Emergency override
    API->>Reviewer: Durable escalation
  else Continue
    API->>Patient: Up to 3 adaptive questions
    API->>Qdrant: Retrieve curated evidence
    API->>Lyzr: Execute SuperFlow (triage + critic + SOAP)
    Lyzr-->>API: Typed care_relay_result JSON
    API->>Gate: Deterministic two-key gate
    Gate-->>API: Final urgency + reason codes
    alt Escalated
      API->>Reviewer: Queue item
    end
    API->>Patient: Guidance + citations + teach-back
    API->>Clinician: Uncertainty map + SOAP draft
  end
```

### Step-by-step (patient path)

1. **Auth** — signup (patient) or login.  
2. **Encounter create** — empty clinical session.  
3. **Consent** — required before processing.  
4. **Intake** — free text, simulated voice transcript, or one of 8 demo scenarios.  
5. **PHI masking** — regex-style masking before any external agent call.  
6. **Red-flag scan** — versioned YAML rules; can force Emergency immediately.  
7. **Adaptive interview** — up to ~3 high-value follow-ups if needed.  
8. **Retrieval** — hybrid search in Qdrant (guidelines + prior encounter memory), or in-memory fallback.  
9. **Orchestration** — Lyzr SuperFlow (or local/mock) produces triage proposal, independent critic, SOAP draft.  
10. **Safety gate** — CareRelay (not Lyzr) sets final urgency and whether to escalate.  
11. **Patient output** — urgency class, instructions, citations, timeline, teach-back check.  
12. **Clinician path** — uncertainty map + provenance SOAP → edit → sign-off.  
13. **Reviewer path** — claim escalation → resolve with note.  

### Urgency classes

| Class | Meaning (demo) |
|---|---|
| **Emergency** | Seek emergency care now |
| **Same-Day** | Human / same-day clinical review |
| **Routine** | Non-urgent clinical follow-up |
| **Self-Care** | Home care with safety-net advice |

### Safety gate (must understand)

Low-risk outputs (`Routine` / `Self-Care`) require **all** of:

- Exact triage ↔ critic agreement  
- Retrieval quality ≥ **0.70**  
- Uncertainty ≤ **0.25**  
- No critical missing facts  

Anything else (red flags, disagreement, timeout, weak retrieval, high uncertainty, Lyzr failure) → **fail closed** to at least Same-Day / escalation.  
**Only the CareRelay gate** emits patient-facing urgency.

---

## 5. How Lyzr is used

Lyzr is the **optional live multi-agent orchestrator** (SuperFlow).

| Item | Detail |
|---|---|
| Provider switch | `ORCHESTRATOR_PROVIDER=lyzr` |
| Credentials | `LYZR_API_KEY`, `LYZR_WORKFLOW_ID` |
| API base | `https://inference.studio.lyzr.ai/api` |
| Lifecycle | `POST /workflows/execute` → poll `GET /executions/{id}` |
| Verify | `make verify-lyzr` or Admin → Verify Lyzr |

**What Lyzr does:** triage proposal, safety critic, SOAP draft JSON.  
**What Lyzr must not do:** final urgency gate, diagnosis, prescribing, EHR write-back.

If credentials are missing / workflow fails / output is invalid → audited failure → Same-Day human review.

Contract: [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md)

Local rehearsal without live Lyzr:

```bash
ORCHESTRATOR_PROVIDER=local
REQUIRE_LIVE_ORCHESTRATION=false
DEMO_MODE=true
```

---

## 6. How Qdrant is used

Qdrant is the **vector store** for retrieval-augmented evidence and longitudinal memory.

| Collection purpose | Role |
|---|---|
| Guidelines corpus | Curated medical guidance snippets for citations |
| Encounter memory | Prior encounters for “longitudinal delta” style comparison |

- Hybrid retrieval: dense + sparse  
- Tenant-separated collection names  
- `RETRIEVAL_PROVIDER=qdrant` with `QDRANT_URL`  
- If Qdrant is down → **in-memory hybrid fallback** (demo still runs; quality may force escalation)

Note: the current API client primarily uses `QDRANT_URL`. Qdrant Cloud API keys may need extra wiring if your cluster requires auth.

---

## 7. Data stores

| Store | Holds |
|---|---|
| **PostgreSQL** | Users, encounters, escalations, append-only audit hash chain |
| **Redis** | Event fan-out / pub-sub (in-memory fallback exists) |
| **Qdrant** | Guideline + encounter vectors |

Audit events are **append-only** (tamper-evident hash chain). Do not rewrite history.

---

## 8. Repository layout

```text
Hackathon/
├── apps/
│   ├── api/                 # FastAPI service
│   │   ├── app/
│   │   │   ├── main.py      # Routes, auth, RBAC
│   │   │   ├── services.py  # Encounter + safety gate
│   │   │   ├── orchestration.py
│   │   │   ├── agents/providers.py
│   │   │   ├── auth.py
│   │   │   ├── store.py
│   │   │   ├── rules.py
│   │   │   └── core.py      # Settings / env
│   │   ├── migrations/      # Alembic
│   │   └── Dockerfile       # Build context = repo root
│   └── web/                 # React SPA + Nginx
│       ├── src/pages/       # Login, Signup, role pages
│       ├── src/api/client.ts
│       ├── nginx.conf       # Proxies /api to API_UPSTREAM
│       └── Dockerfile
├── packages/
│   ├── clinical-rules/      # Red-flag YAML
│   ├── demo-data/           # 8 scenarios
│   └── api-types/           # Generated OpenAPI/TS (do not hand-edit)
├── docs/                    # Architecture, safety, integrations
├── docker-compose.yml
├── Makefile
├── .env.example             # Local
└── .env.production.example  # Hosted
```

---

## 9. Local development

### Prerequisites

- Docker + Docker Compose  
- Node.js 22+, pnpm 11.9.0 (`corepack enable && corepack prepare pnpm@11.9.0 --activate`)  
- Python ≥ 3.12 (for local API tests)

### Quick start

```bash
# From repo root
cp .env.example .env   # if needed
make up                # or: docker compose up --build
```

| Service | URL |
|---|---|
| Web | http://localhost:5173 |
| API docs | http://localhost:8001/docs |
| Qdrant UI | http://localhost:6333/dashboard |

### Local `.env` must stay in demo mode for localhost CORS

```bash
DEMO_MODE=true
SEED_DEMO_DATA=true
DATABASE_URL=postgresql+psycopg://carerelay:carerelay@postgres:5432/carerelay
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Do **not** point local Compose at Render’s **Internal** Postgres URL (it only works on Render’s private network).

### Tests

```bash
make test-api    # pytest
make test-web    # vitest
make test-e2e    # playwright
make test        # all
```

---

## 10. Hosted deployment (e.g. Render)

CareRelay is two Docker images + managed data services.

### Services to create

| Render type | Purpose |
|---|---|
| **Postgres** | `DATABASE_URL` |
| **Key Value** (or Upstash Redis) | `REDIS_URL` |
| **Web Service** — API | `apps/api` image |
| **Web Service** — Web | `apps/web` image |
| Qdrant Cloud or Private Service | `QDRANT_URL` |

**Do not** use Render “Workflow (Beta)” for Lyzr — Lyzr lives in Lyzr Studio.

### API Web Service settings

| Field | Value |
|---|---|
| Language | Docker |
| Root Directory | *(empty)* |
| Docker Build Context | `.` (repo root) |
| Dockerfile Path | `apps/api/Dockerfile` |
| Health Check Path | `/api/v1/health` (no trailing space) |

`DATABASE_URL` from Render Postgres:

```text
postgresql://...  →  postgresql+psycopg://...
```

(The API also auto-normalizes bare `postgresql://` to `+psycopg`.)

### Web Web Service settings

| Field | Value |
|---|---|
| Language | Docker |
| Root Directory | *(empty)* |
| Docker Build Context | `apps/web` |
| Dockerfile Path | `apps/web/Dockerfile` |
| Health Check Path | `/` |
| Env | `API_UPSTREAM=https://<api-service>.onrender.com` |

### Critical production env vars

```bash
DEMO_MODE=false
SEED_DEMO_DATA=false          # or true once to seed demo users
ORCHESTRATOR_PROVIDER=lyzr
REQUIRE_LIVE_ORCHESTRATION=true
RETRIEVAL_PROVIDER=qdrant

DATABASE_URL=postgresql+psycopg://...
REDIS_URL=rediss://...
QDRANT_URL=https://...

JWT_SECRET=<32+ random chars>
A2A_SHARED_TOKEN=<32+ random chars>

LYZR_API_KEY=...
LYZR_WORKFLOW_ID=...          # SuperFlow id from Lyzr Studio

CORS_ORIGINS=https://<web-service>.onrender.com
PUBLIC_API_BASE_URL=https://<api-service>.onrender.com
FORWARDED_ALLOW_IPS=*
```

On the **web** service only:

```bash
API_UPSTREAM=https://<api-service>.onrender.com
```

### URL checklist after deploy

1. `https://<api>/api/v1/health` → `{"status":"ok",...}`  
2. `https://<web>/api/v1/health` → same JSON (Nginx proxy working)  
3. Open `https://<web>/signup` or `/login`  

If web→API returns **502**: check `API_UPSTREAM`, redeploy web after Nginx resolver fixes, and wake the free-tier API (cold start).

---

## 11. Environment variable cheat sheet

| Variable | Meaning |
|---|---|
| `DEMO_MODE` | Relaxes production validators; use `true` locally |
| `SEED_DEMO_DATA` | Seed 4 demo users on API startup |
| `ORCHESTRATOR_PROVIDER` | `lyzr` or `local` |
| `REQUIRE_LIVE_ORCHESTRATION` | If true, missing Lyzr fails readiness / fail-closed |
| `RETRIEVAL_PROVIDER` | Usually `qdrant` |
| `AGENT_PROVIDER` | `mock` / `gemini` / `adk` |
| `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://...`) |
| `REDIS_URL` | Redis connection |
| `QDRANT_URL` | Vector DB base URL |
| `JWT_SECRET` | Signs access tokens |
| `A2A_SHARED_TOKEN` | Protects A2A task calls |
| `LYZR_API_KEY` / `LYZR_WORKFLOW_ID` | Live SuperFlow |
| `CORS_ORIGINS` | Exact browser origins (comma-separated) |
| `PUBLIC_API_BASE_URL` | Public API origin for cards / absolute refs |
| `API_UPSTREAM` | **Web container only** — where Nginx proxies `/api` |
| `VITE_API_BASE` | Usually `/api/v1` (same-origin via Nginx) |
| `DEMO_DATA_PATH` / `CLINICAL_RULES_PATH` | Baked into API image at `/packages/...` |

Production with `DEMO_MODE=false` **rejects** localhost CORS, weak JWT secrets, SQLite, and missing Lyzr when live orchestration is required.

---

## 12. API surface (mental model)

| Area | Examples |
|---|---|
| Health | `GET /api/v1/health`, `GET /api/v1/ready` |
| Auth | `POST /auth/login`, `POST /auth/signup`, `GET /auth/me`, `POST /auth/ws-ticket` |
| Encounters | create, consent, ingest, answers, triage, uncertainty, delta, SOAP, teach-back |
| Escalations | list, claim, resolve |
| Audit | `GET /audit/encounters/{id}` |
| Admin | metrics, integrations, Lyzr verify, ops snapshot |
| Interop | `/a2a/...` agent cards & tasks; `/mcp` read-only ops |

Interactive docs when API is running: `/docs` (OpenAPI).

---

## 13. Eight demo scenarios (keep green)

Seeded in `packages/demo-data/scenarios.json` (when demo mode allows). They exercise Emergency, Same-Day, Routine, Self-Care, disagreement, missing facts, weak retrieval, and related gate paths. Full walkthrough: [docs/demo-script.md](docs/demo-script.md).

---

## 14. Safety & security limitations (read before demos)

- Prototype rules/corpus — **not** medical validation  
- PHI masking is demo-grade regex, not full de-identification  
- JWTs are shared-secret HS256; no MFA / revocation list in MVP  
- Tenant isolation is app-enforced, not Postgres RLS  
- Audit chain is local hash chaining, not externally anchored  
- Never commit `.env` or paste live secrets into git  

Full list: [docs/security/limitations.md](docs/security/limitations.md)

---

## 15. Common failure modes & fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: psycopg2` | `DATABASE_URL` used bare `postgresql://` on old build | Use `postgresql+psycopg://` or pull latest normalizer |
| `FileNotFoundError: .../scenarios.json` | API image built without `packages/` | Build context = repo root; Dockerfile copies `/packages` |
| `CORS_ORIGINS must contain hosted HTTPS` | `DEMO_MODE=false` with localhost CORS | Local: `DEMO_MODE=true`; Prod: real HTTPS web origin |
| Health check 404 `/api/v1/health%20` | Trailing space in Render health path | Set exactly `/api/v1/health` |
| Web `listen ${PORT}` emerg | envsubst filter didn’t include `PORT` | `NGINX_ENVSUBST_FILTER=API_UPSTREAM\|PORT` |
| Login **502** via web | Nginx can’t reach API | Set `API_UPSTREAM`, redeploy web; check API awake |
| Login **401** | No users / wrong password | Signup, or `SEED_DEMO_DATA=true` once |
| Readiness false / Same-Day always | Missing Lyzr credentials | Set key + workflow id, or local orchestrator for demo |

---

## 16. Suggested learning path (new engineer)

1. Read this file + [README.md](README.md).  
2. Run `make up`, open web, walk [docs/demo-script.md](docs/demo-script.md) for all 4 roles.  
3. Read [docs/safety-model.md](docs/safety-model.md) and skim `apps/api/app/services.py`.  
4. Trace one encounter in `main.py` → `services.py` → `orchestration.py`.  
5. Skim frontend `PatientPage` / `ClinicianPage` / `SoapEditor` / `UncertaintyMap`.  
6. If deploying: follow §10 and [docs/integration-setup.md](docs/integration-setup.md).  
7. Before changing clinical rules/corpus: read limitations + agree governance owners.

---

## 17. Disclaimer

CareRelay is a **clinical decision-support demonstration**. It does not provide medical diagnoses or treatment plans. All outputs must be reviewed by a qualified professional before any real-world use.
