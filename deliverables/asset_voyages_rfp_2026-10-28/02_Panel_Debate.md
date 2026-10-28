# ASSET Voyages bid: the panel debate
Internal, for Debanjan only (not for the client) · Wednesday 28 October 2026 · proposal due end of day

**What this is.** Sixteen voices argue the bid three times: top-down (from the business goal to the servers), bottom-up (from the servers back to the goal), then a fast top-down pass to agree. The five project roles are generic senior practitioners. The eleven named lenses are analytical stances based on each person's public thinking (`.claude/memory/panel_roster.md`). They are not real quotes. The resolutions are in **Common ground** at the end.

**What the panel worked from:** the RFP (9 pages) and the optional form; `00_RFP_Analysis_and_Plan.md`; `01_Questions_for_Veena.md`; `research/effort_estimate.md`, `market_pricing_paris_2026.md` and `infra_costs_2026.md`; the draft `proposals/asset-voyages-v1.json`; and the capability delta (what our stack already has, has in part, or lacks).

**What it did not have:** `research/facts.md` (the site research) does not exist yet, so **findings about the current site are pending**. The only measured facts are in `research/live_metrics.json`: the current homepage has about 661 words and 69 links, and it is 5.6 screens tall on a desktop and 12.5 on a phone. Nothing in this debate assumes ASSET's CMS, host, CRM, traffic or URL count.

**Fixed constraints from Debanjan:**
- Build €4,000 HT (L1 €2,500 + L2 €1,500, L0 included).
- €600 HT a month, with every tool paid by ProdCraft.
- He is the only person on the team.
- Custom-built, no WordPress ("ASSET Console").
- "Zero downtime" promised in an honest form.
- Every number backed by a source.

---

## Round 1: top-down
*Business goal → buyers and journeys → pages → components → data → infrastructure → operations*

### 1.1 The business goal

**Product Manager:** Page 1 lists four outcomes:
- qualified enquiries in three activities;
- Veena publishes without a developer;
- SEO value is kept and the old site stays up throughout;
- integrations are prepared without blocking launch.

That is the scorecard. Page 9 adds the grading list: journeys, UX, catalogue, scalability, SEO, security, methodology, **team**, overall cost and maintenance.

**Hormozi:** Then the dream outcome isn't "a website". It's "your three sales teams get enquiries that are already qualified, and Veena runs the site alone". Where does the draft say that in one line?

**Product Manager:** It doesn't. Section 03 lists features.

**Hormozi:** Value = dream outcome × perceived likelihood ÷ (time delay × effort). A solo bidder at €4,000 scores badly on perceived likelihood. You win that back with proof, not adjectives.

**Karpathy:** Before any proof, where is the number? "Qualified enquiries" has no baseline. We don't know how many enquiries ASSET gets today, from which pages, or how many convert.

**Product Manager:** The RFP agrees with you. "Establish a baseline during discovery; commercial targets will be agreed after the audit." So we must not promise "+X% leads".

**Karpathy:** Good. Then the only honest promise is a measurement: an L0 baseline, the same events tracked on the new site, and a monthly comparison. Anything else can't be checked against data.

**Dario Amodei:** Agreed, and the draft already breaks that rule. Section 01 says "today's site does not give them one". We haven't finished researching the site, so that line isn't known to be true. Every claim about their current site waits for `facts.md`, or it comes out.

### 1.2 Buyers and journeys

**UX/UI Designer:** The five journeys are sharp:
- SME owner;
- travel manager;
- HR/communications buyer of a seminar;
- congress participant;
- existing client heading to Wondermiles, ASSET's booking tool.

Each one ends in a human at ASSET: qualification, review, callback or quotation. Nothing ends in a checkout. So the site is a lead machine, and the form is the product.

**Murati:** Picture the congress participant: a hospital doctor on a phone at 11pm, searching "ESC Congress 2027 flights". They land on a listing. What do they see first?

**Product Designer:** The congress name, dates, city, the official source with its verification date, and one button: "Request a flight quote". The form opens pre-filled with the congress. Departure is a free field, because the brief says not to restrict it to one airport.

**Murati:** And after they press send?

**Product Designer:** A confirmation screen and an email that say what happens next and by when.

**Murati:** By when? We don't know ASSET's reply time.

**Product Manager:** That's question 10 to Veena. Until she answers, the confirmation copy carries a placeholder. It must not invent "within 24 hours".

**UX/UI Designer:** The MICE buyer is the hard one. The brief asks for a "progressive brief" and a "clear summary before submission". That means three or four short steps, then a review screen. It is not a 20-field wall.

**Full-Stack Dev:** Progressive forms double the testing. Each step needs keyboard support, error messages and a back button that keeps what you typed.

**UX/UI Designer:** Yes, and that's why it's priced at 3 hours in the forms line, not 1.

### 1.3 Pages

