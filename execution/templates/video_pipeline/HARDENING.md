# HARDENING — Video Pipeline

Audit-stack baseline per `~/.claude/rules/mandatory-audit-stack.md`. Every
"shipped" claim for a scaffolded project MUST land the six-auditor verdict
table below.

---

## Preflight (once per project)

- [ ] `.env` populated (see `.env.example`)
- [ ] `cd compose && npm install` completed successfully
- [ ] `bash tests/front_door_video.sh` — front-door PASS
- [ ] Higgsfield MCP OAuth completed in an interactive Claude session
      (visible via `ToolSearch("select:mcp__higgsfield__*")`)
- [ ] Higgsfield credit balance checked and logged below
- [ ] `config/pipeline.json` `daily_cost_ceiling_eur` set to a value the
      operator has explicitly approved

---

## Higgsfield MCP auth status

| Item | Status | Last checked |
|---|---|---|
| MCP endpoint (mcp.higgsfield.ai) | UNKNOWN | never |
| OAuth completed | UNKNOWN | never |
| Free-tier credits remaining | UNKNOWN | never |
| Paid subscription active | UNKNOWN | never |

Update on every session. If `UNKNOWN` when a live generation is requested,
refuse until refreshed.

---

## Output-quality checklist (per composition)

Every composition rendered for delivery MUST pass:

- [ ] File exists at expected path (`compose/out/<name>.mp4` or `.mov`)
- [ ] File size > 50KB (files below indicate corrupt render — cf. yoga_jitendra Pattern A)
- [ ] `ffprobe` duration matches `config.duration_seconds` within ±1/fps
- [ ] `ffprobe` dimensions match `config.aspect_ratio`
- [ ] `ffprobe` reports frame count > 0
- [ ] If audio expected: audio codec present, non-empty stream
- [ ] Manual visual QA: first frame + middle frame + last frame look right
- [ ] Alpha-preset renders: DaVinci Resolve loads with real transparency
      (checkered background visible on V2)

---

## Virality-predictor baseline

Before publishing, run `mcp__higgsfield__virality_predictor` against the
finished video. Log the score below and refuse to publish if below the
operator's floor:

| Video | Date | Virality score | Floor | Decision |
|---|---|---|---|---|
| _example_ | _YYYY-MM-DD_ | _N/100_ | _50_ | _publish / hold / iterate_ |

Absence of this row block-signals to the reviewer that a video was published
without a virality check.

---

## Mandatory 6-auditor verdict table

Fill this table BEFORE claiming any variant of "done / shipped / ready".
Any single FAIL blocks the claim. All six run in a single parallel batch per
`~/.claude/rules/always-parallelize.md`.

| Auditor | Verdict | Blocking? | Evidence citation |
|---|---|---|---|
| Front-door synthetic | | yes | `bash tests/front_door_video.sh` log |
| Customer-POV / acceptance | | yes | `py tests/acceptance_video.py` output |
| Anneal (classic or adversarial) | | yes if FAIL | rounds + top issue |
| Panel-pass Karpathy | | yes | metric or owed-benchmark line |
| Panel-pass Cherny | | yes | dogfood video path + timestamp |
| Panel-pass Amodei | | yes | commit sha + deploy state |
| Panel-pass Research team | | yes | Honest-gaps section pointer |
| Test suite | | yes | tier counts (unit/integ/accept) |
| Adversarial loop | | yes if FAIL | rounds + convergence signal |

Panel-pass MUST be real sub-agent invocations, not narration. See
`~/.claude/rules/panel-pass.md` "IMPORTANT (2026-07-01)".

---

## Cost ledger (EUR, per ~/.claude/rules/currency-eur.md)

| Date | Stage | Model | Cost € | Cumulative today € |
|---|---|---|---|---|

Auto-populated from `.tmp/<slug>/run_log.jsonl` and workspace-shared
`.tmp/video/spend_log.jsonl`. Kill switch fires at
`config.cost.daily_cost_ceiling_eur`.

---

## Git-tracked artifact check (per live-artifact-acceptance.md)

Before every `wrangler pages deploy` / equivalent publish that includes any
Pages Function or server code:

```bash
# Every source file under compose/src/ MUST be git-tracked. Untracked files
# do NOT ship on some publish targets (cf. yoga_jitendra V0.1: 13 days of
# stale fallback because functions/api/dashboard-data.ts was never git add'd).
comm -23 <(cd compose && find src -type f | sort) <(git ls-files compose/src | sort)
# Any line printed = untracked file blocking a real deploy.
```

Wire this into pre-deploy for any scaffolded project that publishes anywhere.
