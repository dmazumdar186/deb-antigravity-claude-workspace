#!/usr/bin/env python3
"""
Live 5-turn flow simulator against the deployed AgentUp API.

Simulates what the browser does end-to-end:
  1. Opening bubble (from case).
  2. Agent turn 1  →  POST /api/claude mode=roleplay  →  Customer reply 1.
  3. Agent turn 2  →  POST /api/claude mode=roleplay  →  Customer reply 2.
  4. Agent turn 3  →  POST /api/claude mode=roleplay  →  Customer reply 3.
  5. Agent turn 4  →  POST /api/claude mode=roleplay  →  Customer reply 4.
  6. Agent turn 5  →  POST /api/claude mode=roleplay  →  Customer reply 5.  ← must exist
  7. POST /api/claude mode=score with full transcript → scorecard.

Passes when: exactly 5 AI-generated customer replies are received AND the
scorecard returns a valid overall score in [0,100].

Usage:  py tests/live_5_turn_flow.py [--base https://agentup-iag.pages.dev]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


SCENARIO = "Customer has been without internet for four days. Third call about the same outage."
OPENING = "This is the third time I'm calling. Nobody has fixed this. I want to cancel and I want a full refund. Now."
DIFFICULTY = "Advanced"

AGENT_TURNS = [
    "I completely understand your frustration, and I'm truly sorry for what you've been through. Let me pull up your account right now.",
    "I can see all three prior tickets. This has taken far too long. I'm escalating this to our field-services lead directly, right now.",
    "Our field team can be at your address between 2 PM and 4 PM today. As a gesture of goodwill I'm also crediting three days of service back to your account.",
    "You'll receive a confirmation email within the next ten minutes with the technician's name, ETA, and a direct number if anything shifts.",
    "Once the fix is verified today I'll personally call you back to confirm everything is stable. Would 5 PM work for that follow-up?",
]


def post_json(url, payload, timeout=90):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": url.rsplit("/api/", 1)[0],
            "User-Agent": "AgentUp-5-Turn-Live/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://agentup-iag.pages.dev")
    args = ap.parse_args()
    url = args.base.rstrip("/") + "/api/claude"

    print(f"Live 5-turn flow  |  target: {args.base}")
    print("=" * 70)

    transcript = [{"role": "customer", "text": OPENING}]
    ai_replies_seen = 0
    all_ok = True

    for i, agent_text in enumerate(AGENT_TURNS, start=1):
        transcript.append({"role": "agent", "text": agent_text})
        history = transcript[1:]  # exclude opening (server treats it separately)
        print(f"\n[Agent turn {i} sent | history len={len(history)}]")
        try:
            t0 = time.time()
            r = post_json(url, {
                "mode": "roleplay",
                "scenario": SCENARIO,
                "opening": OPENING,
                "difficulty": DIFFICULTY,
                "history": history,
            })
            dt = int((time.time() - t0) * 1000)
            text = r.get("text", "").strip()
            provider = r.get("provider", "?")
            if not text:
                print(f"  FAIL — empty AI reply (provider={provider}, {dt}ms)")
                all_ok = False
                break
            transcript.append({"role": "customer", "text": text})
            ai_replies_seen += 1
            print(f"  PASS — AI reply {ai_replies_seen}/5  ({provider}, {dt}ms)")
            print(f"    \"{text[:110]}{'...' if len(text) > 110 else ''}\"")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"  FAIL — HTTP error on turn {i}: {type(e).__name__}: {e}")
            all_ok = False
            break
        time.sleep(0.4)

    print("")
    print("=" * 70)
    print(f"AI replies received: {ai_replies_seen} / 5   (need 5)")
    print(f"Final transcript length: {len(transcript)}  (should be 11: opening + 5 agent + 5 AI)")

    if ai_replies_seen != 5:
        print("FAIL — did not receive 5 AI replies")
        return 1
    if len(transcript) != 11:
        print(f"FAIL — transcript length wrong (got {len(transcript)}, want 11)")
        return 1

    print("\n[Scoring the full 11-message transcript...]")
    try:
        s = post_json(url, {
            "mode": "score",
            "scenario": SCENARIO,
            "difficulty": DIFFICULTY,
            "transcript": transcript,
        })
        overall = int(s.get("overallScore", -1))
        provider = s.get("_provider", "?")
        if not (0 <= overall <= 100):
            print(f"FAIL — invalid overallScore: {overall}")
            return 1
        print(f"  PASS — overall={overall}/100  ({provider})")
        print(f"    strength: {s.get('strength', '')[:100]}")
        print(f"    improvement: {s.get('improvement', '')[:100]}")
        if s.get("perTurnNotes"):
            print(f"    perTurnNotes: {len(s['perTurnNotes'])} notes (should be 5 — one per agent turn)")
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"FAIL — scoring failed: {type(e).__name__}: {e}")
        return 1

    print("\nLIVE 5-TURN FLOW: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
