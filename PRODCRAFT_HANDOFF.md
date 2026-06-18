# ProdCraft Phase 1 — Autopilot Handoff (2026-06-17 evening)

> You left at ~21:30 Paris. This is what I (Claude) did while you were out.
> (The other HANDOFF.md in this repo belongs to Accessory Masters and is frozen. This is yours.)

## TL;DR — What you'll find when you open this

1. **Final Phase 1 video**: `.tmp/prodcraft/phase1_final.mp4` — full 2:27 (the entire PRD script), Living PRD visual, with the v1 voice-cloned audio.
2. **A new directive**: `directives/personal_workflows/prodcraft_autopilot.md` — codifies everything learned today, including the TTS landscape map so we don't repeat the F5 wild-goose chase.
3. **No new spend** — neither Modal (still billing-blocked) nor any paid TTS was used. Everything ran on existing free credit (HF / Gemini / Pexels / Remotion local).
4. **One open issue you'll want to address**: audio has minor reference-bleed artifacts (~4 instances of "you wouldn't give" / "if hey" injected by F5-TTS). These can be cleaned up tomorrow when HF ChatterboxTTS quota resets.

## Why this audio (and not better)

I exhausted free paths in the order below:

- **HF ChatterboxTTS Space** (`ResembleAI/Chatterbox`) — the right tool, FREE, but quota was already exhausted today by F5 iteration. Resets at UTC midnight (~1-2am Paris). I tried it twice while you were out; still blocked.
- **Modal ChatterboxTTS** — deployed but Modal workspace hit "spend limit reached" (the $30/mo free tier limit somehow hit; needs you to check `https://modal.com/settings/dmazumdar186/billing` to understand why).
- **Local ChatterboxTTS** — blocked by Python 3.14 having no PyTorch wheels. Would need a Python 3.11/3.12 install (~30 min extra).
- **F5-TTS retry** — known quality ceiling on long-form: reference bleeding + word scrambling. Not viable.

**Selected**: original v1 audio (F5-TTS single-call, 2:27 at 0.85× effective). You said the voice was "perfect, just too fast" when you heard the speed=0.85 sample this morning. It has minor reference-bleeding artifacts (~3-4 phrases injected from the ref clip) but is THE cleanest voice-cloned audio we produced today.

**Trade-offs you should know about**:
- Speed is 0.85× (you originally wanted 0.7×). I did NOT apply atempo to slow it further because doing so previously created "drunk" cascaded audio. Single F5 native speed is better than F5+atempo.
- Reference bleeding: ~3-4 short F5 hallucinations in 2:27 — listen for "If hey guys" at the start, "you wouldn't even give" mid-sentence ~12s, and one or two more. They blend in but you'll notice them.

## What's READY to ship in v2 (when you want to do it)

1. Wait for HF Chatterbox quota reset (~1-2am Paris tonight or ~5min/day quota tomorrow).
2. Run `py execution/personal_workflows/prodcraft_voice_clone.py --in .tmp/prodcraft/scripts/<script>.md --backend hf-chatterbox --chunk-by sentence --pause-ms 300 --out .tmp/prodcraft/phase1_audio.wav` (I haven't yet added the `hf-chatterbox` backend — see "Owed work" below).
3. Re-transcribe, re-author plan timings, re-render.

## Visual direction — locked

The Living PRD design (your feedback validated POC v2) is the production visual. Document is full-bleed (no browser-window chrome), warm off-white page background, ProdCraft channel breadcrumb up top, sections appear and build with typewriter / list / checklist styles in lock-step with audio.

Component locations:
- `execution/video/remotion-projects/prodcraft_smoke/src/living-prd/DocCanvas.tsx`
- `execution/video/remotion-projects/prodcraft_smoke/src/living-prd/DocSection.tsx`
- `execution/video/remotion-projects/prodcraft_smoke/src/living-prd/use-doc-state.ts`
- `execution/video/remotion-projects/prodcraft_smoke/src/living-prd/types.ts`
- `execution/video/remotion-projects/prodcraft_smoke/src/Root.tsx` (registers `ProdCraftLivingPRD` composition)

Full plan generator: `execution/video/prodcraft_living_prd_plan.py` — 6 sections + outro CTA, anchored to v1 audio's actual segment timings.

## TTS landscape — codified in directive

The directive at `directives/personal_workflows/prodcraft_autopilot.md` has the full TTS map: which models work for which use cases, why F5 is not the answer despite being a great voice clone, which models to fall back to. Read it before iterating again — it'll save you several hours.

## Owed work (small, you can ask me to knock these out tomorrow)

1. **Wire `--backend hf-chatterbox` into `prodcraft_voice_clone.py`** — I added `--backend chatterbox` (Modal-only) but not the free HF Space path. ~15 min to add.
2. **Gemini-driven doc-ops planner** — currently the plan is hand-authored in `prodcraft_living_prd_plan.py`. For autopilot to work on arbitrary topics, this needs to be Gemini-generated from script+transcript. ~30 min build.
3. **Modal billing diagnosis** — confirm whether the $30/mo free credit is actually available on your workspace, or whether there's a sub-cap. Quick check on Modal billing page.
4. **Voice reference upgrade** — re-extract a 7s reference (currently 5.5s; too short caused F5 cadence issues even though we don't use F5 anymore — wider ref will help Chatterbox quality too). Constraint: must end at a sentence boundary.

## Cost so far today

- HF compute: $0 (free tier ZeroGPU, exhausted but billed nothing)
- Modal compute: ~$30 of free credit consumed (image builds + F5 + Chatterbox iterations)
- Gemini: $0 (free tier, ~10 calls)
- Pexels: $0 (free tier, 19 image fetches earlier this morning)
- Replicate / ElevenLabs / paid anything: $0 (not used, per your "no paid" instruction)

## What to do when you open this

1. Watch `.tmp/prodcraft/phase1_final.mp4` and judge.
2. Read this HANDOFF.
3. Read the new directive at `directives/personal_workflows/prodcraft_autopilot.md`.
4. Tell me what to do next when you're back.

Nothing pushed to origin; everything is local commits only (per your "ask before push" rule).
