# prodcraft_autopilot

End-to-end pipeline for ProdCraft (@ProdCraft) — generate a publishable YouTube video from a topic prompt. Phase 1 produces a watchable MP4 with cloned voice + Living PRD visual; Phases 2-6 add approval gating, upload, scheduling, and FR variants.

## Prior art pass (2026-06-18, retroactively recorded per `~/.claude/rules/prior-art-first.md`)

The rule landed 2026-06-18 morning. This directive's first commit (e420344) was earlier the same day, so the pass is recorded here retroactively from what the work actually did. Future revisions must keep this section current.

- **Public API status (per external service):**
  - **Google Gemini API (script generation):** YES, public, free tier. Used directly.
  - **Hugging Face Spaces (TTS):** YES, public (`ResembleAI/Chatterbox`). Used via `gradio_client`. Free ZeroGPU quota.
  - **Modal (TTS fallback):** Serverless deployment, not third-party.
  - **Pexels (b-roll):** Public REST API + free key. Used directly.
  - **YouTube transcripts:** `youtube_transcript_api` OSS library wrapping YouTube's public transcript endpoints.
  - **Remotion:** Local Node toolchain.
- **Best existing OSS approach for the pipeline shape:** No public OSS combines voice-clone + Living-PRD doc-as-teacher visual + free-tier-only. This pipeline is novel.
- **Why no workaround anti-pattern present:** every external integration uses a documented public API or established OSS wrapper. F5-TTS quality issues are a model-quality problem, not a prior-art gap (Chatterbox is the prior-art-recommended path).
- **Recommended architecture (current):** Gemini script-gen → ChatterboxTTS (HF Space → Modal fallback) → faster-whisper word timings → Remotion (Living PRD).

## Goal

Given a topic and a creator profile, autonomously produce a 2-5 minute educational YouTube video that:
- Speaks in the creator's cloned voice
- Shows an animated document being built in lock-step with the narration (the "Living PRD" visual — the document IS the teacher, not decoration)
- Renders to publishable 1080p30 MP4
- Costs near $0 per run

## Inputs

- **Topic** — one-liner ("How to write a PRD")
- **Creator profile** — `.tmp/prodcraft/voice_profile.json` distilled from past videos
- **Voice sample** — `.tmp/prodcraft/voice_sample/voice_sample.wav` (5-10s reference clip + transcript)
- **Existing video transcripts** (optional) — `.tmp/prodcraft/videos/*.json`

## Outputs

- Final MP4 — `.tmp/prodcraft/phase1_final.mp4`
- Intermediate artifacts — script .md, audio .wav, word timings .json, doc-ops plan .json, Remotion-staged assets
- Cost log — surfaced in console + Modal/HF usage trackers

## Pipeline (Phase 1)

```
topic
  → execution/personal_workflows/prodcraft_script_gen.py   # Gemini, free
  → execution/personal_workflows/prodcraft_voice_clone.py  # F5-TTS or Chatterbox via HF Space OR Modal
  → execution/personal_workflows/prodcraft_transcribe.py   # local faster-whisper (small.en)
  → execution/video/prodcraft_living_prd_plan.py           # hand-authored or Gemini-generated doc-ops plan
  → execution/video/prodcraft_render_living_prd.py         # Remotion: stages assets + renders MP4
```

## TTS — the painful learnings

TTS quality + cost was the entire bottleneck. Models tried and ranked, with 2026-06-19 update after `[[no-paid-tts]]` + HF Zero-GPU quota math:

| Model / Provider | Voice clone? | Quality | Cost / Quota math | Status |
|---|---|---|---|---|
| **Gemini Native TTS** (`gemini-2.5-flash-preview-tts`) | NO (30 prebuilt voices: Orus/Charon/Kore/...) | Excellent prosody + in-prompt style instructions for cadence control | $0 (free 250 RPD, 10 RPM). Single 8K-token call handles entire 3-minute script in one API hit (~55s wall-clock). | **Use this for now** — operator approved Orus on 2026-06-19 |
| ChatterboxTTS via HF Space (`ResembleAI/Chatterbox`) | YES | Best free clone option for voice fidelity | **Structurally infeasible at $0 for full scripts.** Space requests 90s GPU per call vs 300s/day cap → 3 chunks/day → 33-chunk script = 11 days. | Defer until HF PRO ($9/mo) is in budget |
| ChatterboxTTS via Modal (own deployment) | YES | Same model, no quota | ~$0.08/video on A10G. Operator's Modal workspace hit spend-cap as of 2026-06-17. | Blocked on Modal billing |
| F5-TTS via HF Space (`mrfakename/E2-F5-TTS`) | YES | Reference-bleeding + word-scrambling on long-form. Same 60s/call GPU request as Chatterbox. | $0 if quota available, but same daily cap math. | **Do not use** — burned hours on this |
| ElevenLabs | Cloned via paid plan | Best paid quality | $5+/mo | Out of budget |

