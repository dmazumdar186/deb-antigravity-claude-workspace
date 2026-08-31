# CV — Christian Dior Couture / D_NEXT, Senior IT Lead Consultant (GenAI-Assisted Development Deployment Program)

**Built 2026-08-28.** Builder: `execution/personal_workflows/cv_builder_dior_itlead_en.py` (same teal template
as the generic PM CV; content only). Gate: `tests/cv_ats_score_jd.py` (JD-driven; pools hand-extracted from
`Downloads/IT lead job Desc.pdf`). Final PDF: `CV MAZUMDAR Debanjan EN - Dior IT Lead GenAI.pdf` (also copied to
`Downloads/Job Applications 2024/CV/Dior IT Lead GenAI EN/`).

Rebuild: `py execution/personal_workflows/cv_builder_dior_itlead_en.py --out ".tmp/cv_dior_itlead_en.pdf"`
Gate:    `py tests/cv_ats_score_jd.py --cv ".tmp/cv_dior_itlead_en.pdf" --jd "C:/Users/deban/Downloads/IT lead job Desc.pdf"`

## Review trajectory (four independent Fable-5 reviewers, each seeing only the PDF + JD + sources)

| Version | Dior recruiter (20 yr) | D_NEXT hiring manager | Enterprise-ATS engineer (real-parser est.) | Fact-checker | Own gate (proxy / hygiene) |
|---|---|---|---|---|---|
| v1 | 58 MAYBE | 62 INTERVIEW (cond.) | ~70 | WARNINGS: 0 fabricated numbers, 5 wording issues, 1 URL note | 98 (lenient scorer) |
| v2 | 65 MAYBE | 66 INTERVIEW | ~82 | — | 98 |
| v3 | 68 MAYBE, phone-screen yes | 66 INTERVIEW, "ship v3" | ~86 | 4/5 closed; 1 = operator's call | 98 / 98 |
| v4 (final) | **70 MAYBE, phone-screen yes** — "first version where the 3-second screen has no defect" | **66 INTERVIEW** — "ship it; no further wording edits" | **82 — SUBMIT: YES** (range 80–85; 86→82 is the deliberate truthfulness cuts) | **all items closed; nothing not-defensible; locked names absent** | 81 proxy / 100 hygiene (strict scorer: primary title is Product-family → 12/20) |

