# Settings Notes — 2026 Upgrades

Tracks new keys added to `.claude/settings.json` and `.claude/settings.local.json` as part of the workspace 2026 upgrade. Reference for future debugging and rollback.

## 2026-06-11 — Phase 2 workspace upgrade

Added to `.claude/settings.json` `env` block:

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — opt in to Anthropic's Agent Teams feature. Spawns multiple full Claude sessions coordinated by a team lead with a shared mailbox and task list. Distinct from sub-agents (which only report back to the orchestrator); teammates can claim tasks, message each other, and self-coordinate. Requires Claude Code CLI >= 2.1.154. Installed at time of opt-in: 2.1.173.
- `teammateMode=in-process` — render teammate sessions in the same terminal pane (cycle with Shift+Down). Alternative: `tmux` for split-pane.

Hook events for Agent Teams (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) intentionally NOT registered yet. They'll be wired up the first time Agent Teams is used in a real workflow, to avoid registering hook types the CLI may or may not validate strictly.

### Did NOT change in Phase 2

- `model` key in `.claude/settings.json` — at Phase 2 time (2026-06-11) stayed `claude-opus-4-7` because the global TIME-BOUND MODEL POLICY mandated `claude-fable-5[1m]` for Plan Mode. **Updated 2026-06-13:** `~/.claude/settings.json` `model` is now `claude-opus-4-8`. Reason: Plan-mode default per MODEL POLICY in `~/.claude/CLAUDE.md`. Fable 5 / Mythos 5 are no longer available (2026-06-12 US export-control directive). **[SUPERSEDED 2026-08-27 -- Fable 5 is available again and is now the session default; see the 2026-08-27 entry below.]**
- `.claude/settings.local.json` `model` key — file does not exist.

### 2026-08-12 — model sweep to the 5-series (branch `fix/model-sweep-opus5`)

- `.claude/settings.json` and `.claude/settings.local.json` `model` → `claude-opus-5`.
- Briefly set to the `opus[1m]` family alias earlier the same day, then reverted to the
  pinned full name: `~/.claude/rules/model-tier.md` now bans bare aliases in config and
  code, because they resolve differently per provider and drift between Claude Code
  versions. `settings.local.json` does now exist and overrides `settings.json`.
- **Unverified**: whether a bare `claude-opus-5` retains the 1M-context variant that the
  `[1m]` suffix requested. Opus 5 is natively 1M per Anthropic's docs, but Claude Code's
  settings-parser semantics are not documented. Watch for a context-window regression.

### 2026-08-27 -- session default moved to Fable 5

- `~/.claude/settings.json` `model`: `claude-fable-5[1m]` -> `claude-fable-5` (bracket
  alias dropped per the no-alias rule in `~/.claude/rules/model-tier.md`).
- `.claude/settings.json` and `.claude/settings.local.json` `model`: `claude-opus-5` ->
  `claude-fable-5`. Both project files were the reason the user-level Fable pin had no
  effect -- project settings override user settings, and `settings.local.json` overrides
  `settings.json`. Changing only one of the three does nothing.
- The 2026-06-12 export-control suspension of Fable 5 / Mythos 5 is recorded as lifted in
  `~/.claude/CLAUDE.md` and `~/.claude/rules/model-tier.md`. Lifted on operator
  instruction; **verified live later the same day** -- session `9410a201` ran on
  `claude-fable-5` with all three files pinned, no model-access error.
- Fable 5 pricing read off platform.claude.com 2026-08-27: $10 in / $12.50 5m-write /
  $20 1h-write / $1 read / $50 out per MTok. 2x Opus 5, 5x Sonnet 5.
- Agent `.md` `model:` frontmatter accepts full model IDs (same values as `--model`), per
  code.claude.com/docs/en/sub-agents -- the four analysis agents pinned to `claude-fable-5`
  are on documented ground.
- Task-role routing in `execution/` was initially left unchanged, then swept later the same
  day (see the entry below): the judgement tier moved to `claude-fable-5` and the execution
  tier stayed `claude-sonnet-5`.

**Revert (one line):** set `"model": "claude-opus-5"` in `.claude/settings.local.json` --
that file alone wins over the other two, so it is the fastest rollback.


## 2026-09-01 — token-economy sweep (branch `claude/optimize-token-consumption-0svgma`)

Operator was hitting the 5-hour usage cap constantly. Root causes: Fable 5 as the
everywhere-default (usage limits are model-weighted; Fable ≈ 5x Sonnet) and ~15k tokens of
fixed context re-sent on every model call. Changes:

