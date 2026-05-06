# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`gcp-agent-playground` is a learning POC, not production tooling. It exists to explore whether local Apple-Silicon MLX models can support lightweight advisory workflows (GCP/Terraform review, concept explanation, ticket decomposition). See `docs/idea.md` for the full brief and explicit non-goals.

**Synthetic inputs only.** Never feed real corporate data, real tickets, real project IDs, or secrets through this harness — the brief lists this as a hard constraint.

## Commands

```bash
uv sync                                                       # install deps
uv run gcp-agent chat --profile heavy                         # interactive REPL
uv run gcp-agent chat --profile heavy --include <file>        # prepend a file to the first message
uv run gcp-agent review --profile heavy <file>                # one-shot review → outputs/<ts>-review.md
uv run pytest                                                 # fast tests (no model)
uv run pytest tests/test_cli.py::test_chat_help_includes_include_flag   # single test
RUN_LIVE=1 uv run pytest -v                                   # also runs end-to-end smoke tests against a real local model
uv run hf download mlx-community/gemma-4-31b-it-4bit          # pre-pull a model (use `hf`, not the deprecated `huggingface-cli`)
```

Live tests in `tests/test_smoke.py` are gated by `RUN_LIVE=1` because they boot the heavy MLX model — slow and RAM-hungry. Default `pytest` skips them.

## Architecture

The CLI is a tight pipeline; understanding it is mostly about understanding how these five modules collaborate per command:

```
main.py (typer)
  └─ profiles.load(name)      → profiles/<name>.yaml → Profile (pydantic)
     └─ MLXServer(profile)    → spawns mlx_lm.server or mlx_vlm.server subprocess on profile.port
                                 polls /v1/models until ready; logs to outputs/.server-logs/
                                 stops on context-manager exit, atexit, SIGINT, SIGTERM
        └─ LLMClient(profile) → OpenAI SDK pointed at profile.base_url
           └─ workflows.chat / workflows.review
              └─ render.write_review_md (review only) → outputs/<ts>-review.md with metadata header
```

Key invariants:

- **Server lifecycle is bound to one CLI invocation.** Every command cold-starts the model server, runs, then stops. There is no daemon mode (yet — see `docs/backlog.md`). Cold-start time on heavy is the dominant UX cost.
- **Profiles are the single configuration surface.** Model slug, server binary (`mlx_lm.server` for text-only, `mlx_vlm.server` for multimodal), port, temperature, and max_tokens all live in `profiles/<name>.yaml`. The pydantic schema is in `src/gcp_agent_playground/profiles.py`.
- **All profiles share port 8080**, so you can only run one at a time. The `compare` command in the backlog will need to either serialize (stop heavy → start light) or assign distinct ports.
- **Gemma's chat template rejects the `system` role.** `mlx_lm.server` returns 404 `{"error": "System role not supported"}` if you send one. `workflows._prepend_system` works around this by merging `prompts/system.md` into the first user message. Don't add a system role anywhere — re-use that helper.
- **`--include` content is wrapped with explicit `BEGIN/END INCLUDED FILE` delimiters** before being prepended to the first user turn. See `workflows._build_first_user_message`. Encoding errors exit with code 2; large files (>64 KB) print a warning but don't block.
- **Working directory matters.** `prompts/`, `profiles/`, and `outputs/` are resolved relative to CWD, not the package install path. CLI must be invoked from the repo root. (Tracked as a low-priority backlog item.)

## Profile roster (gemma-4)

`docs/backlog.md` has the canonical model roster table. Quick reference:

| Profile  | Model                                       | RAM tier      |
| -------- | ------------------------------------------- | ------------- |
| light    | `mlx-community/gemma-4-e4b-it-4bit`         | 16 GB+        |
| wide     | `mlx-community/gemma-4-26b-a4b-it-4bit`     | 36–64 GB      |
| heavy    | `mlx-community/gemma-4-31b-it-4bit`         | 64–128 GB     |
| x-heavy  | `mlx-community/gemma-4-31b-it-8bit`         | 128 GB (tight)|

Heavy is the default in CLI commands. Light, wide, and x-heavy haven't been validated end-to-end yet.

## Where things live

- `src/gcp_agent_playground/` — five modules; see Architecture above
- `prompts/system.md`, `prompts/terraform_reviewer.md` — prompt templates (read at runtime)
- `examples/terraform/` — synthetic Terraform inputs for `review`
- `outputs/` — generated reviews + server logs (gitignored)
- `docs/backlog.md` — active feature queue with priorities and the model roster
- `notes/future-hardening.md` — deferred security/compliance work (do not move items from there to backlog without explicit decision)
- `notes/lessons-learned.md` — observations from live walks
- `docs/superpowers/specs/` and `docs/superpowers/plans/` — design spec and implementation plan
