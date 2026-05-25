"""
description: Frame-by-frame breakdown of a YouTube video using PySceneDetect +
             perceptual-hash dedup + 3x3 grid tiling + Claude tool-use with
             prompt caching. Supports three tiers: default (latest Sonnet-
             equivalent), premium (latest Opus-equivalent), and gemini (free,
             passes YouTube URL directly to Gemini -- no frame extraction).
             Model IDs are resolved at runtime via execution/modules/model_registry.py.
             v3: added OpenRouter routing (one key reaches Claude/Gemini/GPT-4o vision),
             provider auto-detection from env vars, --provider flag, and
             strict ALLOWED_FAMILIES allowlist enforced in model_registry.py.
             v4: added batch mode (multiple URLs / --urls-file), creator-profile cache
             (per-channel style distillation, injected as context into analysis),
             and channel_id extraction from yt-dlp metadata.
inputs:
  - Positional arg: YouTube URL
  - --tier {default,premium,gemini}  (default: default)
  - --provider {openrouter,anthropic,gemini-direct,auto}  (default: auto)
  - --model <exact-id>               (escape hatch, bypasses registry)
  - --refresh-models                 (force registry re-fetch from APIs)
  - --max-frames N                   (default 24; cap before dedup, range 1-200)
  - --obsidian-vault PATH            (override OBSIDIAN_VAULT env var)
  - --dry-run                        (shallow dry-run: no network calls, no transcript fetch,
                                      no video download; prints planned config + would_* fields.
                                      Use --deep-dry-run for the full pipeline cost estimation.)
  - --deep-dry-run                   (deep dry-run: runs PySceneDetect + frame extraction +
                                      token counting WITHOUT calling the AI API. Preserves the
                                      original dry-run behavior from v1/v2.)
  - --keep-source                    (keep downloaded .mp4 after analysis)
  - Env: OPENROUTER_API_KEY          (preferred -- one key reaches Claude/Gemini/GPT)
  - Env: ANTHROPIC_API_KEY           (legacy fallback for default/premium tiers)
  - Env: GEMINI_API_KEY              (required for free gemini-direct path)
  - Env: OBSIDIAN_VAULT              (optional vault path)
outputs:
  - .tmp/video/{video_id}/breakdown.md          (always)
  - .tmp/video/{video_id}/frames/*.jpg          (scene-change frames; Claude/OR path only)
  - .tmp/video/{video_id}/grids/grid_*.jpg      (tiled 3x3 grids; Claude/OR path only)
  - .tmp/video/{video_id}/transcript.txt
  - {OBSIDIAN_VAULT}/Video Breakdowns/{YYYY-MM-DD}_{slug}.md  (if vault set)
  - stdout: final breakdown path
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("yt_analyzer")

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TMP_BASE = WORKSPACE_ROOT / ".tmp" / "video"

# v2 frame/grid constants
MAX_FRAMES_DEFAULT = 24
GRID_COLS, GRID_ROWS = 3, 3
GRID_CELL_W, GRID_CELL_H = 384, 216
DEDUP_HASH_THRESHOLD = 6       # imagehash hamming distance min to keep frame
PYSCENEDETECT_THRESHOLD = 27   # ContentDetector sensitivity

# Download format unchanged from v1
DOWNLOAD_FORMAT = (
    "18/b[ext=mp4][acodec!=none][vcodec!=none][height<=720]"
    "/best[acodec!=none][vcodec!=none]/best"
)

CLAUDE_MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Tool-use schema for Claude/OR path (forced single call)
# Single source of truth — adapters below convert to provider-specific formats.
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "submit_breakdown",
    "description": "Submit the structured video breakdown.",
    "input_schema": {
        "type": "object",
        "required": [
            "summary",
            "key_takeaways",
            "hook",
            "pacing_cuts",
            "visual_storytelling",
            "transcript_highlights",
            "content_ideas",
        ],
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "A 3-5 sentence overview of what the video is actually about — "
                    "the subject, the argument or thesis, and the conclusion. Plain prose, "
                    "no marketing tone. Should let a reader understand the video's content "
                    "without watching it."
                ),
            },
            "key_takeaways": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 7,
                "description": (
                    "1-7 substantive takeaways from the video's content (NOT how it was "
                    "made — what it claims, argues, or teaches). Each bullet is a complete "
                    "sentence stating a specific point the viewer would walk away knowing. "
                    "On very short videos (under 1 minute) returning 1-2 bullets is fine — "
                    "do NOT fabricate to fill quota. "
                    "DISAMBIGUATION: transcript_highlights captures verbatim quote moments "
                    "with timestamps; summary + key_takeaways are SYNTHESIZED content. "
                    "Different purposes; don't duplicate."
                ),
            },
            "hook": {
                "type": "string",
                "description": (
                    "What grabs attention in the first 15 seconds. "
                    "Specific: combine the opening visual + opening line."
                ),
            },
            "pacing_cuts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["timestamp", "what_changes"],
                    "properties": {
                        "timestamp": {
                            "type": "string",
                            "description": "MM:SS format",
                        },
                        "what_changes": {"type": "string"},
                    },
                },
                "minItems": 3,
            },
            "visual_storytelling": {"type": "string"},
            "transcript_highlights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["timestamp", "quote"],
                    "properties": {
                        "timestamp": {"type": "string"},
                        "quote": {"type": "string"},
                    },
                },
                "minItems": 3,
                "maxItems": 5,
            },
            "content_ideas": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
            },
        },
    },
}

SYSTEM_PROMPT = (
    "You are a video content analyst. Your job is to study YouTube videos "
    "and extract actionable insights about visual storytelling, pacing, and "
    "hooks. Be specific — not generic. When you describe a visual moment, "
    "name what is on screen, not just what is happening conceptually. "
    "Avoid complimenting the creator. This is a working research document."
)

ANALYSIS_USER_PROMPT = """\
Analyze this YouTube video using the frame grids and transcript below.

Each grid image contains up to 9 frames arranged 3×3. Each frame has a "MM:SS" \
timestamp burned into the top-left corner showing when it appeared in the video. \
Use these grids to understand the VISUAL arc of the video.

Metadata:
  Title:    {title}
  Channel:  {channel}
  Duration: {duration_str}
  Frames extracted (before dedup): {raw_frame_count}
  Distinct frames (after dedup):   {dedup_frame_count}
  Grid images:                     {grid_count}

=== TRANSCRIPT ===
{transcript_text}

Fill out each section below:

## Summary
A 3-5 sentence prose overview of what this video is about, what it argues, and what it concludes. Plain language. No marketing voice. Should stand alone — a reader should understand the video's substance from this paragraph without watching it.

## Key Takeaways
1-7 specific, complete-sentence bullets capturing what the viewer would walk away KNOWING. Substance, not style. NOT "the creator uses fast cuts" (that's craft). YES "global wheat prices have risen 40% in the last quarter due to X" (that's content). On very short videos returning 1-2 bullets is fine — do not fabricate to fill quota.

## The Hook (0:00–0:15)
What grabs attention in the first 15 seconds. Combine opening visual + opening line. Be specific.

## Pacing & Cuts
List the major cut/scene transitions with timestamps and what changes.

## Visual Storytelling
Patterns in text overlays, b-roll, camera moves, color, and framing.

## Transcript Highlights
3-5 verbatim quote moments with timestamps.

## Content Ideas Inspired by This
3-5 video concepts this breakdown could inspire.

Call submit_breakdown exactly once with the structured breakdown.
"""


# ---------------------------------------------------------------------------
# Provider auto-detection
# ---------------------------------------------------------------------------

def _auto_detect_provider(tier: str) -> str:
    """
    Pick provider based on tier + which env vars are set.

    Decision table:
      gemini tier:
        GEMINI_API_KEY set  → gemini-direct  (free URL-native path)
        OPENROUTER_API_KEY  → openrouter      (paid frame-grid path)
        neither             → error

      default / premium tier:
        OPENROUTER_API_KEY  → openrouter      (preferred: one key for all models)
        ANTHROPIC_API_KEY   → anthropic        (legacy direct path)
        neither             → error
    """
    has_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if tier == "gemini":
        if has_gemini:
            return "gemini-direct"
        if has_or:
            log.warning(
                "GEMINI_API_KEY not set — routing --tier gemini via OpenRouter "
                "(PAID frame-grid mode, NOT the free URL-native path). "
                "Add GEMINI_API_KEY to .env to get the $0.00 free path."
            )
            return "openrouter"
        raise SystemExit(
            "--tier gemini requires GEMINI_API_KEY (free URL-native path) "
            "or OPENROUTER_API_KEY (paid frame-grid mode) in .env"
        )

    # default / premium
    if has_or:
        return "openrouter"
    if has_anthropic:
        return "anthropic"
    raise SystemExit(
        "--tier default/premium requires OPENROUTER_API_KEY (preferred) "
        "or ANTHROPIC_API_KEY in .env. "
        "Get an OpenRouter key at https://openrouter.ai — one key reaches "
        "Claude, Gemini, and GPT-4o vision."
    )


# ---------------------------------------------------------------------------
# Tool-schema adapters
# ---------------------------------------------------------------------------

def _to_openai_tool_format(schema: dict) -> dict:
    """Convert Anthropic-style tool schema to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["input_schema"],
        },
    }


