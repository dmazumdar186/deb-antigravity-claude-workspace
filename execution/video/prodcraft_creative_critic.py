"""
description: World-class critic for ProdCraft creative-plan videos. Renders sample stills
             across the scenes, feeds them + the plan + the script + word timings to
             Gemini 2.5 Flash (vision-capable, free), and returns structured per-scene
             critique JSON. The critic plays "Pixar lead reviewer" -- merciless on both
             artistic (composition, typography, animation principles) AND technical
             (word-timing sync, mobile legibility, element overlap, orphan motion) lenses.
inputs:
    CLI:
        --plan PATH            creative_plan.json
        --script PATH          script.md
        --words PATH           words.json
        --stills-dir PATH      where rendered sample stills live (1+ per scene)
        --out PATH             critique.json (default: .tmp/prodcraft/critique.json)
    env: GEMINI_API_KEY
outputs:
    {out}                     critique JSON with shape:
        {
          "verdict": "PASS" | "REVISE",
          "overall": "short paragraph",
          "scenes": [
            {
              "id": "...",
              "verdict": "PASS" | "REVISE",
              "score_artistic": 0-10,
              "score_technical": 0-10,
              "issues": ["..."],          // what's wrong
              "fixes": "string of critic notes to inject on reroll"
            }
          ]
        }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "critique.json"

# Pass threshold per scene. Both scores must clear OR the scene is marked REVISE.
PASS_ART_MIN = 7
PASS_TECH_MIN = 7

_SYSTEM = (
    "You are a senior animation lead at Pixar AND a senior brand reviewer at Apple. "
    "You critique educational explainer videos with two lenses: ARTISTIC (composition, "
    "typography, color, motion principles, brand fit) and TECHNICAL (word-timing sync, "
    "mobile-screen legibility, element overlap, motivated motion, animation density). "
    "You score brutally honestly on a 0-10 scale. 7 is the minimum SHIP bar; below 7 the "
    "scene must be rerolled. You always provide concrete, actionable fix notes -- never "
    "vague ('improve composition'), always specific ('the magnifying glass at right "
    "overlaps the user bubble; move it 200px right or replace with a flatter icon'). "
    "You return ONLY a single valid JSON object. No prose. No markdown fences."
)


def _gemini_client():
    from google import genai
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY required for critic")
    return genai.Client(api_key=api_key)


def _stills_for_scenes(stills_dir: Path, scenes: list[dict]) -> dict[str, list[Path]]:
    """Group still PNGs by scene id, ordered by frame number."""
    out: dict[str, list[Path]] = {}
    for s in scenes:
        out[s["id"]] = []
    pat = re.compile(r"crit_(?P<scene>[a-z0-9-]+)_(?P<frame>\d+)\.png", re.IGNORECASE)
    for p in sorted(stills_dir.glob("crit_*.png")):
        m = pat.match(p.name)
        if not m:
            continue
        sid = m.group("scene")
        if sid in out:
            out[sid].append(p)
    return out


def _build_user_prompt(plan: dict, script_body: str, words: list[dict]) -> str:
    timed_lines = []
    line_buf: list[dict] = []
    line_start = words[0]["start"] if words else 0
    for i, w in enumerate(words):
        line_buf.append(w)
        if w["w"].endswith((".", "!", "?")) or len(line_buf) >= 14:
            line_text = " ".join(x["w"] for x in line_buf)
            timed_lines.append(f"  [{line_start:5.1f}-{w['end']:5.1f}s] {line_text}")
            line_buf = []
            if i + 1 < len(words):
                line_start = words[i + 1]["start"]
    if line_buf:
        line_text = " ".join(x["w"] for x in line_buf)
        timed_lines.append(f"  [{line_start:5.1f}-{line_buf[-1]['end']:5.1f}s] {line_text}")
    narration_timed = "\n".join(timed_lines)

    scenes_block = []
    for s in plan["scenes"]:
        beats_lines = []
        for b in s.get("beats", []):
            beats_lines.append(
                f"      [{b['phrase_start_t']:5.1f}-{b['phrase_end_t']:5.1f}s] "
                f"\"{b['phrase']}\" -> {b['visual_action']}"
            )
        scenes_block.append(
            f"  SCENE id={s['id']!r}  t=[{s['start_t']:.1f},{s['end_t']:.1f}]  title={s['title']!r}\n"
            f"    visual_metaphor: {s['visual_metaphor']}\n"
            f"    hook: {s.get('hook', '')!r}\n"
            f"    {len(s.get('timeline', []))} keyframes; {len(s.get('beats', []))} beats:\n"
            + "\n".join(beats_lines)
        )
    plan_summary = "\n\n".join(scenes_block)

    return f"""You are reviewing a ProdCraft explainer video produced from a GLM-authored plan. The narration is FIXED -- you cannot ask to change what the speaker says. You can ONLY critique the visuals + animation + timing.

