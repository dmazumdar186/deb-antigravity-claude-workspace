# Video-Edit Client Pipeline (v2v editing as a service)

> **Status:** prep-only. Activation of this pipeline for a real paying client is **gated on ≥1 real client conversation** confirming interest (per plan file `C:\Users\deban\.claude\plans\https-www-youtube-com-watch-v-7su6w-flub-fluttering-parasol.md` Phase 4, skeptic S1). Until then this directive documents the offer + scoping + pricing so the operator can quote instantly when a lead materializes.
>
> **User-evidence tag:** `[guess]` for every use case listed below until a real client-conversation quote is captured in `directives/gtm_client_workflows/notes/client_<slug>_v2v_intent.md`.

## The offer (short version)

Modify a client's existing video footage with hyperspecific `trigger + change` AI edits. Uses the workspace's `execution/video/prodcraft_video_edit_pipeline.py` under the hood. Method is Nick Saraev's 2026-07 v2v pipeline: source-footage-first, parallel-N candidates, human-select the winner, 720p seam-hiding via scene cuts.

**What we do NOT sell:** text-to-video from scratch (unreliable), continuous long-form narrative editing (character consistency unsolved), replacement of full VFX pipelines (this is targeted per-shot enhancement).

## Named client use cases `[guess]` (re-tag `[seen-it]` when a client says it back)

