# CV review log — AI Product Owner / Product Manager, ISD (Lyon, CDI)

Deliverable: `CV MAZUMDAR Debanjan EN - AI Product Owner ISD.pdf` (same folder).
Source script: `execution/personal_workflows/cv_builder_ai_po_isd_en.py`.
Baseline compared against: `deliverables/cv_ai_pm/CV MAZUMDAR Debanjan EN.pdf` (the CV you uploaded).

## 1. How it stands out, quantitatively

Measured with pdfplumber on the two PDFs (`.tmp/cv_isd_compare.py`, 45 terms lifted from the JD).

| Metric | Uploaded CV | New CV | Change |
|---|---|---|---|
| Pages | 2 | 2 | = |
| Words | 712 | 781 | +10% (one extra Wiser bullet and one extra skills row, both JD-driven) |
| JD terms present (of 45) | 22 (49%) | 39 (87%) | +17 terms |
| Bold figures (numbers in bold) | 33 | 37 | +4 |
| JD responsibility blocks covered (of 5) | 2 | 5 | Backlog, Business partnering & change, Governance were absent |
| Public GitHub repos cited | 0 (projects had no links to the code) | 3, each linked | Anneal, CV Optimizer, YouTube Video Analyzer |

Terms the JD uses that the uploaded CV did not contain at all and the new one does: product vision, delivery cadence, risk escalation, needs gathering, expectation management, support materials, use case, ROI, vendor evaluation, explainability, fairness, compliance, KPI, documentation, reporting, senior stakeholders, data pipelines, change management.

Terms still absent, on purpose: "financial services" and "private equity" (you do not have it; per your brief it is not invented), "cyber" (no evidence of a Cyber-team workflow in your history; the governance row says "AI governance documentation" instead), "AI/ML" as a literal string (the CV says LLM, GenAI, AI agents), "measurable" (figures do the job).

Hard requirements of the JD and where the CV answers them:

- Minimum 5 years PO/PM: header says 11 years PO/PM (Avaya 2015 to today), 15 years in software.
- One significant AI or data product deployment: the Wiser GenAI product line and company-wide rollout, with $150K budget and adoption figures.
- Master's degree: MSc, Toulouse Business School.
- English, French a plus: both C2.
- Healthcare / financial services plus: Evolent is now described as "Healthcare SaaS (US payers and providers)" and "regulated healthcare context (compliance, privacy)".
- Lyon: contact line says "Paris, France — available for Lyon". Remove that if you are not willing to relocate.

Figures bolded for this JD (the ones a Data/AI manager in an ISD scans for): +45% adoption, +40% BU adoption, +20% CSAT, −55% p95 latency, $150K budget, 5 squads, 12+ products, <30-day median, $1M+ pipeline, ~$200K/yr removed, +25–30% delivery predictability, −25% ambiguity, 3 squads, +30% velocity.

## 2. What was reframed (nothing invented)

- Title changed from "Senior Product Manager — AI & Agentic Automation" to "AI Product Owner / Product Manager", the JD's own title. "Senior" dropped from the header because the role is not a senior grade and an ISD recruiter screens for fit, not for overqualification.
- Wiser bullets reorganised to mirror the JD's five responsibility blocks: product line and roadmap, rollout and vendor evaluation, business partnering, delivery and risk. Every figure is the one already on your CV.
- "Vendor and model evaluation (build vs. buy)" is a restatement of running a product line on OpenAI/Anthropic APIs with model choice; "change management and onboarding per BU" is a restatement of the GenAI rollout. Both are reasonable readings of what you already claimed; if either overstates what you did, soften it.
- Skills regrouped as Product ownership, Partnering, AI & data, Responsible AI, Build. The old "Leadership" row went; the ISD role is a bridge, not a management role.
- Evolent, Pitney Bowes and Avaya bullets now use Product Owner vocabulary (backlog, sprint goals, RAID reviews) because the JD title is Product Owner first.
- Projects: three public repos from github.com/dmazumdar186 with clickable links, chosen for relevance to an ISD (release gate for AI code, eval-first product, token-cost control). AgentUp and Job Search Engine were dropped; Humanizer and the mobile template were cut for length.
- The "Impact" line became "Key figures" and leads with adoption and CSAT, which is what "measurable value and adoption" in the JD means.

Assumptions to confirm: RICE and WSJF as prioritisation methods (added to the skills row; remove if you have never used them), "explainability & fairness checks" in the Responsible AI row, "3 continents" for Paris/US/India.

## 3. What was humanized, and how

