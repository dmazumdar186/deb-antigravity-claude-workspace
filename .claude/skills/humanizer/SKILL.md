---
name: humanizer
description: |
  Strip AI-tells from text and rewrite it in a personal voice profile so it
  reads as natural human writing before sending. Four-stage pipeline:
  deterministic pre-pass (free) + LLM rewrite via tool-use + platform
  post-processing. Voice profiles are JSON files with real writing samples
  that teach the LLM to match the person's actual cadence.

  Triggers on: "humanize this", "make this sound less AI", "make this less
  robotic", "rewrite in my voice", "paste-ready", "clean this up so it
  sounds like me", "rewrite for LinkedIn", "make this sound human",
  "remove the AI from this", "strip the AI", "make this sound like Debanjan",
  "humanize before I send this".

  Also triggers when the user pastes a block of AI-generated text and says
  "fix this" or "send this to [person/platform]" — it almost certainly needs
  humanizing first.
user_invocable: true
---

# Humanizer

When invoked, run the humanizer script and return the cleaned text to the user.

## Step 1 — Capture the text

The user will either:
- Paste the text inline in chat ("humanize this: [text]")
- Mention a file path ("humanize the draft in draft.md")
- Have already sent the AI-generated text as context

If the text is not obvious, ask: "Paste the text you want humanized."

## Step 2 — Single text or batch?

**Single text (default):** paste or pipe one block of text and run the single-input commands in Step 4.

**Batch mode:** use `--batch` when you have more than ~5 texts to humanize in one session, or when you need structured CSV output (text_id, original, humanized, tier, cost, error). Batch fans out across parallel workers and isolates per-row failures — a single bad row does not abort the run.

### Batch mode

Trigger: user has a list of AI-drafted texts (cold emails, LinkedIn posts, tweet thread, etc.) and wants all of them humanized in one shot.

**Input CSV format:**
```
text_id,text_to_humanize,voice_name
row1,"Certainly! I'd be happy to delve into this...",debanjan
row2,"Absolutely! Let's leverage synergies...",debanjan
row3,"It's worth noting that this is a game-changer...",
```
- `text_id` — any unique string identifier
- `text_to_humanize` — the AI text to rewrite
- `voice_name` — optional; falls back to `--voice` CLI default if blank

**Run:**
```bash
py execution/content/humanizer.py --batch input.csv --max-workers 4 --tier default --out output.csv
```

**Output CSV columns:** `text_id, original, humanized, tier, cost_usd, error`

Failed rows have a non-empty `error` column; all other rows complete normally. After the run, a summary line is printed to stdout:
```
BATCH SUMMARY: 10 total, 9 succeeded, 1 failed, $0.00312 total cost
```

**Batch + dry-run** (no API calls, no cost):
```bash
py execution/content/humanizer.py --batch input.csv --dry-run --out preview.csv
```

**Batch flags:**
| Flag | Default | Purpose |
|------|---------|---------|
| `--batch <csv>` | — | Input CSV path (mutually exclusive with `--text` / `--file`) |
| `--max-workers N` | 4 | Parallel threads |
| `--out <csv>` | `humanized_<stem>.csv` | Output CSV path |

All other single-input flags (`--voice`, `--platform`, `--tier`, `--max-length`, `--dry-run`, etc.) apply to every row in the batch. Per-row `voice_name` column overrides `--voice` for that row.

## Step 2b — Pick the voice

Default to `--voice debanjan` unless the user specifies otherwise.

If the user says "in my voice" or "sound like me" and they are Debanjan, use `debanjan`.

To add a new voice later: copy `execution/content/voices/_template.json` to `voices/{name}.json` and fill in real writing samples. See `directives/content/humanizer.md` for the "Adding a new voice" section.

## Step 3 — Pick the platform

Ask or infer from context:

| User says | Platform flag |
|-----------|--------------|
| "for LinkedIn" / "LinkedIn post" | `--platform linkedin` |
| "for Slack" / "Slack message" | `--platform slack` |
| "tweet" / "Twitter" / "X" | `--platform tweet` |
| "email" | `--platform email` |
| No platform mentioned | `--platform generic` (default) |

## Step 4 — Run with --show-diff first (recommended)

Always run with `--show-diff` first on the first call so the user can see what changed:

```bash
py execution/content/humanizer.py --text "Certainly! I'd be happy to help you delve into..." --voice debanjan --platform linkedin --show-diff
```

The before/after diff prints to stderr. The humanized text prints to stdout.

For a quick cost check before the real call:
```bash
py execution/content/humanizer.py --text "..." --dry-run --show-diff
```

## Step 5 — Hand back the cleaned text

After the script finishes, copy the stdout output and present it to the user. If `--show-diff` was used, also mention the key changes (e.g., "Stripped 'Certainly!', replaced 'delve', shortened 3 sentences").

## Common commands

```bash
# Basic humanize (stdin)
echo "Certainly! I'd be happy to..." | py execution/content/humanizer.py

# Direct text, show diff
py execution/content/humanizer.py --text "..." --show-diff

# LinkedIn-specific cleanup
py execution/content/humanizer.py --text "..." --platform linkedin --show-diff

# Tweet (hard 280-char cap)
py execution/content/humanizer.py --text "..." --platform tweet

# Dry run (no LLM, see pre-pass + cost estimate)
py execution/content/humanizer.py --text "..." --dry-run

# Premium tier for nuanced rewrite
py execution/content/humanizer.py --text "..." --tier premium --show-diff

# Free Gemini path
py execution/content/humanizer.py --text "..." --tier gemini --show-diff

# From file
py execution/content/humanizer.py --file draft.md --platform email --show-diff
```

## When NOT to use this skill

- The user wants to write something from scratch (use Claude to draft, then humanize)
- The text is already short and direct (e.g., a single sentence reply) -- skip humanizing, it adds latency for minimal gain
- The user explicitly says they like the AI's phrasing and just wants to send it as-is

## Choosing single vs batch

| Situation | Use |
|-----------|-----|
| 1–4 texts in a session | Single-input (`--text` / `--file` / stdin) |
| 5+ texts, or structured CSV output needed | `--batch` |
| Campaign of N cold emails to humanize | `--batch input.csv --max-workers 4` |
| Quick preview before spending credits | `--batch input.csv --dry-run` |
