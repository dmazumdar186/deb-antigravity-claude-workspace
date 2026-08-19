#!/usr/bin/env python3
"""
Diagram Generator — Nano Banana Pro 2

Generates hand-drawn style diagrams from text descriptions.
Style: pastel colored boxes, simple icons, arrows, clean labels on white background.

Usage:
    python generate_diagram.py "Claude Skills architecture: central hub with 5 spokes"
    python generate_diagram.py "Lead gen pipeline: scrape → enrich → outreach" --aspect 16:9
    python generate_diagram.py "Multi-agent consensus pattern" --output my_diagram.png
"""

import argparse
import base64
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.getenv("NANO_BANANA_API_KEY")
MODEL = "gemini-3.1-flash-image-preview"
OUTPUT_DIR = Path(__file__).parent.parent / ".tmp" / "diagrams"

STYLE_PREFIX = """Create a clean, hand-drawn style diagram on a white background. Use soft pastel colored rounded rectangles (light purple, light blue, light green, light pink, light yellow, light teal) for each concept. Include simple line-art icons inside each box. Use thin black arrows to show relationships. Text labels should be clean, dark, and easy to read. Style should look like a whiteboard sketch or notebook illustration — professional but approachable, similar to educational YouTube thumbnails. No photorealistic elements. No gradients. Keep it minimal and clear."""


def generate_diagram(
    description: str,
    aspect_ratio: str = "16:9",
    output_path: str | None = None,
) -> Path:
    """Generate a diagram image from a text description."""
    client = genai.Client(api_key=API_KEY)

    prompt = f"{STYLE_PREFIX}\n\nDiagram to create: {description}"

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    # Extract image from response
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            mime = part.inline_data.mime_type or "image/png"
            ext = "png" if "png" in mime else "jpg"

            if output_path:
                out = Path(output_path)
            else:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                slug = description[:50].lower().replace(" ", "_").replace("/", "_")
                slug = "".join(c for c in slug if c.isalnum() or c == "_")
                out = OUTPUT_DIR / f"{timestamp}_{slug}.{ext}"

            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(image_bytes)
            print(f"Saved: {out}")
            return out

    print("ERROR: No image in response", file=sys.stderr)
    if response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.text:
                print(f"Model said: {part.text}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate hand-drawn style diagrams")
    parser.add_argument("description", help="What the diagram should show")
    parser.add_argument("--aspect", default="16:9", help="Aspect ratio (default: 16:9)")
    parser.add_argument("--output", "-o", help="Output file path")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: NANO_BANANA_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    path = generate_diagram(args.description, args.aspect, args.output)
    print(f"Done: {path}")