THE NARRATION (with word timing):
---
{narration_timed}
---

THE PLAN (one scene per stills group I'm about to attach):
{plan_summary}

I'm attaching 1-3 sample stills per scene (at strategic moments inside that scene). Critique each scene on TWO lenses:

ARTISTIC (0-10):
- Composition / staging (one focal point, balanced layout, ~80px breathing room)
- Typography (primary >=64px, secondary >=48px, tertiary >=36px -- on a mobile screen would you actually be able to read this?)
- Color discipline (page-light bg, navy text, teal accents only; no rainbow)
- Visual metaphor coherence (does the on-screen idea actually clarify the concept?)
- Motion principles (you can't see motion in a still, but you CAN see: is the layout designed to support animation, or just a static illustration?)
- Brand fit (modern flat motion-graphics, NOT stock-illustration, NOT 6th-grader, NOT early-2000s clip-art)

TECHNICAL (0-10):
- Element overlap / collisions
- Off-canvas elements (anything clipping the edge?)
- Density (5-9 elements; 10+ is cluttered, <4 is empty)
- Caption integration (is the bottom-center caption capsule competing with on-canvas content?)
- Word-timing fidelity (look at the beats list -- do the visual_actions actually correspond to what the narrator says during those windows? Mark any orphan motion or timing drift)
- Animation density appropriate (~25% of time moving, ~75% holding -- judge from keyframe count vs duration)

VERDICT RULE:
- PASS if BOTH score_artistic >= 7 AND score_technical >= 7.
- REVISE otherwise.

FIXES MUST BE SURGICAL. Bad: "make it better." Good: "the magnifying glass at (x=1500, y=200) overlaps the user-bubble text; relocate it to (x=1600, y=400) or replace with a 32px chevron-right glyph." Bad: "fonts too small." Good: "the 'YES'/'NO' toggle labels are around 22px; bump to 64px and the toggle pill grows to ~120x60px to match."

Be brutal. If a scene looks like a high-school PowerPoint, score it 4 and say exactly what feels powerpoint-y. If a scene is genuinely Pixar-grade, score 9-10 and say what makes it so. Your fixes feed back into a reroll loop, so the more specific you are the better the next iteration.

Return JSON with EXACTLY this shape (no prose, no fences):

{{
  "verdict": "PASS" | "REVISE",
  "overall": "1 paragraph overall reaction -- the unvarnished truth",
  "scenes": [
    {{
      "id": "scene-id",
      "verdict": "PASS" | "REVISE",
      "score_artistic": 0-10,
      "score_technical": 0-10,
      "issues": ["issue 1", "issue 2", ...],
      "fixes": "concrete, surgical reroll notes (one paragraph, addressed to the SVG author)"
    }}
  ]
}}"""


def critique(plan_path: Path, script_path: Path, words_path: Path, stills_dir: Path) -> dict:
    from google.genai import types as gtypes

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    script_raw = script_path.read_text(encoding="utf-8")
    # Strip frontmatter
    if script_raw.startswith("---"):
        end = script_raw.find("\n---", 4)
        script_body = script_raw[end + 4 :].lstrip("\n") if end >= 0 else script_raw
    else:
        script_body = script_raw
    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    words = words_data.get("words", [])

    scene_stills = _stills_for_scenes(stills_dir, plan["scenes"])
    missing = [sid for sid, paths in scene_stills.items() if not paths]
    if missing:
        print(f"WARN: no stills found for scenes: {missing}", file=sys.stderr)

    # Build the multimodal prompt: text first, then attach images per scene.
    user_text = _build_user_prompt(plan, script_body, words)
    parts: list = [gtypes.Part.from_text(text=user_text)]
    for sid in scene_stills:
        for p in scene_stills[sid]:
            # Tell the model which scene this still belongs to.
            parts.append(gtypes.Part.from_text(text=f"\n--- STILL for scene '{sid}' ({p.name}) ---"))
            data = p.read_bytes()
            parts.append(
                gtypes.Part.from_bytes(
                    data=data,
                    mime_type="image/png",
                )
            )

    client = _gemini_client()
    # Gemini 2.5 Flash on the free tier occasionally 503s on demand spikes.
    # Retry with backoff before giving up; reraise on the final attempt so the
    # pipeline can decide to skip the critique pass for that iteration.
    from google.genai import errors as gerrors
    import time as _time
    response = None
    backoffs = [5, 20, 60]
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + backoffs):
        if delay:
            print(f"  critic retry in {delay}s (attempt {attempt}/{len(backoffs)}) -- last err: {last_exc}", file=sys.stderr)
            _time.sleep(delay)
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=parts,
                config=gtypes.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    response_mime_type="application/json",
                    temperature=0.4,
                ),
            )
            break
        except gerrors.ServerError as exc:
            last_exc = exc
            continue
        except gerrors.ClientError as exc:
            # 400-class: don't retry, surface immediately.
            raise SystemExit(f"Critic ClientError (not retried): {exc}") from exc
    if response is None:
        raise SystemExit(f"Critic failed after {len(backoffs)} retries: {last_exc}")
    raw = (response.text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as exc:
        debug_dir = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "creative_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "critic_raw.txt").write_text(raw, encoding="utf-8")
        raise SystemExit(f"Critic returned non-JSON: {exc}. Raw at {debug_dir / 'critic_raw.txt'}") from exc

    # Enforce verdict-from-scores invariant.
    for s in out.get("scenes", []):
        s_art = s.get("score_artistic", 0)
        s_tech = s.get("score_technical", 0)
        ship_ok = (s_art >= PASS_ART_MIN) and (s_tech >= PASS_TECH_MIN)
        # Trust the model's verdict unless it contradicts the score floor.
        if not ship_ok:
            s["verdict"] = "REVISE"
    all_pass = all(s.get("verdict") == "PASS" for s in out.get("scenes", []))
    out["verdict"] = "PASS" if all_pass else "REVISE"
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="World-class critic for ProdCraft creative plans.")
    p.add_argument("--plan", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--words", required=True)
    p.add_argument("--stills-dir", required=True)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()

    result = critique(
        Path(args.plan).resolve(),
        Path(args.script).resolve(),
        Path(args.words).resolve(),
        Path(args.stills_dir).resolve(),
    )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Concise summary on stderr for orchestrators.
    print(f"VERDICT: {result['verdict']}", file=sys.stderr)
    for s in result.get("scenes", []):
        marker = "OK " if s["verdict"] == "PASS" else "RV "
        print(
            f"  {marker} {s['id']:35s} art={s.get('score_artistic',0)}/10 tech={s.get('score_technical',0)}/10",
            file=sys.stderr,
        )
    print(f"\nFull critique at: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
