# Backlog

Forward work for `gcp-agent-playground` after v1. Use checkboxes; mark items done as they land.

For the deferred-hardening register (corporate data handling, audit trail, redaction, etc.), see `notes/future-hardening.md` instead — that file is the long-tail security/compliance ledger; this file is the active feature queue.

## v1 close-out (priority:high)

- [ ] Capture live-walk observations in `notes/lessons-learned.md`:
  - Heavy-profile cold-start time (server `/v1/models` 200 → first token of an actual response)
  - Quality of the review of `service-account-bad-editor.tf` (does it find `roles/editor`? validation evidence reasonable? open questions sensible?)
  - The "haywire on long paste in `chat`" observation — what happened, how long the pasted content was
  - Any flag/CLI shape mismatches we worked around
- [ ] Commit + push the lessons-learned update.

## Feature backlog

### priority:high

- [ ] **`compare` command.** Run two profiles against the same input, emit a side-by-side `outputs/<ts>-comparison.md` (and a metadata header with both model slugs). Most directly tests the brief's thesis (small-vs-large local model behavior).
  - Sub-task: define a second working profile (light) — pick a small text-only mlx_lm-compatible model, e.g. `mlx-community/gemma-3-1b-it-4bit` or `mlx-community/gemma-3n-E4B-it-lm-4bit`, validate it boots, store the slug in `profiles/light.yaml`.
  - Sub-task: serialize: stop heavy server → start light server → run → stop → optional restart heavy. Or: use distinct ports to run both concurrently if RAM allows.
- [ ] **`chat --include <path>`** flag. Read a file, prepend it (with a clear delimiter) to the first user message of the REPL session. Closes the "I tried to paste a file and it went haywire" gap directly.

### priority:medium

- [ ] **JSON output artifact** for `review`. Add `review.json` alongside `review.md`, with a pydantic schema for findings (issue, why, suggested change, confidence) plus the four required-section presence flags. Sets us up for later programmatic consumers.
- [ ] **Static Terraform checks** as a deterministic pre-pass. Regex/keyword detection of:
  - `roles/editor`, `roles/owner`, `roles/viewer`
  - `google_service_account_key` resources
  - Public bucket / public IAM (`allUsers`, `allAuthenticatedUsers`)
  Run before the model and surface findings in the prompt as "deterministic findings" the model is asked to confirm/expand.
- [ ] **Second prompt template + example.** `prompts/acceptance_to_validation.md` plus `examples/tickets/service-account.md`. Exercises the ticket-decomposition workflow shape from the brief.

### priority:low

- [ ] **`gcp_tutor` prompt** + a third workflow command (`tutor` or expose via `chat --topic <slug>`). Concept-explanation mode.
- [ ] **More synthetic examples.** `service-account-good.tf`, `service-account-key-bad.tf`, `storage-bucket.md`, `workload-identity.md` to exercise the harness across more shapes.
- [ ] **Daemon-mode server** (`gcp-agent server start|stop|status`). Eliminates per-invocation cold-start. Only worth doing if the per-invocation UX hurts in practice.
- [ ] **`pyproject.toml` testpaths.** Add `[tool.pytest.ini_options] testpaths = ["tests"]` so `uv run pytest` finds tests without relying on autodiscovery.
- [ ] **Distinct exit codes for port-conflict (4) and connection-drop (5).** Currently both collapse into the general `ServerError` path (exit 3); spec §6 asks for them separated. Connection-drop also needs an explicit catch on `openai.APIError` to avoid a traceback.
- [ ] **CWD independence.** Resolve `prompts/`, `profiles/`, `outputs/` relative to either the package install location or a `--repo-root` option, so `gcp-agent` can run from anywhere.
- [ ] **Logfile fd cleanup** in `MLXServer.start` — close the parent-side fd after `Popen` returns successfully so we don't hold it open for the lifetime of the CLI invocation.

## Out-of-scope-but-recorded

The deferred-hardening items from the original brief (redaction, secret scanning, audit trail, policy-as-code, threat model, enterprise packaging, etc.) live in `notes/future-hardening.md`. Don't move them here unless we decide one is actually about to be worked on.
