"""
description: Plan visual beats for a ProdCraft video. Feeds Whisper segments (text + start/end times) to Gemini 2.5 Flash, gets back a sequence of beats covering all segments, each classified as stock | diagram | text_card with a payload (search query, FLUX prompt, or card text). Resolves segment indices back to seconds for the Remotion composition.
inputs:
    CLI:
        --words PATH         words+segments JSON from prodcraft_transcribe.py (required)
        --voice-profile PATH voice profile JSON (default: .tmp/prodcraft/voice_profile.json) — used for style context
        --out PATH           output JSON (default: .tmp/prodcraft/visual_beats.json)
        --target-beats N     target beat count (default: 30; LLM may deviate ±5)
    Env:
        GEMINI_API_KEY       required
outputs:
    {out}                    {"beats": [{
                                  "id": "beat_001",
                                  "start_segment": 0, "end_segment": 2,
                                  "start_sec": 0.02, "end_sec": 5.4,
                                  "text": "...",
                                  "type": "stock|diagram|text_card",
                                  "stock_query": "..." | null,
                                  "diagram_prompt": "..." | null,
                                  "card_text": "..." | null,
                                  "rationale": "..."
                              }], "total_beats": N, "audio_duration_sec": float}
    .tmp/prodcraft/visual_beats_raw.txt   on JSON parse failure, debug dump
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
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visual_beats.json"
DEFAULT_VOICE_PROFILE = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_profile.json"
RAW_DEBUG_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visual_beats_raw.txt"

SYSTEM_PROMPT = (
    "You are a YouTube video editor planning visual beats for an educational PM video. "
    "You map narration segments to visuals. Return ONLY valid JSON — no prose, no markdown fences."
)

FLUX_STYLE_BASE = (
    "minimalist vector line illustration, dark navy blue gradient background, "
    "glowing soft white and teal accent lines, no text, no letters, no words, no labels, "
    "no characters, no symbols that look like writing, purely visual, clean geometric shapes, "
    "professional educational diagram style"
)

PROMPT_TEMPLATE = """You are the SHOWRUNNER + VISUAL EDITOR for a ProdCraft (PM-education) YouTube video.

The viewer's question every second is: "why am I watching this instead of just listening?" Your job is to make every visual TEACH something the audio alone cannot — a concept made concrete, an example shown, a structure made spatial. Generic stock photos of "person at laptop" are FORBIDDEN. Every beat must add educational signal.

NARRATION SEGMENTS (transcribed from recorded VO; you cannot change the words):
{segments_block}

AUDIO DURATION: {duration:.1f} seconds across {n_segments} segments.

Plan ~{target_beats} contiguous beats covering ALL segments end-to-end (no gaps). Each beat groups consecutive segments and gets ONE visual treatment.

FOUR beat types (pick the one that BEST teaches that moment):

1. "concept_card" — STRUCTURED TEACHING. Remotion renders a title + grid of labeled items (1-6 items). Best for:
   - Definitions broken into parts ("PRD = What + Why + Who" → 3 items)
   - Lists with labels ("Sections: Vision, Goals, Scope, User Stories" → 4 items)
   - Comparisons (concept A vs concept B → 2 items with sub-labels)
   - Acceptance criteria (3-5 checklist items)
   - Use this LIBERALLY — aim for ~30-40% of beats. This is the highest-information visual.

2. "text_card" — SINGLE PHRASE EMPHASIS. Remotion renders ONE large styled phrase. Best for:
   - Opening hook / closing CTA
   - Definitions stated as one sentence ("PRD: Conduit of Clarity")
   - Punchline-style takeaways
   - Use SPARINGLY (~15-25% of beats). card_text MUST be <= 7 words.

3. "diagram" — METAPHORICAL OR ABSTRACT ILLUSTRATION. FLUX.1 generates a wordless visual concept. Best for:
   - Metaphors ("conduit of clarity" → glowing pipeline carrying light)
   - Process flows shown as abstract shapes (request flowing into output)
   - Spatial concepts (hierarchy as a tree, scope as concentric circles)
   - FLUX CANNOT render text reliably — your prompt MUST be purely visual. Subject only; no labels, no callouts.
   - Use for ~20-25% of beats.

4. "stock" — CONTRETE REAL-WORLD ILLUSTRATION. Pexels photo of an actual relevant subject. Best for:
   - SPECIFIC artifacts: sticky-note PRD on whiteboard, paper wireframe, sketched user flow, post-it kanban board, design mockup on screen
   - User-centered moments: a customer using a product, a checkout button being clicked, a person reading a manual
   - Use SELECTIVELY (~20% of beats). Queries must be SPECIFIC (e.g. "sticky note wall planning" not "person thinking"; "wireframe sketch paper" not "team meeting").
   - FORBIDDEN queries: anything generic like "office", "laptop", "person thinking", "team", "meeting" — these are EXACTLY the wallpaper-grade boredom the viewer would close the tab over.

