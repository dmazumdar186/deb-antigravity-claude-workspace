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

Voice clone TTS quality is the entire bottleneck of this pipeline. Models tried and ranked by quality-on-long-form (2026-06-17 session):

| Model / Provider | Quality | Cost | Status |
|---|---|---|---|
| ChatterboxTTS via HF Space (`ResembleAI/Chatterbox`) | **Best free option** — clean prosody for educational content | $0 (HF ZeroGPU free, ~5min/day) | **Use this** — sentence-chunked, one call per sentence |
| ChatterboxTTS via Modal (own deployment) | Same model, no quota | ~$0.08/video on A10G, free tier `$30/mo` | Fallback when HF quota exhausted |
| F5-TTS via HF / Modal | Has reference-bleeding + word-scrambling on long-form. NOT suitable for this use case. | Same | **Do not use** — burned hours on this |
| ElevenLabs | Best paid quality | $5+/mo | Out of budget |

### F5-TTS failure modes (avoid)
- **Reference bleeding**: if ref text ends mid-sentence (e.g. "...wouldn't give"), F5 inserts that phrase into generated output. *Fix*: trim ref to end at a sentence boundary.
- **Word scrambling on long generations**: ~700+ chars in one call → "drugs purpose", "clinical suit powders". *Fix*: chunk by paragraph (helps) or sentence (best).
- **Reference-too-long bleed**: 9-10s reference more prone to bleeding than 5-6s. But 5s ref → poor cadence model. **Sweet spot is 7-8 seconds with a complete sentence end.**
- **Cascaded atempo = drunk sound**: never apply ffmpeg atempo on top of TTS speed param. Use one OR the other.

### Chatterbox usage
- Free path: gradio_client → `ResembleAI/Chatterbox` HF Space → `/generate_tts_audio` endpoint
- Per-call limit: ~10s audio per call (~300 char text). MUST chunk by sentence.
- Pause padding between sentences: 250-400ms.
- Optimal exaggeration: 0.5 (neutral). Higher = more dramatic (avoid for educational).

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
- Section appearance is staggered slightly *before* the narrator references it (e.g. add at t-0.5s).
- Highlights happen at the moment the narration LANDS the concept (often end of paragraph).
- No camera zooms in the POC — they were noisy. Auto-scroll when content exceeds viewport.

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

# 4) Render audio (sentence-chunked, Chatterbox HF Space)
py execution/personal_workflows/prodcraft_voice_clone.py \
  --in .tmp/prodcraft/scripts/<slug>.md \
  --backend hf-chatterbox \
  --chunk-by sentence \
  --pause-ms 300 \
  --out .tmp/prodcraft/phase1_audio.wav

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

## Status (2026-06-17)

- **Phase 0/0.5**: ✅ shipped (ingest, voice profile, script gen, TTS wrapper, Remotion bootstrap)
- **Phase 1 (v1 - F5 single-call)**: shipped but audio has minor reference-bleed artifacts ("If hey guys", "you wouldn't even give"). Visual = beat-grid (deprecated in favor of Living PRD).
- **Phase 1 (v2 - F5 post-processed)**: rejected — cascaded atempo + injected silences = "drunk" sound.
- **Phase 1 (Living PRD design)**: ✅ POC v2 visual validated by user 2026-06-17. Full plan in `prodcraft_living_prd_plan.py`. **This is the production visual.**
- **Phase 1 (Modal F5/Chatterbox iterations)**: burned through Modal free credit chasing F5 quality before discovering ChatterboxTTS HF Space. Lesson logged.
- **Phase 2** (approval gating): not started — pending Phase 1 acceptance
- **Phase 3-6**: queued

## When to update this directive

- Modal billing limit changes / Modal account topped up
- HF ZeroGPU quota policy changes
- A new voice-clone model becomes the SOTA on long-form educational content
- The Living PRD components gain new abilities (icons, animations, sticky-note overlays)
