# Test tiers

Four tiers, cheapest to most-expensive, all mandatory before "shipped."

| Tier | Runner | What it proves | Cost |
|---|---|---|---|
| **1. Unit** | `npm run test:unit` (Vitest) | Pure functions behave. No network, no build. | ms |
| **2. E2E** | `npm run test:e2e` (Playwright) | Browser can render key routes and interact. Runs against `astro dev`. | seconds |
| **3. Acceptance** | `npm run test:acceptance` | LIVE `$SITE_URL` responds with the right SHAPE + CONTENT. Frozen corpus. Per `~/.claude/rules/output-acceptance-gate.md`. | seconds |
| **4. Front-door synthetic** | `npm run test:frontdoor` | LIVE `$SITE_URL` serves a real user flow end-to-end. Per `~/.claude/rules/front-door-synthetic.md`. | seconds |

## Why four?

Each tier catches a bug class the others miss:

- Unit tests catch bugs in **pure logic**. Cannot detect deploy-drift.
- E2E tests catch bugs in **local page render + JS**. Cannot detect prod-only issues (missing secrets, CF Function untracked in git).
- Acceptance tests catch bugs in **the SHAPE of what production actually serves** (empty fallback vs real data, wrong copy, stale content).
- Front-door tests catch bugs in **the USER FLOW** — auth, redirects, form submission, 3rd-party integrations.

A green tier-1 build with a red tier-3 acceptance is a **shipped-broken project**. See `~/.claude/rules/live-artifact-acceptance.md` exhibit A (yoga_jitendra, 13 days of stale fallback).

## Order of authorship

Write acceptance test **before** writing the feature (per `~/.claude/rules/eval-first.md`).
