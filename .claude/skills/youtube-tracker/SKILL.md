---
name: youtube-tracker
description: Daily YouTube competitor tracking and breakout discovery. Runs autonomously on GitHub Actions. Use when discussing YouTube tracking, competitor growth stats, adding/removing tracked channels, or modifying the tracker.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# YouTube Tracker

Autonomous daily cron that tracks competitor YouTube channels and surfaces breakout small channels with viral videos. Posts digest to Slack.

## Repo & Infrastructure

- **GitHub repo**: `{{GITHUB_USER}}/youtube-tracker` (private)
- **Runs on**: GitHub Actions daily cron at `0 12 * * *` (5am MT / 7am ET)
- **Database**: SQLite committed to git after each run (`data/tracker.db`)
- **Notifications**: Slack webhook (Block Kit format)
- **API**: YouTube Data API v3 (free tier, 10K units/day per key)

## Key Files

Key files (the skill's own scripts are in `.claude/skills/youtube-tracker/`):

| File | Purpose |
|------|---------|
| `.claude/skills/youtube-tracker/tracker.py` | Main script — tracking, mining, notifications |
| `channels.json` | List of tracked channels (`handle` + `name`) |
| `keywords.json` | Search keywords for idea mining (~15 terms) |
| `requirements.txt` | Just `requests` |
| `data/tracker.db` | SQLite database (committed by bot) |
| `.github/workflows/track.yml` | GitHub Actions workflow |

## GitHub Secrets

| Secret | Value |
|--------|-------|
| `YOUTUBE_API_KEYS` | Comma-separated API keys (rotates on quota exhaustion) |
| `WEBHOOK_URL` | Slack incoming webhook URL |

## How It Works

### Phase 1: Competitor Tracking
- Reads `channels.json`, resolves `@handles` to channel IDs (cached in SQLite)
- Batch `channels.list` call for all channels (1 API unit for up to 50)
- Stores daily snapshot (subs, views, video count)
- Computes 24hr growth (absolute + %)

### Phase 2: Idea Mining
- Reads `keywords.json` (~15 keywords)
- `search.list` per keyword (100 units each) for videos from last 7 days
- Filters: 1K-25K subs, views >= 10x subs, duration >= 60s (no Shorts)
- Deduplicates via SQLite UNIQUE constraint

### Phase 3: Slack Notification
- Top 10 competitors sorted by subscriber count
- 24hr growth (absolute + %)
- Milestone alerts (100K/250K/500K/1M crossings)
- Breakout discoveries from last 7 days (up to 8)

## API Key Rotation

Script supports multiple keys via `YOUTUBE_API_KEYS` env var (comma-separated). When one key hits quota (403), it rotates to the next. Falls back to `YOUTUBE_API_KEY` (single key) for backwards compat.

**Quota per key**: 10,000 units/day. Each full run uses ~1,500 units.

## Common Tasks

### Add a channel
Edit `channels.json` — add `{"handle": "@handle", "name": "Display Name"}`. Push to GitHub.

### Remove a channel
Remove from `channels.json`. The channel stays in SQLite history but stops being tracked.

### Add a keyword
Edit `keywords.json`. Each keyword costs ~100 API units/day.

### Change cron schedule
Edit `.github/workflows/track.yml` — update the cron expression.

### Manual run
GitHub Actions > YouTube Tracker > Run workflow (or `workflow_dispatch` via gh CLI).

### Add another API key
1. Add to `YOUTUBE_API_KEYS` secret in GitHub (comma-separated)
2. Add to `.env` locally under `YOUTUBE_API_KEYS`

## Quota Budget
- Competitor tracking: ~1 unit (batch call)
- Idea mining: ~1,500 units (15 searches + channel/video lookups)
- **Total: ~1,500 units/day** (15% of free quota per key)
