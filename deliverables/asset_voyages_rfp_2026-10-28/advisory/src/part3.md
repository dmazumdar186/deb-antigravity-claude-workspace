
# 6. Build plan

## 6.1 Contracts before code

Before the first line of product code (week 1), we write and freeze a `CONTRACTS.md` for the project, following our existing pattern. It is the reference every module and every AI-assisted implementation session is held to.

| Contract | Content |
|---|---|
| C0 Scope | The prototype table (every visible element: included / optional / illustration), section-type list, page and listing counts, T01–T15 annex |
| C1 Schema | Drizzle schema for both databases (§4.1), migration policy (expand/contract) |
| C2 API | Every route: method, path, role, Zod input/output, errors |
| C3 State machines | Transitions, guards, side effects (§4.2) as a typed table, tested |
| C4 Invariants | I-1 … I-8 with their tests (§4.3) |
| C5 Adapters | `EmailProvider`, `Store`, `Clock`, `AIProvider` interfaces, each with a mock |
| C6 CSV v1 | Columns, formats, error codes, duplicate rules |
| C7 Events | Beacon event names and whitelisted properties |
| C8 Ops | Backup, restore, export, deploy, rollback commands |

## 6.2 Walking skeleton (week 1–2)

A thin end-to-end slice deployed to staging, before any feature depth: one Astro page from one `block` → one form (F01) → D1 insert → queue → email via the adapter → Console behind Access listing that enquiry → publish button triggering a rebuild → nightly backup → restore into a fresh D1 → CI with leak scanner, axe and Lighthouse on that one page. It exists to measure the unmeasured: the rebuild time N, the Access + JWT path, the D1 export size and restore time, and the real speed of Console development.

## 6.3 Modules

| # | Module | Content | Est. hours | Owner |
|---|---|---|---|---|
| M1 | Audit and discovery (L0) | Crawl tool, inventory, account register, baseline, workshop, architecture doc | 12 | Debanjan |
| M2 | Design system and mock-ups | Tokens, ≈ 15 components, 8 templates, wireframes, mock-ups 375/1440, prototype | 24 | Debanjan |
| M3 | Public pages | ≈ 20 pages + 3 legal from templates, content integration | 20 | Debanjan |
| M4 | Forms F01–F06 | Three forms, validation, Turnstile, dedup, durable save, email adapter, fallback | 12 | Debanjan |
| M5 | Enquiry back-office | Inbox, statuses, owner, history, logged export, routing | 12 | Debanjan |
| M6 | Measurement + GDPR | Beacon, dashboard, consent, legal pages, DSR | 8 | Debanjan |
| M7 | Console core | Access + roles, block editor (fixed section types), media, revisions + restore, soft delete, audit log, publish pipeline | 44 | Debanjan |
| M8 | Catalogue (public) | Search index, filters, pagination, listing template, past-event rule, `Event` schema, sitemap | 14 | Debanjan |
| M9 | Catalogue (admin) + vault | Congress form, CSV import, exports, editorial + GM&E state machines, encryption, leak scanner | 18 (21 on detailed count) | Debanjan |
| M10 | SEO migration | Redirect generator, chain test, Search Console | 12 | Debanjan |
| M11 | Infrastructure | Envs, CI, backups, drill, monitoring, break-glass | 12 | Debanjan |
| M12 | QA and acceptance | T01–T15, a11y manual, CWV lab, ZAP, acceptance report | 22 | Debanjan (+ independent reviewer agents) |
| M13 | Handover | Guide, runbook, inventory, training ×2, transfer package | 10 | Debanjan |
| M14 | Project management | Weekly written updates, milestone packs, revisions, change control | 18 | Debanjan |
| | **Total core** | | **238** (+ 48 contingency = 286) | |

Every module is one person. The "team" is the founder plus AI-assisted implementation and independent reviewer agents. There is no second human engineer today.

## 6.4 Test strategy

| Tier | Tool | What | When |
|---|---|---|---|
| Unit | Vitest | State machines, permissions matrix, dedup, CSV parser, redirect generator, encryption round-trip | Every push |
| Integration | Vitest + Miniflare / local D1 | Routes against real local D1, adapters mocked and real | Every push |
| E2E | Playwright | Journeys J-1…J-5; Console flows; T01–T10 automated | Every preview deploy |
| Acceptance | T01–T15 suite + report generator | Evidence (screenshots, DB rows, logs) compiled into the acceptance report | J3, J4, J5 |
| Accessibility | axe-core in Playwright; manual NVDA/VoiceOver script | 0 serious violations; manual 5 journeys | Every preview; manual at J3, J5 |
| Performance | Lighthouse CI (lab) per template | LCP ≤ 2.5 s, CLS ≤ 0.1, TBT budget as INP proxy | Every preview |
| Leak test | Scanner over build output + public API responses with seeded canary | 0 matches, canary found in the vault fixture | Every build (blocks deploy) |
| Security | SAST hooks, `npm audit`, ZAP baseline | No HIGH/CRITICAL | push; ZAP at J3, J5 |
| Restore drill | Script + stopwatch | Elapsed ≤ RTO; smoke suite green on restored DB | J5, then monthly |
| Front-door synthetic | Bash probe against live URL | 5 consecutive green days before calling it "live" | From cutover |
| Human-eye gate | Screenshot every page/state/viewport, reviewer reads each | PASS or defect list | J2, J3, J5 |

## 6.5 CI gates

