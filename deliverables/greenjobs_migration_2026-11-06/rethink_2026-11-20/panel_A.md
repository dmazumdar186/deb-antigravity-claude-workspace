# Panel A: is the custom Cloudflare build the right system? (2026-11-20)

Internal. Three blind lenses. Paths are relative to `rethink_2026-11-20/`: `FACTS` = `FACTS.md`, `FM` = `../FEASIBILITY_MATRIX.md`, `REV` = `../REVIEW_2026-11-16_keith_answers.md`, `ARCH` = `../build/ARCHITECTURE.md`, `RUN` = `../build/CUTOVER_RUNBOOK.md`.

## 1. Karpathy lens: measured vs assumed

1. **No staff-hour number exists anywhere.** The brief is to save staff hours, but no doc measures minutes per post today, posts per week or download hours. The console is sized on "volume per month" (FM:50), and that volume is unknown: "~15/month" excludes Gaia's own jobs (FACTS:17), while REV:24 and REV:40 say the real volume is higher, with no figure.
2. **The decision-driving unknown is unmeasured.** If Gaia double-posts its jobs on gaiatalent.com (FACTS:23), the biggest saving is to post once in WordPress (FACTS:22). No plan line uses it.
3. **Live-job counts disagree** by 27 UK / 12 IE (FACTS:16). Nobody has reconciled them.
4. **The risk scores have no basis.** 40/65/80 (REV:90), 60% pay (REV:96) and the chances in REV:68-78 are opinions with no data behind them.
5. **The effort estimate is old.** 18–22 days vs 20 available (FM:61) was set on 6 Nov. Today about 9 working days remain before 3 Dec. No export file has been seen (REV:38, FACTS:32).

## 2. Anthropic rigor lens: hidden assumptions, contradictions, scope creep

1. **Scope creep against the facts.** Feeds are still in phase 2 (ARCH:14-15, ARCH:185-188, FM:108), yet no live job comes through Broadbean or another tool (FACTS:14).
2. **Domain count.** ARCH:3-4 and RUN:3 cover 2 domains. REV:59 needs all 10 off Strategies, and the 8 network sites go dark (FACTS:21). They have no runbook steps.
3. **Path B.** RUN:16-23 still offers path B. REV:17 and REV:36 say it fails for bare domains.
4. **Export types.** RUN:73 and ARCH:91 list five export types. FACTS:33 says six, and the missing one is "Jobs By Email", the alert list.
5. **Alerts.** Alerts are trimmed first (ARCH:12, FM:109), but they are paid advertiser features (FACTS:20, REV:34).
6. **Application routing.** ARCH:53 and ARCH:84 route applications by a global variable. The real need is per-job email or ATS link (FACTS:19, REV:23).
7. **Unexamined assumption:** a CV upload, R2 storage and a mail relay (ARCH:26, ARCH:32) are needed at all. Applications are already a mailto address or an AppLink.

## 3. Sutskever lens: how this fails by 6 Dec

1. **Dependency chain.** Contract → DPA → logins → zone → switch (REV:59-63). The hinge is today (REV:63), and nothing is signed (FACTS:8). Every system shares this risk. Only the minimal one fits in the slack left.
2. **Custom build failure surface.** Pages, Worker, D1, R2, Access, Resend, cron, deploy hook and build token: 9 coupled parts (ARCH:21-35), none deployed (FACTS:41), one maintainer. Staff also lose the admin they know and must learn Access plus a new console. That adds work.
3. **Hosted SaaS failure surface.** Vendor onboarding plus a CSV import plus apex DNS, which still needs path A. Self-posters keep self-service (REV:21), and alerts come built in. Unverified: price per board ×2 inside €600, multi-domain support, and EU data hosting. It is a new vendor chosen 9 days out.
4. **Minimal static board failure surface.** Pages plus a validated job source, applications by mailto or AppLink. 2 parts, and the front end is already built (FM:49). The weak point is the staff edit path: invalid rows get past the validator onto the live board.
5. **Shared floor:** downloads by hand (REV:37, REV:71), the nameserver move, 8 forwards.

## VERDICT: AMEND (cut to a minimal static board)

Keep the static front end, the 301 map and the path-A runbook. Drop the Worker, D1, R2, Access, Resend and feeds from the 3 Dec plan. Jobs come from a Google Form feeding a Sheet: Rashieda, CHM and Mattinson submit, and an "approved" column publishes. The build validates and keeps the last good deploy. Apply by per-job mailto or AppLink. The 8 network domains forward to sector pages. If double-posting is confirmed (FACTS:23), use the gaiatalent.com WordPress jobs feed as the source instead.

- **Claim:** Form+Sheet static board meets the floor with fewer parts and less staff work.
- **Objection:** paid alerts and the newsletter (FACTS:20) have no home, and a Sheet has no audit trail.
- **Resolution:** amend. Import the "Jobs By Email" list into a hosted mail tool that sends an RSS-to-email digest. Sheet version history is the audit trail. The custom platform is quoted only if measured volume justifies it.
