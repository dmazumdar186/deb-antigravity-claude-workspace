# GreenJobs rethink: synthesis of the 12-lens panel (2026-11-20)

Internal. Inputs: panel_A.md (Karpathy, Anthropic research, Sutskever), panel_B.md (Cherny, Brockman, Hassabis),
panel_C.md (Hormozi, Dario Amodei, Daniela Amodei), panel_D.md (Saraev, Murati, Steve Jobs), RESEARCH_options.md, FACTS.md.
All four panels voted AMEND. None voted keep-as-is.

## 1. What the panel found (agreed by two or more panels)

1. **The custom build does not work end to end.**
   - A job posted in the console never reaches the public board: there is no deploy hook, and the cron only retries emails (B, D: `platform_worker/src/index.js:106-131`, `build_site.py`).
   - Apply buttons still point to the old Strategies URLs, which die on 6 Dec (D: `build_site.py:2439`).
   - The 159 tests pass on the parts, but nothing tests the whole path from post to board.
2. **Gaia double-posts by hand.** 73 of Gaia's 79 unique job titles on gaiatalent.com also appear on greenjobs.ie. Gaia's WordPress jobs feed is open: `/wp-json/wp/v2/jobs` returns 200 with 83 jobs, and RSS is available (RESEARCH). This is the largest staff saving available, and the plan never mentioned it.
3. **The plan adds staff work.** Estimated staff time per month (an estimate, panel D):
   - today: ~14 h;
   - the plan as built: ~20 h;
   - an amended system: ~3.5 h.
   
   Diana gets about 14 asks (C). The console posts to one site at a time.
4. **Paid promises would break on 6 Dec:**
   - alerts were first in the trim order (A, C);
   - CHM and Mattinson lose self-posting (C, D);
   - the 8 sector sites go dark (A, B, C, D).
5. **The docs contradict the facts.**
   - Feeds sit in phase 2 although no feed is used.
   - The plan covers 2 domains, but 10 must move.
   - Runbook path B is still listed although it is known not to work.
   - It lists 5 export types; there are 6 (A).
6. **No number is measured.** Staff hours, risk scores and the 40/100 estimate have no data behind them (A).
7. **Bus factor of one.** Only Debanjan can maintain the custom stack (B).

## 2. Decision

**Claim:** replace the custom board with a hosted job-board product and automate around it. The best verified fit is Cavuno:
- network boards from one account, custom domains, Google for Jobs;
- recurring XML feed import, employer self-posting, and CSV export of every table;
- $39 to $105 a month (cavuno.com/pricing, read 2026-11-20).

**Objection:** six must-haves are unverified:
1. email-or-link apply per job;
2. job alerts to candidates;
3. 10 domains, or the 8 sector domains as filtered views;
4. import of jobs and employers from the real Strategies headers;
5. EU data residency. Its DPA says it does "not currently offer EU-only data residency", which matters for about 178k candidate records;
6. whether the Gaia feed maps cleanly.

We also already have a static front end and an import pipeline that pass their tests.

**Resolution (amend):**
1. **A 1-day spike (Mon 23 Nov) against the six must-haves.** Use Cavuno's docs and a trial if one exists without payment; any spend needs the operator's OK.
   - **All six pass → buy.** Cavuno runs both boards and the sector sites. We own the automation around it:
     - Gaia feed sync;
     - data import from the real headers;
     - redirects;
     - DNS;
     - monitoring.
   - **Any must-have fails → fix the custom build** to panel B's target:
     - one Worker renders pages straight from D1, with no static rebuild;
     - a `boards` table, with the sector domains as filtered views;
     - Gaia feed sync into D1;
     - apply by each job's email or link;
     - one end-to-end test gating deploy.
2. **Either way, from today:**
   - build the Gaia feed sync, since it is needed in both branches;
   - fix the apply links;
   - keep the redirect map and DNS inventory.
3. **Candidate data:** import only candidates with `Consent`=yes, and alerts only to `Marketing`=yes. Everything else stays in the raw archive in GreenJobs' own storage, per Keith's written retention decision (still open).
4. **Apache Ant and microservices:** no role here (B).

