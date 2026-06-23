#!/bin/bash
# session-start.sh
# Fires on SessionStart. Injects a brief workspace status as additionalContext
# so the new session opens with current git state + a small set of pre-flight signals
# without the user having to ask.
#
# Also runs the job_search_v2 comprehensive synthetic on every session through
# 2026-06-26 (3-day window requested 2026-06-23 to validate the daily Excel/Sheet
# is producing correct, fresh entries) and embeds the digest in additionalContext.
#
# HARD FAIL-SAFE: this script must NEVER block session init. set +e is on for
# everything, every check is best-effort, and the final exit is always 0.
#
# Configured in .claude/settings.json as a SessionStart hook (timeout 35s).

set +e

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

# ----- job_search_v2 comprehensive synthetic (windowed 2026-06-23 .. 2026-06-26) -----
SYNTHETIC_RAW=""
SYNTHETIC_EXIT=""
TODAY="$(date -u +%Y-%m-%d)"
WINDOW_END="2026-06-26"
if [[ "$TODAY" < "$WINDOW_END" || "$TODAY" == "$WINDOW_END" ]]; then
    SYNTHETIC_RAW="$(timeout 25 py tests/comprehensive_synthetic_job_search_v2.py 2>&1 | head -40)"
    SYNTHETIC_EXIT=$?
fi

# Export everything so python can read via os.environ (safer than heredoc string interp).
export GIT_STATUS UNTRACKED_COUNT LAST_COMMIT CLAUDE_VERSION SYNTHETIC_RAW SYNTHETIC_EXIT WINDOW_END TODAY

# Build the additionalContext payload via python — handles JSON escaping correctly
# even when the synthetic output contains newlines, quotes, backslashes, brackets.
py -c '
import json, os
synthetic_raw = os.environ.get("SYNTHETIC_RAW", "")
synthetic_exit = os.environ.get("SYNTHETIC_EXIT", "")
synthetic_block = ""
if synthetic_raw:
    synthetic_block = (
        "\n\n## Job-search synthetic (auto-runs each session through "
        + os.environ.get("WINDOW_END", "") + ")\n\n"
        "Exit code: " + synthetic_exit + "\n\n"
        "```\n" + synthetic_raw + "\n```\n"
    )
body = (
    "## Workspace status (auto-injected at session start)\n\n"
    "**Branch & status (`git status -sb`):**\n```\n"
    + os.environ.get("GIT_STATUS", "") + "\n```\n\n"
    "**Untracked files:** " + os.environ.get("UNTRACKED_COUNT", "?") + "\n\n"
    "**Last commit:** " + os.environ.get("LAST_COMMIT", "(none)") + "\n\n"
    "**Claude Code CLI:** " + os.environ.get("CLAUDE_VERSION", "(unknown)") + "\n"
    + synthetic_block
)
print(json.dumps({"additionalContext": body}))
' 2>/dev/null

exit 0
