# ProdCraft Video-Edit Pipeline (Video-to-Video, Nick Saraev method)

> **Status:** Phase 1a shipped (dry-run + sensitivity/consent gates + schema + failure handlers). Live mode STUBBED until Higgsfield MCP is installed in Phase 2. See plan file `C:\Users\deban\.claude\plans\https-www-youtube-com-watch-v-7su6w-flub-fluttering-parasol.md`.

Adapted from Nick Saraev's 2026-07-07 video ([`7Su6W_FlUbk`](https://www.youtube.com/watch?v=7Su6W_FlUbk)) — the current best-practice video-to-video editing pipeline. This directive codifies his five rules so any operator or sub-agent can re-run the pipeline reproducibly.

## Prior art pass (per `~/.claude/rules/prior-art-first.md`)

| Provider | Free-tier v2v? | MCP? | Sensitivity | Why-not (or why) |
|---|---|---|---|---|
| **Higgsfield MCP** (chosen primary) | 150 credits/mo, ~15-30 gens | Yes, `mcp.higgsfield.ai/mcp` (hosted, OAuth) | US-hosted routing, but models vary — see sensitivity gate | Multi-model aggregator, Nick's exact tool, no code needed to switch models |
| **HuggingFace Spaces** (chosen €0 dogfood) | Yes, genuinely €0 | No (Gradio API) | Wan-VACE is Chinese-origin; HF hosts US infra | Genuine €0 for dogfood; flaky availability, quota-limited per-IP |
| Runway Gen-3 Turbo direct API | No, ~€0.05/sec | No | US (Runway) | Best-in-class talking-head v2v, paid-only — deferred to Phase 7 |
| Fal.ai | No for v2v | No (Python SDK) | US infra | Matches Higgsfield cost; no unique advantage — deferred |
| Replicate | Some models yes | No | US infra | Higher cold-start latency; overlaps HF Spaces path — deferred |

**Winner:** Higgsfield MCP primary + HF Spaces (Wan-VACE) fallback for €0 dogfood.

## Goal

Modify a real source video clip with a hyperspecific `trigger + change` prompt, generate N candidates in parallel (~20% success rate per gen → N=5 default), let the operator human-select the winner, and produce a final winner MP4 ready for weaving into an edit (with a mandatory scene-cut after per Rule 4).

## Nick's five rules (encoded as code-level constraints)

1. **Source-footage-first.** Input is always a real ≤10s clip. The prompt modifies pixels; it doesn't generate them from scratch. Text-to-video-from-scratch mode does NOT exist in this pipeline.
2. **Trigger + change prompt schema.** Every prompt is `{trigger: <time-gated or event-gated moment>} → {change: <what happens next>}`. Free-form prompts are rejected at schema validation.
3. **Parallel-N generation (default 5).** ~20% success per gen. Generate N in parallel, human-select the winner. Sequential-retry is banned by default; `--sequential` flag is debug-only.
4. **720p seam-hiding is a plan-level discipline aid.** Every AI-edited shot in the timeline is followed by a shot-type change (screen share, B-roll, cutaway). Never a same-shot-type cut. Phase 1 ships as a lint (`--check-plan`); PySceneDetect enforcement is Phase 8.
5. **Long-form via chained clips.** Models cap at ≤10s. Long output = sequence of ≤10s clips, each independently edited then stitched. Long-form chaining is Phase 7 (`prodcraft_longform_chain.py`).

## Sensitivity gate (per `~/.claude/rules/model-tier.md`)

Client footage frequently contains real people's faces. Model *jurisdiction* matters, not the aggregator's hosting infra. Enforced routing at parse-time:

| Model | Jurisdiction | Allowed when `--sensitivity sensitive` |
|---|---|---|
| Gemini Omni | US (Google) | ✅ default |
| Runway Gen-3 | US (Runway) | ✅ |
| Sora 2 | US (OpenAI) | ✅ |
| Veo 3.1 | US (Google) | ✅ |
| Kling 3.0 | China (Kuaishou) | ❌ BLOCKED |
| Wan / Wan-VACE | China (Alibaba) | ❌ BLOCKED |
| Seedance 2.0 | China (ByteDance) | ❌ BLOCKED |
| Hailuo | China (MiniMax) | ❌ BLOCKED |

