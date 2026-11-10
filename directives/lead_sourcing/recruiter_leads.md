# Recruiter Leads (Candidate Outreach System campaign)

## Goal
At least 3,000 send-safe recruiter emails in New York, New Jersey, Boston and Houston, split into one Instantly CSV
per location x segment x personalization, ready for the `DM_Recruitment-{Location}-{Personalized|NoPersonalization}-{D Mon YYYY}`
campaigns (naming as the 2 Nov 2026 DM_ campaigns). Copy is written separately and approved by the operator before launch.

**Output contract:** per-location CSVs in `.tmp/recruiters/campaigns/` (main) and `campaigns/catchall/`, an index
`_campaign_index.csv`, `recruiters_all_YYYY-MM-DD.csv`, `rejects.csv` (with `reject_reason`), `summary.json`.
No Instantly writes from this script.

## Inputs
- Env: `LEADOCEAN_API_KEY`, `OPENROUTER_API_KEY` (Jev), `REOON_API_KEY` or `REOON_TOKEN`.
- Targeting in the script: `TITLES` / `EXCL_TITLES` (no coordinators, interns, military), person `city` keyword
  lists per location with `country=US`; the contact's `state` decides the location (blank state -> exact city).

## Tools/Scripts
`execution/lead_sourcing/recruiter_leads.py [--profile general|agency] <step>`

| Step | What it does | Cost |
|---|---|---|
| `count` | free sizing per location x {verified, untested} -> `counts.json` | free |
| `export [--plan-only] [--budget N] [--sample N]` | all verified rows first, rest of budget to untested in proportion to each pool; downloads to `raw/`; then marks every exported person_id on viewed list `recruiters_w1` | export rows (10,000/day) |
| `mark-viewed` | re-send all exported person_ids to the viewed list | free |
| `gate [--limit N]` | hygiene (dedupe, status, location, free-mail, role, domain match, .gov/.mil, MX via DoH), Jev per person: `recruiter` noul (drop < 0.4), `segment` choice, `specialty` choice; keeps 3 per company before Reoon | Jev ~$0.00004/person |
| `verify --max-credits N` | Reoon power mode on every gated email (shared cache `.tmp/reoon/cache.jsonl`) | 1 credit/email |
| `build` | Reoon buckets, final 2 per company (main first), CSVs `Recruitment_{Loc}_{Agency|InHouse}_{Personalized|NoPersonalization}[_CatchAll].csv` | free |

Profile `agency` (run on a later export day): employer industry Staffing and Recruiting / Executive Search Services,
recruiter titles plus owner/founder/partner/consultant/BD, `excludeViewed` against `recruiters_w1`. Keys are
prefixed `agency:` so both profiles share one gate/verify/build.

## Outputs
`.tmp/recruiters/`: `recruiters_all_YYYY-MM-DD.csv` (columns email, first_name, last_name, title, company_name,
website, city, state, location, segment, specialty, specialty_evidence, personalization, linkedin_url,
company_domain, leadocean_status, reoon_status, reoon_score, send_bucket, source), `campaigns/*.csv`,
`campaigns/catchall/*.csv`, `campaigns/_campaign_index.csv`, `rejects.csv`, `summary.json`. Lead data is never committed.

## Steps
1. `count`; check `unsupported` is empty.
2. `export --plan-only`, then `export --sample 30` on one cell and `gate` it; eyeball Jev answers.
3. `export --budget <rows left today>` (background).
4. `gate`.
5. `verify --max-credits <n>` after `reoon_verify.py --balance`.
6. `build`; report the summary.
7. Next export day: `--profile agency count`, `--profile agency export`, then steps 4-6 again.

## Personalization
`company_name` = brand shortened per the casualize-names rules ("Brightpath Staffing" -> "Brightpath") only when Jev rates the short form natural >= 0.6 (second try: brand + industry word, "Premier Staffing"); cache `company_short.json`; original in `company_full`.
`specialty` = a phrase from `SPECIALTIES` (e.g. "healthcare hiring", "energy hiring") used as `{{specialty}}` in
copy. Shipped only when Jev's specialty confidence >= 0.6 AND one of that specialty's evidence words appears in the
person's own title/headline/summary or employer name/industry (`specialty_evidence` column). Otherwise blank ->
NoPersonalization. `segment` = Agency when the employer industry is staffing/search or Jev says
agency/RPO/freelance at >= 0.6, else InHouse.

## Edge Cases (2026-11-10)
- The general pool ranks large corporate TA teams first (sample: 21/21 in-house at BP, Intuit, Fidelity); the
  Oct 2026 DM_Recruitment copy is agency-shaped ("an agency just like {{companyName}}"), hence the segment split
  and the `agency` profile.
- Pool sizes (recruiter titles, work email): NY 2,479 verified / 7,882 untested; NJ 795 / 3,335; Boston
  1,234 / 3,976; Houston 1,094 / 4,466. Agency profile: NY 1,193 / 5,499; NJ 393 / 1,387; Boston 574 / 2,217;
  Houston 519 / 2,551.
- Person filters: `city`, `country`; there is no person `state` filter (400 "Unrecognized key"). `hqState` is
  dropped when >50k employers match.
- City keyword collisions (Pasadena CA, Newark DE/OH, Cambridge MD) are removed by the contact state check.
- Prior DM_Recruitment campaigns (13-14 Oct) exist in the workspace; upload with `skip_if_in_workspace`.

## Exit Criteria
Every exported row is in a campaign CSV or in `rejects.csv` with a reason; only Reoon `safe` >= 90 in main files;
max 2 per company; report counts per location/segment/bucket, personalized share, credits and Jev cost.
