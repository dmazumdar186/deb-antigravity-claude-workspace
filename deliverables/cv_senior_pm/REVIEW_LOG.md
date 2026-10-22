# Generic Senior PM / Senior AI PM CVs — research, build, humanize, audit (2026-10-22)

Deliverables (this folder):

- `CV MAZUMDAR Debanjan EN.pdf` — generic English CV, 2 pages, ~675 words, 18 bold figures.
- `CV MAZUMDAR Debanjan FR.pdf` — generic French CV, 2 pages, ~740 words, 19 bold figures.
- `audit/` — machine-readable panel verdicts (round 6) and the baseline audit of the CV you uploaded.
- `jd_research/` — the 20 postings used as the yardstick (index + keyword tables). Raw posting text stays in `.tmp/` (third-party content, not committed).

Builders: `execution/personal_workflows/cv_builder_senior_pm_en.py` and `_fr.py`. Audit harness: `execution/personal_workflows/cv_panel_audit.py`.

## 1. Research: the 20 postings

Collected live on 2026-10-22 through the Lever, Ashby and Greenhouse APIs and French boards (WTTJ mirror, Hellowork, Meteojob, collective.work). Source URLs are in `jd_research/index_*.json`.

| # | English (10) | Type | # | French (10) | Type |
|---|---|---|---|---|---|
| 01 | Brevo — Senior PM | Senior PM | 1 | Theodo — Senior PM | Senior PM |
| 02 | Pigment — Senior PM | Senior PM | 2 | Yespark — Senior PM | Senior PM |
| 03 | Pennylane — Senior PM | Senior PM | 3 | Converteo — Senior PM | Senior PM |
| 04 | Datadog — Senior PM, APM | Senior PM | 4 | Evaneos — Senior PM | Senior PM |
| 05 | Doctolib — Senior PM, PLG | Senior PM | 5 | Thiga — PO / PM Senior | Senior PM |
| 06 | Front — Senior PM, AI | Senior AI PM | 6 | Saint-Gobain DBF — Senior PM IA | Senior AI PM |
| 07 | Photoroom — Staff PM, Agentic & AI Platform | Senior AI PM | 7 | EDF — PM Outillage IA | Senior AI PM |
| 08 | Mistral AI — Lead PM, Inference | Senior AI PM | 8 | Hubvisory — AI PM | Senior AI PM |
| 09 | Intercom (Fin) — Staff AI PM | Senior AI PM | 9 | Theodo Data & IA — Lead PM | Senior AI PM |
| 10 | Intercom (Fin) — Senior PM, Service Agent | Senior AI PM | 10 | TEKsystems — IA & Data Portfolio PM | Senior AI PM |

What the postings ask for most (count of postings mentioning the term):

- English core (7+ of 10): outcome and impact metrics (10), end-to-end ownership (9), AI fluency (9), technical fluency with engineers (9), design/UX partnership (9), platform/API (9), cross-functional collaboration (9), roadmap, strategy, prioritisation and trade-offs, problem framing, autonomy (8 each), product judgement, go-to-market, experiments (7 each).
- French core (7+ of 10): IA (10), priorisation (9), data/analytics (9), KPI et mesure d'impact (8), management/coaching d'équipe (8), rigueur (8), vision produit, roadmap, discovery, ROI, parties prenantes, autonomie (7 each).
- Surprises: four of five French Senior PM postings expect daily AI use in the PM craft (Claude, Claude Code named twice). Tools are rarely named in French postings. Nobody asked for a one-page CV. Only 4 of the 10 English postings state years; the French ones range from 3 to 7+.

The CVs were built to carry every core term truthfully. Terms that need facts you do not have were left out on purpose: Figma / design systems, PLG / ARR / CAC / pricing, GPU and inference economics, B2C marketplace years, Productboard / SAFe / ShapeUp, Power BI, Mistral platform.

## 2. Quantitative proof

### 2a. Keyword ATS (deterministic scorer, 0–10 per posting)

`cv_panel_audit.py` scores must-have coverage (50%), named tools (20%), cross-posting core terms (20%) and parseability (10%). It matches FR and EN synonyms and light stemming, the way Jobscan-class matchers and Workday/Greenhouse keyword filters do. Real ATS platforms do not publish a score; this is the closest reproducible stand-in.

| Round | EN mean | EN min | EN ≥9 | FR mean | FR min | FR ≥9 |
|---|---|---|---|---|---|---|
| Baseline: the CV you uploaded | 9.06 | 7.58 | 7/10 | 7.83 | 5.89 | 0/10 |
| Round 3: keyword-maximised rebuild | 9.44 | 8.54 | 7/10 | 9.12 | 7.30 | 6/10 |
| Round 6: final, humanised | 9.08 | 8.33 | 5/10 | 8.73 | 6.42 | 4/10 |

