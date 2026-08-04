# HANDOFF — Video Pipeline Project

_Fill this out incrementally, not at the end. Per user-level CLAUDE.md
"Write HANDOFF.md incrementally, not at the end." Surfacing debt weekly beats
surprises on delivery day._

---

## What this project is

- **Slug:** `__SLUG__`
- **Scaffolded from:** `execution/templates/video_pipeline/` v__TEMPLATE_VERSION__
- **Scaffolded on:** _YYYY-MM-DD_
- **Client / audience:** _who watches these videos_
- **Cadence:** _one-off / weekly / daily_

---

## Current state

- [ ] `.env` populated
- [ ] `cd compose && npm install`
- [ ] Front-door synthetic PASS: `bash tests/front_door_video.sh`
- [ ] Test suite PASS: `py -m pytest tests/ -v`
- [ ] One dry-run of the full pipeline PASS
- [ ] One live end-to-end video produced and reviewed by operator
- [ ] Audit-stack verdict table in `HARDENING.md` fully green
- [ ] LIVE-PROBATIONARY: day 0 of 5 (per front-door-synthetic rule)

---

## Configuration

- Aspect: _from `config/pipeline.json`_
- Target platforms: _from `config/pipeline.json`_
- Analysis provider: _gemini-direct (default) / anthropic / openrouter_
- Generation provider: _higgsfield_mcp (primary) / hf_space (fallback)_
- Daily EUR ceiling: _€ from `config/pipeline.json`_
- Sensitivity: _public / sensitive_
- Consent-verified file: _path or N/A_

---

## Known gaps

_Every gap needs: (a) what, (b) why open, (c) concrete next step._

- **Live analyze stage is stubbed** — the template ships with `_run_live()` as
  a placeholder returning `is_stub: true`. Real projects must implement the
  vision-API call. Reference: `execution/video/youtube_video_analyzer.py`.
- **Live generate stage is stubbed** — Higgsfield MCP tools are only callable
  from an interactive Claude session, not from a bare Python subprocess.
  Real projects either (a) drive generate.py from within a Claude session
  and pass results via the log path, or (b) implement direct-HTTP fallback
  using `HIGGSFIELD_API_KEY`.
- **Publish handlers are stubbed** — TikTok/YouTube/IG uploaders emit
  manual-publish bundles by default. Real publish requires wiring the
  respective MCP or OAuth flow.
- **HF-Space fallback not wired** — the fallback branch in `generate.py`
  logs a warning but does not currently call a real HF Space. Per
  `feedback_check_hf_spaces_first`, real projects should point this at a
  specific free Space (e.g. `ResembleAI/Chatterbox` for TTS,
  `Wan-VACE` for v2v) before deploying.

---

## Owed by the operator

_Externals — provisioning, credentials, approvals._

- [ ] Higgsfield account with subscription tier appropriate to expected volume
- [ ] YouTube Data API OAuth (if publishing to YouTube): client_secret.json + token.json
- [ ] Meta Graph API access token (if publishing to Instagram)
- [ ] Written likeness release from filmed subjects (if `sensitivity=sensitive`)
- [ ] Approval on `daily_cost_ceiling_eur` — the template's default €5/day is a placeholder

---

## Rollback

One-line revert path:
```bash
# From the scaffolded project directory:
git revert HEAD    # or git reset --hard <last-known-good-sha>
# The published video is not automatically unpublished — that's a manual step
# per platform: TikTok / YouTube Studio / IG.
```

---

## Escalation

- Higgsfield credit exhausted mid-run: pipeline exits `QUOTA_EXHAUSTED` with
  partial candidates preserved under `.tmp/<slug>/assets/`.
- MCP OAuth expired: front-door synthetic surfaces DEGRADED state.
- Kill-switch tripped (daily EUR ceiling): pipeline exits code 3
  `DAILY_COST_CEILING_HIT`. Reset by editing ceiling or waiting for next UTC day.
