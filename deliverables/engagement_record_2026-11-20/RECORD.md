# Gaia Talent and GreenJobs: engagement record and promise check (2026-11-20, v4 after three audits)

v1 failed an independent audit against primary sources (7 errors, 10 omissions). This v2 cites primary files.

**Caveats:**
- This clone's git history starts on 16 Nov.
- There are no recorded meetings and no business mail in the connected sources.

Abbreviations used in the citations:
- **Proposal**: `deliverables/greenjobs_redesign_2026-09-22/proposal/GreenJobs_Proposal_v1.0_2026-09-30.md`
- **Plan**: `deliverables/greenjobs_migration_2026-11-06/transition_plan.html` (tag-stripped line numbers)
- **Brief**: `deliverables/greenjobs_redesign_2026-09-22/proposal/keith_costing_brief_2026-09-28.md`
- **Thread**: `keith_linkedin_thread_2026-11-06.txt`
- **REVIEW** and **FEAS**: the 16 Nov review and the feasibility matrix in `deliverables/greenjobs_migration_2026-11-06/`

## 1. Timeline

| Date | Event | Primary source |
|---|---|---|
| 20 Aug | Gaia sourcing: 13 candidates (10 for Role 1, 3 of 5 for Role 2). Keith: "too senior, some not in Ireland" | `gaia_2026-09-10/call_brief_2026-09-10.md:11`; `ENGAGEMENT_RECORD_2026-09-11.md:33` |
| 10 Sep | 27-minute call; Keith praised the interface (ER:56-62, quoting the transcript); corrected list plus Loom for Mon 14 Sep. Our own runbook limited the scope to "no auto-sending, no voice agent, no replacement of Recruit CRM" (operator's recorded promise, not said on the call) | `transcript_2026-09-10_fathom.md:14`; `RUNBOOK_monday_delivery.md:3-6` |
| 11–14 Sep | Corrected run: Role 1 at 2 of 10, Role 2 at 0 of 5. That Keith viewed the Loom on 14 Sep is unverifiable from primary files (Gmail notification only) | `HANDOFF_SESSION_2026-09-11.md:16-17` |
| 17 Sep | Gaia website redesign built. "Keith has NOT been sent anything" | `gaia_redesign_2026-09-17/HANDOFF.md:4` |
| 22–28 Sep | GreenJobs redesign at greenjobs-redesign.pages.dev, including the KPI dashboard. Change document received 28 Sep | Proposal:60; `KEITH_CHANGES_CHECKLIST.md:1` |
| 29 Sep | Answer to the site manager on candidate accounts: "Yes, that stays". Whether the reply was sent is not evidenced | Brief:157,166 |
| 30 Sep | Proposal v1.0: €1,999 front end, €2,999 migration, €999/month | Proposal:117-121,127 |
| 5 Oct | Revised proposal: €1,500, migration €0 for publicity, €600 × 6 months. Sent: not evidenced | `greenjobs-official.official.json:28,90-96` |
| 29 Oct | Keith: €600/month plus €1,500 in Q1 is "doable" | Thread:6 |
| 6 Nov | Strategies: contract ends 6 Dec | Thread:10 |
| 9 Nov | Transition plan sent: switch 3 Dec, floor, trims, phase 2 | Plan:30-37 |

## 2. Promises and the build

The plan (9 Nov) governs 3 Dec. The proposal (30 Sep) governs the service.

**Status key:**
- **Built**: exists in code and passes the offline tests.
- **In build**: assigned to an engineer now.
- **Missing**: not built.
- **Phase 2**: deferred by the 9 Nov plan.

| # | Promise | Source | Status | Action |
|---|---|---|---|---|
| P1 | Both boards on Keith's domains, current jobs, our design | Plan:30; Proposal:60 | In build (job pages from D1) | Keep |
| P2 | Staff console: post, edit, close | Plan:30 | In build (fixes) | Keep |
| P3 | Applications to the inbox Keith chooses | Plan:30 | Built (per-job email or link) | Default inbox asked of Diana |
| P4 | Job alert emails on 3 Dec. Trim order: alerts first, then candidate import (Plan:33); FEAS:109 adds newsletter third | Plan:30,33 | Built (merged 86c441e; flag off; DRY_RUN default) | Add to the go/no-go gate. Trim only with same-day written notice |
| P5a | The candidate records Keith chooses to keep (3 Dec) | Plan:30,33 | In build (consented import, off by default). Archiving everything is a permitted trim only with same-day written notice | Keith decides retention in writing (REVIEW:20) |
| P5b | Candidate accounts with stored CV, one-click apply, saved roles | Proposal:64; Brief:157 ("Yes, that stays") | Phase 2 (Plan:31) | Keep in phase 2 |
| P6 | KPI dashboard, figures live from job data | Proposal:42,60,127 | In build (/api/stats) | Keep |
| P7 | 301 for every indexed URL; full export and import | Proposal:64,83 | Importer built; redirect map generated; 301 serving In build (ops stream) | Keep |
| P8 | Weekly update throughout, and a monthly report | Proposal:92 (weekly); 68,127 (monthly) | In build | **Both** are owed |
| P9 | Daily backups, quarterly restore drill, uptime monitoring | Proposal:68,127,135 | In build | Keep |
| P10 | Broadbean, Idibu, LogicMelon and one CRM | Proposal:64,83 | Phase 2 (Plan:31) | Phase 2 |
| P11 | Employer logins (CHM, Mattinson) | Plan:31 phase 2; REVIEW:21 (notice by 25 Nov) | In build (behind a flag, off); not merged | Staff post for them on 3 Dec. They are told by 25 Nov |
| P12 | 8 network domains | Proposal:105 out of scope; Plan:37 "quoted separately" | Configuration only | Question for Keith |
| P13 | Gaia jobs fed in automatically | Not promised | Standalone sync script, not wired to the board | Offer to Keith as a time saver |
| P14 | Platform costs: Cloudflare ~$5 and Resend ~$20 at cost +3%, billed to GreenJobs | Proposal:148-151; JSON:99 | DECISION.md corrected to the proposal costs (DECISION.md:7) | Use as proposed |
| P15 | Newsletter sends | Proposal:83,149; FEAS:109; REVIEW:34 (paid advertiser feature) | Built (merged 86c441e; NEWSLETTER_ENABLED=0) | Add to the alerts build (third in the trim order) |
| P16 | Export archive in storage in GreenJobs' name before 6 Dec | Plan:33 | In build (export bot and R2, after the DPA) | Keep |
| P17 | 10 working days of daily checks after 3 Dec, against the acceptance list | Plan:24; Proposal:91 | In build (probes, status) | Add a 10-day check schedule and the acceptance list |
| P18 | JobPosting structured data on every role, plus sitemaps | Proposal:34,82,138 | In build (Worker pages) | Keep. Validated in the pipeline smoke tests |
| P19 | Handover: runbook, test register, source repository, everything in GreenJobs-owned accounts | Proposal:85,161 | Partial | Produce the handover pack before go-live |
| P20 | Service levels: 99.9% uptime; 1 business day response (4 h for a posting outage); 2 business-day changes | Proposal:92,134,137,140 | In build (monitoring) | Alerting thresholds set to these |
| P21 | All 100 change-document items done, 11 waiting on Keith's input | Proposal:60,82 | Done items exist on the demo site | Re-verify on the new build. The 11 inputs go in the Keith question list |
| P22 | 5-working-day go-live guarantee | Proposal:89; JSON:89 | Superseded by the 9 Nov plan dates | Record as superseded |
| P23 | The two site-manager fixes | Proposal:82 | Re-verify on the new build | In the acceptance list |
| P24 | Analytics: GA4 and Search Console kept; logo use needs Keith's OK | Proposal:83; Plan:47; REVIEW:26 | In build (GA4 IDs held) | Logo OK goes in the Keith question list |
| P25 | EU data region, firewall/DDoS/SSL, security patches as released | Proposal:68,127 | In build (Cloudflare config; D1 location hint) | Verify in the pipeline |
| P26 | Daily test job through each posting route | Proposal:64,83 | Phase 2 (with P10) | With P10 |
| P27 | Keith signs off on the test address by Fri 27 Nov | Plan:22 | Scheduled | Staging URL to Keith via the operator |
| P28 | Phase-2 target dates set in the contract | Plan:31 | Operator (contract) | None for engineering |
| P29 | Ongoing maintenance: Core Web Vitals green, first-line support for staff and advertisers, rolling content and small changes, Search Console health | Proposal:127 | In build (CWV and Search Console in status checks); support and changes are service work | Monthly report covers it |

## 3. Gaia Talent sourcing: open, dormant since 14 Sep

- **Role 1:** 2 of 10. Needs Keith's seniority ceiling and Ireland rule.
- **Role 2:** 0 of 5. Needs a licensed data source and his go-ahead.
- Both questions go in the Keith question list.

## 4. Contract, payment and legal

Out of scope for this record (operator, 20 Nov 2026).