Per posting, round 6:

| EN | ATS | FR | ATS |
|---|---|---|---|
| Brevo | 8.64 | Theodo | 8.73 |
| Pigment | 10.0 | Yespark | 6.42 |
| Pennylane | 8.40 | Converteo | 8.95 |
| Datadog | 9.58 | Evaneos | 7.93 |
| Doctolib | 8.33 | Thiga | 10.0 |
| Front | 10.0 | Saint-Gobain | 8.17 |
| Photoroom | 8.80 | EDF | 8.08 |
| Mistral | 8.44 | Hubvisory | 10.0 |
| Intercom Staff AI | 9.33 | Theodo Data & IA | 9.00 |
| Intercom Service Agent | 9.33 | TEKsystems | 10.0 |

The keyword score fell between round 3 and round 6 because the panel (below) flagged the keyword-dense skills block and the metric strip as machine-written, and asked for them to be cut. That is the real trade-off: a 9+ on every posting by keyword needs the stuffing that a human reader penalises. Every posting under 9 is under 9 because of a fact you do not have (listed above), not because of wording.

### 2b. Human panel (LLM, three personas, independent JSON verdicts per posting)

Personas: a Lyon career counsellor placing PMs since before 2005, a senior head-hunter for Senior PM / AI PM in France, a senior in-house recruiter screening for that exact job. Each gives fit 0–10, would-call yes/no, objection, fix; plus a verbosity flag and a "reads human" score with the AI tells quoted. Model: Claude Sonnet via OpenRouter; prompts in `cv_panel_audit.py`.

| Metric (round 6) | English CV | French CV |
|---|---|---|
| Postings where all three would call | 7/10 | 10/10 |
| Persona-level "would call" | 23/30 | 30/30 |
| Mean fit (0–10) | 5.9 | 6.8 |
| Fit ≥7 on the generalist Senior PM / AI PM postings | Pigment, Pennylane, Front, Intercom ×2 | Theodo, Converteo (8), Hubvisory (8), Saint-Gobain, EDF, TEKsystems |
| "Too verbose" flags | 1/10 | 0/10 |
| Mean "reads human" (0–10) | 6.8 | 6.8 |

English no-calls, with the panel's reason: Doctolib (PLG: no conversion/ARR/pricing ownership), Mistral (inference: no GPU economics or infra-to-revenue), Datadog recruiter only (APM/observability domain). All three are domain facts, not CV wording.

### 2c. Jev gate (decision model, no text generation)

"Would a 20-year recruiter phone this candidate after a 30-second read?" Probability per posting, mean: EN 0.48, FR 0.67. Lowest: Doctolib 0.16, Mistral 0.19, Yespark 0.25 (B2C). Highest: Hubvisory 0.89, TEKsystems 0.83, Converteo 0.82, Theodo 0.78.

### 2d. Honest verdict against your criteria

- "ATS above 9/10 on all 20": not met, and not meetable truthfully. 9 of 20 postings score ≥9; the other 11 score 6.4–8.9, each because the posting demands a fact outside your history. The baseline CV you uploaded scored ≥9 on 7 of 20.
- "A 20-year recruiter would call": met on 17 of 20 postings by unanimous panel, 18 by majority. The three misses are Doctolib PLG, Mistral inference and (one persona) Datadog APM.
- "Not verbose": met. 0 flags in French, 1 in English (Pigment reviewer wanted the ProdCraft line shorter still). The uploaded CV drew "too verbose" on 9 of 10 French postings in the first panel round.
- "Reads human": partially met. Mean 6.8/10 on both, plateaued over three rounds; the remaining tells the panel names are round percentages without baselines and the skills list itself. Supplying baselines (user counts, before/after numbers) would move this; inventing them would not.

The loop was stopped at round 6 because rounds 5 and 6 produced the same scores within noise, and every remaining fix the panel proposed required new facts.

## 3. What the panel changed, round by round

1. Round 1 (keyword rebuild from the JD model): coverage up, but "too verbose" on 9/10 FR postings; "reads human" 6.
2. Round 4: key-figures strip removed, old PO roles merged into one entry, skills cut from 5 rows to 4, projects to one line, ProdCraft to two lines. "Too verbose" fell to 2/10.
3. Round 5: tenure made explicit ("PO 2015–19, PM since 2021") because "11 years PM/PO" was read as stretched; CSAT wording fixed ("up 20%"); engineering degree moved first in the French Formation; "last four years on GenAI" corrected to "since 2022"; Lyon mention dropped from the generic versions.
4. Round 6: summary now opens on discovery and outcomes (what the generalist postings screen for); slogan sentences cut; the causal "after the rebuild on evaluation gates" removed; vague closers removed; ProdCraft labelled "evenings and weekends" because every reviewer asked whether you are available.

