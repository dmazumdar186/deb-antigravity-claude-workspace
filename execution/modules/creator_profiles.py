"""
description: Creator-profile cache for YouTube Video Analyzer v4. Stores per-channel
             style profiles built from accumulated video breakdowns and distilled via
             LLM to produce actionable creator-signature context for future analyses.
inputs:
  - channel_id: str — YouTube channel ID (e.g. 'UCxxx...' or uploader slug fallback)
  - channel_name: str — human-readable channel name
  - video_metadata: dict — from fetch_metadata_only() / fetch_metadata_and_download()
  - breakdown_text: str — rendered markdown breakdown from a completed analysis
outputs:
  - .tmp/creator_profiles/{channel_id}.json — profile JSON written atomically
  - style_profile dict injected as creator_context string into analysis prompts
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("creator_profiles")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
_PROFILES_DIR = _WORKSPACE_ROOT / ".tmp" / "creator_profiles"

SCHEMA_VERSION = 1

# Placeholder returned by LLM when insufficient data to characterize
_PLACEHOLDER = "insufficient data to characterize"

# Distillation threshold on first build (distill after this many videos)
_INITIAL_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------

def get_profile_path(channel_id: str) -> Path:
    """Return the path for a channel's profile JSON file."""
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR / f"{channel_id}.json"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_profile(channel_id: str) -> dict | None:
    """
    Load a creator profile from disk.

    Returns None if:
    - file does not exist
    - file is corrupt / unparseable
    - schema_version does not match SCHEMA_VERSION (forces re-distillation)
    """
    path = get_profile_path(channel_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to parse creator profile %s: %s — treating as missing", path, exc)
        return None

    if data.get("schema_version") != SCHEMA_VERSION:
        log.warning(
            "Creator profile schema_version mismatch for %s "
            "(got %s, expected %s) — forcing re-distillation",
            channel_id,
            data.get("schema_version"),
            SCHEMA_VERSION,
        )
        return None

    return data


def _save_profile(profile: dict) -> None:
    """Atomic write: write to .json.tmp then rename, same pattern as model_registry.py."""
    path = get_profile_path(profile["channel_id"])
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)
    log.debug("Creator profile saved: %s", path)


# ---------------------------------------------------------------------------
# Append video to profile
# ---------------------------------------------------------------------------

def append_video_to_profile(
    channel_id: str,
    channel_name: str,
    video_metadata: dict,
    breakdown_text: str,
) -> dict:
    """
    Append a completed breakdown to the channel's profile.

    Creates the profile if it doesn't exist yet.
    Bumps build_count, updates last_updated, atomic-writes to disk.
    Returns the updated profile dict.
    """
    profile = load_profile(channel_id) or _new_profile(channel_id, channel_name)

    # Always keep channel_name up to date
    profile["channel_name"] = channel_name

    entry = {
        "video_id": video_metadata.get("video_id", ""),
        "title": video_metadata.get("title", ""),
        "duration_sec": video_metadata.get("duration_sec", 0),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "breakdown_snippet": breakdown_text[:300],  # first 300 chars for audit trail
    }
    profile["profile_built_from"].append(entry)
    profile["build_count"] = len(profile["profile_built_from"])
    profile["last_updated"] = datetime.now(timezone.utc).isoformat()

    _save_profile(profile)
    log.info(
        "Creator profile for %s: build_count=%d, distillation_threshold=%d",
        channel_name,
        profile["build_count"],
        profile["next_distillation_threshold"],
    )
    return profile