PAYLOAD SCHEMAS:

For concept_card:
  "concept_card": {{
      "title": "<title 3-7 words; what concept this card teaches>",
      "items": [
          {{"label": "<short label, 1-3 words>", "sub": "<optional one-line elaboration, <=8 words>"}}
      ]
  }}
  Items count: 1 to 6 (3-4 is the sweet spot for readability).

For text_card:
  "card_text": "<exact phrase, <=7 words>"

For diagram:
  "diagram_prompt": "<wordless visual concept, content-specific>. {flux_style}"
  Example: "a glowing translucent pipeline carrying small geometric tokens of light from left to right between two abstract platforms. {flux_style}"

For stock:
  "stock_query": "<2-5 specific words for Pexels search>"
  Good: "sticky note wall planning", "wireframe sketch paper", "post-it whiteboard brainstorm", "product mockup on screen", "checkout button mobile app"
  BAD: "team meeting", "person at laptop", "office workspace", "professional collaboration"

For every beat, also include:
  "rationale": "<one short sentence on why this visual deepens understanding of this narration>"

CONSTRAINTS (hard, not aspirational):
- Beats must be contiguous: beat[i].end_segment + 1 == beat[i+1].start_segment.
- First beat starts at segment 0. Last beat ends at segment {last_segment_idx}.
- AVERAGE beat duration MUST be 6.0-7.5 seconds. Total beats must be in the range [{min_beats}, {max_beats}].
- MAXIMUM single-beat duration: 10 seconds. If a single concept naturally runs longer in the narration, split it into 2 beats (e.g., concept_card with title + items, then a text_card with the takeaway).
- Never repeat the same beat type more than 2 in a row — VARY the visual treatment.
- Opening (~first 6s) is a hook — prefer text_card or concept_card.
- Closing (~last 6s) is a CTA — prefer text_card.
- When the narration introduces a STRUCTURED concept ("the what, why, and who" / "vision, goals, scope" / "user flows, design specs, acceptance criteria") → use concept_card. ALWAYS.
- When the narration gives an EXAMPLE ("add to cart feature") → either stock (specific real example) or concept_card showing the example's structure.

Return JSON with this schema ONLY (no prose, no fences):

