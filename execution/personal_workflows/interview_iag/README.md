# AgentUp — IAG Hiring Interview Build

**AgentUp** helps call-centre agents sharpen customer-handling skills through short
daily AI-roleplay sessions. Every morning, agents run through **3 customer
scenarios × up to 5 turns each**, then receive automatic scoring across four
dimensions (Empathy · Accuracy · Resolution · Professionalism) with a written
strength + improvement note. A dashboard tracks streak, sessions/week, top/weak
skills, and a 30-day trend.

This is the reference implementation delivered for the IAG Services hiring
exercise. Built on **Astro + React + Tailwind**, deployed to **Cloudflare Pages**
(free tier) with a **Cloudflare Pages Function** that hides the Anthropic API
key. Powered by **Claude Sonnet 4.6** with automatic **Gemini 2.5 fallback**.

---

## Reviewer's map

| Doc | What it shows |
|---|---|
| **[`deliverables/prd_traceability_matrix.md`](deliverables/prd_traceability_matrix.md)** | 75-row audit: every PRD requirement → implementation → test that proves it |
| **[`deliverables/over_deliver_playbook.md`](deliverables/over_deliver_playbook.md)** | The 6 "over-deliver" layers shipped on top of the PRD, ranked by wow × effort |
| **[`ROADMAP.md`](ROADMAP.md)** | What's shipped + the next 5 things I'd build |
| **This file** | How to run, test, and deploy |

Live URL: **https://agentup-iag.pages.dev** — open in Chrome/Edge for the best voice experience. Press **`Ctrl + \``** (or **`⌘ + \``** on Mac) to open the developer HUD and see the LLM pipeline in real time.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Astro 5 + React islands | Static-first, minimal JS shipped, React only where interactivity is needed |
| Styling | Tailwind CSS 3 | Design-system consistency, dark-mode ready |
| Charts | Recharts | Interactive charts, tree-shakeable, dashboard-only |
| Backend | Cloudflare Pages Function | Serverless edge, hides API key, KV rate-limit |
| LLM | Claude Sonnet 4.6 (Anthropic direct) | High-quality roleplay + scoring in a single model |
| Persistence | Browser `localStorage` | Per PRD Section 4 — no server-side auth in scope |
| Voice | Native Web Speech API | Zero server-side STT/TTS cost; browser-native |
| Deploy | Cloudflare Pages (free) | Free tier, edge global, single command |

---

## Architecture

```
Browser (Astro islands)
  ├── localStorage (cases, sessions, streak)
  ├── Web Speech API (mic + TTS for Call channel)
  └── fetch("/api/claude")  ──┐
                              ▼
Cloudflare Pages Function  (functions/api/claude.ts)
  ├── Origin allowlist
  ├── Per-IP daily KV rate-limit (200 req/IP/day)
  ├── Hides ANTHROPIC_API_KEY
  └── ──▶  Anthropic API  (claude-sonnet-4-6)
              modes:
                roleplay → returns 1 customer turn
                score    → returns strict JSON scorecard
```

---

## Local development

```bash
# 1. Install dependencies (Node 20+ recommended)
npm install

# 2. Provide your Anthropic API key locally
cp .env.example .dev.vars
# ...then edit .dev.vars with your ANTHROPIC_API_KEY

# 3. Start dev server (Astro only — no API function)
npm run dev

# 4. Or start with the Pages Function proxying to Claude
npm run build && npm run pages:dev
```

Then open **http://localhost:4321** (astro dev) or **http://localhost:8788** (wrangler pages dev).

---

## Testing

The build is covered by seven tiers of tests. All test scripts live under `tests/`.

| Tier | Command | What it asserts |
|---|---|---|
| **Unit** | `npm test` | `extractJsonObject` shapes, `isScorecard` validation, seeded RNG, streak logic, score aggregation, PII redaction (Indian formats), telemetry cost math, chunked-speech buffering |
| **Integration** | `npm test` | Pages Function routing, prompt assembly, mock-Anthropic happy path + error taxonomy, KV rate-limit boundary, wildcard-origin allowlist, payload-size cap (413), Gemini fallback chain, model-answer mode |
| **E2E (Playwright)** | `npx playwright test` | Full 3-case session in the browser, custom-case creation, filters, dashboard persistence |
| **Acceptance gate** | `py tests/acceptance_agentup.py` | Every route present in `dist/`, no banned models leaked, no hardcoded keys, bundle-size cap, default-cases shape valid |
| **Front-door synthetic** | `bash tests/front_door_agentup.sh https://<your-domain>` | Live URL responds; all 3 pages return h1; live Claude scoring roundtrip returns valid JSON |
| **Negative-test battery** | `bash tests/negative_agentup.sh https://<your-domain>` | 23 adversarial checks (origin injection, malformed body, HTTP method abuse, prompt injection, XSS content, 100KB payload, key leakage) |
| **G-Eval scoring** | `py tests/g_eval_scoring.py --base https://<your-domain>` | Score-consistency (variance across N runs on same transcript) + golden-set discrimination (A+ transcript ≥ 80, fail transcript ≤ 45) |

Full local run:

```bash
npm test              # 49 unit + integration tests
npm run test:e2e      # 6 Playwright E2E tests (spins up dev server)
npm run build && py tests/acceptance_agentup.py
```

---

## Deploy to Cloudflare Pages (free tier)

One-time setup:

```bash
# 1. Create the Pages project (interactive login on first run)
npx wrangler login
npx wrangler pages project create agentup-iag --production-branch main

# 2. Create the KV namespace for rate-limiting
npx wrangler kv namespace create AGENTUP_KV
# → copy the returned id into wrangler.toml's kv_namespaces block

# 3. Set the Anthropic API key as a production secret (never committed)
npx wrangler pages secret put ANTHROPIC_API_KEY --project-name agentup-iag
# ...paste your key when prompted
```

Every deploy:

```bash
npm run build && npx wrangler pages deploy dist --project-name agentup-iag
```

---

## Notes on trade-offs vs. the case study spec

- **Model** — the case study proposed Haiku for roleplay + Sonnet for scoring. This build uses **Sonnet for both**. Sonnet cost on a full 3-case session (5 turns × 3 + 3 scoring calls) is ~€0.10, and quality on multi-turn empathy dialogue is materially higher. The wrapper is model-agnostic — one constant to flip.
- **Vertex vs Anthropic direct** — direct Anthropic API avoided a paid GCP-billing setup for this exercise. The wrapper contract (fetch + JSON) is identical; switching to Vertex is one URL + credential swap.
- **Persistence** — localStorage only per PRD Section 4 (no auth in scope). Clearing browser storage resets the app; a server-side variant would need a user table + auth flow.

---

## File map

```
functions/api/claude.ts      # Pages Function (roleplay + score, KV rate-limit)
src/pages/                   # 3 routes (index / cases / dashboard)
src/components/              # React islands (Training / Cases / Dashboard)
src/lib/                     # Storage, session logic, API client, speech hooks
src/data/default-cases.json  # 5 seed scenarios
tests/unit/                  # 35 vitest tests
tests/integration/           # 14 vitest tests
tests/e2e/                   # 6 Playwright specs
tests/acceptance_agentup.py  # Offline structural gate
tests/front_door_agentup.sh  # Live-URL synthetic
wrangler.toml                # CF Pages config (secrets NOT stored here)
```
