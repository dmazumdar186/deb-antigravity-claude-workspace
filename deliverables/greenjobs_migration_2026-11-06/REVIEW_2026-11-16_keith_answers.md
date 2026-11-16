# GreenJobs: project review of Keith's team's answers (16 Nov 2026, v2 project only)

Internal. Not for sending. The legal question is parked until the operator's lawyer call (Wed 18 or Thu 19 Nov).

Sources:
- Diana's 11 Nov email, forwarded by Keith on 16 Nov.
- Rashieda's 10 Nov answers.
- A live public DNS and site check run today.
- The offline test run today: 131 Worker tests and 28 import tests pass.
- Two blind reviews: delivery and data, and client and commercial.

## 1. What each answer means

| Q | Answer | Firm? | What it changes |
|---|---|---|---|
| 1 Domains | "Not sure"; posting by sector goes to another site automatically | Weak | Live DNS: all 8 network sites (conservation, ecology, environmental, renewable, wind, solar, waste, water `…jobsuk.com`) point to the same Strategies host as greenjobs.co.uk. They go dark on 6 Dec. |
| 2 DNS | .ie at Hosting Ireland; .co.uk at LetsHost; the others at 123 Reg; Diana has "almost all" | Firm | Live: .ie nameservers are webhostingireland; .co.uk nameservers are dnsireland (SOA letshost); the network domains use GoDaddy nameservers. A bare domain on Cloudflare Pages needs Cloudflare nameservers, so runbook path A is the only path. |
| 3 Email | Hosting Ireland | Firm | Live: MX for both domains is Hosting Ireland. Copy every record from the host's zone export (`dig` misses records), email records first. SPF includes `spf.strategiesuk.net`; tidy it after 6 Dec. |
| 4 Exports | Diana and Rashieda, in the admin on the GreenJobs domains | Firm | The admin dies at the switch. "Members profile data" only runs outside 09:00–17:00 UTC. |
| 5 Retention | "Not sure" | Open | Keith decides in writing. Until then: download everything as a raw archive; import jobs and employers only. |
| 6 Posting | Mostly Rashieda; CHM Recruit and Mattinson Partnership post themselves (contracts to Jan 2027) | Firm | Those two lose self-posting on 3 Dec. Staff post for them, and they get notice by Wed 25 Nov. |
| 7 Tools | Broadbean "in the past, not sure now" | Weak | Check whether any live job came in from a feed. If one still feeds, it stops silently on 3 Dec. |
| 8 Applications | Per client: an email or an ATS link | Firm | Per-job apply mode (email or link) in the console, 0.5 day. |
| 9 Volumes | ~15 new jobs a month; employers 1,616 UK / 418 IE; live jobs 105 / 133; candidates 147,681 / 30,097 | Mostly | Live today: 78 UK / 145 IE, mostly Gaia Talent's own jobs, so real posting volume is higher than 15. The alert subscriber count is missing; the "Jobs By Email" export gives it. |
| 10 Payments | None online; invoices and Revolut | Firm | Nothing to build. Online payment is a later quote. |
| 11 Analytics | Doesn't know how; logos OK "I suppose"; asked about AuthorityLabs | Weak | Not needed from her: we hold the GA4 IDs (IE G-ZQPJGM484J, UK G-ZFW03XQE2N; Ecology and Renewable have their own), and Search Console can be re-verified by DNS. Need a one-line OK on logos from Keith. AuthorityLabs is not relevant. |
| 12 Signer | Keith | Firm | Still need: the company name for the contract (GreenJobs Ltd on the sites; Gaia Talent Ltd pays). |

8 of the 12 are firm (67%).

## 2. Misses (things that would have surfaced later as "you should have told me")

