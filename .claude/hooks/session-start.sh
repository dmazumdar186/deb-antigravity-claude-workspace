#!/bin/bash
# session-start.sh
# Fires on SessionStart. Injects a brief workspace status as additionalContext
# so the new session opens with current git state + a small set of pre-flight signals
# without the user having to ask.
#
# HARD FAIL-SAFE: this script must NEVER block session init. set +e is on for
# everything, every check is best-effort, and the final exit is always 0.
#
# Configured in .claude/settings.json as a SessionStart hook.

set +e

WORKSPACE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WORKSPACE_DIR" 2>/dev/null || exit 0

# Best-effort git status (short + branch)
GIT_STATUS="$(git status -sb 2>/dev/null | head -20)"
[[ -z "$GIT_STATUS" ]] && GIT_STATUS="(not a git repo or git unavailable)"

# Best-effort: count untracked files for awareness
UNTRACKED_COUNT="$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
[[ -z "$UNTRACKED_COUNT" ]] && UNTRACKED_COUNT="?"

# Best-effort: last commit one-liner
LAST_COMMIT="$(git log -1 --oneline 2>/dev/null)"
[[ -z "$LAST_COMMIT" ]] && LAST_COMMIT="(no commits)"

# Best-effort: CLI version (informational; doesn't gate anything)
CLAUDE_VERSION="$(claude --version 2>/dev/null | head -1)"
[[ -z "$CLAUDE_VERSION" ]] && CLAUDE_VERSION="(unknown)"

# Emit the additionalContext JSON. If the key name is wrong on this CLI version,
# worst case is the JSON is ignored. Never crashes the session.
cat <<EOF
{
  "additionalContext": "## Workspace status (auto-injected at session start)\n\n**Branch & status (\`git status -sb\`):**\n\`\`\`\n${GIT_STATUS}\n\`\`\`\n\n**Untracked files:** ${UNTRACKED_COUNT}\n\n**Last commit:** ${LAST_COMMIT}\n\n**Claude Code CLI:** ${CLAUDE_VERSION}\n"
}
EOF

exit 0
