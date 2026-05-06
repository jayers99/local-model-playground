# local-model-playground

Local agentic AI playground for synthetic GCP/Terraform advisory tasks. Runs MLX-hosted local models (Gemma 4, GLM-4.5-Air, Qwen3-Coder) on Apple Silicon and exposes a small `lmp` CLI for `chat` and `review` workflows.

This is a learning POC. Use fake/educational inputs only — see `docs/idea.md` for the full brief and non-goals.

## Quickstart (heavy profile, M5 Max 128 GB)

1. Install Python deps:

       uv sync

2. Pre-pull the MLX model declared in `profiles/heavy.yaml`:

       uv run hf download mlx-community/gemma-4-31b-it-4bit

   (`huggingface-cli` is deprecated as of `huggingface_hub` 1.13 — use `hf`.)

3. Chat:

       uv run lmp chat --profile heavy

   To put a file in front of the model up front (avoids the long-paste pitfall), use `--include`:

       uv run lmp chat --profile heavy --include examples/terraform/service-account-bad-editor.tf

4. Review the bundled example:

       uv run lmp review --profile heavy examples/terraform/service-account-bad-editor.tf

   The advisory Markdown lands in `outputs/<timestamp>-review.md`.

## Profiles

Six profiles ship in `profiles/`. All boot + single-turn-generated cleanly on a 128 GB M5 Max as of 2026-05-05. Pick by domain and machine size; see `docs/backlog.md` for the full roster (server binary, parameter counts, cold-start times).

| Profile  | Model                                                | RAM tier       | Best for                                                          |
| -------- | ---------------------------------------------------- | -------------- | ----------------------------------------------------------------- |
| light    | `mlx-community/gemma-4-e4b-it-4bit`                  | 16 GB+         | Fast iteration, concept Q&A, small Terraform review               |
| wide     | `mlx-community/gemma-4-26b-a4b-it-4bit`              | 36–64 GB       | Knowledge-broad MoE — speed of 4B with breadth of 26B             |
| code     | `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit`    | 36–64 GB       | Code review, scaffolding, refactor advice                         |
| heavy    | `mlx-community/gemma-4-31b-it-4bit` *(CLI default)*  | 64–128 GB      | Default deep synthesis — Terraform review, GCP reasoning          |
| arch     | `mlx-community/GLM-4.5-Air-4bit`                     | 96–128 GB      | Architecture / design reasoning — GCP solution shape, trade-offs  |
| x-heavy  | `mlx-community/gemma-4-31b-it-8bit`                  | 128 GB (tight) | Same 31B as heavy at 8-bit for max-fidelity synthesis             |

Pre-pull any of them with `uv run hf download <slug>`. Profiles share port 8080, so only one runs at a time.

## Layout

- `docs/idea.md` — the original POC brief
- `docs/superpowers/specs/` — design spec
- `docs/superpowers/plans/` — implementation plan
- `profiles/` — per-machine MLX runtime profiles
- `prompts/` — system + workflow prompt templates
- `examples/` — synthetic inputs
- `src/local_model_playground/` — the CLI implementation
- `outputs/` — generated reviews (gitignored)
- `notes/future-hardening.md` — deferred work
- `notes/lessons-learned.md` — observations

## What's not here yet

See `docs/backlog.md` for the active feature queue and `notes/future-hardening.md` for deferred security/compliance work. Notably: no `compare` command, no static Terraform pre-checks, no JSON output artifact, no daemon-mode server.
