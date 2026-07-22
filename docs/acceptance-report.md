# Acceptance report

Verified on 2026-07-22 in `DEMO_MODE=true` with no paid-provider credentials.

| Gate | Evidence | Result |
|---|---|---|
| Deterministic red-flag fixture recall | All emergency and Same-Day adversarial phrases matched | Pass |
| No downgrade of Emergency/Same-Day | Exhaustive 4×4 triage/critic matrix | Pass |
| Two-key low-risk requirements | Inclusive 0.70 retrieval / 0.25 uncertainty boundary tests | Pass |
| Credential-free patient workflow under 5 seconds | Playwright outcomes 0.9–3.6 seconds each | Pass |
| Eight seeded browser scenarios | Eight expected guidance/reason-code assertions | Pass |
| Cross-role story | Patient → SOAP sign-off → escalation resolution → admin snapshot | Pass |
| Backend suites | 41 passed; Ruff clean | Pass |
| Lyzr SuperFlow contract | Execute/poll, typed result, key isolation, paused approval, invalid output, and verification tests | Pass (mock transport) |
| Frontend component suites | 2 passed | Pass |
| Production web build | Vite route-split build completed | Pass |
| Mobile/desktop render | Chromium screenshots at 375px and 1440px inspected | Pass |
| Lyzr admin status UI | Production Nginx build visually inspected; verifier button, sanitized missing-credential alert, and no browser console errors | Pass |
| Source integrity | Three source checksums verified | Pass |
| Migration | Fresh SQLite Alembic upgrade to `20260721_0001` | Pass |
| Compose model | `docker compose config --quiet` | Pass |
| Live Compose startup | PostgreSQL, Redis, Qdrant, API, and web started; migration, health, readiness, Nginx, and seeded login verified | Pass |
| Production container rebuild | API excludes development extras; API and web images rebuilt successfully | Pass |
| Blank live-credential behavior | Health remains available; readiness false with sanitized `LYZR_NOT_CONFIGURED` verification result | Pass |
| Credentialed Lyzr smoke test | Requires the team's `LYZR_API_KEY` and deployed `LYZR_WORKFLOW_ID` | Pending credentials |

The demo guidance corpus has citation coverage on every seeded output. The corpus is intentionally tiny and synthetic, so a statistically meaningful greater-than-95% faithfulness claim is outside this prototype’s scope; no medical-validity claim is made.

Browser artifacts are written under `artifacts/browser/` by the E2E suite and intentionally ignored by Git.
