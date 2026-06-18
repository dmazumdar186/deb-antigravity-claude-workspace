"""
description: Full Living PRD doc-ops plan for the entire Phase 1 PRD video (~2:27 of v1 audio). Hand-authored, anchored to actual word-timing JSON of phase1_audio_words.json. Six sections cover the script end-to-end with a final outro CTA.

This is the production plan (the POC plan is in prodcraft_living_prd_plan_poc.py).

inputs:
    CLI:
        --out PATH       output JSON (default: .tmp/prodcraft/living_prd_plan.json)
        --duration FLOAT total duration in seconds (default: 148; matches v1 audio)
outputs:
    {out}                JSON conforming to LivingPRDPlan in living-prd/types.ts
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "living_prd_plan.json"


def build_plan(duration_sec: float) -> dict:
    return {
        "doc_title": "How to Write a Product Requirements Document",
        "doc_subtitle": "A foundational guide for new and aspiring PMs",
        "audio_duration_sec": duration_sec,
        "ops": [
            # ---- Title (0.5s) ----
            {"t": 0.5, "op": "title_in",
             "title": "How to Write a Product Requirements Document"},

            # ---- Section 1: What is a PRD? (t=8, body 14-21) ----
            {"t": 7.5, "op": "add_section", "id": "definition", "title": "What is a PRD?"},
            {"t": 14.5, "op": "typewriter_lines",
             "id": "definition",
             "body_style": "paragraph",
             "lines": [
                 "A foundational document that outlines the what, why, and who of a product or specific feature.",
             ],
             "end_t": 21.0},

            # ---- Section 2: The Three Pillars (t=22, list 23-29) ----
            {"t": 21.5, "op": "add_section", "id": "pillars", "title": "The Three Pillars"},
            {"t": 22.5, "op": "typewriter_lines",
             "id": "pillars",
             "body_style": "list",
             "lines": [
                 "What — vision, scope, features",
                 "Why — goals, problems solved",
                 "Who — users, stakeholders",
             ],
             "end_t": 29.0},
            {"t": 30.0, "op": "highlight_section", "id": "pillars"},

            # ---- Section 3: Conduit of Clarity (t=32, body 35-50) ----
            {"t": 32.0, "op": "add_section", "id": "conduit", "title": "PRD = the Conduit of Clarity"},
            {"t": 34.5, "op": "typewriter_lines",
             "id": "conduit",
             "body_style": "paragraph",
             "lines": [
                 "Not a static document. A living channel that bridges high-level vision and execution detail — aligning engineering, design, marketing, and sales.",
             ],
             "end_t": 53.0},
            {"t": 53.5, "op": "highlight_section", "id": "conduit"},

            # ---- Section 4: What's Inside a PRD? (t=58, checklist 60-84) ----
            {"t": 57.5, "op": "add_section", "id": "inside", "title": "What's Inside a PRD?"},
            {"t": 60.0, "op": "checklist",
             "id": "inside",
             "items": [
                 "Vision, goals, scope",
                 "Features, user stories, acceptance criteria",
                 "Success KPIs (activation, retention, error rate)",
                 "Target users + stakeholder map",
                 "High-level timeline & phasing",
             ],
             "end_t": 84.0},

            # ---- Section 5: Example - Add to Cart (t=85, list 87-96) ----
            {"t": 84.5, "op": "add_section", "id": "example", "title": "Example: \"Add to Cart\""},
            {"t": 86.0, "op": "typewriter_lines",
             "id": "example",
             "body_style": "list",
             "lines": [
                 "User flows — happy path + edge cases",
                 "Error rates and recovery",
                 "Graceful fallbacks when things break",
             ],
             "end_t": 96.5},

            # ---- Section 6: Living Document + Tips (t=98, body+list 100-128) ----
            {"t": 97.5, "op": "add_section", "id": "evolution", "title": "PRDs Evolve. Tips for New PMs."},
            {"t": 100.0, "op": "typewriter_lines",
             "id": "evolution",
             "body_style": "list",
             "lines": [
                 "Concise, clear, user-centric — avoid jargon",
                 "Focus on the WHAT and WHY, leave HOW to engineering",
                 "Involve stakeholders early and often",
                 "Use it as your communication + prioritization tool",
             ],
             "end_t": 128.0},
            {"t": 128.5, "op": "highlight_section", "id": "evolution"},

            # ---- Section 7: Closing CTA (text_card style via final highlight + new section) ----
            {"t": 134.0, "op": "add_section", "id": "cta", "title": "Like, Share, Subscribe."},
            {"t": 135.0, "op": "typewriter_lines",
             "id": "cta",
             "body_style": "paragraph",
             "lines": [
                 "Questions? Drop them in the comments. Hit the bell to never miss a ProdCraft drop.",
             ],
             "end_t": 146.5},
            {"t": 146.0, "op": "highlight_section", "id": "cta"},
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Full Living PRD plan for Phase 1 video.")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--duration", type=float, default=148.0)
    args = p.parse_args()
    plan = build_plan(args.duration)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"OK | living_prd_plan FULL | {len(plan['ops'])} ops | {plan['audio_duration_sec']}s | out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
