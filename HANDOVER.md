# CareRelay — Handover Document

**Audience:** engineer or team taking ownership of this repository  
**Status:** hackathon prototype with production-oriented controls (not clinically validated)  
**Last verified:** 2026-07-22 (see [docs/acceptance-report.md](docs/acceptance-report.md))

Use this document together with [README.md](README.md). The README covers day-one run instructions; this file covers ownership, where logic lives, what is unfinished, and how to operate safely.

---

## 1. What you are inheriting

CareRelay is a multi-role clinical decision-support **demo**:

- **Patient** submits symptoms → gets gated urgency guidance + teach-back.
- **Clinician** reviews uncertainty + editable SOAP with sentence provenance + sign-off.
- **Reviewer** claims/resolves durable escalations.
- **Admin** sees metrics and integration readiness.

Hard product boundaries (by design):

- No diagnosis, prescribing, treatment plans, or EHR write-back.
- No raw chain-of-thought storage or display.
- Deterministic CareRelay safety gate always owns final urgency — agents cannot override Emergency/Same-Day or approve low-risk alone.

Authoritative sources when docs conflict:

1. Patient safety / fail-closed behavior  
2. PRD (`docs/source/CareRelay-PRD.md` and root PRD copy)  
3. Refined architecture JSON (`docs/source/architecture.json`)

Conflict resolutions: [docs/assumptions.md](docs/assumptions.md)

---

## 2. First 30 minutes

```bash
# 1. Full stack
make demo

# 2. Confirm services
open http://localhost:5173          # web
open http://localhost:8001/docs     # API
open http://localhost:6333/dashboard

# 3. Login as patient → run "Emergency red flag" scenario
# 4. Login as reviewer → claim/resolve escalation
# 5. Login as clinician → open encounter, inspect SOAP, sign-off
# 6. Login as admin → check integration panel

# 7. Tests (requires local venv for API)
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -e 'apps/api[dev]'
pnpm install
make test-api
make test-web
```

Demo credentials are in the README. Full walkthrough: [docs/demo-script.md](docs/demo-script.md).

**Expected posture without Lyzr credentials:** API health OK; readiness false with sanitized `LYZR_NOT_CONFIGURED`; non-emergency paths fail closed to Same-Day review.

---

## 3. System map (who owns what)

```text
Browser (React SPA) ──► Nginx (/api,/a2a,/mcp) ──► FastAPI
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              PostgreSQL                  Redis                   Qdrant
           encounters, users,         event fan-out           guidelines +
           escalations, audit         (or in-memory)          encounter memory
                                                              (or in-memory)
```

| Concern | Primary files |
|---|---|
| HTTP/WS/A2A/MCP routes + RBAC | `apps/api/app/main.py` |
| Encounter lifecycle, safety gate, guidance, escalations, SOAP | `apps/api/app/services.py` |
| Lyzr SuperFlow + local orchestrator | `apps/api/app/orchestration.py` |
| Mock / Gemini / retrieval providers | `apps/api/app/agents/providers.py` |
| Red-flag YAML engine | `apps/api/app/rules.py` + `packages/clinical-rules/demo_v1.yaml` |
| PHI masking | `apps/api/app/privacy.py` |
| Auth (PBKDF2 + HS256 JWT) | `apps/api/app/auth.py` |
| Tenant-scoped persistence + audit hash chain | `apps/api/app/store.py` |
| Settings / env | `apps/api/app/core.py` |
| Schema models | `apps/api/app/db/models.py` |
| Seed users / scenarios | `apps/api/app/seed.py`, `packages/demo-data/scenarios.json` |
| Ops MCP allowlist | `apps/api/app/mcp_ops.py` |
| Frontend routes | `apps/web/src/App.tsx` |
| Role pages | `apps/web/src/pages/*Page.tsx` |
| SOAP / uncertainty UI | `apps/web/src/components/SoapEditor.tsx`, `UncertaintyMap.tsx` |
| Auth session store | `apps/web/src/stores/auth.ts` |
| API client | `apps/web/src/api/client.ts` |
| Generated contracts | `packages/api-types/` (**regenerate only**) |

Architecture diagrams: [docs/architecture.md](docs/architecture.md)

---

## 4. Core runtime flow

1. Patient creates encounter → accepts consent.  
2. Submits text / simulated voice / demo scenario.  
3. Backend masks PHI patterns before any external call.  
4. Versioned red-flag rules scan content.  
5. If no immediate override → up to 3 adaptive follow-up questions.  
6. Retrieve curated evidence (Qdrant or in-memory).  
7. Orchestrator runs triage → independent critic → SOAP draft (Lyzr or local/mock).  
8. **Deterministic safety gate** sets final urgency: Emergency | Same-Day | Routine | Self-Care.  
9. Escalations persist in PostgreSQL for the reviewer queue.  
10. Patient sees guidance, reason codes, citations, timeline; clinician edits/signs SOAP.

