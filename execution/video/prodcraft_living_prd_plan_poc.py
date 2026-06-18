"""
description: Doc-ops plan generator for the Living PRD POC. Reads the v3 word-timings JSON, finds semantic anchor phrases in the actual transcript, and emits a plan whose ops are aligned to where those phrases land in audio time. Robust against re-renders that shift timestamps.
inputs:
    CLI:
        --words PATH     word-timings JSON from prodcraft_transcribe.py
        --out PATH       output plan JSON
        --duration FLOAT POC duration in seconds (default: 55)
outputs:
    {out}                living_prd_plan.json conforming to types.ts
    Also prints the anchor-to-timestamp map for debugging
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORDS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_audio_v3_words.json"
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "living_prd_plan.json"


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower())


def find_phrase_time(
    segments: list[dict],
    phrase: str,
    which: str = "start",
    after_t: float = 0.0,
) -> float:
    """Find the start/end time of the first segment whose text contains `phrase` (normalized), starting search after `after_t`.

    which: "start" (segment start) | "end" (segment end) | "mid" (midpoint)
    """
    norm_phrase = _normalize(phrase)
    for seg in segments:
        if seg["start"] < after_t:
            continue
        if norm_phrase in _normalize(seg["text"]):
            if which == "start":
                return float(seg["start"])
            if which == "end":
                return float(seg["end"])
            return (float(seg["start"]) + float(seg["end"])) / 2.0
    raise SystemExit(f"Phrase {phrase!r} not found in any segment after t={after_t}.")


def build_plan(words_data: dict, duration_sec: float) -> tuple[dict, dict]:
    segments = words_data["segments"]

    # Semantic anchors against the actual narration.
    anchors = {
        "ask_question_end": find_phrase_time(segments, "exactly is", "end"),
        "definition_start": find_phrase_time(segments, "simply put", "start"),
        "definition_what_why_who": find_phrase_time(segments, "what why and who", "end"),
        "blueprint_or_features": find_phrase_time(segments, "blueprint", "start", after_t=20.0),
        "consolidate": find_phrase_time(segments, "consolidate", "start", after_t=25.0),
        "outset": find_phrase_time(segments, "outset", "end", after_t=35.0),
        "why_question": find_phrase_time(segments, "why do we need", "start", after_t=35.0),
        "conduit_phrase": find_phrase_time(segments, "conduit", "start", after_t=45.0),
        "living_channel": find_phrase_time(segments, "living channel", "start", after_t=50.0),
    }

    # Plan: 4 sections fit into ~55s with comfortable pacing.
    ops = [
        # Title fades in over the opening greeting.
        {"t": 0.5, "op": "title_in",
         "title": "How to Write a Product Requirements Document"},

        # Section 1: "What is a PRD?" — landed when he asks the question.
        {"t": max(0.5, anchors["ask_question_end"] - 0.5), "op": "add_section",
         "id": "definition", "title": "What is a PRD?"},

        # Definition typewriter: starts when he says "simply put", ends when he hits "what why and who".
        {"t": anchors["definition_start"], "op": "typewriter_lines",
         "id": "definition",
         "body_style": "paragraph",
         "lines": [
             "A foundational document that outlines the what, why, and who of a product or specific feature.",
         ],
         "end_t": min(duration_sec, anchors["definition_what_why_who"] + 0.5)},

        # Section 2: "Why It Exists" — when he transitions to consolidation/stakeholders.
        {"t": anchors["consolidate"] - 0.5, "op": "add_section",
         "id": "why_exists", "title": "Why It Exists"},

        # Why-exists checklist: items revealed as he enumerates.
        {"t": anchors["consolidate"], "op": "checklist",
         "id": "why_exists",
         "items": [
             "Consolidates all requirements",
             "Aligns engineering, design, marketing",
             "One source of truth for the team",
         ],
         "end_t": anchors["outset"] + 0.5},

        # Highlight why_exists when he finishes the section.
        {"t": anchors["outset"] + 0.6, "op": "highlight_section", "id": "why_exists"},

        # Section 3: "PRD = the Conduit of Clarity" — his novel framing.
        {"t": anchors["why_question"] - 0.3, "op": "add_section",
         "id": "conduit", "title": "PRD = the Conduit of Clarity"},

        # Conduit typewriter: starts when he says "conduit", lands the key insight.
        {"t": anchors["conduit_phrase"] - 0.3, "op": "typewriter_lines",
         "id": "conduit",
         "body_style": "paragraph",
         "lines": [
             "Not a static document. A living channel that bridges high-level vision and execution detail.",
         ],
         "end_t": min(duration_sec, anchors["living_channel"] + 4.0)},

        # Final highlight on the conduit framing.
        {"t": min(duration_sec - 1.0, anchors["living_channel"] + 4.2), "op": "highlight_section",
         "id": "conduit"},
    ]

    plan = {
        "doc_title": "How to Write a Product Requirements Document",
        "doc_subtitle": "A foundational guide for new and aspiring PMs",
        "audio_duration_sec": duration_sec,
        "ops": ops,
    }
    return plan, anchors


def main() -> int:
    p = argparse.ArgumentParser(description="Build Living PRD POC plan anchored to actual v3 word timings.")
    p.add_argument("--words", default=str(DEFAULT_WORDS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--duration", type=float, default=55.0)
    args = p.parse_args()

    words_data = json.loads(Path(args.words).read_text(encoding="utf-8"))
    plan, anchors = build_plan(words_data, args.duration)

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print("Anchors (audio-time mapping):")
    for name, t in anchors.items():
        print(f"  {name:30s} t={t:6.2f}s")
    print()
    print(f"OK | living_prd_plan | {len(plan['ops'])} ops | {plan['audio_duration_sec']}s | out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
