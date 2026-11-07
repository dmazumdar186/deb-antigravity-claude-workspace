# GreenJobs: decision table for Keith's twelve answers

Written 2026-11-07. Internal. One row per question, worded as in `../transition_plan.html`. For each likely answer:
the change it triggers (file + key or flag), effort, and its effect on the 3 Dec floor.

Floor (never trimmed): boards on Keith's domains with current jobs; staff posting console; applications to an
inbox. Trim order: alert emails, candidate record import, newsletter. Config keys live in the Worker
`greenjobs-platform` (`execution/gtm_client_workflows/greenjobs_redesign/platform_worker/`, vars in its wrangler
config, secrets as Worker secrets).

Effect codes: **OK** no threat to the floor; **RISK** threatens 3 Dec; **TRIM** moves a trimmable item;
**P2** moves to phase 2; **QUOTE** out of scope, quoted separately.

| Q | Question (as sent) | Likely answer | Change it triggers | Effort | Effect |
|---|---|---|---|---|---|
| Q1 | Domains. Which domains are on the Strategies contract: just greenjobs.ie and greenjobs.co.uk, or other sites too? | Just the two boards | `HOST_SITE_MAP` maps apex + www of both to `ie` / `uk`. Nothing else | 0 | OK |
| | | Two boards plus network sites (the network has 10 sites per `brief.md`) | Scope change, quoted separately. Each extra site needs a `HOST_SITE_MAP` entry **and** a schema migration (`site` is `CHECK (site IN ('ie','uk'))` in every table of `d1/schema.sql`), plus its own export and DNS rows | Per site, quoted | QUOTE; RISK if Keith wants them by 3 Dec |
| | | Not sure | Ask Strategies for the contract domain list; build for two | 0 | OK until answered |
| Q2 | DNS. Who manages DNS and domain registration for them, and who there can make changes? | Registrar login shared with us (password manager) | Runbook path A: zone in GreenJobs' Cloudflare account, NS move at T-3 | 0.5 d | OK |
| | | An IT person or agency makes changes | Runbook path A or B, depending on whether they will move nameservers; switch-day slot booked with them | 0.5 d + their calendar | OK if booked by Wed 11 Nov |
| | | Nameservers cannot move | Runbook path B: `www` CNAME to `*.pages.dev`, apex via ALIAS or forward to www; Worker reached via Pages binding or `workers.dev` + `ALLOWED_ORIGINS` | +0.5 d | OK |
| | | Nobody knows | Registrar lookup (WHOIS) and recovery through the registrar by Keith | Unknown | RISK: blocks staging on a custom subdomain and the switch; staging stays on `*.pages.dev` |
| Q3 | Email. Who hosts the email on those domains (for example info@)? | Google Workspace | MX / SPF / DKIM / DMARC and the Google verification TXT go into the runbook inventory, copied exactly from the zone export | 0.25 d | OK |
| | | Microsoft 365 | Same, plus the autodiscover CNAME and Microsoft verification TXT | 0.25 d | OK |
| | | Another host (registrar mail, Strategies, other) | Same inventory. If Strategies hosts mail, mail needs its own move before Sun 6 Dec: separate mini-plan | 0.25 d, or +1 d if Strategies | OK; RISK if Strategies hosts mail |
| Q4 | Exports. Who on your side can log in to Strategies and run the 'Download Reports' exports with me (five data types per site, in batches)? | A named person on Keith's team | Export rota with them from DPA signature; files to GreenJobs storage; `strategies_import.py --site --report` per batch | 1 to 2 d manual | OK if it starts week 1 |
| | | Keith shares the admin login | Same; we run it in his session; login via password manager | 1 to 2 d | OK |
| | | Nobody has time | Boards still go live with jobs from the refreshed scrape; candidate import is the first item to trim after alerts | 0 | TRIM (candidate import) |
| Q5 | Retention. How far back should we keep candidate and application records? Strategies flagged data protection; I'd suggest two years. | Two years | `strategies_import.py --retention-months 24` (default) | 0 | OK |
| | | Shorter or longer, N months | `--retention-months N`, bounded 6..84; outside the bound needs the operator's word | 0 | OK |
| | | Keep nothing / start clean | No candidate or application import; jobs and employers only. Export archive kept in GreenJobs storage | 0 | TRIM (candidate import) |
| Q6 | Posting today. Who posts jobs today: your team, advertisers themselves, or both? | Keith's team | Console is the only posting path; `STAFF_EMAILS` lists the posters (Access free tier, up to 50 users) | 0 | OK |
| | | Advertisers themselves | Stays staff-posted on 3 Dec (advertisers send jobs to staff). Employer log-ins in phase 2 | 0 now | P2 |
| | | Both | As above; staff volume checked against Q9 | 0 now | P2 |
| Q7 | Posting tools. Which of Broadbean, Idibu and LogicMelon are used, who owns those accounts, and which CRM do you post from? | None | No feed work; phase 2 list shrinks | 0 | OK |
| | | One or more of the three | One feed adapter each in phase 2: ingest endpoint writing `jobs` with `source='feed'`, id `'{site}:{feed}:{ref}'`; vendor onboarding on their clock; staff post by hand until live | 2 d each + vendor lead time | P2 |
| | | A CRM (for example Vincere or Recruit CRM) | One CRM adapter in phase 2 (cap: one CRM); others quoted | 2 d | P2; QUOTE beyond one |
| Q8 | Applications. Where should applications go: one inbox, the consultant on each job, or the advertiser? | One inbox | `APPLY_ROUTING="inbox"`, `APPLY_INBOX_IE`, `APPLY_INBOX_UK` | 0 | OK |
| | | The consultant on each job | `APPLY_ROUTING="consultant"`; console requires `apply_email` on every job (`jobs.apply_email`) | 0.25 d | OK |
| | | The advertiser | `APPLY_ROUTING="advertiser"`; address from the job's `apply_email` or employer contact; `apply_mode='url'` where the advertiser has an ATS link (`jobs.apply_url`, https only) | 0.5 d | OK |
| | | A mix | Per-job `jobs.apply_mode` (inbox, consultant, advertiser or url), `APPLY_ROUTING` as the default | 0.5 d | OK |
| Q9 | Volumes. Roughly how many jobs a month, live candidate accounts, alert subscribers and employer accounts? | Low (tens of jobs, a few thousand candidates) | Defaults for `RATE_APPLY_PER_10MIN`, `RATE_ADMIN_PER_MIN`, `MAX_CV_BYTES`; all free tiers | 0 | OK |
| | | High alert subscriber count | Alerts on a new sender need warm-up: trim decision on alerts (`ALERTS_ENABLED="0"`) by Fri 27 Nov | 0 | TRIM (alerts) likely |
| | | High job volume per day | Raise `RATE_ADMIN_PER_MIN`; check rebuild cadence (one rebuild per 5 min cron at most) | 0.25 d | OK |
| | | Unknown | Defaults; revisit after 10 days of checks | 0 | OK |
| Q10 | Payments. Do any advertisers pay online today (featured jobs, packages)? | No | Nothing | 0 | OK |
| | | Yes | Out of scope for 3 Dec and for phase 2 (employer log-ins exclude purchasing). Quote separately. No code | 0 | QUOTE |
| Q11 | Analytics. Who can give me access to Google Analytics and Search Console for both boards? | Keith or his marketing person grants access | GA4 IDs kept: G-ZQPJGM484J (IE), G-ZFW03XQE2N (UK), not yet wired: the 22 Sep build ships only a `track()` stub and no GA4 tag (verified: no GA4 ID in `build_site.py` or `src/config.json`). Change: add a per-edition `ga4_id` to `src/config.json` and emit the gtag snippet behind the cookie Analytics toggle. Search Console: sitemap resubmit on switch day | 0.25 d | OK |
| | | Nobody has access | Keep the same GA4 IDs anyway; Search Console verified again via DNS TXT after the switch | 0.25 d | OK (SEO checks delayed) |
| Q12 | Contract. Who signs the contract and data processing agreement on your side, and by when? | Keith, Mon 9 Nov | DPA gate opens: CSV exports start | 0 | OK |
| | | Keith, later in the week | Non-candidate work runs; no CSV reaches us until the DPA is signed. If signing passes Wed 11 Nov, 6 Dec does not move and trims are agreed in writing | 0 | RISK to candidate import; TRIM likely |
| | | Someone else, date unknown | Same gate; chase daily | 0 | TRIM (candidate import) |

