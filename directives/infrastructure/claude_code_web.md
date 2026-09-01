# Claude Code on the Web (claude.ai/code) — cloud sessions for this workspace

**Created 2026-08-31.** How to run this repo in Claude Code cloud sessions, what
carries over from the local Windows setup, and the one manual step (secrets).

---

## Goal

Run full-power Claude Code sessions against `dmazumdar186/deb-antigravity-claude-workspace`
from https://claude.ai/code (browser, phone, any machine) — with the workspace's
directives, skills, hooks, agents, and MCP servers intact.

## One-time setup (operator, ~5 minutes)

1. **Connect GitHub**: go to https://claude.ai/code → "Sign in with GitHub" →
   approve → install the Claude GitHub App when prompted (select this repo or all).
   Alternative from a terminal: `claude /login` then `/web-setup`.
2. **Create a cloud environment**: at claude.ai/code, click the **cloud icon above
   the message box** (shows "Default") → **Add cloud environment** → name it
   (e.g. `antigravity`).
3. **Paste environment variables**: the **"Environment variables"** box in that
   dialog accepts standard `.env` format — `KEY=value`, one per line. Run
   `py execution/infrastructure/print_env_for_cloud.py --values` locally, copy the
   output block, paste it there, **Save changes**. (The operator does this by hand;
   secrets never go through chat or git.)
   - Note: values in this box are visible to anyone who can use the environment.
     On a personal account that is just you. For extra-sensitive keys, use
     **API credentials** instead (environment ⚙️ settings → "API credentials" →
     Add credential) — those are encrypted, attached by Anthropic's proxy only to
     the hosts you allowlist, and never visible to the session.
4. **Start a session**: pick the repo + environment, type a prompt. Pre-fill URLs
   work too: `https://claude.ai/code?repo=dmazumdar186/deb-antigravity-claude-workspace`.

## What carries over automatically (cloned with the repo)

- `CLAUDE.md`, `directives/`, `execution/`, `tests/`
- `.claude/settings.json` (model pin `claude-fable-5-1`, permissions, hooks config)
- `.claude/hooks/` — **all hooks are Linux-portable as of 2026-08-31** (they
  resolve `py` → `python3` automatically; `notify-done.sh` no-ops without
  PowerShell)
- `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.claude/rules/`,
  `.claude/workflows/`, `.claude/notes/`
- `.mcp.json` — github / firecrawl / tavily MCP servers, keyed by `${GITHUB_PAT}`,
  `${FIRECRAWL_API_KEY}`, `${TAVILY_API_KEY}` from the cloud environment vars

## What does NOT carry over (local-only by design)

- `.env`, `credentials.json`, `token.json` — gitignored. Env vars come from the
  cloud environment (step 3). Google OAuth token files have no cloud equivalent
  yet; Google-API workflows (Sheets service account via
  `GOOGLE_SERVICE_ACCOUNT_PATH`, Gmail OAuth) stay local-only unless the JSON is
  provided another way.
- `~/.claude/CLAUDE.md`, `~/.claude/rules/`, `~/.claude/skills/` (user-global
  layer) — lives on the Windows machine. It contains personal/client context and
  must NOT be committed to this **public** repo. Cloud sessions run on the
  project layer only; the load-bearing rules are mirrored in repo rules where
  safe.
- `CLAUDE.local.md`, `.claude/settings.local.json` — gitignored, machine-local.
- MCP servers registered with `claude mcp add` at user scope (e.g. perplexity) —
  only `.mcp.json` project-scope servers reach the cloud.
- Anything under `C:\Users\deban\dev\` (anneal, humanizer, mobile-apps) — separate
  repos; clone them into their own cloud sessions if needed.

## Cloud sandbox differences vs this Windows machine

- Linux VM: use `python3`/`python`, not `py`; no PowerShell, no OneDrive paths.
- Windows-path permission entries in `.claude/settings.json` are inert (harmless).
- Network egress is proxied/restricted; GitHub and public package registries
  (pypi, npm) are allowed. First `pip install -r requirements.txt` runs in-session
  (or add it as the environment's setup script for caching).
- Uncommitted local work is invisible to cloud sessions — push the branch first.

## Local ↔ cloud workflows

- Send a task to the cloud from the terminal: `claude --cloud "prompt"` (clones
  the current branch as pushed).
- Follow up: `claude -p "message" --cloud <session-id>`.
- Pull a cloud session down to this machine: `claude --teleport` (needs clean
  git state; fetches the session's branch + full conversation).

## Edge cases / learnings

- 2026-08-31: hooks called `py` (Windows launcher) and would have errored on every
  Bash call in cloud sessions (`safety-guard.sh` is PreToolUse:Bash). Fixed with a
  portable resolver: `PY="$(command -v py || command -v python3 || command -v python)"`.
- The repo is **PUBLIC**. Never commit `.env`, `.env` values, deliverables with
  personal data, or user-global rules. `.env.example` (names only) is the
  committed contract.
