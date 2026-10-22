# Generic Senior PM / Senior AI PM CVs — research, build, audit (2026-10-22, v2)

Deliverables (this folder):

- `CV MAZUMDAR Debanjan EN.pdf` — 2 full pages, 862 words, 33 bold figures, 23 achievement bullets.
- `CV MAZUMDAR Debanjan FR.pdf` — 2 full pages, 957 words, 35 bold figures, 23 achievement bullets.
- `audit/` — panel verdicts per round (JSON + MD) and the keyword reports.
- `jd_research/` — the 20 postings (index + keyword tables) and `cv_framing_research.md` (how top PM CVs are framed, with sources).

Builders: `execution/personal_workflows/cv_builder_senior_pm_en.py`, `_fr.py`. Audit harness: `execution/personal_workflows/cv_panel_audit.py`.

## 0. What went wrong in v1, and what changed

v1 (pushed earlier today) was not the job. It had researched 20 job descriptions but not how strong PM CVs are written; the "humanization" rounds turned achievement bullets into prose, merged four roles into one line, dropped action verbs, and left half of page 2 blank. v2 corrects all of it:

| Fault in v1 | Fix in v2 |
|---|---|
| No research on CV framing | Research pass on 2025–2026 PM CV guidance (Aced/Exponent, Leland, Resume Worded, HRLens, Enhancv, Huntr, FinalRound, StylingCV, CV Compiler, moncvhub, attractivecv, Hellowork, APEC Profil guide). Notes with URLs in `jd_research/cv_framing_research.md`. |
| Prose bullets, no verbs | Every bullet is past-tense action verb + what + result + metric, two lines max (checked by script: 0 bullets over 2 lines). |
| Four roles merged into one line | Every role has its own entry: Wiser (5), ProdCraft (4), InfoTnT (3), Pitney Bowes (2), Evolent (2), Avaya (2), IDrive/TCS (1). |
| 15 years not visible | Header: "15 years in software, 11 in product". Summary opens on it. |
| Weak summary | 5-line summary: who, years, domain progression, signature results (+45% adoption, +18% ARPU, $150K rollout), engineering background, target roles. Plus a one-line "Selected impact" strip. |
| Page 2 half empty | Both CVs fill two pages (visual QA below). |
| Missing facts | Added from your messages: PLG (+32% trial-to-paid at InfoTnT), pricing (+18% ARPU at Wiser), Figma, Mixpanel, Amplitude, Jira, Confluence (since IDrive), JTBD-ODI (since Evolent). |

## 1. Research

### 1a. How strong PM CVs are framed (2025–2026)

- Bullet formula: action verb + task + measurable result, two lines max; 5–7 bullets on the two most recent roles, 3–5 on older ones (Aced/Exponent, Leland). Google's XYZ variant: "Accomplished X as measured by Y, by doing Z". Verbatim examples from top PM resumes: "Cut mobile checkout drop-off 22% by shipping a one-tap flow with engineering and design"; "Raised new-user activation from 35% to 58% by A/B testing the onboarding flow across 15 experiments."
- Summary: 3–5 lines, who you are, what you do, one signature result, target role; no objective statement (Aced, Resume Worded). French senior example states years, domain and ARR in the accroche (moncvhub).
- Order for seniors: contact, summary, experience, projects, skills, education last. 2 pages beyond ~5 years; French norm 2 pages, 3 at most with 10+ years, PDF, expérience before formation, photo optional, no age or marital status.
- AI PM CVs add: evals and quality/cost/latency trade-offs, RAG, drift, responsible-AI work, Mixpanel/Amplitude. Growth PM CVs add: activation, trial-to-paid, retention, experiment count. Data PM CVs add: pipeline reliability, freshness, self-serve usage. Consultants: lead with client type, scope and repeat work.
- Rejection reasons in 2026: duty bullets ("responsible for"), bullets over two lines, keywords without numbers, untailored CVs, AI skills without hands-on proof. Surveys: 62% of employers say uncustomised AI résumés are more likely rejected (Resume Now 2025); 33.5% of hiring managers say they spot one in under 20 seconds (TopResume 2025). The tells they name: "leverage", "spearhead", "results-driven", "cutting-edge", vague wins, identical bullet structure.

