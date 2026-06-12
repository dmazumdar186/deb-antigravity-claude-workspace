# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

## Code Intelligence

Prefer LSP over Grep/Glob/Read for code navigation:
- `goToDefinition` / `goToImplementation` to jump to source
- `findReferences` to see all usages across the codebase
- `workspaceSymbol` to find where something is defined
- `documentSymbol` to list all symbols in a file
- `hover` for type info without reading the file
- `incomingCalls` / `outgoingCalls` for call hierarchy

Before renaming or changing a function signature, use
`findReferences` to find all call sites first.

Use Grep/Glob only for text/pattern searches (comments,
strings, config values) where LSP doesn't help.

After writing or editing code, check LSP diagnostics before
moving on. Fix any type errors or missing imports immediately.

## Architecture

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- SOPs written in Markdown, organized by category in `directives/{category}/`
- Categories: `lead_sourcing/`, `enrichment/`, `personalization/`, `gtm_icp_filters/`, `gtm_client_workflows/`, `custom_scrapers/`, `infrastructure/`, `content/`, `image_generation/`, `video/`, `personal_workflows/`, `n8n_workflows/`, `crm_and_pm/`, `google/`, `rag/`, `subagent/`, `mobile_apps/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/custom_scrapers/scrape_skool_course.md` and come up with inputs/outputs and then run `execution/custom_scrapers/scrape_skool_course.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts organized by category in `execution/{category}/`
- Categories mirror directives: `lead_sourcing/`, `enrichment/`, `personalization/`, `gtm_icp_filters/`, `gtm_client_workflows/`, `custom_scrapers/`, `infrastructure/`, `content/`, `image_generation/`, `video/`, `personal_workflows/`, `n8n_workflows/`, `crm_and_pm/`, `google/`, `rag/`, `subagent/`, `mobile_apps/`
- Shared Python modules live in `execution/modules/` (sources, scrapers, enrichers, personalizers, outputs)
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

**4. Check skills before doing work**
Before writing code, researching a topic, or building a workflow from scratch, check if an installed skill already handles it. Skills are pre-built capabilities (slash commands) that encode best practices and save time.

- **Always scan the available skills list** at the start of a task. If a skill matches the domain (e.g., `/cold-email` for cold email, `/clay` for Clay workflows, `/n8n` for n8n, `/list-building` for lead lists), invoke it.
- **Skills take priority** over ad-hoc work. A skill that covers 80% of the task is better than building from scratch.
- **Ask the user before proceeding without a skill.** If a relevant skill exists but doesn't perfectly fit, confirm with the user: "There's a `/skill-name` skill that covers most of this — should I use it, or do you want a custom approach?"
- **Don't modify CLAUDE.md, directives, or execution scripts without checking with the user first.** Propose the change, explain why, and wait for approval.

## Sub-Agent Delegation

Delegate implementation work to sub-agents to keep main context lean. Full tier-selection rules auto-load from `.claude/rules/sub-agent-delegation.md` when editing agents/workflows/directives.

**Three orchestration tiers — choose by parallelism + context-share needs:**

| Pattern | Best for | Parallelism | Context | Cost |
|---|---|---|---|---|
| Sub-agent (`Agent(...)`) | 1–3 independent tasks, tight result loop | 1–3 | Fresh per agent | Low |
| Dynamic Workflow (`ultracode:`) | 5–16+ independent fan-out tasks, long jobs, runs in background | up to 16 concurrent, 1000 total | Out-of-process | Low–medium (use Haiku 4.5 workers) |
| Agent Team (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) | Long-running parallel sessions with shared task list + peer messaging | N teammates | Each has own context, shared mailbox | Medium–high |

See `.claude/workflows/README.md` for Dynamic Workflows triggers and `.claude/SETTINGS_NOTES.md` for Agent Teams enablement notes.

The global `plan-skeptic` skill at `~/.claude/skills/plan-skeptic/SKILL.md` remains the source of truth for adversarial plan review — no workspace-local `.claude/agents/plan-skeptic.md` exists or should be added (avoids parallel definitions).

**Parallel sub-agents:** When tasks are independent, spawn multiple sub-agents in a single message.

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. **Call the Documenter agent** (see `directives/subagent/documenter.md`) to update the relevant directive
5. System is now stronger

**Documenter Agent:** After updating any script in `execution/`, spawn a sub-agent to sync directives:
```
Task(subagent_type="general-purpose", description="Document script changes",
     prompt="Read directives/subagent/documenter.md and follow its instructions. Script updated: [name]. Changes: [description]")
