---
name: thumbnail-generator
description: Generate YouTube thumbnails by face-swapping onto existing templates, then modify colors, text, and styling. Use when creating thumbnails, recreating thumbnails from other creators, or designing YouTube thumbnails.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Thumbnail Generator — Face Swap + Style Variations

## Goal
Take inspiration thumbnails, generate new thumbnails with Debanjan Mazumdar's face swapped in, then apply modifications. Always produce 5 variations.

## How It Works
1. Send Debanjan Mazumdar's reference photo + target thumbnail to Nano Banana Pro 2 (Gemini image gen)
2. Model swaps Debanjan Mazumdar into the thumbnail
3. Run 5 parallel generations for variation

## Prompt Behavior

### Default (no user edits requested)
When the user just provides a thumbnail to recreate with no additional modification instructions, use this `--prompt`:

```
Replace the man in the thumbnail with the man in the supplied image (the one holding the trophy). The face should match exactly, so that it is the second man in the thumbnail, not the first. Use dynamic contrast on the face. Change nothing else.
```

### With user edits
When the user provides additional modification instructions (e.g., "change background to blue", "replace text with X"), **drop the "Change nothing else" part** and append their instructions instead:

```
Replace the man in the thumbnail with the man in the supplied image (the one holding the trophy). The face should match exactly, so that it is the second man in the thumbnail, not the first. Use dynamic contrast on the face. [USER'S EDIT INSTRUCTIONS HERE]
```

Always pass the prompt via `--prompt` on the CLI.

## Quick Start

```bash
# From YouTube URL
python3 .claude/skills/thumbnail-generator/recreate_thumbnails.py --youtube "https://youtube.com/watch?v=VIDEO_ID"

# From image URL (faster — skips video ID parsing)
python3 .claude/skills/thumbnail-generator/recreate_thumbnails.py --source "https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg"

# From local file
python3 .claude/skills/thumbnail-generator/recreate_thumbnails.py --source "path/to/thumbnail.jpg"

# Edit pass (refine a generated thumbnail)
python3 .claude/skills/thumbnail-generator/recreate_thumbnails.py --edit "active/thumbnails/20260305/120000_abcd_1.png" --prompt "replace text with 'AI AGENTS'"
```

## Always Generate 5 Variations in Parallel
Run 5 parallel processes, each with `-n 1`. The script uses random suffixes in filenames so parallel runs don't collide.

```bash
for i in 1 2 3 4 5; do
  python3 .claude/skills/thumbnail-generator/recreate_thumbnails.py --source "URL" -n 1 \
    --prompt "YOUR PROMPT HERE" &
done
wait
```

## File Locations

| Path | Purpose |
|------|---------|
| `active/thumbnails/face/face.png` | Debanjan Mazumdar's face reference photo (clean headshot) |
| `active/thumbnails/YYYYMMDD/` | Generated thumbnails organized by date |
| `.claude/skills/thumbnail-generator/recreate_thumbnails.py` | Main script |

## Environment
Requires in `.env`:
```
NANO_BANANA_API_KEY=your_gemini_api_key
```

## Dependencies
`google-genai`, `Pillow`, `requests`, `python-dotenv` — no mediapipe, no opencv, no numpy.

## Cost
~$0.14-0.24 per generation. 5 variations = ~$0.80 total.
