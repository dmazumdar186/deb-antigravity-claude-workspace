#!/usr/bin/env bash
# .claude/hooks/verdict-table-check.sh
#
# Phase-1 workspace hardening (2026-08-04). Stop-hook that inspects the
# assistant's final message for "shipped-flavored" framing and, when it
# fires, checks the session transcript for adjacent evidence that the
# mandatory audit stack was actually invoked (per
# ~/.claude/rules/mandatory-audit-stack.md).
#
# On a match without evidence, emits a warning line via `additionalContext`
# (which Claude Code surfaces at the top of the next turn) telling the
# operator that a verdict table is owed.
#
# HARD FAIL-SAFE: this hook is advisory. It NEVER blocks the assistant.
# Any parse error, missing file, or shell mishap exits 0 silently.
#
# Configured in .claude/settings.json as a Stop hook (timeout 5s).
#
# ── How the detection works ─────────────────────────────────────────────
# Claude Code sets $CLAUDE_TRANSCRIPT_PATH (JSONL) for hooks. We read the
# last ~50 events, find the assistant's last text message, and grep for
# the forbidden framings. If matched, we then look back over the last 30
# events for tool_use blocks whose name is Agent/Task and whose input
# description references any of the 6 audit-stack fingerprints
# (front-door, acceptance, anneal, panel, pipeline-auditor, adversarial).
#
# If < 2 distinct audit-stack fingerprints appear, we emit the warning.

set +e

# Portable interpreter: `py` exists only on Windows; cloud/Linux sandboxes have python3.
PY="$(command -v py || command -v python3 || command -v python)"
[ -z "$PY" ] && PY=python3

TRANSCRIPT="${CLAUDE_TRANSCRIPT_PATH:-}"
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    # No transcript path exposed (older CLI or first turn) — nothing to do.
    exit 0
fi

# Delegate the JSONL parsing to python; keeping bash minimal avoids
# quoting nightmares on Windows.
OUT="$("$PY" -c '
import json, os, re, sys

path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
if not path or not os.path.exists(path):
    sys.exit(0)

FORBIDDEN = re.compile(
    r"\b(shipped|live|ready|done|complete|wrapped|good to go|"
    r"100% complete|all set|verified|clean forever)\b",
    re.IGNORECASE,
)
AUDIT_FINGERPRINTS = (
    "front-door", "front_door", "acceptance", "anneal",
    "panel-pass", "panel_pass", "pipeline-auditor", "pipeline_auditor",
    "adversarial", "customer-pov", "customer_pov",
)

# Read tail of the JSONL (last 200 lines is more than enough for a turn).
try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-200:]
except OSError:
    sys.exit(0)

events = []
for ln in lines:
    ln = ln.strip()
    if not ln:
        continue
    try:
        events.append(json.loads(ln))
    except json.JSONDecodeError:
        continue

# Find the last assistant text message.
last_text = ""
for ev in reversed(events):
    if ev.get("type") != "assistant":
        continue
    msg = ev.get("message") or {}
    content = msg.get("content") or []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            last_text = block.get("text", "")
            break
    if last_text:
        break

if not last_text or not FORBIDDEN.search(last_text):
    sys.exit(0)

# Framing detected. Count distinct audit-stack fingerprints in the last
# ~50 events (recent tool calls).
seen = set()
for ev in events[-50:]:
    if ev.get("type") != "assistant":
        continue
    msg = ev.get("message") or {}
    content = msg.get("content") or []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        tool_name = block.get("name", "")
        if tool_name not in ("Agent", "Task"):
            continue
        inp = block.get("input") or {}
        # Description + prompt are the two free-text fields where fingerprints appear.
        blob = (str(inp.get("description", "")) + " " + str(inp.get("prompt", ""))).lower()
        for fp in AUDIT_FINGERPRINTS:
            if fp in blob:
                seen.add(fp.replace("_", "-"))

if len(seen) >= 2:
    sys.exit(0)  # Enough audit-stack evidence in adjacent tool calls.

warning = (
    "\n\n"
    "> ** Shipped-claim detected without mandatory-audit-stack invocation.**\n"
    ">\n"
    "> The last assistant message uses shipped/live/ready/done/complete/wrapped "
    "framing, but < 2 of the 6 mandatory auditors (front-door synthetic, "
    "customer-POV/acceptance, anneal, panel-pass 4-lens, test-suite, "
    "pipeline-auditor/adversarial) fired in the recent tool-call window.\n"
    ">\n"
    "> Per ~/.claude/rules/mandatory-audit-stack.md, a verdict table is required "
    "before any \"done\" claim. Either (a) invoke the missing auditors in the "
    "next turn and produce the table, or (b) log an explicit skip reason.\n"
)

payload = {
    "hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": warning,
    }
}
print(json.dumps(payload))
' 2>/dev/null)"

# ── Jev audit gate (2026-10-07, directives/infrastructure/jev_audit_gate.md) ──
# Score the last 3 sub-agent hand-back reports; weak ones add a warning line.
# Skipped when Jev is toggled off. Fail-safe: any error leaves OUT untouched.
GATE=""
ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
STATE_FILE="$ROOT/.claude/jev/state.json"
if ! grep -Eq '"enabled"[[:space:]]*:[[:space:]]*false' "$STATE_FILE" 2>/dev/null; then
    GATE="$(timeout 3 "$PY" "$ROOT/execution/infrastructure/jev_audit_gate.py" transcript \
        --path "$TRANSCRIPT" --last 3 --json 2>/dev/null)"
fi
if [ -n "$GATE" ]; then
    MERGED="$(GATE_JSON="$GATE" HOOK_OUT="$OUT" "$PY" -c '
import json, os
g = json.loads(os.environ.get("GATE_JSON") or "{}")
res = g.get("results") or []
bad = [r for r in res if r.get("decision") in ("review", "reject")]
out = os.environ.get("HOOK_OUT", "").strip()
if not bad:
    print(out)
    raise SystemExit(0)
why = []
for r in bad:
    why.extend(r.get("reasons") or [r.get("decision", "")])
why = "; ".join(dict.fromkeys(w for w in why if w))[:300]
line = ("\n> **Jev audit gate:** %d of %d recent audit reports scored below the acceptance bar - %s. "
        "Re-run the auditor with explicit evidence before claiming done.\n" % (len(bad), len(res), why))
try:
    payload = json.loads(out) if out else {}
except ValueError:
    payload = {}
hso = payload.setdefault("hookSpecificOutput", {"hookEventName": "Stop"})
hso.setdefault("hookEventName", "Stop")
hso["additionalContext"] = (hso.get("additionalContext") or "") + line
print(json.dumps(payload))
' 2>/dev/null)"
    [ -n "$MERGED" ] && OUT="$MERGED"
fi

[ -n "$OUT" ] && printf '%s\n' "$OUT"
exit 0
