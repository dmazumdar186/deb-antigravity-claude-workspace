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

## Sub-Agent Delegation (Context Preservation)

To keep the main conversation lean and preserve context, delegate implementation work to sub-agents.

**Always spawn a sub-agent for:**
- Writing or modifying code (more than trivial changes)
- Exploring unfamiliar parts of the codebase
- Running tests and fixing failures iteratively
- Multi-file changes or refactors
- Any task that requires reading many files

**Keep in main context:**
- Planning and user clarification
- Final summaries and reporting
- Quick single-file lookups
- Decision-making and routing

**Sub-agent pattern:**
```
Task(
  subagent_type="general-purpose",
  description="[3-5 word summary]",
  prompt="[Detailed task with all context needed. Include: what to do, which files/directories, expected output format, any constraints.]"
)
```

**Example workflow:**

User: "Add a logout button to the navbar"

1. **Main context (you):** Plan the approach, identify navbar location
2. **Sub-agent:** Read navbar component, implement button, handle click event, test
3. **Main context (you):** Report completion with file paths changed

**Why this matters:** Sub-agents get fresh context windows. Heavy code exploration and writing happens there, then results return as concise summaries. Main conversation stays focused on orchestration.

**Parallel sub-agents:** When tasks are independent, spawn multiple sub-agents in a single message:
```
# Good: parallel execution
Task(subagent_type="general-purpose", description="Update frontend", prompt="...")
Task(subagent_type="general-purpose", description="Update backend", prompt="...")
```

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

When creating a new workflow, directive, or execution script:

**1. Choose the right category:**
- Review the category table above and pick the best fit
- Lead generation pipeline? → `lead_sourcing/`
- Adding emails/contacts/data to existing leads? → `enrichment/`
- Cold email copy, personalization, sending? → `personalization/`
- ICP research, scoring, filtering? → `gtm_icp_filters/`
- Client-specific end-to-end GTM pipeline? → `gtm_client_workflows/`
- Generic web scraping or research tool? → `custom_scrapers/`
- Server/cloud/LLM infrastructure? → `infrastructure/`
- CRM or project management tool? → `crm_and_pm/`
- Internal agent tools (like documenter, reviewer) go in `subagent/`

**2. When to create a new category:**
- Only create a new category folder if you have 3+ related files that don't fit existing categories
- Ask the user before creating a new category
- New categories should be broad enough to accommodate future growth

**3. Naming conventions:**
- Use `snake_case` for all filenames
- Prefix with the domain when helpful for discoverability (e.g., `slack_messenger.md`, `slack_channel_manager.md`)
- Directive and script names should match when possible (e.g., `directives/google/gmail.md` ↔ `execution/google/gmail.py`)

**4. File creation checklist:**
```
□ Directive: directives/{category}/{name}.md
□ Script: execution/{category}/{name}.py
□ Both use the same {category} subfolder
□ Names are descriptive and use snake_case
□ Update directives/subagent/documenter.md mapping table if adding new script
```

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Notes & Context Engineering

Context is fuel for decision-making. Capture it well.

### Note Categories

| Tag | Purpose | Example |
|-----|---------|---------|
| `[preference]` | User wants/style | "User prefers terse output" |
| `[technical]` | API quirks, gotchas | "Sheets API needs RAW valueInputOption" |
| `[learned]` | Discovered via error | "Rate limit is 60/min not 100" |
| `[pattern]` | Reusable approach | "Always check for existing before creating" |
| `[constraint]` | Hard limits | "Max 5000 chars for Modal endpoint" |

### Note Format

Keep notes atomic and scannable:
```
- [tag] Subject: Detail. Source/date if relevant.
```

Good: `- [technical] Google Docs: Use batchUpdate API, not markdown asterisks`
Bad: `- I learned that when working with Google Docs you should use the batchUpdate API instead of trying to use markdown asterisks because they don't render properly`

### Where Notes Live

Notes mirror the source structure for easy lookup:

```
.claude/notes/
├── general.md                          # Cross-cutting learnings
├── directives/
│   └── {category}/
│       └── {directive_name}.md         # Notes for specific directive
└── execution/
    └── {category}/
        └── {script_name}.md            # Notes for specific script
```

**Examples:**
- Working with `directives/n8n_workflows/n8n_workflow_builder.md`? Check `.claude/notes/directives/n8n_workflows/n8n_workflow_builder.md`
- Running `execution/google/gmail.py`? Check `.claude/notes/execution/google/gmail.md`

**Lookup protocol:**
1. When activating a directive, also read its notes file if it exists
2. When running a script, check for notes about that script
3. Always load `general.md` at session start

### When to Capture

Capture a note when you:
1. Hit an unexpected error and fix it
2. Discover an API constraint not in docs
3. Learn a user preference through feedback
4. Find a pattern that worked well

### Context Injection Rules

Not all notes belong in every conversation:
- Load `.claude/notes/general.md` at session start
- When reading `directives/{category}/foo.md`, also read `.claude/notes/directives/{category}/foo.md` if it exists
- When running `execution/{category}/bar.py`, check `.claude/notes/execution/{category}/bar.md` first
- Don't dump everything—relevance > completeness

### Automatic Note Capture

A hook (`.claude/hooks/note-taker.sh`) runs after edits to `directives/` or `execution/` files. It prompts you to update notes if you learned something new. See `directives/subagent/note_taker.md` for the full process.

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

## Universal Python-on-Windows hardening rules

Banked from anneal v0.1 + workspace audit pass (2026-05-25). Apply to every new Python script in `execution/`.

1. **Subprocess encoding** — every `subprocess.run/Popen(text=True)` or `capture_output=True` MUST include `encoding="utf-8", errors="replace"`. Windows cp1252 default crashes on bytes ≥ 0x80 (e.g. 0x9d). The `_readerthread` exception is hard to debug because it's swallowed by `subprocess`.
2. **Threading locks** — any shared mutable state inside `ThreadPoolExecutor`/`threading.Thread` MUST be guarded by `threading.Lock`. GIL protects single reference reads/writes but NOT `+=` (read-modify-write) nor concurrent filesystem writes to the same directory (e.g. `mkdir(exist_ok=True)` is racy across threads writing to a shared output dir).
3. **LLM-supplied path validation** — any filename derived from LLM output or external API MUST be `.resolve()`ed and checked `resolved.is_relative_to(boundary)` before being passed to filesystem ops or subprocesses. Pattern: `if not (worktree / user_path).resolve().is_relative_to(worktree.resolve()): raise ValueError(...)`.
4. **Cache-aware Claude pricing** — pricing tables must include 4 entries per Claude model: `input`, `cache_read` (0.1× input), `cache_write` (1.25× input), `output`. Flat-rate over-estimates 5–10× under prompt caching. Cost-calc must accept all 4 token counts from `response.usage.cache_read_input_tokens`/`cache_creation_input_tokens`/`input_tokens`/`output_tokens`.
5. **Never `except Exception: pass`** without a log line and a comment explaining why it's safe. Bare swallows mask the bugs you most need to see (e.g. an OAuth token refresh failing silently → 24h of broken cron).

**Reference implementation**: `C:\Users\deban\dev\anneal\src\anneal\` has hardened versions of all 5 patterns. Crib from there before writing new code:
- `sast/ruff_runner.py` + `sast/semgrep_runner.py` — subprocess-encoding-safe runners
- `cost.py` — cache-aware pricing
- `runner/sandbox.py` — env-stripped subprocess pattern
- `suppressions/store.py` — threading.Lock around concurrent writes
- `runner/javascript_test_runner.py` / `go_test_runner.py` — path-traversal guard pattern

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
