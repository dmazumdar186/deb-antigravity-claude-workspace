# OpenRouter image generation

## Goal
Generate illustration or texture images (client sites, decks) with an image-output model through OpenRouter, safely: dry run by default, a hard budget cap per run, one ledger row per call.

## Tools/Scripts
`execution/image_generation/openrouter_image_gen.py`

## Inputs
- `--prompt "..."` or `--prompt-file PATH` (keep prompts in `.tmp/image_gen/*.txt`)
- `--n` images (1-8), `--name` file stem, `--out-dir` (default `.tmp/image_gen/`)
- `--model` (default `google/gemini-3-pro-image`; list image models free: `curl -s https://openrouter.ai/api/v1/models` and filter `architecture.output_modalities` containing `image`)
- `--budget-usd` run cap (default 1.00), `--est-usd` worst-case per image used by the cap (default 0.20)
- `--live` to spend; without it the run is a dry run that spends 0.00
- env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN`)

## Outputs
- `{out_dir}/{name}-{i}.png`
- `.tmp/image_gen_ledger.jsonl`: one row per call (`ts, model, name, i, cost_usd, secs, file, error`)
- stdout: per-image OK/FAIL with reported cost, total spend

## Steps
1. Write the prompt to a file; dry run to confirm model, count and worst-case cost.
2. `--live --n 2` (two candidates); a blind reviewer worker picks the best against the client's reference (images never enter the main session).
3. Post-process (cut-out, layers, WebP at native resolution, never upscale) in a separate script under `/tmp` or `execution/`.

## Edge Cases
- The model can return text instead of an image: logged as `FAIL no image` with the text snippet; the run continues.
- Backgrounds come back off-white (cream ~244,237,218 or white 253-255), not transparent: colour-key them out in post.
- Gemini 3 Pro Image returns ~1376-1408 x 768 for landscape prompts; ask for "high resolution" but do not upscale afterwards (AI-upscale look was rejected by the client 2026-11-14).
- Observed cost 2026-11-14: about $0.138 per image (`google/gemini-3-pro-image`), $0.23 per image (`openai/gpt-5.4-image-2`, 1024x1024).
- For client work, generate candidates from BOTH image providers (Google + OpenAI; Claude/GLM/Kimi have no image output) and let a blind reviewer rank anonymised copies. 2026-11-14 blind result: Gemini 3 Pro Image won both briefs (line-art Nataraja 9/10 vs OpenAI 8/10; parchment scroll 9/10 vs 7/10).
- A dropped connection mid-call is logged with cost 0.00 and the run continues.

## Output Contract
Images only in `.tmp/image_gen/`; nothing is published until a reviewed derivative is copied into a site's assets.
