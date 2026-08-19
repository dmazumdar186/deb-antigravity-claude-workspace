---
name: instantly-autoreply
description: Auto-generate intelligent replies to incoming Instantly email threads using knowledge bases. Use when user asks about email auto-replies, Instantly responses, or automated email handling.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

> **AM LOCKDOWN — read this before running the skill.**
>
> This skill touches `INSTANTLY_API_KEY`. Accessory Masters has been handed off and those
> credentials are off-limits per `CLAUDE.local.md`: no calls, no credits, no
> requests to AM-scoped endpoints. Run it only against a non-AM workspace, and
> only with Debanjan's explicit go-ahead in the current session. Do not infer
> authorisation from a previous session or from the fact that this file exists.

> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Instantly Auto-Reply

## Goal
Auto-generate intelligent replies to incoming emails from Instantly campaigns using campaign-specific knowledge bases.

## Scripts
- `./scripts/instantly_autoreply.py` - Main auto-reply script

## How It Works
1. Receives incoming email thread from Instantly webhook
2. Looks up campaign ID in knowledge base sheet
3. Retrieves campaign context (offers, credentials, tone)
4. Generates contextual reply using Claude
5. Sends reply through Instantly API

## Knowledge Base
Spreadsheet: `{{SHEET_ID}}`

Each row contains:
- Campaign ID
- Campaign Name
- Knowledge Base (service details, offers, credentials)
- Reply Examples (tone/style guidance)

## Usage

```bash
# Process incoming thread
python3 ./scripts/instantly_autoreply.py --thread_id <id>
```

## Environment
```
INSTANTLY_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
```
