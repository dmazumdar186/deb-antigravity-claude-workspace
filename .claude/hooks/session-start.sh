#!/bin/bash
# session-start.sh
# Fires on SessionStart. Injects a brief workspace status as additionalContext
# so the new session opens with current git state without the user having to ask.
#
# Also (2026-09-01, token-economy sweep) auto-runs the weekly token-usage
# digest — at most once per 7 days, stamp-file gated — and flags an oversized
# CLAUDE.local.md, so the measurement loop needs zero operator action.
#
# HARD FAIL-SAFE: this script must NEVER block session init. set +e is on for
# everything, every check is best-effort, and the final exit is always 0.
#
# Configured in .claude/settings.json as a SessionStart hook (timeout 35s).
# 2026-09-01: removed the expired job_search_v2 synthetic block (window ended
# 2026-06-26) — it was dead weight evaluated on every session start.

set +e

# Portable interpreter: `py` exists only on Windows; cloud/Linux sandboxes have python3.
PY="$(command -v py || command -v python3 || command -v python)"
[ -z "$PY" ] && PY=python3

WORKSPACE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WORKSPACE_DIR" 2>/dev/null || exit 0

GIT_STATUS="$(git status -sb 2>/dev/null | head -20)"
[[ -z "$GIT_STATUS" ]] && GIT_STATUS="(not a git repo or git unavailable)"

UNTRACKED_COUNT="$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
[[ -z "$UNTRACKED_COUNT" ]] && UNTRACKED_COUNT="?"

LAST_COMMIT="$(git log -1 --oneline 2>/dev/null)"
[[ -z "$LAST_COMMIT" ]] && LAST_COMMIT="(no commits)"

CLAUDE_VERSION="$(claude --version 2>/dev/null | head -1)"
[[ -z "$CLAUDE_VERSION" ]] && CLAUDE_VERSION="(unknown)"

# ----- weekly token-usage digest (auto; at most once per 7 days) -----
USAGE_DIGEST=""
STAMP="$WORKSPACE_DIR/.tmp/token_usage_last_run"
mkdir -p "$WORKSPACE_DIR/.tmp" 2>/dev/null
NOW_EPOCH="$(date +%s 2>/dev/null)"
LAST_EPOCH="$(cat "$STAMP" 2>/dev/null | tr -dc '0-9')"
[ -z "$LAST_EPOCH" ] && LAST_EPOCH=0
TIMEOUT_CMD="$(command -v timeout || true)"
if [ -n "$NOW_EPOCH" ] && [ $((NOW_EPOCH - LAST_EPOCH)) -gt 604800 ]; then
    USAGE_DIGEST="$($TIMEOUT_CMD 20 "$PY" execution/infrastructure/token_usage_report.py --days 7 --summary 2>/dev/null | head -8)"
    [ -n "$USAGE_DIGEST" ] && printf '%s' "$NOW_EPOCH" > "$STAMP" 2>/dev/null
fi

# ----- CLAUDE.local.md context-rent check (auto-loads every turn if present) -----
LOCAL_MD_NOTE=""
if [ -f "$WORKSPACE_DIR/CLAUDE.local.md" ]; then
    LOCAL_MD_SIZE="$(wc -c < "$WORKSPACE_DIR/CLAUDE.local.md" 2>/dev/null | tr -d ' ')"
    if [ -n "$LOCAL_MD_SIZE" ] && [ "$LOCAL_MD_SIZE" -gt 3000 ] 2>/dev/null; then
        LOCAL_MD_NOTE="CLAUDE.local.md is ${LOCAL_MD_SIZE} bytes and auto-loads every turn — put it on the token-economy diet (.claude/rules/token-economy.md)."
    fi
fi

# Export so python reads via os.environ (safer than heredoc string interp).
export GIT_STATUS UNTRACKED_COUNT LAST_COMMIT CLAUDE_VERSION USAGE_DIGEST LOCAL_MD_NOTE

"$PY" -c '
import json, os
usage = os.environ.get("USAGE_DIGEST", "")
usage_block = ""
if usage:
    usage_block = (
        "\n\n## Weekly token-usage digest (auto-run, next in 7 days)\n\n"
        "```\n" + usage + "\n```\n"
        "Surface this digest to the user in your first reply.\n"
    )
local_note = os.environ.get("LOCAL_MD_NOTE", "")
local_block = ("\n\n**Context-rent warning:** " + local_note + "\n") if local_note else ""
body = (
    "## Workspace status (auto-injected at session start)\n\n"
    "**Branch & status (`git status -sb`):**\n```\n"
    + os.environ.get("GIT_STATUS", "") + "\n```\n\n"
    "**Untracked files:** " + os.environ.get("UNTRACKED_COUNT", "?") + "\n\n"
    "**Last commit:** " + os.environ.get("LAST_COMMIT", "(none)") + "\n\n"
    "**Claude Code CLI:** " + os.environ.get("CLAUDE_VERSION", "(unknown)") + "\n"
    + usage_block + local_block
)
print(json.dumps({"additionalContext": body}))
' 2>/dev/null

exit 0