### F5-TTS failure modes (avoid)
- **Reference bleeding**: if ref text ends mid-sentence (e.g. "...wouldn't give"), F5 inserts that phrase into generated output. *Fix*: trim ref to end at a sentence boundary.
- **Word scrambling on long generations**: ~700+ chars in one call → "drugs purpose", "clinical suit powders". *Fix*: chunk by paragraph (helps) or sentence (best).
- **Reference-too-long bleed**: 9-10s reference more prone to bleeding than 5-6s. But 5s ref → poor cadence model. **Sweet spot is 7-8 seconds with a complete sentence end.**
- **Cascaded atempo = drunk sound**: never apply ffmpeg atempo on top of TTS speed param. Use one OR the other.

### Chatterbox usage (reference; not the active path)
- Free path: gradio_client → `ResembleAI/Chatterbox` HF Space → `/generate_tts_audio` endpoint
- Per-call limit: ~10s audio per call (~300 char text). MUST chunk by sentence.
- Pause padding between sentences: 250-400ms.
- Optimal exaggeration: 0.5 (neutral). Higher = more dramatic (avoid for educational).
- **Quota wall**: HF free Zero-GPU charges the Space's REQUESTED GPU allocation (90s), not actual usage. 300s/day daily cap → 3 calls/day → infeasible for >3-chunk scripts.

### Gemini Native TTS usage (active path, 2026-06-19)
- API: `from google import genai; client = genai.Client(api_key=GEMINI_API_KEY)`
- Model: `gemini-2.5-flash-preview-tts` (2.5-pro variant available for higher quality, same free tier)
- Endpoint: `client.models.generate_content(model=..., contents=..., config=GenerateContentConfig(response_modalities=["AUDIO"], speech_config=SpeechConfig(voice_config=VoiceConfig(prebuilt_voice_config=PrebuiltVoiceConfig(voice_name="Orus")))))`
- Free tier: 250 RPD, 10 RPM. 3-minute script = 1 API call.
- Output: raw PCM s16le mono at 24kHz → wrap in WAV header before passing downstream
- **Cadence lever (critical for the "no breath" complaint)**: prepend a natural-language style instruction to the text. Default for ProdCraft: `"Read this in a warm, conversational tone, like explaining to a curious learner. Pause naturally at punctuation and take breath between sentences."` Override via `--gemini-style "your instruction"`.
- Voice selection (top 3 sampled 2026-06-19): **Orus** (calm, professional, current pick), Charon (deep, authoritative), Kore (warm, friendly). 27 more available.
- Hardening in `prodcraft_voice_clone.py`: deterministic per-chunk cache keyed on sha256(text + voice + style + model) → resumable across runs; retry-with-backoff 5s/20s/80s on transient API errors.

## Voice sample (reference clip)

`prodcraft_voice_sample.py` extracts a 6-10s window from a public ProdCraft YouTube video.

**Constraints for a good reference**:
- 6-10 seconds (sweet spot 7-8s)
- Must END at a sentence boundary (ref-bleed prevention)
- Voice characteristics consistent (no laughter, music, applause)
- Clean (no background noise; YouTube auto-captioned audio usually fine)

Current reference: 5.5s slice from R_pFOlfiW5s (Product Metrics video), text ending at "Is it because of the price?". Backups in `.tmp/prodcraft/voice_sample/voice_sample_v1.bak/`.

## The visual layer — Living PRD

The visual layer is a SECOND argument running in parallel to the audio. It is NOT decoration. Stock-photo b-roll is forbidden — viewers would close their eyes if the visual didn't earn its place.

