"""
description: Distill ingested ProdCraft transcripts into a SCRIPT-WRITING voice profile (different shape from execution/modules/creator_profiles.py which is for analyzer use). One Gemini 2.5 Flash call, free tier.
inputs:
    Files: .tmp/prodcraft/videos/*.json (from youtube_channel_ingest.py --mode ingest)
    Env: GEMINI_API_KEY (required)
    CLI:
        --build        run distillation (default action)
        --show         print existing profile to stdout
        --min-chars N  only feed transcripts with >= N chars to the distiller (default 500)
outputs:
    .tmp/prodcraft/voice_profile.json     distilled style guide
    .tmp/prodcraft/voice_profile_raw.txt  on JSON parse failure, the raw LLM output for debug
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
VIDEOS_DIR = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "videos"
PROFILE_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_profile.json"
RAW_DEBUG_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_profile_raw.txt"

SYSTEM_PROMPT = (
    "You are a voice/style analyst for content creators. Return ONLY valid JSON — "
    "no prose, no markdown fences. Be specific and grounded in the provided transcripts."
)

PROMPT_TEMPLATE = """You are analyzing the voice and content style of a YouTube creator who makes PM-education videos. \
You will see {n} of their transcripts. Distill an actionable VOICE PROFILE that a writer can use to draft new scripts in this creator's voice.

Channel: {channel}

Transcripts:
{block}

Return a JSON object with EXACTLY this schema. No prose, no markdown fences.

{{
  "voice_signature": "2-3 sentence description capturing tone, persona, perspective, energy level",
  "audience": "1-sentence description of who this creator addresses",
  "topic_areas": ["5-10 PM topics this creator clearly covers based on transcripts"],
  "hook_templates": ["3-5 example opening lines that EXACTLY match this creator's style — phrasing, energy, structure"],
  "structural_templates": [
    {{"name": "explainer-3-act|listicle|opinion|q-and-a|other", "description": "shape and beat structure", "ideal_length_sec": N}}
  ],
  "phrase_patterns": ["5-10 recurring phrases or transitions this creator uses, verbatim if possible"],
  "vocabulary_preferred": ["PM jargon this creator confidently uses"],
  "vocabulary_avoided": ["PM jargon they could use but don't — stylistic choice signals"],
  "pacing_norms": {{"avg_sentence_len_words": N, "favors": "short and punchy | medium-paragraph | long-explanatory"}},
  "cta_templates": ["2-3 example closing CTAs in their style"],
  "sample_paragraph": "One ~150-word paragraph YOU write that sounds exactly like this creator would speak it, on the topic 'How to write a good user story'. This is the WRITER'S NORTH STAR — must pass a blind authenticity check."
}}
"""


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in .env")
    try:
        from google import genai
    except ImportError as e:
        raise SystemExit("Run: py -m pip install google-genai") from e
    return genai.Client(api_key=api_key)


def load_transcripts(min_chars: int) -> tuple[str, list[dict]]:
    if not VIDEOS_DIR.exists():
        raise SystemExit(f"{VIDEOS_DIR} not found. Run youtube_channel_ingest.py first.")
    all_t: list[dict] = []
    for p in sorted(VIDEOS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        all_t.append(data)
    if not all_t:
        raise SystemExit("No transcripts found in .tmp/prodcraft/videos/.")
    long_t = [t for t in all_t if t.get("transcript_chars", 0) >= min_chars]
    if not long_t:
        print(
            f"No transcripts >= {min_chars} chars; falling back to all {len(all_t)} (Shorts only?)",
            file=sys.stderr,
        )
        long_t = all_t
    return "Debanjan Mazumdar / @ProdCraft", long_t


def distill(channel: str, transcripts: list[dict]) -> dict:
    from google.genai import types as genai_types
    client = _gemini_client()
    block = "\n\n---\n\n".join(
        f"## {t.get('title', '')} ({t.get('view_count', 0):,} views, {t.get('transcript_chars', 0)} chars)\n{t.get('transcript', '')}"
        for t in transcripts
    )
    prompt = PROMPT_TEMPLATE.format(n=len(transcripts), channel=channel, block=block)
    print(f"  prompt size: {len(prompt):,} chars (~{len(prompt) // 4:,} tokens)", file=sys.stderr)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[genai_types.Part.from_text(text=prompt)],
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    if not raw:
        raise SystemExit("Empty response from Gemini.")
    # Belt-and-braces: strip markdown fences even though response_mime_type=application/json should prevent them.
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if lines[-1].strip().startswith("```") else "\n".join(lines[1:])
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        RAW_DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
        RAW_DEBUG_PATH.write_text(raw, encoding="utf-8")
        raise SystemExit(
            f"Gemini returned non-JSON. Raw output saved to {RAW_DEBUG_PATH}. Error: {exc}"
        ) from exc


def cmd_build(args: argparse.Namespace) -> int:
    channel, transcripts = load_transcripts(args.min_chars)
    total_chars = sum(t.get("transcript_chars", 0) for t in transcripts)
    print(
        f"Distilling voice profile from {len(transcripts)} transcripts "
        f"({total_chars:,} chars total)...",
        file=sys.stderr,
    )
    profile = distill(channel, transcripts)
    if not profile or not profile.get("voice_signature"):
        raise SystemExit(
            f"Distillation returned an unusable profile (missing voice_signature). "
            f"Raw keys: {list(profile.keys()) if isinstance(profile, dict) else type(profile).__name__}. "
            f"Refusing to write a hollow profile that would silently break downstream script generation."
        )
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK | voice profile written to {PROFILE_PATH}", file=sys.stderr)
    # Tiny summary so the operator can sanity-check at a glance.
    sig = (profile.get("voice_signature") or "")[:200]
    sample = (profile.get("sample_paragraph") or "")[:200]
    print(f"\n--- voice_signature (truncated) ---\n{sig}\n", file=sys.stderr)
    print(f"--- sample_paragraph (first 200 chars) ---\n{sample}...\n", file=sys.stderr)
    return 0


def cmd_show(_args: argparse.Namespace) -> int:
    if not PROFILE_PATH.exists():
        raise SystemExit(f"{PROFILE_PATH} not found. Run with --build first.")
    sys.stdout.write(PROFILE_PATH.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft voice profile distillation (Gemini 2.5 Flash, free tier)")
    p.add_argument("--build", action="store_true", help="Distill voice profile (default action)")
    p.add_argument("--show", action="store_true", help="Print existing profile to stdout")
    p.add_argument("--min-chars", type=int, default=500, help="Only feed transcripts with >= N chars (default 500)")
    args = p.parse_args()
    if args.show:
        return cmd_show(args)
    return cmd_build(args)


if __name__ == "__main__":
    raise SystemExit(main())