**Product Manager:** The page table has ten rows, but some rows are several pages. MICE alone is a hub plus "groups and seminars, incentives and conventions". The draft says "up to [25] pages". Where does 25 come from?

**Solution Architect:** Nowhere. I count about 20 content pages, plus 3 legal pages, plus the congress listings, which are generated from data and aren't hand-built.

**Hormozi:** Then write 20. An unnamed bracket invites scope creep.

**Product Designer:** And state who writes the words. The brief makes ASSET validate services, claims, affiliations and images. It also asks the supplier to state "content writing or migration, revisions and translation effort". If we silently take on copywriting for 20 B2B pages, that alone is a week.

**Product Manager:** So, on content:
- ASSET supplies or approves the copy;
- we migrate the existing text and do light editing for structure and SEO titles;
- two revision rounds per milestone;
- copywriting from scratch is a change request.

**Dario Amodei:** And the brief says to verify historical claims, contact details and notices from the old site before reusing them. I want a claims register: every number, logo, testimonial and affiliation, with ASSET's written OK beside it. That includes Selectour, the network ASSET belongs to, whose name is on their letterhead.

### 1.4 Components

**UX/UI Designer:** A design system of about 8 templates: home, service page, audience page, hub, catalogue, listing, article, contact. Plus about 15 components: hero, proof strip, service cards, FAQ, CTA band, congress card, filter bar, form steps, summary, and so on. The concept in `site/` is a head start, not the design system.

**Product Designer:** The estimate gives design 16 hours. That buys wireframes or mock-ups, not both plus a prototype plus a design system. I want 24.

**Cherny:** Where do the extra 8 hours come from? "I want more" is not a plan.

**Product Designer:** From content integration. If ASSET supplies copy in a structured template, page assembly falls from 24 to 20 hours. And from project management: weekly updates generated from the commit log and the backlog, not written by hand, take PM from 25 to 18.

**Cherny:** That I'll accept, if the weekly update is a script that runs the same way every Friday. Not a promise to "be efficient".

### 1.5 Data

**Solution Architect:** There are four data families:
1. Pages and blocks (editorial).
2. Congresses (public fields).
3. Private authorisations: GM&E codes and evidence. GM&E is Air France-KLM's Global Meetings & Events scheme, which gives an event a code that unlocks discounted fares.
4. Enquiries.

The third family is the one that can sink the bid. The brief names "private code exposure" as a launch-blocking defect.

**Full-Stack Dev:** The draft's answer is that the codes sit in a table the public site can't query. "Can't" has to be structural. The public build gets no connection to that data at all.

**Solution Architect:** So: a separate database for authorisations. Only the admin worker (a small server function) is bound to it. The build that generates public pages literally cannot reach it. And the code itself is encrypted at rest.

**Sutskever:** And how do you know it never leaks? Through a bug, a CSV export or a debug log?

**Full-Stack Dev:** A leak test. Before every release, take every code currently in the vault. Scan every built HTML and JS file, every public API response and every public export for those exact strings. Any hit blocks the release.

**Karpathy:** That's falsifiable. I like it. Seed a fake code into staging and prove the scanner catches it when you deliberately leak it. A test that has never failed has never been tested.

### 1.6 Infrastructure

**Solution Architect:** The public site is static (pre-built HTML) on Cloudflare's network. The Console and the forms run on Cloudflare Workers with a D1 database (Cloudflare's hosted SQLite) and R2 file storage, all in the EU jurisdiction. The research costs it at €5-15 a month, up to about €30 with paid monitoring and AI.

**Brockman:** Can it run unattended for 30 days? Who gets woken up?

**Solution Architect:** Nobody gets woken up. That's the honest answer. One person, business hours.

**Brockman:** Then the design has to make waking up unnecessary. The public site must keep serving when the database or the admin is down.

**Solution Architect:** It does, by construction. The public pages are files and don't call the database to render.

### 1.7 Operations, and the first real fight

**Hormozi:** The €600 plan currently promises "content changes, new pages and congress updates applied on a rolling basis". That's unlimited work for a fixed fee from one person. It's the most dangerous sentence in the proposal.

**Daniela Amodei:** It's also unkind to Veena. When a solo supplier is overloaded, the client feels it as silence. A cap she can see is more respectful than an unlimited promise that quietly erodes.

**Product Manager:** Proposal: 5 hours of changes a month included, logged in the monthly report. Beyond that, €70/h HT, quoted before starting if over a day.

**Hormozi:** Why €70?

**Product Manager:** The research has out-of-contract maintenance at €60-150/h HT in France, and the Paris freelance full-stack median at €520-560 a day. €70/h is €490 for a 7-hour day: inside the market band, below the Paris median, and defensible.

