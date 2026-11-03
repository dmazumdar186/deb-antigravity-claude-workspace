#!/usr/bin/env bash
# .claude/hooks/skillspector-gate.sh
#
# PreToolUse(Bash) gate — the ONE blocking gate of the Jev plugin advisor.
# Pipes the hook's stdin JSON into execution/infrastructure/skillspector_gate.py,
# which detects an unvetted skill/plugin install (git clone into .claude/skills,
# cp/mv into .claude/skills|plugins, `agent-reach add`, plugin enable), runs
# `skillspector scan <target> --no-llm -f json`, and on a HIGH/CRITICAL finding
# emits a PreToolUse permissionDecision=ask so the operator confirms. Anything
# below HIGH is a one-line note; ordinary bash passes untouched.
#
# HARD FAIL-SAFE: advisory on everything except a confirmed HIGH/CRITICAL skill
# install. Any parse error, missing skillspector, timeout, or shell mishap
# exits 0 and lets the command through. Configured in .claude/settings.json as a
# PreToolUse hook (matcher Bash).
set +e

PY="$(command -v py || command -v python3 || command -v python)"
[ -z "$PY" ] && PY=python3

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

"$PY" "$ROOT/execution/infrastructure/skillspector_gate.py" hook
exit 0
