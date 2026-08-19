---
name: gmail
description: Search, read, send, reply, label, and archive Gmail emails across multiple accounts (your-email@example.com, your-work-email@example.com, your-personal-email@example.com). Use for any Gmail or email operations.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Gmail Operations

## Goal
Manage Gmail emails across multiple registered accounts. Search, read, send, reply, label, archive, and mark-read.

## Tools/Scripts
- **All operations**: `.claude/skills/gmail/gmail_unified.py`
- **Authenticate accounts**: `.claude/skills/gmail/gmail_multi_auth.py`
- **Bulk labeling**: `.claude/skills/gmail/gmail_bulk_label.py`
- **Create filters**: `.claude/skills/gmail/gmail_create_filters.py`

## Account Registry

| Account | Email | Credentials File | Token File |
|---------|-------|------------------|------------|
| youraccount | your-email@example.com | credentials.json | token_{{ACCOUNT}}.json |
| yourwork | your-work-email@example.com | credentials_{{ACCOUNT}}.json | token_{{ACCOUNT}}.json |
| personal | your-personal-email@example.com | credentials.json | token_personal.json |

## Quick Reference

### Search Emails
```bash
# Search across all accounts
python3 .claude/skills/gmail/gmail_unified.py --query "is:unread" --limit 50

# Search specific account
python3 .claude/skills/gmail/gmail_unified.py --query "from:hello@cal.com" --account yourwork

# Limit results
python3 .claude/skills/gmail/gmail_unified.py --query "subject:invoice" --limit 10
```

### Read a Specific Email
```bash
python3 .claude/skills/gmail/gmail_unified.py --read MESSAGE_ID --account yourwork

# JSON output for parsing
python3 .claude/skills/gmail/gmail_unified.py --read MESSAGE_ID --account yourwork --json
```

### Send a New Email
```bash
python3 .claude/skills/gmail/gmail_unified.py --send \
  --to "recipient@example.com" \
  --subject "Subject line" \
  --body "Email body text" \
  --account yourwork

# Dry run first
python3 .claude/skills/gmail/gmail_unified.py --send --to "test@example.com" --subject "Test" --body "Test body" --account yourwork --dry-run
```

### Reply to an Email
```bash
# Reply preserves thread, auto-marks original as read
python3 .claude/skills/gmail/gmail_unified.py --reply MESSAGE_ID --body "Reply text here" --account yourwork
```

### Modify Emails (Label, Archive, Mark Read)
```bash
# Apply a label (creates if doesn't exist)
python3 .claude/skills/gmail/gmail_unified.py --query "from:receipts@" --label "Receipts" --account yourwork

# Archive emails
python3 .claude/skills/gmail/gmail_unified.py --query "from:notifications@" --archive

# Mark as read
python3 .claude/skills/gmail/gmail_unified.py --query "from:hello@cal.com" --mark-read

# Combine operations
python3 .claude/skills/gmail/gmail_unified.py --query "subject:invoice" --label "Accounting" --archive --mark-read

# Always dry-run first for bulk operations
python3 .claude/skills/gmail/gmail_unified.py --query "older_than:30d" --archive --dry-run
```

### List Registered Accounts
```bash
python3 .claude/skills/gmail/gmail_unified.py --accounts
```

## Credentials & Authentication

### File Locations (`active/config/`)
- `credentials.json` — OAuth client for your primary + personal accounts (GCP project: `{{GCP_PROJECT_ID}}`)
- `credentials_{{ACCOUNT}}.json` — OAuth client for work account (GCP project: `{{GCP_PROJECT_ID}}`)
- `token_{{ACCOUNT}}.json` — Auth token for your-email@example.com
- `token_{{ACCOUNT}}.json` — Auth token for your-work-email@example.com
- `token_personal.json` — Auth token for your-personal-email@example.com
- `gmail_accounts.json` — Account registry mapping names to token files

All scripts use absolute paths resolved from the script location — no need to `cd` into any directory.

### Troubleshooting Auth Errors

**"Token file not found"** — Run auth flow:
```bash
python3 .claude/skills/gmail/gmail_multi_auth.py --account yourwork --email your-work-email@example.com
python3 .claude/skills/gmail/gmail_multi_auth.py --account youraccount --email your-email@example.com
python3 .claude/skills/gmail/gmail_multi_auth.py --account personal --email your-personal-email@example.com
```

