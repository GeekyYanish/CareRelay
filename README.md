# CareRelay

CareRelay is a hackathon clinical decision-support prototype for **uncertainty-aware urgency guidance** and **provenance-rich SOAP documentation drafts**.

It turns a patient symptom report into gated urgency guidance, a transparent uncertainty view, a traceable SOAP draft for clinician review, and a durable human-review escalation when safety conditions are not met.

> **Not clinically validated.** CareRelay does not diagnose, prescribe, replace emergency services, or write to an EHR. Clinical governance and validation are required before use in care decisions.

## Quick start

```bash
make up
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API / OpenAPI | http://localhost:8001/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |

`make up` copies `.env.example` → `.env` if needed and builds the Compose stack (PostgreSQL, Redis, Qdrant, API, web). It does not create user accounts or encounter data.

Until `LYZR_API_KEY` and `LYZR_WORKFLOW_ID` are set, readiness stays false and non-emergency agent work fails closed to Same-Day human review. Redis and Qdrant have safe in-process fallbacks.

## What it does

| Role | Screen | Capabilities |
|---|---|---|
| Patient | `/patient` | Consent, text/voice-transcript intake, adaptive questions, urgency guidance, citations, timeline, teach-back |
| Clinician | `/clinician` | Encounter list, uncertainty map, sentence-provenanced SOAP edit + sign-off |
| Reviewer | `/reviewer` | Escalation queue, claim, resolve with required note |
| Admin | `/admin` | Outcome metrics, integration readiness, Lyzr verify, read-only ops snapshot |

### Safety model (summary)

1. Consent before processing; external agents receive PHI-masked text only.
2. Versioned YAML red-flag rules run before generative logic.
3. `Routine` / `Self-Care` require exact triage↔critic agreement, retrieval ≥ 0.70, uncertainty ≤ 0.25, and no critical missing facts.
4. Disagreement, timeout, weak retrieval, missing facts, or high uncertainty → durable escalation.
5. Only the deterministic safety gate produces patient-facing urgency; A2A agents cannot.

Details: [docs/safety-model.md](docs/safety-model.md)

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, Tailwind, Zustand, TanStack Query |
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn |
| Data | PostgreSQL 16 (operational state), Redis 7 (event fan-out), Qdrant 1.15 (retrieval) |
| Agents | Lyzr SuperFlow orchestration with deterministic safety controls |
| Interop | A2A agent cards/tasks, read-only Google Cloud Logging/Monitoring MCP |
| Tooling | pnpm workspace, Docker Compose, Nginx, pytest, Vitest, Playwright |

## Repository layout

```text
apps/
  api/                 FastAPI service, Alembic migrations, pytest
  web/                 React SPA, Vitest + Playwright, Nginx image
packages/
  api-types/           Generated OpenAPI + TypeScript types (do not hand-edit)
  clinical-rules/      Versioned deterministic red-flag YAML
docs/                  Architecture, safety, integrations, acceptance
.env.example           Local / Compose template
.env.production.example  Hosted deployment template
docker-compose.yml
Makefile
```

## Local development

**Prerequisites:** Node.js 22+, pnpm 11.9.0, Python ≥ 3.12, Docker + Docker Compose (for full stack).

### Backend

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -e 'apps/api[dev]'
cd apps/api && .venv/bin/uvicorn app.main:app --reload --port 8001
```

### Frontend

```bash
pnpm install
pnpm dev
```

Vite proxies `/api`, `/a2a`, and `/mcp` to `localhost:8001`.

### Useful commands

| Command | Purpose |
|---|---|
| `make up` | Full Compose stack |
| `make down` | Stop Compose |
| `make logs` | Follow API + web logs |
| `make test` | API + web unit + E2E |
| `make test-api` | pytest only |
| `make test-web` | Vitest only |
| `make test-e2e` | Playwright E2E |
| `make build` | Production web build |
| `make generate-types` | Regenerate OpenAPI → TS types |
| `make verify-lyzr` | Sanitize-check live Lyzr workflow |

## Environment

Copy `.env.example` for local services, or `.env.production.example` for hosted deploys. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `AGENT_PROVIDER` | `gemini` \| `adk` |
| `ORCHESTRATOR_PROVIDER` | `lyzr` |
| `RETRIEVAL_PROVIDER` | Normally `qdrant` |
| `MCP_PROVIDER` | `google-cloud` |
| `A2A_ENABLED` | Public A2A cards + token-protected tasks |
| `DATABASE_URL` | SQLAlchemy URL (PostgreSQL in production) |
| `REDIS_URL` / `QDRANT_URL` | Cache / vector store |
| `JWT_SECRET` / `A2A_SHARED_TOKEN` | Required 32-character minimum auth secrets |
| `LYZR_API_KEY` / `LYZR_WORKFLOW_ID` | Live SuperFlow credentials |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Optional Gemini adapter |
| `CORS_ORIGINS` / `PUBLIC_API_BASE_URL` | Browser + A2A card origins |
| `VITE_API_BASE` | Browser API path (usually `/api/v1`) |
| `API_UPSTREAM` | Nginx → API target (production web image) |

Full setup: [docs/integration-setup.md](docs/integration-setup.md)

## Live Lyzr orchestration

1. Build the SuperFlow per [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md).
2. Set `LYZR_API_KEY` and `LYZR_WORKFLOW_ID` in `.env`.
3. Run `make verify-lyzr` or use **Verify Lyzr workflow** on the admin page.
4. CareRelay keeps the deterministic safety gate outside Lyzr; remote workflow/execution IDs are audited per encounter.

External agents receive masked text only. Never put credentials in frontend code or logs.

## Testing

```bash
make test
make test-e2e
```

Run the application with production-compatible environment variables for API integration checks. The web build and component tests run without external credentials.

## Documentation

| Doc | Contents |
|---|---|
| [HANDOVER.md](HANDOVER.md) | Ownership transfer, map of ownership, first-week checklist |
| [docs/architecture.md](docs/architecture.md) | 19-node architecture and data flows |
| [docs/safety-model.md](docs/safety-model.md) | Deterministic gate rules |
| [docs/integration-setup.md](docs/integration-setup.md) | Lyzr, Gemini, MCP, A2A, hosting |
| [docs/lyzr-superflow-contract.md](docs/lyzr-superflow-contract.md) | SuperFlow I/O contract |
| [docs/assumptions.md](docs/assumptions.md) | PRD conflict resolutions |
| [docs/security/limitations.md](docs/security/limitations.md) | Known security/clinical limits |
| [docs/acceptance-report.md](docs/acceptance-report.md) | Verified gates and pending items |
| [docs/requirements-traceability.md](docs/requirements-traceability.md) | Requirements → code map |

## Hosted deployment (outline)

1. Start from `.env.production.example`.
2. Use managed PostgreSQL, Redis, and Qdrant.
3. Set strong `JWT_SECRET` / `A2A_SHARED_TOKEN`, exact HTTPS `CORS_ORIGINS`, and live Lyzr credentials.
4. Deploy `apps/api` and `apps/web` Docker images with private networking; set web `API_UPSTREAM` to the API.
5. Migrations run via API container entrypoint (or a release command).

The repo is container-deployable; publishing a public URL still requires your hosting account and secrets.