**The Living PRD design**: the entire video is a guided tour of a styled document being built in real time. Sections appear, content types out in sync with narration, key takeaways are highlighted. By the end the viewer has both *understood* the concept AND seen a *concrete artifact* they could screenshot.

### Doc-ops schema

`execution/video/remotion-projects/prodcraft_smoke/src/living-prd/types.ts` defines:

```typescript
type DocOp =
  | { t: number; op: "title_in"; title: string }
  | { t: number; op: "add_section"; id: string; title: string }
  | { t: number; op: "typewriter_lines"; id: string; lines: string[];
        body_style?: "paragraph" | "list" | "checklist"; end_t?: number }
  | { t: number; op: "highlight_section"; id: string }
  | { t: number; op: "checklist"; id: string; items: string[]; end_t?: number };
```

Plan format:
```json
{
  "doc_title": "...",
  "doc_subtitle": "...",
  "audio_duration_sec": 148,
  "ops": [...]
}
```

### Timing rules
- Each typewriter / checklist op has an `end_t` — reveal rate is `(t_now - t_start) / (end_t - t_start)`. Hard-locked to audio.
- Section appearance is staggered ~2-3s *before* the narrator references it (e.g. "What is a PRD?" at 8.5s; narrator says "What exactly is" at 10.58s). Tighter than 2s feels reactive; wider than 4s feels disconnected.
- Highlights happen at the moment the narration LANDS the concept (often end of paragraph).
- No camera zooms in the POC — they were noisy. Auto-scroll when content exceeds viewport.

### Precision-anchored plan generation (2026-06-19)
- After transcribing v5 audio (`prodcraft_transcribe.py`), grep the words.json for anchor phrases (e.g. "Conduit of Clarity", "Add to cart", "comments") and set each section's `t` ~2s before the anchor's `start_sec`.
- Linear-scaling all plan timings by `new_duration / old_duration` (the 1.2x hack) is OK for a v0 quick-look but produces 5-10s drift on long sections. Replace with precision anchors for ship-quality.

### DocCanvas auto-scroll (fix landed 2026-06-19, commit `2ee17f1`)
- Previous: `SECTION_BASE_H = 230` fixed constant. Real section heights vary 226-350px depending on body style. CTA section (last) fell ~400px below viewport at the outro because cumulative shortfall added up.
- Current: `estimateSectionHeight(body_lines, body_style)` — paragraph height = (text chars / 60) × 50px line + 128px chrome; list/checklist = items × 59px + 128px chrome.
- If sections grow longer or fonts change, re-tune `PARAGRAPH_LINE_PX`, `LIST_ITEM_PX`, `PARAGRAPH_CHARS_PER_LINE`, `SECTION_CHROME_PX` in `DocCanvas.tsx`.

### Renderer Windows-player fix (commit `a368b82`)
- Remotion's default H.264 encoder emits `yuvj420p` (full-range) + `bt470bg` (PAL/SD) primaries. VLC/Chrome handle this; Windows Films & TV + Media Player render as near-black.
- `prodcraft_render_living_prd.py` now post-processes every Remotion render through ffmpeg with `scale=in_range=full:out_range=tv,format=yuv420p` + bt709 color tags. Adds ~30s per 3-minute 1080p MP4 at CRF 20, no visible quality loss.
- Skippable via `skip_player_fix=True` on the `render()` function if you ever want the raw output.

### Body styles
- `paragraph` — joined into one block, wraps naturally, char-by-char typewriter
- `list` — explicit per-item rows with `▸` markers
- `checklist` — same as list but with `✓` markers (for criteria/advice/steps)

## Commands (Phase 1 end-to-end)

```bash
# 1) Distill voice profile from past videos (once per channel)
py execution/personal_workflows/prodcraft_voice_profile.py --build

# 2) Extract a clean voice reference (~7s, ends at sentence boundary)
py execution/personal_workflows/prodcraft_voice_sample.py --video-id <id> --duration 7

# 3) Generate script from topic
py execution/personal_workflows/prodcraft_script_gen.py --topic "..."

# 4) Render audio (Gemini Native TTS, single-call, in-prompt style instruction)
py execution/personal_workflows/prodcraft_voice_clone.py \
  --in .tmp/prodcraft/scripts/<slug>.md \
  --backend gemini \
  --gemini-voice Orus \
  --out .tmp/prodcraft/phase1_audio.wav
#   (Chatterbox HF path was the prior recommendation; see TTS table for why it
#    was pulled. Use --backend hf-chatterbox only if HF PRO budget exists.)

# 5) Word-level transcribe for caption timing
py execution/personal_workflows/prodcraft_transcribe.py \
  --audio .tmp/prodcraft/phase1_audio.wav \
  --model small.en

# 6) Build doc-ops plan (hand-authored OR Gemini-generated)
py execution/video/prodcraft_living_prd_plan.py
#   - or invoke a Gemini planner that emits ops based on transcript anchors

# 7) Render the MP4
py execution/video/prodcraft_render_living_prd.py
```

