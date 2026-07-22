# Safety model

1. Consent precedes processing and external calls receive masked text.
2. Versioned deterministic red-flag rules run before generative logic and after every answer.
3. `Routine` and `Self-Care` require exact triage/critic agreement, retrieval quality at least 0.70, uncertainty at most 0.25, and no critical missing facts.
4. Red flags, disagreement, timeout, parse failure, missing facts, weak retrieval, or high uncertainty create a durable human escalation.
5. Only the supervisor safety gate can produce patient-facing guidance; individual A2A agents cannot.
6. Every SOAP sentence has provenance. Unsupported sections say they are incomplete.

This is synthetic demonstration logic and has not been clinically validated.

