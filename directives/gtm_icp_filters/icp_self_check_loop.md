# ICP Self-Check-and-Retry Loop — quality gate for lead scraping

Source: Nick Saraev course [4:00:18–4:01:51]; library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §4.

## Goal

Turn the manual "did this scrape actually hit my ICP?" eyeball check into a
self-correcting loop inside any lead-sourcing skill/script, so a bad filter
set fixes itself instead of shipping junk rows downstream.

## Inputs

- ICP definition (roles, firmographics). Course example roles: founder, CEO,
  co-founder, owner, co-owner, partner.
- A scraping source: Apollo (MCP, connected) / Google Maps / existing
  scrapers. (Apify actor is course-inherited and gated — no Apify account/MCP
  held.)

## Tools / Scripts

This is a methodology directive — no paired script by design; it wraps
whichever sourcing script is in play.

- Existing sourcing rails: `execution/lead_sourcing/` (e.g.
  `prospeo_leads.py`, `serper_maps_scraper.py`).
  (`execution/modules/sources/` is currently empty — owed.)
- ICP match judging: rubric design = `claude-fable-5`; per-row classification
  = `claude-sonnet-5` (model-tier rule).

## Outputs

A lead batch that has PASSED the sample gate, plus a log line per round:
`round N: sampled 20, matched M/20, verdict PASS/RETRY, filter delta: <...>`.

## Steps

1. Scrape an initial batch of 100 (minimum viable batch for the gate).
2. Sample 20 rows (random, not top-of-file).
3. Judge each sampled row against the ICP rubric.
4. **Gate: ≥15/20 (75%) must match.** Below threshold → adjust filters
   (roles, industry, size, geography) and re-scrape; repeat autonomously.
5. Cap retries (default 4 rounds — the course's live run converged
   9/20 → 9/20 → 15/20 → 19/20). On cap without passing: STOP and report,
   never ship the failing batch.
   **Paid-source gate**: when rounds consume credits (Apollo, paid scrapers),
   surface the estimated per-round cost in EUR and get operator sign-off (or a
   pre-agreed cap) BEFORE the retry loop runs unattended — per CLAUDE.md's
   self-anneal carve-out for paid tokens/credits.
6. Only after PASS: run enrichment/personalization on the full batch.

## Edge Cases

- **A ~100% uniform verdict is a failed run, not a finding** — if 0/20 or
  20/20 every round, suspect the judge or the probe, per
  `~/.claude/rules/probe-failure-is-not-a-verdict.md`.
- The judge must not reuse the scraper's own filter logic as its oracle
  (shared-oracle blind spot, `output-acceptance-gate.md` Exhibit B) — judge
  from the row's actual content.
- Sampling 20 of 100 leaves tail risk; for paid sends, the downstream
  output-acceptance gate still checks every row that gets a personalized
  email.
- Log every round; a silent retry loop that converges by luck is not a gate.
