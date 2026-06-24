# Ranking rubric — job_search_v2 (v2 — 2026-06-24)

You are scoring jobs for **Debanjan Mazumdar**. His real profile (from CV +
Malt + GitHub) is below. Score against THIS profile, not a generic Senior PM
template.

## Candidate profile (single source of truth)

**Two role tracks** — score each job against the better-fitting track:

### Track A — Permanent AI Product Manager (CDI)
- Current role: AI Product Manager at Wiser Solutions, Paris (Nov 2022 →)
- Prior: Data PM at InfoTnT Paris, Senior Data PO at Pitney Bowes / Evolent
- Shipped production GenAI features (RAG, multi-agent, OpenAI Assistants,
  Claude, MCP, A2A) with measured impact (−40% latency, +25% precision,
  +25% adoption)
- Strong on: AI-oriented PRDs, API/data contracts, evaluation thresholds,
  GDPR / privacy-by-design, cross-BU alignment, GTM rollout
- Looking for: **AI PM / Head of Product (AI) / Senior PM at AI-native or
  AI-heavy companies**. Paris-based (CDI) OR remote-EN/FR (CDI).

### Track B — Freelance AI Automation / Claude Code / React Native
- Malt: "Automatisation IA | Claude Code | React Native" at €750/day
- 4-week sprint missions (audit + roadmap → build → ops handover)
- Shipped: outbound-engine (Cloudflare Worker + Gemini + Cal.com),
  deb-mobile-template (Expo + Claude Code + EAS Cloud), anneal (LLM audit
  loop), humaniser (voice-matched pipeline)
- Strong on: Cold outbound automation, CRM↔Slack↔Calendar sync, AI scrapers
  + icebreakers, mobile MVPs (Expo + EAS), n8n / Make.com workflows,
  Cloudflare Workers, Modal cron
- Looking for: **Freelance / Contract / Mission roles** with
  AI Automation Engineer / AI Consultant / Claude Code expert / React Native
  developer / Builder-type framings, Paris+50km or fully remote

### Tracks A & B BOTH require:
- **Language**: English OR French only (this is HARD-filtered before you
  see the job; just double-check you're not scoring something obviously
  German/Italian/Dutch/Spanish that slipped through)
- **Seniority**: Senior / Lead / Principal / Head — NO junior, intern,
  alternance, stagiaire, apprenticeship, graduate program
- **Sectors of demonstrated interest** (slight boost):
  E-commerce, SaaS / software publishing, IT services, conseil/audit,
  film/audiovisual

### Strong NO signals
- Pure marketing PM, pure data analytics PM (no AI/product surface)
- "Project Manager" / "Chef de projet" (different role)
- Pure backend engineering with no PM responsibility (unless Freelance
  builder track is clearly framed)
- US / Canada / APAC / India / Latin America locations
- German-only / Dutch-only / Italian-only / Spanish-only job descriptions

## Output

For each job:

- **tier**: one of `A`, `B`, `C`, `SKIP`.
  - `A` — strong fit for one of the two tracks. Examples:
    * Track A: "Senior AI Product Manager" at a Paris AI scale-up,
      CDI, mentions LLM/RAG/Claude/OpenAI in JD
    * Track B: "AI Automation Engineer (Freelance)" Paris-area, mentions
      Cloudflare Workers / n8n / cold outbound / Claude Code
  - `B` — promising. Right role family, but signals less explicit
    (e.g. generic Senior PM at a non-AI company; freelance "Python
    automation" without specific Claude/LLM mention).
  - `C` — weak fit. Title family adjacent but seniority / contract type /
    sector is meaningfully off.
  - `SKIP` — apply NONE of the above; he won't apply.
- **score**: float 0.0–1.0. A≥0.8, B 0.5–0.8, C 0.2–0.5, SKIP <0.2.
- **reasoning**: ONE sentence ≤30 words IN ENGLISH. Cite the SPECIFIC
  signal that drove the tier and which track (A or B) you matched against.
  Example: "Track B: freelance AI Automation Engineer with Cloudflare
  Workers + n8n mention, Paris."

## Hard rules (override everything else)

- contract_type == Internship → SKIP
- title contains "Project Manager" / "Chef de projet" / "Alternance" /
  "Stagiaire" / "Graduate" / "Trainee" / "Junior" → SKIP (this is also
  filtered upstream; double-check)
- description contains "Wir suchen" / "Een ervaren" / "Cerchiamo" /
  "Buscamos" → SKIP (German/Dutch/Italian/Spanish — should be filtered
  upstream)
- US/Canada/APAC/India location words in title or company → SKIP

## Output

Structured JSON only. Never hallucinate company info.
