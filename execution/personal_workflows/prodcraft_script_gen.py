"""
description: Generate a ProdCraft YouTube script via Gemini 2.5 Flash, conditioned on the distilled voice profile. Phase 0 = script.md only; full visual_beats.json comes in Phase 1.
inputs:
    Files: .tmp/prodcraft/voice_profile.json (from prodcraft_voice_profile.py)
    Env: GEMINI_API_KEY
    CLI:
        --topic "..."        topic to script (required)
        --length-sec N       target spoken duration in seconds (default 180 = 3 min)
        --source "..."       optional one-line source citation (Substack/Lenny/etc) to weave in
        --format NAME        one of voice_profile.structural_templates names (default: explainer-3-act)
        --out PATH           where to write (default .tmp/prodcraft/scripts/{slug}.md)
outputs:
    {out}                    script.md with YAML frontmatter (title, topic, format, duration) + body
    {out}.json               same content + structured beat breakdown for downstream tools
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_profile.json"
SCRIPTS_DIR = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "scripts"

SYSTEM_PROMPT = (
    "You are a ghostwriter for a YouTube creator. You write spoken scripts that sound EXACTLY like the creator. "
    "Return ONLY valid JSON — no prose, no markdown fences."
)

PROMPT_TEMPLATE = """You are ghostwriting a YouTube script for this creator. Match their voice EXACTLY — phrasing, energy, vocabulary, pacing.

CREATOR VOICE PROFILE:
{profile_json}

TOPIC: {topic}
TARGET SPOKEN DURATION: {length_sec} seconds (~{words} spoken words at ~150 wpm)
STRUCTURAL FORMAT: {fmt} (find this in structural_templates and follow its description)
{source_block}

CONSTRAINTS:
- Open with a hook in the creator's style (see hook_templates — match phrasing, NOT plagiarize verbatim).
- Use the creator's phrase_patterns naturally (at least 3-4 from the list, woven in).
- Use vocabulary_preferred terms; avoid vocabulary_avoided.
- Pacing: target avg sentence length of {avg_sent} words; favor "{pacing_favors}".
- Close with a CTA in the style of cta_templates.
- Must include ONE original framework or take that's the creator's own angle (not just summary of public knowledge). This is the "novel-take" anti-template defense for the YouTube July 2025 inauthentic-content policy.
- Make it CONVERSATIONAL — written to be SPOKEN aloud, not read.

Return a JSON object with EXACTLY this schema. No prose, no markdown fences.

{{
  "title": "YouTube-style title under 70 chars, with the creator's pattern",
  "topic": "the topic in their words",
  "format": "{fmt}",
  "estimated_duration_sec": N,
  "novel_take": "1-sentence statement of the original framework/take this script delivers",
  "hook": "exact opening 2-4 sentences",
  "body_beats": [
    {{"label": "Beat 1 name", "spoken_text": "what the creator says, conversational, ~{beat_words} words"}}
    // 3-7 beats total
  ],
  "cta": "exact closing 2-3 sentences",
  "full_script_md": "The complete spoken text as ONE block of markdown. Use paragraph breaks where the speaker pauses. No stage directions. No '[INSERT...]'. Ready to feed to TTS."
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


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return (s or "untitled")[:60]


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise SystemExit(f"{PROFILE_PATH} not found. Run prodcraft_voice_profile.py --build first.")
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def generate(topic: str, length_sec: int, fmt: str, source: str | None) -> dict:
    from google.genai import types as genai_types
    client = _gemini_client()
    profile = load_profile()
    words_total = int(length_sec * 150 / 60)  # ~150 wpm for natural pace
    avg_sent = profile.get("pacing_norms", {}).get("avg_sentence_len_words", 18)
    pacing_favors = profile.get("pacing_norms", {}).get("favors", "medium-paragraph")
    beat_words = max(50, words_total // 5)  # rough beat target
    source_block = f"SOURCE TO WEAVE IN (cite naturally): {source}" if source else "SOURCE: (none — pure original frame)"

    prompt = PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile, indent=2, ensure_ascii=False),
        topic=topic,
        length_sec=length_sec,
        words=words_total,
        fmt=fmt,
        avg_sent=avg_sent,
        pacing_favors=pacing_favors,
        beat_words=beat_words,
        source_block=source_block,
    )
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
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if lines[-1].strip().startswith("```") else "\n".join(lines[1:])
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        debug_path = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "script_gen_raw.txt"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(raw, encoding="utf-8")
        raise SystemExit(
            f"Gemini returned non-JSON. Raw output saved to {debug_path}. Error: {exc}"
        ) from exc


def cmd_run(args: argparse.Namespace) -> int:
    print(f"Generating script | topic={args.topic!r} | length={args.length_sec}s | format={args.format}", file=sys.stderr)
    script = generate(args.topic, args.length_sec, args.format, args.source)

    out_path = Path(args.out) if args.out else SCRIPTS_DIR / f"{slugify(args.topic)}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Markdown with YAML frontmatter (for human reading + downstream tooling)
    frontmatter = (
        "---\n"
        f"title: {script.get('title', '')}\n"
        f"topic: {script.get('topic', args.topic)}\n"
        f"format: {script.get('format', args.format)}\n"
        f"estimated_duration_sec: {script.get('estimated_duration_sec', args.length_sec)}\n"
        f"novel_take: {script.get('novel_take', '')}\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"voice_profile: .tmp/prodcraft/voice_profile.json\n"
        "---\n\n"
    )
    body = script.get("full_script_md", "").strip() + "\n"
    out_path.write_text(frontmatter + body, encoding="utf-8")

    json_path = out_path.with_suffix(".md.json")
    json_path.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")

    word_count = len(body.split())
    print(f"\nOK | script: {out_path}", file=sys.stderr)
    print(f"OK | structured: {json_path}", file=sys.stderr)
    print(f"     title: {script.get('title', '')}", file=sys.stderr)
    print(f"     novel_take: {script.get('novel_take', '')}", file=sys.stderr)
    print(f"     word_count: {word_count} (target ~{int(args.length_sec * 150 / 60)})", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft script generator (Gemini, voice-profile-conditioned)")
    p.add_argument("--topic", required=True, help="What the script is about")
    p.add_argument("--length-sec", type=int, default=180, help="Target spoken duration in seconds")
    p.add_argument("--format", default="explainer-3-act", help="Structural template name (see voice_profile.structural_templates)")
    p.add_argument("--source", default=None, help="Optional source citation to weave in")
    p.add_argument("--out", default=None, help="Output path (default .tmp/prodcraft/scripts/{slug}.md)")
    args = p.parse_args()
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