- `.claude/settings.json` `model`: `claude-fable-5` → `claude-sonnet-5`. Fable 5 is now an
  **escalation tier** (`/model claude-fable-5` for architecture/judgement moments), not a default.
- Agent pins: `anneal-reviewer`, `code-reviewer`, `qa` → `claude-sonnet-5`;
  `pipeline-auditor` → `claude-opus-5` (one strong adversarial lens retained).
  `documenter`/`note-taker` unchanged (`claude-sonnet-5`).
- CLAUDE.md cut 21.9k → ~6.3k chars (~4k tokens/turn saved); tables and setup detail moved
  to `directives/README.md` and `docs/reference/enforcement.md`. AGENTS.md/GEMINI.md re-mirrored.
- New always-active rule: `.claude/rules/token-economy.md` (context-rent budget, model
  ladder, in-session hygiene). `always-parallelize.md` condensed 5.7k → 1.6k chars.
- 10 longest skill frontmatter descriptions trimmed to ≤ ~320 chars (skill bodies untouched
  — they only load on invocation).
- `.mcp.json`: removed the `github` server — its ~90 tool schemas load every turn locally,
  and `gh` CLI covers the same operations; cloud sessions get their own GitHub MCP anyway.

~~REQUIRED LOCAL FOLLOW-UP~~ **[SUPERSEDED same day by rev B below — do NOT flip local pins
to Sonnet.]**

### 2026-09-01 rev B — default restored to Fable; savings via delegation, not downgrade

Operator decision: "a Ferrari with the fuel consumption of a Toyota" — the top model must
stay the brain. The Sonnet-default part of the sweep is reversed; everything else stands.

- `.claude/settings.json` `model`: back to `claude-fable-5`. Doctrine is now
  **"Fable thinks, Sonnet works"** (`.claude/rules/token-economy.md`): the orchestrator
  session keeps Fable for planning/architecture/review/judgement and delegates all grunt
  work (exploration, implementation, fan-out) to `claude-sonnet-5` sub-agents. Savings come
  from the fixed-context diet (which is billed at Fable weight every turn, so the ~60% cut
  compounds), delegation of bulk token volume to Sonnet, and session hygiene.
- Agent pins: `pipeline-auditor` → `claude-fable-5` (adversarial verification);
  `code-reviewer` → `claude-opus-5` (review tier); `anneal-reviewer`/`qa` stay
  `claude-sonnet-5` (checklist/test execution); `documenter`/`note-taker` unchanged.
- **No local follow-up needed for model pins** — `~/.claude/settings.json` and
  `.claude/settings.local.json` already say `claude-fable-5`, which is now correct again.
  Optional: add the delegation doctrine ("Fable thinks, Sonnet works") to
  `~/.claude/rules/model-tier.md` so local sessions carry it too.

**Revert rev B:** `"model": "claude-sonnet-5"` in `.claude/settings.local.json` (wins over
the other two files); `git checkout` the two agent `.md` files. Revert the context-diet
parts of the sweep only via git history (`94c6d6e`).

### 2026-09-01 rev C — measurement loop + evidence-based skill archive

- New: `execution/infrastructure/token_usage_report.py` + directive — reports burn by
  model/day, skill invocations, and sub-agent spawns from local transcripts
  (cache-aware pricing, API-price proxy for cap burn). Verified live in the cloud
  container: one session showed 16.6M cache-read tokens — the fixed-context rent this
  sweep targets. Run weekly on the Windows machine per the token-economy rule.
- Archived 4 skills with ZERO references in directives/execution/notes, each a demo or a
  duplicate of a kept skill: `generate-report` (weather demo), `recreate-thumbnails`
  (subset of `thumbnail-generator`), `gmail-inbox` (duplicate of `gmail`),
  `pan-3d-transition` (covered by `video-edit`). Restore: `git mv` back from
  `docs/reference/skills-archive/`. Deeper pruning waits for a month of invocation data
  from the usage report.
- `session-start.sh`: removed the expired job_search_v2 synthetic block (window ended
  2026-06-26); hook re-tested, JSON payload intact.

**Operator checklist — rev D update: items 2 and 3 are now AUTOMATED.**
`session-start.sh` auto-runs the usage digest at most once per 7 days (stamp:
`.tmp/token_usage_last_run`) and surfaces it in the session's opening context, and
auto-flags a `CLAUDE.local.md` over 3KB. Zero action needed for either.

