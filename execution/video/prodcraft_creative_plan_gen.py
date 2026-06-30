"""
description: GLM 5.2 generates a bespoke per-section CreativePlan. The director call
             decomposes the audio into scenes AND beats (each beat anchored to a phrase
             in the narration with word-level timing). The scene-author call gets the
             beats + word-timings + Pixar principles + typography floors, and produces
             an SVG composition + animation timeline whose keyframes lock to the
             narration's actual word boundaries.
inputs:
    CLI:
        --script PATH         script.md (frontmatter stripped automatically)
        --words PATH          word timings JSON (provides duration + per-word boundaries)
        --topic "..."         topic one-liner (fallback if script frontmatter lacks `topic`)
        --out PATH            creative_plan.json (default: .tmp/prodcraft/creative_plan.json)
        --num-scenes N        desired scene count (default: 5)
        --provider NAME       personal (GLM 5.2, default) | client (Sonnet 4.6)
        --max-retries N       retries per scene if validation fails (default: 2)
        --reroll SCENE_ID     re-author only this scene; load existing plan from --out
        --reroll-notes "..."  critic feedback to inject into the rerolled scene's prompt
    env: OPENROUTER_API_KEY (personal); ANTHROPIC_API_KEY (client)
outputs:
    {out}                     CreativePlan JSON conforming to src/creative/types.ts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "creative_plan.json"

ALLOWED_TAGS = {
    "svg", "g", "defs", "path", "rect", "circle", "ellipse", "line",
    "polyline", "polygon", "text", "tspan", "title", "desc",
    "linearGradient", "radialGradient", "stop", "mask", "clipPath",
    "pattern", "use", "symbol", "marker", "filter",
    "feGaussianBlur", "feMerge", "feMergeNode", "feOffset", "feFlood",
    "feComposite", "feColorMatrix", "feDropShadow", "feBlend",
}
FORBIDDEN_TAG_RE = re.compile(
    r"<\s*(script|foreignObject|iframe|object|embed|link|style|meta|video|audio|img|image)\b[^>]*>.*?<\s*/\s*\1\s*>"
    r"|<\s*(script|foreignObject|iframe|object|embed|link|style|meta|video|audio|img|image)\b[^>]*/?>",
    re.IGNORECASE | re.DOTALL,
)
ON_HANDLER_RE = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
HREF_HTTP_RE = re.compile(
    r"(href|xlink:href)\s*=\s*(\"https?://[^\"]*\"|'https?://[^']*'|https?://[^\s>]+)", re.IGNORECASE
)
JS_URL_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
ALLOWED_PROPERTIES = {
    "opacity", "translateX", "translateY", "scale", "rotate",
    "stroke-dashoffset", "stroke-dasharray", "fill-opacity", "stroke-opacity",
}
ALLOWED_EASINGS = {"linear", "ease-in", "ease-out", "ease-in-out"}

# Typography floors (pixels in the 1760x750 SVG viewBox -> roughly 1:1 with the
# 1920x1080 render canvas after letterboxing). Anything below these fails
# legibility on a phone-sized playback.
MIN_FONT_PRIMARY = 64    # scene's main label / value
MIN_FONT_SECONDARY = 44  # supporting labels (axes, captions inside the scene)
MIN_FONT_TERTIARY = 28   # smallest acceptable (chip labels, micro-copy)
TEXT_TAG_RE = re.compile(r"<text\b([^>]*)>", re.IGNORECASE)
FONT_SIZE_RE = re.compile(r"font-size\s*=\s*[\"'](\d+(?:\.\d+)?)(?:px)?[\"']", re.IGNORECASE)
# Match opening tags that carry an id="el-*". Tag name is in group 1, attrs in group 2.
EL_ID_TAG_RE = re.compile(
    r"<\s*([a-zA-Z][a-zA-Z0-9]*)\b([^>]*\bid\s*=\s*[\"']el-[a-zA-Z0-9_-]+[\"'][^>]*)>",
    re.IGNORECASE,
)
OPACITY_ATTR_RE = re.compile(r"\bopacity\s*=\s*[\"'](?P<v>[0-9.]+)[\"']", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def sanitize_svg(svg: str) -> tuple[str, list[str]]:
    """Strip dangerous elements / attributes. Returns (clean_svg, list_of_warnings)."""
    warnings: list[str] = []
    cleaned = svg.strip()
    cleaned = re.sub(r"^```(?:svg|xml|html)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    before = cleaned
    cleaned = FORBIDDEN_TAG_RE.sub("", cleaned)
    if cleaned != before:
        warnings.append("stripped forbidden tags (script/foreignObject/iframe/etc.)")
    before = cleaned
    cleaned = ON_HANDLER_RE.sub("", cleaned)
    if cleaned != before:
        warnings.append("stripped inline event handlers (on*=)")
    before = cleaned
    cleaned = HREF_HTTP_RE.sub("", cleaned)
    if cleaned != before:
        warnings.append("stripped external http(s) hrefs")
    before = cleaned
    cleaned = JS_URL_RE.sub("", cleaned)
    if cleaned != before:
        warnings.append("stripped javascript: URLs")
    if "<svg" not in cleaned.lower():
        raise ValueError("sanitized SVG no longer contains <svg> root")
    return cleaned, warnings


def validate_typography(svg: str) -> list[str]:
    """Return a list of typography violations. Empty if all <text> elements meet the floor."""
    errors: list[str] = []
    for i, m in enumerate(TEXT_TAG_RE.finditer(svg)):
        attrs = m.group(1)
        fm = FONT_SIZE_RE.search(attrs)
        if not fm:
            errors.append(f"<text>[{i}]: missing font-size attribute (min {MIN_FONT_TERTIARY}px required)")
            continue
        size = float(fm.group(1))
        if size < MIN_FONT_TERTIARY:
            errors.append(f"<text>[{i}]: font-size={size}px below tertiary floor ({MIN_FONT_TERTIARY}px)")
    return errors


def validate_initial_invisibility(svg: str) -> list[str]:
    """Every id='el-*' element MUST start with opacity='0' in the SVG. Without this,
    GLM's authoring tendency is to put every element on canvas at opacity 1, causing
    'everything visible at frame 0' chaos. Returns a list of offending element ids."""
    errors: list[str] = []
    for m in EL_ID_TAG_RE.finditer(svg):
        attrs = m.group(2)
        # Extract the id value for the error message.
        id_m = re.search(r"id\s*=\s*[\"'](el-[a-zA-Z0-9_-]+)[\"']", attrs, re.IGNORECASE)
        eid = id_m.group(1) if id_m else "<unknown>"
        op_m = OPACITY_ATTR_RE.search(attrs)
        if op_m is None:
            errors.append(f"#{eid}: missing opacity attribute (must start at opacity='0')")
            continue
        try:
            v = float(op_m.group("v"))
        except ValueError:
            errors.append(f"#{eid}: opacity attribute is not a number")
            continue
        # Tolerate up to 0.15: GLM sometimes uses opacity=0.1 for an intentional
        # "dim backdrop / stage" element. The failure mode this rule blocks is
        # opacity=1 (everything visible at frame 0), so the cutoff is generous.
        if v > 0.15:
            errors.append(f"#{eid}: opacity={v} (must start at <=0.15; timeline brings it in)")
    return errors


def validate_timeline(timeline: list[dict], scene_duration_sec: float) -> list[str]:
    """Return a list of validation errors (empty if valid)."""
    errors: list[str] = []
    for i, kf in enumerate(timeline):
        if not isinstance(kf, dict):
            errors.append(f"kf[{i}]: not an object")
            continue
        t = kf.get("t")
        if not isinstance(t, (int, float)) or t < 0:
            errors.append(f"kf[{i}]: t must be >=0 number, got {t!r}")
        if t is not None and t > scene_duration_sec + 1.0:
            errors.append(f"kf[{i}]: t={t} exceeds scene duration {scene_duration_sec:.1f}s + 1.0 slack")
        tgt = kf.get("target")
        if not isinstance(tgt, str) or not tgt:
            errors.append(f"kf[{i}]: target must be non-empty string")
        prop = kf.get("property")
        if prop not in ALLOWED_PROPERTIES:
            errors.append(f"kf[{i}]: property {prop!r} not in {sorted(ALLOWED_PROPERTIES)}")
        if "value" not in kf:
            errors.append(f"kf[{i}]: missing 'value'")
        easing = kf.get("easing", "ease-out")
        if easing not in ALLOWED_EASINGS:
            errors.append(f"kf[{i}]: easing {easing!r} not in {sorted(ALLOWED_EASINGS)}")
        dur = kf.get("duration_sec", 0.4)
        if not isinstance(dur, (int, float)) or dur < 0 or dur > scene_duration_sec + 1.0:
            errors.append(f"kf[{i}]: duration_sec={dur} out of range")
    return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_frontmatter(text: str) -> tuple[str, dict]:
    if not text.startswith("---"):
        return text, {}
    end = text.find("\n---", 4)
    if end < 0:
        return text, {}
    fm_block = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fm = {}
    for line in fm_block.splitlines():
        m = re.match(r"^([\w_]+):\s*(.+)$", line.strip())
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return body, fm


def slice_words(all_words: list[dict], start_t: float, end_t: float) -> list[dict]:
    return [w for w in all_words if w["start"] >= start_t - 0.01 and w["start"] < end_t + 0.01]


def render_word_table(words: list[dict], scene_start: float) -> str:
    """Compact word-timing table for the LLM. Times relative to scene start."""
    lines = []
    for w in words:
        rel = w["start"] - scene_start
        lines.append(f"  t={rel:6.2f}s  {w['w']!r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GLM dispatch
# ---------------------------------------------------------------------------

_SYSTEM_DIRECTOR = (
    "You are a senior animation director at a studio that makes Vox/Kurzgesagt-grade "
    "educational explainers. You read narration transcripts and design scene structures "
    "where every on-screen moment is motivated by a specific phrase in the narration. "
    "Return ONLY a single valid JSON object. No prose. No markdown fences."
)

_SYSTEM_SCENE = (
    "You are a senior motion designer at Pixar / Disney Animation. You author inline "
    "SVG illustrations + matching animation timelines for ProdCraft, a YouTube channel "
    "about product management. You apply the 12 principles of animation -- staging, "
    "anticipation, slow-in-slow-out, hold-for-emphasis, motivated motion. You never "
    "animate for the sake of animation. Every keyframe answers: what is the narrator "
    "saying at this moment, and how does this visual aid understanding? "
    "Return ONLY a single valid JSON object. No prose. No markdown fences."
)


def _call_llm(system: str, user: str, provider: str, max_tokens: int) -> str:
    try:
        from execution.modules.model_router import call_model
    except ImportError:
        sys.path.insert(0, str(WORKSPACE_ROOT))
        from execution.modules.model_router import call_model

    mode = "personal" if provider == "personal" else "client"
    result = call_model(
        "sonnet",
        system=system,
        user=user,
        max_tokens=max_tokens,
        mode=mode,
        sensitivity="public",
    )
    print(f"  routed via {result['provider']} ({result['model']})", file=sys.stderr)
    return (result["text"] or "").strip()


def _extract_json(raw: str) -> dict | list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Director: lay out scene structure with beat decomposition
# ---------------------------------------------------------------------------

def director_call(
    script_body: str,
    words: list[dict],
    audio_duration: float,
    topic: str,
    num_scenes: int,
    provider: str,
) -> list[dict]:
    """Return [{id, title, start_t, end_t, visual_metaphor, beats: [{phrase, phrase_start_t, phrase_end_t, visual_action, pedagogical_purpose}, ...]}, ...]"""
    # Build a compact narration map with timestamps for the director.
    timed_lines = []
    cursor = 0
    line_buf: list[dict] = []
    line_start = words[0]["start"] if words else 0
    for w in words:
        line_buf.append(w)
        if w["w"].endswith((".", "!", "?")) or len(line_buf) >= 14:
            line_text = " ".join(x["w"] for x in line_buf)
            timed_lines.append(f"  [{line_start:5.1f}-{w['end']:5.1f}s] {line_text}")
            line_buf = []
            if cursor + 1 < len(words):
                line_start = words[min(cursor + 1, len(words) - 1)]["start"]
        cursor += 1
    if line_buf:
        line_text = " ".join(x["w"] for x in line_buf)
        timed_lines.append(f"  [{line_start:5.1f}-{line_buf[-1]['end']:5.1f}s] {line_text}")
    narration_timed = "\n".join(timed_lines)

    prompt = f"""You are designing the scene structure of a ProdCraft explainer video.

