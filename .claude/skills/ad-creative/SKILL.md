---
name: ad-creative
description: Generate ad creative at volume via the three-tier pipeline (procedural HTML/CSS/SVG compositing, direct-gen image models, UGC video). Use when the user asks to create ad creative, ad variants, a creative batch, ad copy with visuals, or to run the creative pipeline. Triggers on "ad creative", "generate ads", "ad batch", "ad variants", or /ad-creative. Only worth running when creative production is the actual bottleneck.
---

# Ad Creative — three-tier generation pipeline

Directive: `directives/content/ad_creative_pipeline.md` (read it first — it
carries the edge cases). Course source: library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §2.

## Step 0 — Intake (always)

Collect before generating anything:
1. **Brand/product**: name, offer, audience segments, proof points, URL. If
   only a URL is given, research it and confirm the brief back in 5 bullets.
2. **Reference formats**: folder of screenshot references (own winners
   preferred; Meta Ads Library finds for inspiration — scoop the format, never
   clone the creative).
3. **Tier**: default Tier 1 (compositing) unless photorealism is required
   (Tier 2) or video was requested (Tier 3). State the cost implication before
   any paid API call and get sign-off (EUR).
4. **Batch size**: default 20 variants (Tier 1), 5 per template (Tier 2),
   3 candidates per approved script (Tier 3).

## Tier 1 — Compositing (default; ~80% usable, near-free)

1. Scaffold a procedural HTML/CSS/SVG template approximating the reference:
   gradient mesh background, layered noise/grain (SVG filters), wordmark,
   headline, CTA. One self-contained .html per variant.
2. Build the **ad tuner** page in the same folder: live controls for gradient
   angle/type, grain amount/size/seed/blend mode, font (offer a shortlist:
   Inter, Manrope, Sora, Bricolage Grotesque, Red Hat Display), letter
   spacing, line height, padding, CTA style/copy, zoom — plus an
   **Export Settings** button emitting the values as JSON. Open it for the
   user (browser preview) and WAIT for their exported JSON.
3. Lock the JSON as the template profile (save alongside outputs).
4. Generate the batch: vary headline/CTA/angle per variant against the locked
   profile; keep on-brand zones fixed.
5. Render a **review page**: grid of all variants, checkbox per variant,
   "download selected". Human curates — never auto-pick winners.
6. Output to `deliverables/ad_creative/<brand>/<YYYY-MM-DD>/`.

## Tier 2 — Direct-gen images (paid; ~25% usable, plan 4x overgeneration)

1. Manually verify the model can do the requested transformation ONCE before
   wiring automation. If the base model can't, stop.
2. Key from `.env` (never chat). $0-budget path: Gemini free tier (GLM 5.2 is
   text/code-only — usable for Tier 1 procedural templates, never as an image
   model; non-sensitive inputs only per the model-tier GLM guardrail).
3. Decompose the reference into fixed vs variable **zones** (logo band /
   negative space / product band / footer); prompt varies only variable zones.
4. 5 variants per template; same review-page curation as Tier 1.

## Tier 3 — UGC video (Higgsfield; free tier ≈ 2 clips at 4 credits each —
beyond that is a paid-plan gate requiring operator sign-off)

1. Synthetic influencer from a reference photo (resemble-but-differ), then
   composite influencer + real product as the start frame.
2. ~10 script candidates, first-person testimonial voice. Duration rule:
   <22 words → 8s, ≥22 → 10s. Trim scripts to fit — short scripts make models
   invent filler.
3. **Human checkpoint: present hero frames + scripts for approval BEFORE
   spending video credits.**
4. 3 candidates per approved script; cap concurrent jobs at 3, retry failures
   serially. Cross influencers × products when multiples are supplied.
5. QA pass: extract frames per second, vision-check for malformed results,
   cull before human review.

## Escalation (only on demonstrated recurring need)

Prompt run → this skill → scheduled batch (cron/scheduled task) → cloud
routine. Apply `.claude/rules/automation-boundaries.md`: final asset selection
stays human; error-channel logging before any unattended schedule.

## Hard rules

- Never clone a competitor's creative; formats only.
- Never claim numbers in ad copy that aren't case-study-backed.
- No paid API spend without explicit operator sign-off in this session.
- Deliverable = review page + variants + locked JSON; report costs in EUR.
