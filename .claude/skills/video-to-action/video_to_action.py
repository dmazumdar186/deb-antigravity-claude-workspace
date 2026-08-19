#!/usr/bin/env python3
"""
Video-to-Action: Extract actionable steps from YouTube videos using Gemini.

Gemini analyzes the actual video (visual + audio) and returns structured
step-by-step breakdowns. Supports full video upload or transcript-only mode.

Usage:
    # Full analysis (downloads video, uploads to Gemini)
    python3 video_to_action.py "https://youtube.com/watch?v=VIDEO_ID"

    # Ask a specific question about the video
    python3 video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" -q "What shortcuts are used?"

    # Quick mode (transcript only — faster, cheaper, no visual context)
    python3 video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" --quick

    # Save output to file
    python3 video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" -o active/steps.md
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

API_KEY = os.getenv("NANO_BANANA_API_KEY")
DEFAULT_MODEL = "gemini-2.5-flash"

STEPS_PROMPT = """You are a meticulous technical documenter. Analyze this video frame-by-frame and produce an EXHAUSTIVE, hyper-detailed step-by-step breakdown — as if creating a photographic reconstruction manual that someone could follow with zero prior knowledge.

## Header (provide at the top):
- **Title**: Descriptive title for the procedure
- **Prerequisites**: Everything needed before starting (accounts, software versions, API keys, prior setup)
- **Tools/Software**: Every tool, platform, browser extension, or service shown
- **Key Takeaways**: Critical tips, warnings, gotchas, and best practices mentioned throughout

## For EVERY step, provide ALL of the following:

1. **Step number & Timestamp** (MM:SS)
2. **Action**: Exact imperative instruction
3. **UI Path**: Full click path (e.g., "Settings → Advanced → Toggle 'Enable X'")
4. **Exact Values**: Every field value, dropdown selection, toggle state, URL, expression, or parameter — reproduced character-for-character
5. **Code/Expressions**: Any code snippets, regex patterns, n8n expressions, formulas, or scripts shown — reproduce EXACTLY as displayed, including any on-screen corrections or overlays that fix earlier code
6. **Configuration**: Every checkbox, toggle, dropdown, radio button, and their exact states (enabled/disabled, selected value)
7. **Node Connections**: What this step's output connects to (which node, which input port)
8. **Visual Context**: What's visible on screen — panel names, tab names, sidebar state, modal dialogs
9. **Reasoning**: WHY the presenter makes this choice (if explained)
10. **Mistakes & Corrections**: Any errors the presenter makes and how they fix them
11. **On-Screen Annotations**: Any text overlays, pop-up corrections, or callout boxes that appear

## Additional sections at the end:
- **Scaling & Production Notes**: Any advice on taking this from demo to production scale
- **Common Pitfalls**: Warnings about what can go wrong
- **Complete Architecture Diagram**: ASCII or text description of the full workflow/system from start to finish with all connections

Be EXTREMELY granular. A reader should be able to recreate this EXACTLY from your description alone, without watching the video. When in doubt, include more detail, not less.

Format as clean, well-structured markdown with nested details."""

QUERY_PROMPT = """Watch this video carefully and answer the following question:

{query}

