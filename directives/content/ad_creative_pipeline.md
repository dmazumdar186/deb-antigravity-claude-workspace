# Ad Creative Pipeline — compositing, direct-gen, UGC video

Source: Nick Saraev course [1:15:23–2:59:15, 2:59:15–3:10:57]; library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §2. Skill:
`.claude/skills/ad-creative/SKILL.md`.

## Goal

Generate ad creative at volume — many cheap variants, human curates winners,
ad-platform performance (not taste) picks what ships. Three tiers by fidelity
and cost. Only build when creative production is the actual bottleneck.

## Inputs

- Reference ad formats: screenshots of proven winners (own first; competitors
  via Meta Ads Library for inspiration — "scoop and spin," never clone).
- Business brief: offer, audience segments, angles, proof points (voice-dump
  quality is fine; brief precedes any generation).
- For direct-gen/UGC: product photos; optional influencer reference photo.

## Tools / Scripts

- **Tier 1 — compositing** (default): procedural HTML/CSS/SVG (gradient mesh,
  noise/grain filters, web fonts) rendered by Claude. ~80% usable, near-free.
- **Tier 2 — direct-gen images**: GPT Image 2 class model via API ($ gated);
  $0-budget path: Gemini image gen (free tier). (GLM 5.2 is a text/code
  model — it belongs to Tier 1 as a procedural-template author, NON-SENSITIVE
  inputs only per the `~/.claude/rules/model-tier.md` GLM guardrail; it cannot
  generate images.)
- **Tier 3 — UGC video**: Higgsfield (MCP already proven here — see
  `directives/video/prodcraft_video_edit_pipeline.md`; free tier = 10 credits
  total, veo3_1_lite at 4 credits/clip ≈ 2 clips before a paid plan).
- Skill `/ad-creative` orchestrates Tier 1 end-to-end.

## Outputs

`deliverables/ad_creative/<brand>/<date>/`: variant images (or HTML), a
contact-sheet/review page with per-variant checkboxes + download-selected, and
the locked template JSON.

## Steps

**Tier 1 (compositing):**
1. Collect references into a folder; write the brief.
2. Scaffold a procedural HTML/CSS/SVG template approximating the reference.
3. Build the **ad tuner**: a local page exposing template parameters (gradient
   angle/type, grain amount/size/seed/blend mode, font, letter-spacing, line
   height, padding, CTA style/copy, zoom) with **Export Settings → JSON**.
4. Hand-tune, export JSON, feed back to lock the visual profile.
5. Batch-generate N variants (default 20) varying copy/CTA/angle; render the
   review page.
6. Human curates; ship winners to the ad platform.
7. Repeat use → skill → scheduled batch → cloud routine (Drive/dated folders)
   only if a daily need exists.

**Tier 2 (direct-gen):** manually verify the model can do the transformation
once BEFORE automating [2:07:02] → API key in `.env`/cloud env (never chat) →
decompose the reference into **fixed vs variable zones** (logo band / negative
space / product band / footer) → 5 variants per template → plan ~4x
overgeneration for a ~25% usable rate → same review-page curation.

**Tier 3 (UGC video):** synthetic influencer from reference (resemble-but-
differ) → composite influencer + real product as start frame → ~10 script
candidates, first-person testimonial voice → duration rule: <22 words → 8s,
≥22 → 10s → **human checkpoint: approve hero frames + scripts BEFORE spending
video credits** → 3 candidates per approved script, tested across models in
parallel → cross influencers × products when multiple supplied.

## Edge Cases

- Script shorter than clip length makes video models invent filler (products
  vanish mid-clip) — enforce the word-count/duration rule.
- Video-platform concurrency caps (~8 jobs observed): cap parallel submissions
  at 3, retry failures serially.
- Male synthetic UGC quality lags female (training-data gap) — overgenerate.
- webp references may need conversion to png for image-model upload.
- De-AI the output: grain, background audio, and a vision QA pass (per-second
  frame extraction) that culls malformed clips before human review.
- Upload the real product as a reusable platform "element" image, never a
  text description — keeps the prop consistent across generations.
- Prefer a platform's CLI/MCP over hand-wiring raw API calls when one exists
  (faster, simpler auth); correct a wrong model/parameter the moment you
  notice it rather than letting a doomed batch finish.
- **Final asset selection is never automated** — AI ideates and drafts, a
  human picks and polishes what ships (`.claude/rules/automation-boundaries.md`).
- Costs in EUR when reporting (`~/.claude/rules/currency-eur.md`); direct-gen
  spend needs operator budget sign-off before the first paid call.
