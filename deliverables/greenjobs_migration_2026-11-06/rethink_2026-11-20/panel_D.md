# Panel D: usability and staff hours (2026-11-20)

Blind lenses: automation (Saraev), product/UX (Murati), simplicity (Jobs). Starting assumption: the plan is wrong until the evidence says otherwise.
Paths: `FACTS` = rethink_2026-11-20/FACTS.md, `ARCH` = build/ARCHITECTURE.md, `PW` = execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src, `BS` = execution/gtm_client_workflows/greenjobs_redesign/build_site.py.

## 0. Verified code facts that change the picture

1. **Nothing connects the console to the public board.** ARCH:66-72 says a console write sets "publish pending" and the cron calls `DEPLOY_HOOK_URL`. A grep for `DEPLOY_HOOK` / `publish_pending` across the code returns nothing. The cron at PW/index.js:106-131 only retries application deliveries (wrangler.toml:18 says the same). `BS` reads local JSON files (BS:826, BS:2378) and never fetches `/api/export/jobs`. Today a job Rashieda posts reaches D1 and `/api/jobs`, but it never appears on the static pages.
2. **The static job page has no on-site apply.** BS:2439 sets `apply_url` from the scraped `j["url"]` (the old Strategies job URL), and BS:1614 sets `directApply: False`. Once Strategies switches off on 6 Dec (FACTS:7), every Apply button leads to a dead page. `POST /api/apply` exists (PW/routes/apply.js), but no page posts to it.
3. **The console posts to one site at a time.** The page is tied to the request host (PW/routes/console.js:19), and ids carry the site prefix (PW/routes/admin.js:109-112, 156). A job for both IE and UK has to be typed twice.
4. **Sectors, job type and summary cannot be edited after create.** The edit payload leaves them out (console.js:111 compared with :117-118), and so does the server's `EDITABLE` set (admin.js:49). A typo in a sector means closing the job and posting it again.
5. **Sectors are typed free text** (console.js:30). The employer field is free text too (console.js:26), and the server makes a new employer for each new spelling (admin.js:159-165). The **Close** button has no confirmation (console.js:79-83). The job list has no search and stops at 200 rows (console.js:69). The status picker offers only Live/Draft, so a closed job cannot be reopened (console.js:37).
6. **Auto-expiry works in the API only.** `/api/jobs` hides jobs past their closing date (PW/routes/public.js:10). The static pages keep showing them until the next build, and per item 1 nothing triggers that build.
7. **The 8 network sites are not in scope** (ARCH:8-15), yet they are sold to employers and go dark on 6 Dec (FACTS:21).
8. **CHM Recruit and Mattinson lose self-posting on 3 Dec.** Employer log-ins are phase 2 (ARCH:192), so staff must post those jobs. Both contracts end in Jan 2027 (FACTS:15).

## 1. Workflow map: today vs the plan as built

All minutes are **estimates**. The volume of Gaia's own new jobs is **unknown**. I assume **~60 new posts a month across both boards**, inferred from ~220 live jobs that are "mostly Gaia's" (FACTS:16) and an assumed 1-3 month listing life. The ~15 non-Gaia jobs a month come from FACTS:17. I assume half of today's non-Gaia jobs are self-posted. The Strategies screens were not observed, so the step counts for today are estimates as well.

| Workflow | Today, Strategies (steps / est. min/mo) | Plan as built (steps / est. min/mo) |
|---|---|---|
| Rashieda posts a Gaia job | Log in, open the post form, paste from the Vincere/WP job (possibly the same job typed twice by hand: FACTS:22-23), choose sectors and network sites, save: ~6 steps, ~10 min each, **~600** | Access email-code login, 14 fields (console.js:25-37), sectors typed by hand, repeat for the second site, then check the board, which never updates (§0.1): ~8 steps, ~12 min each, **~720**, and the result is not visible |
| Rashieda edits | ~3 steps, 20/mo × 3 min = **~60** | Edit, save, 409 on a stale edit. Sector fixes need a close and repost (§0.4): **~80 + ~60** |
| Rashieda closes | Expiry on the old platform (assumed); manual closes **~30** | One click with no confirmation, and the static page keeps the job (§0.6): **~20** |
| CHM / Mattinson jobs | They self-post: **0 staff min** | Staff post them from email: 15/mo × 12 = **~180** (all non-Gaia) vs **~70** today |
| Diana: admin, exports | Strategies "Download Reports", logins: **~60** | Access allow-list changes go through the developer (STAFF_EMAILS var, ARCH:53). The console has no export or application view. Inbox only: **~60** |
| Employers self-posting | Strategies employer login | **None until phase 2** (ARCH:192) |
| Candidate search | Strategies list | Static list from scraped data, which goes stale after 6 Dec unless the build is wired |
| Candidate apply (phone) | Strategies form | **Broken**: the link points to the dead Strategies URL (§0.2) |
| Candidate alerts | Live, subscriber count unknown (FACTS:20) | Off (`ALERTS_ENABLED="0"`, ARCH:104). Alerts are sold to advertisers (FACTS:20) |
| **Staff total** | **~820 min (~14 h) / month, estimate** | **~1,180 min (~20 h) / month, estimate**: more hours and less working |

