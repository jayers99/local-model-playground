# Future hardening

Items deliberately deferred from v1. Listed here so they aren't lost.

## Deferred from v1 scope

- `compare` command (run light + heavy profiles against the same input)
- Static Terraform checks (regex/keyword-based detection of `roles/editor`, `roles/owner`, `roles/viewer`, service-account-key resources)
- JSON output artifact (`review.json`) and a structured-output schema
- `gcp_tutor` prompt template + GCP concept-tutor workflow
- `acceptance_to_validation` prompt template + ticket-decomposition workflow
- `examples/tickets/` synthetic acceptance-criteria examples
- Light-profile end-to-end exercise + the lessons-learned comparison table
- Daemon-mode server lifecycle (currently per-invocation; revisit if cold-start UX hurts)

## Deferred hardening (from the original brief)

- Redaction and secret scanning
- Corporate data-handling rules
- Local log retention policy
- Prompt/output audit trail
- Policy-as-code integration
- Terraform `plan` JSON parsing
- Read-only GCP validation commands
- Approval workflow
- Threat model
- Enterprise packaging
- Internal model approval process
- Concurrent-invocation lock files / PID files
- Crashed-server recovery
- Retry on transient HTTP errors
- Model-output safety / redaction