## Monday-evening triage (Mon 9 Nov)

**Nothing blocks Tuesday's start.** Work that touches no candidate data starts Tue 10 Nov: posting console,
front-end refresh, redirect map, staging on `*.pages.dev`.

**Blocks specific work:**

| Answer missing | What waits | Last safe date |
|---|---|---|
| Q12 (DPA signed) | Every CSV export and import, any candidate data work | Wed 11 Nov (inputs deadline); after that, trims agreed in writing |
| Q4 (exporter) | Exports | Wed 11 Nov |
| Q2 (DNS holder) | Custom staging subdomain, path A/B choice, switch-day booking | Wed 11 Nov |
| Q3 (mail host) | MX inventory for the runbook | T-7, Thu 26 Nov |
| Q1 (domain list) | Scope confirmation in the contract | Contract signature |
| Q11 (analytics access) | Search Console checks | Thu 3 Dec |

**Defaults if a question is unanswered:**

| Q | Default taken |
|---|---|
| Q1 | Two boards only; anything else quoted |
| Q2 | Staging on `*.pages.dev`; plan for path A, prepare path B |
| Q3 | Inventory from public DNS (`dig`) and confirm on T-7 |
| Q4 | Candidate import is at risk; boards go live with jobs from the refreshed scrape |
| Q5 | `--retention-months 24` |
| Q6 | Staff post only |
| Q7 | No feeds before 3 Dec; phase 2 list stays as written |
| Q8 | `APPLY_ROUTING="inbox"` with `APPLY_INBOX_IE=info@greenjobs.ie`, `APPLY_INBOX_UK=info@greenjobs.co.uk` (the published contact addresses), confirmed by Keith before go-live |
| Q9 | Default rate limits; alerts decision on Fri 27 Nov |
| Q10 | No online payments in scope |
| Q11 | Keep both GA4 IDs; Search Console after access arrives |
| Q12 | No candidate data until signed |
