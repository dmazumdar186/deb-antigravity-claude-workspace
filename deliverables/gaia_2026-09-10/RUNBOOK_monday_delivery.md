# Runbook — Gaia v2 delivery for Monday 14 Sep 2026, 17:00

What was promised on the call (10 Sep, 27 min): the sourcing system "the same
way as before", a link plus a Loom, a note on how it works with Maddie and
Recruit CRM that Keith can forward to Maddie (the developer who built Gaia's inbound screener). Nothing else. No auto-sending,
no voice agent, no replacement of Recruit CRM.

Everything below runs on the operator's Windows machine, where the cached
run (`execution/gtm_client_workflows/gaia_sourcing/run/gaia-2026-08-20/`)
and the API keys live. The cloud session cannot run the pipeline: no keys,
no cache.

## 0. Preconditions (15 min)

- `git pull` main. Python deps the pipeline needs beyond the suite: `pip install pymupdf pydantic[email] requests playwright` (a missing PyMuPDF now fails loudly instead of yielding empty PDFs).
- `py -m pytest gtm_client_workflows/gaia_sourcing/tests/ -q` from `execution/` — expect all green (584+).
- Balances: Anthropic (was €0 on 20 Aug — top up ~€20), OpenRouter (~$2), Prospeo (1,992 credits). Gemini free tier resets daily (20 req/day/model).
- Keith's thresholds are NOT yet known (the call did not cover them). Use the
  placeholders in `roles.py` and say so in the Loom: Role 1 ceiling
  `principal_or_associate` / 18 years is generous; the Brief Controls page
  lets him tighten to `senior_engineer` himself.

## 1. Corrected cut of the existing pool (offline, no API cost, ~10 min)

```
cd execution
py -m gtm_client_workflows.gaia_sourcing.run --from-stage gate --stage gate --strict-location
py -m gtm_client_workflows.gaia_sourcing.run --stage poolmap
```
Read the per-role line the gate stage prints ("N passed / M excluded by
seniority_ceiling / K by located_ie") and the composition-guard block in
poolmap. Expect Role 1 to collapse (all 10 delivered were Director grade)
and Role 2 to lose the London/Belfast names. That is the honest number; do
not pad.

To try Keith's likely stricter brief on the same cache:
```
py -m gtm_client_workflows.gaia_sourcing.run --from-stage gate --stage gate --max-grade senior_engineer --max-years 15 --counties "" --strict-location
```


## 1b. Cloud-session state (2026-09-10 evening)

The harvests were re-run in the cloud session (campaign `gaia-2026-08-20`,
fresh cache, Serper key present). Learned and fixed today:
- Serper free plan rejects `num > 10`; all three call sites now cap at 10.
- A missing PyMuPDF made every PDF an empty document with no error; it now
  fails loudly. Failed cache entries can be cleared with
  `run.py --purge-failed-cache <error substring>` (e.g. `empty_after_parse`
  after the Anthropic key arrives, so scanned PDFs get OCR'd).
- Without Firecrawl, `fetch_rendered` falls back to raw HTTP; 7 of 16 firm
  directories yield that way. Re-run `harvest_r1 --force` once the key exists.
- Scanned witness statements fail OCR until `ANTHROPIC_API_KEY` is set (and
  the `anthropic` package is installed); they are cached as
  `empty_after_parse` and must be purged before the keyed re-run.

## 1c. Cloud-session state (2026-09-11 evening) -- the corrected cut EXISTS

Everything in sections 0-2 was executed in the cloud session on campaign
`gaia-2026-09-14` (always `export GAIA_CAMPAIGN_ID=gaia-2026-09-14`). The
delivery is committed under `deliverables/gaia_2026-09-14/` (dossier.html,
site/index.html, candidates.csv, pool maps; `console/` is regenerable and
gitignored). Four adversarial audits ran; every substantive finding was
fixed in code with a regression test (suite: 1,086 tests; acceptance gate:
41 checks, passing).

Result: Role 1 -- 471 assessed, 2 gate-passers, **2 of 10 delivered**
(Alicia Joyce / CSEA, John Alcaras / Arcadis); 14 near-misses on residence
evidence, 8 on chartership evidence, listed in `pool_map_role1.md`.
Role 2 -- 65 assessed, **0 of 5**. Model spend EUR 25.69 of a EUR 26.50
cap (operator's USD 30 Console limit is the hard stop). Do NOT re-run
extract or deepen; only offline stages (locate, identity_hygiene, validate,
gate, poolmap, render, console) are affordable.

Rules that now bind every cut (all hard gates, all tested):
- Residence: only a residence-shaped quote ("based in Dublin", "Location:
  County Meath", "Dublin, County Dublin, Ireland") passes. A firm's office
  default passes only when the brief does NOT set require_direct_evidence
  (Role 1 does), and then with a "confirm on first call" note on the card.
  Project locations, universities and "across the UK and Ireland" never do.
- Grade ceiling: highest rung across the title and every employer quote
  that names the person (so "Head of Design" on the firm's own page counts).
- Chartership: CEng (incl. "C. Eng") + MIEI/FIEI/F.I.E.I./"Engineers
  Ireland". MIEI alone, ICE or IStructE alone do not pass.
- Employer: recovered deterministically from the person's own text when the
  model missed it ("<title> at <Firm>", LinkedIn "<title>. <Firm>. <Mon
  YYYY>"); anyone still without one is named as held back, never hidden.
- Cards always show the residence and chartership basis quotes first;
  second opinions come last (max 2, clipped) and never push the
  email-honesty line off the card.

Known data note: `run/gaia-2026-09-14/docs.jsonl` carries 4 malformed lines
(concurrent writers earlier in the session); `load_docs` skips them with a
log line. Claims citing those docs failed quote validation and were dropped,
which is the safe direction.

## 2. Widen the pool for the right grade (needs keys, ~€15–40, 2–4 h)

Role 1 needs 8–15-year Senior/Principal engineers; the "our people" pages
mostly list leadership. Options in order of cost:
1. `deepen_r1` on the near-misses in `pool_map_role1.md` ("missed by one").
2. Re-harvest with more firm directories (add to `sources/company_bios.py` FIRMS)
   and re-run `harvest_r1 → extract → validate → gate`.
3. Chartership register lookups for the four Jacobs near-misses on Role 2
   are MANUAL (verified 2026-09-10): Engineers Ireland's Find-a-member is a
   stateful portal behind a WAF, and IStructE / ICE directories sit behind
   Cloudflare challenges. The plugins in `sources/` honour robots and return
   nothing rather than operate the portals. Do the four lookups by hand in a
   browser, save each result page (Ctrl+S, HTML) into the campaign cache
   directory, and run `sources.registers.claims_from_register_doc` on it so
   the chartership claim carries a verbatim quote and a source. Firecrawl
   rendering of the IStructE/ICE pages is implemented but unverified; try it
   once with the key present and stop if it is challenged.
4. A licensed people-data trial (PDL / Crustdata / Apollo) — only if 1–3
   fall short, and only after a €10 test query proves Irish coverage.

Then `--from-stage contact` (Prospeo), `movability`, `messages`, `linkcheck`, `poolmap`.

## 3. Render and deploy (30 min)

```
py -m gtm_client_workflows.gaia_sourcing.render.render
py -m gtm_client_workflows.gaia_sourcing.tests.acceptance_gaia
```
The acceptance gate now includes the delivery composition guard; it must
pass before anything is sent. Deploy `deliverables/gaia_2026-09-14/site/`
(copy the pattern of `gaia_2026-08-20/site/`) to Cloudflare Pages as a new
project, e.g. `gaia-resourcing-v2`. Deploy
`deliverables/gaia_2026-09-10/brief_controls/` alongside (or regenerate it
from the new dossier with `extract_cards_from_dossier.py` and re-inject the
JSON) so Keith can move the brief settings himself.

## 4. Recruit CRM sync (dry-run only unless Keith gives a key)

```
py -m gtm_client_workflows.gaia_sourcing.run --stage sync_crm          # dry-run: audit log only
py -m gtm_client_workflows.gaia_sourcing.run --classify-reply "Thanks, not looking right now"
```
Live writes need `RECRUIT_CRM_API_KEY` (Recruit CRM Business plan or above;
the account owner generates it) and `--live-crm`. Show the dry-run audit
log in the Loom instead of a live write.

## 5. Loom (≤5 min) — order

1. "You were right on both": the two filter facts, four names.
2. Brief Controls: apply the Senior Engineer ceiling, watch the list re-cut.
3. The corrected dossier: survivors per role, the honest count, the CSV.
4. The hand-off: a card → Recruit CRM candidate (dry-run log), reply
   classification demo, where Maddie takes over.
5. What we need from Keith: seniority ceiling and Ireland rule in one line
   each; Recruit CRM plan tier; which two live roles to run next.

## 6. Send (Monday before 17:00)

Email to Keith with: dossier link, Brief Controls link, the v2 page for
Maddie, Loom link, the honest count, and the two questions. Ask him to forward
the v2 page to Maddie. Do not attach a price; the follow-up call does that.
