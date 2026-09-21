# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Agent Instructions

> Mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.
> **Keep this file lean.** It is re-sent with every model call. Reference material lives in `directives/`, `.claude/rules/`, and `docs/reference/`, loaded on demand — never inline it here. Budget: ≤ 7,000 characters. Rationale: `.claude/rules/token-economy.md`.

## Architecture (3 layers)

LLMs are probabilistic; business logic is deterministic. This system separates them:

1. **Directives** (`directives/{category}/`) — SOPs in Markdown: goals, inputs, tools/scripts, outputs, edge cases. Instructions like you'd give a mid-level employee.
2. **Orchestration** — you. Routing only: read the directive, call execution scripts in order, handle errors, ask when ambiguous, update directives with learnings. Never scrape/process by hand when a script exists.
3. **Execution** (`execution/{category}/`) — deterministic Python scripts. Shared modules in `execution/modules/`. Secrets in `.env` (gitignored).

Why: 90% accuracy per manual step = 59% over 5 steps. Push complexity into deterministic code.

Category map (identical subfolders for `directives/` and `execution/`): **`directives/README.md`** — read before creating any script or directive. New script → matching directive, same category, snake_case. New category only with 3+ related files, ask first.

## Operating principles

1. **Check for existing tools first** — search `execution/` per your directive before writing a script.
2. **Check skills** — scan the available-skills list at task start; a matching skill beats ad-hoc work.
3. **Self-anneal when things break** — read the error, fix the script, re-test (ask first if it burns paid credits), update the directive, then spawn the documenter sub-agent (`directives/subagent/documenter.md`).
4. **Directives are living documents** — update them with API limits, timing, edge cases; say so in the commit.
5. **No HITL, ever (operator standing order, 2026-09-10).** Never ask the operator to do, decide, approve, or paste anything until every option is exhausted: run the commands, gates, migrations and pushes yourself; pick the sensible default and state it; retry, route around, or build the missing piece. Ask only when the action is irreversible and outside the request, or only the operator holds the input (a credential, a client's answer); batch the ask and keep working. After every completed unit of work: run the audit stack, commit, and push (branch and main) with admin rights assumed. **Permissions are pre-granted (2026-09-21):** `.claude/settings.json` runs `defaultMode: bypassPermissions`; commits, pushes, PRs, installs, deploys and tests need no prompt. If a prompt still appears, the fix is a settings rule, never a question to the operator.
6. **Token economy** — main context stays lean; delegate; effort, not model, is the cost dial. Full rule: `.claude/rules/token-economy.md`.

## Models — all Fable (set 2026-09-21)

- **Brain: `claude-fable-5-1`** — session default. Plans, architects, decides, reviews diffs, delegates. It does **not** grind: exploration, implementation from an approved plan, scraping, formatting and fan-out go to worker sub-agents. Every main-session token is a judgement token. Keep the auto-loaded prefix byte-stable so 5.1 cache reads ($0.25/MTok) stay cheap.
- **Workers: `claude-fable-5`** (same $10/$50 as 5.1; Sonnet workers judged too weak 2026-09-21). All sub-agents, Dynamic Workflow workers, execution scripts' default tier, mechanical agents and checklist audits. Mechanical work at `effort: low`, implementation `medium`; only the brain and `pipeline-auditor` (`claude-fable-5-1`) run high.
- Sonnet/Opus/Haiku are not used. Pin full model IDs, never aliases. History + reverts: `.claude/SETTINGS_NOTES.md`. In `execution/`, tiers resolve via `model_registry.LAST_KNOWN_GOOD` (`'default'` = Fable 5; `'premium'` = Fable 5.1).

## Sub-agents & parallelism

- Delegate multi-file exploration and implementation to sub-agents with a complete brief; keep only conclusions in main context. Tier table: `.claude/rules/sub-agent-delegation.md`. Dynamic Workflows (cheapest fan-out): `.claude/workflows/README.md`. Agent Teams are off by default (`.claude/SETTINGS_NOTES.md`).
- Independent work fires concurrently in one tool-call batch; long verification goes `run_in_background: true`. Rule: `.claude/rules/always-parallelize.md`.
- Adversarial plan review: global `plan-skeptic` skill (`~/.claude/skills/plan-skeptic/SKILL.md`); no workspace copy.

## Code navigation

Prefer LSP (`goToDefinition`, `findReferences`, `workspaceSymbol`, `hover`) over Grep/Glob/Read for code; `findReferences` before any rename. Grep/Glob for text/config only. Fix LSP diagnostics immediately after edits.

## Files & memory

- **Deliverables live in cloud services**; local files are processing-only. `.tmp/` holds intermediates — never committed.
- Secrets: `.env`, `credentials.json`, `token.json` (gitignored).
- Notes: `.claude/notes/` mirrors the source tree; load `general.md` at session start; protocol in `directives/subagent/note_taker.md`.
- Past-conversation RAG: `search_conversations("...")` for a familiar error, file, or "that thing we did".

## Webhooks

"Add a webhook that…" → `directives/add_webhook.md`. Modal (Python): `execution/webhooks.json`, `modal deploy execution/modal_webhook.py`. Cloudflare Workers (edge): `execution/infrastructure/`, `wrangler deploy`.

## Enforcement

Once per clone: `bash scripts/install_hooks.sh`. Pre-commit blocks untracked source under deploy dirs; pre-push blocks HIGH/CRITICAL SAST findings; a Stop hook flags "done" claims without the audit stack. `--no-verify` requires an `**Enforcement bypass**:` line in `HANDOFF.md`. Details: `docs/reference/enforcement.md`.

## Mobile apps

Directives/scripts live here; app source in per-app repos at `C:\Users\deban\dev\mobile-apps\{slug}`. Registry: `execution/mobile_apps/registry.json`. Builds via EAS cloud. Run `/mobile-app preflight` before any new app. `execution/infrastructure/api-proxy/` is AM-locked (`CLAUDE.local.md`) — never clone it.

## Cloud sessions (claude.ai/code)

Use `python3`/`python`, never `py`. Secrets come from the environment, not `.env`. No `~/.claude/` layer in cloud — this CLAUDE.md + `.claude/rules/` are the contract. Push branches early. Setup: `directives/infrastructure/claude_code_web.md`.

## Environment

- Python 3.14 local, 3.11 cloud. Claude Code CLI 2.1.173+. Python hardening rules auto-load for `.py` files.
- Model-access errors: revert per `.claude/SETTINGS_NOTES.md`.
- One-shot (local Windows only): if `.tmp/model_pin_migrated_fable51` is absent, run `py execution/infrastructure/migrate_local_model_pins.py`, then delete this line and re-mirror.

Be pragmatic. Be reliable. Self-anneal.
