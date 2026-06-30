"""
description: Production LLM-behavior gate for the Vapi dental voice agent. Pulls the last N calls
for the live assistant from the Vapi REST API and grades each transcript against the same
forbidden-phrase + must-not-end-with-error rules the system prompt enforces.

Why this exists: integration_voice_flow.py exercises the LLM behavior on synthetic Gemini calls
but is bottlenecked by the free-tier Gemini RPM cap. This script audits ACTUAL production
behavior, so the gate runs against the same model + same Vapi runtime + same voice + same ASR
+ same network conditions that real callers hit. It is the cheapest way to detect a regression
that only manifests under Vapi's payload-shape constraints (cf. the 2026-06-27 mojibake / Gemini
400 vapifault, which no offline test could surface).

inputs (env, from .env):
    VAPI_API_KEY          required (Bearer)
    VAPI_ASSISTANT_ID     required (live assistant id)

CLI:
    --limit N             how many recent calls to audit (default 20)
    --since-hours H       only audit calls started within the last H hours (default 24)
    --strict              fail if ANY call has a forbidden phrase OR ended with a vapifault
                          (default: warn-only on history; we expose the recent live calls)

outputs:
    stdout: per-call PASS/WARN/FAIL with offending excerpts
    exit code: 0 on no FAIL conditions, 1 otherwise

Per ~/.claude/rules/output-acceptance-gate.md this is hard-failing (under --strict) and
asserts on the OUTPUT a real user would hear, not on mechanics.
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
except Exception:  # nosec: stream may not support reconfigure on all runtimes
    # Safe to swallow: stdout reconfigure is a best-effort improvement, not load-bearing.
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


# Same forbidden bank as integration_voice_flow.py FORBIDDEN, sourced from every
# operator-listen-test bug since iteration 1.
FORBIDDEN_REGEX = [
    (r"are you sure you (want|need) to (go|leave|end)",      "offers caller an exit"),
    (r"otherwise have a (wonderful|good|great|nice) day",    "premature graceful goodbye"),
    (r"if there'?s nothing else",                            "premature graceful goodbye"),
    (r"have a wonderful day",                                "premature graceful goodbye"),
    (r"do you still (need|want) to (book|continue|stay)",    "wrong-intent interpretation"),
    (r"i am an automated system",                            "robotic disclosure"),
    (r"i'?m a (computer|bot|machine|virtual assistant)",     "robotic disclosure"),
    (r"(\$|€|£)\s?\d+",                                      "quoted a price (forbidden)"),
    # Filler-then-silence: a bot-turn that is ONLY a filler phrase is a regression
    # for the 2026-06-27 bug. We detect this at turn level below, not via this regex.
]
FORBIDDEN = [(re.compile(p, re.IGNORECASE), tag) for p, tag in FORBIDDEN_REGEX]

# Bot-utterance regex: matches if any standalone filler phrase appears AT ALL in the
# turn (originally required the WHOLE turn to be filler; that let "Just a sec. Got it."
# slip through -- the 2026-06-30 11:47 production bug audited as clean by mistake).
FILLER_ANYWHERE = re.compile(
    r"\b(?:one moment|please wait|let me check|hold on|"
    r"give me a (?:sec|second|moment)|just a (?:sec|second|moment)|"
    r"bear with me|one sec)\b",
    re.IGNORECASE,
)

# Vapi endedReasons that indicate a runtime error rather than a clean hang-up.
# These all = "the system crashed" from the operator's POV.
ERROR_END_REASONS = {
    "call.in-progress.error-vapifault-google-400-bad-request-validation-failed",
    "call.in-progress.error-vapifault-google-500",
    "call.in-progress.error-vapifault",
    "call.in-progress.error-twilio",
    "pipeline-error-openai-400",
}

# Structural prompt-level sentinels — these are the rules the 13 new corpus
# scenarios assert against. They're enforced HERE rather than via Gemini-driven
# scenario tests because the free-tier RPM cap makes those tests unreliable.
# This audit pass guarantees the deployed system prompt still encodes the
# behavior the new scenarios describe -- a structural gate, not a behavioral one.
SYSTEM_PROMPT_REQUIRED_SENTINELS = [
    # Filler-then-silence regression (2026-06-27 13:20)
    ("NEVER use bare filler phrases", "filler-then-silence rule (scenario: regression_filler_then_silence)"),
    # ASR-misheard-as-Goodbye regression (2026-06-27 10:53)
    ("Goodbye / Hello / single ambiguous words", "ASR-misheard-as-goodbye rule (scenario: regression_asr_goodbye_misheard_as_name)"),
    # Tool-failure recovery (covers: calcom 0 slots, 409 duplicate, network error)
    ("Tool failure recovery", "tool-failure recovery rule (scenarios: negative_calcom_zero_slots, negative_calcom_409_slot_taken)"),
    # Are-you-still-there (covers: boundary_silence_after_phone_digits)
    ("Are you still there", "silence keep-alive rule (scenario: boundary_silence_after_phone_digits)"),
    # ONE-QUESTION-AT-A-TIME (covers: barge-in, premature-yes)
    ("ONE-QUESTION-AT-A-TIME", "one-question rule (scenarios: boundary_barge_in_mid_sentence, negative_yes_before_slots_proposed)"),
    # Repeat phone digit-by-digit (covers: 9-digit, 11-digit boundaries)
    ("digit by digit", "phone-readback rule (scenarios: boundary_phone_9_digits_too_short, boundary_phone_11_digits_too_long)"),
    # English only handoff (covers: negative_french_mid_call_switch)
    ("only handles English", "english-only handoff rule (scenario: negative_french_mid_call_switch)"),
    # Never offer to end the call (covers: refuse-phone, hangup-mid-booking)
    ("Never offer to end the call", "no-exit-offer rule (scenarios: negative_caller_refuses_phone_number, negative_caller_hangs_up_mid_booking)"),
]


def audit_system_prompt(api_key: str, assistant_id: str) -> list[str]:
    """Pull the live assistant config and verify every corpus-scenario sentinel."""
    url = f"https://api.vapi.ai/assistant/{assistant_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "vapi-audit/0.4.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        a = json.loads(r.read().decode("utf-8", errors="replace"))
    sys_msg = next(
        (m.get("content", "") for m in (a.get("model") or {}).get("messages", [])
         if m.get("role") == "system"),
        "",
    )
    missing: list[str] = []
    for sentinel, scenario in SYSTEM_PROMPT_REQUIRED_SENTINELS:
        if sentinel not in sys_msg:
            missing.append(f"sentinel {sentinel!r} -> {scenario}")
    return missing


def fetch_calls(api_key: str, assistant_id: str, limit: int) -> list[dict]:
    url = f"https://api.vapi.ai/call?assistantId={assistant_id}&limit={limit}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "vapi-audit/0.3.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def find_forbidden_in_text(text: str) -> list[str]:
    return [tag for rx, tag in FORBIDDEN if rx.search(text or "")]


def grade_call(c: dict) -> dict:
    findings: list[str] = []
    severity = "PASS"

    ended = (c.get("endedReason") or "").lower()
    if ended in ERROR_END_REASONS:
        findings.append(f"endedReason={ended} (runtime crash, caller heard silence)")
        severity = "FAIL"

    bot_turns: list[str] = []
    for m in c.get("messages") or []:
        if (m.get("role") or "").lower() == "bot":
            txt = m.get("message") or ""
            bot_turns.append(txt)
            for tag in find_forbidden_in_text(txt):
                findings.append(f"forbidden({tag}) in bot turn: {txt[:160]!r}")
                severity = "FAIL"
            if FILLER_ANYWHERE.search(txt):
                findings.append(f"filler phrase in bot turn (forbidden): {txt[:160]!r}")
                if severity != "FAIL":
                    severity = "WARN"

    # Eager-tool-call detection (the 2026-06-30 11:47 production bug). list_slots
    # must NOT fire before the caller has given first_name + last_name + confirmed
    # phone. Heuristic: walk messages in order; count user turns BEFORE the first
    # list_slots tool_calls message; require >= 4 user turns AND an affirmation
    # ("yes", "yeah", "correct") between the last digit-dictation and the tool call.
    user_turns_before_ls = 0
    saw_phone_confirmation = False
    fired_ls_early = False
    for m in c.get("messages") or []:
        role = (m.get("role") or "").lower()
        if role == "user":
            user_turns_before_ls += 1
            content = (m.get("message") or "").lower()
            if user_turns_before_ls >= 4 and any(
                w in content for w in ("yes", "yeah", "yep", "correct", "right")
            ):
                saw_phone_confirmation = True
        elif role == "tool_calls":
            for tc in m.get("toolCalls") or []:
                if (tc.get("function") or {}).get("name") == "list_slots":
                    if user_turns_before_ls < 4 or not saw_phone_confirmation:
                        fired_ls_early = True
                    break
            if fired_ls_early:
                break
    if fired_ls_early:
        findings.append(
            f"EAGER list_slots: fired after only {user_turns_before_ls} user turn(s), "
            f"phone_confirmed={saw_phone_confirmation} -- 2026-06-30 bug class."
        )
        severity = "FAIL"

    # Mojibake check on tool results (would indicate the worker leaked non-ASCII).
    for m in c.get("messages") or []:
        if (m.get("role") or "").lower() == "tool_call_result":
            blob = json.dumps(m.get("result") or {}, ensure_ascii=False)
            try:
                for b in blob.encode("utf-8"):
                    if b >= 0x80:
                        findings.append(f"non-ASCII byte 0x{b:02x} in tool result: {blob[:160]!r}")
                        severity = "FAIL"
                        break
            except UnicodeEncodeError:
                findings.append("tool result not encodable as UTF-8")
                severity = "FAIL"

    return {
        "id": c.get("id", "?"),
        "startedAt": c.get("startedAt"),
        "endedReason": c.get("endedReason"),
        "findings": findings,
        "severity": severity,
        "bot_turn_count": len(bot_turns),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--since-hours", type=int, default=24)
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if ANY call FAILs or WARNs (default: only on FAIL)")
    args = ap.parse_args()

    api_key = os.environ.get("VAPI_API_KEY")
    assistant_id = os.environ.get("VAPI_ASSISTANT_ID")
    if not api_key or not assistant_id:
        print("VAPI_API_KEY and VAPI_ASSISTANT_ID required", file=sys.stderr)
        return 2

    # Structural prompt-level audit first -- this is the gate for the 13 new
    # corpus scenarios that the deterministic acceptance simulator can't evaluate.
    print("structural audit: live system prompt vs corpus-scenario sentinels")
    try:
        missing_sentinels = audit_system_prompt(api_key, assistant_id)
    except urllib.error.HTTPError as exc:
        print(f"vapi GET /assistant HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
              file=sys.stderr)
        return 2
    structural_fail = 0
    if missing_sentinels:
        for m in missing_sentinels:
            print(f"FAIL  prompt missing {m}")
        structural_fail = len(missing_sentinels)
    else:
        print(f"PASS  all {len(SYSTEM_PROMPT_REQUIRED_SENTINELS)} corpus-scenario sentinels present in live prompt")
    print()

    try:
        calls = fetch_calls(api_key, assistant_id, args.limit)
    except urllib.error.HTTPError as exc:
        print(f"vapi API HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:200]}",
              file=sys.stderr)
        return 2

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
    recent = []
    for c in calls:
        started = c.get("startedAt")
        if not started:
            continue
        try:
            t = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t >= cutoff:
            recent.append(c)

    print(f"audit: {len(recent)} calls in the last {args.since_hours}h (of {len(calls)} fetched)")

    fail = warn = clean = 0
    for c in recent:
        g = grade_call(c)
        line = (
            f"{g['severity']:<4}  {g['startedAt']}  {g['id'][:20]}  "
            f"end={g['endedReason']}  ({g['bot_turn_count']} bot turns)"
        )
        print(line)
        for f in g["findings"]:
            print(f"      - {f}")
        if g["severity"] == "FAIL":
            fail += 1
        elif g["severity"] == "WARN":
            warn += 1
        else:
            clean += 1

    print(f"\nsummary: {clean} clean, {warn} warn, {fail} fail (of {len(recent)} in window); "
          f"{structural_fail} prompt sentinels missing")

    if fail > 0 or structural_fail > 0:
        return 1
    if args.strict and warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