def _to_anthropic_tool_format(schema: dict, cache_control: dict | None = None) -> dict:
    """
    Build Anthropic-format tool dict from TOOL_SCHEMA.
    Optionally appends cache_control for prompt-caching beta.
    Use this instead of inline tool-list construction in analyze_with_claude_v2.
    """
    tool: dict = dict(schema)
    if cache_control is not None:
        tool["cache_control"] = cache_control
    return tool


# --------------------------------------------------------------------------- #
# URL / video-id handling  (PRESERVED from v1)                                #
# --------------------------------------------------------------------------- #

YOUTUBE_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:m\.youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})"),
]

# Fix 7 — SSRF guard: only allow real YouTube URLs
_YOUTUBE_HOST_RE = re.compile(
    r"^https://(www\.|m\.)?youtube\.com/|^https://youtu\.be/"
)


def extract_video_id(url: str) -> str:
    for pat in YOUTUBE_ID_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    raise ValueError(
        f"Could not extract a YouTube video ID from URL: {url!r}. "
        "Supported forms: youtube.com/watch?v=ID, youtu.be/ID, /shorts/ID, /embed/ID."
    )


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:max_len].rstrip("-") or "video"


# --------------------------------------------------------------------------- #
# Step 2: Captions  (PRESERVED from v1)                                       #
# --------------------------------------------------------------------------- #


def fetch_transcript(video_id: str) -> list[dict]:
    """Return list of {start, duration, text}. Raises if no captions exist."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as e:
        raise SystemExit(
            "youtube-transcript-api is not installed. Run:\n"
            "  py -m pip install youtube-transcript-api"
        ) from e

    try:
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
            entries = [
                {"start": s.start, "duration": s.duration, "text": s.text}
                for s in fetched
            ]
        except AttributeError:
            entries = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["en", "en-US", "en-GB"]
            )
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        raise SystemExit(
            f"No captions available for video {video_id}. "
            "This tool requires captions (captions-only mode). "
            "Try a different video or enable captions on YouTube."
        ) from e
    except VideoUnavailable as e:
        raise SystemExit(
            f"Video {video_id} is unavailable (private, deleted, or region-blocked)."
        ) from e

    if not entries:
        raise SystemExit(f"Empty transcript returned for video {video_id}.")
    return entries


def format_transcript(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        start = float(e["start"])
        mm = int(start // 60)
        ss = int(start % 60)
        text = str(e["text"]).replace("\n", " ").strip()
        lines.append(f"[{mm:02d}:{ss:02d}] {text}")
    return "\n".join(lines)


def _parse_transcript_txt(text: str) -> list[dict]:
    """
    Parse the on-disk [MM:SS] format back to list[dict].
    Sets start=(mm*60+ss), duration=(next_start - this_start, or 3 for last),
    text=the caption line.
    """
    pattern = re.compile(r"^\[(\d{2}):(\d{2})\] (.+)$")
    entries: list[dict] = []
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            mm, ss, txt = int(m.group(1)), int(m.group(2)), m.group(3)
            entries.append({"start": mm * 60 + ss, "duration": 3.0, "text": txt})
    # Backfill duration from successive start times
    for i in range(len(entries) - 1):
        entries[i]["duration"] = float(entries[i + 1]["start"] - entries[i]["start"])
    return entries


def get_or_fetch_transcript(
    video_id: str,
    work_dir: Path,
    force_refresh: bool = False,
) -> list[dict]:
    """
    Cache-first transcript retrieval.
    - If transcript.txt already exists in work_dir and force_refresh is False,
      parse and return it without any network call.
    - Otherwise, fetch live from YouTube, write transcript.txt, and return entries.
    """
    cache_file = work_dir / "transcript.txt"
    if not force_refresh and cache_file.exists():
        cached_text = cache_file.read_text(encoding="utf-8")
        entries = _parse_transcript_txt(cached_text)
        if entries:
            log.info(
                "Transcript loaded from cache (%d entries, %d chars)",
                len(entries), len(cached_text),
            )
            return entries
        log.warning("Cached transcript.txt was empty or unparseable — fetching live.")

    entries = fetch_transcript(video_id)
    transcript_text = format_transcript(entries)
    work_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(transcript_text, encoding="utf-8")
    log.info(
        "Transcript fetched and cached: %d entries, %d chars",
        len(entries), len(transcript_text),
    )
    return entries


# --------------------------------------------------------------------------- #
# Step 3 & 4: Metadata + download  (PRESERVED from v1)                        #
# --------------------------------------------------------------------------- #


def fetch_metadata_and_download(url: str, work_dir: Path) -> tuple[dict, Path]:
    try:
        import yt_dlp
    except ImportError as e:
        raise SystemExit(
            "yt-dlp is not installed. Run: py -m pip install yt-dlp"
        ) from e

    out_template = str(work_dir / "source.%(ext)s")
    ydl_opts = {
        "format": DOWNLOAD_FORMAT,
        "outtmpl": out_template,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "socket_timeout": 30,  # seconds — prevents indefinite hang on slow/dead connections
    }

    log.info("Downloading video (low-res) via yt-dlp...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info.get("is_live") or info.get("was_live"):
        raise SystemExit("Live streams are not supported.")

    # Resolve channel_id; fall back to sanitized uploader slug if missing (Shorts/embeds)
    channel_id = info.get("channel_id")
    if not channel_id:
        uploader = info.get("uploader") or info.get("channel") or "unknown"
        channel_id = re.sub(r"[^a-z0-9]+", "-", uploader.lower()).strip("-") or "unknown"
        log.warning(
            "channel_id missing from yt-dlp response — using uploader slug: %r", channel_id
        )

    metadata = {
        "title": info.get("title", "Untitled"),
        "channel": info.get("uploader") or info.get("channel", "Unknown"),
        "channel_id": channel_id,
        "duration_sec": int(info.get("duration") or 0),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "description": (info.get("description") or "")[:500],
    }

    candidates = list(work_dir.glob("source.*"))
    if not candidates:
        raise SystemExit("yt-dlp did not produce a downloaded file.")
    video_path = candidates[0]
    log.info("Downloaded %s (%.1f MB)", video_path.name, video_path.stat().st_size / 1e6)
    return metadata, video_path


def fetch_metadata_only(url: str) -> dict:
    """
    Use yt-dlp to fetch video metadata WITHOUT downloading the video.
    Used by the gemini-direct path (Gemini reads YouTube natively; no download needed).
    Fix 13: skip-download for metadata on gemini-direct branch.
    """
    try:
        import yt_dlp
    except ImportError as e:
        raise SystemExit(
            "yt-dlp is not installed. Run: py -m pip install yt-dlp"
        ) from e

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True, "socket_timeout": 30}) as ydl:
        info = ydl.extract_info(url, download=False)

    # Resolve channel_id; fall back to sanitized uploader slug if missing (Shorts/embeds)
    channel_id = info.get("channel_id")
    if not channel_id:
        uploader = info.get("uploader") or info.get("channel") or "unknown"
        channel_id = re.sub(r"[^a-z0-9]+", "-", uploader.lower()).strip("-") or "unknown"
        log.warning(
            "channel_id missing from yt-dlp response — using uploader slug: %r", channel_id
        )

    return {
        "title": info.get("title", "Untitled"),
        "channel": info.get("uploader") or info.get("channel", "Unknown"),
        "channel_id": channel_id,
        "duration_sec": int(info.get("duration") or 0),
        "upload_date": info.get("upload_date"),
    }


# --------------------------------------------------------------------------- #
# Step 5a: Scene detection via PySceneDetect  (NEW, replaces ffmpeg filter)   #
# --------------------------------------------------------------------------- #


def get_ffmpeg_binary() -> str:
    """PRESERVED from v1."""
    try:
        import imageio_ffmpeg
    except ImportError as e:
        raise SystemExit(
            "imageio-ffmpeg is not installed. Run: py -m pip install imageio-ffmpeg"
        ) from e
    return imageio_ffmpeg.get_ffmpeg_exe()


def detect_scenes_pyscenedetect(video_path: Path) -> list[float]:
    """
    Run PySceneDetect ContentDetector on the video.
    Returns a list of scene-start timestamps in seconds.
    Falls back to fixed-interval (1 per 10s) signal if 0 scenes detected.
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError as e:
        raise SystemExit(
            "scenedetect is not installed. Run: py -m pip install scenedetect"
        ) from e

    log.info("Running PySceneDetect (threshold=%d)...", PYSCENEDETECT_THRESHOLD)
    try:
        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=PYSCENEDETECT_THRESHOLD))
        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()
    except Exception as exc:
        log.warning("PySceneDetect failed (%s) — will use fixed-interval fallback.", exc)
        return []

    timestamps = [
        scene[0].seconds if hasattr(scene[0], "seconds") else scene[0].get_seconds()
        for scene in scene_list
    ]
    log.info("PySceneDetect found %d scenes.", len(timestamps))
    return timestamps


