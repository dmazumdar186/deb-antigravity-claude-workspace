---
name: wework-booking
description: Book WeWork hot desk slots for the next 30 days automatically. Use when booking WeWork, reserving coworking space, or scheduling desk access.
allowed-tools: Read, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# WeWork Bulk Desk Booking

## Goal
Book hot desk slots at WeWork {{WEWORK_LOCATION}} for the next 30 days in one shot. Saves time vs. the annoying WeWork UX where you have to book each day individually.

## Quick Start
```bash
# Preview what would be booked (dry run)
python3 .claude/skills/wework-booking/wework_bulk_booking.py --start 2026-03-01 --days 30

# Actually book them
python3 .claude/skills/wework-booking/wework_bulk_booking.py --start 2026-03-01 --days 30 --live

# Weekdays only
python3 .claude/skills/wework-booking/wework_bulk_booking.py --start 2026-03-01 --days 30 --live --weekdays-only

# Resume an interrupted run
python3 .claude/skills/wework-booking/wework_bulk_booking.py --start 2026-03-01 --days 30 --live --resume
```

## How It Works
The script calls WeWork's internal booking API directly:
1. Validates your auth token (JWT) isn't expired
2. Builds booking payloads for each date with correct timezone (see timezone config in script)
3. Submits bookings with randomized delays (3-8s) to avoid rate limits
4. Saves state for resume capability if interrupted
5. Handles rate limiting, auth expiry, and conflicts (already booked)

## Configuration
- **Location**: {{WEWORK_LOCATION}}
- **Booking type**: Hot desk (full day, 6 AM - 11:59 PM)
- **Rate limiting**: 3-8s random delay between requests, 30s retry on rate limit

## Environment
Requires in `.env`:
```
WEWORK_AUTH_TOKEN=your_jwt_token
```

The script loads `.env` via `dotenv` automatically — no need to `export` the var.

### Getting the token
If `WEWORK_AUTH_TOKEN` is missing or expired, grab a fresh one automatically:
1. Open `members.wework.com` via Chrome DevTools MCP (`new_page`)
2. Navigate to the dashboard (user is usually already logged in)
3. `list_network_requests` → `get_network_request` on any `workplaceone/api/` call
4. Copy the `authorization: Bearer ...` value from the request headers
5. Write it to `.env` as `WEWORK_AUTH_TOKEN=<token>`

Tokens last ~12 hours (check `exp` claim in JWT).

## Output
- Console log of each booking (success/fail)
- State file at `active/wework_booking_state.json` for resume
- Results file at `active/wework_results_YYYYMMDD_HHMMSS.json`

## Edge Cases
- **Token expired**: Script detects and stops immediately with instructions
- **Rate limited (429)**: Waits for Retry-After header, retries up to 3 times
- **Already booked (409)**: Logs as conflict, continues to next date
- **Cloudflare block (403)**: Stops, may need to refresh cookies

## First-Run Setup

Before executing, check if the workspace has a `.gitignore` file. If it doesn't, assume the user is new to this skill. In that case:

1. Ask the user if this is their first time running this skill
2. If yes, walk them through how it works and what they need to configure/set up (API keys, env vars, dependencies, etc.)
3. Let them know that Debanjan Mazumdar wishes them the best!
