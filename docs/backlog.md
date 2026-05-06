# Backlog

Forward work for `gcp-agent-playground` after v1. Use checkboxes; mark items done as they land.

For the deferred-hardening register (corporate data handling, audit trail, redaction, etc.), see `notes/future-hardening.md` instead — that file is the long-tail security/compliance ledger; this file is the active feature queue.

## Model roster

Reference table for the profile work below. RAM tiers are rough working-set estimates for the listed server binary; add headroom for OS + other apps. The gemma-4 variants ship multimodal-shaped weights so they need `mlx_vlm.server`; GLM-4.5-Air and Qwen3-Coder are text-only and use `mlx_lm.server`.

| Profile  | Model slug                                            | Server           | Params (active)          | MacBook RAM    | Purpose                                                                                                  |
| -------- | ----------------------------------------------------- | ---------------- | ------------------------ | -------------- | -------------------------------------------------------------------------------------------------------- |
| light    | `mlx-community/gemma-4-e4b-it-4bit`                   | `mlx_vlm.server` | ~4B                      | 16 GB+         | Fast iteration, concept explanation, small Terraform review.                                             |
| wide     | `mlx-community/gemma-4-26b-a4b-it-4bit`               | `mlx_vlm.server` | 26B total / ~4B active   | 36–64 GB       | MoE — 4B-class compute speed with 26B-breadth knowledge. Middle tier when latency matters more than depth.|
| code     | `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit`     | `mlx_lm.server`  | 30B total / 3B active    | 36–64 GB       | Coding-specialized MoE — code review, scaffolding, refactor advice.                                      |
| heavy    | `mlx-community/gemma-4-31b-it-4bit`                   | `mlx_vlm.server` | 31B                      | 64–128 GB      | Default deep-synthesis tier — Terraform review, GCP reasoning. Currently in `profiles/heavy.yaml`.       |
| arch     | `mlx-community/GLM-4.5-Air-4bit`                      | `mlx_lm.server`  | 106B total / 12B active  | 96–128 GB      | Architecture / design reasoning — GCP solution shape, trade-offs, system decomposition.                  |
| x-heavy  | `mlx-community/gemma-4-31b-it-8bit`                   | `mlx_vlm.server` | 31B                      | 128 GB (tight) | Same 31B as heavy at 8-bit for max-fidelity local synthesis. Slowest tokens/sec, biggest cold-start.     |

## v1 close-out (priority:high)

- [ ] Capture live-walk observations in `notes/lessons-learned.md`:
  - Heavy-profile cold-start time (server `/v1/models` 200 → first token of an actual response)
  - Quality of the review of `service-account-bad-editor.tf` (does it find `roles/editor`? validation evidence reasonable? open questions sensible?)
  - The "haywire on long paste in `chat`" observation — what happened, how long the pasted content was
  - Any flag/CLI shape mismatches we worked around
- [ ] Commit + push the lessons-learned update.

## Feature backlog

### priority:high

- [ ] **`compare` command.** Run two profiles against the same input, emit a side-by-side `outputs/<ts>-comparison.md` (and a metadata header with both model slugs). Most directly tests the brief's thesis (small-vs-large local model behavior). Heavy is `mlx-community/gemma-4-31b-it-4bit` (in use); pair it with a light tier for fast iteration and an x-heavy tier for max-fidelity runs.
  - [x] Sub-task: define a second working profile (light) — `mlx-community/gemma-4-e4b-it-4bit` (~2B "Edge 4B" variant, comfortably fits a 36 GB MacBook), validated boot + single-turn generation 2026-05-05. Note: e4b ships multimodal-shaped weights, so light uses `mlx_vlm.server` (text-only `mlx_lm.server` loads the listener but crashes on first generation).
  - Sub-task: define an x-heavy profile — `mlx-community/gemma-4-31b-it-8bit` (same 31B model at 8-bit for higher-fidelity local synthesis; gemma-4 tops out at 31B params, so the next tier up is precision, not size). Store in `profiles/x-heavy.yaml`. Expect bigger RAM footprint and slower tokens/sec than heavy.
  - Sub-task: serialize: stop heavy server → start light server → run → stop → optional restart heavy. Or: use distinct ports to run both concurrently if RAM allows.
- [x] **`chat --include <path>`** flag. Read a file, prepend it (with a clear delimiter) to the first user message of the REPL session. Closes the "I tried to paste a file and it went haywire" gap directly.

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
