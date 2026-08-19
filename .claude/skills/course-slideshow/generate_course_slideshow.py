#!/usr/bin/env python3
"""
Course Slideshow Generator

Takes a course outline markdown, generates 3 diagrams per chapter via Gemini,
and assembles everything into a single Excalidraw file laid out as a vertical
slideshow:

    Course Title (large text)

    Chapter 1 Heading
    [Diagram 1]   [Diagram 2]   [Diagram 3]

    Chapter 2 Heading
    [Diagram 1]   [Diagram 2]   [Diagram 3]

    ...

Usage:
    python generate_course_slideshow.py <outline.md> [--output out.excalidraw]
    python generate_course_slideshow.py <outline.md> --chapters 0,1,2  # only first 3
    python generate_course_slideshow.py <outline.md> --dry-run  # parse only, no generation
"""

import argparse
import base64
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────

API_KEY = os.getenv("NANO_BANANA_API_KEY")
MODEL = "gemini-3.1-flash-image-preview"

STYLE_PREFIX = (
    "Create a clean, hand-drawn style diagram on a PURE WHITE (#FFFFFF) background. "
    "The background MUST be perfectly white — no gray, no off-white, no paper texture, "
    "no noise, no subtle tint. Pure flat white everywhere that is not a drawn element. "
    "Use ONLY these exact colors for all drawn elements — boxes, borders, fills, arrows, "
    "and accents. This is a strict palette, do not use any other colors:\n"
    "  - #333333 (Dark Charcoal) — text labels, thin arrows, outlines\n"
    "  - #6b7080 (Slate) — dark box fills, primary containers\n"
    "  - #9a9ea8 (Silver) — secondary box fills, mid-tone elements\n"
    "  - #b3c4c4 (Pale Steel) — tertiary fills, connectors, subtle accents\n"
    "  - #d4d9cc (Light Sage) — lightest fills, background boxes, muted elements\n"
    "Use rounded rectangles for each concept. Include simple line-art icons inside each box. "
    "Use thin dark arrows to show relationships. Text labels should be clean, dark, "
    "and easy to read (always #333333 or #6b7080). "
    "Style should look like a whiteboard sketch or notebook illustration — "
    "professional but approachable, similar to educational YouTube thumbnails. "
    "No photorealistic elements. No gradients. No shadows. No paper texture. "
    "Keep it minimal and clear. "
    "The diagram must be 16:9 aspect ratio (wide, not tall)."
)

# Layout constants (pixels on the infinite Excalidraw canvas)
IMG_WIDTH = 640          # each diagram image width
IMG_HEIGHT = 360         # 16:9 ratio
IMG_GAP = 400            # horizontal gap between diagrams (5x original)
CHAPTER_GAP = 600        # vertical gap between chapter sections (5x original)
HEADING_TO_IMG = 250     # vertical gap from heading to images (5x ~50)
TITLE_HEIGHT = 70        # space for course title
START_X = 100            # left margin
START_Y = 100            # top margin
MAX_PARALLEL = 3         # parallel Gemini requests


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class Chapter:
    number: str           # "0", "1", "2", etc.
    title: str            # full heading text
    content: str          # everything under this heading
    diagrams: list[Path] = field(default_factory=list)


@dataclass
class CourseOutline:
    title: str
    chapters: list[Chapter]


# ── Outline parser ──────────────────────────────────────────────────────────

def parse_outline(md_path: Path) -> CourseOutline:
    """Parse a course outline markdown into structured chapters."""
    text = md_path.read_text()
    lines = text.split("\n")

    # Extract title from first H1
    title = "Untitled Course"
    for line in lines:
        if line.startswith("# ") and not re.match(r"^# \d+\.", line):
            title = line.lstrip("# ").strip()
            break

    # Split into chapters at H1 boundaries: "# N. ..." or "# 0. ..."
    chapter_pattern = re.compile(r"^# (\d+)\.\s+(.+)$")
    chapters = []
    current_chapter = None
    content_lines = []

    for line in lines:
        match = chapter_pattern.match(line)
        if match:
            # Save previous chapter
            if current_chapter is not None:
                current_chapter.content = "\n".join(content_lines).strip()
                chapters.append(current_chapter)
            current_chapter = Chapter(
                number=match.group(1),
                title=match.group(2).strip(),
                content="",
            )
            content_lines = []
        elif current_chapter is not None:
            content_lines.append(line)

    # Save last chapter
    if current_chapter is not None:
        current_chapter.content = "\n".join(content_lines).strip()
        chapters.append(current_chapter)

    return CourseOutline(title=title, chapters=chapters)


# ── Diagram generation ──────────────────────────────────────────────────────

