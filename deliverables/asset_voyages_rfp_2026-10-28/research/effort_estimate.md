# Effort estimate: one person (Debanjan) working with Claude Code
28 October 2026. Hours are hands-on hours including Claude Code supervision, review and fixes. Basis: past builds in this workspace (GreenJobs: public boards + 3,047 checks; Jitendra: FR/EN live site with forms, moderation, GDPR; medspa: approval pipeline). Items marked "new" have no prior code to lift (see the capability delta: Console, roles, versions, backups, CWV/a11y tooling).

| Work item | Reuse | Hours |
|---|---|---|
| L0 audit: crawl, URL inventory, tech/SEO/legal audit, baseline, architecture doc | partial | 8 |
| Design system, wireframes, desktop + mobile mock-ups of ~8 templates, prototype (concept already started) | partial | 16 |
| Public site: ~25 French pages from templates, content integration | high | 24 |
| Forms F01–F06: 3 forms, validation, anti-spam, dedup, acknowledgement, notification fallback | partial | 12 |
| Enquiry back-office: inbox, status, owner, history, CSV export, routing by activity | new | 12 |
| ASSET Console core: login via Cloudflare Access (MFA), 5 roles, page/block editor, media, version history + restore, soft delete, access log | new | 40 |
| Congress catalogue: data model, search/filters/sort/pagination, listing pages, past-event rule | partial | 14 |
| Congress admin: CSV import with validation + duplicate detection, export, editorial workflow, internal GM&E workflow, protected code vault, leak test | new | 18 |
| SEO migration: redirect map, sitemap, canonicals, hreflang-ready, structured data, Search Console | partial | 8 |
| GDPR + consent + legal pages + conversion events without personal data | high | 6 |
| Infrastructure: dev/staging/prod, noindex + password on staging, CI, daily backups + restore drill, uptime monitoring + alerts | new | 10 |
| QA: T01–T15 test cases, WCAG 2.2 AA audit (automated + manual), Core Web Vitals lab reports, acceptance report | partial | 16 |
| Handover: illustrated admin guide, runbook, account inventory, two training sessions (Veena + backup) | partial | 10 |
| Project management: weekly written updates, milestone documents, revision rounds on feedback (~15 %) | — | 25 |
| **Total core (L0 + L1 + L2)** | | **≈ 220 h** |
| Contingency for unknowns (current CMS export, content delays, revisions) +20 % | | 44 |
| **Planning figure** | | **≈ 265 h** |

Options (hours): English activation 8 · CRM connector 6 · Wondermiles feasibility 4 / SSO 12 · AI ingestion queue 16.

## Calendar (the part that is not under our control)

| Pace | Hours/week | Build weeks (265 h) |
|---|---|---|
| 4–5 h/day, 5 days | ≈ 22 h | ≈ 12 weeks |
| 6–8 h/day, 5 days | ≈ 35 h | ≈ 7.5 weeks |

The client side adds calendar time no matter how fast we build: 6 milestone approvals at about 3 working days each, content and photos from ASSET, account/DNS access from the current supplier, and the Christmas break (≈ 2 weeks of slow replies).

**Realistic launch, at 6–8 h/day, go-ahead Mon 16 Nov 2026:** staging complete mid-January 2027, launch week of 25 January 2027 (≈ 10 calendar weeks including Christmas). Stabilisation then runs 4 weeks in the background (≈ 2–3 h/week).

**Without Christmas or approval waits**, the build itself is about 7–8 working weeks full-time. Delivering in 4–5 weeks is only possible by cutting scope (for example, Console page editor at launch limited to text/images, Congress internal workflow as statuses only).

## Rate check
€4,000 ÷ 265 h ≈ **€15/hour** (≈ €105/day at 7 h). This is the number the panel must weigh against the market data in `market_pricing_paris_2026.md`.