| Use case | Typical scope | Approx per-shot budget | Notes |
|---|---|---|---|
| Ad creative touch-ups | 3-6 shots, 5-10s each | €50-€120/shot | Hook shots + product reveals. Best fit. |
| Hook-shot magical transitions | 1 shot per short-form | €80-€150/shot | Cannon-shot for TikTok/Reels/Shorts. Reruns 5×+ to hit 20% success. |
| Cinematic relighting (day→night, sunny→magic-hour) | 1-3 shots | €120-€200/shot | Higher candidate count needed. |
| Wardrobe/prop swaps | 1-2 shots | €80-€180/shot | Snap-triggered outfit change (Nick's demo). |
| Product-shot animation (static→dynamic) | 1 shot | €60-€100/shot | Non-PII → Kling/Wan allowed (cheapest tier). |

**Client-side deliverables:** raw source clips (≤10s each, MP4/MOV), written `trigger + change` brief per shot, signed likeness release for every filmed subject appearing in `sensitive` runs.

**Our deliverables:** winner MP4 per shot + HTML index of all candidates + manifest.json + edit-suggestion for seam-hiding cut.

## Cost math (pass through + markup)

Raw compute per shot (Higgsfield free tier or paid):

| Model | Per candidate | ×5 candidates | Notes |
|---|---|---|---|
| Gemini Omni | €0.92 | €4.60 | Default for talking-head, sensitive-eligible |
| Runway Gen-3 | €0.46 | €2.30 | Alt sensitive-eligible |
| Kling 3.0 | €0.28 | €1.40 | **Non-PII only** (Chinese jurisdiction, blocked for faces) |
| Wan-VACE (HF Space) | €0 | €0 | Non-PII only, flaky availability |

Currency per `~/.claude/rules/currency-eur.md`: display in EUR; conversion USD×0.92.

**Higgsfield free tier**: 150 credits/mo ≈ 15-30 candidate gens/mo. First job past that requires the client to pay through a Higgsfield subscription pass-through OR the operator to burn personal credits (not recommended past €10 without client PO).

**Operator markup**: recommend 3-5× raw compute + fixed setup fee €150 per project. Nick's method has 20% first-run success rate; budget 5 candidates minimum per shot to hit acceptable output.

## Scoping constraints to flag to every client

Before quoting, walk the client through these constraints so expectations are set:

1. **10-second clip cap.** Every shot must be ≤10s. Longer scenes → chunk into multiple ≤10s shots with visual cuts between them. No seamless continuous action across cuts is possible today (character consistency unsolved).
2. **~20% success rate per generation.** We generate 5 candidates per shot; the client should not expect the first candidate to be the winner. Turnaround time reflects this (5 candidates in parallel ≈ 5-15 min per shot in the best case).
3. **720p output resolution.** AI-edited shots come out at 720p. The final edit MUST cut to different footage immediately after each AI shot (screen share, B-roll, cutaway). Same-shot-type transitions after AI edits look visibly broken.
4. **Sensitivity/jurisdiction routing.** Any shot with a real person's face/voice/body routes through US-jurisdiction models only (Gemini Omni, Runway, Sora, Veo). Chinese-jurisdiction models (Kling, Wan, Seedance, Hailuo) are reserved for product shots / animation / abstract content.
5. **Deepfake AUP.** No political, non-consensual, impersonating, or misleading-news content. Operator refuses and refunds on breach detected during production.
6. **EU AI Act Art. 50 disclosure (in force 2 Aug 2026).** Every delivered v2v output that depicts a real person must be labeled to the viewer as AI-generated/modified. Two options in the deliverable: (a) visible on-frame corner glyph "AI-edited" for the duration of the modified shot, and/or (b) C2PA JUMBF provenance metadata embedded in the container. **Default: both.** Client opts out at their own legal risk (documented in engagement letter).
7. **French TVA/VAT posture.** Operator's current regime is **franchise en base de TVA** (under €37.5k services/year). Quotes read `TVA non applicable — art. 293 B du CGI` and are HT = TTC. If operator crosses threshold mid-year, quotes flip to `HT + 20% TVA = TTC` and open engagements are re-quoted (client informed at intake). Never quote gross-of-TVA and issue net-of-TVA — that's how you get an accountant surprise at year-end.
8. **Third-party IP clearance.** Source footage frequently contains third-party IP: BGM (music licensing), brand logos in frame, trademarked product designs, third-party talent, filming location rights. V2V modification produces a **derivative work** that inherits the infringement. The likeness release covers filmed subjects only. The client warrants at intake, in the engagement letter, that (a) music is either license-cleared or public-domain, (b) any brand logos/products in-frame are cleared for the use case, (c) filming location has no exclusive-media clause. Operator refuses if unresolved.

## Legal/consent workflow (mandatory before any `sensitive` shot)

For every filmed human subject appearing in a `sensitive` shot:

1. Client obtains signed likeness release using our template: `directives/gtm_client_workflows/likeness_release_template.md`.
2. Client sends signed PDF to operator BEFORE upload.
3. Operator stores release in `.tmp/video/<slug>/consent/<subject-slug>.pdf` and invokes pipeline with `--consent-verified <path>`. Pipeline logs SHA + mtime for post-hoc audit.
4. Client engagement letter includes the Deepfake Acceptable Use clause (template snippet below).
5. Retention: releases kept for 5 years per French *droit à l'image* practice; content deleted from Higgsfield within 30 days of delivery (verify on next login — see Phase 2.5 gap in `prodcraft_video_edit_pipeline.md`).

### Deepfake AUP clause (paste into engagement letter)

> **Acceptable use.** The Provider generates AI-modified video content for the Client using the Provider's video-to-video editing pipeline. The Client warrants that:
>
> (a) it holds a valid, signed likeness release from every human subject appearing in any source footage supplied to the Provider;
>
> (b) all third-party intellectual property visible or audible in the source footage (background music, brand logos, trademarked products, location rights, third-party talent) is either cleared for the intended use case or falls under a public-domain / fair-dealing exemption the Client is willing to defend;
>
> (c) the delivered content will not be used for political messaging, non-consensual imagery, impersonation of third parties without their prior written consent, or misleading news framing;
>
> (d) the delivered content will be distributed with the AI-modification disclosure required under EU AI Act Article 50 (in force 2 August 2026) — either the visible on-frame "AI-edited" glyph the Provider embeds by default, or an equivalent viewer-facing disclosure the Client provides on the distribution channel; opting out of both disclosures is at the Client's sole legal risk;
>
> (e) the Client will retain the signed likeness releases and all IP-clearance evidence for a minimum of five (5) years.
>
> The Provider reserves the right to refuse or terminate any engagement on evidence of breach, with a pro-rated refund for undelivered work.
>
> **Pricing:** all fees quoted in EUR. The Provider operates under the *franchise en base de TVA* regime (art. 293 B du CGI); no TVA is charged. Should the Provider cross the TVA threshold during the engagement, the Client will be notified and open scope re-quoted with TVA at the applicable rate.

## Ramayana-scale / long-form scoping

Client requests for narrative long-form (episodes, movies, series) are **scoped to Phase 7 (`prodcraft_longform_chain.py`), not the current pipeline**. If a client asks for a Ramayana-scale project today:

- Confirm they understand it will be N × ≤10s clips with visual cuts between shots, not continuous action.
- Confirm they accept character/wardrobe/lighting discontinuities across cuts (hard open problem in v2v; not solved by Nick's method either).
- Provide the per-shot cost math × their shot count as a range (e.g. 90-min at ~1 shot per 10s = 540 shots × €5-€15 each = €2,700-€8,100 raw compute + markup).
- Recommend a Phase 3.5 dogfood: 30 seconds (3 shots) as a proof point before quoting the full project.

## MCP-bypass guardrail (from skeptic round 2, residual concern 3)

**Never invoke Higgsfield MCP directly on client footage from a bare Claude session.** All client shots go through `execution/video/prodcraft_video_edit_pipeline.py` because the sensitivity gate, consent gate, and audit log live there — not in the MCP client itself. A direct MCP call bypasses the routing and the audit trail.

## EU AI Act Art. 50 disclosure — implementation owed (post-audit finding)

The Deepfake AUP clause above states the Provider embeds visible + C2PA disclosure by default. The pipeline does NOT yet implement this stamping:

- **Visible glyph:** post-processing pass overlaying "AI-edited" text or icon in a corner of the modified shot (ffmpeg drawtext filter).
- **C2PA metadata:** embed JUMBF manifest into the output container per C2PA v1.4 spec (see `c2pa` Python SDK or `truepic-cai`).

Both are Phase 6-adjacent owed-work: **do NOT accept a sensitive client engagement until this ships.** Cost estimate: ~4h build + 2h test.

## Notes / owed-work

- **Ramayana Phase 7 orchestrator not built.** Long-form scoping above is quotable but delivery for anything >5 chained shots requires the chain orchestrator.
- **PySceneDetect seam enforcement Phase 8.** Today the seam rule is operator discipline + a plan-JSON lint. Automated enforcement (frame-analysis after render) is deferred until acceptance-corpus > 10 triplets OR first client complains.
- **User-evidence tags.** Convert every `[guess]` above to `[seen-it]` when a client conversation confirms it, and log the quote in `directives/gtm_client_workflows/notes/client_<slug>_v2v_intent.md` per plan Phase 3.5 gate.
- **Higgsfield ToS retention/training clauses** — pending manual read on next Higgsfield login (see `prodcraft_video_edit_pipeline.md` §Higgsfield ToS review).
