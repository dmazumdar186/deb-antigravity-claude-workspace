# Test plan: ASSET demonstration (5 Nov 2026)

**Scope:** the five stories in `21_Acceptance_Gates_5_Stories.md`, tested on:
- **Option A**: the WordPress plugin `wp_demo/`, run in WordPress Playground.
- **Option B**: the custom platform `custom_demo/`, live at https://asset-voyages-demo.debanjan186.workers.dev.
- **The hub page** `site/demo/`.

**Delivery rule:** nothing is sent until every row below is PASS on both options. Every test case must be in the register, `25_Test_Register.md`, with its evidence. The extra idea (`23_`) is built only after that, and only if there is time.

**Register format:** one row per test case, with these columns:
`ID | Type | Option | Story/gate | Steps | Expected | Actual | Evidence (file/log) | Status | Run date`.

IDs are `<TYPE>-<A|B|H>-NNN`, for example `UNIT-B-004` or `MONKEY-A-002`.

## Test types, pass criteria, tools

| # | Type | What it covers | Pass when | Tool / owner |
|---|---|---|---|---|
| 1 | **Unit** | Pure logic: input validation (dates, passenger count 1–50, email, consent), CSV formula escaping, reference numbering, code encryption and decryption round-trip, mask formatting, the role/permission matrix, throttle counters, the status state machine (allowed and refused transitions). | 100 % of cases pass; every validator has a boundary case on each side (0/1, 50/51, same day/day before). | B: `node --test`. A: a PHP CLI harness over the plugin classes, run under `php`. Worker: test engineer. |
| 2 | **Integration** | Server and database together: a form POST creates a row, a status change writes history, an approved grant allows a reveal, a revoked grant refuses it, a reset restores the seed, and editing a seed record copies it without touching the original (B). | All pass against a fresh local instance (`wrangler dev` with D1 / Playground CLI). | Playwright `request` + curl. Test engineer. |
| 3 | **End-to-end** | Every gate in S1–S5 and X1–X4, through the real UI. | All gates PASS locally **and** on the deployed URL. | Existing builder suites, re-run by the test engineer, not the builder. |
| 4 | **Smoke** | After every deploy: catalogue, a congress page, the console login page and the hub return 200; each role can log in; one enquiry goes in and shows up in « Demandes ». | 100 % in under 2 minutes; run after every deploy. | `qa/smoke_<A|B>.mjs`. |
| 5 | **Sanity** | After every fix: the touched story's gates plus the smoke test. | Pass before the full re-run. | Same suites, filtered. |
| 6 | **Performance** | Public catalogue and congress page: TTFB, LCP, CLS and page weight at 1440 and Pixel 7 (slow 4G profile); 30 concurrent catalogue requests (gentle; free tier) giving p50/p95; console list pages. A: Playground boot time measured and reported honestly (it runs in the browser). | B: LCP ≤ 2.5 s on mobile profile, CLS ≤ 0.1, p95 ≤ 800 ms, no 5xx. A: the same targets measured after boot; boot time stated as-is. | Playwright performance APIs + Lighthouse if available (Chromium at `/opt/pw-browsers/chromium`). |
| 7 | **SAST** | Static analysis of every source line: PHP (plugin) and JS (Worker, hub); secret scanning of the repo diff; dependency audit. | 0 high/critical findings; each medium either fixed or waived with a reason; 0 secrets. | `semgrep` (rulesets: php, javascript, owasp-top-ten, secrets), `npm audit --omit=dev`, `php -l`, a grep for `eval(`, `innerHTML`, `$wpdb->query(` without `prepare`. |
| 8 | **Security (DAST)** | Security headers, cookie flags, CSRF on every POST, the full 3×N authorisation matrix (logged out / contributeur / equipe / direction × every route), IDOR, session fixation, login throttle, error pages leaking nothing. | Every cell matches the expected allow/deny; headers present. | Probe scripts under `qa/security_<A|B>/`. |
| 9 | **Adversarial** | A blind red team tries to steal a GM&E code, read enquiries, deface the public site, bypass validation, inject script or formulas. | No HIGH or MEDIUM findings open. B: re-run after fix round 1. A: first run. | `pipeline-auditor`. |
| 10 | **Monkey** | Random clicks, typing (unicode, emoji, long strings, script and formula payloads), back/forward and resize, 300 actions per role per option, seeded and reproducible. | 0 5xx, 0 uncaught console errors, 0 codes leaked into any DOM snapshot, no dead ends (always a way back). | `qa/monkey_<A|B>.mjs` (fixed seed, logged replay). |
| 11 | **Usability** | Click budgets (the E gates) measured by a first-time user who follows only the labels; Nielsen's 10 heuristics; plain-language labels; error recovery. | Every E gate is within budget; no heuristic rated "severe". | UX reviewer agent. |
| 12 | **Accessibility (part of UX)** | axe-core on every screen; keyboard-only run of each story; focus visible; contrast. | 0 serious/critical axe violations; every story completes by keyboard. | `@axe-core/playwright` (npm, free). |
| 13 | **UX/UI + human eye review** | Screenshots of every story at 1440 and 390, read by an independent reviewer: clipping, overflow, French typography, consistency, polish. | Reviewer verdict SHIP. | Eye reviewer (X6). |
| 14 | **UAT (internal)** | Scripted scenarios written as Veena would run them: one per story, visitor side and team side, run step by step by a reviewer acting as a non-technical office assistant on the deployed demos, with a sign-off sheet. | All scenarios PASS; the sign-off sheet is completed in `26_UAT_Signoff.md`. This is internal UAT; the client's UAT is part of the project (T01–T15). | UAT agent. |
| 15 | **Hub page** | Links to both options work; the X7 items are present; the recordings play; the Hallmark gate passes; eye review SHIP; `/redteam` on the text. | All pass. | Existing `research/demo_page.mjs` + reviewers. |

## Order

1. Builders finish. Option A local suite green; Option B live suite green.
2. **In parallel, for each option:** test engineer (types 1–7, 10), security and adversarial (8–9), UX and UAT (11–14).
3. Fix defects; sanity tests; full re-run of the affected types.
4. Recordings of both walkthroughs (taken only once the UI is final); hub eye review; `/redteam` on the hub and the email.
5. Register complete, every row PASS, results summarised in `22_Acceptance_Results.md`.
6. Deliver the links. Only then, if there is time, the extra (`23_`).
