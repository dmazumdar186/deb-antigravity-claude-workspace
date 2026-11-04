# CLAUDE.md

> Identical in CLAUDE.md, AGENTS.md, GEMINI.md. Workspace-wide, no exceptions unless the operator names one. Re-sent every call: ≤ 7,000 chars; reference goes in `directives/`, `.claude/rules/`, `docs/reference/`.

## Architecture (3 layers)

LLMs are probabilistic; business logic is deterministic.
1. **Directives** (`directives/{category}/`): Markdown SOPs (goal, inputs, scripts, outputs, edge cases, output contract).
2. **Orchestration**: you. Run the directive's scripts in order, handle errors, write learnings back.
3. **Execution** (`execution/{category}/`): deterministic Python; shared code in `execution/modules/`.

Category map: `directives/README.md` (read first). New script → matching directive, same category, snake_case.

## Build contract (everything we ship)

1. **Idempotent.** Re-runs converge: upserts on stable IDs, dedupe ledgers, skip-if-done markers, never a double send or charge. Zero-new input is a no-op.
2. **Sandboxed.** Anything that spends, sends, posts or deletes defaults to `--dry-run` / offline `--check`; assert spend 0.00 around it. Live needs an explicit flag, a budget guard and a cost-ledger row. Least privilege; secrets never in code, logs or `.mcp.json`.
3. **Red-teamed by default.** Every system, outward message or deliverable gets a full adversarial audit (`pipeline-auditor` + parallel lens workers returning verdicts). Exempt only pure reads and no-logic edits (typo, format); "looks trivial" is not an exemption. Probe: None/empty replies, hostile input (formula/prompt injection, path traversal), timeouts, rate limits, pagination, re-runs, Windows vs Linux, cloud without `.env`.
4. **Gated.** Outward text ships only via `/redteam`: every name, figure, date, term and quote traced to a source line; 4 blind lenses PASS on the exact text. A hook denies unrecorded Gmail sends.
5. **Bounded gates.** Every filter has a floor and a ceiling; every reject carries its evidence quote; any claim about a named third party is a build-time assertion, not a review note.
6. **Fail loud on delivery, open on advice.** A missed deliverable alerts; helpers (Jev) degrade silently.

## Debate protocol (pushback by default, cheap by design)

- Every non-trivial idea, the operator's or yours, meets its strongest objection before adoption: **Claim → Objection → Resolution** (keep / amend / drop), ≤ 3 lines.
- Attack on every axis: correctness, security, cost, operator time, reversibility, client perception.
- Debate depth scales with stakes (the audit does not): facts none; reversible choices one line; irreversible, client-facing or paid get `plan-skeptic` / panel lenses.
- Each round shrinks the options; stop when an objection repeats; ship only the survivor.
- Challenged? Re-check the source, answer with evidence (`Verified:` / `Corrected:`). Never "you're right", apology or folding to please.

## Operating principles

1. **Reuse first.** Search `execution/` and the skills list before writing anything.
2. **Self-anneal.** Read the error, fix the script, re-test (ask first only if it burns paid credits), update the directive, spawn the documenter (`directives/subagent/documenter.md`), log `[tag] subject: detail` in `.claude/notes/`. Promote a learning here only if it is cross-cutting.
3. **No HITL (standing order 2026-09-10).** Run commands, gates, migrations and pushes yourself; pick the sensible default and state it. Ask only for irreversible actions outside the request or inputs only the operator holds (credential, client answer); batch the ask, keep working. After each unit: audit stack, commit, push the branch, merge to `main`, push `main`. Permissions are pre-granted; a prompt means a missing settings rule, not a question.
4. **Output contract (2026-10-26).** What the operator asked to receive (fields, shape, channel, cadence) is fixed. No notes, counts, debug or machine payload in a human deliverable; machine state gets its own channel. Changing a deliverable or schedule needs the operator's word; an audit "hardening" is not it. Re-read the contract line before shipping.
5. **Source beats recall.** Recorded client feedback (commits, directives) outranks transcripts; count from source, paginate every list API.
6. **Spend discipline (2026-11-03).** Script Claude calls use the subscription, not OpenRouter; default `bulk`; no per-row premium re-pin; paid calls pass a budget guard and log to a ledger.

## Models: Jev-routed tiers, effort `low`, Haiku banned (2026-10-06)

`/jev on` (`directives/infrastructure/jev.md`) routes each prompt; scripts use `--mode`. Pin full IDs:
`claude-sonnet-5-5` bulk (search, reformat, per-row); `claude-opus-5-5` standard (code/writing from a plan); `claude-fable-5-1` judgement (session, architecture, debugging, audits; session + subagent default).

Classify / pick / score / gate over N items is a Jev call, never an LLM loop. `/jev off` before confidential prompts. `model_registry.LAST_KNOWN_GOOD`: `bulk`/`default`/`premium`. History: `.claude/SETTINGS_NOTES.md`.

## Delegation & tokens (`.claude/rules/token-economy.md`, `always-parallelize.md`)

- **Decompose, then fan out.** Every task starts as a dependency list; independent units run as parallel sub-agents in one batch (disjoint files, `isolation: worktree` for writers), fully briefed, returning ≤ 300 words. The main session plans, judges, merges; never grinds. Inline only for one step of ≤ 3 tool calls. Images only via workers.
- Background long jobs, never sleep-poll. LSP for code (`findReferences` before a rename).
- Tiers `.claude/rules/sub-agent-delegation.md`; workflows `.claude/workflows/README.md`; Agent Teams off.

## Files, secrets, outward identity

- Deliverables live in cloud services; `.tmp/` is scratch, never committed. `.gitignore` drops `*.png`: shipped assets need a `!path` override.
- Secrets: `.env`, `credentials.json`, `token.json` (gitignored). Cloud has env vars only; name a missing variable in `HANDOFF.md` and take the non-key path.
- Notes: `.claude/notes/` (load `general.md` at start; `directives/subagent/note_taker.md`). Past sessions: `search_conversations("...")`.
- Client pages on Cloudflare Pages only, never github.io. Sign as "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".

## Pointers

- Enforcement: once per clone `bash scripts/install_hooks.sh`; hooks run the audit stack; `--no-verify` needs an `**Enforcement bypass**:` line in `HANDOFF.md` (`docs/reference/enforcement.md`).
- Mobile apps: source `C:\Users\deban\dev\mobile-apps\{slug}`, registry `execution/mobile_apps/registry.json`, EAS builds, `/mobile-app preflight` first. `execution/infrastructure/api-proxy/` is AM-locked: never clone.
- Cloud: `python3` 3.11, never `py`; no `~/.claude/` layer; push early (`directives/infrastructure/claude_code_web.md`).
- One-shot (local Windows only): if `.tmp/model_pin_migrated_fable51` is absent, run `py execution/infrastructure/migrate_local_model_pins.py`, then delete this line and re-mirror.

Argue, then converge.