## Cost model

- ChatterboxTTS via HF: $0
- Pexels images (if used for hybrid): $0 (free tier 200/hour)
- FLUX.1 schnell via HF (if used for diagrams): $0 (free)
- Gemini script gen + planner: $0 (Flash free tier ~150 RPD)
- Remotion render: $0 (local)
- **Per-video cost: $0** at this volume

## Honest limits

- **TTS quality ceiling**: F5 / Chatterbox are good but not ElevenLabs-level. Long-form prosody can drift. Sentence chunking mitigates but doesn't eliminate.
- **HF ZeroGPU free tier**: ~5min/day shared across all HF Spaces. Heavy iteration days can exhaust it. Resets at UTC midnight (rolling 24h).
- **Modal free tier**: $30/month for new accounts, but workspace-level spend caps can hit lower. Verify on `https://modal.com/settings/<user>/billing` before relying.
- **Python 3.14 / PyTorch**: as of 2026-06, no PyTorch wheels for 3.14. Local TTS install requires Python 3.11/3.12 in a separate env.

## Status (2026-06-19)

- **Phase 0/0.5**: ✅ shipped (ingest, voice profile, script gen, TTS wrapper, Remotion bootstrap)
- **Phase 1 (v1 - F5 single-call)**: superseded — audio had reference-bleed artifacts ("If hey guys", "you wouldn't even give"). Visual = beat-grid (deprecated).
- **Phase 1 (v2 - F5 post-processed)**: rejected — cascaded atempo + injected silences = "drunk" sound.
- **Phase 1 (v3 - Gemini Orus + 1.2x linear scale)**: superseded — audio approved, but CTA section off-screen due to DocCanvas auto-scroll bug.
- **Phase 1 (v4 - Gemini Orus + precision anchors + DocCanvas fix)**: ✅ **SHIP-GRADE.** `.tmp/prodcraft/phase1_v4.mp4`. Gemini Orus voice + conversational style instruction + per-section height auto-scroll + Windows-compat codec + sub-second visual/narration sync.
- **Phase 1.5 (Brand signature, $0 path)**: ✅ **SHIPPED** (2026-06-19 evening). Operator re-opened the deferred 3D-avatar phase and re-scoped it to "enhance Living PRD signature instead" after rejecting paid paths (Replicate/HeyGen/Real3DPortrait+Colab Pro). New `BrandBookends.tsx` component overlays a branded intro card (first ~2.2s) and outro subscribe card (last ~4.5s) on top of the existing Living PRD canvas — no audio padding, no paid services. Toggleable via `enableBookends` prop (default ON). Ship artifact: `.tmp/prodcraft/phase1_v5_bookends.mp4` (177.7s, with intro+outro). Verified frames at 0.8s (intro card), 60s (doc canvas intact), 177s (outro subscribe overlay).
- **Phase 2 (approval gating)**: ✅ **SHIPPED** (2026-06-19). `execution/personal_workflows/prodcraft_queue.py` (CLI: add/list/approve/reject/pop-approved) + `prodcraft_dashboard.py` (Streamlit: pending/approved/rejected tabs, video preview, metadata edits, ✓/✗ buttons). State at `.tmp/prodcraft/queue/{pending,approved,rejected,uploaded}/<slug>/`.
- **Phase 3 (YouTube upload)**: ✅ **WIRED** (2026-06-19). `prodcraft_youtube_upload.py` — Data API v3 resumable upload from oldest approved item. **Blocked on operator-side setup**: place desktop OAuth client_secret.json at `.tmp/prodcraft/youtube_client_secret.json` (or set `$YOUTUBE_CLIENT_SECRET`). Add operator's YouTube account as a test user on the OAuth consent screen. First run does browser OAuth and caches refresh token at `.tmp/prodcraft/youtube_token.json`. Subsequent runs reuse it. Dry-run verified (`--dry-run` correctly reads queue + reports missing client_secret).
- **Phase 4 (scheduling)**: ✅ **SHIPPED** (2026-06-19). `config/prodcraft_topics.yml` = operator-curated topic queue. `prodcraft_schedule.py` = picks oldest unprocessed topic + calls orchestrator + marks processed. `.github/workflows/prodcraft-weekly.yml` = GH Actions cron `0 9 * * 3` (Wed 10am Paris winter / 11am summer). Cloud run requires GH Secrets: `GEMINI_API_KEY`, optional `YOUTUBE_CLIENT_SECRET_JSON` + `YOUTUBE_TOKEN_JSON` for auto-upload. Dry-run verified (next topic = product-discovery-interviews).
- **Phase 5 (FR variants)**: ✅ **SHIPPED** (2026-06-19). `prodcraft_script_gen.py --language fr` adds a French language clause to the Gemini prompt + body-fallback for the case when Gemini omits `full_script_md`. Orchestrator's `--language fr` chains: script (fr) → voice (Aoede + French style instruction) → transcribe (lang=fr) → plan_gen (Gemini emits FR plan from FR script) → render. Dogfood verified: FR script produces 1578-char fluent French body from hook + 3 body_beats + cta fallback.
- **Phase 6 (thumbnails)**: ✅ **SHIPPED** (2026-06-19). `execution/image_generation/prodcraft_thumbnail.py` — pure Pillow $0 path, 1280x720 PNG matching bookend brand (dark navy, teal accent rail, big Inter-bold title, eyebrow + handle). Visually verified on PRD title.
- **Phase 7 (end-to-end orchestrator)**: ✅ **SHIPPED** (2026-06-19). `prodcraft_orchestrate.py` chains script_gen → voice_clone (Gemini) → transcribe → plan_gen → render → thumbnail → queue add. Per-phase `--skip` and `--dry-run` flags. Generative `prodcraft_living_prd_plan_gen.py` replaces the hand-authored PRD-specific plan: takes an arbitrary script + word timings + topic, prompts Gemini for a strict-JSON doc-ops plan (5-15s reveal-paced sections + CTA), validates against the schema. Dogfood: real script + real words → 13-op plan in 177.7s with correct section pacing. (Honest-gap: a full topic→YouTube e2e dogfood run on a NEW topic is owed; the new components are individually verified but a clean end-to-end render+queue on a fresh topic is the next concrete validation step.)