def _new_profile(channel_id: str, channel_name: str) -> dict:
    """Return a blank profile dict for a new channel."""
    return {
        "schema_version": SCHEMA_VERSION,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "profile_built_from": [],
        "style_profile": None,
        "build_count": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "last_distillation_at": None,
        "next_distillation_threshold": _INITIAL_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Distillation threshold
# ---------------------------------------------------------------------------

def should_distill(profile: dict) -> bool:
    """Return True iff build_count has reached next_distillation_threshold."""
    return profile.get("build_count", 0) >= profile.get("next_distillation_threshold", _INITIAL_THRESHOLD)


def bump_distillation_threshold(profile: dict) -> None:
    """Advance next_distillation_threshold by 5 after a successful distillation."""
    profile["next_distillation_threshold"] = profile.get("build_count", 0) + 5


# ---------------------------------------------------------------------------
# Distillation LLM call
# ---------------------------------------------------------------------------

_DISTILLATION_SYSTEM = (
    "You are a creator-style analyst. Return ONLY valid JSON — no prose, no markdown fences."
)

_DISTILLATION_PROMPT_TEMPLATE = """\
You are a creator-style analyst. You will be given {n} video breakdowns from the same YouTube channel. \
Your job: synthesize a cross-video style profile.

Channel: {channel_name}
Breakdowns ({n} total):

{breakdowns_block}

Now produce a JSON object matching this schema (return ONLY the JSON, no prose, no markdown fence):

{{
  "hook_patterns": [3-5 strings describing recurring hook techniques; if too few breakdowns to support, return an empty array []],
  "pacing_patterns": [2-4 strings on cadence, length, structure; empty array if uncertain],
  "visual_style": [3-5 strings on framing, color, on-screen elements; empty array if uncertain],
  "common_topics": [3-5 noun-phrase topic tags; empty array if uncertain],
  "creator_signature": "MUST always be a non-empty string. If uncertain or insufficient data, write exactly: \\"insufficient data to characterize\\". Never return null for this field.",
  "common_b_roll_choices": [0-5 strings; empty array if none observed],
  "average_cuts_per_minute": <float, or null if not measurable from breakdowns — null is acceptable here>
}}

Rules:
- Empty arrays are acceptable for list fields when uncertain
- creator_signature must ALWAYS be a string (use the literal "insufficient data to characterize" placeholder when uncertain)
- average_cuts_per_minute is the only field allowed to be null
- Do NOT fabricate patterns from a single observation
"""

_RETRY_NOTE = (
    "Your previous response was not valid JSON. Return only valid JSON, nothing else."
)


def distill_profile(profile: dict, tier: str = "gemini") -> dict:
    """
    Run a distillation LLM call over all breakdowns in profile['profile_built_from'].

    Returns an updated profile dict with style_profile populated (and writes to disk).
    On JSONDecodeError: retries ONCE, then sets style_profile=None and logs ERROR.
    """
    # Build breakdowns block from stored snippets
    built_from = profile.get("profile_built_from", [])
    n = len(built_from)
    channel_name = profile.get("channel_name", "Unknown")

    breakdown_lines: list[str] = []
    for i, entry in enumerate(built_from, 1):
        title = entry.get("title", "Untitled")
        duration = entry.get("duration_sec", 0)
        snippet = entry.get("breakdown_snippet", "(no preview available)")
        breakdown_lines.append(
            f"=== Video {i}: {title} ({duration}s) ===\n{snippet}\n"
        )
    breakdowns_block = "\n".join(breakdown_lines)

    prompt = _DISTILLATION_PROMPT_TEMPLATE.format(
        n=n,
        channel_name=channel_name,
        breakdowns_block=breakdowns_block,
    )

    style_profile = _call_distillation_llm(prompt, tier=tier, retry_prefix="")
    if style_profile is None:
        # Retry once
        log.warning("First distillation attempt failed — retrying with JSON reminder.")
        style_profile = _call_distillation_llm(
            prompt, tier=tier, retry_prefix=_RETRY_NOTE + "\n\n"
        )

    if style_profile is None:
        log.error(
            "Distillation failed twice for %s — storing style_profile=None. "
            "Will retry on next analysis run.",
            channel_name,
        )
        profile["style_profile"] = None
    else:
        # Validate creator_signature
        sig = style_profile.get("creator_signature")
        if not sig or not isinstance(sig, str) or not sig.strip():
            style_profile["creator_signature"] = _PLACEHOLDER

        profile["style_profile"] = style_profile
        profile["last_distillation_at"] = datetime.now(timezone.utc).isoformat()
        bump_distillation_threshold(profile)
        log.info(
            "Distilled creator profile for %s from %d videos (next threshold: %d)",
            channel_name,
            n,
            profile["next_distillation_threshold"],
        )

    _save_profile(profile)
    return profile


def _call_distillation_llm(
    prompt: str, tier: str = "gemini", retry_prefix: str = ""
) -> dict | None:
    """
    Internal: call the LLM for distillation. Returns parsed dict or None on parse failure.
    Uses resolve_model() from model_registry to select the model.
    """
    sys.path.insert(0, str(_WORKSPACE_ROOT / "execution" / "modules"))
    try:
        from model_registry import resolve_model  # type: ignore[import-not-found]
    except ImportError as exc:
        log.error("Cannot import model_registry: %s", exc)
        return None

    full_prompt = retry_prefix + prompt

    if tier == "gemini":
        return _distill_via_gemini(full_prompt, resolve_model)
    else:
        # default/premium: use anthropic direct
        return _distill_via_anthropic(full_prompt, resolve_model, tier)


def _distill_via_gemini(prompt: str, resolve_model) -> dict | None:
    """Call Gemini directly (free tier) for distillation."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not set — cannot distill via Gemini")
        return None

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        log.error("google-genai not installed — cannot distill via Gemini")
        return None

    model_id = resolve_model("gemini", "default")
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=[genai_types.Part.from_text(text=prompt)],
            config=genai_types.GenerateContentConfig(
                system_instruction=_DISTILLATION_SYSTEM,
            ),
        )
    except Exception as exc:
        log.error("Gemini distillation call failed: %s", exc)
        return None

    raw = (response.text or "").strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = "\n".join(lines[1:-1]) if lines and lines[-1].strip() == "```" else "\n".join(lines[1:])
        raw = inner.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Gemini distillation JSON parse failed: %s | raw=%r", exc, raw[:200])
        return None


def _distill_via_anthropic(prompt: str, resolve_model, tier: str) -> dict | None:
    """Call Anthropic directly for distillation (default/premium tier)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set — cannot distill via Anthropic")
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        log.error("anthropic not installed — cannot distill via Anthropic")
        return None

    registry_tier = "premium" if tier == "premium" else "default"
    model_id = resolve_model("anthropic", registry_tier)
    client = Anthropic(api_key=api_key)

    try:
        resp = client.messages.create(
            model=model_id,
            max_tokens=1024,
            system=_DISTILLATION_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        log.error("Anthropic distillation call failed: %s", exc)
        return None

    raw = ""
    for block in resp.content:
        if hasattr(block, "text"):
            raw = block.text.strip()
            break

    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = "\n".join(lines[1:-1]) if lines and lines[-1].strip() == "```" else "\n".join(lines[1:])
        raw = inner.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Anthropic distillation JSON parse failed: %s | raw=%r", exc, raw[:200])
        return None


# ---------------------------------------------------------------------------
# Context formatter
# ---------------------------------------------------------------------------

def format_creator_context(profile: dict) -> str | None:
    """
    Format the creator profile into a short context string for injection into analysis.

    Returns None if:
    - profile has no style_profile
    - creator_signature is the placeholder (case-insensitive, stripped comparison)
    - creator_signature is empty/null
    """
    if not profile:
        return None
    style = profile.get("style_profile")
    if not style:
        return None

    sig = style.get("creator_signature") or ""
    # R3 fix: case-insensitive stripped comparison to handle LLM variants like
    # "Insufficient data to characterize." (capital I + period)
    if sig.lower().strip().rstrip(".") == _PLACEHOLDER:
        return None

    channel_name = profile.get("channel_name", "Unknown")
    build_count = profile.get("build_count", 0)

    lines: list[str] = [
        f"Past observations about {channel_name} (compiled from {build_count} prior video analyses):"
    ]

    hook_patterns = style.get("hook_patterns") or []
    if hook_patterns:
        lines.append(f"- Hook pattern: {'; '.join(hook_patterns[:3])}")

    visual_style = style.get("visual_style") or []
    if visual_style:
        lines.append(f"- Visual style: {'; '.join(visual_style[:3])}")

    pacing = style.get("pacing_patterns") or []
    avg_cuts = style.get("average_cuts_per_minute")
    pacing_parts = list(pacing[:2])
    if avg_cuts is not None:
        pacing_parts.append(f"{avg_cuts:.1f} cuts/min average")
    if pacing_parts:
        lines.append(f"- Pacing: {'; '.join(pacing_parts)}")

    topics = style.get("common_topics") or []
    if topics:
        lines.append(f"- Common topics: {', '.join(topics[:5])}")

    if sig:
        lines.append(f"- Creator signature: {sig}")

    lines.append(
        "\nUSE THESE AS CONTEXT ONLY. Describe what is actually in THIS video. "
        "If the video diverges from the patterns above, note the divergence."
    )

    return "\n".join(lines)