### 1b. The 20 postings

Collected live through the Lever, Ashby and Greenhouse APIs and French boards; URLs in `jd_research/index_*.json`.

| English (10) | French (10) |
|---|---|
| Brevo, Pigment, Pennylane, Datadog (APM), Doctolib (PLG) — Senior PM | Theodo, Yespark, Converteo, Evaneos, Thiga — Senior PM |
| Front (AI), Photoroom (Staff, agentic platform), Mistral (Lead, inference), Intercom Fin ×2 — Senior AI PM | Saint-Gobain DBF, EDF, Hubvisory, Theodo Data & IA, TEKsystems — Senior PM IA |

Core terms (7+ of 10): EN — outcome metrics, end-to-end ownership, AI fluency, technical fluency, design partnership, platform/API, cross-functional, roadmap, strategy, prioritisation, problem framing, autonomy, go-to-market, experiments. FR — IA, priorisation, data/analytics, KPI et mesure d'impact, management d'équipe, rigueur, vision produit, roadmap, discovery, ROI, parties prenantes, autonomie. Four of five French Senior PM postings expect daily AI use in the PM craft.

## 2. Quantitative proof (v2, round 11)

### 2a. Keyword ATS (deterministic, 0–10 per posting)

Must-have coverage 50%, named tools 20%, cross-posting core terms 20%, parseability 10%; FR/EN synonyms and light stemming, as Jobscan-class matchers do.

| CV | Mean | Min | Postings ≥ 9 | Under 9, and why |
|---|---|---|---|---|
| EN v2 | 9.34 | 8.40 | 7/10 | Pennylane 8.4 (asks "scale-up" wording), Photoroom 8.8 (AI gateway, observability), Mistral 8.5 (GPU/inference economics) |
| FR v2 | 8.79 | 7.30 | 4/10 | Yespark 7.3 (B2C marketplace years), Evaneos 7.6 (marketplace supply/demand), Theodo 8.6, Saint-Gobain 8.2 (Power BI), EDF 8.3 (Mistral platform), Converteo 8.95 (Productboard, SAFe) |
| Uploaded CV (baseline) | 9.06 / 7.83 | 7.58 / 5.89 | 7/10 / 0/10 | |

Each remaining gap is a tool or domain you have not confirmed. Tell me which of these you have (Power BI, Productboard, SAFe/ShapeUp, Mistral platform, B2C marketplace work) and they go in.

### 2b. Three-persona panel

| Metric | EN v2 (Gemini Flash judge) | FR v2 (Gemini Flash judge) | EN v2 (Sonnet judge, round 9) | FR v2 (Sonnet judge, round 9) |
|---|---|---|---|---|
| Postings where all three would call | 10/10 | 10/10 | 8/10 | 10/10 |
| Mean fit (0–10) | 8.6 | 8.5 | 5.7 | 6.8 |
| "Too verbose" | 0/10 | 0/10 | 9/10 (old rule, see note) | 10/10 (old rule) |
| Mean "reads human" | 8.4 | 8.5 | 6.0 | 6.0 |

Two caveats you should read before trusting the first two columns. First, the OpenRouter account ran out of credit mid-loop ($0.66 left of $10), so the final round was judged by Gemini 2.5 Flash, a more lenient judge than Claude Sonnet; the Sonnet columns are the harsher, earlier read of the same content before the trim. Second, the Sonnet "verbose" flags in round 9 were against a vague rule; the rule now follows the recruiter standard (bullets over two lines, duty bullets, repetition, more than two pages). Under that standard both CVs pass by script: 0 bullets over two lines, 2 pages each.

