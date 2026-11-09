# Directive: OpenCode (open-source AI coding agent CLI)

Workspace-local SOP for installing [OpenCode](https://github.com/anomalyco/opencode) — a terminal (TUI) AI coding agent, provider-agnostic (Anthropic, OpenAI, Google, OpenRouter, Groq, local models), with built-in `build` (full access) and `plan` (read-only) agents. It is a **CLI**, not a Claude Code plugin or skill, and not a long-running service. Companion to `directives/infrastructure/freellmapi.md` (OpenCode can point at FreeLLMAPI's OpenAI-compatible endpoint).

## Goal

One reproducible command that clones/updates a read-only reference copy of the source and installs/upgrades the `opencode` CLI through upstream's documented package-manager path (`npm i -g @opencode/cli`), never the `curl | bash` installer. Idempotent: re-running fast-forwards the clone and is a no-op when the pinned version is already installed.

## Inputs

- **None required to install.**
- Provider credentials, used at runtime only (names only, never stored by us): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_GENERATIVE_AI_API_KEY`, `GROQ_API_KEY` — or `opencode auth login`, which stores keys in OpenCode's own data dir.
- Optional env overrides: `OPENCODE_DIR` (default `$HOME/dev/opencode`), `OPENCODE_REF` (clone ref), `OPENCODE_VERSION` (npm version/dist-tag, default `latest`), `OPENCODE_PM` (`npm`|`bun`), `OPENCODE_SKIP_CLONE=1`.

## Tools / scripts

- `execution/infrastructure/setup_opencode.sh`
  - `bash execution/infrastructure/setup_opencode.sh` — clone/update + install/upgrade CLI
  - `--dry-run` — print the plan, change nothing
  - `--uninstall` (alias `--down`) — remove the global CLI (clone and `~/.config/opencode` kept)
- Upstream reference clone (untrusted, read-only): `/tmp/ext/anomalyco_opencode`. Canonical docs: README "Installation", https://opencode.ai/docs.

## How it runs

- **Vetted at:** commit `7524e5f4955267efa9882e2dd0f485c363ae49e4` (repo version 2.2.5; npm `latest` was 2.2.6 on 2026-11-09). Pin with `OPENCODE_VERSION=2.2.6` for reproducibility.
- **License:** MIT.
- npm package `@opencode/cli` ships a JS launcher; its `postinstall` (`node ./postinstall.mjs`) selects the platform (avx2/musl aware) and `npm install`s the matching prebuilt binary package from the npm registry. No curl, no out-of-registry download.
- No port by default. `opencode serve` (optional headless server) binds `127.0.0.1` by default (server picks from 4096 upward; the background "service" mode uses 49374, or 28894 on Windows). Never bind `0.0.0.0`.
- **Phones home (by design):** models catalog fetch, autoupdate check, the opencode.ai "Zen"/free-models inference gateway, and opt-in `/share` links. Opt-outs: `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1`, `OPENCODE_DISABLE_FREE_MODELS=1`; never `/share` client code.

## Steps

1. `bash execution/infrastructure/setup_opencode.sh --dry-run` to preview.
2. `OPENCODE_VERSION=2.2.6 bash execution/infrastructure/setup_opencode.sh` to install (pinned).
3. `opencode auth login` (or export a provider key from `.env` in the shell), then `cd <project> && opencode`.
4. Optional: point it at FreeLLMAPI via a custom OpenAI-compatible provider in `opencode.json` (`baseURL http://localhost:3001/v1`).
5. Remove: `bash execution/infrastructure/setup_opencode.sh --uninstall`.

## Outputs

- `opencode` on PATH (npm global bin, or `~/.bun/bin` with `OPENCODE_PM=bun`).
- Reference clone at `$OPENCODE_DIR` (not built, not executed).
- No files in this repo, no secrets written.

## Edge cases / learnings

- **Spend:** OpenCode itself is free; model calls bill the chosen provider. Workspace spend discipline applies — prefer the subscription/free routes, never put a paid key in a committed `opencode.json`.
- **Claude Code interop:** OpenCode reads Claude Code config/skills by default; set `OPENCODE_DISABLE_CLAUDE_CODE=1` (or `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`) to keep it out of `.claude/`.
- **Upstream repo `.opencode/skills/`** are dev skills for OpenCode's own codebase; nothing to install from them.
- Do not run the repo's root `bun install` (husky `prepare` + `postinstall` scripts) — the clone is reference only.
- "Remove versions older than 0.1.x before installing" (upstream tip): if `opencode --version` shows 0.x, run `--uninstall` first.
- **Windows:** run the script in Git Bash with Node 20+ (`npm i -g` works natively); the postinstall picks the `windows-x64`/`arm64` binary. Alternatives: the desktop app (`opencode-desktop-win-x64.exe`) or `mise use -g opencode`. Server default port shifts to 28894 on Windows to avoid Hyper-V reserved ranges.
- **Cloud container:** a real install is a normal npm global install (free); the dry-run was verified here, no live install performed.