`--sensitivity` is REQUIRED (no default). Bare Claude sessions must NOT invoke Higgsfield MCP directly on client footage — always through this script.

## Consent gate

For `--sensitivity sensitive`:

1. **Written likeness release** from every filmed subject BEFORE upload. Template lives at `directives/gtm_client_workflows/likeness_release_template.md` (Phase 4).
2. **`--consent-verified <path>`** flag REQUIRED. Script checks file exists + non-empty, logs `sha256 + mtime + path` into `.tmp/video/<slug>/run.log` for post-hoc audit. Content is NOT validated — the operator attests fitness at invocation time.
3. **Client engagement letter** includes the deepfake acceptable-use clause (no political, no non-consensual, no impersonation, no misleading news).

## Inputs

CLI:
- `--source PATH` — real source clip (≤10s duration; script checks via ffprobe).
- `--trigger "..."` — natural-language description of the trigger moment (time-gated: "at exactly 2.9 seconds"; or event-gated: "when the man snaps his fingers").
- `--change "..."` — natural-language description of what happens next.
- `--n INT` — number of parallel candidates (default 5).
- `--model NAME` — one of the models in the sensitivity table (default `gemini-omni`).
- `--sensitivity {sensitive,public}` — REQUIRED. Filters model choice.
- `--consent-verified PATH` — REQUIRED when `--sensitivity sensitive`. Path to signed release.
- `--out DIR` — working dir (default `.tmp/video/<slug>/`).
- `--dry-run` — schema + gates + cost estimate only; no API calls; €0.
- `--live` — real generation (STUB until Phase 2).
- `--sequential` — debug-only; disables parallel-N.
- `--winner ID` — after human-select, promote candidate to `winner.mp4`.
- `--check-plan PATH` — lint operator-authored shot list for seam-rule violations.

Env:
- `HIGGSFIELD_MCP_TOKEN` — reserved for future direct-API fallback (Phase 6+). MCP path uses OAuth, no env var needed.

## Tools/Scripts

- `execution/video/prodcraft_video_edit_pipeline.py` — this pipeline.
- ffprobe (external, from ffmpeg) — for source-duration checks. Install: `winget install ffmpeg`.
- **Higgsfield MCP** at `https://mcp.higgsfield.ai/mcp` — installed 2026-07-07 via `claude mcp add --transport http --scope user higgsfield https://mcp.higgsfield.ai/mcp` (recorded in `~/.claude.json`). Requires browser OAuth on the operator's next interactive Claude session before tool schemas load. Public catalog (per higgsfield.ai/mcp):
  - `video-analyzer` — probable input for the "analyze then edit" workflow
  - `cinematic-image-to-video` — closest to Nick's method; likely accepts a source image/video + prompt
  - `motion-control-recast` — v2v with camera-motion control
  - `marketing-video-generator` — text→ad video (not v2v; deprioritize)
  - `soul-character-training` — character-consistency (deprioritize for single-clip)
  - `viral-clip-generator`, `personal-clipper` — repurposing tools
  - `background-image-remover`, `image-expander`, `image-reframer`, `image-upscaler`, `video-upscaler` — post-processing helpers
  - Formal per-tool JSON schemas are NOT published; the pipeline will introspect at runtime via `ToolSearch("select:mcp__higgsfield__*")` once OAuth is complete.
- Phase 3+: HuggingFace Space (Wan-VACE) — Gradio API (public-sensitivity only).

## Outputs

- `<out>/candidates/candidate_{1..N}.mp4` — all generated candidates.
- `<out>/index.html` — human-select interface (click-play-and-pick).
- `<out>/run.log` — invocation log incl. consent file SHA/mtime, model, per-candidate exit codes, cost.
- `<out>/spend_log.jsonl` (workspace-shared: `.tmp/video/spend_log.jsonl`) — per-invocation spend for daily rolling gate.
- `<out>/winner.mp4` — after `--winner ID` follow-up.
- `<out>/manifest.json` — pipeline metadata (source, prompt, model, timestamps, verdicts).

## Steps

