# Session handoff — Gaia Radar, 2026-09-11 ~13:45 UTC

Branch `claude/candidate-search-filters-xtxcks`, merged into `main` at bbd3b4f (1072 tests green). Working copy has ONE untracked folder: `deliverables/gaia_2026-09-14/` (the regenerating delivery; commit only after acceptance + audit pass; `console/` inside it is gitignored).

## Standing orders (in CLAUDE.md principle 5)
No HITL: never ask the operator; exhaust options; audit, commit, push (branch and main) after every unit, admin rights assumed. Keys live in the workspace `.env` (gitignored, never commit): ANTHROPIC, FIRECRAWL, PROSPEO, SERPER, APOLLO (Apollo free plan has NO API access — dead end). PDL: operator cannot sign up. Firecrawl MCP: 401, dead; Firecrawl REST via key works. Playwright/Chromium cannot egress through the sandbox proxy.

## Money
Anthropic ledger: EUR 25.16 cumulative of a EUR 26.5 cap (`run.py --spend`; `core/config.py max_cost_eur_total`); operator has $30 credit and a $30 Console spend limit as the hard stop. Do NOT re-extract or re-deepen (each ~EUR 3–6). Only offline stages (locate, identity_hygiene, validate, gate, poolmap, render, console) and, at most once more, the tail (`--from-stage adversarial --force --plan anthropic_budget`, ~EUR 0.7).

## Goal by Monday 14 Sep 17:00
Send Keith Molony (Gaia Talent) a corrected shortlist link + Loom + the v2 page. Promise: Senior Engineer grade, Republic of Ireland residence, Engineers Ireland chartership, verified contact, honest counts. Client's earlier complaint: too senior (Directors), not in Ireland (London/Belfast).

## Where the run stands
Campaign `gaia-2026-09-14` (always `export GAIA_CAMPAIGN_ID=gaia-2026-09-14`; deliverables go to `deliverables/gaia_2026-09-14/`; never write into `gaia_2026-08-20`).
Pool: 536 people (471 Role 1 Senior Structural, 65 Role 2 Transport/Cork). Last delivery before chain11: 10 Role 1 cards, 0 Role 2. Two adversarial audits (Fable pipeline-auditor) failed on substance; every finding was fixed in code (commits 9708bdd, 376154b, e8354ec, 1621e9f). Chain11 (`scratchpad/chain11.sh`, logs `p11a.log`, `p11b.log`, `acc11.log`, status `chain11.status`, done-marker `chain11.done` in the session scratchpad; if the scratchpad is gone, just re-run the commands below) was re-running: locate --force → identity_hygiene --force → validate,gate,poolmap --accept-senior-titles → tail → acceptance.

## Next steps, in order
1. From `execution/`: if chain11 did not finish, run
   `GAIA_CAMPAIGN_ID=gaia-2026-09-14 python3 -m gtm_client_workflows.gaia_sourcing.run --stage locate --force`, then `--stage identity_hygiene --force`, then `--stage validate,gate,poolmap --accept-senior-titles`, then `--from-stage adversarial --force --plan anthropic_budget --accept-senior-titles`, then `python3 -m gtm_client_workflows.gaia_sourcing.tests.acceptance_gaia`.
2. Third adversarial audit with the `pipeline-auditor` agent (prompt pattern: check identity per claim URL, grade via gates._grade_of, chartership = CEng + MIEI/FIEI/Engineers Ireland, residence basis per card (OCSC is multi-country: on-page quote required), floor acceptance on TITLE only, employer sector, verbatim quotes, composition_violations, drafts, pool maps, spend, 08-20 folder unchanged). Expect OCSC cards without on-page residence to have dropped; that is correct.
3. If it passes (or only LOW findings): republish `deliverables/gaia_2026-09-14/site/index.html` to the existing artifact https://claude.ai/code/artifact/16f9282e-e30e-4a4b-b6e2-624d836a7e80 (same file path republishes), publish `deliverables/gaia_2026-09-14/console/index.html` as a new artifact, commit `deliverables/gaia_2026-09-14` (dossier.html, site/, candidates.csv, pool maps; console is gitignored), push branch + merge main.
4. Update `deliverables/gaia_2026-09-10/RUNBOOK_monday_delivery.md` and the v2 page (`deliverables/gaia_2026-09-10/v2_proposal.md` + `v2_proposal/index.html`, artifact https://claude.ai/code/artifact/bc97d901-68da-4a96-9888-538dd8c65eed) with the real numbers: Role 1 delivered N of 10 from 471 assessed; Role 2 0 of 5 from 65 (Cork residence + chartership evidence gap; near-misses listed); cost EUR ~0.07 per delivered card; sources: 58 firm directories, 25 witness statements (48 scans recovered by free local OCR), 103 search-snippet discoveries.
5. Regenerate the Brief Controls page from the new dossier if time allows (`deliverables/gaia_2026-09-10/extract_cards_from_dossier.py` then inject JSON into `deliverables/gaia_2026-09-10/brief_controls/index.html`).
6. Loom storyboard and email text are in `deliverables/gaia_2026-09-10/radar_final_spec.md` and the runbook; the operator records the Loom.

## Known honest gaps to state to Keith
Role 2 (Cork) yields zero under strict residence; the pool needs Cork-based transport engineers from sources we do not have for free (licensed people data needs a paid Apollo/PDL plan). Chartership registers cannot be automated. Some cards have no verified email (Prospeo no-match); statuses are labelled, never merged.

## Artifacts
Call brief https://claude.ai/code/artifact/e5cd1898-abd0-4f02-81c2-3eeef8c7c7be · Brief Controls https://claude.ai/code/artifact/3d47597e-04bd-42ec-bb15-ce6126b93703 · v2 page https://claude.ai/code/artifact/bc97d901-68da-4a96-9888-538dd8c65eed · corrected shortlist https://claude.ai/code/artifact/16f9282e-e30e-4a4b-b6e2-624d836a7e80
