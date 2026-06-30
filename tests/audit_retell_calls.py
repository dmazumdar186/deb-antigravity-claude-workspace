"""
description: Production-grade auditor for Retell calls. Mirrors audit_vapi_calls.py for the
Retell-flavored call shape. Pulls recent calls from /v2/list-calls + grades each on:
  - eager-tool-call regression class (the exact 2026-06-30 11:47 Vapi bug):
    asserts list_slots was NOT called before turn 5+ (greet, get_reason, get_first_name,
    get_last_name, get_phone, confirm_phone are all conversation nodes, so any list_slots
    tool call before those have been visited = structural failure of the flow architecture)
  - forbidden phrases (offers exit, premature goodbye, robot disclosure, quoted price)
  - filler-only bot turn (no follow-up question)
  - silence-timed-out + disconnection_reason errors

CLI:
    --limit N           how many recent calls (default 10)
    --since-hours H     only audit calls started in the last H hours (default 24)
    --strict            also exit 1 on WARN

outputs:
    stdout: per-call PASS/WARN/FAIL, exit 0 on clean, 1 on FAIL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Best-effort stream reconfigure.
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


FORBIDDEN_REGEX = [
    (r"are you sure you (want|need) to (go|leave|end)",      "offers caller an exit"),
    (r"otherwise have a (wonderful|good|great|nice) day",    "premature graceful goodbye"),
    (r"if there'?s nothing else",                            "premature graceful goodbye"),
    (r"have a wonderful day",                                "premature graceful goodbye"),
    (r"do you still (need|want) to (book|continue|stay)",    "wrong-intent interpretation"),
    (r"i am an automated system",                            "robotic disclosure"),
    (r"i'?m a (computer|bot|machine|virtual assistant)",     "robotic disclosure"),
    (r"(\$|EUR|USD)\s?\d+",                                  "quoted a price (forbidden)"),
]
FORBIDDEN = [(re.compile(p, re.IGNORECASE), tag) for p, tag in FORBIDDEN_REGEX]

FILLER_ONLY = re.compile(
    r"^\s*(?:one moment\.?|please wait\.?|let me check\.?|hold on\.?|"
    r"give me a (?:sec|second|moment)\.?|just a moment\.?|just a sec\.?)\s*$",
    re.IGNORECASE,
)

ERROR_DISCONNECT_REASONS = {
    "error_llm_websocket_open", "error_llm_websocket_lost_connection",
    "error_llm_websocket_runtime", "error_llm_websocket_corrupt_payload",
    "error_no_audio_received", "error_user_not_joined", "error_retell",
    "error_unknown", "error_inactivity",
}


def fetch_calls(api_key: str, limit: int) -> list[dict]:
    url = "https://api.retellai.com/v2/list-calls"
    body = json.dumps({"limit": limit, "sort_order": "descending"}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def find_forbidden_in_text(text: str) -> list[str]:
    return [tag for rx, tag in FORBIDDEN if rx.search(text or "")]


def grade_call(c: dict) -> dict:
    findings: list[str] = []
    severity = "PASS"

    disc = (c.get("disconnection_reason") or "").lower()
    if disc in ERROR_DISCONNECT_REASONS or "error" in disc:
        findings.append(f"disconnection_reason={disc} (runtime error)")
        severity = "FAIL"

    # Retell call shape (verified against /v2/get-call response 2026-06-30):
    #   - transcript_object: per-turn list, roles in {agent, user}
    #   - tool_calls (top level): array of {name, start_time_sec, tool_call_id, type, success}
    #   - transcript_with_tool_calls: interleaved view with the tool calls inline
    # Earlier version of this auditor looked for tool calls inside transcript_object roles
    # like "tool_call_invocation" -- they don't exist in Retell's shape, so every call
    # graded as "0 tool calls" even when both list_slots and book_slot fired successfully.
    # That blind spot lasted the entire 2026-06-30 listen-test session.
    transcript = c.get("transcript_object") or []
    twtc = c.get("transcript_with_tool_calls") or []
    tool_calls_top = c.get("tool_calls") or []

    for turn in transcript:
        role = (turn.get("role") or "").lower()
        if role == "agent":
            content = turn.get("content") or ""
            for tag in find_forbidden_in_text(content):
                findings.append(f"forbidden({tag}) in agent turn: {content[:160]!r}")
                severity = "FAIL"
            if FILLER_ONLY.match(content):
                findings.append(f"filler-only agent turn (forbidden per 2026-06-27 rule): {content!r}")
                if severity != "FAIL":
                    severity = "WARN"

    # Eager-tool-call detection: walk the interleaved transcript_with_tool_calls in
    # chronological order. Count user turns BEFORE the first list_slots invocation;
    # require >=4 user turns AND a phone-confirm 'yes' before list_slots fires.
    user_turns_before_ls = 0
    saw_phone_confirmation = False
    fired_ls_early = False
    for entry in twtc:
        role = (entry.get("role") or "").lower()
        # The interleaved structure uses 'tool_call_invocation' or 'tool_call_result' as roles.
        if role == "user":
            user_turns_before_ls += 1
            content = (entry.get("content") or "").lower()
            if user_turns_before_ls >= 4 and any(
                w in content for w in ("yes", "yeah", "yep", "correct", "right", "that's right")
            ):
                saw_phone_confirmation = True
        elif role in ("tool_call_invocation", "tool_call", "function_call"):
            name = (entry.get("name") or entry.get("tool_name") or "").lower()
            if name == "list_slots":
                if user_turns_before_ls < 4 or not saw_phone_confirmation:
                    fired_ls_early = True
                break

    # Fallback: if transcript_with_tool_calls doesn't carry role-labeled invocations,
    # use the top-level tool_calls array + start_time_sec to compare against user turn
    # timestamps. The 2026-06-30 calls had tool_calls populated but no inline invocations
    # in transcript_with_tool_calls (just inline at the right time).
    if not fired_ls_early and tool_calls_top:
        first_ls = next((tc for tc in tool_calls_top if (tc.get("name") or "").lower() == "list_slots"), None)
        if first_ls:
            ls_t = first_ls.get("start_time_sec") or 0.0
            user_turns_before = 0
            saw_yes_before = False
            for turn in transcript:
                if (turn.get("role") or "").lower() != "user":
                    continue
                # word-level timing: take the first word's start as the turn start
                words = turn.get("words") or []
                t_start = (words[0].get("start") if words else None) or 0.0
                if t_start >= ls_t:
                    break
                user_turns_before += 1
                if user_turns_before >= 4 and any(
                    w in (turn.get("content") or "").lower()
                    for w in ("yes", "yeah", "yep", "correct", "right")
                ):
                    saw_yes_before = True
            if user_turns_before < 4 or not saw_yes_before:
                fired_ls_early = True
                user_turns_before_ls = user_turns_before
                saw_phone_confirmation = saw_yes_before

    if fired_ls_early:
        findings.append(
            f"EAGER list_slots: fired after only {user_turns_before_ls} user turn(s) "
            f"and phone_confirmation={saw_phone_confirmation} -- this is the 2026-06-30 bug class."
        )
        severity = "FAIL"

    # Repeated-goodbye detection: the "All set... Have a good day" close didn't end
    # the call on 2026-06-30 prod runs; Lisa repeated it 2-3 times because the close
    # node had no terminal action. Flag any call where the same agent goodbye-shaped
    # turn appears more than once.
    goodbye_count = sum(
        1 for t in transcript
        if (t.get("role") or "").lower() == "agent"
        and "all set" in (t.get("content") or "").lower()
        and "have a good day" in (t.get("content") or "").lower()
    )
    if goodbye_count >= 2:
        findings.append(f"close-loop: goodbye repeated {goodbye_count}x (end node missing)")
        if severity != "FAIL":
            severity = "WARN"

    return {
        "id": c.get("call_id", "?"),
        "startedAt": (c.get("start_timestamp")
                       and datetime.fromtimestamp(c["start_timestamp"] / 1000, tz=timezone.utc).isoformat()),
        "disconnection_reason": c.get("disconnection_reason"),
        "findings": findings,
        "severity": severity,
        "turn_count": len(transcript),
        "tool_call_count": len(tool_calls_top),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--since-hours", type=int, default=24)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("RETELL_API_KEY")
    if not api_key:
        print("RETELL_API_KEY required", file=sys.stderr)
        return 2

    try:
        calls = fetch_calls(api_key, args.limit)
    except urllib.error.HTTPError as exc:
        print(f"retell HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
              file=sys.stderr)
        return 2

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
    recent = []
    for c in calls:
        ts = c.get("start_timestamp")
        if not ts:
            continue
        t = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        if t >= cutoff:
            recent.append(c)

    print(f"audit: {len(recent)} retell calls in the last {args.since_hours}h (of {len(calls)} fetched)")

    clean = warn = fail = 0
    for c in recent:
        g = grade_call(c)
        print(f"{g['severity']:<4}  {g['startedAt']}  {g['id'][:24]}  "
              f"disconn={g['disconnection_reason']}  ({g['turn_count']} turns, {g['tool_call_count']} tool calls)")
        for f in g["findings"]:
            print(f"      - {f}")
        if g["severity"] == "FAIL":
            fail += 1
        elif g["severity"] == "WARN":
            warn += 1
        else:
            clean += 1

    print(f"\nsummary: {clean} clean, {warn} warn, {fail} fail")
    if fail > 0:
        return 1
    if args.strict and warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
