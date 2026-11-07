# GreenJobs: moving off Strategies by 6 Dec 2026 (feasibility matrix)

Written 2026-11-06 (Fri). Internal working doc, not for sending. Sources in brackets.

## 1. What Keith is actually asking

Keith has given Strategies notice. They host the **GreenJobs job boards** (greenjobs.ie, greenjobs.co.uk:
"Job Board website by Strategies", classic ASP), not gaiatalent.com, which is WordPress by Hidden Depth
[`greenjobs_redesign_2026-09-22/src/data/brief.md:14,95`; `gaia_redesign_2026-09-17/research/gaiatalent_com_audit.md:158-174`].

He forwarded Strategies' exit note and asked one thing: **"let me know what you need to ensure a smooth
transition."** The note itself tells us the constraints:

| Fact from Strategies' note | What it means for us |
|---|---|
| Contract ends **Sun 6 Dec 2026**, billed to the end even if DNS moves earlier | Hard deadline: **20 working days** from Mon 9 Nov. Keith pays Strategies plus us in November, so there is no money reason to cut over early. |
| Content is only copy-paste from pages; images saved by hand | No content export. We already hold a scrape of every role and page (165 roles, 22 Sep snapshot) [`greenjobs_redesign_2026-09-22/HANDOFF.md`]. We refresh it and add a full static archive. |
| Data comes from admin → "Download Reports": recruiters, candidate registrations, profiles, jobs, applications. CSV, per type, **per site**, in batches of a few months | Someone with the admin login has to run it, or give us the login. It's slow and manual, so it starts **this week**, not in week 4. |
| "Data protection considerations" about old records | Keith is the data controller and we're the processor. Sign a DPA before any CSV reaches us. Import only records still worth keeping. |
| Changing DNS cuts access to the old sites; temporary URLs cost extra | Export everything **before** DNS moves. DNS isn't managed by Strategies, so someone else (a registrar or IT person) holds it. We need to find out who. |
| "each of your sites" | Strategies may host more than the two boards (the network has 10 sites [`brief.md:28-29`]). **This is the biggest scope question.** |

Our side of the deal (LinkedIn): **€600/month from now, plus €1,500 in Q1 2027**, written into a contract.
This replaces the 30 Sep proposal (€4,998 build + €999/month, 6-week plan with go-live 18 Nov)
[`proposal/GreenJobs_Proposal_v1.0_2026-09-30.md:75-128`]. Nothing is signed yet.

## 2. Read through each senior lens

- **Executive / leadership:** Keith wants zero downtime and no lost data, and he has already committed (notice given). Our job is to take the worry off him: one list, one timeline, one owner.
- **Project:** we have 4 weeks of work against a 6-week plan. The front end is built and tested; the platform (accounts, alerts, posting console, multiposter feeds) is **not** built. The worker in `execution/.../greenjobs_redesign/worker/` is only the Ask-GreenJobs stub.
- **Technical:** the critical path is DNS access, the data export, the posting routes (Broadbean / Idibu / LogicMelon) and email (MX, SPF, DKIM) surviving the DNS change. Passwords won't export, so candidates have to set a new one.
- **Data / legal:** GDPR Art. 28 DPA; a retention cut-off (e.g. candidates active in the last 24 months); CSVs stored only in the client's accounts, never in git or `.tmp`. The password-reset email also needs a lawful basis and a notice.
- **Commercial / sales:** €600/month for a compressed build is thin. The contract has to fix the **6 Dec MVP scope** and put the rest in phase 2, or scope creep eats the margin. It also needs a written Q1 €1,500 date.
- **Marketing / SEO:** a 301 map from the old ASP URLs, JobPosting schema, keeping the GA4 IDs (G-ZQPJGM484J IE, G-ZFW03XQE2N UK [`brief.md:96`]) and resubmitting to Search Console, so Google for Jobs doesn't drop the roles.
- **GTM / strategy:** this is the foothold. Land it cleanly and gaiatalent.com plus the 8 network sites follow as paid scope (already excluded in the proposal, `:85`).

## 3. Feasibility matrix

RAG is for "live by Thu 3 Dec" (3 days of buffer before the 6 Dec cut-off).

