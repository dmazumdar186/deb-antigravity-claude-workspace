# YouTube Video Analyzer — Directive

## Goal

Take a YouTube URL and produce a structured markdown breakdown that captures the **visual storytelling** of the video — the hook, the cuts, the b-roll choices, the pacing — not just the transcript. The intended use is to study top creators: paste a URL, get a breakdown that pipes into an Obsidian vault for later reuse as content ideas.

## When to use

- User pastes a YouTube URL and asks to "analyze", "break down", "study", or "extract ideas from" the video.
- User says "I want to learn from this creator" with a video link.
- User asks for the "hook" or "structure" of a YouTube video they linked.

## Inputs

### CLI flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `url` (positional) | Yes | — | YouTube video URL (watch / youtu.be / shorts / embed) |
| `--tier` | No | `default` | `default` = latest Sonnet-equivalent (cheap); `premium` = latest Opus-equivalent (best quality); `gemini` = free URL-native via Gemini direct, or paid frame-grid via OR if no `GEMINI_API_KEY` |
| `--provider` | No | `auto` | `openrouter` / `anthropic` / `gemini-direct` / `auto`. Auto selects based on env vars (see Provider selection below). |
| `--model <exact-id>` | No | — | Escape hatch — bypass registry and use this exact model ID. Requires `--tier` to indicate which provider path to use (Claude or Gemini). |
| `--refresh-models` | No | false | Force the model registry to re-fetch from provider APIs (bypasses 7-day cache) |
| `--max-frames` | No | 24 | Cap on frames extracted before perceptual-hash dedup |
| `--obsidian-vault` | No | `OBSIDIAN_VAULT` env | Path to Obsidian vault root |
| `--dry-run` | No | false | Lightweight smoke check: skip all network calls and pipeline work, print planned configuration and would_* fields. Use this for canary monitoring. |
| `--deep-dry-run` | No | false | Run the full pipeline (download, scene detection, frame extraction, grid tiling) and print pipeline stats + cost estimate, BUT skip the actual AI API call. Useful for cost forecasting before a real run. |
| `--keep-source` | No | false | Don't delete the downloaded .mp4 |
| `--refresh-transcript` | No | false | Force a fresh transcript fetch from YouTube even if `transcript.txt` already exists in the work dir. |

### Env vars

- `OPENROUTER_API_KEY` — **preferred**. One key reaches Claude, Gemini, and GPT-4o vision via OpenRouter. Used for `--tier default` and `--tier premium`. Also used for `--tier gemini` if `GEMINI_API_KEY` is absent (paid frame-grid mode).
- `ANTHROPIC_API_KEY` — legacy fallback for `--tier default` and `--tier premium` when `OPENROUTER_API_KEY` is not set.
- `GEMINI_API_KEY` — required for the **free** URL-native `--tier gemini` path (Gemini reads YouTube directly, $0.00). Without it, `--tier gemini` falls back to OpenRouter (paid).
- `OBSIDIAN_VAULT` — optional. If set, breakdown is also written into `{vault}/Video Breakdowns/`

## Outputs

- `.tmp/video/{video_id}/breakdown.md` — always
- `.tmp/video/{video_id}/transcript.txt` — full transcript with timestamps (Claude path only)
- `.tmp/video/{video_id}/metadata.json` — title, channel, duration, etc.
- `.tmp/video/{video_id}/frames/*.jpg` — scene-change frames with timestamp overlays (Claude path only)
- `.tmp/video/{video_id}/grids/grid_*.jpg` — 3×3 tiled grid images sent to Claude (Claude path only)
- `{OBSIDIAN_VAULT}/Video Breakdowns/{YYYY-MM-DD}_{slug}.md` — if vault is set
- Source `.mp4` is deleted after analysis unless `--keep-source`

### Breakdown structure

```
# {Title}
**Channel:** ...
**Duration:** ...
**URL:** ...
**Analyzed:** ...
**Tier:** ...
**Frames processed:** N (after dedup)

## The Hook (0:00–0:15)
## Pacing & Cuts
## Visual Storytelling
## Transcript Highlights
## Content Ideas Inspired by This

## Full Transcript (collapsed)
```

