---
name: video-to-action
description: Extract actionable steps from YouTube videos using Gemini video understanding. Use when user provides a YouTube link and wants to learn procedures, extract steps, understand visual tutorials, or turn video content into executable instructions.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Video-to-Action — Learn from YouTube via Gemini

## Goal
Take a YouTube URL → send the video to Gemini → get back structured, actionable steps that Claude can understand and execute. Works for tutorials, demos, how-tos, and any procedural video content.

## How It Works

1. **Full mode** (default): Downloads video at low res → uploads to Gemini File API → Gemini watches the video and returns structured analysis
2. **Quick mode** (`--quick`): Extracts transcript only → sends to Gemini → faster and cheaper but no visual context
3. **Fallback chain**: If video upload fails → extracts frames every 30s + transcript → sends as images + text

## Usage

```bash
# Default: full video analysis (visual + audio)
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID"

# Ask a specific question about the video
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" -q "What keyboard shortcuts are demonstrated?"

# Quick mode: transcript only (faster, cheaper)
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" --quick

# Save to file
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" -o active/steps.md

# JSON output
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" --json

# Use Gemini Pro for maximum detail (slower, more expensive)
python3 .claude/skills/video-to-action/video_to_action.py "https://youtube.com/watch?v=VIDEO_ID" -m gemini-2.5-pro
```

## When to Use Which Mode

| Mode | Flag | Speed | Cost | Best For |
|------|------|-------|------|----------|
| Full | (default) | ~1-3 min | ~$0.05-0.20 | Visual tutorials (Blender, Figma, code editors), demos with UI |
| Quick | `--quick` | ~15-30s | ~$0.01-0.03 | Talks, lectures, podcasts, text-heavy content |

## Workflow: Video → Action

After extracting steps, Claude can:
1. **Execute steps directly** — if the steps involve CLI commands, code, or file operations
2. **Create a checklist** — save steps to a file for the user to follow
3. **Build automation** — turn procedural steps into a script or n8n workflow
4. **Create course content** — use as research input for outline-generator skill

### Example: Learning a Blender Tutorial
```
User: Learn how to model a donut from this video: https://youtube.com/watch?v=...
```
1. Run video_to_action.py to extract steps
2. Claude receives structured steps with timestamps, menu paths, keyboard shortcuts
3. Claude can then guide the user through each step, or even drive Blender via scripting

## Environment
Requires in `.env`:
```
NANO_BANANA_API_KEY=your_gemini_api_key
```

## Dependencies
- `yt-dlp` — video/transcript download
- `ffmpeg` — frame extraction (fallback mode)
- `google-genai` — Gemini API
- `Pillow` — image handling (fallback mode)
- `python-dotenv`

## Limitations
- Gemini File API: videos up to ~2GB / ~1 hour for full analysis
- Longer videos: use `--quick` mode or ask about specific timestamps
- Some videos have no auto-captions — `--quick` mode will fail, use full mode
- Private/age-restricted videos may not download
