# gcp-agent-playground

Local agentic AI playground for synthetic GCP/Terraform advisory tasks. Runs a local MLX-hosted Gemma model on Apple Silicon and exposes a small `gcp-agent` CLI for `chat` and `review` workflows.

This is a learning POC. Use fake/educational inputs only — see `docs/idea.md` for the full brief and non-goals.

## Quickstart (heavy profile, M5 Max 128 GB)

1. Install Python deps:

       uv sync

2. Pre-pull the MLX model declared in `profiles/heavy.yaml`:

       uv run hf download mlx-community/gemma-2-27b-it-4bit

   (`huggingface-cli` is deprecated as of `huggingface_hub` 1.13 — use `hf`.)

3. Chat:

       uv run gcp-agent chat --profile heavy

4. Review the bundled example:

       uv run gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf

   The advisory Markdown lands in `outputs/<timestamp>-review.md`.

## Layout

- `docs/idea.md` — the original POC brief
- `docs/superpowers/specs/` — design spec
- `docs/superpowers/plans/` — implementation plan
- `profiles/` — per-machine MLX runtime profiles
- `prompts/` — system + workflow prompt templates
- `examples/` — synthetic inputs
- `src/gcp_agent_playground/` — the CLI implementation
- `outputs/` — generated reviews (gitignored)
- `notes/future-hardening.md` — deferred work
- `notes/lessons-learned.md` — observations

## What's not here yet

See `notes/future-hardening.md`. Notably: no `compare` command, no static checks, no JSON output, no light-profile validation in v1.