| v5 (operator facts) | **76 SHORTLIST (borderline)** — "first screen answers the mission owner's three practical questions unprompted" | **72 INTERVIEW (firm)** — "submit v5; no further structural edits" | (parse unchanged; keywords only gained) | (operator-stated facts; no source to check) | 82 proxy / 100 hygiene |
| v6 (final: recruiter D1–D4 + HM's three inferences trimmed pending confirmation) | — | — | — | — | **85 proxy / 100 hygiene** (gate no longer scores the bare adjectives "enterprise-wide" / "complex") |

Baseline generic PM CV on the same gate: proxy 30 / FAIL — the gate discriminates on JD fit, not hygiene.

## Operator answers (2026-08-28, chat) and how v5 used them

| Q | Answer | Rendered as |
|---|---|---|
| 1 Program lead? | **yes** | headline "IT Program Lead", Wiser b1 "as program lead end-to-end", Skills "IT Program Management" — now confirmed, not inferred |
| 2 Scale | "yes" — no numbers | nothing added; "global, enterprise-wide" stays an adjective. **Still owed: BUs / countries / users / engineers** |
| 3 Budget | **$150K USD** | summary + Wiser b1 "$150K program budget with consumption tracked against forecast" (forecast tracking is inferred from owning the budget — confirm) ; Skills "Program Budget & Forecast Tracking" |
| 4 Exec tier | **CPO** | "go/no-go steering reviews with the CPO and BU leads", "executive reporting to the CPO" |
| 5 Change mgmt | "brought AI infra from fragmented usage in Wiser" | summary + Wiser b4: "consolidated fragmented, team-by-team AI usage into one shared AI infrastructure and operating model across the BUs — the change-management core of the program" |
| 6 Availability | **immediately available** | contact line "Immediately available for consulting missions — Paris area (hybrid)" |

Still unanswered (unclaimed on the CV): training headcount / formats, operational committee existence, engineering-productivity KPIs, Copilot administration, consulting vehicle (freelance / portage / ESN), MSc full-time.

## What changed and why (v1 → v4)

- **Honesty (fact-checker):** no number is fabricated; all match `personal_brand/metrics_canonical.md` or counts taken from
  this workspace on 2026-08-28. Removed: "6 review agents" (4 of 6 are reviewers), "260+ production scripts" (43 are tests),
  "440+ commits", "forecasting" (unsourced → "estimation"), "each with health endpoints" (true only for deployed systems),
  "security review" (unsourced), Evolent "budget" (unsourced), "Since 2022 … GenAI program" (predates ChatGPT → "At Wiser
  (since 2022)"), team-adoption claim for the AI SDLC (→ "reference implementation … single-operator scale to date").
- **3-second scan (recruiter):** honest headline (held title first), third-person summary without the JD's deliverables
  list, availability line, +33 phone, no number repeated 3× on page 1, 2010–2015 split into dated entries, projects
  deduplicated, 2-line headline.
- **Parseability (ATS engineer):** bullet glyph now embedded Arial U+2022 (was Helvetica DEL → `(cid:127)`), one em dash
  per title line, descriptor never after the date range, "Apr 2019 – Sep 2019", US spellings, literal JD terms only where a
  bullet evidences them.
- **JD-echo migration (recruiter's named pattern):** phrases cut from one section kept reappearing one section lower.
  v4 test: every hit of "transformation program / complex / formal authority / Program Charter / operational committees /
  Stakeholder Mapping / knowledge sharing / adoption strategy" must point at a bullet with a fact, or go. Kept with a fact:
  "without formal authority over any squad" (PM coordinating 5 squads), "knowledge sharing (playbooks)", "GenAI Adoption
  Strategy & Planning" (+40 % cross-BU adoption), "enterprise-wide" (cross-BU global rollout). Gone: the rest.

## Recruiter ↔ ATS tension, and the shared-oracle warning

The recruiter and the ATS engineer pulled opposite ways on JD literals. The fact-checker's addendum names the trap: the
gate's pools reward exactly the phrases with no source ("operational committee", "budget", "forecast", "transformation
program", "complex", "steering"). **A green gate score is therefore NOT evidence a claim is true** — v4's proxy dropped from
98 to 81 when unsourced literals came out, and that drop is the correct outcome, not a regression to fix by re-adding words.
The number that matters for the ATS is the engineer's estimate (v3 ≈ 86); the remaining gap to a "top-20 % auto-forward"
band is structural (Product-family titles, no luxury exposure, no Copilot administration, no program-budget figure).

## Operator-owned facts — the only way to move the ceiling (every reviewer converged on these)

1. **Was the Wiser GenAI rollout run as a *program* with you as its lead?** Drives the headline "IT Program Lead", Wiser
   bullet 1 "as program lead", Skills "IT Program Management". If no → say so and these words come out.
2. Program scale: number of BUs / countries / users / engineers across the 5 squads; program duration.
3. Budget: any program or vendor budget you were accountable for (€ figure); annual LLM spend governed.
4. Executive tier: most senior attendee of the go/no-go steering reviews (title), cadence, chaired vs presented; did an
   operational committee exist?
5. Change management: number of people trained / sessions / formats; comms plan; champions or community of practice.
6. Any engineering-productivity KPI ever measured (cycle time, PR throughput, review latency, defect escape).
7. Org-level administration of Copilot / Cursor / Claude Code (seat policy, telemetry, IP settings) — if none, keep the
   "Copilot-class" hedge.
8. Consulting vehicle (freelance / portage / via ESN) and start date; Wiser exit timing.
9. MSc 2019–2021 full-time? (closes the 21-month gap explicitly).
10. Interview prep: denominators for every % (+40 % BU adoption of what / baseline / period; "+25–30 % delivery precision"
    definition; "+30 % scalability"); who verifies the $1M+ pipeline; the list of 12+ products with go-live dates.

## Deliberate decisions (recorded so they are not re-litigated)

- USD figures ($1M+, ~$200K/yr, $85K) kept: canonical across CV / LinkedIn / prodcraft.fyi; changing one surface breaks
  `check_metric_coherence.py`.
- "Bilingual (C2)" for FR: operator-confirmed elsewhere; recruiter warns it will be tested on the first call.
- AgentUp hyperlink `agentup-iag.pages.dev`: kept — it is the operator's own public deployment; the hostname reveals the
  other hiring company to anyone who hovers. Operator's call.
- "80+ directive specifications" kept (hiring manager values it as spec-driven evidence; recruiter would drop it).
- Justified alignment + bold metrics: the operator's template; unchanged.

## Audit stack (2026-08-28)

| Auditor | Verdict | Evidence |
|---|---|---|
| Front-door synthetic | PASS | builder CLI → 2-page PDF → `cv_ats_score_jd.py` PASS (81/100 proxy ≥ 80; hygiene 100; 0 hard rules) |
| Customer-POV / output acceptance | PASS | recruiter 3-second scan on rendered PNGs, v1→v4; page renders inspected each round |
| Anneal | PASS | classic, cheap-gemini tier, CONVERGED clean in 1 round, $0.0015 |
| Panel — evidence / dogfood / deployment / gaps | PASS | four real sub-agents × 3–4 rounds; gate validated against a known-bad input (generic CV → 30) |
| Test suite | PASS | `pytest -k cv`: 20 passed, 4 skipped; `test_cv_builder.py` now pins the new builder (2 pages) |
| Adversarial / pipeline-auditor | WARNINGS → closed | fact-checker counted from source: 30 claims, 0 fabricated; 4 wording fixes applied; 1 operator call |
| SAST | PASS | 0 high / critical |
