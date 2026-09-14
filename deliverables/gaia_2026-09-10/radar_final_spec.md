# Gaia Radar — panel-revised final system (10 Sep 2026)

Seven lenses were run on `skyscraper_design.md` (Brockman, Cherny, Sutskever, Murati, Karpathy, Hormozi, Saraev). This is the system that survived. Verdicts converged on four points: ship narrower than the draft, put a human approval gate before any contact, make the eval independent and numeric, and sell placements not a pool.

## Bottleneck (Saraev, Hormozi, Sutskever agree)
Gaia's constraint is precision and consultant follow-up capacity, not sourcing volume. Keith's words: cut the wheat from the chaff, replies at ~3%, run 50–100 jobs on two consultants. The product optimises one number: first conversations per 10 sourced-and-gated candidates, read from Recruit CRM stage transitions, not from our own counts. Secondary: approved-candidate rate.

## What ships Monday (must-ship)
1. Brief Contract per job, versioned; every shortlist names its brief version; off-limits list lives in the brief and re-gates on every re-cut.
2. Sources for the live roles only: public records, firm directories, Engineers Ireland / IStructE / ICE registers, one licensed people-data provider chosen by a Friday go/no-go test (≥40 matched Irish profiles per niche with title, employer, dates). Written fallback: registers + directories + bylines, pool labelled "directory-sourced, N of est. M".
3. Provider contract before any new source: `SourceProvider.fetch(query) -> list[RawDocument]`, `cost_eur`, `rate_limit_s`, `text_source`; all HTTP through `core/cache.py`; fixture-first contract tests per provider; no network in CI.
4. Identity resolution as a pure function with a collision fixture suite (same name/different firm; same firm/different person) before it touches the pipeline.
5. Gates: existing five plus ceiling, plus two new checks from Karpathy: a years figure must be grammatically the person's, not the firm's; a title-derived grade needs a second source or a years figure before it alone passes.
6. ICP sample check between sourcing and gating: sample 20 per source batch, ≥15 must match the brief, else adjust the source filter before spending on contact.
7. Movability: deterministic rules, labelled "unvalidated" in the console until a backtest exists; a ranking hint, never a drop.
8. Contact: verified or catch-all only; contact blocked if the employer/title claim is older than 14 days without corroboration (stale-employer risk).
9. Outreach: human-approved template pool built from Gaia's own past notes; four fuzzy variables (project they gave evidence on, mutual scheme or firm, movability signal phrase, chartership year). Every draft sits in "pending consultant approval"; the opt-out registry and off-limits gate run at draft creation, not only at reply time. Nothing sends from Prodcraft.
10. Recruit CRM hand-off through the single `_write` chokepoint (dry-run default, audit, cap). Interested → stage Screening → Maddie's existing trigger.
11. Console, task-first: Today (approvals pending, new movable signals, replies needing action), Job shortlist with Brief Controls, Candidate card (evidence quotes, sources, movability, draft with Approve), Pool map. Badges on every page: LIVE / CACHED / STUB. Health banner per pool and integration.
12. Scorecard, six numbers: composition violations (must be 0), quote-drop rate, grade precision, residence precision, delivered / pool, cost per delivered card. Labels: two independent labellers (Deb and a blind Sonnet prompt that never sees extractor output) on a 30-profile subset, Cohen's kappa reported; ship threshold ≥90% grade precision.
13. Learning loop wiring (logging only this week): outcome per (candidate, template_id, movability_bucket) into the audit log; weekly job reports reply and placement rate per template and bucket; templates rotate by weight, never rewritten by a model; a `correction` claim type when a consultant or reply contradicts a stored claim.
14. Modal endpoint for live re-cut: read-only against cached gate output, writes to its own namespace, never the stage files; pre-warmed before the demo, with a recorded fallback.

## Cut from Monday
Client Radar (BD is Gaia's revenue activity; not promised). Extra niches beyond the live roles. Gmail draft creation unless Keith consents by Friday (copy-ready text is the default). Movability backtest claims. Console pages for empty niches. "Gaia owns the code" as a pitch line.

## Loom storyboard (5 minutes)
0:00 a real job pasted into the Brief Contract. 0:30 re-cut fires live; shortlist renders with evidence quotes. 1:30 one candidate card: quote, source, movability, draft, Approve. 2:30 the CRM sync log (dry-run) and where Maddie picks up. 3:30 the scorecard number and the honest denominator. 4:30 the corrected 20-Aug list as the "we listened" callback, then the two questions for Keith.
Lead image for the email: one candidate card with "replied, in CRM, stage Screening" if a real reply exists by Monday; otherwise the corrected shortlist.

## Offer (after the demo, one sentence)
"For €X per niche per month, Radar puts three movable-now, evidence-checked candidates in front of you within 24 hours of any role in that niche. Cancel any month, and if you don't get three approved candidates in the first 30 days you pay nothing."
Unit: per niche per month. Anchor: less than one Recruit CRM Business seat, against one €14–20k placement. Gaia owns the pool and the data; Prodcraft runs the engine. Charge from day one, small, with the no-fee clause; do not offer a second free pilot.

## Ladder
Brief Contract, gates, contact: Skill (run per role with review). Pool refresh, movability: Loop. Nothing becomes a Routine until the ICP check runs clean for weeks. Outreach sending: never.

## Directive
`directives/gtm_client_workflows/gaia_sourcing.md` to be created (needs operator approval): invariants I1–I9, stage/cache/lock model, provider contract, "no HTTP outside core/cache.py".
