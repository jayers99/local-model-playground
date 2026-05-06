# Lessons learned

This file is filled in as v1 is exercised. After walking the manual smoke checklist (see `docs/superpowers/specs/2026-05-05-gcp-agent-playground-design.md` §7.2), record:

- Surprises during install or first run
- Cold-start time observed for the heavy profile
- Quality observations on the synthetic Terraform review
- Any flag/CLI shape changes in `mlx_lm.server` we had to work around
- Tasks the local model handled well vs. tasks where it underperformed

## Model-slug discovery saga (Task 1 follow-up)

The brief named `mlx-community/gemma-4-31b-it-4bit`. That slug **does** exist on Hugging Face but is multimodal (image-text-to-text) and requires `mlx_vlm`, not `mlx_lm.server`. The same trap exists across the whole `gemma-3-Nb-it-*` and `gemma-4-Nb-it-*` series: any `-it-` instruction-tuned slug without `text` in the name is multimodal.

Sequence we walked:

1. `mlx-community/gemma-2-27b-it-4bit` — text-only, `mlx_lm`-compatible, but the 4-bit weights are broken: `mlx_lm.generate` produces pure `<pad>` tokens for any prompt (verified by bypassing `mlx_lm.server` entirely). Avoid.
2. `mlx-community/gemma-2-9b-it-4bit` — smaller fallback we briefly switched to, but never tested live because we found a better Gemma 3 option.
3. `mlx-community/gemma-3-text-27b-it-4bit` — text-only Gemma 3 27B. Slug pattern `gemma-3-text-Nb-it-Mbit` is the explicit text-only sibling of the multimodal `gemma-3-Nb-it-Mbit`. Works with `mlx_lm.server`. A solid backup choice.
4. **Final landing: `mlx-community/gemma-4-31b-it-4bit` via `mlx_vlm.server`.** This is the slug from the original brief. It IS multimodal (image-text-to-text), but `mlx_vlm.server` exposes the same `/v1/chat/completions` OpenAI-compatible endpoint and accepts text-only requests fine. Adding a `server_binary` field to `Profile` (defaulting to `mlx_lm.server` for future text-only models, set to `mlx_vlm.server` on heavy) lets us drive both runtimes with the same harness. ~18.4 GB on disk.

Two more text-only Gemma options exist if needed:

- `mlx-community/gemma-3n-E4B-it-lm-4bit` — Gemma 3n architecture, ~7B effective params (smaller, faster).
- `mlx-community/gemma-3-1b-it-4bit` — tiny, would suit a future light profile.

Server flags actually exercised:

- `mlx_lm.server --use-default-chat-template` — we briefly added this when chat templates first looked off; turned out the underlying issue was the broken Gemma 2 27B 4-bit quant, not the template. Removed once we landed on `mlx_vlm.server`, which doesn't accept it. Default behavior (use the tokenizer's chat_template) is correct for any properly-quantized Gemma model.

Architectural takeaway: the `LLMClient` is a generic OpenAI SDK pointed at `base_url`, and both `mlx_lm.server` and `mlx_vlm.server` expose `/v1/chat/completions`. So the runtime choice is a pure server-binary swap — a single profile field (`server_binary`), no client code change. Worth remembering when other Apple-Silicon-native servers (e.g. `mlx-openai-server`, `vMLX`, etc.) come up: as long as they speak `/v1/chat/completions`, they slot in.

Workflow change forced by Gemma's chat template:

- Gemma's tokenizer chat template raises `'System role not supported'` if `messages[0].role == 'system'`. `workflows.py` was updated to merge the system prompt into the first user message (`_prepend_system`). This is permanent; Gemma 2/3/4 all share that constraint.

## Cold-start measurements (2026-05-05, M5 Max 128 GB, page cache hot)

Run via `uv run python scripts/bench_cold_start.py <profile>`, which times three phases against `time.monotonic()`:

- `listener_ready_s` — process start until `/v1/models` returns 200 (HTTP listener up)
- `first_token_s` — listener-ready until the first streamed chunk arrives (lazy model load + prefill of system prompt + first token)
- `full_response_s` — listener-ready until the response stream ends

| Profile | listener_ready | first_token | full_response | server binary    |
| ------- | -------------- | ----------- | ------------- | ---------------- |
| light   | 2.6 s          | 0.3 s       | 0.4 s         | `mlx_vlm.server` |
| wide    | 3.1 s          | 0.4 s       | 0.5 s         | `mlx_vlm.server` |
| code    | 0.5 s          | 2.0 s       | 2.2 s         | `mlx_lm.server`  |
| heavy   | 3.6 s          | 0.6 s       | 1.4 s         | `mlx_vlm.server` |
| x-heavy | 4.6 s          | 0.8 s       | 2.3 s         | `mlx_vlm.server` |
| arch    | 1.1 s          | 10.7 s      | 12.3 s        | `mlx_lm.server`  |

Two findings:

1. **`mlx_vlm.server` has a noticeably heavier import.** Listener-ready is consistently 2.6–4.6 s on the four `mlx_vlm.server` profiles vs. 0.5–1.1 s on the two `mlx_lm.server` profiles. Most of the time `lmp` looks "stuck" before the model loads, it's actually mlx_vlm pulling in vision-tower modules. Heavy uses mlx_vlm because gemma-4 is multimodal-shaped, but text-only profiles boot the listener ~3 s faster.
2. **arch (GLM-4.5-Air, 57 GB on disk) is the only profile where first-token cost is meaningful at hot cache** — 10.7 s. The smaller gemma-4 variants stay sub-second because the file pages are already mapped and the model is small enough that load + prefill happens almost instantly. Truly cold-after-reboot numbers will be much larger for any profile bigger than ~30 GB; budget for it before claiming arch/x-heavy are usable interactively.

Caveat: these are warm-disk, cold-process numbers. To reproduce a true cold start, run `sudo purge` (drops macOS file cache) before each invocation.

## Manual checklist (post-v1 features)

- [ ] `chat --include`: run `lmp chat --profile heavy --include examples/terraform/service-account-bad-editor.tf`, ask "what's wrong here?", confirm the model identifies `roles/editor` (proves the file content reached the model). Note any size-warning behavior for follow-up calibration.