## 2. Lens 1: Nick Saraev, automation (ranked)

1. **Pull Gaia's jobs automatically; this removes about 70% of staff time.** gaiatalent.com runs WordPress with a `jobs` post type plus location, category, type and sector taxonomies (FACTS:22). Poll `/wp-json/wp/v2/jobs` every 15 min. Upsert on `{site}:wp:{post_id}`, the id shape the plan already reserves for feeds (ARCH:185-187). Close a job when WP unpublishes it. Map WP sectors onto the GreenJobs list. Gate: this depends on FACTS:23 (whether these are the same jobs), so diff them first. Use Vincere only if WP lacks jobs.
2. **Publish on write.** Either the Worker renders the job pages, or each write calls the deploy hook. This closes the §0.1 gap with no human step.
3. **Nightly auto-expiry.** Default the closing date to 30 days, close expired jobs and rebuild (§0.6).
4. **Weekly alert digest** from live jobs to imported subscribers who gave consent (`Consent`/`Marketing`, FACTS:34). Runs with no human step.
5. **Network sites:** have the same build emit sector-filtered pages for each network domain. Do not maintain them by hand.
- **A human stays in the loop for:** choosing which Gaia jobs to publish (a WP tag), employer/client jobs, failed application deliveries (ARCH:200), and the staff allow-list.

## 3. Lens 2: Mira Murati, product and UX (ranked)

1. **Phone apply is the product, and it does not exist** (§0.2). Build a 4-field form on the job page: name, email, CV, consent (validate.js:285-293 already handles phone and note as optional). Use a sticky Apply button and show a receipt on screen.
2. **Console: post once and pick the sites.** Add IE/UK checkboxes, a sector picklist, an employer picker (stops duplicate employers, admin.js:159), a **Duplicate** button, and a confirmation on Close.
3. **Make every create field editable** (§0.4). Add a "Closed" status and a reopen option.
4. **After Save, show a "View live" link** so Rashieda can see the job is up instead of guessing.
5. **Cut the apply modes from 4 to 2** (email or URL), matching the export's `Email`/`AppLink` columns (FACTS:19). Today four modes plus two fields (console.js:34-36) is the main thing new staff would have to learn.
6. Add search and a status filter to the job list (console.js:69). The Access login is new for staff, so give them a one-page screenshot guide.

## 4. Lens 3: Steve Jobs, simplicity (ranked)

**The one thing:** a candidate on a phone finds a green job and applies in under a minute, and a job posted shows up within minutes. Everything else is secondary.

Say **no** to:
1. Employer log-ins: two clients whose contracts end Jan 2027 (FACTS:15).
2. Broadbean/Idibu/LogicMelon feeds: none are live (FACTS:14).
3. A CRM integration.
4. Candidate log-ins.
5. Importing ~178k candidate profiles into the app. Archive them; import only alert subscribers who gave consent.
6. A newsletter engine. Send it from an existing mail tool.
7. The Draft status.
8. Four apply modes. Keep two.
9. Free-text sectors.
10. A separate post for each site.

## 5. VERDICT: **AMEND**

The floor is right: boards, console and apply. The pipe between them is missing, though, and the plan raises staff hours. Simplest system that cuts staff hours:

1. Job pages are served from D1, either rendered by the Worker or rebuilt on every write, and appear within minutes.
2. An on-site 4-field apply form posts to the existing `/api/apply`.
3. Gaia jobs sync automatically from the gaiatalent.com WP REST API with a "publish to GreenJobs" tag, after FACTS:23 is confirmed.
4. One console form with site checkboxes, a sector picklist, an employer picker, Duplicate, a Close confirmation and full editing.
5. Auto-expiry: 30-day default, nightly close and rebuild.
6. A weekly alert digest to subscribers who gave consent, fully automatic.
7. Each network domain shows its sector's jobs from the same build (or a 301 to the sector page, confirmed with Keith because it changes what was sold).
8. CHM/Mattinson jobs: staff post them from forwarded emails until Jan 2027. No employer log-ins.

Estimated staff time under this system: Gaia spot checks ~30 + non-Gaia 15 × 6 = 90 + edits ~60 + Diana ~30 ≈ **~210 min (~3.5 h) / month (estimate)**, against ~14 h today and ~20 h for the plan as built.

**Claim:** syncing Gaia's jobs from gaiatalent.com removes most staff hours.
**Objection:** FACTS:23 says it is unknown whether these are the same jobs, and WP may lack the apply email or closing date.
**Resolution:** amend. Diff the 16 Nov live list against WP REST first. Ship console + publish + apply for 3 Dec (the floor), and add the sync in week 2 behind a WP tag.