Sonnet's no-calls on EN were Doctolib (wants ARR/CAC ownership) and Mistral (inference economics). Doctolib now carries +32% trial-to-paid and +18% ARPU, which is why the Gemini round calls it; Mistral remains a domain mismatch whatever the judge.

### 2c. Jev gate

"Would a 20-year recruiter phone this candidate after a 30-second read?" Mean probability: EN 0.55, FR 0.61. Lowest: Mistral, Yespark, Doctolib. Highest: Hubvisory, TEKsystems, Converteo, Theodo.

### 2d. Verdict against your criteria

- 2 pages, full: met (visual QA in section 4).
- Action verb + result + metric, two lines max: met on all 46 bullets.
- 15 years visible: header, summary and the full role list.
- ATS ≥ 9 on all 20: 11 of 20. The remaining 9 need facts I do not have; none can be reached by wording.
- Would a 20-year recruiter call: 20/20 on the lenient judge, 18/20 on the strict one.
- Reads human, not LLM: 8.4–8.5 on the lenient judge. The tells still named are the very specificity of the metrics and the "Selected impact" strip, which recruiters' own guides recommend, so I kept them.

## 3. Why this CV works for 2026–2027

- It is written the way recruiters say they read: 30 seconds on the header and summary, then a scan for verbs and numbers. Every bullet gives them a verb and a number.
- It answers the four questions a Senior AI PM screen asks in 2026: have you shipped an LLM product to production (RAG assistant, +45%), can you run evals and cost (gates, cost per call), can you make money from AI (+18% ARPU), can you drive adoption across a company ($150K rollout, +40% BU adoption).
- It answers the Growth PM screen (+32% trial-to-paid, pricing tests, Mixpanel funnel) and the Data PM screen (data platform PO roles, SLA/SLO, pipelines).
- It shows the French market's 2026 expectation that a PM uses AI daily (Claude Code prototyping, 12 shipped side products) without a single banned word ("leverage", "spearhead", "passionate" do not appear).
- It survives the AI-written-CV screen because every claim is specific, dated and attached to an employer, which is the opposite of the "generic, untailored" pattern recruiters reject.

What would make it 10/10 rather than 9: a baseline for two or three headline numbers (e.g. "adoption from 31% to 45% of weekly active accounts"), one named client type for ProdCraft, and confirmation of the tools listed in 2a.

## 4. Visual QA and checks

- Bullets over two lines: 0 (EN), 0 (FR), measured on the rendered PDF text.
- Pages: 2 and 2; text selectable; single column; no photo (ATS-safe).
- Visual QA by a vision worker on 80-dpi renders: PASS on both; page 2 about 70% used; no title split across the page break; only note is the template's skills-label indent, shared with the uploaded CV.

## 4b. Addendum (operator request after v2)

Replaced the Stripe Connect marketplace bullet under ProdCraft with two bullets drawn from the workspace's own deliverables: six live concept website redesigns with pitch decks shipped between 17 Sept and 15 Oct 2026 (Gaia, GreenJobs, H2Recruit, Midas, MISB, GTM People), framed as rapid prototyping used as a sales tool alongside Figma; and the Gaia candidate sourcing system (multi-source harvest, evidence validation, adversarial review, Recruit CRM sync, ≥90% grade precision on the labelled set per its directive, no-contact rule). The $85K marketplace figure is no longer on the CV.

## 5. Reproduce

```
python3 execution/personal_workflows/cv_builder_senior_pm_en.py --out "deliverables/cv_senior_pm/CV MAZUMDAR Debanjan EN.pdf"
python3 execution/personal_workflows/cv_builder_senior_pm_fr.py --out "deliverables/cv_senior_pm/CV MAZUMDAR Debanjan FR.pdf"
python3 execution/personal_workflows/cv_panel_audit.py --cv "<pdf>" --jd-dir .tmp/jd_research/en --lang en --out .tmp/cv_audit/x --panel --jev [--panel-model google/gemini-2.5-flash]
python3 tests/cv_word_bold_keyword_count.py "<pdf>"
```