Gate rules: [docs/safety-model.md](docs/safety-model.md)

### Eight seeded scenarios (must keep green)

| ID | Name | Intent |
|---|---|---|
| `emergency` | Emergency red flag | Deterministic Emergency override |
| `same-day` | Deterministic Same-Day | Rule-based Same-Day |
| `self-care` | Self-Care agreement | Two-key low-risk approval |
| `routine` | Routine agreement | Two-key Routine approval |
| `disagreement` | Critic disagreement | Fail closed → Same-Day |
| `missing-facts` | Missing critical facts | Escalation |
| `low-retrieval` | Low retrieval quality | Escalation |
| `timeout` | Provider timeout | Fail closed → Same-Day |

Source: `packages/demo-data/scenarios.json`. E2E asserts all eight in `apps/web/tests/e2e/`.

---

## 5. API surface (cheat sheet)

Base path: `/api/v1`

| Area | Endpoints |
|---|---|
| Health | `GET /health`, `GET /ready` |
| Auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/ws-ticket` |
| Demo | `GET /demo/scenarios` |
| Encounters | CRUD-ish: create/list/get, consent, demo-scenario, ingest, answers, triage, uncertainty, delta, SOAP get/patch/sign-off, teach-back, escalate |
| Escalations | `GET /escalations`, claim, resolve |
| Admin | metrics, integrations, Lyzr verify, ops snapshot |
| Audit | `GET /audit/encounters/{id}` |
| A2A | `/a2a/{triage\|critic\|documentation}` (+ well-known cards) |
| MCP | `POST /mcp` (local mock / Google Cloud adapter) |

OpenAPI: http://localhost:8001/docs — regenerate TS types with `make generate-types`.

Roles: `patient` | `clinician` | `reviewer` | `admin`. Tenant scoping is **application-enforced** in `store.py` (no DB RLS yet).

---

## 6. Configuration & secrets

| Mode | Template | Notes |
|---|---|---|
| Local / Compose | `.env.example` | `DEMO_MODE=true`, `SEED_DEMO_DATA=true` |
| Hosted | `.env.production.example` | Rejects demo secrets; requires real DB/Redis/Qdrant URLs |

**Secrets never belong in git or frontend.** `.env` is gitignored.

Critical production toggles:

- `DEMO_MODE=false`, `SEED_DEMO_DATA=false`
- Strong `JWT_SECRET`, rotated `A2A_SHARED_TOKEN`
- Exact HTTPS `CORS_ORIGINS` + `PUBLIC_API_BASE_URL`
- `API_UPSTREAM` for the web Nginx image
- Live Lyzr: `LYZR_API_KEY`, `LYZR_WORKFLOW_ID`, `ORCHESTRATOR_PROVIDER=lyzr`

Credential-free rehearsal only:

```bash
ORCHESTRATOR_PROVIDER=local
REQUIRE_LIVE_ORCHESTRATION=false
```

Integration steps: [docs/integration-setup.md](docs/integration-setup.md)  
Lyzr contract: [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md)

---

## 7. How to change common things

| Change | Where | Caution |
|---|---|---|
| Red-flag phrases / urgency | `packages/clinical-rules/demo_v1.yaml` | Safety-critical; re-run `make test-api` + E2E |
| Demo scenario outcomes | `packages/demo-data/scenarios.json` | Keep E2E expectations in sync |
| Gate thresholds | `apps/api/app/core.py` + `services.py` | Document; not clinically calibrated |
| New API field | `schemas.py` → implement → `make generate-types` | Never hand-edit `packages/api-types` |
| UI role page | `apps/web/src/pages/` | Keep disclaimer / no-diagnosis posture |
| Auth accounts | `apps/api/app/seed.py` | Demo only; replace for production IAM |
| DB schema | Alembic under `apps/api/migrations/` | API Dockerfile runs migrations on start |

Lint: Ruff (line length 100) for Python. Frontend follows existing Vite/React patterns (lazy routes, React Query, Zustand auth).

---

## 8. Testing & quality gates

```bash
make test-api    # pytest — safety matrix, RBAC, audit, A2A, MCP, Lyzr adapter (mocked transport)
make test-web    # Vitest component tests
make test-e2e    # Playwright — 8 scenarios + cross-role handoff
make build       # production web build
```

Acceptance snapshot (2026-07-22): 41 API tests pass; E2E + Compose + production images pass; **credentialed Lyzr smoke still pending**.

Browser artifacts land in `artifacts/browser/` (gitignored).

Before merging safety-related changes, treat as mandatory:

1. Safety matrix / red-flag tests green  
2. All eight scenario E2Es green  
3. No credentials or PHI in logs/UI  

---

## 9. Known limitations & open work

Documented in [docs/security/limitations.md](docs/security/limitations.md). Highest-signal items for the next owner:

| Item | Status | Suggested next step |
|---|---|---|
| Live Lyzr SuperFlow smoke test | Pending credentials | Deploy workflow per contract; set secrets; `make verify-lyzr`; run one full encounter |
| Gemini / Google ADK / Cloud MCP | Adapters wired; need live verify | Supply keys; exercise fail-closed paths |
| Clinical validation | Out of scope | Governance before any real-patient use |
| PHI masking | Regex demo only | Replace with validated DLP |
| Auth | Shared JWT secret, seeded users | Managed identity, MFA, rotation, revocation |
| Tenant isolation | App-level filters | Add PostgreSQL RLS + independent authz tests |
| WebSockets | Snapshot-then-close | Real Redis consumers, reconnect cursors |
| Encounter “delta” | Simplified prior summary | True longitudinal vector comparison if product needs it |
| Public hosting | Containers ready; no platform account in-repo | Wire secrets + managed data services on chosen host |

---

## 10. First-week ownership checklist

- [ ] Run `make demo` and complete the [demo script](docs/demo-script.md) for all four roles  
- [ ] Read safety model, architecture, assumptions, and limitations docs  
- [ ] Confirm `.env` is local-only; rotate any shared demo secrets if the repo was shared broadly  
- [ ] Decide orchestrator posture: stay on mock/local vs wire Lyzr  
- [ ] If Lyzr: create SuperFlow, paste credentials, verify, capture one audited `execution_id`  
- [ ] Run full `make test` (or CI equivalent) on a clean machine  
- [ ] Identify hosting target; copy `.env.production.example` into the secret manager  
- [ ] Agree clinical governance owners before changing rules/corpus for anything beyond demos  
- [ ] Note contacts for Lyzr workspace, Google Cloud project (if used), and hosting account  

---

## 11. Operational tips

- **Fail closed is intentional.** Timeouts, parse errors, and missing Lyzr credentials should escalate to human Same-Day review — do not “fix” by auto-approving low risk.  
- **Audit events are append-only** with a SHA-256 hash chain in PostgreSQL. Do not rewrite history; investigate via `GET /audit/encounters/{id}`.  
- **A2A cards are public; tasks need `A2A_SHARED_TOKEN`.** The final safety gate is deliberately not exposed as an A2A agent.  
- **Google Cloud MCP** is read-only allowlisted (`list_log_entries`, `list_log_names`, `list_timeseries`, `list_alerts`). Policy sample: `docs/security/google-cloud-mcp-readonly-policy.json`.  
- **Compose volumes** persist Postgres/Qdrant data locally (`postgres_data`, `qdrant_storage`). Use `make down` / volume prune only when you intend to wipe state.

---

## 12. Documentation index

| Path | Use when |
|---|---|
| [README.md](README.md) | Setup, accounts, commands |
| [docs/architecture.md](docs/architecture.md) | System design |
| [docs/safety-model.md](docs/safety-model.md) | Gate rules |
| [docs/demo-script.md](docs/demo-script.md) | Live demo |
| [docs/integration-setup.md](docs/integration-setup.md) | Provider wiring + hosting |
| [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md) | Exact Lyzr I/O |
| [docs/assumptions.md](docs/assumptions.md) | PRD vs implementation choices |
| [docs/security/limitations.md](docs/security/limitations.md) | What must not be claimed |
| [docs/acceptance-report.md](docs/acceptance-report.md) | What was verified |
| [docs/requirements-traceability.md](docs/requirements-traceability.md) | FR → code mapping |
| [docs/source/](docs/source/) | PRD + architecture JSON + checksums |

---

## 13. Handover contacts (fill in)

| Role | Name | Notes |
|---|---|---|
| Outgoing owner | | |
| Incoming owner | | |
| Lyzr / agent studio access | | |
| Cloud / hosting access | | |
| Clinical reviewer (if any) | | |

**Transfer checklist for outgoing owner**

- [ ] Share this file + README + access to secrets (out of band — never commit)  
- [ ] Confirm whether live Lyzr/Gemini/GCP credentials exist and where they live  
- [ ] Point to last green acceptance report date and any uncommitted local changes  
- [ ] Call out any env-specific overrides not in `.env.example`  

---

*CareRelay is a safety-first demo. When unsure, prefer fail-closed escalation over convenience.*