## 4. Humanization log (the counsellor's pen)

| Machine draft | Final | Why |
|---|---|---|
| "Senior Product Manager, AI and data products, from discovery to adoption." | "Senior Product Manager on AI and data products. Continuous discovery and customer interviews first, then a roadmap with outcomes attached and a launch that gets measured." | "From X to Y" is a template phrase; the replacement says what you actually do, in the order a recruiter asks about it. |
| "Reads code, prototypes before writing the spec, and can hold a trade-off discussion with an engineer as easily as a roadmap review with a CPO." | "Prototypes with Claude Code before writing the spec; works through trade-offs with engineers and roadmap with the CPO." | Triplets with a flourish are the most-flagged tell; the fact (you prototype, you argue trade-offs) stays. |
| "The trade-offs are made in the open, which is why they hold." | removed | Aphorism. Flagged by 18 of 20 reviewers. |
| "Key figures: +45% • +20% • −55% • $150K • $1M+ • ~$200K/yr • 5 squads" | removed; each number now sits in its own bullet with its context | A stat strip reads as generated and repeats the bullets. |
| "Sprint ambiguity down 25%; delivery predictability up 25–30%." | removed | Un-baselined process percentages are the second most-flagged tell; the A/B and evaluation practices stay as facts. |
| "12+ AI products shipped at a <30-day median, owning discovery, PRDs, backlog and release gates" | "Side practice, evenings and weekends: 12 small AI products for clients, including an agentic outbound pipeline on Cloudflare Workers that replaced about $200K/yr of manual work" | Every reviewer asked whether ProdCraft means you are leaving; naming it a side practice answers the question before it is asked. |
| Skills: 5 rows, 40 items, incl. MCP, LLM-as-judge, golden set, red-vs-blue | 4 rows, 28 items, plain names | Keyword blocks mirror the posting and read as ATS bait; the panel discounted them. |
| "+30% scalabilité" (Evolent), "−25% instabilité" (Avaya), "−20% time-to-market" (Pitney) | one merged PO entry keeping only the Avaya velocity figure | "Near-identical round percentages across unrelated roles" was flagged on every French posting. |
| Three open-source project bullets | one line naming Anneal and the GitHub profile | Reviewers said the projects added length without helping a generalist application. |
| Em-dashes and arrows as sentence joints | colons, commas, full stops | Dash-glue is the single most recognisable LLM habit. |
| "Looking for a senior PM or AI PM role in a product team that ships." | "Paris-based, bilingual English and French, remote-friendly." | Objective statements are out of fashion in France; logistics are what the recruiter needs to know. |

What stays deliberately machine-free: no first person, no adjectives without a number, British spelling in English, French typography (espace before %, « K$ »), dates and employers unchanged, two pages, selectable text.

## 4b. Round 7–8 addendum (facts supplied by the candidate after round 6)

Added on 2026-10-22 after confirmation: product-led growth, pricing and packaging, Figma and Mixpanel at Wiser and InfoTnT; Jira and Confluence since IDrive; JTBD / Outcome-Driven Innovation since Evolent. Placed in the role bullets where they happened and in the skills rows; no new metrics were attached to them.

| Metric (round 8) | English CV | French CV |
|---|---|---|
| Keyword ATS mean / postings at 9+ | 9.18 / 7 of 10 | 8.69 / 4 of 10 |
| Postings where all three personas would call | 8 of 10 | 8 of 9 scored (one panel call errored) |
| "Too verbose" flags | 0 | 0 |
| Mean "reads human" | 6.7 | 6.9 |

Brevo moved from 8.64 to 9.6 (Figma was its missing must-have) and Doctolib from 8.33 to 9.0 on keywords, but the Doctolib panel still declines: it wants a named conversion, ARR or CAC result, which the CV does not carry. Mistral is unchanged for the same reason (inference economics).

## 5. Reproduce

```
python3 execution/personal_workflows/cv_builder_senior_pm_en.py --out "deliverables/cv_senior_pm/CV MAZUMDAR Debanjan EN.pdf"
python3 execution/personal_workflows/cv_builder_senior_pm_fr.py --out "deliverables/cv_senior_pm/CV MAZUMDAR Debanjan FR.pdf"
python3 execution/personal_workflows/cv_panel_audit.py --cv "<pdf>" --jd-dir .tmp/jd_research/en --lang en --out .tmp/cv_audit/x_en --panel --jev
python3 tests/cv_word_bold_keyword_count.py "<pdf>"
```

Panel and Jev need `OPENROUTER_API_KEY`. The JD research folder is regenerated by the two research briefs described in the directive changelog.
