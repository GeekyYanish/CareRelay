# CareRelay assumptions and conflict resolutions

The PRD is authoritative for behavior, the refined 19-node architecture JSON for structure, and patient safety wins every conflict.

| Conflict | Resolution |
|---|---|
| Patient UI is React Native in the diagram while the delivery stack specifies Vite | One responsive React + Vite application serves all roles. |
| Diagram shows Kong, gRPC, BullMQ, and separate services | Preserve the boundaries as FastAPI modules; use HTTP/WebSocket, Redis fan-out, and PostgreSQL-backed durable escalations. |
| Med-PaLM 2 appears in source diagrams | It is never required. Mock providers are default, with optional Gemini/Google ADK and Lyzr adapters. |
| No CareRelay Mermaid resource was attached | Generate diagrams from the authoritative architecture JSON. |
| Qdrant or Redis may be unavailable | In-memory retrieval and event-bus adapters keep DEMO_MODE usable; low retrieval quality still fails closed. |
| Uncertainty Map is P1 in an older PRD | The supplied refined PRD marks FR-05 P0, so it is P0 here. |
| Earlier scaffold referenced a single Lyzr agent chat endpoint | Replace it with the official SuperFlow execute/poll lifecycle using `LYZR_WORKFLOW_ID`; retain the deterministic CareRelay gate after workflow completion. |
| “Production ready live” requested without a hosting account or provider credentials | Deliver deployable containers, production environment template, live readiness/verification, and blank secret slots. Publishing a public URL remains the single hosting-account action. |

## Prototype boundaries

- Red-flag rules and the corpus are synthetic demonstration resources, not validated clinical policy.
- CareRelay offers urgency guidance and documentation drafts, never diagnosis, prescribing, dose changes, or autonomous EHR writes.
- External agents receive masked text only. Raw chain-of-thought is neither stored nor shown.
- Default thresholds (retrieval 0.70, maximum low-risk uncertainty 0.25) are demonstration settings, not clinical calibration.