1. Parse CLI + validate schema (trigger + change both required + non-empty).
2. Sensitivity gate: reject Chinese-jurisdiction models when `sensitive`.
3. Consent gate: when `sensitive`, require `--consent-verified <path>`; hash + log the file.
4. Duration gate: ffprobe source; reject > 10s with clear "chunk per Rule 5" message.
5. Cost estimate: N × per-model rate (EUR); if > €2, prompt operator confirmation.
6. Daily rolling gate: read `spend_log.jsonl` today's total; warn at €5 cumulative.
7. `--dry-run`: emit manifest.json + cost estimate + exit 0. **Ends here for Phase 1.**
8. `--live`: dispatch N candidates in parallel via `asyncio.gather` (or sequential if `--sequential`). **STUBBED until Phase 2.**
9. Handle failure modes (see Edge Cases).
10. Render `index.html` for human-select.
11. Operator runs `--winner ID` to promote chosen candidate to `winner.mp4`.

## Edge cases

- **Source > 10s:** hard error at schema validation. Message: "Source clip is {N}s; models cap at 10s. Chunk source per Rule 5 or use `prodcraft_longform_chain.py` (Phase 7)."
- **Higgsfield OAuth fails (Phase 2+):** exit code + `HIGGSFIELD_OAUTH_FAILED` + remediation link + suggests HF Space fallback.
- **All N candidates refused for content policy:** print refusal reasons; halt with `ALL_REFUSED`; NO auto-retry (would re-refuse + burn credits).
- **Free tier exhausted mid-batch:** partial candidates preserved to `<out>/candidates/partial/`; exit with `QUOTA_EXHAUSTED` + candidates-produced count.
- **MCP timeout mid-`asyncio.gather`:** individual candidate failures caught + skipped; if fewer than 2 candidates land, exit with `INSUFFICIENT_CANDIDATES`.
- **`--sensitivity sensitive` + Chinese-jurisdiction model:** hard error at parse-time with clear routing-table reprint.
- **`--sensitivity sensitive` + missing `--consent-verified`:** hard error.
- **HF Space cold-start (Phase 3+):** pre-flight `curl -sI <space-url>`; abort with "try later or fall back to Higgsfield free tier" message if Space is queued.

## Cost math (per Nick's video + prior-art pass)

- Higgsfield free tier: 150 credits/mo. Kling 3.0 8s ≈ 2 credits → ~15-30 gens/mo free.
- Gemini Omni batch (paid): €0.46 per 10s clip → €2.30 for N=5 (USD_TO_EUR=0.92 per `~/.claude/rules/currency-eur.md`).
- Client work: pass Higgsfield subscription through in the quote.

## Cost gate

Any single invocation with estimate > **€2** prompts operator confirmation. Additionally, cumulative daily spend > **€5** logs a warning (rolling counter in `spend_log.jsonl`).

## Higgsfield ToS review (Phase 2.5)

Assistant attempted 2026-07-07 to fetch `higgsfield.ai/{terms,tos,terms-of-service,privacy}` — all returned 404 to unauthenticated fetchers (the site is JS-rendered + auth-gated for legal pages). **Operator owes a manual read** of the retention + training-data clauses on their next Higgsfield login, before any real client footage upload. Notes go here when captured. Until captured, treat every uploaded clip as public-corpus-eligible from Higgsfield's side and inform clients accordingly.

Known second-hand from the higgsfield.ai/mcp public page: free tier = 150 credits/mo; browser OAuth is the auth flow; no explicit training-opt-out toggle mentioned.

## Known gaps (per plan Honest Gaps section)

- **Automated video critic** — deferred to Phase 6. Phase 1 uses HTML human-select.
- **PySceneDetect seam enforcement** — deferred to Phase 8; Phase 1 = plan-JSON lint only.
- **Long-form chaining** — deferred to Phase 7.
- **Character/wardrobe/lighting continuity across chained clips** — hard open problem in v2v; not solved by Nick's method either. Chained clips must have visual cuts between them, not seamless continuous action.
- **Live-mode Higgsfield adapter** — stubbed in Phase 1a; real dispatch wired in Phase 2 after MCP install.

## Notes

- Never invoke Higgsfield MCP directly on client footage from a bare Claude session — always through this script (sensitivity gate + consent gate + audit log live here, not in the MCP client).
- The `consent-verified` file check is presence-only. A stale, expired, or wrong-subject release passes. Operator attests fitness; the audit log (SHA + mtime) enables post-hoc catch of stale-release reuse.
