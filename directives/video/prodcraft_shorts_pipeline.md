# ProdCraft Long-form -> Vertical Shorts Pipeline (skeleton stub)

> **Status: stub directive.** Skeleton not implemented yet. Captured 2026-06-25 as part of the 12-AI-tools backlog (see `docs/ideas/12_ai_tools_money_makers_2026-06-25.md` shortlist #2 — the OpusClip-style extension of ProdCraft). Pick up when the operator wants to repurpose his own ProdCraft long-forms into TikTok / Reels / Shorts, OR when a creator client asks for "clipping as a service."

## Goal

Take a single long-form video (podcast, talk, interview, ProdCraft Living-PRD render) → output 5-10 captioned vertical 9:16 shorts ready to post. No new model spend — combines already-shipped workspace components.

## The already-shipped components

| Component | File | Role |
|-----------|------|------|
| Scene-cut detection | already used in `youtube_video_analyzer.py` (PySceneDetect) | Find the natural cut boundaries |
| Word-level transcription | `execution/personal_workflows/prodcraft_transcribe.py` | Whisper -> aligned word timings for captions |
| Beat / interesting-moment scoring | `execution/personal_workflows/prodcraft_beats.py` | Gemini scores each segment for "would this work as a hook?" |
| Vertical caption rendering | `execution/video/remotion-projects/prodcraft_smoke/src/Captions.tsx` | Already does 9:16 caption animation |
| Render orchestration | `execution/video/prodcraft_render.py` | ffmpeg + Remotion-CLI integration |

## Steps when implementing

1. New script `execution/video/prodcraft_shorts_pipeline.py`:
   - `--input <video>` (path or YouTube URL — leverage existing yt-dlp wrapper).
   - PySceneDetect to find boundaries.
   - Transcribe with `prodcraft_transcribe`.
   - Score each scene with `prodcraft_beats` (or a new lighter scorer if `beats` is too heavy).
   - Top-N candidates -> for each: crop to 9:16 (center crop OR auto-track-face if cv2 face detect is cheap), burn captions via the existing Remotion comp.
   - Output: `.tmp/shorts/{video-slug}/short_{n}.mp4` × N.
2. Write directive with full Goal / Inputs / Tools / Outputs / Steps / Edge Cases sections.
3. `tests/front_door_prodcraft_shorts.sh`: fixture is a ~60s clip + assert ≥3 shorts produced + each is < 60s + each has the captions track.

## Why this is a stub today

ProdCraft is the operator's own product. The shorts pipeline is most useful AFTER ProdCraft's first long-form rendered and posted — which is still ahead of us in the autopilot directive. Implement after the first ProdCraft long-form ships.

## Honest gaps

- No face-tracking crop yet (center-crop loses face when the speaker moves).
- `prodcraft_beats` runs on Gemini and may rate-limit on a long video with many segments — needs batching / a cheaper local scorer (silence-gap detector?) as a fallback.
- No automatic post-to-TikTok / Reels / Shorts — output is local .mp4 only. Posting requires per-platform OAuth which is its own engagement.
- No "clipping as a service" billing flow — that's an Instantly + Stripe build for later.