```

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/{category}/` - Python scripts organized by category
- `directives/{category}/` - SOPs in Markdown organized by category
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Category subfolders (same for both directives/ and execution/):**
| Category | Purpose |
|----------|---------|
| `lead_sourcing/` | Finding leads — local business scrapers, Google Maps, Instagram, Apollo, Exa |
| `enrichment/` | Adding data to leads — email finding, verification, contact enrichment, domain checks |
| `personalization/` | Cold email copy & delivery — personalization, foundational copy, Instantly, GHL |
| `gtm_icp_filters/` | ICP research, lead qualification, signal scoring, filtering, buying signals |
| `gtm_client_workflows/` | Client-specific GTM pipelines (agent_gtm, bret_gtm, ecommerce_gtm) |
| `custom_scrapers/` | Generic scraping tools — Skool, browser automation, sitemap parser, Perplexity, SearXNG |
| `infrastructure/` | VPS deployment, Cloudflare workers, LLM hosting, fine-tuning, backup scripts |
| `content/` | Text processing — humanizer, PDF generation, diagrams, spam checker |
| `image_generation/` | Thumbnail creation, image assets |
| `video/` | Video analysis, YouTube downloads, transcripts, channel research |
| `personal_workflows/` | Personal automations — morning briefing, iMessage, email categorizer |
| `n8n_workflows/` | n8n workflow builder, API, dynamic generators |
| `crm_and_pm/` | CRM & project management — ClickUp, Typeform |
| `google/` | Google Workspace integrations (Gmail, Calendar, Meet, Sheets, Docs) |
| `rag/` | Retrieval-augmented generation, conversation memory |
| `subagent/` | Internal agent workflows (note_taker, documenter, reviewer) |
| `mobile_apps/` | Mobile app development — Expo + RN scaffolding, EAS Build, TestFlight/Play deploy, AI integration |

**Shared modules** (`execution/modules/` only — no directive equivalent):
| Module | Purpose |
|--------|---------|
| `modules/sources/` | Lead source connectors (Apollo, Exa, Google Maps, CSV import) |
| `modules/scrapers/` | Web scrapers (BBB, Yelp, Yellow Pages, LinkedIn, Reddit, etc.) |
| `modules/enrichers/` | Enrichment plugins (Apollo, Clay, contact, minimal) |
| `modules/personalizers/` | Personalization strategies (full, light, none) |
| `modules/outputs/` | Output formatters (Instantly, SmartLead, CSV) |
| `modules/foundational_copy/` | Voice-of-customer research and copy generation |

### Creating New Directives/Scripts

```
□ Directive: directives/{category}/{name}.md
□ Script: execution/{category}/{name}.py
□ Both use the same {category} subfolder — snake_case names
□ Only create a new category if you have 3+ related files that don't fit existing ones (ask first)
□ Update directives/subagent/documenter.md mapping table if adding new script
```

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Notes & Context Engineering

Full note-taking protocol is in `directives/subagent/note_taker.md`. Summary:
- Notes live in `.claude/notes/` mirroring the source structure (`directives/`, `execution/`, `general.md`).
- Format: `- [tag] Subject: Detail.` Tags: `[preference]`, `[technical]`, `[learned]`, `[pattern]`, `[constraint]`.
- Load `general.md` at session start. Load the note file paired to any directive/script you open.
- Capture when: unexpected error fixed, API constraint found, user preference observed, reusable pattern found.

## Conversation Memory (Long-term RAG)

Past conversations are automatically captured to a RAG collection on `/clear` or logout. **Use this to recall prior discussions.**

**When to search:**
- Hitting an error you might have solved before
- Working on a file/feature you've touched in past sessions
- User references "that thing we did" or "remember when"
- Starting work on a familiar system (auth, API, specific integrations)

