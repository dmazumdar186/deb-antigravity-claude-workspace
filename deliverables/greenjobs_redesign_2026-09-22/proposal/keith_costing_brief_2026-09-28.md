# Keith Molony (Gaia Talent / GreenJobs) — costing brief and reply plan
Date: 2026-09-28. Trigger: Keith's LinkedIn DM 11:31 ("overall feedback is very positive… Can you give me a costing for this and what you can offer?").

## 1. What we now know (research, 2026-09-28)

| Item | Finding | Source |
|---|---|---|
| Keith | Managing Director, Gaia Talent (Ireland's first green-sector recruiter, ~9 staff). Owns greenjobs.ie and greenjobs.co.uk (trading as GreenJobs Ltd, Ennis). | linkedin.com/in/keith-molony-3715473, gaiatalent.com/team, repo notes |
| Current job-board supplier | **Strategies (strategies.co.uk)**, hosted job-board platform. Public "from £899/month" (~€1,030), pricing "based on functionality, integrations and support". Includes hosting, security, SEO, support, employer self-service, candidate accounts, job alerts, CV database, Broadbean / Idibu / LogicMelon / JobAdder integrations. 8–12 week delivery. Tiers: Launch / Grow / Scale. | strategies.co.uk/job-board-software, softwareadvice.co.uk/software/280453/jobweb |
| gaiatalent.com supplier | Hidden Depth (Dublin), WordPress + Elementor, "CloudPress site care plan" included. Published fees €5k–€50k, 40% deposit. | hiddendepth.ie/made/gaia-talent |
| Keith's likely recurring spend today | Strategies ≥ €1,030/mo (2 boards may be one contract or two) + WP care plan €50–250/mo ⇒ roughly **€1,100–1,400/month, €13–17k/year** before any ad spend. | derived |
| Our prior quote | €1,875 for the GreenJobs redesign; Keith "not yet convinced it's value for money". Moving off the vendor was flagged as "a second job", never priced. | research/panel_pass.md |
| What we built | GreenJobs IE+UK demo: 204 static pages, 186 real roles, filters, map, saved jobs, ⌘K palette, JobPosting JSON-LD, salary insights, career quiz, employers page. Gaia demo: home/jobs/team. Both on Cloudflare Pages. No back end (posting, accounts, payments, alerts). | HANDOFF.md, build_spec.md |
| Irish maintenance market | Brochure site €30–150/mo; complex/e-commerce €120–500/mo; bespoke platforms €500–2,000/mo; agency retainers €500–1,450/mo. | insightmultimedia.ie, digimark.ie, grangewebdesign.com, sevenoways.com |
| Rebuild market | Freelance full redesign $2.5k–10k; rebuild/platform migration $5k–20k+; Irish freelancers €3k–9k per site, agencies €5k–16k. | jegdesign.com, skillmammoth.com, naveck.com |
| Job-board SaaS alternatives | JBoard $199–679/mo; Niceboard $399/mo; SmartJobBoard $439/mo. All cheaper than Strategies' entry but still €200–400/mo before design. | capterra.com, jobboardly.com |

**The gap Keith has not said out loud:** what he saw is a front end. "Moving from our current supplier" means replacing Strategies' back end: employer self-service posting and billing, candidate accounts and job alerts, CV database, admin, multiposting feeds (Broadbean/Idibu/LogicMelon, which is how two recruiters supply 98% of IE listings), and redirecting thousands of indexed browse URLs. The costing has to name this, or the deal dies at the Finance Manager.

## 2. Offer structure (recommended)

Three separable lines. Keith buys 1 alone, 1+3, or all three.

**Line 1 — Front-end rebuild + polish list (fixed fee, 15 working days)**
- GreenJobs IE + UK editions, everything in the demo, plus every item in Keith's polish document.
- Price: **€2,750** (was €1,875 for IE only; UK edition and the polish list are the delta). Floor if pushed: €2,250.
- Guarantee kept: live on his domains within 15 working days of sign-off or he doesn't pay.
- gaiatalent.com refresh (home/jobs/team as demoed, fix blank bios, add B Corp + Hometree proof, JobPosting schema): **+€1,200** bundled, €1,500 standalone.

**Line 2 — Platform migration off Strategies (fixed fee, milestone-paid, 6–8 weeks)**
- Employer self-service posting, packages and Stripe billing; candidate accounts, saved jobs, email job alerts, weekly newsletter; CV upload/search for recruiters; admin dashboard; XML/API ingest for Broadbean, Idibu, LogicMelon; full data export from Strategies; 301 map for every indexed URL; analytics.
- Stack: Cloudflare Pages + Workers + D1/R2, Postmark/Resend for mail, Stripe. Running cost under €50/month.
- Price: **€7,500** (bracket €6,500–8,500 depending on which integrations he actually uses). 40% on start, 40% at staging, 20% at go-live.
- Only after the discovery answers in §4. Do not quote a firm number before those.

**Line 3 — Monthly management (the recurring Keith flagged as "the biggest upside")**

| Tier | €/month | Covers |
|---|---|---|
| Care | **350** | Hosting, SSL, backups, uptime and feed monitoring, security patches, up to 4 h changes, monthly report. All three sites. |
| Grow (recommend) | **650** | Care + 10 h/month: SEO and content (blog/salary insights), newsletter send, employer analytics, new features from a shared backlog, quarterly review call. |
| Scale | 950 | Grow + 20 h, priority same-day, AI "Ask GreenJobs" and CV matching features. |

- 3-month minimum, then rolling monthly. 10% off for annual prepay. Contrast with Strategies' contract lock-in.
- Until Line 2 ships, Care covers the Cloudflare front end sitting in front of Strategies data; price then is €250.

**Year-1 maths for the Finance Manager (Lines 1+2+Grow):** €2,750 + €7,500 + 12×€650 = **€18,050**, versus €13–17k/year today with no upgrade. **Year 2 onward: €7,800/year vs €13–17k**, saving €5–9k every year. With Care instead of Grow, year 1 is €14,450 and year 2 is €4,200. Lead with year 2.

## 3. What to say to Keith now (LinkedIn DM, today)

Keep it short. Give one anchor number so the Wednesday conversation with Finance starts from ours, ask the four questions the price depends on, and commit a date.

> Thanks Keith, that's great to hear. I've read the polish notes, all doable and they'll go into the build.
>
> Two parts to the costing, so you can take it to Finance on Wednesday:
>
> 1. The rebuild you've seen, both IE and UK plus your polish list: a fixed fee, live on your domains within 15 working days, and you don't pay if it isn't.
> 2. Monthly management of the three sites: from €350/month, rolling monthly after the first 3, no lock-in. That covers hosting, backups, monitoring, security and a block of change hours each month.
>
> The bigger question is moving off Strategies fully (employer posting, candidate accounts, job alerts, Broadbean feeds). I can price that as a fixed one-off so your recurring cost drops well under what you pay now. To get it right I need four things:
> - what Strategies charges you today and when the contract renews / notice period
> - which of Broadbean, Idibu, LogicMelon your recruiters actually post through
> - roughly how many paying advertisers and candidate accounts are on the boards
> - who hosts gaiatalent.com now and what that care plan costs
>
> I'll have the full proposal with you Wednesday morning so it lands the same day your Finance Manager is back. Happy to do 20 minutes on a call with her too if useful.

Then send the proposal as a one-page PDF Wednesday: the three lines, the year-1 vs year-2 table, and the 15-day guarantee.

## 4. Discovery answers needed before Line 2 is firm
1. Strategies invoice amount, tier, renewal date, notice period, data-export terms.
2. Integrations in use (Broadbean partner setup costs Broadbean-side fees; Idibu and LogicMelon are cheaper to wire).
3. Number of employer accounts, live candidate accounts, job-alert subscribers, newsletter list size.
4. Whether GreenJobs sells advertising today (featured jobs, newsletter sponsorship) and revenue per year — decides whether Stripe billing is in scope.
5. gaiatalent.com hosting/care plan cost and whether he wants it moved.

## 5. Risks to state in the proposal (they are also your defence against scope creep)
- SEO: thousands of indexed browse URLs on greenjobs.ie. Line 2 includes the redirect map; a dip for 4–8 weeks is normal and must be written down.
- Multiposting: Broadbean integration depends on Broadbean onboarding us as a destination; timeline is theirs, not ours.
- The polish document: fix its items in Line 1 only if they are front-end. Anything needing accounts or posting belongs to Line 2 and should be labelled so.
- Don't drop below Care €350 for three sites. Irish agency retainers start at €500; going lower signals hobbyist and makes the monthly hours unprofitable.

## 6. Sources
- Strategies pricing and features: https://www.strategies.co.uk/job-board-software/ , https://www.softwareadvice.co.uk/software/280453/jobweb , https://www.capterra.ie/alternatives/131124/jobweb
- Hidden Depth / gaiatalent.com: https://hiddendepth.ie/made/gaia-talent/
- GreenJobs recruiter zone and network: https://www.greenjobs.ie/recruiter-zone-advertising.cms.asp , https://www.onrec.com/directory/job-boards/green-jobs-ireland
- Keith: https://www.linkedin.com/in/keith-molony-3715473/ , https://gaiatalent.com/team/
- Irish maintenance pricing: https://www.insightmultimedia.ie/website-maintenance-costs-in-ireland-a-2026-price-guide/ , https://digimark.ie/website-maintenance-cost-ireland/ , https://www.grangewebdesign.com/blog/website-maintenance-in-ireland-what-it-actually-costs-in-2026/ , https://sevenoways.com/blog/website-maintenance-cost-ireland/
- Redesign/rebuild pricing: https://www.jegdesign.com/website-redesign-cost-2026/ , https://skillmammoth.com/blog/website-redesign-cost , https://www.naveck.com/blog/web-development-companies-cost-ireland/
- Job-board SaaS: https://www.capterra.com/p/204197/Niceboard/ , https://www.jobboardly.com/blog/best-job-board-software , https://www.guideflow.com/blog/job-board-software

## 7. Addendum (2026-09-28, evening): what to tell Keith about his 28 Sept notes

His document was split into 114 individual requests and every one was verified on the live build (`research/qa_2026-09-28/requirements_matrix_v2.md`). 100 are done. The remaining 11 are his to supply or confirm, and the site says so in his own words where a figure is missing:

**Needs information from GreenJobs (7)**
1. Candidate audience figure (monthly visitors) for the employers page.
2. Weekly newsletter reach (subscriber count).
3. LinkedIn and network distribution figures.
4. Two or three UK employer testimonials, verbatim.
5. Permission to display each employer's logo (only employers with live roles are shown today).
6. A GB phone number, if he wants one on the UK site.
7. Examples of UK placements or campaigns (employer, role, outcome).

**Needs a decision from Keith (4)**
8. Hero credibility line: his draft says "Roles across 10 sectors"; the site shows the live count (14) because he also asked for six new sectors. Which does he want?
9. "Transport and active travel" is merged into "Sustainable infrastructure & transport". Keep merged or split?
10. Membership package contents: his site never lists them, so the column reads "Ask us". What does membership include?
11. Content hub: a salary guide exists; career-advice articles and market reports need topics or copy from him.

**Paste-ready line for the LinkedIn thread**
> Every point in your notes is now live on the demo, both editions. Eleven items need something from your side (audience figures, testimonials, logo permissions, membership contents and a couple of naming calls); they're listed on your evidence page under "Launch checklist". Send me those whenever convenient and I'll drop them in the same day.