### Operator-side setup checklist for cloud autopilot
1. Create a Google Cloud project (or use existing). Enable **YouTube Data API v3**.
2. **OAuth consent screen** (`console.cloud.google.com/apis/credentials/consent`): External, add operator's YouTube channel email as a test user. (Test users are required as of late 2024 — "Advanced → Go to (unsafe)" was removed.)
3. Create OAuth 2.0 Client ID (Desktop application). Download JSON. Place at `.tmp/prodcraft/youtube_client_secret.json`.
4. First local run of `prodcraft_youtube_upload.py` does browser OAuth; saves refresh token to `.tmp/prodcraft/youtube_token.json`.
5. For GH Actions auto-upload: paste the contents of `youtube_token.json` into repo secret `YOUTUBE_TOKEN_JSON` and `youtube_client_secret.json` into `YOUTUBE_CLIENT_SECRET_JSON`. Also set `GEMINI_API_KEY` repo secret.

### One-line revert
- Phase 1.5 (brand bookends): `git revert 5ace2c8`
- Phases 2-7: `git revert <next commit hash>` (single commit per the next commit in this branch)

### Commits this branch (Phase 1 ship)
- `a368b82` — renderer Windows-player compat + hf-chatterbox backend (kept for future HF PRO budget)
- `be6d9c4` — Gemini Native TTS backend (current active path)
- `2ee17f1` — DocCanvas auto-scroll per-section height estimator (fixes CTA off-screen)

## When to update this directive

- Modal billing limit changes / Modal account topped up
- HF ZeroGPU quota policy changes
- A new voice-clone model becomes the SOTA on long-form educational content
- The Living PRD components gain new abilities (icons, animations, sticky-note overlays)
