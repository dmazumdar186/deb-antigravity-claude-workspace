# Directive: Claude Code plugins (the five `/jev on` extras)

## Goal

Reproducibly enable the five external Claude Code plugins the operator added on top of the
workspace mods, and keep a trust record for each. Sits beside `directives/infrastructure/jev.md`.

## Inputs

- `uv` on PATH (fetches Python; already present in cloud + local).
- Network access to github.com and the plugins' package sources.
- Optional: an Anthropic/OpenRouter key if you want SkillSpector's full LLM scan (static scan needs none).

## Tools / Scripts

- `python3 execution/infrastructure/jev_router.py on|status`
- `skillspector scan|mcp` (CLI, `uv tool`)
- `agent-reach setup|add|login|doctor` (CLI, `uv tool`)
- `.claude/settings.json` — `extraKnownMarketplaces` + `enabledPlugins`
- `execution/infrastructure/setup_freellmapi.sh`, `setup_pentagi.sh`

## Outputs

- Two plugins (lemo-opuscar, ponytail) loading from `settings.json`.
- Two CLI tools + their skills (`skill-inspector` in repo, `agent-reach` user-level).
- A dated trust record (below) for each scanned plugin.

## What is installed where

| Plugin | Repo | Kind | How it loads |
|---|---|---|---|
| lemo-opuscar | `lemomo-ai/lemo-opuscar` | marketplace `lemolab` → plugin `lemo-opuscar` | `.claude/settings.json` `extraKnownMarketplaces` + `enabledPlugins` |
| ponytail | `DietrichGebert/ponytail` | marketplace `ponytail` → plugin `ponytail` | same |
| skill-inspector (NVIDIA SkillSpector) | `nvidia/skillspector` | **skill copied into repo** `.claude/skills/skill-inspector/` + `skillspector` CLI | skill auto-loads; CLI via `uv tool install` |
| Agent-Reach | `Panniantong/Agent-Reach` | **CLI + user-level skill** | `uv tool install`; `agent-reach setup` links `~/.claude/skills/agent-reach` |
| FreeLLMAPI | `tashfeenahmed/freellmapi` | **self-hosted service** (not a plugin) | `execution/infrastructure/setup_freellmapi.sh` → see `directives/infrastructure/freellmapi.md` |

The seven workspace mods (`jev-router-mod`, `safety-guard-mod`, `done-notify-mod`,
`session-ledger-mod`, `context-meter`, `quota-watch`, `tool-timing`) stay enabled from
marketplace `deb-workspace-mods`. "Turn on all mods" = those seven + the two plugin-shaped extras
above already enabled in `enabledPlugins`.

## Steps — reproduce (cloud session or fresh clone)

```bash
# 1. Jev router on
python3 execution/infrastructure/jev_router.py on

# 2. CLI tools (uv required)
uv tool install 'skillspector[mcp] @ git+https://github.com/NVIDIA/skillspector.git'
uv tool install git+https://github.com/Panniantong/Agent-Reach
agent-reach setup          # installs default channels, links the skill

# 3. lemo-opuscar + ponytail load from settings.json on next session start.
#    First lemo-opuscar run self-bootstraps (node_modules, .venv, Chromium) via its setup.sh.
```

`.claude/settings.json` already carries the marketplaces and `enabledPlugins` entries, so plugins
load automatically; only the CLI tools and `agent-reach setup` are imperative steps.

## Trust record (scanned before enabling, 2026-11-03)

Scanned every bundled skill with `skillspector scan <dir> -r --no-llm`:

- **ponytail** — 6 LOW. Clean.
- **skill-inspector** — 1 LOW. Clean (it is the scanner itself).
- **Agent-Reach** skill — 1 LOW. Clean.
- **lemo-opuscar** — 1 MEDIUM, 1 HIGH. The HIGH (`TM2` command-chaining, `scripts/setup.sh:73`) is a
  **false positive**: `rm -rf .venv` fires only when the venv's interpreter is already broken
  (post-Python-upgrade), gated behind a health check, to rebuild it. Reviewed and accepted.

Re-run the scan before upgrading any of these: `skillspector scan <plugin-skills-dir> -r`.

## Plugin advisor (Jev-graded — never remember which tool to use)

The Jev router doubles as a **plugin advisor** so the operator does not have to remember these
extras exist. Hybrid surfacing (operator decision, 2026-11-03):

- **Non-blocking suggestions** for `agent-reach`, `lemo-opuscar`, `skill-inspector`, `freellmapi`,
  `pentagi`. On each prompt the router asks Jev one extra `choice` (batched into the existing
  tier+skill call) "which ONE capability, if any, materially helps THIS prompt?". A hit ≥
  `advisor_min_confidence` (0.6) surfaces a single `💡 <capability>: <value_add>` line in the
  jev-router-mod band — never a pause, deduped once per session. `ponytail` + `safety-guard` are
  always-on and documented, never suggested.
- **One blocking gate**: `skillspector_gate.py` (`PreToolUse(Bash)`) fires only when a command is
  about to install/clone an **unvetted** skill or plugin (git clone into `.claude/skills`, `cp`/`mv`
  into `.claude/skills|plugins`, `agent-reach add`, plugin enable). It scans the target with
  `skillspector … --no-llm -f json`; HIGH/CRITICAL → `permissionDecision=ask` (operator confirms,
  finding surfaced); below HIGH or unscannable → fail-open note. This is the same SkillSpector trust
  check as the manual pre-install scan above, now automatic.
- Map: `.claude/jev/advisor.json`. Details, CLI (`jev_router.py advise …`,
  `skillspector_gate.py check …`), and validation: `directives/infrastructure/jev.md`.

## Privacy / safety notes

- **Agent-Reach is read-only** (search/read/subtitles/quotes/jobs) and never posts, likes or DMs.
  Login is per-channel and user-driven; it copies an existing browser session rather than asking for
  passwords. Default channels (github, youtube, bilibili, v2ex, web) need no login. Full capability
  table printed by `agent-reach setup --text`.
- **lemo-opuscar** renders films locally (headless Chromium + a Python venv); first run downloads
  deps. No network egress beyond package/browser install and the model calls the agent itself makes.
- **ponytail** adds hooks + a band and an optional per-task ledger/webhook (`userConfig`); the webhook
  is empty by default so nothing leaves the machine unless the operator sets it.

## Edge cases

- Cloud sessions are ephemeral: `uv tool install` + `agent-reach setup` must be re-run each fresh
  container (or scripted in `session-start`). The repo-committed `skill-inspector` skill and the
  `settings.json` plugin entries survive because they are checked in.
- Agent-Reach's skill is template-rendered (`{{VERSION}}`, `{{CHANNEL_TABLE}}`) by its installer — do
  **not** copy its raw `skill/` folder into the repo; run `agent-reach setup` instead.
- SkillSpector's full LLM analysis needs an API key; `--no-llm` (static YARA + heuristics) is enough
  for a pre-install gate and is what the trust record above used.
