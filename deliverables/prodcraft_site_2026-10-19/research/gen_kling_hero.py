#!/usr/bin/env python3
"""Kling 3.0 (Higgsfield) hero footage for prodcraft.fyi v2 — thin wrapper over the GreenJobs script.

description: Adds a 'prodcraft' prompt to generate_hero_footage.PROMPTS and runs its estimate-first flow.
inputs: same flags as execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py; HF_API_TOKEN env.
outputs: <out>/prodcraft.mp4, prodcraft-m.mp4, prodcraft-poster.jpg, prodcraft.json
"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "execution/gtm_client_workflows/greenjobs_redesign"))
import generate_hero_footage as g  # noqa: E402

g.PROMPTS["prodcraft"] = (
    "Macro cinematic shot of a dark charcoal paper page in low warm light. Thin gold metallic ink lines "
    "slowly draw themselves across the page into a clean system diagram: small nodes connected by "
    "hairlines, a few nodes glowing softly, tiny gold particles drifting along the lines like data. "
    "Slow steady camera drift to the right, shallow depth of field, soft paper grain, no text, no "
    "letters, no logos, no people, no hands, minimal and calm, palette of charcoal black, bone white "
    "and muted gold, the lower third of the frame calm and uncluttered."
)
if not os.environ.get("HF_API_TOKEN") and os.environ.get("HIGGSFIELD_API_KEY"):
    os.environ["HF_API_TOKEN"] = os.environ["HIGGSFIELD_API_KEY"]
if "--edition" not in sys.argv:
    sys.argv += ["--edition", "prodcraft"]
sys.exit(g.main())