**"invalid_scope: Bad Request"** — Delete token and re-auth:
```bash
rm active/config/token_{{ACCOUNT}}.json
python3 .claude/skills/gmail/gmail_multi_auth.py --account youraccount --email your-email@example.com
```

**"Access blocked: org_internal"** — The GCP OAuth app is set to Internal. Go to the GCP consent screen and switch User Type to External, or add the email as a test user:
`https://console.cloud.google.com/apis/credentials/consent?project={{GCP_PROJECT_ID}}`

**"Failed to authenticate"** — Check that `credentials.json` / `credentials_{{ACCOUNT}}.json` exist in `active/config/`.

## Required Scopes
- `gmail.modify` — Read/write emails
- `gmail.labels` — Create/manage labels
- `gmail.settings.basic` — Manage settings
- `spreadsheets` — Google Sheets access
- `drive` — Google Drive access

## Tone of Voice — Outgoing Emails

All outgoing emails (send and reply) MUST follow these rules. This is non-negotiable.

1. **Shorter is better.** Say it in 2-3 sentences if you can. Debanjan Mazumdar doesn't write essays in email.
2. **Write like a human, not an LLM.** No "Honest take:" openers. No "Not X. Not Y. Z." parallelism. No motivational-poster energy. Avoid the stereotyped LLM pattern where every sentence feels crafted and punchy — real humans meander a bit, use filler words ("yeah", "honestly", "like"), and don't structure their thoughts into perfect rhetorical triplets.
3. **Vary importance across sentences.** Not every sentence should feel like it matters equally. Some sentences are just connective tissue — boring, functional, forgettable. That's normal. Don't try to make every line interesting or use "good" words. Intentionally be boring in places — it signals human.
4. **Include at least one minor mistake.** A small spelling error, a missed capital letter, a slightly awkward comma, forgetting a period. Humans don't proofread casual emails perfectly. Pick one and leave it in.
5. **Use longer sentence structures with particles.** Humans connect thoughts with "and", "but", "so", "though", "because" rather than chopping everything into short declarative fragments.
6. **Match Debanjan Mazumdar's voice.** Direct, casual, no corporate speak. They'd say "yeah that sucks" not "I understand that must be frustrating."
7. **Use parentheticals and qualifiers.** Humans hedge naturally — "(frankly)", "in my experience", "in general", "like you're mentioning". These make it feel like you're actually thinking, not reciting. Don't strip them out for conciseness.
8. **Don't be dismissive-short.** Brief is good but you still need social grace — acknowledge the person's effort in reaching out, close warmly. Busy-but-kind, not too-cool-to-care.
9. **Add light filler.** Slightly unnecessary phrases like "and thank you for giving me a shout here" or "like you're mentioning" are human signals. They're clunky and that's the point.
10. **No double hyphens (--).** Use a comma instead, even if it's not grammatically perfect. Humans don't write em-dashes in casual emails.
11. **Don't offer to do things, just do them or skip.** Don't say "let me know if you want me to send the link" — either include it or just thank them. No dangling offers.
12. **Never copy user instructions verbatim.** When Debanjan Mazumdar gives direction for a reply (e.g. "tell them X"), treat it as intent, not dictation. Adapt the message to fit the specific conversation, the person's tone, and what they actually asked. Use your intelligence to make it sound natural and responsive, not pasted. **Exception:** If Debanjan Mazumdar says "verbatim", copy exactly as given.

## Quick Actions

**"Forward to sponsorships"** — When the user says "fw to sponsorships", "forward to sponsorships", or any equivalent, forward the email to `sponsorships@example.com` and mark the original as read. No draft needed, just do it.

## Edge Cases
- **Multiple accounts**: Search runs across all accounts unless `--account` specified
- **Send/read/reply**: Require `--account` since they operate on a single mailbox
- **Missing token**: Script warns and skips account; re-run `gmail_multi_auth.py`
- **Label doesn't exist**: Auto-created when using `--label`
- **Token expired**: Script auto-refreshes if refresh token exists

## Gmail Search Syntax Reference
- `is:unread` — unread emails
- `from:user@example.com` — from specific sender
- `to:me` — sent directly to you
- `subject:keyword` — subject contains word
- `has:attachment` — has attachments
- `newer_than:7d` / `older_than:30d` — date filters
- `label:inbox` — in inbox (not archived)
