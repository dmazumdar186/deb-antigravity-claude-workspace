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

    # Retell exposes transcript as transcript_object (per-turn list) and a tool_calls list.
    transcript = c.get("transcript_object") or []
    bot_turns: list[tuple[int, str]] = []  # (index_in_transcript, content)
    for i, turn in enumerate(transcript):
        role = (turn.get("role") or "").lower()
        if role == "agent":
            content = turn.get("content") or ""
            bot_turns.append((i, content))
            for tag in find_forbidden_in_text(content):
                findings.append(f"forbidden({tag}) in agent turn: {content[:160]!r}")
                severity = "FAIL"
            if FILLER_ONLY.match(content):
                findings.append(f"filler-only agent turn (forbidden per 2026-06-27 rule): {content!r}")
                if severity != "FAIL":
                    severity = "WARN"

    # Eager-tool-call regression class. list_slots must NOT fire before the caller has
    # given first_name, last_name, AND confirmed phone. Heuristic: walk through transcript
    # in order; before encountering list_slots, we must have observed at least 4 user
    # turns (reason, first_name, last_name, phone) AND a phone-confirm exchange.
    tool_calls = []
    for turn in transcript:
        if (turn.get("role") or "").lower() in ("tool_call_invocation", "tool", "function_call"):
            name = turn.get("name") or turn.get("tool_name") or ""
            tool_calls.append({"name": name, "turn": turn})

    # Walk transcript chronologically, count user turns before first list_slots.
    user_turns_before_list_slots = 0
    saw_phone_confirmation = False
    fired_list_slots_early = False
    for turn in transcript:
        role = (turn.get("role") or "").lower()
        content = (turn.get("content") or "").lower()
        if role == "user":
            user_turns_before_list_slots += 1
            if any(w in content for w in ("yes", "yeah", "yep", "correct", "right", "that's right")):
                # Possible phone confirmation -- we'll trust the flow's gating.
                # We treat this as a soft signal only when it follows >=3 prior user turns.
                if user_turns_before_list_slots >= 4:
                    saw_phone_confirmation = True
        elif role in ("tool_call_invocation", "tool", "function_call"):
            name = (turn.get("name") or turn.get("tool_name") or "").lower()
            if name == "list_slots":
                if user_turns_before_list_slots < 4 or not saw_phone_confirmation:
                    fired_list_slots_early = True
                break  # we only care about the FIRST list_slots call

    if fired_list_slots_early:
        findings.append(
            f"EAGER list_slots: fired after only {user_turns_before_list_slots} user turn(s) "
            f"and phone_confirmation={saw_phone_confirmation} -- this is the 2026-06-30 bug class."
        )
        severity = "FAIL"

    return {
        "id": c.get("call_id", "?"),
        "startedAt": (c.get("start_timestamp")
                       and datetime.fromtimestamp(c["start_timestamp"] / 1000, tz=timezone.utc).isoformat()),
        "disconnection_reason": c.get("disconnection_reason"),
        "findings": findings,
        "severity": severity,
        "turn_count": len(transcript),
        "tool_call_count": len(tool_calls),
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