# --------------------------------------------------------------------------- #
# Step 5b: Frame extraction at timestamps  (NEW)                              #
# --------------------------------------------------------------------------- #


def extract_frames_at_timestamps(
    video_path: Path,
    timestamps: list[float],
    frames_dir: Path,
    max_frames: int,
) -> list[tuple[Path, float]]:
    """
    Extract one frame per timestamp using ffmpeg.
    Returns list of (frame_path, timestamp_sec) sorted by timestamp.
    Resizes each frame to GRID_CELL_W × GRID_CELL_H.
    Falls back to fixed-interval if timestamps list is empty.
    """
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("frame_*.jpg"):
        f.unlink()

    ffmpeg = get_ffmpeg_binary()

    # Determine timestamps to extract
    if not timestamps:
        # Fixed-interval fallback: 1 frame per 10s
        log.warning("No scene timestamps — falling back to fixed-interval (1 frame/10s).")
        # Estimate duration via ffprobe-style call; use max_frames * 10s as upper bound
        ts_list: list[float] = [i * 10.0 for i in range(max_frames)]
    else:
        ts_list = sorted(timestamps)

    # Cap to max_frames
    if len(ts_list) > max_frames:
        # Evenly subsample to maintain coverage
        step = len(ts_list) / max_frames
        ts_list = [ts_list[int(i * step)] for i in range(max_frames)]

    results: list[tuple[Path, float]] = []
    vf = f"scale={GRID_CELL_W}:{GRID_CELL_H},format=yuvj420p"

    log.info("Extracting %d frames at scene timestamps...", len(ts_list))
    for i, ts in enumerate(ts_list):
        out_path = frames_dir / f"frame_{i:04d}.jpg"
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", str(ts),
            "-i", str(video_path),
            "-vf", vf,
            "-frames:v", "1",
            "-q:v", "5",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and out_path.exists():
            results.append((out_path, ts))
        else:
            log.debug("Frame extraction failed at ts=%.1f: %s", ts, result.stderr[:100])

    log.info("Extracted %d frames successfully.", len(results))
    return results


# --------------------------------------------------------------------------- #
# Step 5c: Perceptual-hash dedup  (NEW)                                       #
# --------------------------------------------------------------------------- #


def dedup_frames_by_hash(
    frames_with_ts: list[tuple[Path, float]],
) -> list[tuple[Path, float]]:
    """
    Remove near-duplicate frames using imagehash.dhash.
    Keeps a frame only if its hash differs from the previously kept frame
    by at least DEDUP_HASH_THRESHOLD (hamming distance).
    Returns the filtered list preserving original order.
    """
    try:
        import imagehash
        from PIL import Image
    except ImportError as e:
        raise SystemExit(
            "imagehash / Pillow not installed. Run: py -m pip install imagehash Pillow"
        ) from e

    if not frames_with_ts:
        return []

    kept: list[tuple[Path, float]] = []
    last_hash = None

    for frame_path, ts in frames_with_ts:
        try:
            img = Image.open(frame_path)
            h = imagehash.dhash(img)
        except Exception as exc:
            log.debug("Could not hash %s (%s) — keeping it.", frame_path.name, exc)
            kept.append((frame_path, ts))
            continue

        if last_hash is None or (h - last_hash) >= DEDUP_HASH_THRESHOLD:
            kept.append((frame_path, ts))
            last_hash = h
        else:
            frame_path.unlink(missing_ok=True)  # remove dupe to save disk

    log.info(
        "Dedup: %d → %d frames (removed %d near-duplicates).",
        len(frames_with_ts),
        len(kept),
        len(frames_with_ts) - len(kept),
    )
    return kept


# --------------------------------------------------------------------------- #
# Step 5d: Timestamp overlay  (NEW)                                           #
# --------------------------------------------------------------------------- #