## 3. Client asks: asynchronous only, no calls (operator order, 2026-11-20)

| Ask | How, with no call | How we confirm without asking |
|---|---|---|
| Nameserver change at Hosting Ireland, LetsHost and 123 Reg | A one-page click guide per registrar with the exact values to paste, done any time in a 2-day window | Our watcher polls public DNS every 10 minutes and emails "done, checked" when each domain moves |
| Zone export | Not asked. Cloudflare's record scan plus our public inventory; she forwards the registrar's own zone file only if the scan misses mail records | A diff of the scan against the inventory, with the email records checked first |
| Strategies exports (6 types × 2 sites) | After the DPA, she sends the Strategies admin login once through a one-time secret link (no account needed). Our export bot downloads everything outside 09:00–17:00 UTC into GreenJobs' own storage | Row counts per export are compared with the admin's totals |
| Default applications inbox | One yes or no: "info@ unless you prefer Rashieda" | — |

Open risk: if a registrar sends a login code to info@ on the domain being moved, she must log in before the move. The guide puts each login before its change.

## 4. Metrics and evals (what we measure, how it is graded, where it is shown)

Graded by deterministic scripts, never by an LLM. Shown on one GreenJobs status page with a daily update; a red result emails the operator the same day.

| # | Metric | How it is measured | Pass | Warn | Fail |
|---|---|---|---|---|---|
| M1 | Migration fidelity: jobs, employers and applications imported ÷ exported | Count reconciliation per export, plus a field diff on a 50-row random sample | 100% and 0 field diffs | ≥99% | <99% |
| M2 | Redirect coverage: old URLs that end on a 200 page in ≤2 hops | Crawl every URL in redirect_map.json | ≥99% | ≥95% | <95% |
| M3 | Availability of all 10 domains and their www names | 5-minute uptime probe | ≥99.5%/week | ≥99% | <99% |
| M4 | Email intact: MX and SPF match the inventory, and a test mail to each info@ arrives | Daily DNS diff plus a test send | all match | — | any mismatch |
| M5 | Time to live: from a job created (console or Gaia feed) to visible on the board | Timestamp diff from the audit log and a probe | ≤15 min | ≤60 min | >60 min |
| M6 | Gaia double-posting removed: share of Gaia jobs arriving by feed, not by hand | Source field on each job | ≥95% | ≥80% | <80% |
| M7 | Staff minutes per month | Console audit-log minutes plus a 2-question monthly check-in with Rashieda; baseline is today's estimate (14 h), marked as such | ≤4 h | ≤8 h | >8 h |
| M8 | Apply delivery: applications sent ÷ apply submissions (email mode); valid https links (link mode) | Worker or vendor logs and a link checker | ≥99% | ≥97% | <97% |
| M9 | Consent compliance: alerts sent to anyone without Marketing=yes | Join of the send log with consent | 0 | — | ≥1 (stop sends) |
| M10 | Google for Jobs eligibility: job pages with valid JobPosting JSON-LD | Schema validator over every live job | 100% | ≥95% | <95% |
| M11 | Search: indexed pages and organic clicks vs the 4 weeks before the switch | Search Console and GA4 | ≥90% of baseline by week 6 | ≥75% | <75% |

AI parts, each scored on a labelled set with `execution/infrastructure/jev_validate.py` before go-live:

| # | Metric | Labelled set | Pass |
|---|---|---|---|
| E1 | Gaia feed to GreenJobs mapping: sector, region and job type picked by Jev from the feed taxonomy | 100 hand-labelled Gaia jobs | ≥95% exact; below the confidence cut, a job goes to Rashieda's queue |
| E2 | Duplicate detection: a feed job already on the board (prevents double listing) | 100 pairs from the 73 matched titles plus 100 non-matches | precision ≥99%, recall ≥95% |
| E3 | Sector routing to the 8 sector sites | 100 jobs, hand-labelled | ≥95% |

## 5. Before this is final

1. The client executive lens: Gaia Talent's CEO, CTO, CDO (data) and CPO.
2. The 1-day buy spike.
3. The redteam gate on any client text.
4. The previous reply to Diana proposed screen-share calls. It is withdrawn and must be rewritten as asynchronous.
