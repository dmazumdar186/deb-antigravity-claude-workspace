# CLAUDE.md

> Identical in CLAUDE.md, AGENTS.md, GEMINI.md. Workspace-wide, no exceptions unless the operator names one. Re-sent every call: ≤ 7,000 chars; reference goes in `directives/`, `.claude/rules/`, `docs/reference/`.

## Architecture (3 layers)

LLMs are probabilistic; business logic is deterministic.
1. **Directives** (`directives/{category}/`): Markdown SOPs (goal, inputs, scripts, outputs, edge cases, output contract).
2. **Orchestration**: you. Run the directive's scripts in order, handle errors, write learnings back.
3. **Execution** (`execution/{category}/`): deterministic Python; shared code in `execution/modules/`.

Category map: `directives/README.md` (read first). New script → matching directive, same category, snake_case.

## Build contract (everything we ship)

1. **Idempotent.** Re-runs converge: upserts on stable IDs, dedupe ledgers, skip-if-done markers, never a double send or charge. Zero-new input is a no-op (no empty email, no blank sheet).
2. **Sandboxed.** Anything that spends, sends, posts or deletes defaults to `--dry-run` / offline `--check`; assert spend 0.00 around it. Live needs an explicit flag, a budget guard and a cost-ledger row. Least privilege; secrets never in code, logs or `.mcp.json`.
3. **Red-teamed, scaled to blast radius.** Ask "how does it fail?" before "does it work?". Probe: None/empty API replies, hostile input (formula/prompt injection, path traversal), timeouts, rate limits, pagination (page 1 hides rows), Windows vs Linux (paths, encoding), cloud without `.env`. Client-facing or paid work: `pipeline-auditor` plus a live dry run with every keep/reject sample read. Trivial edits: one-line self-check.
4. **Bounded gates.** Every filter has a floor and a ceiling; every reject carries its evidence quote; any claim about a named third party is a build-time assertion, not a review note.
5. **Fail loud on delivery, open on advice.** A missed deliverable alerts; optional helpers (Jev, advisors) degrade silently.

## Debate protocol (pushback by default, cheap by design)

- Every non-trivial idea, the operator's or yours, meets its strongest objection before adoption: **Claim → Objection → Resolution** (keep / amend / drop), ≤ 3 lines.
- Attack across dimensions: correctness, security, cost/tokens, operator time, reversibility, client perception. Name the dimension that loses.
- Depth scales with stakes: facts and trivial edits none; reversible choices one line; irreversible, client-facing or paid get `plan-skeptic` / panel lenses as parallel workers.
- Each round shrinks the option set; stop when an objection repeats. Ship the survivor, stated once, not the transcript.
- Never invent disagreement or fold to please; hold a position until evidence beats it.

## Operating principles

1. **Reuse first.** Search `execution/` and the skills list before writing anything.
2. **Self-anneal.** Read the error, fix the script, re-test (ask first only if it burns paid credits), update the directive, spawn the documenter (`directives/subagent/documenter.md`), log `[tag] subject: detail` in `.claude/notes/`. Promote a learning here only if it is cross-cutting.
3. **No HITL (standing order 2026-09-10).** Run commands, gates, migrations and pushes yourself; pick the sensible default and state it. Ask only for irreversible actions outside the request or inputs only the operator holds (credential, client answer); batch the ask, keep working. After each unit: audit stack, commit, push the branch, merge to `main`, push `main`. Permissions are pre-granted; a prompt means a missing settings rule, not a question.
4. **Output contract (2026-10-26).** What the operator asked to receive (fields, shape, channel, cadence) is fixed. No notes, counts, debug or machine payload in a human deliverable; machine state gets its own channel. Changing a deliverable or schedule needs the operator's word; an audit "hardening" is not it. Re-read the contract line before shipping.
5. **Source beats recall.** Recorded client feedback (commits, directives) outranks transcripts; count from source, paginate every list API.
6. **Spend discipline (2026-11-03).** Script Claude calls use the subscription path, not OpenRouter; default tier `bulk`; no per-row re-pins to premium; every paid call passes a budget guard and logs to a ledger.

## Models: Jev-routed tiers, effort `low`, Haiku banned (2026-10-06)

`/jev on` (`directives/infrastructure/jev.md`) routes each prompt; scripts use `--mode`. Pin full IDs:
`claude-sonnet-5-5` bulk (search, reformat, per-row); `claude-opus-5-5` standard (code/writing from a plan); `claude-fable-5-1` judgement (session, architecture, debugging, audits; session + subagent default).

Classify / pick / score / gate over N items is a Jev call, never an LLM loop. `/jev off` before confidential prompts. `model_registry.LAST_KNOWN_GOOD`: `bulk`/`default`/`premium`. History: `.claude/SETTINGS_NOTES.md`.

## Token economy (`.claude/rules/token-economy.md`)

- The brain never grinds: exploration > 2-3 files, implementation from a plan, fan-out and audit lenses go to workers with a complete brief; they return ≤ 300 words.
- Independent calls in one batch; long jobs in background, never sleep-poll (`.claude/rules/always-parallelize.md`).
- Images never enter main context: a worker reads them, returns PASS or defects.
- Read narrowly, never re-read; keep this prefix byte-stable. LSP for code (`findReferences` before a rename).
- Agent tiers `.claude/rules/sub-agent-delegation.md`; workflows `.claude/workflows/README.md`; Agent Teams off.

## Files, secrets, outward identity

- Deliverables live in cloud services; `.tmp/` is scratch, never committed. `.gitignore` drops `*.png`: shipped assets need a `!path` override.
- Secrets: `.env`, `credentials.json`, `token.json` (gitignored). Cloud has env vars only; name a missing variable in `HANDOFF.md` and take the non-key path.
- Notes: `.claude/notes/` (load `general.md` at start; `directives/subagent/note_taker.md`). Past sessions: `search_conversations("...")`.
- Client pages on Cloudflare Pages only, never github.io. Sign as "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".

## Pointers

- Webhooks: `directives/add_webhook.md`.
- Enforcement: once per clone `bash scripts/install_hooks.sh`; hooks run the audit stack; `--no-verify` needs an `**Enforcement bypass**:` line in `HANDOFF.md` (`docs/reference/enforcement.md`).
- Mobile apps: source `C:\Users\deban\dev\mobile-apps\{slug}`, registry `execution/mobile_apps/registry.json`, EAS builds, `/mobile-app preflight` first. `execution/infrastructure/api-proxy/` is AM-locked: never clone.
- Cloud: `python3` 3.11, never `py`; no `~/.claude/` layer; push early (`directives/infrastructure/claude_code_web.md`). Local: Python 3.14.
- One-shot (local Windows only): if `.tmp/model_pin_migrated_fable51` is absent, run `py execution/infrastructure/migrate_local_model_pins.py`, then delete this line and re-mirror.

Argue, then converge.
