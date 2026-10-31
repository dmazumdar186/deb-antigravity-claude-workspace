# Final QA — Reply to clarifications (01c, 2026-10-31)

## Verdict: FIX (10 small required edits), then SEND

## Verdict per lens
- **Coverage/order:** all 7 asks answered directly, in the client's order. No material over-sharing; the monthly-maintenance invoicing line is the only unasked detail (kept, bounded).
- **Hostile reading:** five unbounded phrases ("any competent", "confirms", "every page", "at any time", "anything that fails a test at no cost") plus unbounded J6 and maintenance invoicing. Fixed below.
- **Hormozi:** 50/50 reads as a confident house rule; deposit value clear (reserves slot, starts audit). Risk reversal real once bounded to T01–T15 in scope.
- **Saraev:** human decision points named (written acceptance, management authorisation, feasibility study before integration). Template-reusable.
- **Daniela Amodei:** respectful; closing line gives time. No distrust tone.
- **Dario Amodei:** "the console you saw" presumes; "audit confirms" presumes the outcome; "any competent developer" overclaims. Fixed.
- **Murati:** numbered bold heads, short paragraphs; point 3 and 6 are dense but phone-readable.
- **Brockman:** after edits, every promise points to a bounded artefact (proposal table, template, T01–T15, transfer package).
- **MECE/consistency:** point 3 (rights on final payment) matches point 6 (balance at J5) and questions page ("once the delivered work is paid"); J6 source handover matches brief. Point 4 rounds match the site. Point 5 scope clean. **Point 7 contradicted Q23 default** (link to today's Traveldoo address) — fixed. Dates 10 November / 24–48 working hours consistent; no fees, no client names; British English consistent.

## REQUIRED edits (old → new)
1. "a small custom administration (the console you saw)" → "a small custom administration (the console shown on the concept pages)"
2. "Any competent web developer can maintain it from the repository and the documentation; that is a design goal, not a side effect." → "A web developer familiar with these standard tools can maintain it from the repository and the documentation; that is a design goal, not a side effect."
3. "The audit at the start of the project confirms this choice against your current setup," → "The audit at the start of the project checks this choice against your current setup,"
4. "the text, images and links of every page;" → "the text, images and links of every page, within its agreed sections;"
5. "a full export of pages, congresses, enquiries and media in open formats, runnable by your team at any time;" → "a full export of pages, congresses, enquiries and media in open formats, which your team can run itself from handover;"
6. "Stabilisation (J6) is included." → "Stabilisation (J6) is included, for the period set in the proposal."
7. "Maintenance is invoiced at the start of each month." → "Maintenance, if you choose the plan, is invoiced at the start of each month from launch."
8. "and correct anything that fails a test at no cost." → "and correct, at no extra cost, anything in the agreed scope that fails one of the acceptance tests (T01 to T15)."
9. "several of your 30 answers change that scope." → "several of your answers to the 30 questions change that scope."
10. "a simple, configurable "client login" link to Wondermiles," → "a simple "client login" link, which your team can point to Wondermiles or keep on today's Traveldoo address (question 23),"

## OPTIONAL edits
- Point 4: "and two rounds on content per stage" → "and two revision rounds at each content stage" (mirrors site wording).
- Point 6: consider dropping "as on every ProdCraft project" only if not literally true of every past project.

## Corrected email

**To:** direction@assetvoyages.com
**Subject:** Re: Request for Proposal – ASSET Voyages Website Redesign

Dear Ms Veena Khatri,

Thank you for the quick reply. Here are the clarifications, point by point. Where an answer depends on information we don't have yet, I say so, and the written proposal will settle it.

**1. Technologies, and whether someone else can maintain the site**
The site would be built on standard, widely used open-source tools: a static site generator for the public pages, a small custom administration (the console shown on the concept pages) running on Cloudflare's platform, with a standard SQL database for congresses and enquiries. There is no proprietary framework and no licence that ties the site to ProdCraft. A web developer familiar with these standard tools can maintain it from the repository and the documentation; that is a design goal, not a side effect. The audit at the start of the project checks this choice against your current setup, and the proposal names the exact components so your management can have them checked independently.

**2. What your team can change on its own**
Through the console, without a developer: the text, images and links of every page, within its agreed sections; adding, editing, approving and unpublishing pages, articles and FAQ entries; the full congress catalogue (create, edit, import, approve, archive); the enquiry list (status, owner, notes, export). Pages are built from a set of agreed sections (for example text, image and text, list, call to action), so your team can reorder and reuse them. What stays with a developer: adding a new type of section, changing the design system, and anything touching integrations or the underlying platform. The exact list of section types is fixed in the proposal, so there is no ambiguity later about what is editable.

**3. Source code, documentation, data exports and transfer assistance**
Yes, all four are part of the core scope. Specifically: the complete source repository, held in a repository organisation in ASSET's name, with full rights and administrative access passing to ASSET on final payment; an administration guide and a technical runbook (deploy, restore, export); a full export of pages, congresses, enquiries and media in open formats, which your team can run itself from handover; and a defined transfer package if you ever move to another supplier. All service accounts (domain, hosting, database, email sending) are opened in ASSET's name; your existing accounts and data are yours at all times. The proposal sets out what the transfer package contains and how long transfer assistance is included, so it is not open-ended on either side.

**4. Design revision rounds, and what from the prototype is included at launch**
Two revision rounds are included at each design stage (wireframes, then desktop and mobile mock-ups), and two rounds on content per stage; further rounds are quoted before they start. On the prototype: it was built to show the direction and to make the congress journey concrete, not as a feature list. The proposal will carry a one-page table listing every element visible in the prototype and the console with one of three marks: included at launch, optional (priced separately), or illustration only. You will see that table before you sign, so nothing in the prototype can be assumed either way.

**5. Importing and checking the initial 300 congress listings**
Importing is included, provided the spreadsheet follows the template we supply (we provide it with the proposal, and we validate it with a dry run before the real import). Checking is included at the level of data quality: required fields, dates, duplicates, broken links to official sites, and a report of what was rejected and why. What is not included is researching or verifying the events themselves, or finding missing information; that remains with your team, who know the congresses. If you would like us to take on that research, it is a separate item and we would scope it with you.

**6. Fixed price, payment milestones, maintenance costs and rates for future changes**
Yes. The proposal will give a fixed price for the core scope (audit, core site, congress catalogue), tied to a written scope so the price holds; the monthly maintenance plan with its contents and measured commitments; and an hourly rate with a simple change procedure for anything outside the scope.

Payment follows two of your milestones, as on every ProdCraft project: 50% at J0, on signature, which reserves the build slot and starts the audit; and 50% at J5, on acceptance, before cutover. Acceptance means the tests in your brief (T01 to T15) pass on the staging site and ASSET confirms it in writing; the site then goes live on your domain once that payment is settled, together with management's authorisation. Stabilisation (J6) is included, for the period set in the proposal. Maintenance, if you choose the plan, is invoiced at the start of each month from launch.

In return, we commit to a dated schedule and correct, at no extra cost, anything in the agreed scope that fails one of the acceptance tests (T01 to T15). The proposal sets out the acceptance procedure and what happens if either side runs late, so there are no surprises in either direction.

I would rather not put figures in an email ahead of the proposal: a price only means something next to the scope it covers, and several of your answers to the 30 questions change that scope. The proposal follows within 24 to 48 working hours of your answers, or by 10 November on the stated assumptions if the answers come later.

**7. Wondermiles**
Agreed. For launch we quote a simple "client login" link, which your team can point to Wondermiles or keep on today's Traveldoo address (question 23), with click measurement and no passwords stored on your site. API and single sign-on are priced separately, in two steps: first a short feasibility study (what Wondermiles actually allows, contractually and technically), then the integration itself, quoted only once the study has an answer. I prefer not to quote the integration before that, because its cost depends almost entirely on what Wondermiles supports.

Please take the time you need with your manager. The answer sheet remains the quickest way for us to turn this into a precise, fixed proposal.

Kind regards,
Debanjan
Founder, ProdCraft
debanjan@prodcraft.fyi