def overlay_timestamp(frame_path: Path, ts_sec: float) -> None:
    """
    Burn a MM:SS timestamp into the top-left corner of the frame (in-place).
    Semi-transparent black background + white text via PIL.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise SystemExit("Pillow not installed. Run: py -m pip install Pillow") from e

    mm = int(ts_sec // 60)
    ss = int(ts_sec % 60)
    label = f"{mm:02d}:{ss:02d}"

    img = Image.open(frame_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # Best-effort font — fall back to default if truetype unavailable
    try:
        font = ImageFont.truetype("arial.ttf", size=18)
    except OSError:
        font = ImageFont.load_default()

    # Measure text
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad = 3

    # Semi-transparent background rectangle
    draw.rectangle(
        [0, 0, text_w + pad * 2, text_h + pad * 2],
        fill=(0, 0, 0, 160),
    )
    draw.text((pad, pad), label, fill=(255, 255, 255, 255), font=font)

    img.save(frame_path, "JPEG", quality=85)


# --------------------------------------------------------------------------- #
# Step 5e: Grid tiling  (NEW)                                                 #
# --------------------------------------------------------------------------- #


def tile_frames_into_grids(
    frames_with_ts: list[tuple[Path, float]],
    out_dir: Path,
) -> list[Path]:
    """
    Composite up to GRID_COLS × GRID_ROWS frames per grid image.
    Grid canvas: (GRID_CELL_W * GRID_COLS) × (GRID_CELL_H * GRID_ROWS).
    Partial last grid is padded with black cells.
    Returns list of grid image paths.
    """
    try:
        from PIL import Image
    except ImportError as e:
        raise SystemExit("Pillow not installed. Run: py -m pip install Pillow") from e

    out_dir.mkdir(parents=True, exist_ok=True)
    cells_per_grid = GRID_COLS * GRID_ROWS
    grid_w = GRID_CELL_W * GRID_COLS
    grid_h = GRID_CELL_H * GRID_ROWS

    grid_paths: list[Path] = []
    n_grids = math.ceil(len(frames_with_ts) / cells_per_grid) if frames_with_ts else 0

    # R2-2: import ImageDraw for placeholder rendering on paste failure
    try:
        from PIL import ImageDraw, ImageFont
    except ImportError:
        ImageDraw = None  # type: ignore[assignment]
        ImageFont = None  # type: ignore[assignment]

    def _draw_placeholder(canvas: "Image.Image", x: int, y: int) -> None:
        """Render a visible gray placeholder cell with 'MISSING' text at (x, y)."""
        if ImageDraw is None:
            return
        draw = ImageDraw.Draw(canvas)
        # Gray background
        draw.rectangle(
            [x, y, x + GRID_CELL_W - 1, y + GRID_CELL_H - 1],
            fill=(64, 64, 64),
        )
        label = "MISSING"
        try:
            font = ImageFont.truetype("arial.ttf", size=20)
        except Exception:
            font = ImageFont.load_default()
        # Center text
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = len(label) * 8, 12
        tx = x + (GRID_CELL_W - tw) // 2
        ty = y + (GRID_CELL_H - th) // 2
        draw.text((tx, ty), label, fill=(200, 200, 200), font=font)

    for g in range(n_grids):
        canvas = Image.new("RGB", (grid_w, grid_h), (0, 0, 0))
        batch = frames_with_ts[g * cells_per_grid : (g + 1) * cells_per_grid]

        real_pastes = 0
        placeholder_count = 0
        for idx, (frame_path, _ts) in enumerate(batch):
            row = idx // GRID_COLS
            col = idx % GRID_COLS
            x_off = col * GRID_CELL_W
            y_off = row * GRID_CELL_H
            try:
                cell = Image.open(frame_path).convert("RGB")
                cell = cell.resize((GRID_CELL_W, GRID_CELL_H), Image.LANCZOS)
                canvas.paste(cell, (x_off, y_off))
                real_pastes += 1
            except Exception as exc:
                # R2-2: render a visible placeholder instead of leaving the cell black
                _draw_placeholder(canvas, x_off, y_off)
                placeholder_count += 1
                log.warning(
                    "Frame paste failed at grid cell %d (%s): %s — placeholder rendered",
                    idx, frame_path.name, exc,
                )

        log.info(
            "Grid %d/%d: %d real frames + %d placeholders",
            g + 1, n_grids, real_pastes, placeholder_count,
        )

        grid_path = out_dir / f"grid_{g:02d}.jpg"
        canvas.save(grid_path, "JPEG", quality=85)
        grid_paths.append(grid_path)

    log.info("Tiled %d frames into %d grid image(s).", len(frames_with_ts), len(grid_paths))
    return grid_paths


# --------------------------------------------------------------------------- #
# Step 5f: Full Claude-path frame pipeline  (replaces extract_scene_frames)   #
# --------------------------------------------------------------------------- #


def build_frame_grids(
    video_path: Path,
    work_dir: Path,
    max_frames: int,
) -> tuple[list[tuple[Path, float]], list[Path], int]:
    """
    Full pipeline: detect → extract → dedup → overlay → tile.
    Returns (deduped_frames_with_ts, grid_paths, raw_frame_count).
    """
    frames_dir = work_dir / "frames"
    grids_dir = work_dir / "grids"

    # 1. Detect scenes
    timestamps = detect_scenes_pyscenedetect(video_path)

    # 2. Extract frames
    raw_frames = extract_frames_at_timestamps(video_path, timestamps, frames_dir, max_frames)
    raw_count = len(raw_frames)

    # 3. Dedup
    deduped = dedup_frames_by_hash(raw_frames)

    # 4. Burn timestamps
    for frame_path, ts in deduped:
        overlay_timestamp(frame_path, ts)

    # 5. Tile into grids
    grid_paths = tile_frames_into_grids(deduped, grids_dir)

    return deduped, grid_paths, raw_count


# --------------------------------------------------------------------------- #
# Step 6a: Claude analysis with tool-use + caching  (replaces analyze_with_claude)
# --------------------------------------------------------------------------- #


def encode_frame(path: Path) -> dict:
    """Encode a single image file as a base64 Claude vision block."""
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": data,
        },
    }


def _duration_str(duration_sec: int) -> str:
    mm = duration_sec // 60
    ss = duration_sec % 60
    return f"{mm:02d}:{ss:02d}"


def analyze_with_claude_v2(
    metadata: dict,
    transcript_text: str,
    grid_paths: list[Path],
    model_id: str,
    raw_frame_count: int,
    dedup_frame_count: int,
    creator_context: str | None = None,
) -> dict:
    """
    Send grid images + transcript to Claude via tool-use (forced submit_breakdown).
    Applies prompt caching on the tools block + system message.
    Returns the structured breakdown dict from the tool call.
    """
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise SystemExit(
            "anthropic is not installed. Run: py -m pip install anthropic"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in environment / .env")

    client = Anthropic(api_key=api_key)

    # Build user message: grid images + analysis prompt
    user_content: list[dict] = []
    for gp in grid_paths:
        user_content.append(encode_frame(gp))

    user_prompt = ANALYSIS_USER_PROMPT.format(
        title=metadata["title"],
        channel=metadata["channel"],
        duration_str=_duration_str(metadata.get("duration_sec", 0)),
        raw_frame_count=raw_frame_count,
        dedup_frame_count=dedup_frame_count,
        grid_count=len(grid_paths),
        transcript_text=transcript_text,
    )
    user_content.append({"type": "text", "text": user_prompt})

    # Tool with cache_control on the static tools block (via _to_anthropic_tool_format)
    tools_payload = [
        _to_anthropic_tool_format(TOOL_SCHEMA, cache_control={"type": "ephemeral"})
    ]

    # System with cache_control
    system_payload = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    if creator_context:
        log.info("Injecting creator context (%d chars) as pre-analysis user message.", len(creator_context))

    log.info(
        "Calling Claude (model=%s, grids=%d, dedup_frames=%d, transcript_chars=%d)...",
        model_id,
        len(grid_paths),
        dedup_frame_count,
        len(transcript_text),
    )

    # Build message list: [system(cached)] → [user(creator_context)?] → [user(grids+transcript)]
    # creator_context block has NO cache_control (per-channel, low reuse — would break caching)
    messages_payload: list[dict] = []
    if creator_context:
        messages_payload.append({"role": "user", "content": creator_context})
    messages_payload.append({"role": "user", "content": user_content})

    resp = client.messages.create(
        model=model_id,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=system_payload,
        tools=tools_payload,
        tool_choice={"type": "tool", "name": "submit_breakdown"},
        messages=messages_payload,
    )

    usage = resp.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    log.info(
        "Claude usage: input=%d, output=%d, cache_read=%d, cache_write=%d tokens",
        usage.input_tokens,
        usage.output_tokens,
        cache_read,
        cache_write,
    )

    # Extract tool_use block
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_breakdown":
            return block.input

    raise SystemExit("Claude did not call submit_breakdown — unexpected response shape.")


# --------------------------------------------------------------------------- #
# Step 6b: OpenRouter analysis (OpenAI-compatible SDK, tool-use)  (v3 NEW)    #
# --------------------------------------------------------------------------- #


def analyze_with_openrouter(
    metadata: dict,
    transcript_text: str,
    grid_paths: list[Path],
    model_id: str,
    raw_frame_count: int,
    dedup_frame_count: int,
    creator_context: str | None = None,
) -> dict:
    """
    Send grid images + transcript to any vision+tools model via OpenRouter.
    Uses the OpenAI-compatible API (base_url=https://openrouter.ai/api/v1).
    Works for Anthropic models, OpenAI GPT-4o, Google Gemini, etc. via OR.
    Returns the structured breakdown dict from the tool call.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise SystemExit(
            "openai is not installed. Run: py -m pip install openai"
        ) from e

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set in environment / .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Build user content: images as base64 data URLs (OpenAI format)
    user_content: list[dict] = []
    for gp in grid_paths:
        b64 = base64.standard_b64encode(gp.read_bytes()).decode("ascii")
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    user_prompt = ANALYSIS_USER_PROMPT.format(
        title=metadata["title"],
        channel=metadata["channel"],
        duration_str=_duration_str(metadata.get("duration_sec", 0)),
        raw_frame_count=raw_frame_count,
        dedup_frame_count=dedup_frame_count,
        grid_count=len(grid_paths),
        transcript_text=transcript_text,
    )
    user_content.append({"type": "text", "text": user_prompt})

    tool_def = _to_openai_tool_format(TOOL_SCHEMA)

    # Build message list: system → [user(creator_context)?] → user(grids+transcript)
    or_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if creator_context:
        log.info("Injecting creator context (%d chars) as pre-analysis user message (OR).", len(creator_context))
        or_messages.append({"role": "user", "content": creator_context})
    or_messages.append({"role": "user", "content": user_content})

    kwargs: dict = {
        "model": model_id,
        "messages": or_messages,
        "tools": [tool_def],
        "tool_choice": {"type": "function", "function": {"name": "submit_breakdown"}},
        "max_tokens": CLAUDE_MAX_TOKENS,
    }

    # Anthropic prompt caching passthrough via OR (only effective on anthropic/* models)
    if model_id.startswith("anthropic/"):
        kwargs["extra_body"] = {"cache_control": {"type": "ephemeral"}}

    log.info(
        "Calling OpenRouter (model=%s, grids=%d, dedup_frames=%d, transcript_chars=%d)...",
        model_id,
        len(grid_paths),
        dedup_frame_count,
        len(transcript_text),
    )

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        err_str = str(exc)
        if "402" in err_str or "payment" in err_str.lower() or "credit" in err_str.lower():
            raise SystemExit(
                f"OpenRouter returned a payment error: {exc}\n"
                "Top up credits at https://openrouter.ai/credits"
            ) from exc
        raise SystemExit(f"OpenRouter API call failed: {exc}") from exc

    # Log usage if available
    if resp.usage:
        log.info(
            "OR usage: prompt=%d, completion=%d tokens",
            resp.usage.prompt_tokens or 0,
            resp.usage.completion_tokens or 0,
        )

    # Parse the tool-call arguments (JSON string)
    choices = resp.choices
    if not choices or not choices[0].message.tool_calls:
        raise SystemExit(
            "OpenRouter did not return a tool call for submit_breakdown — "
            "unexpected response shape. Try --provider anthropic as fallback."
        )

    tool_call = choices[0].message.tool_calls[0]
    try:
        return json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Could not parse tool-call arguments as JSON: {exc}\n"
            f"Raw arguments: {tool_call.function.arguments[:500]}"
        ) from exc