{{
  "beats": [
    {{
      "start_segment": 0,
      "end_segment": 1,
      "type": "concept_card",
      "stock_query": null,
      "diagram_prompt": null,
      "card_text": null,
      "concept_card": {{
        "title": "What's in a PRD?",
        "items": [
          {{"label": "What", "sub": "Vision, scope, features"}},
          {{"label": "Why", "sub": "Goals, problem solved"}},
          {{"label": "Who", "sub": "User personas, stakeholders"}}
        ]
      }},
      "rationale": "Makes the PRD's tri-part structure spatial; viewer learns the shape, not just the words."
    }}
  ]
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


def _format_segments(segments: list[dict]) -> str:
    lines = []
    for i, s in enumerate(segments):
        lines.append(f"[SEG_{i:02d}] {s['start']:6.2f}-{s['end']:6.2f}s | {s['text']}")
    return "\n".join(lines)


def _validate_beats(beats: list[dict], n_segments: int) -> None:
    if not beats:
        raise SystemExit("LLM returned 0 beats.")
    # Contiguity + coverage check.
    if beats[0]["start_segment"] != 0:
        raise SystemExit(f"First beat must start at segment 0; got {beats[0]['start_segment']}.")
    if beats[-1]["end_segment"] != n_segments - 1:
        raise SystemExit(
            f"Last beat must end at segment {n_segments - 1}; got {beats[-1]['end_segment']}."
        )
    for i, b in enumerate(beats):
        if b["start_segment"] > b["end_segment"]:
            raise SystemExit(f"Beat {i}: start_segment > end_segment.")
        if i > 0 and beats[i]["start_segment"] != beats[i - 1]["end_segment"] + 1:
            raise SystemExit(
                f"Beat {i} non-contiguous: prev end={beats[i-1]['end_segment']}, "
                f"this start={beats[i]['start_segment']}."
            )
        t = b.get("type")
        if t not in ("stock", "diagram", "text_card", "concept_card"):
            raise SystemExit(f"Beat {i}: unknown type {t!r}.")
        if t == "stock" and not b.get("stock_query"):
            raise SystemExit(f"Beat {i}: type=stock requires stock_query.")
        if t == "diagram" and not b.get("diagram_prompt"):
            raise SystemExit(f"Beat {i}: type=diagram requires diagram_prompt.")
        if t == "text_card":
            ct = b.get("card_text") or ""
            if not ct:
                raise SystemExit(f"Beat {i}: type=text_card requires card_text.")
            if len(ct.split()) > 8:
                print(f"WARN: beat {i} card_text > 8 words: {ct!r}", file=sys.stderr)
        if t == "concept_card":
            cc = b.get("concept_card") or {}
            if not cc.get("title"):
                raise SystemExit(f"Beat {i}: type=concept_card requires concept_card.title.")
            items = cc.get("items") or []
            if not (1 <= len(items) <= 6):
                raise SystemExit(f"Beat {i}: concept_card.items must have 1-6 entries; got {len(items)}.")
            for j, it in enumerate(items):
                if not it.get("label"):
                    raise SystemExit(f"Beat {i}: concept_card.items[{j}] missing label.")


def _resolve_timings(beats: list[dict], segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for i, b in enumerate(beats):
        s_idx = b["start_segment"]
        e_idx = b["end_segment"]
        start_sec = segments[s_idx]["start"]
        end_sec = segments[e_idx]["end"]
        text = " ".join(segments[idx]["text"] for idx in range(s_idx, e_idx + 1)).strip()
        out.append({
            "id": f"beat_{i:03d}",
            "start_segment": s_idx,
            "end_segment": e_idx,
            "start_sec": round(start_sec, 3),
            "end_sec": round(end_sec, 3),
            "duration_sec": round(end_sec - start_sec, 3),
            "text": text,
            "type": b["type"],
            "stock_query": b.get("stock_query"),
            "diagram_prompt": b.get("diagram_prompt"),
            "card_text": b.get("card_text"),
            "concept_card": b.get("concept_card"),
            "rationale": b.get("rationale", ""),
        })
    return out


def plan_beats(words_json: Path, voice_profile_path: Path, out_path: Path, target_beats: int) -> dict:
    from google.genai import types as genai_types

    data = json.loads(words_json.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    if not segments:
        raise SystemExit(f"No segments in {words_json}.")
    duration = data.get("duration_sec", 0)

    client = _gemini_client()
    prompt = PROMPT_TEMPLATE.format(
        segments_block=_format_segments(segments),
        duration=duration,
        n_segments=len(segments),
        last_segment_idx=len(segments) - 1,
        target_beats=target_beats,
        min_beats=max(20, target_beats - 4),
        max_beats=target_beats + 6,
        flux_style=FLUX_STYLE_BASE,
    )
    print(f"  Gemini prompt size: {len(prompt):,} chars", file=sys.stderr)

    # Retry loop for free-tier flakiness (RemoteProtocolError disconnects).
    last_err: Exception | None = None
    response = None
    for attempt in range(1, 5):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[genai_types.Part.from_text(text=prompt)],
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.4,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=2048),
                ),
            )
            break
        except Exception as exc:
            last_err = exc
            print(f"  Gemini attempt {attempt}/4 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            import time as _t
            _t.sleep(2 * attempt)
    if response is None:
        raise SystemExit(f"Gemini call failed after 4 attempts. Last error: {last_err}")
    raw = (response.text or "").strip()
    if not raw:
        raise SystemExit("Empty response from Gemini.")
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if lines[-1].strip().startswith("```") else "\n".join(lines[1:])
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        RAW_DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
        RAW_DEBUG_PATH.write_text(raw, encoding="utf-8")
        raise SystemExit(
            f"Gemini returned non-JSON. Raw saved to {RAW_DEBUG_PATH}. Error: {exc}"
        ) from exc

    beats_raw = parsed.get("beats", [])
    _validate_beats(beats_raw, len(segments))
    beats = _resolve_timings(beats_raw, segments)

    avg_dur = sum(b["duration_sec"] for b in beats) / len(beats)
    max_dur = max(b["duration_sec"] for b in beats)
    if avg_dur > 9.0 or max_dur > 14.0:
        print(
            f"WARN: beat pacing off — avg={avg_dur:.1f}s max={max_dur:.1f}s "
            f"(target avg 6-7s, max <=10s). Keeping result but flag for re-plan.",
            file=sys.stderr,
        )

    out = {
        "audio_duration_sec": duration,
        "total_segments": len(segments),
        "total_beats": len(beats),
        "beats": beats,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    type_counts = {}
    for b in beats:
        type_counts[b["type"]] = type_counts.get(b["type"], 0) + 1
    print(
        f"OK | beats | {len(beats)} beats | stock={type_counts.get('stock', 0)} "
        f"diagram={type_counts.get('diagram', 0)} text_card={type_counts.get('text_card', 0)} "
        f"| out={out_path}",
        file=sys.stderr,
    )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Plan visual beats from Whisper segments via Gemini.")
    p.add_argument("--words", required=True, help="words JSON from prodcraft_transcribe.py")
    p.add_argument("--voice-profile", default=str(DEFAULT_VOICE_PROFILE), help="(reserved for future use)")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output beats JSON")
    p.add_argument("--target-beats", type=int, default=30, help="Target beat count (LLM may deviate ±5)")
    args = p.parse_args()

    plan_beats(Path(args.words), Path(args.voice_profile), Path(args.out), args.target_beats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
