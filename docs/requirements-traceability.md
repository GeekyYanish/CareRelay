# Requirements traceability

| Requirement | Implementation | Verification |
|---|---|---|
| FR-01 intake | Text and simulated voice transcript endpoints + patient UI | API tests + 375/1440 browser flows |
| FR-02 adaptive triage | Three-turn deterministic question bank; re-scan after every answer | Safety/API tests |
| FR-03 SOAP provenance | Typed sentence provenance and clinician editor | Unit + component + lifecycle E2E |
| FR-04 four urgency classes | Exact public enum and deterministic order | Exhaustive 4×4 gate matrix + eight-scenario E2E |
| FR-05 Uncertainty Map | Known/missing/contradiction/red-flag UI | Component + clinician E2E |
| FR-06 Safety Critic | Independent provider call and typed schema | Gate boundary/matrix tests |
| FR-07 escalation | PostgreSQL escalation records and reviewer console | API + cross-role lifecycle E2E |
| FR-08 longitudinal delta | Patient-scoped encounter comparison endpoint | REST contract + clinician page |
| FR-09 teach-back | Deterministic failure/restatement/success tracking | API test + patient E2E |
| Auditability | Tenant-wide SHA-256 chain with per-encounter explorer | Chain-link test + admin lifecycle E2E |
| Tenant/RBAC isolation | Repository filters, JWT roles, scoped WebSocket tickets | Tenant and single-use ticket tests |
| Redis/Qdrant resilience | Redis fan-out and Qdrant tenant hybrid collections with local fallback | Fallback unit/API paths; Compose graph validated |
| Lyzr orchestration | SuperFlow execute/poll lifecycle, masked typed input, Pydantic + semantic output validation, execution audit, readiness and admin verifier | Five adapter contract/failure tests; credentialed workflow verification pending supplied key/ID |
| A2A | Typed cards and authenticated task calls | A2A contract test |
| Google Cloud MCP | Fixed read-only allowlist + local mock | Allowlist rejection + admin E2E |
| Generated contracts | FastAPI OpenAPI and shared TypeScript declarations | `make generate-types` |