# --------------------------------------------------------------------------- #
# Step 6c: Gemini path  (NEW in v2, preserved)                                #
# --------------------------------------------------------------------------- #

GEMINI_STRUCTURED_PROMPT = """\
You are a video content analyst. Watch this YouTube video and produce a structured breakdown.

Return ONLY a valid JSON object with these exact keys:
{{
  "summary": "<string — a 3-5 sentence prose overview of what the video is actually about: the subject, the argument or thesis, and the conclusion. Plain language. No marketing tone. Should let a reader understand the video's content without watching it.>",
  "key_takeaways": [
    "<string — complete sentence stating a specific point the viewer would walk away knowing>",
    ... 1-7 entries. Substantive content only (NOT craft observations like 'creator uses fast cuts'). On very short videos returning 1-2 bullets is fine — do NOT fabricate to fill quota. DISAMBIGUATION: transcript_highlights captures verbatim quote moments with timestamps; summary + key_takeaways are SYNTHESIZED content. Different purposes; don't duplicate."
  ],
  "hook": "<string — what grabs attention in first 15s; combine opening visual + opening line>",
  "pacing_cuts": [
    {{"timestamp": "MM:SS", "what_changes": "<string>"}},
    ... at least 3 entries
  ],
  "visual_storytelling": "<string — patterns: text overlays, b-roll, camera moves, color, framing>",
  "transcript_highlights": [
    {{"timestamp": "MM:SS", "quote": "<string>"}},
    ... 3-5 entries
  ],
  "content_ideas": ["<string>", ... 3-5 entries]
}}

Be specific, not generic. No compliments to the creator. This is a working research document.
"""


def analyze_with_gemini(url: str, metadata: dict, model_id: str, creator_context: str | None = None) -> dict:
    """
    Pass YouTube URL directly to Gemini (no frame extraction needed).
    Returns the same structured dict shape as analyze_with_claude_v2.
    """
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as e:
        raise SystemExit(
            "google-genai is not installed. Run: py -m pip install google-genai"
        ) from e

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set in environment / .env")

    client = genai.Client(api_key=api_key)

    if creator_context:
        log.info("Injecting creator context (%d chars) as leading Part (Gemini).", len(creator_context))

    log.info("Calling Gemini (model=%s) with YouTube URL...", model_id)

    # Build contents: [creator_context Part?] + URL Part + analysis prompt Part
    gemini_contents: list = []
    if creator_context:
        gemini_contents.append(genai_types.Part.from_text(text=creator_context))
    gemini_contents.append(genai_types.Part.from_uri(file_uri=url, mime_type="video/*"))
    gemini_contents.append(genai_types.Part.from_text(text=GEMINI_STRUCTURED_PROMPT))

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=gemini_contents,
        )
    except Exception as exc:
        raise SystemExit(f"Gemini API call failed: {exc}") from exc

    raw_text = response.text or ""
    log.info("Gemini response: %d chars", len(raw_text))

    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first line (```json) and last line (```)
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        cleaned = inner.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.warning("Gemini returned non-JSON — attempting partial parse. Error: %s", exc)
        # Best-effort: return a dict with raw text as hook
        return {
            "hook": cleaned[:500],
            "pacing_cuts": [],
            "visual_storytelling": "(Gemini response was not valid JSON — see raw output below)",
            "transcript_highlights": [],
            "content_ideas": [],
            "_raw_gemini_response": cleaned,
        }


# --------------------------------------------------------------------------- #
# Step 7: Markdown rendering  (replaces build_breakdown_markdown)              #
# --------------------------------------------------------------------------- #


def render_breakdown_markdown(
    url: str,
    metadata: dict,
    structured_data: dict,
    transcript_text: str | None = None,
    frame_count: int = 0,
    tier: str = "default",
) -> str:
    """
    Single renderer for both Claude and Gemini paths.
    Takes the structured dict and emits the markdown breakdown.
    """
    duration_sec = metadata.get("duration_sec") or 0
    mm = duration_sec // 60
    ss = duration_sec % 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _coerce_to_list(value, inner_keys: list[str] | None = None) -> list:
        """Opus sometimes returns list fields as XML-tagged strings. Parse them back."""
        if isinstance(value, list):
            return value
        if not isinstance(value, str) or not value.strip():
            return []
        item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
        items = item_pattern.findall(value)
        if not items:
            return [value.strip()] if not inner_keys else []
        if inner_keys:
            result = []
            for raw in items:
                d = {}
                for key in inner_keys:
                    m = re.search(rf"<{key}>(.*?)</{key}>", raw, re.DOTALL)
                    if m:
                        d[key] = m.group(1).strip()
                result.append(d if d else raw.strip())
            return result
        return [item.strip() for item in items]

    def _render_timestamped(items: list, ts_key: str, body_key: str, quote: bool = False) -> str:
        lines = []
        for item in items:
            if isinstance(item, dict):
                ts = item.get(ts_key, "?")
                body = item.get(body_key, "")
                lines.append(f'- **{ts}** — "{body}"' if quote else f"- **{ts}** — {body}")
            elif isinstance(item, str):
                lines.append(f"- {item}")
        return "\n".join(lines)

    pacing_md = _render_timestamped(
        _coerce_to_list(structured_data.get("pacing_cuts"), ["timestamp", "what_changes"]),
        "timestamp", "what_changes",
    )
    highlights_md = _render_timestamped(
        _coerce_to_list(structured_data.get("transcript_highlights"), ["timestamp", "quote"]),
        "timestamp", "quote", quote=True,
    )

    # Content ideas
    ideas = _coerce_to_list(structured_data.get("content_ideas"))
    ideas_md = "\n".join(f"- {idea}" for idea in ideas)

    # Frame line (only meaningful for Claude/OR path)
    frames_line = (
        f"**Frames processed:** {frame_count} (after dedup)\n"
        if frame_count > 0
        else ""
    )

    transcript_section = ""
    if transcript_text:
        transcript_section = f"""
---

## Full Transcript

<details>
<summary>Click to expand</summary>

```
{transcript_text}
```

</details>
"""

    # Summary and Key Takeaways (v4.1 — content-first sections)
    summary = structured_data.get("summary") or ""
    key_takeaways = _coerce_to_list(structured_data.get("key_takeaways"))
    summary_section = f"\n## Summary\n\n{summary}\n" if summary else ""
    takeaways_md = "\n".join(f"- {t}" for t in key_takeaways)
    takeaways_section = f"\n## Key Takeaways\n\n{takeaways_md}\n" if takeaways_md else ""

    return f"""# {metadata['title']}

**Channel:** {metadata['channel']}
**Duration:** {mm:02d}:{ss:02d}
**URL:** {url}
**Analyzed:** {now}
**Tier:** {tier}
{frames_line}{summary_section}{takeaways_section}
## The Hook (0:00–0:15)

{structured_data.get('hook', '—')}

## Pacing & Cuts

{pacing_md or '—'}

## Visual Storytelling

{structured_data.get('visual_storytelling', '—')}

## Transcript Highlights

{highlights_md or '—'}

## Content Ideas Inspired by This

{ideas_md or '—'}
{transcript_section}"""


# --------------------------------------------------------------------------- #
# Pricing table (shared between main and _run_batch)                          #
# --------------------------------------------------------------------------- #