## How to run

```bash
# Standard (latest Sonnet-equivalent, cheapest)
py execution/video/youtube_video_analyzer.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"

# Best quality (latest Opus-equivalent)
py execution/video/youtube_video_analyzer.py "URL" --tier premium

# Free path — no frame extraction, Gemini reads YouTube directly
py execution/video/youtube_video_analyzer.py "URL" --tier gemini

# Dry-run smoke test (no API call, no cost)
py execution/video/youtube_video_analyzer.py "URL" --dry-run

# Force registry refresh (adopt a newly-released model)
py execution/video/youtube_video_analyzer.py "URL" --refresh-models

# Escape hatch: exact model ID
py execution/video/youtube_video_analyzer.py "URL" --tier default --model claude-sonnet-4-7

# Override vault location
py execution/video/youtube_video_analyzer.py "URL" --obsidian-vault "C:\path\to\vault"
```

## Tools / dependencies

```
yt-dlp                    # YouTube download + metadata
youtube-transcript-api    # Captions
imageio-ffmpeg            # Bundled ffmpeg binary (no system install needed)
scenedetect               # PySceneDetect — scene detection (replaces ffmpeg filter)
imagehash                 # Perceptual hash dedup (dhash)
Pillow                    # Image compositing (timestamp overlays, grid tiling)
anthropic                 # Claude API (vision + tool-use)
google-genai              # Gemini API (free YouTube-URL path)
python-dotenv             # Env loading
```

Install: `py -m pip install yt-dlp youtube-transcript-api imageio-ffmpeg scenedetect imagehash Pillow anthropic google-genai`

## Pipeline

### Claude path (`--tier default` or `--tier premium`)

