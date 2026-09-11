# Shortlist Check — POC plan (day 1 build, day 2 brainstorm)

Written 2026-09-11. Owner: Debanjan Mazumdar. Audience for this file: the operator and the day-2 brainstorm.

## The one sentence

Recruit CRM finds names. Maddie's screener handles the people who apply. Shortlist Check proves the people a consultant is about to call: chartered, resident, right grade, real contact, with the quote and the source on every line, and an honest count of what it rejected and why.

## Why this and not something Keith already pays for

From Recruit CRM's own pages as of 2026-09-11 (`.tmp/research/recruit_crm_capabilities_2026-09.md`, sourced):
- AI Sourcing returns profiles from LinkedIn and the public web with no evidence quotes, no source links, no filter breakdown; credit-metered.
- AI matching is one 0-100 "bimetric" score. No hard rule ("must be chartered", "must live in County X") is documented; a non-qualifier is down-weighted, not removed.
- No credential or identity verification exists natively. Their own blog treats background checks as a third-party category.
- Sequences send on email, SMS and LinkedIn and pause on failure. No reply classification, no snooze or next-step logic is documented.
- "Verified emails and phone numbers" via the Chrome extension, with no method or accuracy rate disclosed.
- API needs the Business plan or above. CSV export of candidates is standard on paid plans.

So the layer sells the six things none of that does: hard rules, evidence behind every verdict, chartership and residence checked against the public record, an honest rejected list, labelled contact confidence, and reply classification into the CRM. Nothing in the POC re-does sourcing, matching scores, sequencing or parsing.

## Who reads what