**How to search:**
```
search_conversations("how did we fix the auth bug")
search_conversations("what approach for the webhook system")
```

**What's captured:** Key exchanges only—user questions, your explanations, decisions, learnings. Tool outputs and code dumps are filtered out.

## Cloud Webhooks (Modal + Cloudflare Workers)

The system supports event-driven execution via **Modal webhooks** and **Cloudflare Workers**. Each webhook maps to exactly one directive with scoped tool access.

- **Modal** — Python-based serverless functions. Best for heavy compute, long-running tasks, and anything that needs the full Python execution environment.
- **Cloudflare Workers** — Edge-deployed JS/TS workers. Best for low-latency endpoints, lightweight transformations, and globally distributed routing.

**When user says "add a webhook that...":**
1. Read `directives/add_webhook.md` for complete instructions
2. Create the directive file in `directives/`
3. Choose runtime: Modal (Python, heavy compute) or Cloudflare Workers (edge, low-latency)
4. **Modal path:** Add entry to `execution/webhooks.json`, deploy with `modal deploy execution/modal_webhook.py`
5. **Cloudflare path:** Create/update worker in `execution/infrastructure/`, deploy with `wrangler deploy`
6. Test the endpoint

**Key files:**
- `execution/webhooks.json` - Webhook slug → directive mapping (Modal)
- `execution/modal_webhook.py` - Modal app (do not modify unless necessary)
- `execution/infrastructure/` - Cloudflare Workers scripts
- `directives/add_webhook.md` - Complete setup guide

## Python Hardening

Python hardening rules (subprocess encoding, threading locks, LLM path validation, cache-aware pricing, bare-except) auto-load from `.claude/rules/python-hardening.md` when editing `.py` files. Reference implementation: `C:\Users\deban\dev\anneal\src\anneal\`.

## Mobile App Development (Hybrid Workspace)

Directives and execution scripts for mobile apps live in this workspace under `directives/mobile_apps/` and `execution/mobile_apps/`. **Actual app source code lives in separate per-app repos** at `C:\Users\deban\dev\mobile-apps\{app-slug}\`, cloned from `C:\Users\deban\dev\mobile-apps\_template\`.

- **Registry**: `execution/mobile_apps/registry.json` is the single source of truth tracking every app (slug, repo path, bundle IDs, EAS project ID, last build SHA, /api/health URL, Play tester gate state).
- **Builds**: all iOS/Android builds go through **EAS Build (cloud)** — no Xcode / Mac required (user is on Windows).
- **Preflight required**: always run `/mobile-app preflight` before starting a new app. Phase 4-5 are gated on `APPLE_ENROLLMENT_STATUS=active`.
- **Template versioning**: pinned per-app in `.template-version`. Do not auto-upgrade existing apps when the template changes.
- **AM-locked path**: `execution/infrastructure/api-proxy/` is locked under the Accessory Masters handoff (`CLAUDE.local.md`). The mobile_apps Phase 4 Worker is scaffolded from scratch via `wrangler init <slug>-api --yes` — never cloned from api-proxy.
- **Anneal audit**: after each phase, the `/mobile-app` skill runs `py -m anneal.cli classic --diff-file <patch> --repo <app-repo>` (phases 1-3) or `py -m anneal.cli adversarial <base-ref> --repo <app-repo>` (phases 4-5) from `C:\Users\deban\dev\anneal\`. Adversarial mode does NOT accept `--diff-file`.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

## Environment

- Python: 3.14
- Default session model: `claude-opus-4-7` (orchestration) until 2026-06-21; revisit after Fable-5 plan-mode policy expires.
- Plan Mode reasoning: `claude-fable-5[1m]` until 2026-06-21 23:59 (global rule from `~/.claude/CLAUDE.md`).
- Implementation / exploration sub-agents: `claude-sonnet-4-6` (default for Agent calls without model override).
- High-volume fan-out workers (Dynamic Workflows / agent teams of N parallel workers): `claude-haiku-4-5`.
- Per-agent model override: `model:` frontmatter in `.claude/agents/*.md`.
- Claude Code CLI: 2.1.173+ (Dynamic Workflows + Agent Teams enabled via `.claude/settings.json` `env` block).
