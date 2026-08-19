---
name: course-slideshow
description: >
  Generate an Excalidraw slideshow from a course outline. Parses chapter headings,
  generates 3 diagrams per chapter via Gemini, and assembles into a single .excalidraw
  file with vertical slideshow layout. Use when preparing course recording visuals,
  creating annotatable slides, or invoking /course-slideshow.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Course Slideshow Generator

Turn a finalized course outline into a single Excalidraw file you can scroll through
while recording. Each chapter gets 3 diagrams laid out horizontally — annotate 1-3
of them on camera, then scroll down to the next chapter.

## When to Use

- After a course outline is finalized (via outline-generator or manually)
- User says "slideshow", "course slides", "excalidraw slides", or invokes `/course-slideshow`
- User wants annotatable visual aids for a YouTube course recording

## Inputs

1. **Course outline markdown** — a file in `active/youtube-strategy/outlines/`
2. **Chapter filter** (optional) — which chapters to process (e.g., first 3 for testing)

## Full Pipeline (always follow all 3 steps)

### Step 1: Generate Excalidraw slideshow

```bash
# Full course (all chapters)
.venv/bin/python .claude/skills/course-slideshow/generate_course_slideshow.py \
  active/youtube-strategy/outlines/OUTLINE.md

# First 3 chapters only (for testing)
.venv/bin/python .claude/skills/course-slideshow/generate_course_slideshow.py \
  active/youtube-strategy/outlines/OUTLINE.md --chapters 0,1,2

# Custom output path
.venv/bin/python .claude/skills/course-slideshow/generate_course_slideshow.py \
  active/youtube-strategy/outlines/OUTLINE.md -o active/my_slideshow.excalidraw

# Dry run (parse only, show chapters, no Gemini calls)
.venv/bin/python .claude/skills/course-slideshow/generate_course_slideshow.py \
  active/youtube-strategy/outlines/OUTLINE.md --dry-run
```

### Step 2: Create Google Doc from outline

**Always create a Google Doc** so Debanjan Mazumdar has a recording reference alongside the Excalidraw slideshow.

```bash
python3 .claude/skills/course-slideshow/md_to_gdoc.py \
  active/youtube-strategy/outlines/OUTLINE.md \
  --title "Course Title — Outline"
```

> Uses `gws` CLI under the hood (no Python Google API dependencies needed).

After creation, update the outline markdown's `Google Doc:` field with the returned URL.

### Step 3: Report deliverables

Always report both outputs to the user:
- **Excalidraw slideshow** — file path + "Open at https://excalidraw.com → File → Open"
- **Google Doc** — URL link

## Output Layout

```
Course Title (40px)

1. The Wow Moment (32px heading)
[Concept diagram]   [Process diagram]   [Comparison diagram]

2. How AI Agents Work (32px heading)
[Concept diagram]   [Process diagram]   [Comparison diagram]

3. Self-Modifying Instructions (32px heading)
[Concept diagram]   [Process diagram]   [Comparison diagram]

...
```

Each diagram is 640×360px (16:9). Three per row with 400px gaps.
Chapters are separated by 600px vertical gap.

## Recording Workflow

1. Open the .excalidraw file at https://excalidraw.com → File → Open
2. Open the Google Doc alongside for talking points
3. Zoom to fit the first chapter's row of 3 diagrams
4. Use Excalidraw's pen/arrow tools to annotate while recording
5. Scroll down to the next chapter when ready

## Diagram Types (per chapter)

1. **Concept/Architecture** — big-picture overview of the topic
2. **Process/Workflow** — step-by-step flow diagram
3. **Comparison/Decision** — when to use, trade-offs, vs alternatives

## Caching

Generated diagram PNGs are cached in `active/.tmp/course-diagrams/`. If you
re-run the script, existing PNGs are reused (not re-generated). Delete the
cache dir to force regeneration.

## Cost

- ~$0.02-0.05 per diagram × 3 per chapter × N chapters
- Full 14-chapter course: ~$0.84-2.10 total

## Environment

Requires `NANO_BANANA_API_KEY` in `.env` (Gemini API key).
Requires Google OAuth credentials at `active/config/credentials.json` + `active/config/token.json`.
