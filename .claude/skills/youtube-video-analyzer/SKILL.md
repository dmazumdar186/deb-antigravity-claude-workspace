---
name: youtube-video-analyzer
description: |
  Extract a frame-by-frame breakdown of any YouTube video — the hook, the
  cuts, the visual storytelling, the pacing, transcript highlights, and
  content ideas. Goes beyond plain transcripts by using PySceneDetect to find
  real scene cuts, deduplicating near-identical frames, tiling them into
  compact 3×3 grids, and analyzing with Claude's vision via tool-use — or
  passing the URL directly to Gemini for a completely free run.
  Use whenever the user pastes a YouTube URL and asks to "analyze", "break
  down", "study", or "extract ideas from" the video. Also triggers on "what's
  the hook in this video", "how is this video structured", or any request to
  learn from a specific YouTube creator with a link attached.
---

# YouTube Video Analyzer

When invoked, run the analyzer script and surface the breakdown to the user.

## Step 1 — Capture the URL

The user will typically paste a YouTube URL. Validate that it matches one of:
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- `https://www.youtube.com/shorts/...`
- `https://m.youtube.com/watch?v=...`

If the URL is missing or invalid, ask the user for a valid YouTube URL.

## Setup (env vars)

**Simplest setup**: paste `OPENROUTER_API_KEY` into `.env` — one key reaches Claude, Gemini, and GPT-4o vision via OpenRouter. The script auto-detects it and routes accordingly. Add `GEMINI_API_KEY` on top to unlock the **$0.00 free** URL-native Gemini path for `--tier gemini` (otherwise that tier falls back to paid frame-grid mode via OR). `ANTHROPIC_API_KEY` still works as a legacy fallback if you don't have an OR key.

**Dependencies:**
```
pip install yt-dlp youtube-transcript-api imageio-ffmpeg scenedetect imagehash Pillow anthropic google-genai openai
```

## Step 2 — Choose a tier

Three tiers are available:

| Tier | Flag | Cost | When to use |
|---|---|---|---|
| **default** | `--tier default` (or omit) | ~$0.03/video | Standard quality, cheapest Claude path |
| **premium** | `--tier premium` | ~$0.05/video | Best quality — richer visual analysis, more nuanced pacing notes |
| **gemini** | `--tier gemini` | **$0.00** | Free. Gemini reads the YouTube URL natively — no frame extraction needed. Use when user wants zero spend or to compare outputs. |

If the user hasn't specified, default to `--tier default` for most videos. Suggest `--tier gemini` when the user mentions cost or wants a quick free check. Suggest `--tier premium` when deep visual analysis or a long-form video warrants it.

Model IDs are resolved at runtime from the provider's model list — no specific version is hardcoded. The script will log which model it picked. Use `--refresh-models` to force a re-fetch (e.g. when you want to ensure a newly-released model version is adopted).

## Step 3 — Optional dry-run check

Two dry-run modes are available:

- **`--dry-run`** (shallow): No network calls, no pipeline work. Prints planned config + `would_*` fields + estimated cost immediately. Use this for canary monitoring or a quick sanity check.
- **`--deep-dry-run`** (full pipeline, no AI call): Downloads the video, runs PySceneDetect, extracts and deduplicates frames, tiles grids, then prints real frame count, dedup count, grid count, and a calibrated token/cost estimate — but skips the AI API call. Use this for accurate cost forecasting before a paid run.
- **`--refresh-transcript`**: Force a fresh transcript fetch from YouTube even if a cached `transcript.txt` exists in the work dir. Pass this when the cached transcript looks stale or truncated.

For unfamiliar long videos, run with `--deep-dry-run` first to see real frame/grid counts and an accurate token estimate. Print the JSON output and ask the user if they want to proceed with the paid call.

```
py execution/video/youtube_video_analyzer.py "<URL>" --deep-dry-run
```

Use `--dry-run` (not `--deep-dry-run`) for automated canary checks — it returns immediately with no network calls.

Skip the dry-run step if the user has already confirmed they want a full analysis, or if the video is short (under 5 min).

## Step 4 — Run the full analysis

