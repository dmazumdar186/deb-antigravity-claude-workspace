# Gaia Sourcing / Radar — directive

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
(console), `render/check_page.py` (Shortlist Check page). Shortlist Check
intake/matching: `layers/intake.py`. Shortlist Check arithmetic:
`eval/time_value.py`. Live re-cut: `execution/modal_radar.py`. Acceptance:
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

## Shortlist Check (`--check`, offline)
Purpose: validate a list of names a recruiter already has against a role's
brief without re-harvesting or calling any provider — zero spend whenever
every name is already in the cached pool. Built for Gaia's Keith Molony;
plan and copy source of truth: `deliverables/gaia_poc_check/PLAN.md`
(`keith_copy.md` for exact wording).

Inputs: `--check <path>` (CSV or plain-text list) + optional `--check-role`,
`--check-out` (default `deliverables/gaia_poc_check`). CSV columns
(aliases, case-insensitive): `name`/`full_name`/`candidate_name` (or
`first_name`+`last_name`), `employer`/`company`/`organization`/
`organisation`, `title`/`job_title`, `linkedin_url`/`linkedin`, `role`/
`role_id` (accepts a role_id, a role's own title, or `role1`/`role2`),
`contact_status`/`email_status` (verified/catch_all/inferred/guess/none).
Plain text: one name per line. Requires `extract` and `validate` already
cached for the campaign; never runs a stage.

Command: `py -m gtm_client_workflows.gaia_sourcing.run --check names.csv
[--check-role role1_senior_structural_engineer] [--check-out DIR]
[--max-grade ... --max-years ... --min-years ... --counties ...
--strict-location|--lenient-location]`. No override flags → Role 1
defaults to senior_engineer / 15 years / strict residence (the promised
brief); Role 2 keeps its own brief unchanged. Mutually exclusive with
`--stage`.

Outputs (all offline, EUR 0.00): `check_results.json` (contract: campaign,
`brief[]` per role applied, `input` — `source` is the CSV's bare filename
only, never the operator-local path — `summary` counts —
submitted/duplicates_dropped/matched/pass/near_miss/out/not_checked/
by_rule/residence/contact — `rows[]`, `pool[]` — the honest denominator —
and `time_value` assumptions/weekly/august_list), `check.csv` (utf-8-sig
encoding so Excel renders accented Irish names correctly on first open;
every cell that starts with `= + - @ \t \r` is apostrophe-guarded against
formula injection), `check_sync.json` (one dry-run Recruit CRM payload +
note per row, `mode: "dry_run"` — `run.py --check` never calls the CRM),
and `keith/index.html` (the client-facing render, built from the same JSON
in the same invocation so page and data can never drift apart).

Recruit CRM sync (day 2 decision (a), dry-run only): `check_row_to_payload`
writes custom fields `Shortlist Check` (`PASS`/`NEAR MISS`/`OUT`/
`NOT CHECKED`), `Shortlist Check line` (the row's one-line summary), and
`Shortlist Check brief` (the row's brief_version) — no email address is
ever put in this payload, only a contact label. `check_note` writes the
candidate note: status, rules failed, up to 5 evidence quotes + source URL
(cap raised from 3 to 5 on 2026-09-13; failing-gate quotes are ordered
before passing-gate ones so the cap doesn't cut a failing gate's own
basis quote), the contact label, and the fixed Art. 14 line. `check.csv`
also carries the CRM-facing `Shortlist Check` / `Shortlist Check line`
columns so the CSV export and the CRM field can never drift apart. This
becomes the "Checked" column in the dashboard Maddie already built (reads
Recruit CRM natively); no UI of ours is shown to Keith's team day to day —
Keith's one-page check stays the pitch document.

Statuses: PASS (clears every hard gate); NEAR_MISS (fails exactly one
gate, not client-side); OUT (client-side, or fails ≥2 gates); NOT_CHECKED
(name not found in the cached pool).

Evidence rules: only what the quote says, never the pipeline's own
inference. A firm-office mention ("joined the Cork office of X") or a
stamped firm-default location is NOT residence evidence under strict/
direct residence — it fails outright, with note "firm office mention, not
a residence statement" (`located_ie` gate); under the lenient default it
passes with a confirm-on-first-call note, surfaced separately in
`passed_with_note[]` so a clean PASS/NEAR_MISS never hides a firm-office or
Irish-scheme-only basis. Under strict residence, Irish-scheme/client-only
evidence (no direct residence statement) also fails outright with note
"no direct residence evidence; Irish scheme work only". A discipline
exclude term fires only from the person's own stated discipline or title
claim, never a passing mention in an employer/project sentence.

Years-figure gates: floor and ceiling read the same stated bound
differently. A strict lower bound ("over 15 years") credits `base` (15)
for a FLOOR gate — "over 7 years" does not clear an 8-year floor, since it
only proves more than 7, not the 8 asked for — but credits `effective`
(base+1 = 16) for a CEILING gate, since "over 15" is strictly above a
15-year cap. An inclusive lower bound ("at least 15 years") or a stated
ceiling phrase ("no more than 15 years") keeps `effective` at the literal
figure for both; a stated ceiling phrase is skipped entirely by the floor
gate (it proves an upper limit, not a minimum).

Limits: names not in the cached pool are NOT_CHECKED, not FAIL — `--check`
never re-harvests or searches for them. No discovery is run. Engineers
Ireland register lookups are not automated; chartership still rests on
quoted claims already in the pool.

15-name input convention: the demo/pilot input is the 13 names Keith
received on 20 August (`input_2026-08-20.csv`) plus the 2 candidates
delivered on 14 September (Alicia Joyce, John Alcaras), appended to the
same file. `layers/intake.py::split_delivered` (shared by `run.py` and
`render/check_page.py` so the two can never disagree) splits by POSITION
only — the last 2 rows of exactly 15, from that exact filename — never by
status; any other file or row count falls back to treating every row as
"original" with nothing "delivered". This also gates the page's
provenance sentence (`_intake_description`): only that exact
file+row-count pair earns the "13 you were sent on 20 August and the 2
delivered on 14 September" line, otherwise the page states only a plain
count.

Regenerate command (offline, EUR 0.00): `python3 -m
gtm_client_workflows.gaia_sourcing.run --check
../deliverables/gaia_poc_check/input_2026-08-20.csv`.

## Edge cases and learnings
- 2026-09-13 (day 2, `deliverables/gaia_poc_check/PLAN.md` "Day 2
  decisions"): found 2026-09-13 — a floor gate ("over 7 years" vs. an
  8-year floor) was crediting the effective (base+1) figure instead of
  the stated base, letting Ronan McCrea's "over 7 years" clear the floor
  it should have missed one year short of; fixed to use `fig.base` for
  floor gates (ceiling gates correctly keep `fig.effective`). Same day:
  the validator's `normalize()` now folds the OCR confusion of `1`/`l`/`I`
  to `i` on both sides of the quote-vs-source comparison (per-character
  fold, not fuzzy matching — cannot make a fabricated quote match), which
  rescued Pearse Sutton's "I have over 40 years" claim, dropped because
  the source PDF's OCR rendered it "1 have over 40 years". Also: a
  firm-office or Irish-scheme-only residence mention now carries an
  explicit, distinct note wording per case (see Evidence rules above)
  rather than a generic residence failure. `input.source` in
  `check_results.json` is deliberately the CSV's bare filename, not the
  full on-disk path, so a client deliverable never leaks an operator's
  local directory structure. Re-validate of the cached corpus (offline,
  EUR 0.00) after these fixes: role 2 validated claims 366 -> 367, role 2
  seniority-not-met 53 -> 52, role 1 unchanged, delivered set unchanged,
  acceptance 41/41. Audit stack run: anneal-reviewer, code-reviewer,
  pipeline-auditor on the numbers, plus a seven-lens review (Keith,
  Isadora, Maddie, the end client, a CFO, a data-protection solicitor, a
  Recruit CRM salesperson) feeding `deliverables/gaia_poc_check/
  OBJECTIONS.md`; commit and push both branch and main.
- 2026-09-11: added `--check` (offline Shortlist Check against the cache;
  see section above). Spend is asserted 0.00 before and after — a paid
  call during `--check` is a hard SystemExit, not a warning.
- 2026-08-20: seniority floor with no ceiling passed Director titles;
  residence gate accepted Irish scheme work as residence. Fixed 2026-09-10.
- Two overlapping runs corrupt each other silently; the lock exists for
  that reason.
- Gemini free tier is 20 requests/day/model.
- OCR path must go through the cost ceiling (it once drained the balance).
- Recruit CRM API requires the Business plan; field names are assumed
  until the first live call.