**Dario Amodei:** And the availability table says "99.9% per month" and "4 hours for a site outage". Cloudflare publishes an SLA (a service-level agreement, i.e. a contractual uptime promise) only for its Business plan, at about $200-250 a month, which we're not buying. The research lists multi-hour Cloudflare incidents in June and November 2025. A solo supplier with no on-call cannot honestly sign 99.9% (about 43 minutes of downtime a month). And "zero downtime" as an outcome is false for any website on earth.

**Hormozi:** Debanjan wants to say "zero downtime". It sells.

**Dario Amodei:** Then say the true version, which is still strong. **Zero-downtime deployments:** no update ever takes the site offline, and any release can be rolled back instantly. Pair it with a measured availability target. The research recommends 99.5%, measured by an independent probe every 5 minutes.

**Karpathy:** And publish the measurement every month, including the bad months.

*Round 1 open questions: price tension, MFA, the Christmas calendar, references. Round 2 starts from the bottom.*

---

## Round 2: bottom-up
*Infrastructure → data model → each feature → journeys → does it achieve the goal and win the tender?*

### 2.1 Infrastructure, from the metal up

**Full-Stack Dev:** Here's what exists and what doesn't.
- **Exists:** static Astro sites on Cloudflare Pages, French/English, Turnstile anti-spam, the consent banner, a GDPR data-request flow, sitemaps and structured data, test registers.
- **Partial:** redirects, which we've only ever shipped as 302 (temporary). The RFP demands 301 or 308 (permanent).
- **Missing:**
  - D1 databases;
  - Cloudflare Access;
  - backups with a tested restore;
  - Core Web Vitals tooling (Google's speed metrics);
  - axe accessibility tooling;
  - external uptime monitoring;
  - a crawl-to-redirect-map tool.

**Brockman:** None of that is exotic, but it's all first-time work. First-time work is where the estimate lies.

**Solution Architect:** Backups:
- a nightly export of the database to R2 by a scheduled worker;
- D1 "Time Travel" (point-in-time restore, 30 days on the paid plan);
- a weekly copy to a second provider, because one vendor holding both the data and its backup is one failure away from losing both.

The second provider isn't priced in the research yet.

**Brockman:** And the restore drill? RPO 24 hours means you can lose at most a day of data. RTO 8 business hours means you're back within 8 working hours. Has anyone timed a restore?

**Full-Stack Dev:** No. The first one happens in J5, before launch, and it's test T13. That's the right place for it to fail if it's going to.

**Brockman:** Uptime: UptimeRobot's free plan gives 50 monitors at 5-minute checks. I want four:
- the homepage;
- one congress listing;
- the form endpoint's health check;
- the Console login.

Plus a dead-man alarm on the nightly backup: if no fresh dump appears by 06:00, alert.

**Cherny:** Is all of that in code, reproducible from the repo? If Debanjan's laptop dies, can a stranger redeploy from the runbook?

**Full-Stack Dev:** That's the target: one-command deploy, configuration in the repo, secrets in Cloudflare's secret store, never in Git.

### 2.2 Login, MFA and the hole round 1 missed

**Solution Architect:** The draft says "multi-factor login by authenticator app or your company Microsoft or Google accounts" via Cloudflare Access. Small problem: Access doesn't do authenticator-app codes by itself. It delegates to an identity provider (the service that holds your company logins). Its built-in fallback is a one-time code sent by email, which is a single factor.

**Dario Amodei:** So the draft promises something we can't yet deliver.

**Solution Architect:** Only if ASSET has no Microsoft 365 or Google Workspace. If they do, MFA is enforced there and Access trusts it. If they don't, we build in-app authenticator codes (TOTP, the 6-digit codes from an app like Google Authenticator). That's about 6 extra hours, paid from contingency.

**Product Manager:** That's a question for Veena, and it's not on the list of 20.

**Brockman:** Also, the research says that in the June 2025 Cloudflare outage, Access logins failed 100% for about two and a half hours. If the admin is behind Access, the admin goes down with it.

**Dario Amodei:** And a "break-glass" back door that bypasses Access is a security hole.

**Brockman:** Not if it's on the command line, not on the web. The technical admin can deploy, roll back and query the database with a Cloudflare API token from a terminal, with no web login exposed. Veena waits; the public site keeps serving; nothing is lost.

**Dario Amodei:** Accepted. A runbook entry, not a hidden URL.

### 2.3 The data model, feature by feature

**Full-Stack Dev:** The enquiry record, to match the brief's minimum data model:
- an identifier and the enquiry type;
- the date;
- source and campaign, stored as UTM codes (the tags on a marketing link) and the referring site, never personal data;
- contact details;
- the congress reference where relevant;
- status, owner, a history of events;
- a consent record: the version of the privacy notice shown, and the marketing opt-in with a timestamp.

**Sutskever:** Worst plausible failure on submit?

**Full-Stack Dev:** The database write fails and the visitor sees "thank you". That's the silent lead-killer. So the visitor sees success only after a durable write: first the database, with a backup store as a fallback if it fails. Then the notification email via Brevo, with Resend if Brevo fails. If both fail, the enquiry is flagged, retried every 15 minutes, and shown as a red banner in the Console. That covers F04's "fallback if the notification email fails".

**Karpathy:** How will you know the fallback works?

**Full-Stack Dev:** Test T01-T02 includes a run with the email provider deliberately broken.

**Product Designer:** Duplicates (F04, T01). Same email, same type, same congress, within 24 hours: we don't create a second record. We add an event to the first one and tell the visitor "we already have your request".

**Murati:** Make sure that message doesn't read like an error. To the doctor it should feel like "we've got you".

**Solution Architect:** Congresses (C01-C07). Here's how the two workflows stay apart:
- The **editorial status** (draft, approval, published) lives on the congress record.
- The **business authorisation workflow** lives only in the private database, with eight stages from "detected" to "archived".
- The public page shows a "preferential fares" message (C05) only when the business stage is "approved for sale" **and** an approver has ticked it.

So the public site never sees the internal stage itself. It only sees a yes/no flag the approver controls.

**Anthropic research:** Define "duplicate" for the CSV import. "Similar title" isn't a definition.

**Full-Stack Dev:** Exact match on the normalised title (lower-case, no accents, no punctuation), plus the same start date, plus the same city. That's a hard duplicate and it's rejected. Same normalised title in the same year with a different date or city is a soft duplicate: flagged for a human. Every import starts with a dry run that writes nothing, followed by a report: rows OK, rejected, flagged.

**Anthropic research:** And the CSV schema is versioned, so a file prepared in March still imports in September.

### 2.4 Speed, accessibility and the tooling gap

**UX/UI Designer:** The quality table asks for LCP ≤ 2.5 s, INP ≤ 200 ms and CLS ≤ 0.1 "at the 75th percentile where field data is available", plus lab reports by template. In plain words:
- **LCP:** how fast the main content appears.
- **INP:** how fast the page reacts to a tap.
- **CLS:** how much the layout jumps around.

**Karpathy:** "Where field data is available" is doing a lot of work. Field data comes from Google's Chrome UX Report, which only publishes figures for sites with enough Chrome traffic. A niche B2B site may never qualify. So the honest promise is lab reports per template on every release, plus field data if and when Google publishes it. The draft's "Core Web Vitals targets met on every template" is a promise we can't measure.

**Full-Stack Dev:** We have no Lighthouse CI (Google's automated speed audit) and no axe (an automated accessibility checker) wired into our builds today. Wiring both into the test run is about 4 hours. Manual keyboard and screen-reader testing of the five journeys is separate: about 3 hours. So QA goes from 16 to 22 hours.

**Product Designer:** WCAG 2.2 AA (the European accessibility standard for websites) is a *design target* in the brief, not a certification. The proposal must say "target, with automated and manual tests and a defect log". It must not say "compliant".

### 2.5 SEO migration, from the bottom

**Full-Stack Dev:** We don't know how many URLs the current site has. The homepage has 69 links, which says nothing about the total. The crawl-to-redirect-map tool doesn't exist. Building it means:
- crawl;
- an inventory with status, title and canonical;
- a mapping sheet;
- a generated redirect file;
- a test that every old URL makes exactly one permanent hop to a live page.

That's about 4 hours. SEO goes from 8 to 12.

**Solution Architect:** Cloudflare Pages redirect files support 301 and 308. Our only blocker was habit.

**Hassabis:** Here's where it compounds. That crawl-and-map tool is reusable on every redesign ProdCraft ever sells. So are the Console, the leak scanner, the backup drill and the Lighthouse/axe gates. This bid is underpriced as a project, but as R&D for the next ten bids it's cheap.

**Saraev:** Careful. Build the tool once by hand on ASSET, prove the output is right, *then* make it a product. Don't automate a redirect map you've never checked by eye. Customer-felt steps keep a human: ASSET approves the redirect map line by line for priority URLs.

### 2.6 The AI option (L4), from the bottom

**Sutskever:** Where does the model sit in the loop? It reads official congress websites and proposes candidate listings. Worst plausible output: a congress that doesn't exist, wrong dates, or a fake "official source" URL.

**Saraev:** What bounds that?

**Sutskever:** Four things:
- a fixed output schema;
- an allowlist of source domains;
- a check that the source URL actually loads and contains the title and dates;
- a human approval button.

Nothing publishes without the button, which the brief requires anyway. Then add an eval set: 30 known congresses with known dates. Re-run it whenever the model changes, so we notice if it gets worse.

**Anthropic research:** Pin the model ID and the prompt, and log both against every candidate. The brief asks for an audit trail.

**Saraev:** And this is rung two at best: a skill run on a schedule, with a person at the end. Don't sell it as an "AI agent".

### 2.7 The journeys, re-walked from the bottom

**Murati:** Walk Veena's day:
1. She logs in through her company account.
2. She edits the Business Travel FAQ and presses "Publish".
3. What happens?

**Solution Architect:** The page is static, so publishing triggers a rebuild. It goes live in a few minutes, not instantly. We haven't measured the build time for 20 pages plus 300 listings.

**Murati:** Then tell her. Show "Publishing… live in about N minutes" with a real N measured on staging. Otherwise she'll think it failed and press it five times.

**Full-Stack Dev:** And it has to be safe if she does: five presses, one build.

**Daniela Amodei:** And the backup editor. The brief says "Veena and a backup user". Train both, and give each their own login. Shared passwords defeat the access log.

### 2.8 Does it win the tender? The price fight

**Product Manager:** Bottom-up hours after this round:

| Line | Was | Now |
|---|---|---|
| Audit + workshops | 8 | 12 |
| Design | 16 | 24 |
| Pages | 24 | 20 |
| QA | 16 | 22 |
| SEO | 8 | 12 |
| Console | 40 | 44 |
| Infrastructure | 10 | 12 |
| Project management | 25 | 18 |
| GDPR + measurement | 6 | 8 |

The 2 extra hours of GDPR and measurement come out of PM. Core total: **238 h**. Plus 20% contingency, **≈ 286 h**.

**Karpathy:** So €4,000 ÷ 286 h = **€14 an hour**, about €98 for a 7-hour day. The Paris freelance full-stack median is €520-560 a day.

**Hormozi:** That's not a price, that's a donation. Debanjan, say it plainly: on the build alone you're working at about a fifth of market.

**Product Manager:** He's fixed the €4,000. Our job is to make it survivable, not to override him.

**Hormozi:** Then look at lifetime value, not the build. €600 a month, minus €5-30 of tools, is about €570-595 of margin. The work is about 10 hours a month: 5 of operations, 5 of included changes. That's about €58 an hour.

**Karpathy:** Run the numbers by horizon:

| Horizon | Revenue | Hours | Per hour | Per 7-h day |
|---|---|---|---|---|
| Build only | €4,000 | 286 h | ≈ €14 | ≈ €98 |
| Year 1 (build + 12 months) | €11,200 | ≈ 406 h | ≈ €28 | ≈ €193 |
| Three years | €25,600 | ≈ 646 h | ≈ €40 | ≈ €277 |

Still about half the Paris median, even over three years.

**Hormozi:** And with the draft's 3-month minimum, ASSET can take a €4,000 build and leave after €1,800 of fees. That's €5,800 for about 316 hours: €18 an hour. The minimum term is the whole business model. It has to be 12 months.

**Daniela Amodei:** Does a 12-month minimum feel like a trap to ASSET? The brief is explicit about handover and ASSET's control.

**Dario Amodei:** It's honest if it's commercial, not technical. The accounts, code and data are theirs from day one, and they can walk at any time. If they leave inside the first 12 months, the remaining months of the minimum term are due. Write that sentence plainly next to the price, so the low build price and the term are read together.

**Hormozi:** And say *why* the build is €4,000: the build is priced as part of a 12-month managed partnership. That's a true sentence, and it turns "suspiciously cheap" into "structured".

**Product Manager:** Should we print an anchor price, a "standard" build price?

**Dario Amodei:** Only one you'd actually charge. Debanjan hasn't set one, so no invented "was €18,000". The effort table by role, which the RFP requires anyway, shows the work honestly: about 41 days. That's the anchor.

**Hormozi:** Fine. Then reverse the risk where it's cheap to:
- the 20% balance is due only on launch acceptance;
- a service credit if availability misses the target.

**Product Manager:** On payments: 30/30/40 leaves him funding 12 weeks of work on €1,200. The new schedule:

| When | Share | Amount |
|---|---|---|
| J0 kickoff approval | 30% | €1,200 |
| J2 mock-ups approval | 30% | €1,200 |
| J4 Congresses on staging | 20% | €800 |
| Launch acceptance | 20% | €800 |

**Daniela Amodei:** And the team question. The RFP grades "team" and asks for a "named project lead and effort by role". The draft has four rows with "[name]". There's only one name.

**Dario Amodei:** Then print one name and five roles, with days against each. Say that Claude Code (an AI coding assistant) is a tool he uses, not a team member. Say that French copy is validated by ASSET, as the brief requires. Inventing a designer or a QA person would be the one lie that loses the bid *and* the reputation.

**Hassabis:** The bus factor (the risk that everything stops if one person is unavailable) is the real objection a management committee will raise about a solo supplier. Answer it with the handover design:
- the repository is in ASSET's GitHub from day one;
- a runbook a stranger can follow;
- documented exports;
- a standard stack (Astro, TypeScript, SQLite) that any web developer can read.

**Brockman:** And holidays. A support window is fine, but name the cover. If there's no backup person, say that the public site keeps serving without him, and that urgent fixes are acknowledged within the window.

### 2.9 The calendar

**Product Manager:** At 286 hours:
- **6-8 h/day** (about 35 h a week): 8.2 build weeks.
- **4-5 h/day** (about 22 h a week): 13 build weeks.

Go-ahead is Monday 16 November 2026. Christmas: the builder is off 24 December to 1 January, and assume no client approvals from 21 December to 1 January. Six approvals at about 3 working days each.

**Brockman:** Pace A lands staging on Friday 22 January 2027 and launch in the week of 8 February: 12 weeks, the low end of their 12-18. Pace B lands staging around 19 February and launch in the week of 8 March, still inside 16 weeks.

**Hormozi:** Promise A. Speed is value.

**Brockman:** Promise A only if he blocks 6 hours a day on ASSET for 11 weeks. He's solo; other clients exist. Plan A, contract B.

**Murati:** Then the client sees one planned date and one latest date. That's what a careful buyer wants anyway.

---

## Round 3: convergence (top-down, fast)

**Product Manager:** Goal: qualified enquiries, an editable site, SEO kept, options decoupled. Agreed?
**All:** Agreed.

**Murati:** Journeys: five, each ending at a named human step. The confirmation copy waits for ASSET's real reply time.
**UX/UI Designer:** Agreed.

**Product Designer:** Pages: 20 content pages + 3 legal pages + generated listings. ASSET supplies the copy; we migrate it and edit lightly; two revision rounds per milestone.
**Hormozi:** Agreed, and the count goes in the price table.

**Solution Architect:** Data:
- authorisations in a separate database that the public build cannot reach;
- a leak scanner that blocks release, proven by a seeded fake code;
- durable-write-first enquiries with a two-provider email fallback;
- a defined duplicate rule.

**Sutskever, Karpathy:** Agreed.

**Brockman:** Infrastructure:
- static public site;
- nightly backup plus a weekly off-platform copy;
- a timed restore drill before launch and every quarter after;
- four external monitors and a dead-man alarm on backups;
- break-glass from the command line.

**Cherny:** Agreed, all in the repo.

**Dario Amodei:** Uptime wording: zero-downtime *deployments* with instant rollback, 99.5% measured, and no 100% promise. MFA depends on ASSET's identity provider, with TOTP as the fallback.
**All:** Agreed.

**Hormozi:** Money: €4,000 stays. It's tied to a 12-month minimum. The plan includes 5 h of changes a month; beyond that, €70/h. Payments are 30/30/20/20.
**Daniela Amodei:** Agreed, if the 12-month term is printed next to the price, not buried in the terms.

**Karpathy:** Is any constraint dangerous? Yes, two:
- €600 with unlimited changes for one person;
- 99.9%/4-hour outage response with no on-call.

Both are fixed above. The €4,000 itself is dangerous only without the 12-month term.
**Product Manager:** Minuted.

---

## Common ground

### 1. Price structure under the €4,000 constraint

**Build: €4,000 HT.** L0 included, L1 €2,500, L2 €1,500. Unchanged.

**What €4,000 buys** (stated in the proposal):
- L0, L1 and L2 to T01-T15 acceptance;
- up to 20 French content pages from about 8 templates, plus 3 legal pages;
- import of up to 300 congress listings from ASSET's CSV;
- copy supplied or approved by ASSET; we migrate it and edit lightly for structure and SEO;
- 2 revision rounds per milestone;
- 2 training sessions (Veena and a backup editor).

**Why it's that low** (printed beside the price): "The build is priced as part of a 12-month managed partnership."

**Minimum term:** 12 months from launch, then rolling monthly with 30 days' notice. If ASSET ends the plan early, the remaining months of the minimum term are due. Accounts, code and data stay ASSET's throughout: no technical lock-in.

**Payments:**

| Milestone | Share | Amount HT |
|---|---|---|
| J0 approval | 30% | €1,200 |
| J2 approval | 30% | €1,200 |
| J4 approval | 20% | €800 |
| Launch acceptance | 20% | €800 |

**Change requests:** €70/h HT (≈ €490 a day; market €60-150/h, Paris full-stack median €520-560 a day). Written quote before starting any change over one day, assessed for cost, schedule, security and SEO impact, as the brief requires.

**Options unchanged:**

| Option | Price HT | Basis |
|---|---|---|
| English activation (translation excluded) | €750 | 8 h |
| CRM connector | €500 | 6 h |
| L3a Wondermiles feasibility | €400 | 4 h |
| L3b Wondermiles single sign-on | €1,200 | 12 h |
| L3c Wondermiles API | quoted after L3a | |
| L4 AI congress ingestion | €1,500 | 16 h |

These options sit at about €83-100/h. They're the only lines priced near market.

**Honest economics, for Debanjan only:**
- Build: about €14/h.
- Year 1: about €28/h.
- Three years: about €40/h (≈ €277 a day), roughly half the Paris median.

This is viable only as a reusable-asset investment (Console, crawl tool, leak scanner, QA gates). It's dangerous if the 12-month term is dropped.

**Three-year core cost:** €4,000 + 36 × €600 = **€25,600 HT** (€5,120 VAT at 20%, **€30,720 TTC**). Annual recurring cost: €7,200 HT (€8,640 TTC). There are no separate licences.

### 2. Monthly plan (€600 HT) and its measured commitments

**Included:**
- **Hosting and every tool subscription, paid by ProdCraft.** Expected cost €5-15 a month, up to ≈ €30. Accounts are in ASSET's name; ProdCraft pays the bills.
- **Security patches and dependency updates.**
- **Backups:** nightly export, 30-day point-in-time restore, weekly off-platform copy.
- **Restore drill** every quarter.
- **Monitoring:** 4 external monitors, a backup alarm and a public status page.
- **Speed and accessibility checks:** Lighthouse and axe reports on every release and every month.
- **SEO health:** Search Console, broken links and redirects.
- **Up to 5 hours of changes a month**, logged. Unused hours don't roll over.
- **Help for Veena and the backup editor.**
- **Monthly report:** availability, incidents, backups, enquiries by activity, congress searches, hours used.

| Commitment | Measured how |
|---|---|
| Public-site availability target: 99.5% a month (≈ 3 h 39 min allowed) | External probe every 5 minutes; reported monthly |
| Deployments without interruption; instant rollback | Release log in the monthly report |
| RPO 24 h / RTO 8 business hours | Timed quarterly restore drill, with the result reported |
| Support window: Monday-Friday 9:00-18:00, Paris time | |
| Acknowledgement: outage or failed form within 4 business hours; other requests within 1 business day | Ticket timestamps |
| Changes within the 5 h allowance done within 2 business days | Change log |
| Critical security patches applied within 2 business days of release | Patch log |
| Speed: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 (lab, per template); field data at the 75th percentile only where Google publishes it | Lighthouse CI report; Chrome UX Report if available |
| Service credit: 10% of that month's fee if availability is below 99.5%, capped at one month's fee a year | Probe data |

**Exclusions:**
- outages of third-party hosts (Cloudflare, Wondermiles);
- maintenance announced 48 h ahead;
- force majeure;
- content errors in copy ASSET supplied;
- weekends and holidays, unless optional on-call is agreed and priced.

### 3. Honest uptime wording (replaces "zero downtime" and 99.9%)

**FR:** « Les mises à jour du site sont déployées sans interruption de service : le site public reste en ligne pendant chaque mise en production, avec retour arrière immédiat possible. Le site public vise une disponibilité mensuelle de 99,5 %, mesurée par une sonde externe indépendante toutes les 5 minutes et communiquée chaque mois, hors maintenance annoncée 48 h à l'avance, force majeure et panne d'un hébergeur tiers. Aucune disponibilité de 100 % n'est garantie. Objectifs de restauration : perte de données maximale de 24 h (RPO), remise en service sous 8 heures ouvrées (RTO). En cas de non-atteinte de l'objectif mensuel, un avoir de 10 % de la mensualité est appliqué, plafonné à une mensualité par an. »

**EN:** "Site updates are deployed with zero downtime: the public site stays online during every release, and any release can be rolled back instantly. The public site targets 99.5% monthly availability, measured by an independent external probe every 5 minutes and reported monthly, excluding maintenance announced 48 hours ahead, force majeure and third-party host failures. No 100% availability is guaranteed. Recovery targets: at most 24 hours of data loss (RPO) and service restored within 8 business hours (RTO). If the monthly target is missed, a credit of 10% of that month's fee applies, capped at one month's fee per year."

### 4. Timeline (go-ahead Monday 16 November 2026)

The proposal shows the planned dates (pace A, 6-8 h/day) and one contractual latest date (pace B, 4-5 h/day). Christmas assumption: the builder is off 24 December-1 January; no approvals 21 December-1 January.

| Milestone | Deliverable ready | ASSET approval by (≈ 3 working days) |
|---|---|---|
| J0 Kickoff | Wed 18 Nov 2026 | Fri 20 Nov 2026 |
| J1 Audit and discovery | Fri 27 Nov 2026 | Wed 2 Dec 2026 |
| J2 UX and UI | Fri 11 Dec 2026 | Wed 16 Dec 2026 |
| J3 Core website on staging | Fri 15 Jan 2027 | Wed 20 Jan 2027 |
| J4 Congresses on staging | Fri 22 Jan 2027 | Wed 27 Jan 2027 |
| J5 Pre-launch: acceptance report, training, restore drill | Fri 5 Feb 2027 | Written go-ahead Mon 8 Feb 2027 |
| Launch (DNS cutover) | Tue 9 Feb 2027 | |
| J6 Stabilisation closed | Fri 5 Mar 2027 | |

- **Contractual latest launch:** Friday 12 March 2027 (pace B: staging around Fri 19 Feb, launch in the week of 8 March, stabilisation closed Fri 2 Apr 2027).
- **Elapsed time:** pace A ≈ 12 weeks, pace B ≈ 16 weeks. Both are inside ASSET's indicative 12-18 weeks.
- **Delays:** all dates move day for day with late ASSET inputs (access, content, CSV, mailboxes, partner confirmations) and approvals beyond 3 working days.

### 5. Scope phasing

- **Launch (€4,000):** everything needed to pass T01-T15.
  - The Console page editor is a structured block editor (fixed section types with fields), not a free drag-and-drop page builder.
  - The GM&E workflow is the eight statuses plus their fields, approver and history, with no automation.
  - The measurement dashboard is a simple table in the Console.
- **Months 1-3 of the plan (inside the 5 h a month):** baseline-versus-new comparison; commercial targets agreed with ASSET (the RFP's own sequence); content additions; Search Console follow-up; small UX fixes from real enquiries.
- **Options, only on written selection:** English, CRM, L3a/b/c, L4. None is needed for launch.

### 6. What the proposal must change

The full list is in `03_Functional_Breakdown.md` §Z. The headlines:
1. Fill or neutralise the [SITE FINDING] placeholders (facts pending).
2. Replace the 99.9% availability and "4 hours" wording.
3. Cap the monthly changes.
4. Set a 12-month minimum term.
5. Use the 30/30/20/20 payment schedule.
6. Make the team a single named person with effort in days by role.
7. Add the architecture diagram, data flows and cost table.
8. Make MFA depend on ASSET's identity provider.
9. Turn the CWV promise into a lab-report promise.
10. Add the CSV schema, data model, retention rules, conversion events and CRM specification.
11. Add a T01-T15 mapping table.
12. Label concept work honestly in the references.
13. Add VAT/TTC columns to the options table.

### 7. Honest gaps, by lens

**1. Karpathy (measurement)**
- There's no enquiry baseline. Every outcome claim waits for L0.
- The 286 h estimate comes from analogy with past builds, not from a timed ASSET prototype. The Console (44 h) is the largest unmeasured line.
- The static rebuild time ("live in N minutes") hasn't been measured.
- Field Core Web Vitals may never be available for this site.

**2. Cherny (tooling craft)**
- The crawl-to-redirect tool, leak scanner, Lighthouse/axe gates, backup cron and restore drill don't exist yet. Each needs a directive and a `--mock` test before it's trusted.
- The weekly-update script is assumed, not built.

**3. Dario Amodei (honesty and legal exposure)**
- Site claims in sections 01-02 are unverified until `facts.md` exists.
- Veena's surname and title in the JSON don't come from the RFP; verify before sending.
- Whether GreenJobs, MISB and Gaia are concepts or commissioned work must be stated truthfully.
- The CNIL retention guidance (CNIL is France's data-protection authority) and the Google Event structured-data policy are cited from memory; verify them.
- The DPA (data processing agreement) template isn't drafted.

**4. Anthropic research (rigour)**
- The duplicate rule, past-event rule and retention periods are proposals awaiting ASSET's approval.
- The AI option's eval set (30 known congresses) doesn't exist.
- Model and prompt pinning for L4 is designed but not implemented.

**5. Hormozi (offer and economics)**
- €40/h over three years is about half the market. The offer is only sound if the 12-month term holds and the reusable assets are actually reused.
- There's no verifiable travel/MICE reference, so perceived likelihood rests on the concept site and the live FR/EN sites.

**6. Saraev (automation boundaries)**
- L4 is a supervised, scheduled skill, not an agent.
- The redirect map and the CSV import must be checked by a human on ASSET before either becomes a product.
- There's no error channel yet for the scheduled jobs (backups, retries).

**7. Daniela Amodei (people and trust)**
- There's no named holiday or sickness cover.
- The support window is business hours only.
- Veena's reply-time promise in the confirmation email is unknown (question 10).
- The 12-month term must be visible, not buried.

**8. Sutskever (failure modes)**
- The leak scanner only catches codes it knows about. A code typed into a free-text field elsewhere (for example a congress description) would only be caught if that field is scanned too. Scope: all public output.
- The L4 hallucination bounds are designed, not tested.

**9. Murati (user experience)**
- The MICE progressive brief and the listing-page hierarchy are unvalidated with real ASSET buyers.
- The publish-delay message needs a measured N.
- Mobile testing on real devices depends on which devices Debanjan owns.

**10. Brockman (reliability)**
- The second backup provider isn't chosen or priced.
- The Access outage dependency is accepted (the admin goes down while the public site stays up).
- There's no on-call.
- The restore drill has never been run on this stack.

**11. Hassabis (long-horizon strategy)**
- The compounding claim (that each reusable asset makes the next bid cheaper) only holds if the Console is built as a product with ASSET as its first tenant, with ASSET-specific code kept separate.
- There's no plan yet for selling ASSET Console to bid two.