1. Resolve model ID at runtime via `execution/modules/model_registry.py` — no hardcoded IDs.
2. Extract video ID from URL (supports watch / youtu.be / shorts / embed / m.youtube.com)
3. **Transcript cache-first** — `get_or_fetch_transcript(video_id, work_dir)` checks `.tmp/video/{id}/transcript.txt` first. If it exists and is parseable, returns it without a network call (format: `[MM:SS] text` per line). On cache miss or empty file, fetches live via `youtube-transcript-api` and writes the cache file. Pass `force_refresh=True` to bypass cache. **Errors out cleanly if no captions exist.**
4. Download video at 360p via `yt-dlp` (low-res — vision model doesn't need 4K)
5. Get metadata: title, channel, duration, upload date
6. **Scene detection** via PySceneDetect `ContentDetector(threshold=27)` — far more accurate than ffmpeg's `select='gt(scene,X)'` filter, especially on tutorial/slide/screencast content. Falls back to fixed-interval (1 frame/10s) if 0 scenes detected.
7. **Frame extraction** — ffmpeg extracts one frame per scene timestamp, resized to 384×216, with `format=yuvj420p` fix.
8. **Perceptual-hash dedup** — `imagehash.dhash` removes near-identical frames (hamming distance < 6 from previous kept frame). Typically reduces ~24 raw frames to 18–23 distinct frames.
9. **Timestamp overlay** — PIL burns `MM:SS` text into each frame's top-left corner so Claude can reference timing.
10. **Grid tiling** — PIL composites up to 9 frames per 3×3 grid (1152×648 canvas). 24 frames → 3 grids. Claude receives 3 images instead of 24, cutting vision tokens ~85%.
11. **Claude analysis** — structured tool-use call forcing `submit_breakdown` exactly once. System message + tools block are marked with `cache_control: {type: "ephemeral"}` for prompt caching (0.1× cost on cache reads, 5-min TTL).
12. Write breakdown markdown + transcript to `.tmp/video/{id}/` and (if vault set) Obsidian vault.
13. Delete source .mp4 unless `--keep-source`.

### Gemini path (`--tier gemini`)

1. Resolve Gemini model ID at runtime via model registry.
2. Pass YouTube URL directly to `client.models.generate_content()` with a structured JSON prompt.
3. Gemini reads the video natively — no yt-dlp download, no ffmpeg, no frame extraction.
4. Parse JSON response into the same structured dict shape used by the Claude path.
5. Render breakdown markdown and write outputs.

## Dynamic model resolution

Model IDs are **never hardcoded** in `youtube_video_analyzer.py`. They are resolved at runtime via `execution/modules/model_registry.py`:

| Tier | Provider (auto) | Registry tier | Resolution logic |
|---|---|---|---|
| `default` | openrouter (if OR key set) | `openrouter/default` | Live `/api/v1/models`, allowlist+vision+tools filtered, prefers `anthropic/claude-sonnet-*` |
| `default` | anthropic (fallback) | `anthropic/default` | Latest sonnet-family model from `models.list()` |
| `premium` | openrouter (if OR key set) | `openrouter/premium` | Prefers `anthropic/claude-opus-*`, ladder: gpt-5, gpt-4o, gemini-3, gemini-2.5-pro, sonnet |
| `premium` | anthropic (fallback) | `anthropic/premium` | Latest opus-family model from `models.list()` |
| `gemini` | gemini-direct (if GEMINI key) | `gemini/default` | Latest flash-variant from `models.list()` — **$0.00 free** |
| `gemini` | openrouter (fallback, paid) | `openrouter/gemini` | Prefers `google/gemini-2.5-pro` — frame-grid mode, ~$0.02 |

### Provider selection (auto-detect)

When `--provider auto` (default), provider is chosen from env vars:

| Tier | Keys present | Provider chosen | Path |
|---|---|---|---|
| `default` / `premium` | `OPENROUTER_API_KEY` | `openrouter` | Preferred — one key |
| `default` / `premium` | `ANTHROPIC_API_KEY` (no OR key) | `anthropic` | Legacy direct |
| `gemini` | `GEMINI_API_KEY` | `gemini-direct` | **Free** URL-native |
| `gemini` | `OPENROUTER_API_KEY` (no Gemini key) | `openrouter` | Paid frame-grid mode |
| any | neither key | error | Clear message shown |

Use `--provider <explicit>` to override auto-detection (escape hatch).

### OpenRouter allowlist

`ALLOWED_FAMILIES = ("anthropic/", "openai/", "google/")` — enforced **before any other filter** in `_resolve_openrouter()`. Models outside these families (Llama, Grok, Mistral, DeepSeek, Qwen, etc.) are never considered regardless of recency or benchmarks. Edit this constant in `model_registry.py` to add/remove families.

### OpenRouter fee

OpenRouter adds a **5.5% platform fee** over direct-provider pricing. This is the cost of unified-key convenience. Use `ANTHROPIC_API_KEY` directly if you want to avoid the fee on Claude calls.

Resolution order:
1. Local cache at `.tmp/model_registry.json` (TTL: 7 days)
2. Live API query (OR: anonymous `GET /api/v1/models`; Anthropic/Gemini: authenticated `models.list()`)
3. Stale cache (if API fails)
4. `LAST_KNOWN_GOOD` literals in `model_registry.py` (absolute fallback)

The first run after cache expiry (or with `--refresh-models`) prints which model was resolved for each tier. When Anthropic releases a new Opus version, the next `--refresh-models` run automatically adopts it — zero code changes.

`--model <exact-id>` bypasses the registry entirely; useful for pinning to a specific version during testing.

## Cost expectations

| Tier | OR key only | OR + Gemini key | Anthropic direct (legacy) |
|---|---|---|---|
| v1 (old) | ~$0.30 | ~$0.30 | ~$0.30 |
| **`default`** | **~$0.032** (OR) | **~$0.032** (OR) | **~$0.030** |
| **`premium`** | **~$0.053** (OR) | **~$0.053** (OR) | **~$0.050** |
| **`gemini`** | **~$0.02** (OR frame-grid) | **$0.00** (direct URL-native) | n/a |

The 5.5% OR premium is the cost of unified-key convenience. Adding `GEMINI_API_KEY` on top of OR unlocks the **$0.00 free path** for the Gemini tier. Llama / Grok / Mistral are never picked — `ALLOWED_FAMILIES` enforces this in code.

Calculation: 3 grids × ~1400 tokens/grid (R3 calibrated: ~155 tokens/cell × 9 cells) → ~4.2k visual tokens + ~3.5k transcript ≈ ~8k input. Costs expressed as ranges — exact amounts shift with each model release but the architecture is unaffected.

**Always use `--deep-dry-run` first on unfamiliar long videos** to see real frame count, dedup result, grid count, and token estimate before paying. Use `--dry-run` for lightweight canary checks (no network calls, no pipeline work).

## Edge cases & gotchas

1. **No captions** — script exits 1 with clear message. Captions-only mode by design. To support caption-less videos, add local Whisper later.
2. **Age-restricted / private / region-blocked videos** — yt-dlp will raise; surface to user.
3. **Live streams** — refused (the script checks `is_live` / `was_live` flags).
4. **Very long videos (>1h)** — PySceneDetect may find 200+ scenes; capped to `--max-frames` (default 24) before extraction. Dedup reduces further. Cost stays flat.
5. **Spaces in workspace path (OneDrive)** — all paths use `pathlib.Path`, ffmpeg subprocess receives them as separate args (not shell-joined), so spaces are safe.
6. **YouTube API changes break yt-dlp periodically** — if download fails with a parser error, run `py -m pip install --upgrade yt-dlp` first.
7. **PySceneDetect finds 0 scenes on static-camera content** — script falls back to 1 frame / 10 sec automatically. Logged as WARNING.
8. **Non-English captions** — current language preference is `en, en-US, en-GB`. To extend, edit the `languages=` list in `fetch_transcript()`.
9. **Gemini path 429 (rate limited)** — Gemini free tier is 8h/day. Catch 429 errors and surface clearly; user can wait or switch to Claude path.
10. **Dedup too aggressive** — if important visual moments are being removed, lower `DEDUP_HASH_THRESHOLD` (e.g. to 4). If not aggressive enough (redundant frames remain), raise to 8.

## Self-anneal hooks

- If yt-dlp consistently fails on a class of URLs (e.g. shorts), check whether `--format` selector needs adjustment.
- If Claude returns truncated breakdowns, raise `CLAUDE_MAX_TOKENS`.
- If PySceneDetect is slow on very long videos, set `downscale_factor=2` in the `open_video()` call.
- If Claude does not call `submit_breakdown`, check that `tool_choice={"type": "tool", "name": "submit_breakdown"}` is set.
- If LAST_KNOWN_GOOD in model_registry.py shows stale model IDs in logs, update them.

## Changelog

- **2026-05-18** — v3: Added OpenRouter routing with strict `ALLOWED_FAMILIES = ("anthropic/", "openai/", "google/")` allowlist enforced before any other filter (Llama/Grok/Mistral never picked). One OR key now reaches Claude, Gemini, and GPT-4o vision via `--provider openrouter`. Added `_auto_detect_provider()` — prefers OR key over Anthropic key; prefers Gemini direct key for free URL-native path. Added `--provider {openrouter,anthropic,gemini-direct,auto}` flag. Added `analyze_with_openrouter()` using OpenAI-compatible SDK (`base_url=https://openrouter.ai/api/v1`). `--tier gemini` with OR key uses frame-grid mode (paid ~$0.02), not free URL-native — warning surfaced in logs. OR adds 5.5% platform fee vs direct. `OPENROUTER_API_KEY` added as preferred env var.
- **2026-05-18** — v2 refactor. Replaced ffmpeg scene-change filter with PySceneDetect ContentDetector. Added perceptual-hash dedup (imagehash.dhash). Added 3×3 grid tiling (24 frames → 3 grid images, ~85% vision token reduction). Rewrote Claude call as tool-use with forced `submit_breakdown` + prompt caching. Added dynamic model resolution via `model_registry.py` — no hardcoded model IDs. Added `--tier {default,premium,gemini}`, `--refresh-models`, `--model` (escape hatch). Default `--max-frames` dropped 60 → 24. Added Gemini free path (URL-native, no frame extraction). Cost: ~$0.03 default, ~$0.05 premium, $0.00 gemini (vs ~$0.30 in v1).
- **2026-05-18** — Initial build (v1). Captions-only mode, ffmpeg scene-change frames, hardcoded Sonnet model. Single-URL invocation.
