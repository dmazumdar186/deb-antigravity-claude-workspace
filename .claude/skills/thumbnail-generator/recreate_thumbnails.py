#!/usr/bin/env python3
"""
Recreate YouTube thumbnails with Debanjan Mazumdar's face using Nano Banana Pro 2.

Send a reference photo of Nick + the target thumbnail to Gemini image gen.
Generates 5 variations by default.

Usage:
    # From YouTube URL
    python3 recreate_thumbnails.py --youtube "https://youtube.com/watch?v=VIDEO_ID"

    # From local file or image URL
    python3 recreate_thumbnails.py --source "path/to/thumbnail.jpg"

    # Edit pass (refine a generated thumbnail)
    python3 recreate_thumbnails.py --edit "path/to/generated.png" --prompt "change background to blue"
"""

import argparse
import base64
import io
import os
import random
import re
import string
import sys
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types

load_dotenv()

# Constants
REFERENCE_PHOTOS_DIR = Path(__file__).parent.parent.parent.parent / "active" / "thumbnails" / "face"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "active" / "thumbnails"
API_KEY = os.getenv("NANO_BANANA_API_KEY")
MODEL = "gemini-3-pro-image-preview"
THUMB_SIZE = (1280, 720)


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_youtube_thumbnail(video_id: str) -> Image.Image | None:
    """Download YouTube thumbnail in best available quality."""
    for quality in ['maxresdefault', 'sddefault', 'hqdefault', 'mqdefault']:
        url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                if img.size[0] > 200:
                    print(f"Downloaded thumbnail: {quality} ({img.size})")
                    return img
        except Exception:
            continue
    return None


def load_reference_photo() -> Image.Image | None:
    """Load Debanjan Mazumdar's face reference photo."""
    if not REFERENCE_PHOTOS_DIR.exists():
        print(f"Warning: Reference photos not found at {REFERENCE_PHOTOS_DIR}")
        return None

    # Look for face.png first, then any image
    face_path = REFERENCE_PHOTOS_DIR / "face.png"
    if face_path.exists():
        img = Image.open(face_path).convert("RGB")
        print(f"Loaded reference: {face_path.name}")
        return img

    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    for f in sorted(REFERENCE_PHOTOS_DIR.iterdir()):
        if f.suffix.lower() in extensions:
            img = Image.open(f).convert("RGB")
            print(f"Loaded reference: {f.name}")
            return img

    return None


def generate_thumbnail(
    source_image: Image.Image,
    reference_photo: Image.Image,
    additional_prompt: str = "",
    extra_images: list[tuple[str, Image.Image]] | None = None,
) -> Image.Image | None:
    """
    Generate a thumbnail with Nick's face swapped in.

    Sends reference photo + source thumbnail to Gemini, asks for face swap.
    extra_images: list of (label, Image) tuples for additional reference images.
    """
    client = genai.Client(api_key=API_KEY)

    thumb = source_image.copy()
    thumb.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)

    # Build contents array and image labels
    contents: list = [reference_photo, thumb]
    image_labels = "IMAGE 1: Reference photo of the person to insert.\nIMAGE 2: A YouTube thumbnail to recreate."
    if extra_images:
        for i, (label, img) in enumerate(extra_images, start=3):
            contents.append(img)
            image_labels += f"\nIMAGE {i}: {label}"

    prompt = f"""{image_labels}

TASK: Replace the person in the thumbnail with the person from the reference image. The face should match exactly, so that it is the reference person in the thumbnail, not the original person. Change nothing else.

Output in 16:9 format at 1280x720.

{additional_prompt}"""

    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    data = part.inline_data.data
                    if data:
                        img_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        return Image.open(io.BytesIO(img_bytes))
                elif hasattr(part, 'text') and part.text:
                    print(f"Model note: {part.text[:200]}")

        print("No image in response")
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None


