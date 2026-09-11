# Session handoff — Gaia Radar, 2026-09-11 evening (UTC)

Branch `claude/candidate-search-filters-xtxcks`; merged into `main` after every unit. Working copy is clean after the last push (check `git status --short`; `deliverables/gaia_2026-09-14/console/` is gitignored and regenerable).

## Standing orders (CLAUDE.md principle 5)
No HITL: never ask the operator; exhaust options; audit (anneal-reviewer, code-reviewer, pipeline-auditor), commit, push branch + main after every unit, admin rights assumed. Keys live in the workspace `.env` (gitignored, never commit): ANTHROPIC, FIRECRAWL, PROSPEO, SERPER, APOLLO (Apollo free plan has no API access). PDL: operator cannot sign up. Firecrawl MCP is dead (401); Firecrawl REST via the key works. Playwright/Chromium cannot egress through the sandbox proxy. Cloud sessions use `python3`, never `py`.

## Money
Anthropic ledger: EUR 25.69 cumulative of a EUR 26.50 cap (`run.py --spend`; `core/config.py max_cost_eur_total`); the operator's USD 30 Console spend limit is the hard stop. Do NOT re-run extract or deepen (EUR 3-6 each). Affordable: offline stages (locate, identity_hygiene, validate, gate, poolmap, scorecard, render, console) and, at most once, `--stage adversarial --force --plan anthropic_budget` (~EUR 0.05 per card) or `--stage messages --force` (~EUR 0.01 per card).

## Goal by Monday 14 Sep 17:00
Send Keith Molony (Gaia Talent) the corrected shortlist link + Loom + the v2 page (for Steph). Promise: Senior Engineer grade, Republic of Ireland residence with direct evidence, Engineers Ireland chartership, verified/labelled contact, honest counts.

## Where it stands (DONE in this session)
Campaign `gaia-2026-09-14` (`export GAIA_CAMPAIGN_ID=gaia-2026-09-14`; deliverables in `deliverables/gaia_2026-09-14/`; never write into `gaia_2026-08-20`).
- Role 1: 471 assessed, 2 gate-passers, **2 of 10 delivered** (Alicia Joyce / CSEA, John Alcaras / Arcadis). Near-misses named in `pool_map_role1.md` (14 on residence evidence, 9 on chartership).
- Role 2: 65 assessed, **0 of 5**.
- Acceptance gate: 41 checks PASS. Suite: 1,086 tests PASS. Four pipeline-auditor audits; the fourth ran on the frozen tree (its verdict is in the commit message of the final commit).
- Rules now binding (all tested, see the runbook §1c): residence needs a residence-shaped quote; firm-office defaults pass only when the brief does not require direct evidence, and then with a card note; unstamped `Person.location` never passes but still excludes (Belfast/London); grade ceiling scans the title and every employer quote naming the person; chartership accepts "C. Eng"/"F.I.E.I."; employer is recovered deterministically from the person's own text; held-backs are named in the banner and pool map; basis quotes are pinned first on every card; second opinions render last, max 2, clipped.
- Docs updated with real numbers: `deliverables/gaia_2026-09-10/RUNBOOK_monday_delivery.md` (§1c), `v2_proposal.md` + `v2_proposal/index.html` ("The corrected cut, as it stands").

## Next steps, in order
1. Verify the tree is clean and `main` == branch head (`git log --oneline -3`). If any audit finding was left open, it is listed in the last commit message under "Open".
2. Republish `deliverables/gaia_2026-09-14/site/index.html` to the existing artifact https://claude.ai/code/artifact/16f9282e-e30e-4a4b-b6e2-624d836a7e80 (Artifact tool, `url` param) and `deliverables/gaia_2026-09-10/v2_proposal/index.html` to https://claude.ai/code/artifact/bc97d901-68da-4a96-9888-538dd8c65eed. Publish `deliverables/gaia_2026-09-14/console/index.html` as a new artifact if the console is wanted in the Loom (regenerate with `--stage console` first if the folder is missing).
3. Brief Controls (https://claude.ai/code/artifact/3d47597e-04bd-42ec-bb15-ce6126b93703) deliberately still re-cuts the 20 August 13-card list: that is the "you were right on both" demo. Leave it.
4. Loom storyboard + email text: `deliverables/gaia_2026-09-10/radar_final_spec.md` and the runbook §5-6. The operator records the Loom; draft the email body for them in chat if asked.
5. If spend allows and a reviewer wants more names: the only cheap lever left is `--stage deepen_near_misses --force --deepen-gates located_ie --plan anthropic_budget --accept-senior-titles` (targets ONLY search-snippet persons failing residence; 0 targets at last run because the two snippet near-misses were re-classified). Do not widen FIRMS without re-harvesting (paid).

## Known honest gaps to state to Keith
Role 2 (Cork) yields zero under strict residence; the pool needs Cork-based transport leads from a licensed people-data source. Chartership registers cannot be automated. Alicia Joyce has no verified email (labelled "none"); her second-opinion pass returned nothing parseable twice and the card says so. `docs.jsonl` has 4 malformed lines (skipped with a log line; affected claims were dropped, the safe direction).

## Artifacts
Call brief https://claude.ai/code/artifact/e5cd1898-abd0-4f02-81c2-3eeef8c7c7be · Brief Controls https://claude.ai/code/artifact/3d47597e-04bd-42ec-bb15-ce6126b93703 · v2 page https://claude.ai/code/artifact/bc97d901-68da-4a96-9888-538dd8c65eed · corrected shortlist https://claude.ai/code/artifact/16f9282e-e30e-4a4b-b6e2-624d836a7e80
