# Gaia Sourcing / Radar — directive (DRAFT, needs operator approval before moving to `directives/gtm_client_workflows/gaia_sourcing.md`)

## Goal
Deliver evidence-verified, brief-matched shortlists of passive candidates for
Gaia Talent's engineering roles, hand them into Recruit CRM, and never
contact a candidate ourselves.

## Inputs
- A Brief Contract per role (`roles.py` JobSpec with `seniority_band` and
  `location_rule`; CLI overrides `--max-grade --max-years --min-years
  --counties --strict-location`).
- Sources: public records (ACP oral hearings, scheme sites), firm
  directories, registers (Engineers Ireland, IStructE, ICE), licensed
  people data (one provider chosen by `--coverage-test`), bylines.
- Secrets (env / `.env`): `ANTHROPIC_API_KEY`, `PROSPEO_API_KEY`,
  `SERPER_API_KEY`, `FIRECRAWL_API_KEY`, one of `PDL_API_KEY` /
  `CRUSTDATA_API_KEY` / `APOLLO_API_KEY`, `RECRUIT_CRM_API_KEY` (live sync
  only), `ALERT_WEBHOOK_URL`.

## Tools / scripts
`execution/gtm_client_workflows/gaia_sourcing/run.py` stages:
`harvest_r1, harvest_r2, harvest_r2_web, extract, validate, gate, deepen_r1,
adversarial, contact, movability, messages, linkcheck, poolmap, scorecard,
sync_crm`. Render: `render/render.py` (dossier), `render/console.py`
(console). Live re-cut: `execution/modal_radar.py`. Acceptance:
`tests/acceptance_gaia.py`. Contracts for new components:
`RADAR_CONTRACTS.md`.

## Invariants (from HANDOFF §5, binding)
I1/I2 no claim without a verbatim quote validated against the cached
source; drop rate is the hallucination metric. I3 gates are deterministic
Python; a model may propose, never decide. I4 off-limits employers blocked
everywhere. I5 email statuses never collapsed. I6 Art. 14 notice and
opt-out injected as fixed strings. I7 Prodcraft never contacts candidates;
drafts wait for consultant approval. I8 first channel LinkedIn from a named
consultant's own seat. I9 one pipeline process at a time (run lock).
Radar additions: all HTTP through `core/cache.py`; every provider metered;
composition guard refuses a delivery that breaks the brief; opt-out
registry checked at draft creation and at sync; stale evidence (>30 days)
flagged and blocked from sync; scorecard ship threshold: 0 composition
violations and ≥90% grade precision on the labelled set.

## Outputs
`deliverables/<campaign>/`: dossier site, console, `candidates.csv`,
pool maps, scorecard. `run/<campaign>/`: stage JSON, recuts, approvals.
`logs/`: audit, opt-out, outcomes, alerts.

## Edge cases and learnings
- 2026-08-20: seniority floor with no ceiling passed Director titles;
  residence gate accepted Irish scheme work as residence. Fixed 2026-09-10.
- Two overlapping runs corrupt each other silently; the lock exists for
  that reason.
- Gemini free tier is 20 requests/day/model.
- OCR path must go through the cost ceiling (it once drained the balance).
- Recruit CRM API requires the Business plan; field names are assumed
  until the first live call.