def edit_thumbnail(
    source_image: Image.Image,
    edit_instructions: str,
) -> Image.Image | None:
    """Edit an existing thumbnail with instructions."""
    client = genai.Client(api_key=API_KEY)

    thumb = source_image.copy()
    thumb.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)

    prompt = f"""IMAGE 1: A thumbnail that needs editing.

TASK: Make the following changes to this thumbnail:
{edit_instructions}

Keep everything else exactly the same. Only modify what is explicitly requested.
Output in 16:9 format at 1280x720."""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[thumb, prompt],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    data = part.inline_data.data
                    if data:
                        img_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        return Image.open(io.BytesIO(img_bytes))
                elif hasattr(part, 'text') and part.text:
                    print(f"Model note: {part.text[:200]}")

        print("No image in response")
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Recreate YouTube thumbnails with Debanjan Mazumdar")
    parser.add_argument("--youtube", "-y", type=str, help="YouTube video URL")
    parser.add_argument("--source", "-s", type=str, help="Source thumbnail URL or file path")
    parser.add_argument("--edit", "-e", type=str, help="Edit an existing thumbnail (path)")
    parser.add_argument("--prompt", "-p", type=str, default="", help="Additional instructions")
    parser.add_argument("--output", "-o", type=str, help="Output filename")
    parser.add_argument("--variations", "-n", type=int, default=5, help="Number of variations (default: 5)")
    parser.add_argument("--refs", type=str, nargs="*", help="Extra reference images as 'label::path' pairs")

    args = parser.parse_args()

    if not API_KEY:
        print("Error: NANO_BANANA_API_KEY not set in .env")
        sys.exit(1)

    # Create date-based output folder
    date_folder = OUTPUT_DIR / datetime.now().strftime("%Y%m%d")
    date_folder.mkdir(parents=True, exist_ok=True)
    time_stamp = datetime.now().strftime("%H%M%S") + "_" + "".join(random.choices(string.ascii_lowercase, k=4))

    # === EDIT MODE ===
    if args.edit:
        if not args.prompt:
            print("Error: --edit requires --prompt with edit instructions")
            sys.exit(1)

        print(f"Loading image to edit: {args.edit}")
        edit_image = Image.open(args.edit)

        result = edit_thumbnail(edit_image, args.prompt)
        if result is None:
            print("Edit failed")
            sys.exit(1)

        output_path = date_folder / (args.output or f"{time_stamp}_edited.png")
        result.save(output_path)
        print(f"\nSaved: {output_path}")
        return

    # === RECREATION MODE ===
    if not args.youtube and not args.source:
        print("Error: Provide --youtube URL, --source image, or --edit image")
        sys.exit(1)

    # Load source thumbnail
    source_image = None
    if args.youtube:
        video_id = extract_video_id(args.youtube)
        if not video_id:
            print(f"Error: Could not extract video ID from {args.youtube}")
            sys.exit(1)
        source_image = get_youtube_thumbnail(video_id)
        if not source_image:
            print("Error: Could not download YouTube thumbnail")
            sys.exit(1)
    elif args.source:
        if args.source.startswith(("http://", "https://")):
            resp = requests.get(args.source, timeout=30)
            resp.raise_for_status()
            source_image = Image.open(io.BytesIO(resp.content))
        else:
            source_image = Image.open(args.source)

    print(f"Source size: {source_image.size}")

    # Load reference photo
    reference_photo = load_reference_photo()
    if not reference_photo:
        print("Warning: No reference photo found. Results may vary.")

    # Load extra reference images if provided
    extra_images = None
    if args.refs:
        extra_images = []
        for ref in args.refs:
            if "::" in ref:
                label, path = ref.split("::", 1)
            else:
                label, path = Path(ref).stem, ref
            img = Image.open(path).convert("RGB")
            extra_images.append((label, img))
            print(f"Loaded extra ref: {label} ({path})")

    # Generate variations
    output_paths = []
    for i in range(args.variations):
        print(f"\n--- Variation {i + 1}/{args.variations} ---")

        result = generate_thumbnail(
            source_image=source_image,
            reference_photo=reference_photo,
            additional_prompt=args.prompt,
            extra_images=extra_images,
        )

        if result is None:
            print(f"Failed to generate variation {i + 1}")
            continue

        if args.output and args.variations == 1:
            output_path = date_folder / args.output
        else:
            output_path = date_folder / f"{time_stamp}_{i + 1}.png"

        result.save(output_path)
        output_paths.append(str(output_path))
        print(f"Saved: {output_path}")

    print(f"\n=== Generated {len(output_paths)}/{args.variations} variations ===")
    for path in output_paths:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
