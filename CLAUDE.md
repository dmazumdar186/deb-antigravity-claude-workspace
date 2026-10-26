# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Agent Instructions

> Mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.
> **Keep this file lean.** It is re-sent with every model call. Reference material lives in `directives/`, `.claude/rules/`, and `docs/reference/`, loaded on demand — never inline it here. Budget: ≤ 7,000 characters. Rationale: `.claude/rules/token-economy.md`.

## Architecture (3 layers)

LLMs are probabilistic; business logic is deterministic. This system separates them:

1. **Directives** (`directives/{category}/`) — SOPs in Markdown: goals, inputs, tools/scripts, outputs, edge cases. Instructions like you'd give a mid-level employee.
2. **Orchestration** — you. Routing only: read the directive, call execution scripts in order, handle errors, ask when ambiguous, update directives with learnings. Never scrape/process by hand when a script exists.
3. **Execution** (`execution/{category}/`) — deterministic Python scripts. Shared modules in `execution/modules/`. Secrets in `.env`.

Category map (identical subfolders for `directives/` and `execution/`): **`directives/README.md`** — read before creating any script or directive. New script → matching directive, same category, snake_case. New category only with 3+ related files, ask first.

## Operating principles

1. **Check for existing tools first** — search `execution/` per your directive before writing a script.
2. **Check skills** — scan the available-skills list at task start; a matching skill beats ad-hoc work.
3. **Self-anneal when things break** — read the error, fix the script, re-test (ask first if it burns paid credits), update the directive, then spawn the documenter sub-agent (`directives/subagent/documenter.md`).
4. **Directives are living documents** — update them with API limits, timing, edge cases; say so in the commit.
5. **No HITL, ever (operator standing order, 2026-09-10).** Never ask the operator to do, decide, approve, or paste anything until every option is exhausted: run the commands, gates, migrations and pushes yourself; pick the sensible default and state it; retry, route around, or build the missing piece. Ask only when the action is irreversible and outside the request, or only the operator holds the input (a credential, a client's answer); batch the ask and keep working. After every completed unit of work: run the audit stack, commit, and push (branch and main) with admin rights assumed. **Permissions are pre-granted (2026-09-21):** `.claude/settings.json` runs `defaultMode: bypassPermissions`; commits, pushes, PRs, installs, deploys and tests need no prompt. If a prompt still appears, the fix is a settings rule, never a question to the operator.
6. **Token economy** — main context stays lean; delegate; low effort everywhere. Full rule: `.claude/rules/token-economy.md`.
7. **Output contract (2026-10-26).** What the operator asked to receive (fields, shape, channel, cadence) is a contract. Never add a note, count, debug dump or machine payload to a human deliverable; machine state gets its own channel. Changing a deliverable or a schedule needs the operator's word; an audit "hardening" is not it. It slips through convenience during fixes: re-read the directive's contract line before shipping.

## Models — Jev-routed tiers (set 2026-10-06)

- **Three tiers, effort `low` everywhere, Haiku banned.** `/jev on` (`directives/infrastructure/jev.md`) runs Jev as a per-prompt router that picks the tier; a directive's `--mode` does the same for scripts. Pin full IDs, never aliases:
  - `claude-sonnet-5-5` (OR `anthropic/claude-sonnet-5.5`) — **bulk/fast**: search, reformat, lookups, bulk per-row work.
  - `claude-opus-5-5` (OR `anthropic/claude-opus-5.5`) — **standard**: routine coding and writing, sub-agent implementation from a plan.
  - `claude-fable-5-1` (OR `anthropic/claude-fable-5.1`) — **judgement**: the main session, architecture, debugging, audits, anything ambiguous. Session default and `CLAUDE_CODE_SUBAGENT_MODEL` default.
- The brain does **not** grind: exploration, implementation from a plan, scraping, formatting and fan-out go to workers with a complete brief; every main-session token is a judgement token. Keep the auto-loaded prefix byte-stable.
- Supersedes "Fable 5.1 only" (2026-09-21). History + reverts: `.claude/SETTINGS_NOTES.md`. In `execution/`, `model_registry.LAST_KNOWN_GOOD` maps `bulk`/`default`/`premium` to the three tiers.

## Sub-agents & parallelism

- Delegate multi-file exploration and implementation to sub-agents; keep only conclusions in main context. Tiers: `.claude/rules/sub-agent-delegation.md`. Workflows (cheapest fan-out): `.claude/workflows/README.md`. Agent Teams off by default.
- Independent work fires in one tool-call batch; long verification runs in background. Rule: `.claude/rules/always-parallelize.md`.
- Adversarial plan review: global `plan-skeptic` skill; no workspace copy.

## Code navigation

Prefer LSP over Grep/Glob/Read for code; `findReferences` before any rename. Grep/Glob for text/config. Fix LSP diagnostics after edits.

## Files & memory

- **Deliverables live in cloud services**; local files are processing-only. `.tmp/` holds intermediates — never committed.
- Secrets: `.env`, `credentials.json`, `token.json` (gitignored).
- Notes: `.claude/notes/` mirrors the source tree; load `general.md` at start; protocol in `directives/subagent/note_taker.md`.
- Past-conversation RAG: `search_conversations("...")` for a familiar error or "that thing we did".

## Webhooks

"Add a webhook that…" → `directives/add_webhook.md` (Modal: `execution/modal_webhook.py`; Cloudflare Workers: `execution/infrastructure/`).

## Enforcement

Once per clone: `bash scripts/install_hooks.sh`. Pre-commit, pre-push (SAST) and Stop hooks enforce the audit stack; `--no-verify` needs an `**Enforcement bypass**:` line in `HANDOFF.md`. Details: `docs/reference/enforcement.md`.

## Mobile apps

Directives/scripts live here; app source in `C:\Users\deban\dev\mobile-apps\{slug}`; registry `execution/mobile_apps/registry.json`; EAS cloud builds; `/mobile-app preflight` before any new app. `execution/infrastructure/api-proxy/` is AM-locked (`CLAUDE.local.md`) — never clone it.

## Cloud sessions (claude.ai/code)

Use `python3`/`python`, never `py`. Secrets come from the environment, not `.env`. No `~/.claude/` layer in cloud — this CLAUDE.md + `.claude/rules/` are the contract. Push branches early. Setup: `directives/infrastructure/claude_code_web.md`.

## Environment

- Python 3.14 local, 3.11 cloud. CLI 2.1.173+. Python hardening rules auto-load for `.py`.
- Model-access errors: revert per `.claude/SETTINGS_NOTES.md`.
- One-shot (local Windows only): if `.tmp/model_pin_migrated_fable51` is absent, run `py execution/infrastructure/migrate_local_model_pins.py`, then delete this line and re-mirror.

Be pragmatic. Reliable. Self-anneal.