Lens used: a Lyon-based career counsellor who has placed product people in IT departments since well before LLMs, writing in English for an English-language JD but keeping French CV habits (short, factual, no first person, no self-praise, figures instead of adjectives).

| Machine draft | Humanized | Why |
|---|---|---|
| "Senior Product Manager with 15 years in B2B SaaS, specialized in AI, GenAI and agentic automation products. I run product discovery with business teams, defend prioritization at VP/C-level, and stay hands-on..." | "Product Owner / Product Manager, 11 years on data and AI products, the last four on GenAI. Used to sitting between an IT department, business lines and a Data/AI lead: a vague business need becomes a backlog developers can work from, then gets followed through to adoption." | French CVs do not say "I". The sentence names the three parties in the JD's org chart and describes the actual job in plain words a Data/AI manager would use in the interview. |
| "stay hands-on — LLM, RAG, agent orchestration, low-code and Python — when building is the fastest path to impact" | "Hands-on enough on LLM, RAG and agents to challenge a vendor or an estimate." | "Fastest path to impact" is LLM filler. A counsellor would say what being hands-on buys the employer: you can push back on a vendor or a dev estimate. |
| "Own the AI/GenAI product line end-to-end (...): discovery → PRDs → LLM evaluation gates → rollout" | "Owner of the AI/GenAI product line (...): vision and roadmap with the CPO, weekly backlog refinement with business and dev, release gated by LLM evaluation" | Arrows and "end-to-end" are machine tells. Replaced with the cadence itself: weekly refinement, a gate before release. |
| "Aligned 5 cross-functional squads (Paris, US, India) on one prioritized roadmap — through influence, without formal authority." | "5 cross-functional squads (Paris, US, India) on one roadmap, without line authority." | Same fact, half the words. "Line authority" is how a French HR reader says it. |
| "Ran A/B tests, feature flags and drift monitoring with GDPR / privacy-by-design guardrails" | "Delivery and risk: A/B tests, feature flags, drift monitoring, GDPR / privacy-by-design written into every AI story." | Labelled the bullet with the JD's own heading. "Written into every AI story" is concrete; "guardrails" is a buzzword. |
| "Shipped an autonomous outbound engine (agentic pipeline: Claude-based reply classification...) — $1M+ qualified pipeline, ~$200K/yr SDR cost replaced." | "One agentic outbound pipeline (...): $1M+ qualified pipeline, ~$200K/yr of manual work removed." | "SDR cost replaced" reads as sales jargon to an IT department. "Manual work removed" is the ISD framing. |
| "Structured product discovery (...) → prioritized roadmap and backlog — −35% iteration cycles" | "Set up product discovery (...) and a prioritised backlog where there was none." | "Where there was none" is the kind of detail a counsellor adds because it is what the interviewer asks next. British spelling throughout, as expected in France. |
| "+30% platform scalability via SLA/SLO frameworks and QA governance" | "Data product backlog in a regulated healthcare context (compliance, privacy): SLA/SLO framework, QA governance, documentation standards." | Leads with the context the JD rewards (healthcare, regulated) before the method. |
| Em-dashes and arrows as sentence joints (12 in the original experience section) | Colons, commas and full stops | Dashes-as-glue is the most recognisable LLM tell; a human CV writer uses punctuation that existed before 2022. |
| Skills row "Leadership: VP/C-level stakeholder management • Delivering through ambiguity" | Removed | "Delivering through ambiguity" is a LinkedIn-ism. The JD is a bridge role; "Partnering" with needs gathering and expectation management says what you will actually do. |
| Projects as feature lists ("multilingual ATS scoring + CV rewrite; eval-first build") | One plain sentence each, with the GitHub link | A recruiter clicks; a sentence tells them what they will find. |

Checks a counsellor would run before sending, all done: no first-person pronouns; no adjectives without a figure ("strong", "proven", "passionate" absent); every bullet starts with a noun or a past-tense verb; dates and employers unchanged; two pages; text selectable for ATS; British spelling; no em-dash sentence glue.

## 4. Build and checks

```
python3 execution/personal_workflows/cv_builder_ai_po_isd_en.py --out "deliverables/cv_ai_po_isd/CV MAZUMDAR Debanjan EN - AI Product Owner ISD.pdf"
python3 -I .tmp/cv_isd_compare.py "<pdf>"     # pages, words, bold figures, 45-term JD coverage
```

Visual QA: two rounds by a vision worker on 80-dpi page renders. Round 1 found the skills label column colliding with the value column and page 2 under-filled; fixed by widening the label column to 3.6 cm and raising body text 0.4 pt. Round 2 result is in the session summary.