| # | Workstream | Built already? | Needs from Keith / 3rd party | Effort | Risk | RAG |
|---|---|---|---|---|---|---|
| 1 | Contract (€600/mo + €1,500 Q1) + DPA | No | Signature | 0.5 d | Work starts unsigned | 🟢 |
| 2 | Scope: which sites Strategies hosts | — | List of every domain on the Strategies contract | — | 10 sites, not 2 | 🟠 until answered |
| 3 | DNS + registrar access, Cloudflare account in GreenJobs' name | No | Registrar login or the IT contact; current zone file | 0.5 d | Unknown holder; MX lost on cut-over | 🟠 |
| 4 | Email on the domains (info@ inboxes, MX) | No | Who hosts the mailboxes | 0.5 d | Mail outage at cut-over | 🟢 if MX is copied first |
| 5 | Data export (5 report types × 2 sites, batched) | No | Admin login or Keith's staff running it; retention cut-off decision | 1–2 d manual | Timeouts; slow; PII handling | 🟢 if it starts wk 1 |
| 6 | Content archive (pages, images) | Partly (22 Sep scrape) | Nothing | 0.5 d | Pages missed by the scrape | 🟢 |
| 7 | Front end IE + UK (100 change items, schema, sitemaps) | **Yes**, 3,047 checks | Logo permissions, testimonials | 1 d refresh + deploy | Low | 🟢 |
| 8 | Staff posting console (admin posts / edits / closes jobs) | No | Who posts today, volume per month | 3–4 d | Core MVP | 🟢 |
| 9 | Applications → employer / consultant inbox | No | Where applications go today | 1–2 d | Core MVP | 🟢 |
| 10 | Candidate accounts, CV store, saved jobs | No | Count of live accounts | 3–4 d | Password reset email; consent | 🟠 |
| 11 | Job alerts + weekly newsletter (Resend) | No | Subscriber count; sender domain DNS (SPF/DKIM) | 2 d | Deliverability on a new sender | 🟠 |
| 12 | Employer / recruiter accounts | No | Count; paying advertisers? | 2–3 d | Billing/packages are out of scope | 🟠 |
| 13 | Multiposter feeds (Broadbean, Idibu, LogicMelon) | No | **Which ones are used**, account owners, contacts | 2 d each + vendor lead time | Broadbean onboarding runs on their clock | 🔴 by 3 Dec; 🟢 with manual fallback |
| 14 | CRM posting (Vincere or Recruit CRM?) | No | Which CRM; API plan | 2 d | Unclear which CRM | 🟠 → phase 2 |
| 15 | Data import + dedupe | No | Exports from #5 | 1–2 d | Dirty CSVs | 🟢 |
| 16 | 301 redirect map, GA4, Search Console | Partly | GA / Search Console access | 1 d | SEO dip | 🟢 |
| 17 | Parallel run + DNS cut-over + 10 days of checks | — | Written sign-off | 3 d | Slip into the weekend of 5–6 Dec | 🟠 |

Total for the MVP (#1–9, 11, 15–17): about **18–22 working days** against 20 available. That's tight but feasible
**only if** #13 and #14 move to phase 2 and staff post by hand through the console in the meantime.

## 4. Debate on the plan

- **Claim:** full platform parity by 6 Dec. **Objection:** the platform alone was scoped at 3 weeks plus a 2-week parallel run, and Broadbean's lead time is outside our control. **Resolution: amend.** Ship the MVP by 3 Dec (front end, posting console, applications, alert sign-up, imported data, redirects). Multiposters, CRM posting and employer self-service come in phase 2 (Dec–Jan), covered by the €600/month.
- **Claim:** move DNS early to get off Strategies sooner. **Objection:** they bill to 6 Dec anyway, and an early move kills access to the export. **Resolution: drop.** Cut over on Thu 3 Dec, after the final delta export.

## 5. Timeline (20 working days)

| Week | Dates | Outcome |
|---|---|---|
| 0 | Mon 9 Nov | Keith gets the requirements list (§6). Contract + DPA signed. |
| 1 | 9–13 Nov | Inputs deadline Wed 11 November: contract, DPA and access to DNS, Strategies and analytics; any slip moves the switch date. Access in hand (DNS, Cloudflare, Resend, GA). Exports run. Front end deployed on a staging subdomain. |
| 2–3 | 16–27 Nov | Posting console, applications, candidate accounts, alerts, import. Staging acceptance with Keith and the site manager. |
| 4 | 30 Nov–3 Dec | Final delta export, parallel check, DNS cut-over Thu 3 Dec, daily checks. Fri 4 Dec is the buffer. |
| After | Dec–Jan | Phase 2: Broadbean / Idibu / LogicMelon, CRM posting, employer self-service. €1,500 due Q1 per contract. |

## 6. What we need from Keith (the core of the Monday reply)

1. Every domain on the Strategies contract (just the two GreenJobs boards, or the network sites too?).
2. Who manages DNS and the registrar for each domain, plus a login or a contact who can make changes.
3. Who hosts the email on those domains (so info@ keeps working through the switch).
4. Admin access to Strategies for the data export, or a named person on his team to run it, and his retention cut-off (we suggest records active in the last 24 months).
5. Which posting tools his recruiters and advertisers use (Broadbean, Idibu, LogicMelon) and who owns those accounts.
6. Roughly how many live candidate accounts, alert subscribers, employer accounts and jobs per month.
7. Whether any advertisers pay online today (featured jobs, packages).
8. Access to Google Analytics and Search Console for both boards.
9. Logo permissions and testimonials (the launch checklist from 22 Sep).
10. A 20-minute call on Monday to walk through the plan and sign the contract and DPA.

A reply to Keith built from §6 counts as outward text, so it has to pass `/redteam` before it is sent.

## 7. Contract terms that bound the scope (added after red-team round 2)

- Keith signs off on the test address by Fri 27 November. If inputs slip, we cut the 3 December scope rather than move the date, because Strategies switches off on 6 December. A changed switch date is a schedule change agreed in writing, not a breach.
- Each 3 December item has a short acceptance list in the contract, tested on the test address before the switch. There are 10 days of daily checks after the switch.
- Trim order for 3 December is agreed in writing. Advertiser online payment (featured jobs, packages) is not in the 3 December list.
- Phase 2 (Dec–Jan, covered by the monthly arrangement) is a named list with a target date per item: candidate log-ins, employer log-ins, Broadbean / Idibu / LogicMelon feeds, CRM posting. Anything off the list is quoted separately.
- Until candidate log-ins arrive, candidates browse and apply without an account. Passwords won't come across in the exports, so candidates set a new one when log-ins go live.
- Logins are shared through a password manager, never in a chat message.
