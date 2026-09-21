# Recruit CRM — AI & Automation Capability Inventory (as of 2026-09-11)

Research method: WebSearch + WebFetch against recruitcrm.io, help.recruitcrm.io, and third-party
review sites (tavily/firecrawl MCP tools were unavailable this session). Some pages (peoplemanagingpeople.com,
g2.com) returned HTTP 403 to WebFetch and could only be sourced via search-engine snippets, which are
noted explicitly below as lower-confidence secondary evidence, not a primary-source fetch.

**Strict rule applied**: every claim below has a URL. Anything I could not find on a Recruit CRM–owned
page is marked "not found on their pages as of 2026-09-11" rather than assumed absent.

---

## 1. Release notes / product updates (2026)

Source: https://recruitcrm.io/category/product-updates/ and page 2
(https://recruitcrm.io/category/product-updates/page/2/)

Recruit CRM does **not** run a conventional dated changelog (no "v2.4 — Sept 2026" style entries). The
"Product Updates" blog category is a mix of feature-launch posts, press/award announcements, and
listicles. No entry on either page fetched carried an explicit 2026 release date in a machine-checkable
format; dated evidence instead comes from individual feature/help pages (see below), where the most
recent explicit date found was **"Last updated: 19-06-2026"** on
https://recruitcrm.io/blogs/recruit-crm-ai-features/ and
https://recruitcrm.io/blogs/recruit-crm-ai-candidate-matching-resume-parsing/.

Entries visible in the Product Updates category (no reliable individual dates extracted):
- "Self Updating Profiles" — quote: *"Know when a candidate or contact has a new job & get alerts for lost fees through backdoor hires."*
- "Recruit CRM earns top spot in Gartner report 2026" — award/press, not a product change.
- "Recruit CRM wins 2026 Best Feature Set Award — TrustRadius" — award/press, not a product change.
- "Recruit anywhere with Recruit CRM's mobile recruitment app" — mobile app launch.
- GoodFirms / GetApp "Category Leaders" mentions — award/press, not product changes.

help.recruitcrm.io has no dedicated "release notes" URL either; its homepage surfaces a "What's new!"
box pointing to individual help articles (video library, Email Sequencing, SSO setup, Deal Split,
Workflow Automation app-support, 2FA) rather than a changelog. Source: https://help.recruitcrm.io/en/

**Conclusion**: Recruit CRM does not publish a single canonical, dated AI/automation changelog. Feature
claims below are sourced from the individual product/help pages instead, each dated where a date exists.

---

## 2. AI Sourcing

Sources: https://recruitcrm.io/sourcing/ , https://spott.io/resources/recruit-crm-in-depth-review-for-recruiting-firms

| Aspect | Finding | Quote |
|---|---|---|
| Data source | LinkedIn / "public web data"; vendor states GDPR compliance | *"the data partner is 'GDPR compliant and used by Fortune 500 companies'"* and only uses *"publicly available data"* (recruitcrm.io/sourcing/) |
| Inputs | Natural language, voice | *"senior react developer in Berlin"*-style queries; *"Voice-enabled sourcing for hands-free searching"* (recruitcrm.io/sourcing/) |
| Filters | Page does not itemize structured filters (location/certification/seniority) beyond what's expressible in the natural-language query — **not found** as separate filter fields on this page as of 2026-09-11 |
| Result contents | Auto-enriched profile, no evidence of a numeric relevance "score" or evidence quotes/citations on the sourcing page itself — **not found** |
| Contact data | Chrome extension provides *"verified emails and phone numbers"* per recruitcrm.io/sourcing/ — no methodology/verification-rate disclosure found |
| Cost / credits | Sourcing page does not disclose price; pricing lives on a separate page. Spott.io's independent summary: *"AI Sourcing takes a natural-language or voice query and pulls profiles from public web data, but it runs on credits, with a set number of searches per plan."* (spott.io) |
| Import | *"Instantly import top candidates into your Recruit CRM database"* — *"no copy-paste, no spreadsheets"* (recruitcrm.io/sourcing/) |

Free-tool variant (separate lead-gen tool, not the paid product): search-engine synthesis reported
*"3 searches per day with 10 candidate profiles per search"* and *"5 email and 5 phone credits per
month"* — this is a secondary-source (search-snippet) claim, not independently confirmed by direct
fetch, flagged as lower confidence.

---

## 3. AI candidate matching ("bimetric scoring") and resume parsing

Source: https://recruitcrm.io/blogs/recruit-crm-ai-candidate-matching-resume-parsing/ (dated 19-06-2026)

- **What it scores**: *"skills, experience, education, location, language, job titles, industry, and more"*; described as a *"two-way matching algorithm"* generating a *"matching rate"* between two profiles.
- **Explainability**: partial — numeric only, not reason-coded. *"a window will appear showcasing a roster of candidates that align with the chosen candidate's comprehensive profile, each accompanied by a match score ranging from 0 to 100."* No breakdown of which sub-factors drove the score was found on this page.
- **Hard rules**: **not found** on their pages as of 2026-09-11 — the page describes only weighted/holistic scoring; there is no documented way to force a hard constraint (e.g., "must be chartered," "must live in county X") as a filter that excludes non-matches rather than merely scoring them lower.
- **Tier limits**: pricing page (recruitcrm.io/pricing/) states matching is capped: **2 matches on Pro**, **50 matches on Business**; Enterprise not explicitly re-stated as unlimited on the fetched pricing content (see §7).
- **Resume parser** (help.recruitcrm.io/en/articles/3029953): powered by Sovren per the blog post. Extracts *"Candidate's Name, Phone Number, Email, City, Full Address, Specialization, Work Experience Year, Work Experience Month, Current Organization, Title, Skills, Language Skills, Summary, Educational Qualification, Work and Education History and social medial [sic] URLs."* Runs de-duplication: *"will first check if a candidate with the same Email ID, LinkedIn URL, or Contact Number already exists"*; *"Existing data will not be overwritten by default."* Multi-language support claimed. Documented limitation: *"can be influenced by the quality of the input data... completeness and clarity of information in the resumes can impact the precision of the parsing."*

---

## 4. Outreach sequencing

Source: https://help.recruitcrm.io/en/articles/8110265-sequences-within-recruit-crm

- **Channels**: Email, SMS, LinkedIn messages, and internal tasks — *"Emails: Send a series of scheduled email templates..."*, *"SMS messages"*, *"Create a sequence of LinkedIn messages to be sent to candidates and contacts at scheduled intervals"*, and internal *"task sequences"*.
- **Reply classification**: **not found** on their pages as of 2026-09-11 — the sequences help article makes no mention of automatic reply classification (e.g., interested/not-interested/OOO detection).
- **Snooze / next-step automation**: **not found** as a named feature; the article only documents that *"Failed steps pause enrollment until issues are resolved (disconnected accounts, invalid contact info, etc.)"* and that *"A candidate or contact can only be actively enrolled in one sequence at a time."* This is failure-pausing, not an intelligent snooze/next-best-action feature.
- **Sender identity**: when multiple email accounts are connected, the user can *"select the email ID you want to use for sending the sequence before completing the enrollment"* — i.e., human-chosen sender per sequence, not an AI-selected identity.

---

## 5. "AI agent" / copilot / auto-screening / AI interview / verification / compliance

Source: https://recruitcrm.io/blogs/recruit-crm-ai-features/ (dated 19-06-2026)

Recruit CRM brands a small set of task-specific "agents" (not a general-purpose chat copilot):
- **Custom Field Parsing Agent** — *"Train an agent to recognise custom fields in resumes you parse."*
- **Candidate Submission Agent** — *"Let AI craft a polished candidate list ready for email submission."*
- **Resume/CV Formatting Agent** — *"Generate AI-formatted resumes on the spot and save them as PDFs."*
- **Candidate Pitching Agent** — *"Create polished, branded candidate pitch emails with AI."*
- Plus GPT-integration utilities: job description generator, candidate summary generator, AI-enabled notes/call logs, AI email template generator, AI call transcript.
- **Self Updating Profiles**: *"Know when a candidate or contact has a new job & get alerts for lost fees through backdoor hires."* — a passive monitoring/alert feature, not screening.

**Not found on their own pages as of 2026-09-11**: an "AI interview" feature, "auto-screening" of applicants, "candidate verification" / credential-check / identity-fraud-detection feature, or background-check functionality. Recruit CRM's own blog post on background checks
(https://recruitcrm.io/blogs/background-check-guide/) treats background checks as a *third-party*
topic/integration category, not a native Recruit CRM capability — consistent with "not built natively."

**Compliance**: the AI-features page states *"GDPR compliant"* and *"AICPA and IAF certified"* — general
company/platform compliance certifications, not a per-feature "compliance notice" UI element (no such
UI element documented on the pages fetched).

---

## 6. API / webhooks / Zapier / CSV import-export

- **API plan gating**: help.recruitcrm.io/en/articles/4411980 — *"The Open API is only available to users on the 'Business' plan or higher."* Live docs at https://docs.recruitcrm.io (not independently fetched this session).
- **Webhooks**: the API-docs help article header references *"API docs, Webhooks"* but the fetched excerpt gave no operational detail (event list, retry policy, signing). Zapier's own listing (https://zapier.com/apps/recruitcrm/integrations/webhook) documents Recruit CRM triggers including *"new call log is added,"* *"candidate is assigned to a job,"* *"new candidate is added,"* *"new candidate applied through Talent Pool,"* *"candidate is marked as offlimit,"* and *"candidate's pitch stage is updated"* — these read as Zapier-mediated triggers (poll or Recruit CRM → Zapier webhook), not a general customer-facing webhook console; not confirmed as a self-serve webhook UI inside the product itself.
- **Zapier app**: confirmed live — https://zapier.com/apps/recruitcrm/integrations ("connect with 5000+ apps").
- **CSV export**: help.recruitcrm.io/en/articles/2727207 — *"You can export candidate, contact, job, company & Deal records to CSV/Excel files... choose fields... hit the 'Export' button."*
- **Full data export**: help.recruitcrm.io/en/articles/3591116 — *"Data Export and Full Export options available only to accounts on paid subscription plans (Pro, Business and Enterprise)... you'll find the CSVs for all candidates, companies, contacts, jobs, and deals data."*
- **Export specifically of AI-Sourced results** (as distinct from database candidates): **not found** as a separately documented export path on the pages fetched — sourcing page only documents "import into Recruit CRM," implying AI-sourced profiles become ordinary candidate records that are then exportable like any other candidate, but no page explicitly confirms this chain.

---

## 7. Pricing (per seat, annual billing, from recruitcrm.io/pricing/ and corroborated by spott.io)

| Plan | Price (annual, per user/mo) | AI / automation notes from the pricing page |
|---|---|---|
| **Pro** | $95 (spott.io-quoted; recruitcrm.io/pricing/ did not render exact digits to WebFetch) | Chrome sourcing extension, AI resume parser, GPT integration, AI sourcing included; candidate matching capped at **"2 matches"**; **"No API access"**; single hiring pipeline; up to 15 custom fields |
| **Business** ("Most Popular") | $135 | Everything in Pro + automated email sequencing, bulk texting, executive search report generator, resume formatting, custom roles/teams, multiple pipelines, SSO, audit logs, 2 email connections; candidate matching **"50 matches"**; up to 150 custom fields; **"Includes open API access"** |
| **Enterprise** ("Highest ROI") | $215 | Everything in Business + workflow automation, advanced analytics, LinkedIn messaging integration, data enrichment (phone & email), calling/texting credits, "Recruit Craft," job multiposting/direct-apply; **"1,000 task automation units and 10 job postings per user monthly"**; **"500 data enrichment credits per user monthly"**; dedicated account manager |

Note: monthly (non-annual) billing is ~$14/$24/$44 more per seat on Pro/Business/Enterprise respectively
per a third-party summary (avahr.com/WebSearch synthesis) — not independently re-verified by direct
fetch of recruitcrm.io/pricing/ dollar figures, which did not render numerals to WebFetch (likely
client-side rendered toggle). Treat the exact dollar figures as secondary-sourced, structurally
corroborated by two independent third parties (spott.io and the avahr.com search synthesis) but not a
first-party screenshot/quote.

Job multiposting is a separate paid add-on (starts at $20/mo for 7 postings on annual billing per
third-party search synthesis; not independently confirmed by direct fetch).

---

## 8. Published limitations / reviews on accuracy or data quality

Capterra reviews (via search-engine snippets — direct fetch of capterra.com review pages returned
usable results only through search snippets, not a full WebFetch of the review page HTML):
- *"The AI and data enrichment elements can be improved upon. Data Enrichment does not always provide accurate data. AI sourcing, while great, can also have inaccuracies (like in all AI instances currently)."*
- *"CV parsing is not very precise, ai tools not very precise in feedback."*
- *"The AI feature isn't the best, I rarely get a good profile when I'm searching for different profiles using AI."*

Spott.io (independent review site, direct-fetched): flags the credit/tier gating itself as a structural
limitation — *"AI tooling spreads across tiers as you scale"* and *"in-database search still depends on
how completely records were filled in"* (i.e., match quality is bounded by how well recruiters filled in
CRM fields, not purely by the AI).

G2 (g2.com/products/recruit-crm-ats/reviews) and PeopleManagingPeople
(peoplemanagingpeople.com/tools/recruit-crm-review/) both returned **HTTP 403 to WebFetch** this
session and could not be directly quoted; a prior WebSearch synthesis (lower confidence, not a direct
quote from the page) reported G2 users saying *"AIRA sourcing feature making sourcing easier"* (note:
"AIRA" appears to be a Recruiterflow-branded term surfacing in the search results, not confirmed as
Recruit CRM's own naming — treat this attribution as unverified/possibly conflated in the search
synthesis) and *"LinkedIn sourcing could be improved."* This paragraph is flagged low-confidence and
should be re-verified by a session with working G2/PeopleManagingPeople access before being relied on.

---

## What a verification layer could add that none of the above does

Limited strictly to gaps evidenced (or evidenced-absent) from Recruit CRM's own pages above:

1. **Hard eligibility rules on matching.** Recruit CRM's bimetric matching (§3) is documented only as a
   0–100 holistic *score*; no page describes a way to enforce a non-negotiable constraint (e.g., "must
   hold an active charter/license," "must reside in county X") that removes non-qualifying candidates
   rather than merely down-weighting them. A verification layer could add a hard-rule gate that runs
   before or alongside the score.

2. **Evidence/citations behind a match or sourcing result.** Neither the AI Sourcing page nor the
   matching blog post documents evidence quotes, source links, or a citation trail showing *why* a
   profile scored the way it did — only the final numeric score/profile. A layer that shows the
   underlying evidence (which resume line, which public profile field) for each score would be new.

3. **Credential/identity verification.** No native background-check, credential-check, or candidate
   identity-verification feature was found on any Recruit CRM page (§5); their own blog treats
   background checks as a third-party category. A verification layer that confirms licenses,
   certifications, or identity would not duplicate anything documented here.

4. **Reply classification and next-best-action in sequences.** The Sequences help article (§4)
   documents scheduled multi-channel sends and failure-pausing only — no automatic classification of
   inbound replies (interested/not-interested/OOO) and no intelligent snooze/next-step logic. This is
   a documented absence, not a competitor claim.

5. **Verified-contact-data methodology/accuracy disclosure.** Recruit CRM claims "verified emails and
   phone numbers" from its Chrome extension but discloses no verification method or accuracy rate
   (§2). A layer that discloses/audits its own contact-verification confidence would differ from an
   unqualified "verified" claim.

6. **Explainable match reasoning at the sub-score level.** The 0–100 match score (§3) is not broken down
   by factor on the pages found. A layer that decomposes "why this score" (which of skills/experience/
   education/location drove it, and by how much) is not documented as existing today.

These six items are the only gaps I can point to a specific Recruit CRM (or reviewer) URL and quote
for. Anything not listed here that *might* also be a gap (e.g., internal scoring methodology, model
provenance, data-source licensing) simply was not documented on any page reachable this session, and
its absence should not be treated as proof it doesn't exist in some undocumented form — it means "not
found on their pages as of 2026-09-11," per the brief's evidentiary standard.