```bash
# Default tier (cheapest Claude path)
py execution/video/youtube_video_analyzer.py "<URL>"

# Premium tier (best-quality Claude path)
py execution/video/youtube_video_analyzer.py "<URL>" --tier premium

# Free Gemini path
py execution/video/youtube_video_analyzer.py "<URL>" --tier gemini

# Batch mode — analyze multiple videos in one command (free Gemini path)
py execution/video/youtube_video_analyzer.py URL1 URL2 URL3 --tier gemini

# Batch from a file (one URL per line, # comments skipped)
py execution/video/youtube_video_analyzer.py --urls-file my_videos.txt --tier gemini

# Force model registry refresh
py execution/video/youtube_video_analyzer.py "<URL>" --refresh-models

# Keep the downloaded .mp4 after analysis (useful for debugging)
py execution/video/youtube_video_analyzer.py "<URL>" --keep-source
```

The Claude path will:
1. Fetch captions (errors out if none exist — captions-only mode)
2. Download the video at 360p
3. Detect scene cuts via PySceneDetect (more accurate than ffmpeg filter)
4. Extract frames, dedup via perceptual hash, burn timestamp overlays
5. Tile into 3×3 grid images (~3 grids for a 14-min video)
6. Send grids + transcript to Claude via tool-use (forced `submit_breakdown` call) with prompt caching
7. Write the breakdown to `.tmp/video/{video_id}/breakdown.md` and (if `OBSIDIAN_VAULT` env is set) into the user's Obsidian vault under `Video Breakdowns/`

The Gemini path skips steps 2–5 entirely — Gemini reads the YouTube URL natively.

## Step 5 — Read the breakdown and surface it

After the script finishes, read the `.tmp/video/{video_id}/breakdown.md` file and present the breakdown to the user. Highlight the path so the user can find the file. If it was also written to their Obsidian vault, mention that.

The breakdown now leads with **## Summary** (3-5 sentence prose overview of what the video says) and **## Key Takeaways** (1-7 synthesized content bullets) before the craft sections (The Hook, Pacing & Cuts, etc.). Surface the summary + takeaways first when presenting to the user — they answer "what does this video say" before "how was it made".

## Creator-profile cache (v4)

If you analyze 3 or more videos from the same channel, a creator-style profile builds automatically. After the third video, the analyzer runs a distillation pass (using Gemini free tier by default) to synthesize recurring patterns — hook styles, pacing, visual style, common topics — into a compact profile stored at `.tmp/creator_profiles/{channel_id}.json`.

Subsequent breakdowns from that channel automatically receive this context: the analysis prompt is pre-loaded with past observations so the breakdown can note where the new video follows or diverges from the creator's established patterns.

The profile updates every 5 additional videos (threshold: 3, 8, 13, …). Use `--refresh-creator-profile` to force re-distillation immediately. Use `--show-creator-profile "UCxxx" --no-analyze` to inspect the current profile. Use `--no-creator-profile` to skip profile features for a single run.

## When NOT to use this skill

- Non-YouTube URLs (TikTok, Instagram — not supported)
- Videos without captions (Claude path will error out; warn user up front; suggest Gemini path as it doesn't rely on captions)
- Live streams (script refuses)

## Common follow-up tasks

After producing a breakdown the user may want to:
- Compare against a previous breakdown — read both .md files and contrast
- Build a "hooks library" — aggregate the **The Hook** section across many breakdowns into one master file
- Generate scripts inspired by a creator's style — pass the breakdown back to Claude with a "write me a 60-second video script in this style" prompt
- Compare Claude vs Gemini output on the same video — run both tiers and diff

## Cost

| Tier | Typical cost per video |
|---|---|
| `--tier default` (latest Sonnet-equivalent) | ~$0.03 |
| `--tier premium` (latest Opus-equivalent) | ~$0.05 |
| `--tier gemini` (latest Gemini Flash, free tier) | $0.00 |

v2 is ~10× cheaper than v1 thanks to PySceneDetect, perceptual-hash dedup, and 3×3 grid tiling (which reduces vision tokens ~85%). The script prints token usage after each run. Always `--deep-dry-run` first on unfamiliar long videos for an accurate cost forecast; use `--dry-run` for lightweight canary checks.
