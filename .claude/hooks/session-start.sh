#!/bin/bash
# session-start.sh
# Fires on SessionStart. Injects a brief workspace status as additionalContext
# so the new session opens with current git state without the user having to ask.
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

# Export so python reads via os.environ (safer than heredoc string interp).
export GIT_STATUS UNTRACKED_COUNT LAST_COMMIT CLAUDE_VERSION

"$PY" -c '
import json, os
body = (
    "## Workspace status (auto-injected at session start)\n\n"
    "**Branch & status (`git status -sb`):**\n```\n"
    + os.environ.get("GIT_STATUS", "") + "\n```\n\n"
    "**Untracked files:** " + os.environ.get("UNTRACKED_COUNT", "?") + "\n\n"
    "**Last commit:** " + os.environ.get("LAST_COMMIT", "(none)") + "\n\n"
    "**Claude Code CLI:** " + os.environ.get("CLAUDE_VERSION", "(unknown)") + "\n"
)
print(json.dumps({"additionalContext": body}))
' 2>/dev/null

exit 0
