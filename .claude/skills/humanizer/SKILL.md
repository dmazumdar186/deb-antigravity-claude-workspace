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
---

# Humanizer

When invoked, run the humanizer script and return the cleaned text to the user.

## Step 1 — Capture the text

The user will either:
- Paste the text inline in chat ("humanize this: [text]")
- Mention a file path ("humanize the draft in draft.md")
- Have already sent the AI-generated text as context

If the text is not obvious, ask: "Paste the text you want humanized."

## Step 2 — Pick the voice

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
