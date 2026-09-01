# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Agent Instructions

> Mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.
> **Keep this file lean.** It is re-sent with every model call, every turn, every session. Reference material lives in `directives/`, `.claude/rules/`, and `docs/reference/` and is loaded on demand — never inline it back here. Budget: ≤ 7,000 characters. Full rationale: `.claude/rules/token-economy.md`.

## Architecture (3 layers)

LLMs are probabilistic; business logic is deterministic. This system separates them:

1. **Directives** (`directives/{category}/`) — SOPs in Markdown: goals, inputs, tools/scripts, outputs, edge cases. Natural-language instructions like you'd give a mid-level employee.
2. **Orchestration** — you. Intelligent routing only: read the directive, call execution scripts in the right order, handle errors, ask when ambiguous, update directives with learnings. You don't scrape/process by hand when a script exists.
3. **Execution** (`execution/{category}/`) — deterministic Python scripts. Shared modules in `execution/modules/`. Secrets in `.env` (gitignored).

Why: 90% accuracy per manual step = 59% over 5 steps. Push complexity into deterministic code; you focus on decisions.

Category map (identical subfolders for `directives/` and `execution/`): **`directives/README.md`** — read it before creating any new script or directive. New script → matching directive, same category, snake_case. New category only with 3+ related files, ask first.

## Operating principles

1. **Check for existing tools first** — search `execution/` per your directive before writing a script.
2. **Check skills** — scan the available-skills list at task start; a matching skill beats ad-hoc work. If the fit is imperfect, confirm with the user before going custom.
3. **Self-anneal when things break** — read the error, fix the script, re-test (ask first if it burns paid credits), update the directive, then spawn the documenter sub-agent (`directives/subagent/documenter.md`).
4. **Directives are living documents** — update them with API limits, timing, edge cases. Never create or overwrite a directive without asking.
5. **Don't modify CLAUDE.md, directives, or execution scripts without user approval** — propose, explain, wait.
6. **Token economy** — main context stays lean; delegate exploration; escalate model tier only deliberately. Full rule: `.claude/rules/token-economy.md`.

## Models (token-economy tiering — set 2026-09-01)

- **Default / driving tier: `claude-sonnet-5`** ($2/$10 MTok). Session default, execution scripts' default tier, fan-out workers, mechanical agents (documenter, note-taker), and most audit agents.
- **Escalation / judgement tier: `claude-fable-5`** ($10/$50 — 5x Sonnet, 2x Opus). **Not a default anywhere.** Switch deliberately with `/model claude-fable-5` for architecture decisions, debugging that has resisted one Sonnet attempt, or high-stakes analysis — then switch back.
- **Adversarial audit: `claude-opus-5`** — pinned only in `.claude/agents/pipeline-auditor.md` (the independent verification lens).
- Haiku is banned for all project work. Pin full model IDs, never aliases. History + revert one-liners: `.claude/SETTINGS_NOTES.md`. In `execution/`, tiers resolve via `model_registry.LAST_KNOWN_GOOD` (`'default'` = Sonnet; `'premium'` = judgement tier).

## Sub-agents & parallelism

- Delegate multi-file exploration and implementation to sub-agents (fresh context, Sonnet); keep only conclusions in main context. Tier-selection table: `.claude/rules/sub-agent-delegation.md`. Dynamic Workflows: `.claude/workflows/README.md`. Agent Teams: `.claude/SETTINGS_NOTES.md`.
- Independent work fires concurrently in one tool-call batch; long-running verification goes `run_in_background: true`. Full rule: `.claude/rules/always-parallelize.md`.
- Adversarial plan review: global `plan-skeptic` skill (`~/.claude/skills/plan-skeptic/SKILL.md`); no workspace-local copy should exist.

## Code navigation

Prefer LSP (`goToDefinition`, `findReferences`, `workspaceSymbol`, `hover`, call hierarchy) over Grep/Glob/Read for code; run `findReferences` before any rename or signature change. Grep/Glob only for text/config patterns. Check LSP diagnostics after edits; fix type errors immediately.

## Files & memory

- **Deliverables live in cloud services** (Google Sheets/Slides etc.); local files are processing-only. `.tmp/` holds all intermediates — never committed, always regenerable.
- Secrets: `.env`, `credentials.json`, `token.json` (all gitignored).
- Notes: `.claude/notes/` mirrors source tree; load `general.md` at session start; protocol in `directives/subagent/note_taker.md`.
- Long-term RAG over past conversations: `search_conversations("...")` when hitting a familiar error, file, or "that thing we did".

## Webhooks

"Add a webhook that…" → read `directives/add_webhook.md`. Modal (Python, heavy compute): entry in `execution/webhooks.json`, `modal deploy execution/modal_webhook.py`. Cloudflare Workers (edge, low-latency): `execution/infrastructure/`, `wrangler deploy`.

## Enforcement

One-time per clone: `bash scripts/install_hooks.sh`. Pre-commit blocks untracked source under deploy-target dirs; pre-push blocks HIGH/CRITICAL findings from `execution/infrastructure/workspace_sast.py`; an advisory Stop hook (`verdict-table-check.sh`) flags "shipped/done" claims without the mandatory audit stack. Bypassing with `--no-verify` requires an `**Enforcement bypass**:` line in `HANDOFF.md`. Details: `docs/reference/enforcement.md`.

## Mobile apps

Directives/scripts live here; app source lives in per-app repos at `C:\Users\deban\dev\mobile-apps\{slug}`. Registry of record: `execution/mobile_apps/registry.json`. All builds via EAS cloud (no Xcode). Run `/mobile-app preflight` before any new app. `execution/infrastructure/api-proxy/` is AM-locked (`CLAUDE.local.md`) — never clone it for Phase 4 Workers.

## Cloud sessions (claude.ai/code)

Use `python3`/`python`, never `py`. Secrets come from the cloud environment's variables, not `.env`. The user-global `~/.claude/` layer doesn't exist in cloud — this repo's CLAUDE.md + `.claude/rules/` are the contract. Push branches first; uncommitted local work is invisible. Setup: `directives/infrastructure/claude_code_web.md`.

## Environment

- Python 3.14. Claude Code CLI 2.1.173+.
- Python hardening rules auto-load from `.claude/rules/python-hardening.md` when editing `.py` files.
- Fable 5 access was suspended 2026-06-12 (export control) and re-enabled 2026-08-27; if a model-access error appears, revert per `.claude/SETTINGS_NOTES.md`.

Be pragmatic. Be reliable. Self-anneal.
