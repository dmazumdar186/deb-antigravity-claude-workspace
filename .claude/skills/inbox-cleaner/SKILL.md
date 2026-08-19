---
name: inbox-cleaner
description: Clean up Gmail inbox by reading all unread emails, using AI to identify which ones are genuinely important (personalized, human-written), and marking the rest as read. Use when cleaning inbox, triaging email, or clearing unread notifications.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Inbox Cleaner — AI-Powered Unread Email Triage

## Goal
Go through every unread email across ALL 3 accounts, classify each one as important or not, and mark unimportant ones as read automatically (no confirmation step). Only truly personalized, human-written emails survive as unread.

## What Counts as Important
An email is important ONLY if it was clearly written by a human specifically for Debanjan Mazumdar. Indicators:
- References specific details about Nick, his business, or prior conversations
- Contains substantive content that couldn't be a template
- Comes from a known contact with a real message
- Replies in an existing thread with genuine human input

## What Gets Marked as Read (Not Important)
- Automated notifications (GitHub, Stripe, Slack digests, calendar, etc.)
- Marketing emails and newsletters
- Cold outreach / sales emails (templated pitches, "I noticed your company..." spam)
- Service alerts, receipts, shipping updates
- Social media notifications
- Automated replies (out-of-office, delivery confirmations)
- Mass emails from SaaS products
- Any email that feels like it was sent to 100+ people

## Process

Run all 3 accounts in parallel. For each account, run fetch → classify → mark-read sequentially, then present a single summary at the end. **Do NOT ask for confirmation before marking as read** — just do it and report what was kept.

### Per-account steps (run sequentially within each account, but all 3 accounts in parallel):

```bash
# 1. Fetch
.venv/bin/python3 .claude/skills/inbox-cleaner/inbox_cleaner.py --fetch --account {account}

# 2. Classify
.venv/bin/python3 .claude/skills/inbox-cleaner/inbox_cleaner.py --classify --account {account}

# 3. Mark as read (no confirmation needed)
.venv/bin/python3 .claude/skills/inbox-cleaner/inbox_cleaner.py --mark-read --account {account}
```

### After all accounts are done:

Run `--review` on each account and present a single combined summary showing only the important emails that were kept unread. Keep it brief.

## Accounts
Supports all 3 Gmail accounts via `--account`:

| Account | Email | Default |
|---------|-------|---------|
| `yourwork` | your-work-email@example.com | Yes |
| `youraccount` | your-email@example.com | |
| `personal` | your-personal-email@example.com | |

```bash
# Clean yourwork (default)
python3 .claude/skills/inbox-cleaner/inbox_cleaner.py --fetch

# Clean a specific account
python3 .claude/skills/inbox-cleaner/inbox_cleaner.py --fetch --account youraccount
```

Auth tokens and credentials are in `active/config/` (same as the gmail skill).

## Output
- `active/inbox_unread_{account}.json` — fetched unread emails
- `active/inbox_classified_{account}.json` — classification results with reasoning
- Console summary showing what was kept vs marked read

## Edge Cases
- If classification is uncertain, keep the email as unread (err on the side of caution)
- Emails from contacts in existing threads should be treated as important even if short
- Forwarded emails: judge based on the forwarding context, not the forwarded content

## First-Run Setup

Before executing, check if the workspace has a `.gitignore` file. If it doesn't, assume the user is new to this skill. In that case:

1. Ask the user if this is their first time running this skill
2. If yes, walk them through how it works and what they need to configure/set up (API keys, env vars, dependencies, etc.)
3. Let them know that Debanjan Mazumdar wishes them the best!
