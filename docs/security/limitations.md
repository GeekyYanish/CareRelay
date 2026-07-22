# Security and clinical limitations

- This is a hackathon prototype with production-oriented deployment controls, not a medically validated production clinical system. The rules, thresholds, guideline corpus, and urgency outputs require formal clinical governance before any real use.
- Demo JWTs use a shared symmetric secret and local account seed. Production requires managed identity, secret rotation, revocation, MFA for privileged roles, and short sessions.
- PHI masking uses common regex patterns and is not a complete de-identification system. Production requires validated DLP, explicit data residency, provider agreements, and leak testing.
- PostgreSQL tenant filters are repository-enforced, not database row-level security. Production should add RLS and independent authorization tests.
- The hash chain exposes tampering but is not externally anchored. Production should sign or anchor audit checkpoints in immutable storage.
- The WebSocket transport currently emits a scoped snapshot then closes. Production fan-out needs Redis subscription consumers, backpressure, and reconnect cursors.
- Google Cloud MCP summaries are sanitized and read-only by allowlist, but production must also enforce the documented organization policy and minimum IAM roles.
- The Lyzr SuperFlow adapter is fully wired through execute, status polling, output validation, readiness, auditing, and fail-closed handling. It still requires a credentialed smoke test against the team's deployed workflow and a provider data-processing/governance review. Gemini, Google ADK/A2A bridging, and Google Cloud MCP likewise require credentialed verification.
- There is deliberately no EHR write-back, diagnosis, prescribing, treatment-plan generation, or chain-of-thought storage/display.