The ONE remaining manual item (an account setting no repo file or tool can change):
detach unused claude.ai connectors. Exact steps: open https://claude.ai/settings/connectors
in a browser → for each connector not used for work (e.g. Spotify; Apollo/Upwork if
outreach is dormant) click its "…"/configure control → Disconnect/Remove. Apollo alone
attaches ~70 tool definitions to every cloud session. Reconnecting later is one click on
the same page.

**DONE 2026-09-01** — operator disconnected Apollo (~70 tools), Spotify, and Upwork;
verified live from the cloud session (their MCP servers dropped mid-session, ~75 tool
definitions gone from every future cloud session). The token-economy sweep (revs A-D) is
now fully closed: no open items.

## 2026-09-01 — Fable 5 → Fable 5.1 migration (branch `claude/migrate-fable-5-1-iemoio`)

Operator-requested migration of the judgement tier to Claude Fable 5.1, framed to make
the "Ferrari with Toyota fuel consumption" doctrine (rev B above) hold harder. Verified
against platform.claude.com (migration guide, prompt-caching pricing, effort docs) and
OpenRouter's live catalogue on 2026-09-01.

- **Why it strengthens the doctrine:** same $10 in / $50 out per MTok as Fable 5, but
  cache reads dropped $1.00 → **$0.25/MTok** (0.025x input — an exception to the usual
  0.1x rule). The fixed always-loaded prefix, re-read at brain weight every orchestrator
  turn, now costs near Sonnet cache-read rates ($0.20). Low effort on Fable 5.1 is also
  often competitive with Opus/Sonnet on $/task. Delegation doctrine unchanged: Sonnet
  still does all grunt work.
- `.claude/settings.json` `model`: `claude-fable-5` → `claude-fable-5-1`.
- Agent pin: `pipeline-auditor` → `claude-fable-5-1`. `code-reviewer` (`claude-opus-5`)
  and the Sonnet agents unchanged.
- `model_registry.LAST_KNOWN_GOOD`: anthropic premium → `claude-fable-5-1`; openrouter
  premium → `anthropic/claude-fable-5.1` (**dot**, not dash — OpenRouter uses dots for
  minor versions; verified live, cache read $0.25 there too). `model_router` `fable`
  alias moved likewise. Old `claude-fable-5` rows KEPT in pricing tables (historical
  transcripts) but no tier resolves to it anymore.
- **Breaking change handled:** forced tool choice (`tool_choice={"type":"tool"|"any"}`)
  returns 400 on `claude-fable-5-1`. Premium-capable call sites in `humanizer.py`,
  `gaia_sourcing/core/providers.py`, and `youtube_video_analyzer.py` were migrated to
  `tool_choice: auto` + an explicit prompt sentence naming the tool + `strict: true`
  (`additionalProperties: false`). Sonnet-pinned call sites untouched.
- CLAUDE.md/AGENTS.md/GEMINI.md Models section, `token-economy.md`,
  `python-hardening.md` rule 4 (cache-read multiplier is model-dependent), directives
  (`model_chooser`, `claude_code_web`, `free_cc_proxy`, `fuzzy_variables`,
  `icp_self_check_loop`, `_TEMPLATE_autoresearch`, `video/youtube_video_analyzer`)
  updated to the new IDs.

**REQUIRED LOCAL FOLLOW-UP (cloud session cannot reach these):** on the Windows machine,
`~/.claude/settings.json` and `.claude/settings.local.json` still pin `claude-fable-5`
and OVERRIDE the repo file (local > project > user). Set both to `claude-fable-5-1`,
and update `~/.claude/rules/model-tier.md` if it names the old ID.

**Revert (one line):** `"model": "claude-fable-5"` in `.claude/settings.local.json`;
`git revert` the migration commit for the code/tier changes. Fable 5 remains served, so
reverting is safe.

## Reverting

To disable Agent Teams: remove the `env` block (or just the two new keys) from `.claude/settings.json`. Restart Claude Code. No other workspace files depend on this opt-in.

## Verification after edit

```powershell
py -c "import json; json.load(open('.claude/settings.json'))"  # should print no errors
claude --version  # should be 2.1.173 or later
```

## Related files

- `.claude/settings.json` — primary config.
- `~/.claude/CLAUDE.md` — global model policy.
- `CLAUDE.md` — workspace Environment section documents the model strategy.
- `.claude/agents/*.md` — per-agent `model:` frontmatter. Should be `claude-fable-5`
  (analysis agents) or `claude-sonnet-5` (mechanical agents) per the role-based routing in
  `~/.claude/rules/model-tier.md`; Haiku is banned. Full IDs, never bare aliases.
