# GreenJobs rethink: confirmed facts (2026-11-20)

Every line carries its source. Anything not here is unknown.

## Client and deadline
- Client: Keith Molony, Gaia Talent Ltd (a recruitment agency), which owns the GreenJobs boards greenjobs.ie and greenjobs.co.uk. Source: keith_linkedin_thread_2026-11-06.txt; REVIEW_2026-11-16 Q12.
- The current host is Strategies (classic ASP job-board platform). The contract ends **Sun 6 Dec 2026**. After that the sites are switched off, and access afterwards costs a fee. Source: keith_linkedin_thread_2026-11-06.txt line 10.
- Price agreed in principle: €600/month from now, plus €1,500 in Q1 2027. Not yet signed. Source: keith_linkedin_thread lines 3-6; REVIEW §7.
- Planned switch: Thu 3 Dec. Source: build/README.md.

## Volumes and people
- Staff: Diana Lupu (finance administrator, non-technical; runs exports and holds the logins) and Rashieda (posts most jobs). Source: REVIEW Q4, Q6; SOURCE_diana_2026-11-19.txt.
- **Gaia Talent posts its own jobs manually.** Source: Diana's email, 19 Nov 15:17.
- **No live jobs come through Broadbean or another tool.** Source: Diana, 19 Nov.
- Two clients post jobs themselves: CHM Recruit and Mattinson Partnership (contracts run to Jan 2027). Source: REVIEW Q6.
- Live jobs, as stated by the client: 105 UK / 133 IE. Observed live on 16 Nov: 78 UK / 145 IE, mostly Gaia's own jobs. Source: REVIEW Q9.
- The client says about 15 new jobs a month (this excludes Gaia's own). Employers on record: 1,616 UK / 418 IE. Candidates: 147,681 UK / 30,097 IE. Source: REVIEW Q9.
- Payments: none online; invoices and Revolut. Source: REVIEW Q10.
- Applications: each client uses either an email address or an ATS link. Source: REVIEW Q8. The Jobs export has `Email` and `AppLink` columns. Source: build/import/REAL_HEADERS_2026-11-19.json.
- The alert subscriber count is unknown. The "Jobs By Email" export has 13 columns. Alerts and the weekly newsletter are sold to advertisers. Source: REVIEW §2.2; REAL_HEADERS.
- The 8 sector "network" sites (conservation, ecology, environmental, renewableenergy, wind, solar, waste, water …jobsuk.com) are sold to employers as "displayed on all relevant network websites". They run on the same Strategies host and also go dark on 6 Dec. Source: REVIEW §2.1; build/dns/ZONE_INVENTORY_2026-11-20.md.
- Gaia's own site, gaiatalent.com, runs on WordPress with a custom "jobs" post type and taxonomies (location, category, type, sector). Gaia's CRM is Vincere. Source: deliverables/gaia_redesign_2026-09-17/research/gaiatalent_com_audit.md lines 141, 173.
- **Unknown:** whether Gaia's jobs on GreenJobs are the same jobs as on gaiatalent.com (double posting by hand). Being checked.

## DNS and hosting
- greenjobs.ie: domain, hosting, email and SSL are all at Hosting Ireland.
- greenjobs.co.uk: LetsHost.
- The 8 network domains: 123 Reg (nameservers GoDaddy).
- Diana can log in to all three. Logins send codes to the info@ inboxes.
- Source: Diana, 19 Nov; build/dns/ZONE_INVENTORY_2026-11-20.md.

## Exports (real headers in hand, no data yet)
- Six types per site: Recruiters, Members registration, Members profile, Jobs, Jobs By Email, Job Applications.
- Members data carries `Consent` and `Marketing` fields.
- Source: REAL_HEADERS_2026-11-19.json.

## Current plan (what is under review)
- Custom build on Cloudflare: static Pages sites, a Worker API, a D1 database, R2 for CVs, Cloudflare Access for the staff console, Resend for email.
- Both boards plus a custom staff posting console.
- Phase 2 (Dec–Jan): candidate and employer logins, feeds, CRM.
- 159 offline tests pass. Nothing is deployed.
- Source: build/ARCHITECTURE.md, build/README.md, FEASIBILITY_MATRIX.md.
