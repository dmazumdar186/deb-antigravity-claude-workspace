---
name: diagram-generator
description: Generate hand-drawn style diagrams from text descriptions. Whiteboard-sketch aesthetic with pastel boxes, simple icons, and clean labels. Use when creating diagrams, flowcharts, architecture visuals, or explanatory illustrations.
allowed-tools: Read, Bash, Glob
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Diagram Generator — Hand-Drawn Style

## Goal
Generate clean, hand-drawn style diagrams from natural language descriptions. Output looks like a whiteboard sketch — pastel rounded rectangles, simple line-art icons, thin arrows, clean labels on white background.

## Usage

```bash
python3 .claude/skills/diagram-generator/generate_diagram.py "description of diagram" --aspect 16:9
```

### Options
- `--aspect` — Aspect ratio (default: `16:9`)
- `--output` / `-o` — Custom output path (default: `.tmp/diagrams/TIMESTAMP_SLUG.png`)

### Examples
```bash
# Architecture diagram
python3 .claude/skills/diagram-generator/generate_diagram.py "Claude Skills architecture: central hub with 5 spokes"

# Pipeline flow
python3 .claude/skills/diagram-generator/generate_diagram.py "Lead gen pipeline: scrape → enrich → outreach" --aspect 16:9

# Custom output path
python3 .claude/skills/diagram-generator/generate_diagram.py "Multi-agent consensus pattern" -o my_diagram.png
```

## Environment
Requires in `.env`:
```
NANO_BANANA_API_KEY=your_gemini_api_key
```

## Output
- Default location: `Business/active/.tmp/diagrams/`
- Format: PNG
- Style: Pastel boxes, hand-drawn aesthetic, white background, no photorealistic elements

## Cost
~$0.02-0.05 per generation (Gemini Flash)

## Model
Uses `gemini-3.1-flash-image-preview` via google-genai SDK.