_TIER_COST_PER_M_TOKENS: dict[str, float] = {
    # OpenRouter models (approx $ per M input tokens, incl. 5.5% OR fee)
    "anthropic/claude-sonnet-4.6": 3.17,
    "anthropic/claude-sonnet-4-6": 3.17,
    "anthropic/claude-opus-4.7": 15.86,
    "anthropic/claude-opus-4-7": 15.86,
    "google/gemini-2.5-pro": 1.27,
    "openai/gpt-4o": 2.65,
    "openai/gpt-4o-mini": 0.16,
    # Direct Anthropic (no OR fee)
    "claude-sonnet-4-6": 3.00,
    "claude-opus-4-7": 15.00,
    # Gemini direct (free quota)
    "gemini-2.5-flash": 0.00,
    "gemini-3.1-flash-lite-preview": 0.00,
}


def _estimate_cost(mid: str, est_input_tokens: int, est_output_tokens: int = 2000) -> str:
    price_per_m = _TIER_COST_PER_M_TOKENS.get(mid)
    if price_per_m is None:
        # Try prefix match for unknown variants (e.g. gemini-2.5-flash-*)
        for key, val in _TIER_COST_PER_M_TOKENS.items():
            if mid.startswith(key) or key.startswith(mid):
                price_per_m = val
                break
    if price_per_m is None:
        return "~$? unknown pricing"
    total = price_per_m * (est_input_tokens + est_output_tokens) / 1_000_000
    return f"~${total:.3f} expected"


# --------------------------------------------------------------------------- #
# Step 8: Output writers  (PRESERVED from v1)                                 #
# --------------------------------------------------------------------------- #


def write_outputs(
    breakdown_md: str,
    work_dir: Path,
    metadata: dict,
    obsidian_vault: Path | None,
) -> tuple[Path, Path | None]:
    primary = work_dir / "breakdown.md"
    primary.write_text(breakdown_md, encoding="utf-8")

    vault_path: Path | None = None
    if obsidian_vault:
        if not obsidian_vault.exists():
            log.warning(
                "OBSIDIAN_VAULT path does not exist: %s — skipping vault write.",
                obsidian_vault,
            )
        else:
            target_dir = obsidian_vault / "Video Breakdowns"
            target_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            slug = slugify(metadata["title"])
            vault_path = target_dir / f"{date_str}_{slug}.md"
            vault_path.write_text(breakdown_md, encoding="utf-8")

    return primary, vault_path


# --------------------------------------------------------------------------- #
# Single-URL analysis core (extracted for reuse by both main and _run_batch)  #
# --------------------------------------------------------------------------- #