def split_content_into_subtopics(content: str) -> list[str]:
    """Split chapter content into ~3 distinct subtopic chunks.

    Splits on bold markdown headers (**Header:**) or paragraph boundaries,
    aiming for 3 roughly equal sections covering different material.
    """
    # Try splitting on bold headers first (e.g. **How it works:** or **Part 1:**)
    bold_pattern = re.compile(r'\n(?=\*\*[^*]+(?::|—)\*?\*?\s)')
    sections = bold_pattern.split(content)
    sections = [s.strip() for s in sections if s.strip()]

    if len(sections) >= 3:
        # Merge into exactly 3 groups
        per_group = max(1, len(sections) // 3)
        groups = [
            "\n\n".join(sections[:per_group]),
            "\n\n".join(sections[per_group:2 * per_group]),
            "\n\n".join(sections[2 * per_group:]),
        ]
        return [g[:1500] for g in groups]

    # Fallback: split on double newlines (paragraph boundaries)
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        per_group = max(1, len(paragraphs) // 3)
        groups = [
            "\n\n".join(paragraphs[:per_group]),
            "\n\n".join(paragraphs[per_group:2 * per_group]),
            "\n\n".join(paragraphs[2 * per_group:]),
        ]
        return [g[:1500] for g in groups]

    # Last resort: just return the whole content 3 times (short chapter)
    return [content[:1500]] * 3


def make_diagram_prompts(chapter: Chapter) -> list[str]:
    """Generate 3 diagram descriptions for a chapter, each covering a DIFFERENT subtopic."""
    title = chapter.title
    subtopics = split_content_into_subtopics(chapter.content)

    prompts = []
    for i, subtopic in enumerate(subtopics):
        prompts.append(
            f"{STYLE_PREFIX}\n\n"
            f"This chapter is titled: \"{title}\"\n\n"
            f"Create a diagram for THIS SPECIFIC SUBTOPIC (part {i+1} of 3):\n"
            f"{subtopic}\n\n"
            f"IMPORTANT: Focus ONLY on the content above. Do NOT create a general "
            f"overview of \"{title}\". Instead, visualize the specific concepts, "
            f"steps, or comparisons described in this subtopic text. "
            f"Pick the best diagram style (architecture, flow, comparison, checklist, "
            f"or table) based on what the content naturally calls for."
        )
    return prompts


def generate_single_diagram(
    client: genai.Client, prompt: str, output_path: Path, max_retries: int = 3, timeout: int = 120
) -> Path:
    """Generate one diagram image via Gemini with timeout and retries."""
    import signal

    class TimeoutError(Exception):
        pass

    def _handler(signum, frame):
        raise TimeoutError("Gemini request timed out")

    for attempt in range(1, max_retries + 1):
        try:
            old_handler = signal.signal(signal.SIGALRM, _handler)
            signal.alarm(timeout)
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(image_bytes)
                    return output_path

            raise RuntimeError(f"No image in Gemini response for: {output_path.name}")

        except TimeoutError:
            if attempt < max_retries:
                print(f"timeout (attempt {attempt}/{max_retries}), retrying...", end=" ", flush=True)
            else:
                raise RuntimeError(f"Gemini timed out {max_retries} times for: {output_path.name}")
        except Exception as e:
            if attempt < max_retries and "timeout" in str(e).lower():
                print(f"error (attempt {attempt}/{max_retries}), retrying...", end=" ", flush=True)
            else:
                raise


def generate_chapter_diagrams(
    chapter: Chapter,
    output_dir: Path,
    client: genai.Client,
) -> list[Path]:
    """Generate 3 diagrams for a chapter. Returns list of PNG paths."""
    prompts = make_diagram_prompts(chapter)
    paths = []

    for i, prompt in enumerate(prompts):
        slug = re.sub(r"[^a-z0-9]+", "_", chapter.title.lower())[:40]
        out_path = output_dir / f"ch{chapter.number}_{slug}_d{i+1}.png"

        if out_path.exists():
            print(f"  [cached] {out_path.name}")
            paths.append(out_path)
            continue

        print(f"  [generating] {out_path.name}...", end=" ", flush=True)
        try:
            generate_single_diagram(client, prompt, out_path)
            print("done")
            paths.append(out_path)
        except Exception as e:
            print(f"FAILED: {e}")
            # Create a placeholder so layout still works
            paths.append(None)

    return paths


# ── Excalidraw assembly ─────────────────────────────────────────────────────

def make_id(length: int = 10) -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def create_text_element(
    text: str, x: float, y: float, font_size: int = 28
) -> dict:
    # Approximate width: fontSize * 0.6 per char (Nunito)
    width = len(text) * font_size * 0.6
    height = font_size * 1.25
    return {
        "id": make_id(),
        "type": "text",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "index": "a" + make_id(2),
        "roundness": None,
        "seed": random.randint(1, 2**31),
        "version": 1,
        "versionNonce": random.randint(1, 2**31),
        "isDeleted": False,
        "boundElements": None,
        "updated": int(time.time() * 1000),
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": font_size,
        "fontFamily": 5,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": text,
        "autoResize": True,
        "lineHeight": 1.25,
    }


def create_image_element(
    file_id: str, x: float, y: float, width: float, height: float
) -> dict:
    return {
        "id": make_id(),
        "type": "image",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": "transparent",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "index": "a" + make_id(2),
        "roundness": None,
        "seed": random.randint(1, 2**31),
        "version": 1,
        "versionNonce": random.randint(1, 2**31),
        "isDeleted": False,
        "boundElements": None,
        "updated": int(time.time() * 1000),
        "link": None,
        "locked": False,
        "fileId": file_id,
        "status": "saved",
        "scale": [1, 1],
        "crop": None,
    }


def embed_image_file(image_path: Path) -> tuple[str, dict]:
    """Read PNG, return (fileId, fileData) for Excalidraw files object."""
    image_bytes = image_path.read_bytes()
    file_id = hashlib.sha1(image_bytes).hexdigest()

    suffix = image_path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime = mime_map.get(suffix, "image/png")

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    file_data = {
        "mimeType": mime,
        "id": file_id,
        "dataURL": data_url,
        "created": int(time.time() * 1000),
    }
    return file_id, file_data


def assemble_excalidraw(
    outline: CourseOutline,
    chapters_with_diagrams: list[tuple[Chapter, list[Path]]],
) -> dict:
    """Build the complete Excalidraw JSON with embedded images."""
    elements = []
    files = {}
    y_cursor = START_Y

    # Course title
    elements.append(
        create_text_element(outline.title, START_X, y_cursor, font_size=40)
    )
    y_cursor += TITLE_HEIGHT + 40

    # Each chapter (1-based display numbering)
    for display_idx, (chapter, diagram_paths) in enumerate(chapters_with_diagrams, start=1):
        # Chapter heading (1-based)
        heading = f"{display_idx}. {chapter.title}"
        elements.append(
            create_text_element(heading, START_X, y_cursor, font_size=32)
        )
        y_cursor += HEADING_TO_IMG

        # 3 diagrams side by side
        for i, img_path in enumerate(diagram_paths):
            if img_path is None or not img_path.exists():
                continue

            file_id, file_data = embed_image_file(img_path)
            files[file_id] = file_data

            x = START_X + i * (IMG_WIDTH + IMG_GAP)
            elements.append(
                create_image_element(file_id, x, y_cursor, IMG_WIDTH, IMG_HEIGHT)
            )

        y_cursor += IMG_HEIGHT + CHAPTER_GAP

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://github.com/{{USERNAME}}/course-pipeline",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff",
        },
        "files": files,
    }


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a course slideshow Excalidraw file from an outline"
    )
    parser.add_argument("outline", help="Path to course outline markdown file")
    parser.add_argument("--output", "-o", help="Output .excalidraw file path")
    parser.add_argument(
        "--chapters",
        help="Comma-separated chapter indices to process (e.g. 0,1,2). Default: all",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse outline and show chapters without generating diagrams",
    )
    parser.add_argument(
        "--diagrams-dir",
        help="Directory for intermediate diagram PNGs (default: active/.tmp/course-diagrams/)",
    )
    args = parser.parse_args()

    outline_path = Path(args.outline)
    if not outline_path.exists():
        print(f"ERROR: {outline_path} not found", file=sys.stderr)
        sys.exit(1)

    # Parse outline
    print(f"Parsing: {outline_path}")
    outline = parse_outline(outline_path)
    print(f"Title: {outline.title}")
    print(f"Chapters: {len(outline.chapters)}")
    for ch in outline.chapters:
        print(f"  {ch.number}. {ch.title} ({len(ch.content)} chars)")

    if args.dry_run:
        print("\n[dry-run] No diagrams generated.")
        return

    # Filter chapters if specified
    chapters = outline.chapters
    if args.chapters:
        indices = [int(x.strip()) for x in args.chapters.split(",")]
        chapters = [ch for ch in chapters if int(ch.number) in indices]
        print(f"\nFiltered to {len(chapters)} chapters: {[ch.number for ch in chapters]}")

    if not API_KEY:
        print("ERROR: NANO_BANANA_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=API_KEY)

    # Diagrams directory
    diagrams_dir = Path(
        args.diagrams_dir
        or str(Path(__file__).resolve().parent / "../../../active/.tmp/course-diagrams")
    ).resolve()
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nDiagrams dir: {diagrams_dir}")

    # Generate diagrams for each chapter
    chapters_with_diagrams = []
    total_diagrams = len(chapters) * 3
    generated = 0

    for chapter in chapters:
        print(f"\nChapter {chapter.number}: {chapter.title}")
        diagram_paths = generate_chapter_diagrams(chapter, diagrams_dir, client)
        chapters_with_diagrams.append((chapter, diagram_paths))
        generated += sum(1 for p in diagram_paths if p is not None)

    print(f"\nGenerated {generated}/{total_diagrams} diagrams")

    # Assemble Excalidraw file
    print("\nAssembling Excalidraw file...")
    excalidraw_data = assemble_excalidraw(outline, chapters_with_diagrams)

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", outline.title.lower())[:50]
        output_path = Path(f"active/youtube-strategy/diagrams/{slug}_slideshow.excalidraw")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(excalidraw_data))

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nSaved: {output_path}")
    print(f"File size: {file_size_mb:.1f} MB")
    print(f"Elements: {len(excalidraw_data['elements'])}")
    print(f"Embedded images: {len(excalidraw_data['files'])}")
    print(f"\nOpen at: https://excalidraw.com → File → Open")


if __name__ == "__main__":
    main()
