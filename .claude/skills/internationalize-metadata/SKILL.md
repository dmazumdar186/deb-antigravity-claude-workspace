---
name: internationalize-metadata
description: Internationalize YouTube video metadata for dubbed uploads. Use when given a language and a video description to produce localized title, description, and audio extraction. Triggers on "internationalize", "dub metadata", "localize metadata", or /internationalize-metadata.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Internationalize Metadata

Takes an original English YouTube video description + a target language and produces ready-to-paste metadata for the dubbed version upload.

## Inputs

The user provides:
1. **Target language** (e.g., Hindi, French, German, Spanish)
2. **Original video title**
3. **Original video description** (full YouTube description with links, chapters, etc.)
4. Optionally: path to the dubbed MP4 to extract audio from

## Process

### 1. Generate Title

- Keep all English keywords/brand names intact (Claude Code, N8N, Antigravity, etc.) — these are search terms
- Add the language name in English (e.g., "Hindi Dub", "French Dub")
- Stay under 60 characters
- Keep the year if present
- Format: `{Original Title Core} - {Language} Dub ({Year})`
- Example: `Claude Code Full Course 4 Hours - Hindi Dub (2026)`

### 2. Generate Description

Structure:
```
{flag emoji} {Language} dubbed version of the original {Video Title}!
{film emoji} Original (English): {original video URL}

{rest of original description — keep ALL links, affiliate codes, chapters, etc. unchanged}
```

Rules:
- Add a 2-line header with language flag emoji + link back to original English video
- Keep the entire original description body unchanged (links, affiliate codes, chapters, CTAs)
- Do NOT translate the description body — it stays in English
- Do NOT modify any URLs, promo codes, or affiliate links
- Keep all chapters/timestamps exactly as-is

### 3. Extract Audio (if MP4 path provided)

```bash
ffmpeg -y -i "{input}.mp4" -vn -acodec aac -b:a 192k "{output}.m4a"
```

YouTube's "Add audio track" feature for multi-language dubs expects audio-only files (M4A/MP3).

### 4. Output

Present the title and description as copy/paste blocks using code fences, plus confirm the audio file path if extracted.

## Language Flag Emoji Map

- Hindi: 🇮🇳
- French: 🇫🇷
- German: 🇩🇪
- Spanish: 🇪🇸
- Portuguese: 🇧🇷
- Japanese: 🇯🇵
- Korean: 🇰🇷
- Chinese: 🇨🇳
- Arabic: 🇸🇦
- Italian: 🇮🇹