def _analyze_single_url(
    url: str,
    provider: str,
    tier: str,
    model_id: str,
    vault_path_obj: Path | None,
    args,  # argparse Namespace — carries max_frames, keep_source, refresh_transcript, etc.
    creator_profiles_mod=None,  # optional: the imported creator_profiles module
) -> dict:
    """
    Analyze a single YouTube URL end-to-end.

    Returns a result dict:
      {url, video_id, status, breakdown_path, tokens_used, cost, error,
       metadata, channel_id, channel_name}

    status: "ok" | "error"
    """
    result: dict = {
        "url": url,
        "video_id": None,
        "status": "error",
        "breakdown_path": None,
        "tokens_used": 0,
        "cost": "~$0.000",
        "error": None,
        "channel_id": None,
        "channel_name": None,
    }

    # SSRF guard
    if not _YOUTUBE_HOST_RE.match(url):
        result["error"] = f"URL must be a YouTube URL; got: {url!r}"
        return result

    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        result["error"] = str(e)
        return result

    result["video_id"] = video_id
    work_dir = TMP_BASE / video_id
    work_dir.mkdir(parents=True, exist_ok=True)

    log.info("=== Analyzing %s (video_id=%s) ===", url, video_id)

    try:
        # ------------------------------------------------------------------
        # Gemini-direct path
        # ------------------------------------------------------------------
        if provider == "gemini-direct":
            metadata = fetch_metadata_only(url)
            metadata["video_id"] = video_id
            (work_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            result["channel_id"] = metadata.get("channel_id")
            result["channel_name"] = metadata.get("channel", "Unknown")

            # Creator-profile READ
            creator_context: str | None = None
            use_profiles = creator_profiles_mod and not getattr(args, "no_creator_profile", False)
            if use_profiles:
                profile = creator_profiles_mod.load_profile(metadata["channel_id"])
                if profile:
                    creator_context = creator_profiles_mod.format_creator_context(profile)
                    if creator_context:
                        log.info(
                            "Using creator profile for %s (%d prior videos)",
                            metadata["channel"],
                            profile.get("build_count", 0),
                        )

            structured = analyze_with_gemini(url, metadata, model_id, creator_context=creator_context)

            breakdown_md = render_breakdown_markdown(
                url=url,
                metadata=metadata,
                structured_data=structured,
                tier="gemini",
            )
            primary, vault_path = write_outputs(breakdown_md, work_dir, metadata, vault_path_obj)
            result["breakdown_path"] = str(primary)
            result["status"] = "ok"

            # Creator-profile WRITE + distill
            if use_profiles:
                breakdown_text = primary.read_text(encoding="utf-8")
                updated = creator_profiles_mod.append_video_to_profile(
                    metadata["channel_id"], metadata["channel"], metadata, breakdown_text
                )
                if getattr(args, "refresh_creator_profile", False) or creator_profiles_mod.should_distill(updated):
                    updated = creator_profiles_mod.distill_profile(updated, tier=tier)
                    log.info(
                        "Distilled creator profile for %s from %d videos",
                        metadata["channel"],
                        updated.get("build_count", 0),
                    )

            return result

        # ------------------------------------------------------------------
        # Claude / OpenRouter path
        # ------------------------------------------------------------------
        transcript_entries = get_or_fetch_transcript(
            video_id, work_dir,
            force_refresh=getattr(args, "refresh_transcript", False),
        )
        transcript_text = format_transcript(transcript_entries)
        log.info("Transcript ready: %d entries, %d chars", len(transcript_entries), len(transcript_text))

        metadata, video_path = fetch_metadata_and_download(url, work_dir)
        metadata["video_id"] = video_id
        (work_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        result["channel_id"] = metadata.get("channel_id")
        result["channel_name"] = metadata.get("channel", "Unknown")

        max_frames = getattr(args, "max_frames", MAX_FRAMES_DEFAULT)
        deduped_frames, grid_paths, raw_frame_count = build_frame_grids(video_path, work_dir, max_frames)
        dedup_frame_count = len(deduped_frames)
        grid_count = len(grid_paths)

        est_visual_tokens = grid_count * 1400
        est_transcript_tokens = len(transcript_text) // 4
        est_total_tokens = est_visual_tokens + est_transcript_tokens + 500

        # ------------------------------------------------------------------
        # Deep-dry-run check (inside single-URL core so batch can trigger it)
        # ------------------------------------------------------------------
        if getattr(args, "deep_dry_run", False):
            print(json.dumps({
                "video_id": video_id,
                "title": metadata["title"],
                "channel": metadata.get("channel"),
                "channel_id": metadata.get("channel_id"),
                "duration_sec": metadata["duration_sec"],
                "tier": tier,
                "provider": provider,
                "model_id": model_id,
                "transcript_chars": len(transcript_text),
                "raw_frames_before_dedup": raw_frame_count,
                "distinct_frames_after_dedup": dedup_frame_count,
                "grid_count": grid_count,
                "estimated_input_tokens": est_total_tokens,
                "estimated_cost": _estimate_cost(model_id, est_total_tokens),
                "work_dir": str(work_dir),
            }, indent=2))
            if not getattr(args, "keep_source", False) and video_path.exists():
                try:
                    video_path.unlink()
                except (PermissionError, OSError) as exc:
                    log.warning("Could not delete source .mp4: %s", exc)
            result["status"] = "ok"
            return result

        # Creator-profile READ
        creator_context = None
        use_profiles = creator_profiles_mod and not getattr(args, "no_creator_profile", False)
        if use_profiles:
            profile = creator_profiles_mod.load_profile(metadata["channel_id"])
            if profile:
                creator_context = creator_profiles_mod.format_creator_context(profile)
                if creator_context:
                    log.info(
                        "Using creator profile for %s (%d prior videos)",
                        metadata["channel"],
                        profile.get("build_count", 0),
                    )

        if provider == "openrouter":
            structured = analyze_with_openrouter(
                metadata=metadata,
                transcript_text=transcript_text,
                grid_paths=grid_paths,
                model_id=model_id,
                raw_frame_count=raw_frame_count,
                dedup_frame_count=dedup_frame_count,
                creator_context=creator_context,
            )
        else:
            # provider == "anthropic"
            structured = analyze_with_claude_v2(
                metadata=metadata,
                transcript_text=transcript_text,
                grid_paths=grid_paths,
                model_id=model_id,
                raw_frame_count=raw_frame_count,
                dedup_frame_count=dedup_frame_count,
                creator_context=creator_context,
            )

        try:
            (work_dir / "structured_response.json").write_text(
                json.dumps(structured, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("Could not cache structured_response.json: %s", exc)

        breakdown_md = render_breakdown_markdown(
            url=url,
            metadata=metadata,
            structured_data=structured,
            transcript_text=transcript_text,
            frame_count=dedup_frame_count,
            tier=tier,
        )
        primary, vault_path = write_outputs(breakdown_md, work_dir, metadata, vault_path_obj)

        # Fix 8 — wrap unlink() in try/except for Windows PermissionError
        if not getattr(args, "keep_source", False) and video_path.exists():
            try:
                video_path.unlink()
                log.info("Deleted source .mp4 to save disk.")
            except (PermissionError, OSError) as exc:
                log.warning("Could not delete source .mp4 (file in use): %s", exc)

        result["breakdown_path"] = str(primary)
        result["cost"] = _estimate_cost(model_id, est_total_tokens)
        result["tokens_used"] = est_total_tokens
        result["status"] = "ok"

        # Creator-profile WRITE + distill (per-video, not batch-end — R2 fix)
        if use_profiles:
            breakdown_text = primary.read_text(encoding="utf-8")
            updated = creator_profiles_mod.append_video_to_profile(
                metadata["channel_id"], metadata["channel"], metadata, breakdown_text
            )
            if getattr(args, "refresh_creator_profile", False) or creator_profiles_mod.should_distill(updated):
                updated = creator_profiles_mod.distill_profile(updated, tier=tier)
                log.info(
                    "Distilled creator profile for %s from %d videos",
                    metadata["channel"],
                    updated.get("build_count", 0),
                )

        return result

    except SystemExit as exc:
        result["error"] = str(exc)
        return result
    except Exception as exc:
        log.exception("Unexpected error analyzing %s", url)
        result["error"] = str(exc)
        return result


# --------------------------------------------------------------------------- #
# Batch loop                                                                   #
# --------------------------------------------------------------------------- #


def _run_batch(urls: list[str], args, provider: str, tier: str, model_id: str,
               vault_path_obj: Path | None, creator_profiles_mod=None) -> int:
    """
    Process multiple YouTube URLs sequentially (or in parallel with --parallel N).

    Returns exit code:
      0 — all succeeded
      1 — all failed
      2 — partial (some succeeded, some failed)
    """
    import uuid
    import concurrent.futures

    run_id = uuid.uuid4().hex[:8]
    batch_dir = TMP_BASE / f"_batch_{run_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    log.info("Batch run %s: %d URLs", run_id, len(urls))

    parallel = getattr(args, "parallel", 1) or 1

    results: list[dict] = []

    if parallel > 1:
        log.info("Parallel mode: N=%d", parallel)
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(
                    _analyze_single_url,
                    url, provider, tier, model_id, vault_path_obj, args, creator_profiles_mod,
                ): url
                for url in urls
            }
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
    else:
        for url in urls:
            r = _analyze_single_url(
                url, provider, tier, model_id, vault_path_obj, args, creator_profiles_mod
            )
            results.append(r)
            status_sym = "[OK]" if r["status"] == "ok" else "[FAIL]"
            log.info("%s %s", status_sym, url)

    # ------------------------------------------------------------------
    # Batch summary
    # ------------------------------------------------------------------
    successes = [r for r in results if r["status"] == "ok"]
    failures  = [r for r in results if r["status"] != "ok"]

    total_tokens = sum(r.get("tokens_used", 0) for r in successes)

    print("\n" + "=" * 60)
    print(f"BATCH SUMMARY  (run_id={run_id})")
    print("=" * 60)
    print(f"  {len(urls)} URLs processed, {len(successes)} succeeded, {len(failures)} failed")
    if total_tokens:
        print(f"  Total estimated tokens: {total_tokens:,}")
    print()

    if successes:
        print("  Breakdowns written:")
        for r in successes:
            print(f"    [OK]   {r['url']} -> {r['breakdown_path']}")
    if failures:
        print("  Failures:")
        for r in failures:
            print(f"    [FAIL] {r['url']} — {r['error']}")

    # R3 finding 2: surface "no profile context yet" for channels below threshold
    if creator_profiles_mod and not getattr(args, "no_creator_profile", False):
        channels_below: dict[str, dict] = {}
        for r in successes:
            cid = r.get("channel_id")
            cname = r.get("channel_name", "Unknown")
            if cid:
                profile = creator_profiles_mod.load_profile(cid)
                if profile:
                    bc = profile.get("build_count", 0)
                    thresh = profile.get("next_distillation_threshold", 3)
                    if bc < thresh:
                        channels_below[cid] = {
                            "name": cname, "build_count": bc, "threshold": thresh
                        }
        if channels_below:
            print()
            for cid, info in channels_below.items():
                bc, thresh = info["build_count"], info["threshold"]
                lo, hi = max(1, bc - len(urls) + 1), bc
                print(
                    f"  NOTE: Videos {lo}-{hi} processed without creator-profile context "
                    f"for {info['name']} "
                    f"(threshold of {thresh} not yet reached — distill on next run)."
                )

    print("=" * 60)

    # Write summary markdown
    summary_lines = [
        f"# Batch Analysis Summary\n",
        f"**Run ID:** {run_id}  ",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Total URLs:** {len(urls)}  ",
        f"**Succeeded:** {len(successes)}  ",
        f"**Failed:** {len(failures)}  ",
        "",
        "## Results",
        "",
    ]
    for r in results:
        sym = "OK" if r["status"] == "ok" else "FAIL"
        line = f"- [{sym}] {r['url']}"
        if r["status"] == "ok":
            line += f" — [{r.get('breakdown_path', '')}]({r.get('breakdown_path', '')})"
        else:
            line += f" — ERROR: {r.get('error', '')}"
        summary_lines.append(line)

    summary_path = batch_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"\n  Summary written: {summary_path}")

    if not failures:
        return 0
    if not successes:
        return 1
    return 2


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube video analyzer — v4 (batch mode + creator-profile cache)."
    )
    # v4: accept multiple positional URLs
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more YouTube video URLs. Combine with --urls-file for larger batches.",
    )
    parser.add_argument(
        "--urls-file",
        type=str,
        default=None,
        help="Path to a file with one YouTube URL per line. '#' lines and blank lines are skipped.",
    )
    parser.add_argument(
        "--tier",
        choices=["default", "premium", "gemini"],
        default="default",
        help=(
            "Analysis tier: 'default' (latest Sonnet-equivalent via registry), "
            "'premium' (latest Opus-equivalent), "
            "'gemini' (free URL-native via Gemini direct, or paid frame-grid via OR if no GEMINI_API_KEY). "
            "Default: default"
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "anthropic", "gemini-direct", "auto"],
        default="auto",
        help=(
            "Provider to use. 'auto' (default) selects based on env vars: "
            "OPENROUTER_API_KEY -> openrouter; ANTHROPIC_API_KEY -> anthropic; "
            "GEMINI_API_KEY -> gemini-direct (for --tier gemini). "
            "Override with an explicit provider to bypass auto-detection."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Exact model ID — escape hatch that bypasses the registry. "
            "Requires --tier to know which provider path to use."
        ),
    )
    parser.add_argument(
        "--refresh-models",
        action="store_true",
        help="Force model registry to re-fetch from provider APIs (bypass 7-day cache).",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=MAX_FRAMES_DEFAULT,
        help=f"Max frames to extract before dedup (default {MAX_FRAMES_DEFAULT}, range 1-200).",
    )
    parser.add_argument(
        "--obsidian-vault",
        type=str,
        default=None,
        help="Override OBSIDIAN_VAULT env var (must be an absolute path).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Shallow dry-run: no network calls. Uses cached model IDs or LAST_KNOWN_GOOD fallback. "
            "No transcript fetch, no video download. Prints planned config + would_* fields and exits. "
            "Use --deep-dry-run for the full pipeline cost-estimation dry-run."
        ),
    )
    parser.add_argument(
        "--deep-dry-run",
        action="store_true",
        help=(
            "Deep dry-run: runs PySceneDetect + frame extraction + token counting "
            "WITHOUT calling the AI API. Produces cost estimate with real frame/grid counts. "
            "Downloads the video; slower than --dry-run."
        ),
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Do not delete the downloaded .mp4 after analysis.",
    )
    parser.add_argument(
        "--refresh-transcript",
        action="store_true",
        help="Force re-fetch transcript from YouTube even if a cached transcript.txt exists.",
    )
    # v4: creator-profile flags
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        metavar="N",
        help="Process N URLs in parallel (default: 1 = sequential). Use with caution — YouTube may rate-limit.",
    )
    parser.add_argument(
        "--refresh-creator-profile",
        action="store_true",
        help="Force re-distillation of the creator profile even if threshold not yet reached.",
    )
    parser.add_argument(
        "--show-creator-profile",
        type=str,
        default=None,
        metavar="CHANNEL_ID",
        help="Print the creator profile JSON for a given channel_id and exit. Requires --no-analyze.",
    )
    parser.add_argument(
        "--no-creator-profile",
        action="store_true",
        help="Skip creator-profile read AND write for this run (regression-safe escape hatch).",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="Skip the analysis pipeline entirely. Used with --show-creator-profile.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # --show-creator-profile validation
    # ------------------------------------------------------------------
    if args.show_creator_profile and not args.no_analyze:
        parser.error("--show-creator-profile requires --no-analyze")

    if args.show_creator_profile and args.no_analyze:
        sys.path.insert(0, str(WORKSPACE_ROOT / "execution" / "modules"))
        try:
            import creator_profiles as cp  # type: ignore[import-not-found]
        except ImportError as e:
            raise SystemExit(f"Could not import creator_profiles: {e}") from e
        profile = cp.load_profile(args.show_creator_profile)
        if profile is None:
            print(
                f"No profile found for channel_id={args.show_creator_profile!r}. "
                f"Profiles are stored in {cp.get_profile_path(args.show_creator_profile)}",
                file=sys.stderr,
            )
            return 1
        print(json.dumps(profile, indent=2, ensure_ascii=False))
        return 0

    # ------------------------------------------------------------------
    # Collect + validate URLs upfront (fail fast)
    # ------------------------------------------------------------------
    all_urls: list[str] = list(args.urls or [])

    if args.urls_file:
        urls_file = Path(args.urls_file)
        if not urls_file.exists():
            parser.error(f"--urls-file not found: {args.urls_file!r}")
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                all_urls.append(stripped)

    if not all_urls:
        parser.error("Provide at least one URL as a positional argument or via --urls-file.")

    # Validate all URLs upfront
    for url in all_urls:
        if not _YOUTUBE_HOST_RE.match(url):
            parser.error(f"URL must be a YouTube URL; got: {url!r}")
        try:
            extract_video_id(url)
        except ValueError as e:
            parser.error(str(e))

    # Fix 2 — validate --max-frames range
    if args.max_frames < 1 or args.max_frames > 200:
        parser.error("--max-frames must be between 1 and 200")

    # ------------------------------------------------------------------
    # Model registry import
    # ------------------------------------------------------------------
    try:
        sys.path.insert(0, str(WORKSPACE_ROOT / "execution" / "modules"))
        from model_registry import resolve_model  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            f"Could not import model_registry: {e}\n"
            "Ensure execution/modules/model_registry.py exists."
        ) from e

    tier = args.tier

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------
    if args.provider == "auto":
        provider = _auto_detect_provider(tier)
    else:
        provider = args.provider

    # R2-3 — full tier/provider cross-validation matrix
    _VALID_COMBOS = {
        "default":  {"anthropic", "openrouter", "auto"},
        "premium":  {"anthropic", "openrouter", "auto"},
        "gemini":   {"gemini-direct", "openrouter", "auto"},
    }
    if args.provider not in _VALID_COMBOS[args.tier]:
        parser.error(
            f"--tier {args.tier} is incompatible with --provider {args.provider}. "
            f"Valid providers for tier '{args.tier}': {sorted(_VALID_COMBOS[args.tier])}"
        )

    # ------------------------------------------------------------------
    # Model resolution (once, outside any loop)
    # ------------------------------------------------------------------
    _allow_net = not args.dry_run

    if args.model:
        model_id = args.model
        log.info("Using user-supplied model override: %s", model_id)
    else:
        if provider == "openrouter":
            or_tier = "gemini" if tier == "gemini" else ("premium" if tier == "premium" else "default")
            model_id = resolve_model("openrouter", or_tier, refresh=args.refresh_models, allow_network=_allow_net)
        elif provider == "anthropic":
            registry_tier = "premium" if tier == "premium" else "default"
            model_id = resolve_model("anthropic", registry_tier, refresh=args.refresh_models, allow_network=_allow_net)
        elif provider == "gemini-direct":
            model_id = resolve_model("gemini", "default", refresh=args.refresh_models, allow_network=_allow_net)
        else:
            raise SystemExit(f"Unknown provider: {provider!r}")
        log.info("Resolved model: %s -> %s", provider, model_id)

    # Mode log line
    if provider == "openrouter":
        cost_note = "paid frame-grid mode via OR -- NOT free URL-native" if tier == "gemini" else "paid via OR (incl. 5.5% OR fee)"
    elif provider == "anthropic":
        cost_note = "paid direct"
    else:
        cost_note = "FREE (URL-native Gemini)"
    log.info("Mode: %s / %s / %s", provider, model_id, cost_note)

    # ------------------------------------------------------------------
    # Obsidian vault
    # ------------------------------------------------------------------
    vault_arg = args.obsidian_vault or os.environ.get("OBSIDIAN_VAULT")
    if vault_arg:
        if not Path(vault_arg).is_absolute():
            parser.error(f"--obsidian-vault must be an absolute path; got: {vault_arg!r}")
        vault_path_obj = Path(vault_arg).resolve()
    else:
        vault_path_obj = None

    # ------------------------------------------------------------------
    # SHALLOW dry-run gate (single URL only — before any network calls)
    # ------------------------------------------------------------------
    if args.dry_run:
        url = all_urls[0]
        video_id = extract_video_id(url)
        work_dir = TMP_BASE / video_id
        est_grids_guess = max(1, args.max_frames // 9)
        est_visual_tokens_guess = est_grids_guess * 1400
        est_total_guess = est_visual_tokens_guess + 2500 + 500
        print(json.dumps({
            "video_id": video_id,
            "tier": tier,
            "provider": provider,
            "model_id": model_id,
            "would_fetch_transcript": True,
            "would_download_video": provider != "gemini-direct",
            "would_call_provider": provider,
            "would_use_model": model_id,
            "estimated_cost": _estimate_cost(model_id, est_total_guess),
            "note": (
                "Shallow dry-run: no network calls made. "
                "Use --deep-dry-run for real frame/grid counts and token estimate."
            ),
            "work_dir": str(work_dir),
        }, indent=2))
        return 0

    # ------------------------------------------------------------------
    # Creator-profiles module (lazy import, skipped if --no-creator-profile)
    # ------------------------------------------------------------------
    creator_profiles_mod = None
    if not args.no_creator_profile:
        try:
            import creator_profiles as cp_mod  # type: ignore[import-not-found]
            creator_profiles_mod = cp_mod
        except ImportError:
            log.warning(
                "creator_profiles module not found — creator-profile features disabled. "
                "Ensure execution/modules/creator_profiles.py exists."
            )

    # ------------------------------------------------------------------
    # Single-URL path (v3 backward compat) vs batch path
    # ------------------------------------------------------------------
    if len(all_urls) == 1:
        # Single-URL: preserve original print behavior
        url = all_urls[0]
        result = _analyze_single_url(
            url, provider, tier, model_id, vault_path_obj, args, creator_profiles_mod
        )
        if result["status"] == "ok":
            if result["breakdown_path"]:
                print(f"\n[OK] Breakdown written: {result['breakdown_path']}")
            return 0
        else:
            print(f"\nERROR: {result['error']}", file=sys.stderr)
            return 1
    else:
        return _run_batch(
            all_urls, args, provider, tier, model_id, vault_path_obj, creator_profiles_mod
        )


if __name__ == "__main__":
    sys.exit(main())
