# Human-eye verdict — GreenJobs demo (IE + UK), 2026-09-30

Scope under test: everything in Keith's document (39 checklist items) plus the two site-manager
requests of 2026-09-29 (package table = Premium posting + Membership only; full job-description
preview in the post-a-job builder), on BOTH editions. Skill: `.claude/skills/human-eye-test/SKILL.md`.

## Tier results (final run, commit under this verdict)

| Tier | Result | Count |
|---|---|---|
| 1 Automated (`run_all.py`: build + validate + scrape + gaps, node, dashboard DOM, layout) | PASS | 3,047 checks, 0 failed |
| 2 Layout regression (`layout.test.mjs`, 12 rules, 40 baselines) | PASS | 1,732 assertions, 0 failed |
| 3 Screenshot matrix (`human_eye_shots.cjs`, `human_eye_plan.json`) | PASS | 180 shots (30 page-states × 3 viewports × 2 themes), 0 health warnings (overflow, clipped, console, failed requests) |
| 4 Human-eye review (two reviewer agents read every PNG) | PASS after fixes | 186 images read; r4 raised 2 P2 + 6 P3; both P2 and 4 P3 fixed, 2 P3 accepted (below) |
| 5 Functional walk (`walk.js`, both editions, 1440/390) | PASS | 134/134 |
| 6 Panel (code-reviewer, pipeline-auditor, honesty lens) | PASS | code review PASS (0 critical, 2 test additions made); pipeline audit PASS with 2 doc warnings (both fixed) |
| 7 Verdict | this file | |

## Rounds

| Round | Defects found | Fixed | Notes |
|---|---|---|---|
| r1 (2026-09-29) | 37 (4 P1) | 37 | mobile table "Standard" column, map chips, stats mismatch across pages, closed/unverified job headers — `human_eye/DEFECTS.md` |
| r2 | 20 | 20 | separator pairs, dark carousel mask, Membership ticks, sterling source line, NI map label — `human_eye/DEFECTS_r2.md` |
| r3 | 13 (1 P1) | 13 | sticky thead at 1024, salary labels + currency prefix, dashboard copy/tile heights, single Location row, treemap labels, insights labels at 390 — `human_eye/DEFECTS_r3.md` |
| r4 (final) | 8 | 6 | see below |

## r4 defects and status

| Sev | Screenshot | Defect | Status |
|---|---|---|---|
| P2 | ie_dashboard_1440/1024_* | KPI tile descriptions clamped with ellipsis, methodology lost | Fixed: clamp removed; tiles stay equal-height per row |
| P2 | ie/uk_insights_390_* | Phone histogram used 5 bands, desktop and guides use 7 | Fixed: one band set everywhere (`SALARY_EDGES`); phone shortens labels to "20–30k" and alternates rows when 7 bands |
| P3 | uk_job-euro_* | Hero chip "United Kingdom (UK), Ireland (nationwide)" vs sidebar "Ireland & UK (nationwide)" | Fixed: chip uses the same label |
| P3 | ie_subscribe_* | "job alerts by email" said twice | Fixed: intro sentence dropped, quiet note kept |
| P3 | uk_home_1024 | snapshot chip loses pill outline when the stats strip wraps | Accepted: wrapped chip is still legible; revisit in the platform build |
| P3 | ie/uk_insights_1024 | histogram labels ~9 px at 1024 | Accepted: SVG scales with the card; readable, below the 1440/390 size. Platform build renders charts natively |
| P3 | ie_cookie-settings_* | initial focus on the close button | Accepted: WAI-ARIA dialog pattern allows first focusable; changing focus order is a platform-build item |
| P3 | ie vs uk employers hero | IE has no "from N employers" | Intentional: Keith's document asks for no employer count on IE (`emp_count_phrase`) |

## Coverage of the matrix
Pages/states: home, home-carousel, home-reduced-motion, jobs, jobs-facets, jobs-map, jobs-fit, job (euro, sterling, unverified), sectors, insights, compass, guides, landing, employers, employers-table, employers-preview, employers-longjd, dashboard, subscribe, cookie-settings, 404. Viewports 1440/1024/390; light/dark; reduced-motion on the carousel. Both editions where the page exists on both.

## Honest gaps
- Chromium in this container cannot reach the live Cloudflare host through the proxy; every shot is of the local build that is deployed byte-for-byte (`.greenjobs-build-ok` marker). Live verification is by HTTP fetch of both editions after deploy, not by screenshot.
- Real browsers other than Chromium (Safari, Firefox) were not exercised.
- The post-a-job builder is a preview only; nothing is submitted (by design, demo).
- Dashboard "wired" tiles show "—" until analytics exists on the platform build; the copy says so.
- 2 sterling twins remain "unverified" (figure mismatch on the source site) and are labelled as such on their job pages.