Be specific and reference timestamps where relevant. If the video shows visual procedures,
describe them in detail including exact UI elements, menu paths, settings, and values shown."""


def extract_video_id(url: str) -> str | None:
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_transcript(url: str) -> str | None:
    """Get video transcript via yt-dlp auto-subs."""
    video_id = extract_video_id(url)
    if not video_id:
        return None

    tmp_dir = Path(tempfile.gettempdir()) / "v2a_subs"
    tmp_dir.mkdir(exist_ok=True)

    try:
        subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en",
             "--skip-download", "--sub-format", "vtt",
             "-o", str(tmp_dir / "%(id)s"), url],
            capture_output=True, text=True, timeout=30
        )

        # Find the subtitle file
        vtt_path = None
        for f in tmp_dir.glob(f"{video_id}*.vtt"):
            vtt_path = f
            break

        if not vtt_path or not vtt_path.exists():
            return None

        text = vtt_path.read_text()
        vtt_path.unlink()

        # Parse VTT: keep timestamps + text, strip tags
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')):
                continue
            line = re.sub(r'<[^>]+>', '', line)
            if line:
                lines.append(line)
        return '\n'.join(lines)
    except Exception as e:
        print(f"Warning: transcript extraction failed: {e}", file=sys.stderr)
    return None


def download_video(url: str) -> Path | None:
    """Download video at low resolution for Gemini upload."""
    tmp_dir = Path(tempfile.gettempdir()) / "v2a_video"
    tmp_dir.mkdir(exist_ok=True)

    video_id = extract_video_id(url)
    output_path = tmp_dir / f"{video_id}.mp4"

    if output_path.exists():
        output_path.unlink()

    try:
        subprocess.run(
            ["yt-dlp",
             "-f", "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst",
             "--merge-output-format", "mp4",
             "--max-filesize", "200M",
             "-o", str(output_path), url],
            capture_output=True, text=True, timeout=300
        )

        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"Downloaded video: {size_mb:.1f}MB", file=sys.stderr)
            return output_path
    except Exception as e:
        print(f"Warning: video download failed: {e}", file=sys.stderr)
    return None


def extract_frames(video_path: Path, interval: int = 30) -> list[Path]:
    """Extract frames at regular intervals using ffmpeg."""
    frames_dir = video_path.parent / "frames"
    frames_dir.mkdir(exist_ok=True)

    for f in frames_dir.glob("*.jpg"):
        f.unlink()

    try:
        subprocess.run(
            ["ffmpeg", "-i", str(video_path),
             "-vf", f"fps=1/{interval}", "-q:v", "5",
             str(frames_dir / "frame_%04d.jpg")],
            capture_output=True, timeout=120
        )
        frames = sorted(frames_dir.glob("*.jpg"))
        print(f"Extracted {len(frames)} frames (every {interval}s)", file=sys.stderr)
        return frames
    except Exception as e:
        print(f"Warning: frame extraction failed: {e}", file=sys.stderr)
    return []


def upload_to_gemini(file_path: Path, client: genai.Client):
    """Upload file to Gemini File API and wait for processing."""
    uploaded = client.files.upload(file=file_path)

    while uploaded.state == "PROCESSING":
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state == "ACTIVE":
        return uploaded
    raise RuntimeError(f"File upload failed: state={uploaded.state}")


def analyze_full(url: str, query: str | None, client: genai.Client, model: str) -> str:
    """Download video → upload to Gemini → analyze."""
    video_path = download_video(url)
    if not video_path:
        print("Video download failed, falling back to frames+transcript", file=sys.stderr)
        return analyze_frames(url, None, query, client, model)

    print("Uploading to Gemini...", file=sys.stderr)
    try:
        uploaded = upload_to_gemini(video_path, client)
    except Exception as e:
        print(f"Upload failed ({e}), falling back to frames+transcript", file=sys.stderr)
        return analyze_frames(url, video_path, query, client, model)

    prompt = QUERY_PROMPT.format(query=query) if query else STEPS_PROMPT

    try:
        response = client.models.generate_content(
            model=model,
            contents=[uploaded, prompt]
        )
        # Cleanup
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass
        video_path.unlink(missing_ok=True)
        return response.text
    except Exception as e:
        print(f"Video analysis failed ({e}), falling back to frames+transcript", file=sys.stderr)
        return analyze_frames(url, video_path, query, client, model)


def analyze_frames(url: str, video_path: Path | None, query: str | None,
                   client: genai.Client, model: str) -> str:
    """Fallback: transcript + extracted frames sent as images."""
    transcript = get_transcript(url)
    frames = extract_frames(video_path, interval=30) if video_path and video_path.exists() else []

    prompt = QUERY_PROMPT.format(query=query) if query else STEPS_PROMPT
    parts = []

    if transcript:
        parts.append(f"## Video Transcript\n\n{transcript[:50000]}")

    # Include up to 20 frames
    for i, frame_path in enumerate(frames[:20]):
        try:
            img = Image.open(frame_path)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            parts.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))
            parts.append(f"[Frame at ~{(i + 1) * 30}s]")
        except Exception:
            continue

    if not parts:
        raise RuntimeError("No transcript or frames available. Cannot analyze.")

    parts.append(prompt)

    response = client.models.generate_content(model=model, contents=parts)

    # Cleanup
    if video_path:
        video_path.unlink(missing_ok=True)
    for f in frames:
        f.unlink(missing_ok=True)

    return response.text


def analyze_transcript(url: str, query: str | None, client: genai.Client, model: str) -> str:
    """Quick mode: transcript only."""
    transcript = get_transcript(url)
    if not transcript:
        raise RuntimeError("Could not get transcript. Does the video have captions?")

    prompt = QUERY_PROMPT.format(query=query) if query else STEPS_PROMPT
    full_prompt = f"## Video Transcript\n\n{transcript[:80000]}\n\n---\n\n{prompt}"

    response = client.models.generate_content(model=model, contents=full_prompt)
    return response.text


def main():
    parser = argparse.ArgumentParser(description="Extract actionable steps from YouTube videos via Gemini")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--query", "-q", help="Specific question to ask about the video")
    parser.add_argument("--quick", action="store_true",
                        help="Transcript-only mode (faster, cheaper, no visual context)")
    parser.add_argument("--json", action="store_true", help="Output as JSON wrapper")
    parser.add_argument("--output", "-o", help="Save output to file")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL,
                        help=f"Gemini model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not API_KEY:
        print("Error: NANO_BANANA_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"Error: invalid YouTube URL: {args.url}", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=API_KEY)

    mode = "quick" if args.quick else "full"
    print(f"Analyzing: {args.url} | Mode: {mode} | Model: {args.model}", file=sys.stderr)

    if args.quick:
        result = analyze_transcript(args.url, args.query, client, args.model)
    else:
        result = analyze_full(args.url, args.query, client, args.model)

    if args.json:
        output = json.dumps({
            "video_url": args.url,
            "video_id": video_id,
            "mode": mode,
            "query": args.query,
            "analysis": result
        }, indent=2)
    else:
        output = result

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
        print(f"\nSaved to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