1. **The 8 network sites die on 6 Dec,** and they are not in the plan. Employers are sold "displayed on all relevant network websites". The minimum fix is to forward each domain to its sector page on greenjobs.co.uk; full separate sector sites are quoted later.
2. **Alerts and the weekly newsletter are paid advertiser features,** and the plan promised alerts for 3 Dec. They must not be first in the trim order without Keith's word.
3. **Diana's answers went to `dmazumdar@teamprodcraft.com`.** Five working days were lost, and the 16 Nov 16:42 email asked for answers already given. Ask everyone to use debanjan@prodcraft.fyi.
4. **Runbook path B doesn't work** for the bare domains. Path A means moving nameservers, which carries email, so email records are copied first.
5. **The export login lives on the domains.** Once DNS moves, the export is gone. The profile export only runs outside 9–5 UTC, and it is roughly 178k candidates done by hand.
6. **No real export file has been seen.** The import headers are guesses, so a one-row sample of each of the 5 types is needed early.
7. **Self-posters (CHM, Mattinson) and possibly Broadbean** stop silently on 3 Dec.
8. **Real posting volume is higher than "15 a month"** (Gaia's own jobs), so the console must be quick for Rashieda.
9. **The €1,500 Q1 payment is missing from the 9 Nov email.** The contract must hold both terms.
10. **conservationjobsuk.com already has a TLS certificate mismatch.** It was there before us; tell Keith.
11. **The plan's own dates have slipped.** Build from 10 Nov, inputs by 11 Nov: none of it happened.

## 3. Front to back (today forward)

1. **Mon 16 – Tue 17 Nov.** Reply to Keith: answers received; the right address; start the downloads now; send the 5 one-row samples; ask for the logins.
2. **Wed 18 – Fri 20 Nov.** Contract and DPA out, signed, first month paid. Logins to Hosting Ireland, LetsHost and 123 Reg arrive through a password manager. A Cloudflare account is opened in GreenJobs' name. The import is fixed against the real headers. A test site goes up on `*.pages.dev`.
3. **Mon 23 – Wed 25 Nov.** Console: post, edit and close, with apply by email or link. Redirect map. Network domains forwarded on the test plan. CHM and Mattinson told.
4. **Thu 26 – Fri 27 Nov.** Zone exports; every record recreated in Cloudflare; Keith signs off the test site; full raw archive done; alerts decision.
5. **Mon 30 Nov.** Nameservers move (web still points to Strategies); email tested.
6. **Tue 1 Dec.** Short TTLs; sender records for alerts and application mail.
7. **Wed 2 Dec.** Final download; posting freeze at 17:00; go/no-go.
8. **Thu 3 Dec.** Switch the web records; test each site; network domains forward.
9. **Fri 4 Dec, 17:00.** Last chance to switch back. After that, 10 days of daily checks.

## 4. Back to front (what must already be true)

1. **To survive Sun 6 Dec,** all 10 domains point away from Strategies and every report is downloaded.
2. **That needs a switch on Thu 3 Dec,** which needs Cloudflare holding both zones with email intact by Mon 30 Nov.
3. **That needs the zone exports by Thu 26 Nov,** which need the registrar and host logins by Fri 20 Nov.
4. **The import needs real samples by Fri 20 Nov.** The archive needs downloads starting this week, which needs the DPA.
5. **The DPA and logins need a contract.** So the contract, DPA and first payment by **Fri 20 Nov** is the hinge of the whole plan. Mon 23 Nov is the absolute latest; after that only the floor ships: jobs, staff console, applications, raw archive.

## 5. Negative scenarios

| # | What goes wrong | Chance | Damage | Earliest warning |
|---|---|---|---|---|
| 1 | Network sites go dark | High (if not planned) | Advertiser promise, SEO | Wed 25 Nov |
| 2 | Signature or payment slips past 20 Nov | Medium-high | Everything compresses | Fri 20 Nov |
| 3 | Downloads incomplete before the switch | Medium-high | Data lost for good | Fri 27 Nov |
| 4 | Real export headers break the import | Medium | Import slips | First sample |
| 5 | Email breaks on the nameserver move | Medium-low | High | Thu 26 Nov |
| 6 | A bare domain is down | Medium | High | Mon 30 Nov |
| 7 | Self-posters or a feed stop silently | Medium-high | Client contracts | Wed 25 Nov |
| 8 | Alerts land in spam or get cut | High | Broken promise | Fri 27 Nov |
| 9 | Diana has no time for the downloads | Medium | Archive incomplete | Fri 20 Nov |
| 10 | Logins are missing ("almost all") | Medium | Switch blocked for that domain | Fri 20 Nov |

## 6. Scores (project only)

| Area | Score | Basis |
|---|---|---|
| Answers from Keith's team | 67/100 | 8 of 12 firm |
| Code | 75/100 | 159/159 tests pass offline; nothing deployed; no real export file; network forwarding and alerts not built |
| Access | 5/100 | No logins in hand |
| Agreement (contract, DPA, payment) | 10/100 | Ready to draft; nothing sent |
| Data safety | 15/100 | No downloads yet |
| Time | 40/100 | About 12 working days left against 18–22 estimated, partly covered by the build pack |
| **Overall: both boards switched safely on 3 Dec** | **40/100** | About **65** if the Fri 20 Nov hinge holds; about **80** once the test site is signed off on 27 Nov |

## 7. Upfront payment (project view only)

- Asking is commercially right and expected. Keith agreed to "€600/month starting now"; his budget limit was the €1,500, which is deferred to Q1.
- Send it as a package, never as a bare money ask: contract (both terms) + DPA + invoice, after a "here's where we are" email.
- Probability Keith pays within 5 working days of receiving the package: about 60%. It is lower if it lands before the "answers received" email, and higher once he sees the test site moving.
- Timing: send the package right after the lawyer call (Wed 18 or Thu 19 Nov). That still meets the Fri 20 Nov hinge.
