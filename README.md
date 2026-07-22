# CareRelay

CareRelay is a hackathon clinical decision-support prototype for uncertainty-aware urgency guidance and provenance-rich SOAP drafts. It is **not medically validated**, does not diagnose or prescribe, and does not replace emergency services or professional review.

## Run the complete demo

```bash
make demo
```

- Web: http://localhost:5173
- API/OpenAPI: http://localhost:8001/docs
- Qdrant dashboard: http://localhost:6333/dashboard

The command creates `.env` when needed, starts every service, applies Alembic migrations, and seeds idempotently. The checked-in environment template selects the live Lyzr SuperFlow adapter; until `LYZR_API_KEY` and `LYZR_WORKFLOW_ID` are pasted, readiness reports false and non-emergency agent work fails closed to Same-Day review. PostgreSQL stores operational state and durable escalations; Redis and Qdrant have safe in-process fallbacks.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Patient | `patient@demo.carerelay.local` | `demo-patient` |
| Clinician | `clinician@demo.carerelay.local` | `demo-clinician` |
| Reviewer | `reviewer@demo.carerelay.local` | `demo-reviewer` |
| Admin | `admin@demo.carerelay.local` | `demo-admin` |

## Local development

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -e 'apps/api[dev]'
cd apps/api && .venv/bin/uvicorn app.main:app --reload --port 8001

pnpm install
pnpm dev
```

## Live Lyzr orchestration

- Create the deterministic SuperFlow described in [the Lyzr contract](docs/lyzr-superflow-contract.md).
- Paste its values into `.env` as `LYZR_API_KEY=` and `LYZR_WORKFLOW_ID=`. No Lyzr SDK is needed: the backend uses Lyzr's supported HTTPS execute and execution-status APIs through `httpx`.
- Start the stack, then run `make verify-lyzr` or use “Verify Lyzr workflow” on the administrator page.
- Every successful encounter records its remote workflow and execution IDs. Lyzr never owns the final deterministic safety gate.

Additional adapters:

- `AGENT_PROVIDER=gemini` or `adk`, `GEMINI_API_KEY`, and `GEMINI_MODEL` enable the structured Gemini adapter for the explicit local fallback path.
- `MCP_PROVIDER=google_cloud`, `GOOGLE_CLOUD_PROJECT`, and a short-lived `GOOGLE_CLOUD_MCP_TOKEN` enable the fixed read-only Logging/Monitoring calls.
- A2A cards are public at `/a2a/{triage|critic|documentation}/.well-known/agent-card.json`; task calls require `A2A_SHARED_TOKEN` and never expose the final safety gate.

External agents receive masked text. Never place credentials in the frontend or logs.

For a hosted deployment, copy `.env.production.example` into the secret manager/environment of the platform running the API container. Set the public web/API origins, managed PostgreSQL/Redis/Qdrant URLs, strong JWT and A2A secrets, and keep `SEED_DEMO_DATA=false`. The repository is container-deployable; an actual public URL still requires the chosen hosting account and its deployment credentials.

## Test

```bash
make test
make test-e2e
```

See [assumptions](docs/assumptions.md), [architecture](docs/architecture.md), [safety model](docs/safety-model.md), [demo script](docs/demo-script.md), [integration setup](docs/integration-setup.md), [security limitations](docs/security/limitations.md), and the [acceptance report](docs/acceptance-report.md).
