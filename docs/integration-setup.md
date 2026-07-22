# Live integration setup

The main environment template is wired to Lyzr SuperFlow. It intentionally leaves credentials blank so secrets can be supplied by `.env` or a deployment secret manager without entering source control.

## Gemini / Google ADK

Set `AGENT_PROVIDER=gemini`, `GEMINI_API_KEY`, and optionally `GEMINI_MODEL`. The adapter requests JSON Schema output, validates it with Pydantic, re-runs deterministic safety logic, and fails closed on timeout or invalid output. Install the `live-agents` Python extra only for official ADK/A2A bridge experiments.

## Lyzr

1. In Lyzr Agent Studio, create the triage, safety critic, and documentation agents, then place them in a deterministic SuperFlow. Use the exact input/output contract in `docs/lyzr-superflow-contract.md`.
2. Deploy the workflow and copy its `wf_...` identifier.
3. Paste `LYZR_API_KEY=` and `LYZR_WORKFLOW_ID=` into `.env` (or inject them as hosted secrets). Keep `ORCHESTRATOR_PROVIDER=lyzr` and the official base `https://inference.studio.lyzr.ai/api`.
4. Run `make verify-lyzr`. The command calls `GET /workflows/{workflow_id}` and prints only sanitized workflow metadata.
5. Run an encounter and check the admin integration panel or encounter JSON for the `execution_id`. CareRelay executes with `POST /workflows/execute`, polls `GET /executions/{execution_id}`, and validates the completed output with Pydantic plus semantic checks.

No extra Lyzr client library is needed; the supported REST API is called with the already-installed `httpx` client. The API key is sent only in the `x-api-key` header and is never returned, audited, or logged. The fixed safety gate remains inside CareRelay and cannot be exposed by a Lyzr agent.

For a credential-free rehearsal only, set `ORCHESTRATOR_PROVIDER=local` and `REQUIRE_LIVE_ORCHESTRATION=false`. This is visibly reported as `demo-fallback`, not as a live integration.

## Google Cloud operations MCP

Set `MCP_PROVIDER=google_cloud`, `GOOGLE_CLOUD_PROJECT`, and a short-lived `GOOGLE_CLOUD_MCP_TOKEN`. Only `list_log_entries`, `list_log_names`, `list_timeseries`, and `list_alerts` are accepted. Apply the sample organization policy in `docs/security/google-cloud-mcp-readonly-policy.json`; clinical agents have no MCP reference.

## A2A

Cards are public at `/a2a/{triage|critic|documentation}/.well-known/agent-card.json`. Send JSON-RPC typed data parts to `/a2a/{agent}` with `Authorization: Bearer $A2A_SHARED_TOKEN`. The final gate is intentionally not an A2A agent.

## Hosted deployment values

Start from `.env.production.example`. Use managed PostgreSQL, Redis, and Qdrant endpoints; set `DEMO_MODE=false`, `SEED_DEMO_DATA=false`, a strong `JWT_SECRET`, a rotated `A2A_SHARED_TOKEN`, exact HTTPS `CORS_ORIGINS`, and the public HTTPS `PUBLIC_API_BASE_URL`. Production mode rejects startup if these safety-critical values are missing or still local/demo values. Run the API and web Dockerfiles on a platform that supports private service networking. Set the web container's `API_UPSTREAM` to the API's private or public HTTPS origin; Nginx keeps the browser on the web origin and proxies `/api`, `/a2a`, and `/mcp`. Run database migrations as a release command or allow the API container entrypoint to run them before Uvicorn starts.