A pull request cannot merge unless all pass: typecheck → lint → unit → integration → build → leak scanner → SEO lint (one H1, titles, canonicals, hreflang, no internal status words) → preview deploy → E2E → axe (0 serious) → Lighthouse (thresholds per template) → front-door on preview. Pushes also run workspace SAST (blocks HIGH/CRITICAL). Main is protected; deploy to prod only from tagged releases.

## 6.6 Definition of done per milestone

| Milestone | Done when |
|---|---|
| J0 | Signed proposal and deposit cleared; RACI; access inventory sent; schedule with dates; repo and Cloudflare account created in ASSET's name; written approval |
| J1 | Crawl inventory with decision column; account register; baseline (CWV lab, trackers, forms, Search Console); architecture doc; backlog; risk register; walking skeleton on staging; written approval |
| J2 | Wireframes + mock-ups for 8 templates at 375 and 1440; prototype link; design-system page; claims register started; ≤ 2 revision rounds; written approval |
| J3 | All L1 pages on staging from Console content; F01/F02 pass T01–T02; tracking events verified; axe 0 serious; Lighthouse within targets; Console editing usable by Veena; written approval |
| J4 | 300 listings imported (or ASSET's file, with rejection report); T03–T08 pass; vault + leak test green; written approval |
| J5 | Redirect map approved and T10 green; T01–T15 all pass; acceptance report delivered; training session 1 done; restore drill timed; rollback plan; written acceptance (or deemed after 5 working days); payment cleared; written go; DNS cutover |
| J6 | 4 weeks: daily checks, Search Console weekly, fixes, outstanding-items list closed, training session 2, handover pack complete (repo, accounts, secrets rotated, exports), closure document |

## 6.7 Handover as a product

The client's essential conditions include supplier handover. We treat it as a feature with its own acceptance:

| Item | What ASSET gets | Test |
|---|---|---|
| Media upload | Upload with required alt text and rights note | Veena uploads during T15 |
| CSV dry run | Self-serve import with report | Veena imports a 10-row file |
| One-click export | ZIP of all data + media + manifest | T14 |
| Restore | Runbook + script; drill record | T13 |
| Per-screen help | Short help panel on every Console screen | Review |
| Generated guide | Illustrated admin guide generated from the Console's own screenshots | Veena follows it in T15 |
| Training | Two remote sessions (Veena, backup editor), recorded; second session 4 weeks after launch | Attendance |
| Runbook | Deploy, rollback, restore, export, rotate secrets, add a user; written for a stranger at 6 a.m. | A person not involved follows it |
| Inventory | Every account, owner, plan, cost, renewal date | Signed |
| Transfer package | Repo, docs, inventory, secrets transfer via password manager, a defined period of transfer assistance (to set in the proposal) | Checklist |

**Operations without us.** Nightly backup, monthly restore drill, external monitor and dependency PRs run on schedules, not on the founder's memory. If ProdCraft stops, the site keeps running on ASSET's accounts; what stops is patching and support.

## 6.8 Questions for the reviewers

1. Is a walking skeleton in weeks 1–2 realistic alongside the L0 audit, or does it delay J1?
2. Which CI gate would you drop as cost without benefit at this scale? Which is missing?
3. Is our definition of done for J3 strong enough to stop us declaring the Console done before Veena can use it?
4. How would you test "a stranger can follow the runbook" credibly?

# 7. Effort, timeline, price

## 7.1 Hours

Two estimates exist; both are **estimates by analogy** with past builds, not measured on this stack.

| Work item | `effort_estimate.md` | `03_` reconciled |
|---|---|---|
| L0 audit | 8 | 12 |
| Design system, mock-ups, prototype | 16 | 24 |
| Public pages | 24 | 20 |
| Forms F01–F06 | 12 | 12 |
| Enquiry back-office | 12 | 12 |
| Console core | 40 | 44 |
| Catalogue public | 14 | 14 |
| Catalogue admin + vault | 18 | 18 (21 detailed) |
| SEO migration | 8 | 12 |
| GDPR + consent + measurement | 6 | 8 |
| Infrastructure | 10 | 12 |
| QA and acceptance | 16 | 22 |
| Handover | 10 | 10 |
| Project management | 25 | 18 |
| **Core total** | **≈ 220** | **238** |
| Contingency 20% | 44 | 48 |
| **Planning figure** | **≈ 265** | **286** |

Options (hours): English activation 8 · CRM connector 6 · Wondermiles feasibility 4 / SSO 12 · AI ingestion 16. The largest single uncertainty is the Console (40–44 h): it has no prior code and is where a one-person estimate is most likely to be wrong by a factor.

## 7.2 Included quantities

Up to 20 content pages from ≈ 8 templates + 3 legal pages; up to 300 listings imported from ASSET's spreadsheet; copy supplied or approved by ASSET, migrated with light editing; 2 revision rounds per design stage and per content stage; 2 training sessions; 4-week stabilisation.

## 7.3 Calendar

Assumptions: signature and deposit by Fri 13 Nov 2026; start Mon 16 Nov; approvals within 3 working days; Christmas slow period 21 Dec–1 Jan, no launch in it. Lean pace ≈ 35 h/week; conservative ≈ 22 h/week plus realistic client delays. **These are estimates.** We intend to contract the conservative dates.

| Milestone | Lean (≈ 9–10 weeks to launch) | Conservative (≈ 13–14 weeks) |
|---|---|---|
| J0 Kickoff approved | Fri 20 Nov 2026 | Fri 20 Nov 2026 |
| J1 Audit approved | Wed 2 Dec | Wed 2 Dec |
| J2 UX/UI approved | Wed 16 Dec | Fri 8 Jan 2027 |
| J3 Core site on staging | Fri 15 Jan 2027 | Fri 5 Feb |
| J4 Congresses | Fri 22 Jan | Fri 19 Feb |
| J5 Acceptance + cutover | Week of 25 Jan | Fri 12 Mar |
| J6 Stabilisation ends | Fri 26 Feb | Fri 9 Apr |

Building in 4–5 weeks is only possible by cutting scope (for example, Console editing limited to text and images; GM&E workflow as statuses only).

## 7.4 Price options and market evidence

| Option | Build HT | Plan HT | Effective build rate (265 h) |
|---|---|---|---|
| Lean | €4,000 | €600/mo, 12 min | ≈ €15/h |
| **Recommended** | **€7,500** | **€600/mo, 12 min** | ≈ €28/h |
| Fair solo | €9,500–12,000 | €600–750 | ≈ €36–45/h |
| Market (small agency) | €18,000–25,000 | €750–900 | ≈ €68–94/h |

Market evidence (`D/research/market_pricing_paris_2026.md`; mostly search-engine summaries, some second-hand; **verify before quoting**):

| Evidence | Figure | Source |
|---|---|---|
| Experienced Paris full-stack freelance day rate | ≈ €520–600/day (median ≈ 525–560) | Malt barometer 2026, TJMetre 2026, Freeland 2026 |
| Small agency day rate (5–15 people) | €550–800/day | La Fabrique du Net 2026 (summary) |
| Custom site with back-office and APIs | from €8,000 | Agence2web 2026 |
| Medium web app | €20,000–50,000 | Seedweb 2026 |
| Maintenance, multi-page corporate WordPress | €100–350/month | Make Different, Ellebay 2026 |
| Out-of-contract hourly | €60–150 HT | Ellebay, Make Different 2026 |

At 265 h, even the recommended price is ≈ 5% of a freelance day-rate equivalent (265 h ≈ 38 days × €550 ≈ €21k). The plan fee is above the WordPress maintenance range because it includes hosting, tools, SLA, backups, drills and 5 h of changes.

## 7.5 Three-year total cost of ownership (core only, HT)

| Option | Build | Plan 36 months | 3-year total | TTC (20% VAT) |
|---|---|---|---|---|
| Lean | 4,000 | 21,600 | 25,600 | 30,720 |
| Recommended | 7,500 | 21,600 | 29,100 | 34,920 |
| Market low | 18,000 | 27,000 | 45,000 | 54,000 |
| Market high | 25,000 | 32,400 | 57,400 | 68,880 |

The RFP asks for this figure explicitly and says not to count a service twice; tool costs are inside the plan.

## 7.6 Running costs (paid by ProdCraft inside the plan; accounts in ASSET's name)

| Item | Monthly (estimate, Oct 2026 prices) | Source |
|---|---|---|
| Workers Paid (incl. D1, Queues, Time Travel 30 d) | $5 ≈ €4.3 | Cloudflare pricing pages, 28 Oct 2026 |
| D1, R2, Access (≤ 50 users, unverified on Cloudflare's page), Turnstile, Web Analytics | €0 at this size | Cloudflare docs |
| Brevo (300/day free; Starter if needed) | €0–9 | Brevo |
| Resend (fallback, free tier) | €0 | Resend |
| UptimeRobot (free; Solo optional) | €0–10 | UptimeRobot |
| Off-platform backup store | TBD (not yet chosen or priced) | — |
| Domain | ≈ €9–32/year | estimate |
| AI helper (L4 only) | €5–20 | own estimate |
| **Total** | **≈ €5–15/month; up to ≈ €25 with paid monitoring** | |

## 7.7 Questions for the reviewers

1. Is €7,500 + €600/month a credible bid, or is it so low it signals risk to a procurement panel? Would you go to €9.5k+?
2. Is the 20% contingency enough for a one-person build with a never-built Console?
3. Is contracting the conservative calendar the right call in a competitive bid where a rival may promise 10 weeks?

# 8. Risk model and grading

## 8.1 Complexity

A weighted function-point style score: each module's share of effort (weight) times a complexity rating from 1 (trivial, done many times) to 10 (novel, hard to test). Ratings are our judgement. The original table was produced in session; this is a reconstruction that reproduces the stated score.

| Module | Weight | Complexity (1–10) | Contribution | Why |
|---|---|---|---|---|
| Public pages | 0.15 | 3 | 0.45 | Template, done before |
| Forms + dedup + fallback | 0.10 | 6 | 0.60 | Async email, two providers, durable save |
| Enquiry back-office | 0.08 | 5 | 0.40 | CRUD + history |
| Console editor, media, versions | 0.22 | 8 | 1.76 | New; UX for non-developers; rebuild loop |
| Roles, MFA, audit | 0.10 | 7 | 0.70 | Access JWT + matrix |
| Catalogue public | 0.08 | 4 | 0.32 | Pattern exists |
| Catalogue admin + import | 0.10 | 7 | 0.70 | Dedup, dry run, idempotency |
| GM&E vault + workflow | 0.07 | 8 | 0.56 | Encryption, isolation, leak proof |
| SEO migration | 0.05 | 7 | 0.35 | Unknown URL count; client approval |
| Infra, backups, monitoring | 0.05 | 7 | 0.35 | Never run restore drill on D1 |
| **Total** | **1.00** | | **≈ 6.2 / 10** | |

## 8.2 Confidence model

We model on-time, in-scope delivery to J5 acceptance as the probability that **none** of a set of independent risks materialises badly enough to break the contracted date or scope:

<p class="formula">P(success) = Π<sub>i</sub> (1 − r<sub>i</sub>)</p>

where r<sub>i</sub> is the residual probability, after mitigation, that risk *i* causes a contract-level miss. Independence is an assumption and is optimistic: late client inputs and founder availability are correlated through the calendar. The r<sub>i</sub> values are our judgement; the table reconstructs the session's model and reproduces its stated totals (≈ 0.73 conservative, ≈ 0.55 lean).

**Please put your own number in the last column.**

| # | Risk | Mitigation | r (conserv.) | r (lean) | Your r |
|---|---|---|---|---|---|
| R1 | Client inputs late (content, CSV, approvals, access) | Defaults; deemed approval; day-for-day shift; pause clause; weekly written chase | 0.08 | 0.14 | |
| R2 | Founder availability (illness, overload; single point of failure) | Conservative calendar; runbook; repo in client's name; no backup developer yet | 0.07 | 0.11 | |
| R3 | Console scope overrun | Fixed section types; walking skeleton measures speed in week 1–2; scope-cut list ready | 0.03 | 0.08 | |
| R4 | Current-site access / DNS / domain ownership blocked | Ask at J0 (Q4, Q5); what-to-ask template; parallel build | 0.03 | 0.05 | |
| R5 | GM&E vault design flaw or leak | Structural isolation; encryption; leak scanner with canary; role tests | 0.01 | 0.01 | |
| R6 | SEO migration loses a critical URL | Crawl + GSC data; chain test; T10; weekly monitoring | 0.02 | 0.03 | |
| R7 | Platform limitation (D1, Access, Workers) discovered late | Skeleton exercises every binding early | 0.01 | 0.02 | |
| R8 | Notification failure in production | Two providers; durable save; banner | 0.01 | 0.01 | |
| R9 | Acceptance dispute / test redefinition | T01–T15 frozen in annex; deemed acceptance; defects only against tests | 0.01 | 0.03 | |
| R10 | CSV data quality from client | Template; dry run; rejection report; research excluded | 0.01 | 0.03 | |
| R11 | Backup/restore fails at drill | Drill in skeleton and at J5; Time Travel as second layer | 0.01 | 0.02 | |
| R12 | Scope creep | Change control paid first | 0.01 | 0.04 | |
| | **P = Π(1 − r)** | | **≈ 0.735** | **≈ 0.552** | |

Reading: on the conservative calendar we estimate roughly a 3-in-4 chance of hitting J5 on the contracted date and scope; on the lean calendar, about even. The two largest residuals (R1, R2) are not engineering risks. The model does not cover the risk of **losing the bid**, nor post-launch defects.

## 8.3 The 11-lens panel pass on this plan

Each lens is an analytical stance, named after a public figure's known emphasis (`.claude/memory/panel_roster.md`). They are not quotes and not endorsements.

**1. Karpathy (measurement).** The plan is better instrumented than most: every acceptance test has a dataset and an expected result, and the KPIs in §9 name a tool. But the inputs to the plan are not measured. The 238/286 h estimate is by analogy; the Console has never been timed; the rebuild delay N and restore time are unknown. *Honest gaps:* no enquiry baseline yet; field CWV may never exist for a site this size; the risk probabilities are judgement, not data. The walking skeleton is the first real measurement and should re-base the estimate at J1.

**2. Cherny (tooling craft).** Contracts before code, adapters with mocks, idempotent imports, deterministic gates in CI: this is the right shape for AI-assisted building. *Honest gaps:* the crawl→redirect tool, leak scanner, Lighthouse/axe gates, backup cron and restore drill do not exist; each needs a directive and a `--mock` test before it can be trusted. The weekly-update script is assumed, not built.

**3. Dario Amodei (honesty, legal exposure).** The plan avoids unprovable claims: no fare wording without written GM&E confirmation, claims register, verbatim quotes only. *Honest gaps:* CNIL retention guidance and Google's Event structured-data policy are cited from memory; the DPA is not drafted; whether prior builds were commissioned or concept work must be stated precisely in references; "deemed acceptance" must be worded so it is not misleading.

**4. Anthropic research (rigour).** Definitions are mostly precise (duplicate keys, state guards, thresholds). *Honest gaps:* the duplicate rule, past-event rule and retention periods are proposals awaiting approval; the L4 eval set does not exist; model and prompt pinning for L4 is designed but not implemented; the confidence model assumes independence it does not have.

**5. Hormozi (offer, economics).** Risk reversal runs both ways (free fixes against T01–T15; deemed acceptance). *Honest gaps:* at €7.5k the build is ≈ €28/h; the economics only work if the 12-month term holds and the Console is reused for the next client. There is no travel/MICE reference, so perceived likelihood rests on the concept site.

**6. Saraev (automation boundaries).** Human decisions are kept where the client feels them: approvals, publication, GM&E stages, acceptance. L4 is a supervised scheduled skill, not an agent. *Honest gaps:* there is no error channel yet for scheduled jobs; the redirect map and CSV import must be checked by an ASSET human before they count.

**7. Daniela Amodei (people, trust).** Accounts in the client's name, transparent costs, strikable credit request. *Honest gaps:* no named holiday or sickness cover; support is business hours only; the reply-time promise to enquirers is unknown (Q15); the 12-month minimum must be visible, not buried.

**8. Sutskever (failure modes).** The vault is protected structurally, not by convention. *Honest gaps:* the leak scanner only catches codes it knows; a code typed into a congress description would be caught only because all public output is scanned for every stored code, which must be implemented and tested exactly that way. L4 hallucination bounds are designed, not tested.

**9. Murati (user experience).** The concept proves the public journey on phones. *Honest gaps:* the MICE progressive brief and listing hierarchy are unvalidated with real buyers; the Console UX for a non-technical editor is the least proven part of the whole plan; real-device testing depends on which devices the founder owns.

**10. Brockman (reliability).** Atomic deploys, instant rollback, Time Travel, dead-man alarm. *Honest gaps:* the second backup provider is not chosen or priced; an Access outage takes the admin down (accepted); there is no on-call; the restore drill has never been run on this stack.

**11. Hassabis (long-horizon).** The plan compounds only if the Console is built as a product with ASSET as its first tenant and ASSET-specific code kept separate. *Honest gaps:* there is no plan yet for the second tenant; reuse value is asserted, not demonstrated.

## 8.4 The five-expert view

| Expert | View on this plan | Main concern |
|---|---|---|
| Senior Product Manager | Requirements are fully mapped; defaults turn ambiguity into decisions | The client may experience defaults and deemed approvals as pressure; proposal tone matters |
| Senior Product Designer | Concept is strong; design system scope is right-sized | Console design for Veena is under-specified compared with the public site |
| Senior Solution Architect | Modular monolith, vault isolation and EU D1 are sound for the scale | Single-vendor concentration; second backup location undecided; Directus trade-off should be tested, not argued |
| Senior UX/UI Designer | Journeys are short (≤ 2–3 clicks); axe-clean concept | Progressive MICE form and editor need usability testing with real users |
| Senior Full-Stack Developer | Stack is standard and maintainable by others | 44 h for a block editor with versions, media and preview is optimistic; spike it first |

## 8.5 Questions for the reviewers

1. Please re-score R1–R12 in the table and add any risk we missed.
2. Is the complexity score's weighting of the Console (22% weight, 8/10) right?
3. Is P = Π(1 − r) a reasonable model here, or would you use something else (for example a reference-class forecast)?

# 9. KPIs and acceptance metrics per stage

Each KPI has a target, a measurement method, a tool and an owner. "Baseline" means measured, not targeted.

## 9.1 J0 Kickoff

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| Access inventory completeness | 100% of listed accounts (domain, DNS, hosting, email, GA, GSC, GBP) with named owner and access status | Account register; count filled / total | Debanjan, Veena |
| Accounts created in ASSET's name | 100% (GitHub org, Cloudflare, Brevo, monitor) | Register + screenshots | Debanjan |
| Deposit cleared | Yes before work | Bank | Debanjan |
| Schedule approved | Written | Email | Management |

## 9.2 J1 Audit and discovery

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| URL inventory | Count of crawled URLs (baseline) with 100% assigned a decision | Crawl tool + decision sheet | Debanjan |
| Search Console coverage | Top pages by clicks covered in the map: 100% of URLs with ≥ 1 click in 16 months | GSC export | Debanjan |
| Baseline CWV (lab) | LCP, CLS, TBT on 5 key pages recorded | Lighthouse | Debanjan |
| Tracker inventory | Count of trackers and tags found | Network log crawl | Debanjan |
| Forms inventory | Count and destinations | Crawl + manual | Debanjan |
| Skeleton measures | Rebuild time N, restore time, Console velocity recorded | Stopwatch, CI logs | Debanjan |
| Estimate re-baselined | Yes, with delta vs 286 h | Spreadsheet | Debanjan |

## 9.3 J2 UX and UI

| KPI | Target | Method | Owner |
|---|---|---|---|
| Mock-ups approved | 8/8 templates | Approval email | Management |
| Revision rounds used | ≤ 2 per stage | Change log | Debanjan |
| Click depth to each form | ≤ 2–3 from home | Click-count table | Debanjan |
| Claims register | Started; every claim on mock-ups listed | Register | Veena |

## 9.4 J3 Core website

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| Pages built | n/total (target 23/23) | Console page list | Debanjan |
| Forms pass | T01, T02 green | Playwright suite | Debanjan |
| Accessibility | axe 0 serious/critical on all templates | axe-core in CI | Debanjan |
| Performance (lab, mobile profile) | LCP ≤ 2.5 s, CLS ≤ 0.1, TBT ≤ 200 ms (INP proxy) per template | Lighthouse CI | Debanjan |
| Events | All 8 event types fire with correct properties, 0 PII | Beacon test + payload grep | Debanjan |
| Editor usable | Veena edits one page alone | Observed session | Veena |

## 9.5 J4 Congresses

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| Listings imported / rejected / flagged | Counts reported; rejected rows returned with error codes | Import report | Debanjan, Veena |
| Dedup rate | Hard duplicates rejected 100%; soft flagged | Import report on a seeded file | Debanjan |
| Leak test | 0 matches across all public output; canary detected | Leak scanner | Debanjan |
| T03–T08 | 100% pass | Suite | Debanjan |
| Role matrix | 100% of role × route cells as specified | Matrix test | Debanjan |

## 9.6 J5 Pre-launch

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| T01–T15 | 100% pass, evidence in report | Acceptance report | Debanjan; Veena confirms |
| Redirect coverage | 100% of priority URLs; ≥ 95% of all inventoried URLs with a decision implemented; 0 chains; 0 blanket-to-home | Redirect test on staging | Debanjan |
| Restore drill | RTO measured and ≤ 8 business hours; smoke suite green | Drill script + stopwatch | Debanjan |
| Lighthouse | Performance ≥ 90, Accessibility ≥ 95, SEO ≥ 95 per template (lab) | Lighthouse CI | Debanjan |
| Security | ZAP baseline: 0 high; SAST 0 HIGH/CRITICAL | ZAP, SAST | Debanjan |
| Launch blockers | 0 (security, data loss, failed form, code exposure, missing critical redirect) | Go/no-go checklist | Management |

## 9.7 J6 Stabilisation (4 weeks)

| KPI | Target | Method / tool | Owner |
|---|---|---|---|
| Uptime | ≥ 99.5% measured by external probe | UptimeRobot | Debanjan |
| Search Console errors | No new 404 on mapped URLs; coverage errors trending to 0 | GSC weekly | Debanjan |
| Enquiries/day | Baseline by activity (no target until agreed post-audit) | D1 counts | Veena |
| Time-to-first-edit by Veena | First solo publish ≤ 3 working days after launch | Audit log | Veena |
| Outstanding items | 0 open at J6 close | List | Debanjan |
| Front-door synthetic | 5 consecutive green days | Probe | Debanjan |

## 9.8 Post-launch (monthly, in the plan)

| KPI | Target | Method / tool |
|---|---|---|
| Availability | ≥ 99.5% monthly, excluding provider-wide incidents (stated in SLA) | External probe |
| Backup success | 100% of nightly jobs; 0 missed heartbeats | Cron log + dead-man alarm |
| Restore drill | Monthly, pass, time recorded | Drill log |
| Change SLA | Requests within 5 h/month delivered within an agreed number of working days (to set) | Ticket log |
| Security patches | Critical within 2 business days; others monthly | Patch log |
| Enquiries by activity | Reported, with source and conversion events | D1 + beacon dashboard |
| CWV field data | Reported if CrUX publishes it | CrUX |

## 9.9 Questions for the reviewers

1. Which KPI here is a vanity metric? Which business KPI is missing?
2. Is 99.5% the right promise for a Cloudflare-only stack with no platform SLA?
3. Is TBT an acceptable lab proxy for INP?

# 10. Open decisions and asks for the reviewers

## 10.1 Open decisions

| # | Decision | Options | Our lean | What would change it |
|---|---|---|---|---|
| D1 | Build price | €4,000 vs €7,500 (vs ≥ €9,500) | €7,500 + €600/mo × 12 | Evidence that procurement discounts low bids as risky |
| D2 | Console | Build (custom on Workers + D1) vs Directus | Build | A credible estimate that the custom Console exceeds ≈ 70 h, or vault isolation achievable in Directus with equal confidence |
| D3 | Console UI | Preact vs web components (Lit or vanilla) | Undecided; Preact for velocity, web components for zero-framework longevity | Your view on maintainability by a third party |
| D4 | Database | D1 (EU) vs external Postgres (e.g. EU-hosted managed) | D1 | Concerns about D1 maturity, export, limits or lock-in |
| D5 | Deemed acceptance | 5 working days after staging delivery | Keep, worded politely | Evidence it costs us the bid |
| D6 | Off-platform backup store | Not yet chosen | Choose before J1 | Your recommendation |
| D7 | Backup developer | None today | Name one before signature | Whether you think the bid is viable without one |
| D8 | Locale prefix for French | `/` vs `/fr/` | Decide from crawl | Old URL structure |

## 10.2 What we ask you to tell us

1. The single change that would most increase the chance of on-time, in-scope delivery.
2. The single change that would most increase the chance of winning the bid.
3. Anything in this pack you believe is wrong, not just risky.
4. Anything you would refuse to sign off on in a design review.

## 10.3 Questions for the reviewers

1. D2 and D4: if you were the sole engineer, which would you choose and why?
2. Is there any part of the plan you would cut entirely?

## 10.4 Scoring sheet

<table class="score">
<tr><th>§</th><th>Section</th><th>Score 1–10</th><th>Comment</th></tr>
<tr><td>1</td><td>Business context</td><td></td><td></td></tr>
<tr><td>2</td><td>Requirements, complete</td><td></td><td></td></tr>
<tr><td>3</td><td>What exists today</td><td></td><td></td></tr>
<tr><td>4</td><td>System design</td><td></td><td></td></tr>
<tr><td>5</td><td>Architecture</td><td></td><td></td></tr>
<tr><td>6</td><td>Build plan</td><td></td><td></td></tr>
<tr><td>7</td><td>Effort, timeline, price</td><td></td><td></td></tr>
<tr><td>8</td><td>Risk model and grading</td><td></td><td></td></tr>
<tr><td>9</td><td>KPIs per stage</td><td></td><td></td></tr>
<tr><td>10</td><td>Open decisions</td><td></td><td></td></tr>
<tr><td>—</td><td><b>Overall: would you fund this plan?</b></td><td></td><td></td></tr>
</table>

Reviewer name: ______________________ Date: ______________ Time spent: ______ h

# Appendix A. The 30 questions with defaults

Source: `D/01b_Questions_source.md`. "AF" = Answer first. Defaults apply if not answered in writing by Friday 6 November 2026.

| Q | Question (short) | Default if unanswered |
|---|---|---|
| 1 AF | Proposal due date, decision date, launch constraints | Proposal 24–48 working h after answers or by 10 Nov; start within 5 working days of signature; launch ≈ 12 weeks after start; no launch 21 Dec–1 Jan |
| 2 AF | Budget range or cap | Quote as set out in proposal; options priced separately |
| 3 AF | Approvers per stage; days per approval | Management approves in writing within 3 working days; silence = deemed approval of design/content; launch needs written go; acceptance 5 working days on T01–T15 only |
| 4 | Who maintains today's site; contract/notice | Nothing limits the project; ASSET arranges handover |
| 5 AF | Accounts in ASSET's name; owner of new accounts | ASSET gives access at kickoff; new accounts in ASSET's name, management owner, Veena admin |
| 6 AF | Which domain(s) | `asset-voyagesdaffaires.com`; `assetvoyages.com` redirects (web only) |
| 7 | Read-only GA/GSC; trackers and campaigns to keep | Plan from our own crawl; no trackers carried over; cookie-free counting; ads excluded |
| 8 | Selectour requirements | Logo and membership line as today |
| 9 AF | Who writes copy; page counts | ASSET writes new copy; we migrate ≤ 20 pages + 3 legal, light edit, within 2 rounds |
| 10 | Brand guidelines | Keep logo and colours; short style guide |
| 11 | Photos, logos, testimonials, figures, named team | Only what is on today's site and confirmed in writing; illustrations; no named team |
| 12 | SME simplified offer | Page explains and collects requests; no prices |
| 13 | Assistance services, hours, numbers | 24/7 wording as today; phone only once confirmed |
| 14 | English journeys, timing, translator | French only at launch; English option; ASSET pays translation |
| 15 AF | Recipients per enquiry type; reply time | One shared mailbox (direction@assetvoyages.com); no reply time promised |
| 16 | CRM / newsletter tools | None; site enquiry list + Excel export; no marketing tick box |
| 17 | 10 sample rows; sources; yearly volume | One spreadsheet ≤ 300 rows in our template; one import + error list; no research |
| 18 AF | GM&E participation; code mechanics | No fare code or fare wording until confirmed in writing; vault holds code, evidence, validity |
| 19 | Who does each GM&E step; final approver | Veena moves steps; management approves for sale |
| 20 | What to show publicly about fares | Only "request a quote" |
| 21 | Past congress: archive or remove | Stays as past edition without quote button; link to next edition |
| 22 | Quote scope: multiple departures, hotel, transfers | One group, one departure, flights only; extras in free text |
| 23 | Wondermiles vs Traveldoo; other client tools | One "Client login" to Traveldoo URL, editable; no SSO; no other tools |
| 24 | Wondermiles contact; what may be shown; docs access | Text only, no logo/screenshots until approved; no technical link-up |
| 25 | AI option first use | Finds new congresses on official sites for human review; nothing auto-published |
| 26 | Microsoft 365 / Google Workspace | One-time code to work email + second factor; or client IdP with its MFA |
| 27 | EU/France data; security questionnaires; data contact | DB in EU; US providers under DPAs; no questionnaire included; management handles DSRs |
| 28 | Admin users and access | Two editors; management reads enquiries and approves congresses; only Veena and management see GM&E codes |
| 29 | Expected monthly changes | Up to 5 h/month in the plan; no carry-over |
| 30 | Support hours; tolerable interruption | Mon–Fri 9:00–18:00 Paris; site back within 8 business hours after a serious incident on our side; provider outages excluded |

# Appendix B. Glossary

| Term | Meaning |
|---|---|
| MICE | Meetings, Incentives, Conferences and Exhibitions: corporate group events |
| GM&E | Air France–KLM Global Meetings & Events: event codes giving attendees discounted fares; agencies apply per event |
| Selectour Affaires | French network of business-travel agencies, of which ASSET is a member |
| Wondermiles / Traveldoo | Online booking tools used by corporate clients; the RFP names Wondermiles, today's site links Traveldoo |
| SSO | Single sign-on (SAML or OpenID Connect) |
| IdP | Identity provider (Microsoft 365, Google Workspace) |
| MFA / OTP / TOTP | Multi-factor authentication / one-time PIN / time-based authenticator code |
| RPO / RTO | Recovery point objective (max data loss, 24 h) / recovery time objective (max time to restore, 8 business hours) |
| CWV: LCP, INP, CLS | Core Web Vitals: Largest Contentful Paint, Interaction to Next Paint, Cumulative Layout Shift |
| TBT | Total Blocking Time, a lab metric correlated with INP |
| p75 | 75th percentile of field (real-user) measurements |
| CrUX | Chrome UX Report, Google's public field-data set |
| hreflang | HTML annotation linking language versions of a page |
| Canonical | The preferred URL for a page, declared to search engines |
| 301 / 308 | Permanent HTTP redirects |
| D1 | Cloudflare's hosted SQLite database; Time Travel = point-in-time restore |
| R2 | Cloudflare object storage, no egress fees |
| Workers / Pages | Cloudflare serverless compute / static hosting |
| Access | Cloudflare Zero Trust login gateway |
| Turnstile | Cloudflare's privacy-friendly CAPTCHA alternative |
| ULID | Sortable unique identifier |
| Zod / Drizzle | TypeScript validation library / TypeScript ORM and migrations |
| SAST | Static application security testing |
| ZAP | OWASP Zed Attack Proxy, an automated web-security scanner |
| DPA / SCCs / DPF | Data processing agreement / EU standard contractual clauses / EU-US Data Privacy Framework |
| CNIL | France's data-protection authority |
| DSR | Data subject rights request (GDPR access, erasure, etc.) |
| HT / TVA / TTC | Excluding VAT / VAT / including VAT |
| RACI | Responsible, accountable, consulted, informed |
| Jev | ProdCraft's pinned classify/score/gate model routing (OpenRouter) |
| Front-door synthetic | A probe that exercises the live production URL as a user would |

# Appendix C. File index of the deliverable folder

`D/ = deliverables/asset_voyages_rfp_2026-10-28/`

| File | Content |
|---|---|
| `00_RFP_Analysis_and_Plan.md` | Internal RFP analysis, have/build table, CMS decision, first pricing, delivery plan |
| `01_Questions_for_Veena.md` | Cover email for the questions |
| `01b_Questions_source.md` | 30 questions with defaults |
| `01c_Reply_to_clarifications_2026-10-31.md` | Reply to the client's seven clarification questions |
| `02_Panel_Debate.md` | 16-voice debate; Common ground; Honest gaps by lens |
| `03_Functional_Breakdown.md` | Every RFP cell → build, acceptance, status, gap, hours |
| `04_Concept_Paper.md` | Concept « Du brief au retour » |
| `05_`, `06_` | Panel audits of the outgoing pages (11 lenses; project experts) |
| `07_Question_Coverage_Matrix.md` | MECE proof for the 30 questions |
| `08_`–`15_` | Audit rounds 1–3 and fix logs |
| `16_Proposal_Carryover.md` | Must-do items for the priced proposal |
| `17_Verification_Operator_Edits.md` | Verification of operator edits |
| `18_Payment_Terms_Vetting.md` | 50/50 terms and guardrail table |
| `19_Final_QA_Reply_2026-10-31.md` | QA of the clarifications reply |
| `20_Internal_Founder_QA.md` | Founder Q&A: deliverability, price, architecture, risk |
| `99_INTERNAL_kickoff_call_checklist.md` | 72-question long list |
| `HANDOFF.md` | What was built, verified facts, gates |
| `proposal/` | Proposal v1.0 (MD, DOCX, PDF), legal review, pre-contract clarifications PDF |
| `research/` | Effort estimate, market pricing, infra costs, functional suite, film renderer, model logs |
| `site/` | Concept site source (home, `pour-asset/`, `console/`, `questions/`, `_headers`) |
| `screens/` | Review screenshots |
| `advisory/` | This pack (MD, HTML, PDF) |

# Appendix D. Sources

**Client.** ASSET Voyages RFP, Version 0.4 EN, 28 October 2026 (restricted). Current site `asset-voyagesdaffaires.com`, fetched 28 October 2026, including `/solutions-voyages-affaires-pme/expertise-tarifaires/` and `/solutions-voyages-affaires-pme/politique-de-voyages/`.

**Infrastructure** (checked 28 October 2026, `D/research/infra_costs_2026.md`):

- Workers pricing: https://developers.cloudflare.com/workers/platform/pricing/
- Static assets billing: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- Pages limits: https://developers.cloudflare.com/pages/platform/limits/
- D1 pricing: https://developers.cloudflare.com/d1/platform/pricing/
- D1 Time Travel: https://developers.cloudflare.com/d1/reference/time-travel/
- D1 data location (EU jurisdiction): https://developers.cloudflare.com/d1/configuration/data-location/
- R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Zero Trust account limits: https://developers.cloudflare.com/cloudflare-one/account-limits/
- Access one-time PIN and independent MFA: developers.cloudflare.com (Cloudflare One docs), checked 28 October 2026
- Turnstile plans: https://developers.cloudflare.com/turnstile/plans/
- Web Analytics: https://www.cloudflare.com/web-analytics/ (no custom events, per FAQ)
- Customer DPA: https://www.cloudflare.com/cloudflare-customer-dpa/
- Business SLA: https://www.cloudflare.com/business-sla/
- Incident reports: https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/ ; https://blog.cloudflare.com/fail-small-resilience-plan/ ; https://blog.cloudflare.com/5-december-2025-outage/
- Brevo: https://www.brevo.com/products/transactional-email/ · Resend: https://resend.com/pricing · UptimeRobot: https://uptimerobot.com/pricing/ · Postmark: https://postmarkapp.com/pricing · Amazon SES: https://aws.amazon.com/ses/pricing/

**Market** (`D/research/market_pricing_paris_2026.md`, 28 October 2026; mostly search summaries):

- Malt barometer: https://www.malt.fr/t/barometre-tarifs/tech/developpeur-backend/developpeur-fullstack
- TJMetre: https://tjmetre.fr/barometre · Freeland: https://barometre.freeland.com/tjm/developpeur
- La Fabrique du Net: https://www.lafabriquedunet.fr/agences/pages/agences-developpement-web/tarifs
- Agence2web: https://www.agence2web.com/tarifs-site-web/ · Seedweb: https://seedweb.fr/prix-site-internet/
- Ellebay: https://ellebay-digital.com/blog/cout-maintenance-site-web-2026 · Make Different: https://makedifferent.fr/blog/cout-maintenance-site-web/

**Not sourced in this pack** (flagged): CNIL prospect-retention period (cited from memory); Google Event structured-data policy (to check); Access free tier ≤ 50 users (third-party source); the 65/65 functional-gate figure (folder records 62/62); the original complexity and risk tables (reconstructed to match stated totals); French late-payment article numbering (to verify with an accountant).
