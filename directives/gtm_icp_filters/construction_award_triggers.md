# Construction Federal Award Triggers (USAspending.gov)

## Goal

Give a cold email to a US construction firm one dated, checkable opener: a NEW federal contract it was awarded in the
last N days, with a readable awarding agency. Free public data, no key.

## Inputs

- `--region west|east|midwest|south|mountain` (state lists in `REGIONS`) or `--states CA,OR`.
- `--days` (default 90), `--end` (default today), `--naics` (default `23` = 236 + 237 + 238; the API accepts only
  2-, 4- or 6-digit codes, a 3-digit code is HTTP 400).
- `--min-amount 250000 --max-amount 100000000`: bounds on the award's initial obligation (USD). The floor is the
  federal Simplified Acquisition Threshold (smaller buys are rarely a story); the ceiling drops mega-awards that go to
  firms far above 500 staff.

## Tools/Scripts

`python3 execution/gtm_icp_filters/construction_award_triggers.py --region west` (`--check` = offline, caches only).
Consumed by `execution/lead_sourcing/trigger_batch_leads.py`.

## Steps

1. **Pull** `POST /api/v2/search/spending_by_transaction/` (contracts A-D, recipient state, NAICS, window), one walk
   per state, 100 per page until `hasNext` is false.
2. **Keep only original awards**: modification number `Mod == "0"`. Its `Action Date` is the "awarded on" date.
3. **Amount band** on the original transaction amount, then **one row per recipient** (UEI): newest award.
4. **Award detail** `GET /api/v2/awards/<generated_internal_id>/` (cached): `date_signed`, parent recipient, awarding
   office. The office names the DoD branch (`ENDIST` = U.S. Army Corps of Engineers, `NAVFAC`).
5. **Readable agency**: sub-agency renamed via `AGENCY_RENAME` (e.g. Forest Service -> U.S. Forest Service); an
   internal "Office of ..." sub-agency falls back to the department.

## Outputs

`.tmp/referral/triggers/construction/`: `awards_<region>_<start>_<end>.json` (raw originals), `award_detail/*.json`,
`construction_triggers_<region>.csv` (`recipient,uei,state,parent,award_id,action_date,date_signed,amount,agency,
agency_raw,subagency_raw,office_raw,naics,description,evidence_url`).

## Edge Cases

- **Do not use `spending_by_award` with `date_type: action_date`**: it returns any award with ANY transaction in the
  window, so a 2023 award modified last week shows up (observed 2026-11-13: a 2024 VA cemetery contract with a
  2026-10 mod). Transactions with `Mod == "0"` are the only "awarded on" signal.
- **DoD lag**: DoD procurement is published on USAspending with a 90-day delay, so a 90-day window holds almost no
  Army Corps / NAVFAC / Air Force awards (0 of 123 West recipients on 2026-11-13). Widen `--days` to 180 to include
  them, at the cost of an older trigger.
- Idempotent: the raw pull is cached per region + window; `--refresh` re-pulls. Award details cached per award.
- Recipient names are legal names (ALL CAPS, LLC/INC); readable names come from the LeadOcean match downstream.
- Amount is kept as data only; outward copy must not print it unless the operator decides otherwise.
