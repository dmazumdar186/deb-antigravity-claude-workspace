# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Agent Instructions

## 3-Layer Architecture

| Layer | Role | Location |
|-------|------|----------|
| **Directive** | SOPs defining goals, inputs, tools, outputs, edge cases | `directives/` |
| **Orchestration** | You. Read directives, call scripts in order, handle errors, update directives | — |
| **Execution** | Deterministic Python scripts. API calls, data processing, file ops | `execution/` |

Don't do work yourself that a script can do deterministically. Read the directive, prepare inputs, run the script.

## Operating Principles

**1. Check for tools first.** Read `execution/REGISTRY.md` before writing anything new. After creating a script, run `python3 execution/generate_registry.py`.

**2. Self-anneal when things break.** Read error → fix script → test again (confirm with user if paid API) → update directive with what you learned → log change in directive's changelog. Max 3 retries, then stop and report.

**3. Update directives as you learn.** Directives are living documents. Add API constraints, better approaches, edge cases. Don't create/overwrite directives without asking.

**4. Security.** NEVER hardcode secrets. Always `.env` + `os.environ.get()`. Ask user before adding new credentials. Never move secrets out of env files.

**5. Cost control.** Confirm before API calls >$5. For Apify: prioritize Starter-plan-compatible, pay-per-result actors. Default Reddit scraper: `trudax/reddit-scraper-lite`.

**6. Workspace sync.** Synced via GitHub. See `directives/workspace_sync.md`. NEVER commit `.env`, `credentials.json`, `token.json`, `.venv/`.

**7. Maximize parallelism.** Always split independent subtasks into parallel subagents/background tasks. Research, testing, coding — never sequential when parallel is possible.

**8. Self-verification (mandatory).** Every task ends with proof it works. Run the thing, check the output. Cost guard: confirm with user if verification costs >$1. Loop limit: 3 attempts then stop. Never say "done" without proof.

**9. Code review after writing (mandatory).** After creating or significantly modifying any script (`execution/`, `projects/`, `personalizers/`), spawn the `code-reviewer` agent (`.claude/agents/code-reviewer.md`). If it returns FAIL, fix critical issues before reporting done. Then spawn the `qa` agent (`.claude/agents/qa.md`) to test the script. Skip only for trivial edits (comments, typos, single-line changes).

## Memory

Persistent memory is stored in `.claude/memory/` (synced via git across machines). **Do NOT use `~/.claude/` for memory — always save to `.claude/memory/` in the repo.**

- `MEMORY.md` is the index — one line per entry
- Each memory is a separate `.md` file with frontmatter (name, description, type)
- Only check memory when the user asks to recall something or references past work — not every conversation
- When the user says "remember this" or "save this," write to `.claude/memory/`

## File Organization

| Directory | Contents |
|-----------|----------|
| `.claude/memory/` | Persistent memory (synced via git) |
| `directives/` | SOPs (Markdown) |
| `execution/` | Python scripts |
| `campaigns/` | Campaign config JSONs |
| `personalizers/` | Lead personalization modules |
| `credentials/` | Google SA keys, OCI keys. NEVER commit. |
| `data/` | Active data (`reports/`, `exports/`) |
| `blueprints/` | n8n workflows, Make.com blueprints |
| `projects/` | Sub-projects (papaya, chatbot) |
| `assets/` | PDFs, Excel, collateral |
| `docs/` | Strategy docs |
| `.tmp/` | Intermediate files. Never commit. Deletable. |
| `.archive/` | Completed campaign data. Gitignored. |
| `.deprecated/` | Archived/obsolete code |

Local files are for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.).