| Reader | What they need to see | Artifact |
|---|---|---|
| Keith (MD, industry since the 1990s; "I'm a recruiter, not a techie guy"; proud of Maddie, liked the simplicity of the August page) | His own 20 August list, checked. Big numbers. Plain words. Hours and euros. What it is not. | `keith/index.html` — one page, no jargon, no settings, one paste box |
| Maddie (the developer who built Gaia's inbound screener; per the operator, no one named Steph exists, Fathom garbled the name) | That this adds a stage before Maddie's, never touches hers, and is engineered, not prompted: contracts, deterministic gates, verbatim validation, dry-run CRM adapter, tests, cost per name | `maddie/index.html` — technical appendix |
| The operator | The build, the numbers, the open questions for day 2 | this file + `check_results.json` |

Words never used on Keith's page: AI, LLM, model, platform, pipeline, automated, system, agent. Words used: the check, the list, proof, the rule, checked by hand.

## The demo that costs nothing

The 13 names Keith received on 20 August are all in the restored `gaia-2026-09-14` cache (536 persons assessed, extract + validate + gate done). So the POC runs the check on the exact list Keith already holds, offline, zero model spend:

Result, final run (11 Sep, no override flags: Role 1 defaults to the promised Senior Engineer ceiling, 15 years, strict residence; Role 2 keeps its own Associate Director / 25-year brief until Keith answers):
- 13 in, 0 pass, 2 near miss, 11 out. Every one of the 13 fails the seniority ceiling for its role (10 structural names are Director or Associate Director; Gerry Healy is evidenced at 26 years against a 25-year cap; Andrew Archer and Pearse Sutton are Director grade).
- Residence: 0 evidenced as living outside the Republic; 11 have no statement of where they live at all (Taskov and Penco have office-history quotes, London 2013 and 2015; the rest have project or market mentions only). Pat Brady's "first joined the Cork office of" is a firm-office mention and no longer counts, which is the gate fix of 11 Sep.
- Chartership evidence missing for Petho and Penco. Contact labels from the August CSV: 7 verified, 5 guesses, 1 none.
- The near-miss lines carry their actual reason ("evidenced at 26 years' experience, above the 25-year ceiling; everything else passes").

The page also carries the whole 536-person pool as a small JSON so the paste box works for any name already checked; a name not in the pool shows "not checked yet, one working day" rather than a fake verdict.

## Quantified value (assumptions editable on the page, defaults stated)

Time-value is new code (`eval/time_value.py`), deterministic, no model:
- `minutes_per_manual_check` default 15 (open LinkedIn, the firm page, the Engineers Ireland register, confirm location, find an address). Keith sets the real number on day 2.
- `names_per_week` default 40 (Keith's stated ambition is 50-100 live jobs on two consultants; 40 names a week is conservative).
- `hourly_cost_eur` default 45.
- Output: hours per week, euros per month, and for the August list specifically: 13 names x 15 min = 3.25 consultant hours spent on a list where 0 qualified, plus 4 emails written to 4 people who could never be placed on that brief.
- Client-facing error rate: August 13 of 13 wrong on today's brief; September 0 of 2 wrong (audited four times).

These are the only numbers on Keith's page. Every one is either counted from source or an assumption he can change.

## Build (day 1)

Code lives in `execution/gtm_client_workflows/gaia_sourcing/` and follows its contracts (`core/contracts.py`), hardening rules, and test layout.

1. `layers/intake.py` — `load_names(csv_or_list) -> list[IntakeRow]`; `match_pool(rows, persons) -> matched/unmatched` by normalised full name (+ employer tiebreak, Unicode-folded, O'Reilly-safe). Deterministic `person_id` for unmatched rows (same slug rule as extract). No network.
2. `eval/time_value.py` — pure functions, assumptions as one dataclass, unit-tested.
3. `run.py --check <csv> [--out <dir>]` — offline: loads cache, runs gates on matched persons under the current brief (CLI overrides apply), writes `check_results.json` (contract below) + `check.csv` (CRM-importable: name, employer, status, reasons, evidence note). Unmatched rows are listed as `NOT_CHECKED`; discovery for them is designed (reuse `sources/technical_evidence.discover_for` pattern with per-gate query templates) but NOT run in the POC: budget is EUR 0.81 of 26.50 and the operator's USD 30 Console cap is the hard stop.
4. `render/check_page.py` — renders `keith/index.html` from `check_results.json`. Static, one file, no external calls, works at 400px, prints.
5. `deliverables/gaia_poc_check/maddie/index.html` — the technical appendix, written by hand.
6. Tests for 1-4; suite stays green; acceptance-style check for the Keith page (every OUT row names its rule; every PASS row has a quote and a source; the words on the banned list do not appear).
7. Audit stack (anneal-reviewer, code-reviewer, pipeline-auditor on the numbers), commit, push branch and main, publish both pages as artifacts.

## `check_results.json` contract

```
{
  "campaign": "gaia-2026-09-14", "generated_at": "<iso>", "brief_version": "<role_id>@<git sha>",
  "brief": {"role_id": "...", "title": "...", "rules": [{"gate_id": "...", "label": "...", "rule_text": "..."}]},
  "input": {"source": "20 August 2026 delivery", "rows": [{"name": "...", "employer": "...", "title": "..."}]},
  "summary": {"submitted": 13, "matched": 13, "not_checked": 0, "pass": 0, "near_miss": n, "out": n,
              "by_rule": {"seniority_ceiling": 10, "located_ie": 4, "chartered": 2, ...},
              "contact": {"verified": 0, "catch_all": 0, "guess": 5, "none": 1, "unknown": 7}},
  "rows": [{"name", "employer", "title", "status": "PASS|NEAR_MISS|OUT|NOT_CHECKED",
            "failed": [{"gate_id", "label", "reason"}], "evidence": [{"dimension", "quote", "source_url"}],
            "contact": "verified|catch_all|guess|none|unknown", "one_line": "<plain English, <= 20 words>"}],
  "pool": [{"name", "employer", "status", "failed_labels": [...]}],
  "time_value": {"assumptions": {...}, "august_list": {...}, "weekly": {...}}
}
```

## Open for day 2 (brainstorm)

0. The dashboard Maddie built (Keith showed it on the call: per-consultant queue, score per job, flag over 60, sync for call, screened / synced / drafts counts, jobs list, left tabs). The strongest fit is a "checked" column in that dashboard fed by `check_results.json`, not a separate page for daily use; Keith's one-page check stays as the pitch document. Needs from the operator: the dashboard's tab names and what a candidate row shows, from the recording.

1. Is the buyer Keith (hours) or the client relationship (no wrong CV to TOBIN)? The page leads with hours; the guarantee line leads with the relationship. Pick one for the headline.
2. Intake source in the pilot: Recruit CRM CSV export (standard on paid plans), LinkedIn Recruiter project export, or a pasted list? All three are the same code path.
3. Discovery for names not in the pool: cost per name (Serper + fetch + extract, roughly EUR 0.10-0.30) and who pays. Needs the Console cap raised before any live run.
4. Engineers Ireland register: terms of use unverified; until then chartership is evidenced from the person's own post-nominals and their employer's page, and the card says which.
5. Maddie boundary: the check writes a candidate at stage "Sourced" with an evidence note; her screener's trigger stays on the stage it already uses. Confirm with Maddie that a sourced candidate entering at that stage does not fire the inbound flow twice.
6. Pricing rung for the check alone (per role, per month, or per verified name) versus the Radar subscription in `radar_final_spec.md`.
7. The transcript is now in `deliverables/gaia_2026-09-10/transcript_2026-09-10_fathom.md`. Keith's written feedback before the call was "too senior, some not in Ireland" (commit a626381); on the call he repeated the seniority point. "You were right on both" stands. He gave no minutes-per-name figure; the page's 15 minutes stays an assumption until he sets it. His own frame for the buy decision: "is this a value add or another AI headspace thing taking us from our ABCs"; "speed and accuracy"; and his direct comparison "0 to 100 match scores, similar to what you did" is the objection the Keith page must answer in one line: a score says how similar, a check says whether, and why.