TOPIC: {topic}
TOTAL DURATION: {audio_duration:.1f} seconds
TARGET SCENE COUNT: {num_scenes}

THE NARRATION WITH WORD-LEVEL TIMING (each line is a sentence-ish chunk):
---
{narration_timed}
---

YOUR JOB has TWO parts:

PART 1 -- divide the timeline into {num_scenes} contiguous scenes. Each scene is a thematic chunk -- one big visual idea sustained across multiple narration moments.

PART 2 -- inside each scene, decompose the narration into BEATS. A beat is the smallest unit of "narrator says one thing, one visual moment happens to support it." Typical beat length: 2-5 seconds. A 30s scene typically has 6-10 beats.

For each scene, return:
- id: kebab-case slug, unique
- title: 3-6 words, plain English (this is the scene header)
- start_t: seconds (scene starts here)
- end_t: seconds (scene ends here; must equal next scene's start_t, except the last which ends at {audio_duration:.1f}s)
- visual_metaphor: one big visual idea that all this scene's beats live inside. Example: "Two chat bubbles -- the interviewer's on the left, the user's on the right -- with words physically moving between them." Make it concrete, geometric, animatable in SVG. NO stock-photo vocabulary. NO 3D. NO photography. Modern flat-vector / motion-graphics style.

For each beat inside that scene, return:
- phrase: EXACT substring of the narration this beat covers (must be findable in the narration above)
- phrase_start_t: seconds (when the narrator BEGINS this phrase)
- phrase_end_t: seconds (when the narrator FINISHES this phrase)
- visual_action: 1 sentence describing what changes on-screen DURING this phrase. Examples: "Bubble A's last three words detach, slide right, and dock into Bubble B reformatted as a question with a question-mark glyph." / "A yellow highlight sweeps across the phrase 'planted the answer'." / "The clock reaches zero, the chime icon flashes, the next bubble fades in."
- pedagogical_purpose: 1 sentence explaining WHY this animation aids understanding at this moment. If you can't write this sentence, the animation is gratuitous -- redesign.

Constraints:
- Scenes contiguous, cover [0, {audio_duration:.1f}]s exactly.
- Beats inside a scene contiguous, cover [scene.start_t, scene.end_t] exactly. No gaps, no overlaps.
- Every beat's phrase_start_t / phrase_end_t MUST align with actual word boundaries from the narration table above (within ~0.3s tolerance).
- 4-10 beats per scene. Less = lazy direction; more = the scene needs to be split.
- Visual metaphors must REUSE consistent elements within a scene. If a scene has chat bubbles, those bubbles persist throughout the scene -- they aren't replaced beat-to-beat. Only their state changes (position, content, highlight).

Return JSON with EXACTLY this shape:

{{
  "scenes": [
    {{
      "id": "...",
      "title": "...",
      "start_t": 0,
      "end_t": 0,
      "visual_metaphor": "...",
      "beats": [
        {{
          "phrase": "...",
          "phrase_start_t": 0,
          "phrase_end_t": 0,
          "visual_action": "...",
          "pedagogical_purpose": "..."
        }}
      ]
    }}
  ]
}}"""
    raw = _call_llm(_SYSTEM_DIRECTOR, prompt, provider, max_tokens=6000)
    obj = _extract_json(raw)
    scenes = obj.get("scenes") if isinstance(obj, dict) else None
    if not isinstance(scenes, list) or not scenes:
        raise SystemExit(f"Director returned no scenes. Raw: {raw[:500]}")
    for i, s in enumerate(scenes):
        for k in ("start_t", "end_t", "visual_metaphor", "beats"):
            if k not in s:
                raise SystemExit(f"Scene {i} missing {k!r}: {s}")
        s["start_t"] = float(s["start_t"])
        s["end_t"] = float(s["end_t"])
        if not isinstance(s["beats"], list) or not s["beats"]:
            raise SystemExit(f"Scene {i} has no beats")
    scenes[0]["start_t"] = 0.0
    scenes[-1]["end_t"] = audio_duration
    return scenes


# ---------------------------------------------------------------------------
# Scene author: SVG + timeline locked to word boundaries
# ---------------------------------------------------------------------------

def author_scene(
    scene_meta: dict,
    scene_words: list[dict],
    provider: str,
    max_retries: int,
    extra_critic_notes: str = "",
) -> dict:
    """Generate SVG + timeline for one scene, locked to actual word boundaries."""
    duration = scene_meta["end_t"] - scene_meta["start_t"]
    word_table = render_word_table(scene_words, scene_meta["start_t"])

    beats_block = []
    for i, b in enumerate(scene_meta["beats"]):
        rel_start = b["phrase_start_t"] - scene_meta["start_t"]
        rel_end = b["phrase_end_t"] - scene_meta["start_t"]
        beats_block.append(
            f"BEAT {i + 1} -- scene-relative t=[{rel_start:5.2f}, {rel_end:5.2f}]s\n"
            f"  narrator says: \"{b['phrase']}\"\n"
            f"  visual action: {b['visual_action']}\n"
            f"  why this aids understanding: {b['pedagogical_purpose']}"
        )
    beats_text = "\n\n".join(beats_block)

    critic_clause = ""
    if extra_critic_notes.strip():
        critic_clause = (
            "\n\nCRITIC NOTES from the previous attempt -- you MUST address each of these:\n"
            f"{extra_critic_notes.strip()}\n"
        )

    prompt = f"""You are authoring ONE scene of a ProdCraft explainer.

SCENE TITLE: {scene_meta['title']}
SCENE DURATION: {duration:.1f} seconds (animations are scene-relative -- t=0 is when this scene begins)
VISUAL METAPHOR (the persistent on-screen idea for this scene): {scene_meta['visual_metaphor']}

WORD-LEVEL NARRATION TIMING DURING THIS SCENE (t is scene-relative):
{word_table}

BEATS YOU MUST HIT, IN ORDER:

{beats_text}
{critic_clause}

YOUR OUTPUT -- a single JSON object with three fields: svg, timeline, hook.

============================================================
PART A -- SVG composition
============================================================

Author a self-contained inline SVG with viewBox="0 0 1760 800" that holds ALL the visual elements every beat references. Persistent elements stay in the SVG and are animated; you do NOT swap SVGs between beats.

VISUAL DISCIPLINE -- TREAT THESE AS LAWS:

(0) INITIAL STATE = INVISIBLE. Every animated element (everything with id="el-*") MUST have opacity="0" set explicitly in the SVG. SVG's default opacity is 1, so a missing opacity attribute = visible-at-frame-0 = chaos. The timeline brings it in. The ONLY exceptions: gradient/filter <defs> blocks (no id needed; no animation), and ONE optional "stage backdrop" element which may use opacity 0.05-0.12 to be faintly visible from the start. Every other id="el-*" element MUST start with opacity="0".

CORRECT pattern (do this):
  <g id="el-card" opacity="0">
    <rect x="100" y="100" width="400" height="200" rx="16" fill="#0b1220"/>
    <text x="300" y="220" text-anchor="middle" font-size="48" font-weight="600" fill="white">Hello</text>
  </g>
  ...then in timeline: {{"t": 1.2, "target": "el-card", "property": "opacity", "value": 1, "duration_sec": 0.4}}

WRONG pattern (NEVER do this -- it fails validation):
  <g id="el-card"> ... </g>                          // no opacity attr = visible from t=0
  <rect id="el-bg" opacity="0.3" ... />              // 0.3 too high; backdrop cap is 0.12
  <g id="el-card" opacity="1"> ... </g>              // pinned visible

(1) STAGING: at any moment, there must be ONE focal point. Not two competing centerpieces. Secondary elements either don't yet exist (animated in later), or are dimmed (opacity 0.25).

(2) BREATHING ROOM: ~80px padding from the viewBox edge. Elements must not touch or overlap unless intentional (e.g. an arrow piercing a target). No element accidentally overlaps another. Map out positions on a mental grid before placing.

(3) TYPOGRAPHY FLOOR (this is HARD -- the renderer rejects scenes that violate it):
    - PRIMARY label (the scene's BIG word -- e.g. "ECHO" or "ASK THIS"): font-size="80" or bigger.
    - SECONDARY labels (axis names, captions inside the scene): font-size="48" or bigger.
    - TERTIARY (chip labels, micro-copy): font-size="36" minimum. Below 32 fails validation.
    - font-family="Inter, system-ui, sans-serif" everywhere.
    - font-weight: 700 for primary, 600 for secondary, 500 for tertiary.

(4) ELEMENT DENSITY CAP: 5-9 distinct visual elements per scene (NOT counting decorative gradients/filters). More than that and the viewer can't track what's happening.

(5) IDs: every animated element MUST carry id="el-<slug>". Static decorations (gradients, filters) need no id.

(6) PALETTE:
    - Background is the page (light #fafbfd). Don't paint a background rect.
    - Primary fill / stroke: #0b1220 (deep navy).
    - Accent (highlights, current focus): #1c8b7c (ProdCraft teal).
    - Muted: rgba(11,18,32,0.45).
    - Warning / wrong: #c14f3f (used SPARINGLY).
    Avoid pastels and rainbow palettes. The whole scene reads in 2-3 colors max.

(7) NO PROHIBITED TAGS: only svg, g, defs, path, rect, circle, ellipse, line, polyline, polygon, text, tspan, linearGradient, radialGradient, stop, mask, clipPath, use, symbol, filter (and its primitives). No <script>, <foreignObject>, <iframe>, <image>, <link>, event handlers, http(s) hrefs.

============================================================
PART B -- timeline (the animation)
============================================================

The timeline is an ordered array of keyframes that animate the SVG over the scene's {duration:.1f}-second duration. Each keyframe:
{{"t": 1.6, "target": "el-bubble-1", "property": "opacity", "value": 1, "duration_sec": 0.4, "easing": "ease-out"}}

Allowed properties: opacity, translateX, translateY, scale, rotate, stroke-dashoffset, stroke-dasharray, fill-opacity, stroke-opacity.
Allowed easings: linear, ease-in, ease-out, ease-in-out. NEVER linear except for ultra-mechanical motion (clock ticks). Default ease-out.

ANIMATION DISCIPLINE -- TREAT THESE AS LAWS:

(1) MOTIVATED MOTION: every keyframe lines up with a specific moment in the narration. Look at the WORD TIMING TABLE above. Each beat's visual action begins AT or 0.1-0.3s BEFORE the narrator first speaks that beat's keyword. The action lands BY the time the narrator finishes the keyword. NEVER animate something the narrator isn't currently talking about.

(2) HOLDS: between beats, the frame is STILL. Most of a 30s scene is HOLD time. Motion is the exception, not the rule. Total moving-frame-time should be ~25% of scene duration. The other ~75% is the viewer reading what just appeared.

(3) ANTICIPATION: before a big move, the element does a tiny opposing move (scale 1.0 -> 0.94 -> 1.0 over 0.2s before scale 1.0 -> 1.1). This is what makes motion feel "Pixar" instead of "PowerPoint."

(4) STAGGER: when revealing multiple sibling elements (e.g. 3 bullet points), stagger them by 0.15-0.3s. Don't pop them in simultaneously.

(5) ONE THING AT A TIME: never animate more than 2 elements simultaneously unless they're a coordinated pair (e.g. arrow + target). The viewer's eye can't track parallel motion.

(6) EXIT BEFORE ENTER: when a beat ends and the next beat introduces a new focal element, the old one DIMS or SHRINKS first (0.3s), THEN the new one appears (0.3s). The transition is 0.6s of single-thread motion, not 0.3s of crossfade chaos.

(7) PROPERTY USE:
   - opacity 0 -> 1 to introduce something.
   - opacity 1 -> 0.3 to dim something (don't go to 0 unless it's truly leaving).
   - scale 0.92 -> 1.04 -> 1.0 for a "pop in with weight" (settle).
   - translateY +20 -> 0 paired with opacity 0 -> 1 for "rise into existence."
   - stroke-dashoffset N -> 0 for "drawing a line" (the SVG path must have stroke-dasharray set to its own length).

(8) KEYFRAME COUNT: 20-40 keyframes for a 30s scene. Below 15 = under-animated. Above 50 = noisy.

(9) TIMING SANITY CHECK: read your timeline back. For each keyframe, ask "what is the narrator saying at this t?" Look at the word table. If you can't justify it, delete it.

============================================================
PART C -- hook (optional supporting line)
============================================================

`hook`: a 1-line on-screen subtitle that frames the scene's POINT in plain words. Shown beneath the scene for the full duration. MAX 70 chars. Empty string if the scene speaks for itself.

============================================================
OUTPUT FORMAT (no prose, no fences):
============================================================

{{
  "svg": "<svg viewBox=\\"0 0 1760 800\\" xmlns=\\"http://www.w3.org/2000/svg\\">...</svg>",
  "timeline": [
    {{"t": 0.0, "target": "el-root", "property": "opacity", "value": 1, "duration_sec": 0.5, "easing": "ease-out"}}
  ],
  "hook": "..."
}}"""

    last_err: str | None = None
    last_raw: str = ""
    for attempt in range(max_retries + 1):
        if attempt:
            print(f"    retry {attempt}/{max_retries} for scene '{scene_meta['id']}' (last err: {last_err})", file=sys.stderr)
        try:
            raw = _call_llm(_SYSTEM_SCENE, prompt, provider, max_tokens=24000)
            last_raw = raw
            if not raw:
                last_err = "empty response"
                continue
            obj = _extract_json(raw)
            if not isinstance(obj, dict) or "svg" not in obj or "timeline" not in obj:
                last_err = "missing svg/timeline keys"
                continue
            cleaned_svg, warns = sanitize_svg(obj["svg"])
            for w in warns:
                print(f"    sanitize: {w}", file=sys.stderr)
            typo_errs = validate_typography(cleaned_svg)
            if typo_errs:
                last_err = f"typography violations: {len(typo_errs)} (e.g. {typo_errs[0]})"
                continue
            invis_errs = validate_initial_invisibility(cleaned_svg)
            if invis_errs:
                last_err = f"initial-invisibility violations: {len(invis_errs)} (e.g. {invis_errs[0]})"
                continue
            timeline = obj["timeline"]
            if not isinstance(timeline, list):
                last_err = "timeline not a list"
                continue
            errs = validate_timeline(timeline, duration)
            if errs:
                last_err = f"{len(errs)} timeline errors: {errs[:2]}"
                continue
            if len(timeline) < 12:
                last_err = f"only {len(timeline)} keyframes — under-animated (need 15-50)"
                continue
            hook = obj.get("hook", "")
            if not isinstance(hook, str):
                hook = ""
            hook = hook[:80]
            return {"svg": cleaned_svg, "timeline": timeline, "hook": hook}
        except json.JSONDecodeError as exc:
            last_err = f"json decode: {exc}"
            continue
        except ValueError as exc:
            last_err = f"validation: {exc}"
            continue
    debug_dir = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "creative_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / f"{scene_meta['id']}_last_raw.txt").write_text(last_raw or "<empty>", encoding="utf-8")
    raise SystemExit(
        f"Scene '{scene_meta['id']}' failed after {max_retries + 1} attempts. Last error: {last_err}. "
        f"Last raw output saved to {debug_dir / (scene_meta['id'] + '_last_raw.txt')}"
    )


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------

def generate(
    script_path: Path,
    words_path: Path,
    topic: str,
    num_scenes: int,
    provider: str,
    max_retries: int,
) -> dict:
    raw = script_path.read_text(encoding="utf-8")
    body, fm = _strip_frontmatter(raw)
    topic = topic or fm.get("topic") or "Untitled"

    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    audio_duration = float(words_data.get("duration_sec") or 0)
    if audio_duration <= 0:
        raise SystemExit(f"words JSON has invalid duration_sec: {words_data.get('duration_sec')}")
    words = words_data.get("words", [])

    print(f"Director: planning {num_scenes} scenes + beats over {audio_duration:.1f}s ...", file=sys.stderr)
    scene_metas = director_call(body, words, audio_duration, topic, num_scenes, provider)
    print(f"  director returned {len(scene_metas)} scenes:", file=sys.stderr)
    for s in scene_metas:
        print(f"    {s['id']:30s} t=[{s['start_t']:5.1f},{s['end_t']:5.1f}] {len(s['beats'])} beats", file=sys.stderr)

    scenes_out: list[dict] = []
    for s in scene_metas:
        scene_words = slice_words(words, s["start_t"], s["end_t"])
        print(f"\nAuthoring scene '{s['id']}' ({s['title']!r}) ...", file=sys.stderr)
        try:
            artifact = author_scene(s, scene_words, provider, max_retries)
        except SystemExit as exc:
            # Tolerate single-scene authoring failure: insert a minimal placeholder
            # so the rest of the plan still ships. The critique loop can reroll
            # this scene next iteration with critic notes.
            print(f"WARN: scene '{s['id']}' authoring failed -- inserting placeholder. ({exc})", file=sys.stderr)
            duration = s["end_t"] - s["start_t"]
            artifact = {
                "svg": (
                    f"<svg viewBox=\"0 0 1760 800\" xmlns=\"http://www.w3.org/2000/svg\">"
                    f"<text id=\"el-placeholder-{s['id']}\" x=\"880\" y=\"400\" "
                    f"text-anchor=\"middle\" font-family=\"Inter, sans-serif\" "
                    f"font-size=\"48\" font-weight=\"600\" fill=\"rgba(11,18,32,0.35)\" "
                    f"opacity=\"0\">(scene awaiting reroll: {s['title']})</text></svg>"
                ),
                "timeline": [
                    {"t": 0.3, "target": f"el-placeholder-{s['id']}", "property": "opacity",
                     "value": 1, "duration_sec": 0.6, "easing": "ease-out"},
                    {"t": max(0.0, duration - 1.0), "target": f"el-placeholder-{s['id']}",
                     "property": "opacity", "value": 0, "duration_sec": 0.6, "easing": "ease-in"},
                ],
                "hook": "",
            }
        scenes_out.append({
            "id": s["id"],
            "title": s["title"],
            "start_t": s["start_t"],
            "end_t": s["end_t"],
            "visual_metaphor": s["visual_metaphor"],
            "beats": s["beats"],
            "svg": artifact["svg"],
            "hook": artifact["hook"],
            "timeline": artifact["timeline"],
        })

    plan = {
        "doc_title": fm.get("title") or topic,
        "audio_duration_sec": audio_duration,
        "scenes": scenes_out,
    }
    return plan


def reroll_scene_in_plan(
    plan_path: Path,
    words_path: Path,
    scene_id: str,
    critic_notes: str,
    provider: str,
    max_retries: int,
) -> dict:
    """Load existing plan, re-author one scene with critic feedback, save in place."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    words = words_data.get("words", [])

    target = next((s for s in plan["scenes"] if s["id"] == scene_id), None)
    if target is None:
        raise SystemExit(f"Scene id {scene_id!r} not found in plan. Available: {[s['id'] for s in plan['scenes']]}")

    scene_words = slice_words(words, target["start_t"], target["end_t"])
    scene_meta = {
        "id": target["id"],
        "title": target["title"],
        "start_t": target["start_t"],
        "end_t": target["end_t"],
        "visual_metaphor": target["visual_metaphor"],
        "beats": target["beats"],
    }
    print(f"Rerolling scene '{scene_id}' with critic notes ({len(critic_notes)} chars) ...", file=sys.stderr)
    artifact = author_scene(scene_meta, scene_words, provider, max_retries, extra_critic_notes=critic_notes)

    target["svg"] = artifact["svg"]
    target["hook"] = artifact["hook"]
    target["timeline"] = artifact["timeline"]
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan


def main() -> int:
    p = argparse.ArgumentParser(description="GLM 5.2 creative-plan generator for ProdCraft (v2: beat-decomposed + Pixar-disciplined).")
    p.add_argument("--script", required=False)
    p.add_argument("--words", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--num-scenes", type=int, default=5)
    p.add_argument("--provider", default="personal", choices=("personal", "client"))
    p.add_argument("--max-retries", type=int, default=2)
    p.add_argument("--reroll", default="", help="Scene id to re-author (requires --out to point at an existing plan).")
    p.add_argument("--reroll-notes", default="", help="Critic feedback to inject into the rerolled scene's prompt.")
    args = p.parse_args()

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.reroll:
        if not out_path.exists():
            raise SystemExit(f"--reroll requires an existing plan at {out_path}")
        plan = reroll_scene_in_plan(
            out_path,
            Path(args.words).resolve(),
            args.reroll,
            args.reroll_notes,
            args.provider,
            args.max_retries,
        )
    else:
        if not args.script:
            raise SystemExit("--script required when not in --reroll mode")
        plan = generate(
            Path(args.script).resolve(),
            Path(args.words).resolve(),
            args.topic,
            args.num_scenes,
            args.provider,
            args.max_retries,
        )
        out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "ok": True,
        "out": str(out_path),
        "scenes": len(plan["scenes"]),
        "duration_sec": plan["audio_duration_sec"],
        "total_keyframes": sum(len(s["timeline"]) for s in plan["scenes"]),
        "total_beats": sum(len(s.get("beats", [])) for s in plan["scenes"]),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - best-effort UTF-8 on Windows
        pass
    sys.exit(main())
