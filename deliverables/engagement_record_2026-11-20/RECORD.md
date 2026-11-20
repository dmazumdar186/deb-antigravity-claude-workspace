# Gaia Talent and GreenJobs: engagement record and promise check (2026-11-20)

Built from four independent readers. Each reader's file holds the citations:
- A_gaia_talent.md
- B_greenjobs_redesign_proposal.md
- C_greenjobs_migration_nov.md
- D_meetings_mail_drive.md

**Caveat:** this clone's git history starts on 16 Nov, so August–October commits are cited through the files that quote them. There are no recorded meetings and no business mail in the connected sources.

## 1. Timeline

| Date | Event | Source |
|---|---|---|
| 20 Aug | Gaia sourcing: 13 candidates delivered (10 for Role 1, 3 of 5 for Role 2). Keith: "too senior, some not in Ireland". He praised the interface | A |
| 10 Sep | 27-minute call. Corrected list plus Loom promised for Mon 14 Sep. Scope: "no auto-sending, no voice agent, no replacement of Recruit CRM" | A |
| 11–14 Sep | Corrected run: Role 1 at 2 of 10, Role 2 at 0 of 5. Shortlist Check bundle published. Keith viewed the Loom walkthrough on 14 Sep (Loom notification) | A, D |
| 17 Sep | Gaia website redesign built for free. No record that it was sent | A |
| 22–28 Sep | GreenJobs redesign built (greenjobs-redesign.pages.dev), including the KPI dashboard. Written feedback docx dated 28 Sep | B, D |
| 30 Sep | Proposal v1.0: €1,999 front end, €2,999 migration, €999/month, full scope (see §2) | B |
| 5 Oct | Revised proposal JSON: €1,500 at signing, migration €0 for publicity, €600/month for 6 months. Sent: UNCERTAIN | B |
| 29 Oct | Keith on LinkedIn: €600/month from now plus €1,500 in Q1 2027 is "doable" | C |
| 6 Nov | Strategies' notice: contract ends Sun 6 Dec | C |
| 9 Nov | Email and transition plan sent (switch 3 Dec, floor, trim order, phase 2) | C |
| 10–19 Nov | Rashieda's and Diana's answers. Header rows received 19 Nov | C |
| 20 Nov | No contract, DPA or invoice exists. Reply to Diana gated, not yet sent | C |

## 2. What was promised for GreenJobs, and where the build stands

The binding promise for 3 Dec is the **9 Nov transition plan**, quoted below. The 30 Sep proposal describes the full service.

The 9 Nov wording: "Both GreenJobs boards… current jobs, your team posting, editing and closing jobs through a simple admin console… applications reaching the inbox you choose, job alert emails, and the candidate records you choose to keep."
- Never trimmed: the boards, the console and applications.
- Trim order: alerts first, then the candidate import, with the client told in writing the same day.
- Phase 2: candidate and employer logins, Broadbean / Idibu / LogicMelon, one CRM.
- The other domains are quoted separately.

| # | Promise | Source | In today's build? | Action |
|---|---|---|---|---|
| P1 | Both boards on Keith's domains, current jobs, our design | 9 Nov, 30 Sep | Yes (job pages rendered from D1) | Keep |
| P2 | Staff console: post, edit, close | 9 Nov | Yes (fixes in progress) | Keep |
| P3 | Applications to the inbox Keith chooses | 9 Nov | Yes (per-job email or link) | Keep. Default inbox asked of Diana |
| P4 | **Job alert emails on 3 Dec** | 9 Nov | **No.** Not built, not in the gate | **Build now.** Trim only with same-day written notice to Keith |
| P5 | **Candidate records Keith chooses to keep** | 9 Nov; 30 Sep "Yes, that stays" | **Contradicted.** DECISION sent all candidates to an archive | **Fix:** build a consented candidate import; Keith decides retention in writing |
| P6 | KPI dashboard, figures live from job data | 30 Sep | Added today | Keep |
| P7 | 301 for every indexed URL; full export and import | 30 Sep | Yes (redirect map, importer) | Keep |
| P8 | Maintenance service: uptime monitoring, daily backups with quarterly restore drill, monthly report | 30 Sep | Partial (probes yes; backups no; weekly email instead of monthly) | **Add daily D1 backup and restore drill; a monthly report replaces my weekly email** |
| P9 | Posting tools and CRM | 30 Sep; phase 2 on 9 Nov | No | Phase 2, as agreed |
| P10 | Employer logins (CHM, Mattinson) | Phase 2 on 9 Nov | **Pulled forward** | **Revert:** staff post for them on 3 Dec; they get notice by 25 Nov; code stays behind a flag |
| P11 | 8 network domains | Out of scope; "quoted separately" | **Added** | **Prepare the config only.** Your call whether to quote or include it |
| P12 | Gaia jobs fed in automatically | Not promised | **Added** | Keep behind a flag; offer to Keith as a time saver, never present it as agreed |
| P13 | Hosting costs: Cloudflare ~$5 and Resend ~$20 billed to GreenJobs | 30 Sep and 5 Oct | **Contradicted.** I wrote "free tier, no paid third parties" | **Corrected:** platform fees as proposed. Your ruling stands that no new third-party product such as Cavuno is added |

## 3. Gaia Talent sourcing: open, dormant since 14 Sep

- **Role 1:** 2 of 10 delivered. Needs Keith's seniority ceiling and Ireland rule.
- **Role 2:** 0 of 5. Needs a paid people-data source and his go-ahead.
- Nothing has been priced or paid. Your call: are the roles still open?

## 4. Contract, payment and legal

Out of scope for this record. The operator holds the contract, and a lawyer has cleared going ahead (operator, 20 Nov 2026). Engineering does not track or flag these items.
