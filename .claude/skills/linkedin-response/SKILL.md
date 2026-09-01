---
name: linkedin-response
description: Respond to LinkedIn DMs with short, casual, human-like messages matching Debanjan Mazumdar's voice. Use for replying to thank-yous, compliments, interest expressions, and simple questions in LinkedIn messaging.
allowed-tools: Read, Grep, Glob, mcp__chrome-stealth__take_snapshot, mcp__chrome-stealth__click, mcp__chrome-stealth__hover, mcp__chrome-stealth__evaluate_script, mcp__chrome-stealth__navigate_page
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# LinkedIn DM Response

## Goal
Triage and respond to LinkedIn DMs with short, lowercase, human-like messages matching Debanjan Mazumdar's casual texting voice.

## Model Recommendation
Run this skill on the execution tier (`claude-sonnet-5`; `sonnet` alias in sub-agent spawns). The task is procedural (classify → execute DOM action) and doesn't need the judgement tier.

## CRITICAL SAFETY CONSTRAINTS

**NEVER send a message without explicit user approval.** Always:
1. Show the proposed response (or batch table in dry-run)
2. Wait for user confirmation
3. Only then type and send

## CRITICAL: No Double Messages

**NEVER reply if Debanjan Mazumdar's message is the most recent one in the conversation.** The cadence must always be them→me→them→me. Never me→me. If Debanjan Mazumdar already replied last, skip the conversation entirely. This is the single most important rule — double-messaging looks automated and not human.

## Voice & Style Rules

Debanjan Mazumdar's LinkedIn DM voice:
- **Always lowercase** (never capitalize, even sentence starts)
- **Short** — typically 2-8 words, occasionally a short sentence
- **Casual/friendly** — like texting a friend
- **No punctuation overkill** — one exclamation max, no periods on short replies
- **No emojis** unless the other person used them first (then mirror sparingly)
- **Never formal** — no "Thank you for your kind words" or "I appreciate your message"
- **Never salesy** — don't pitch {{COMMUNITY_NAME}} or link to anything
- **Context-aware** — generate responses intelligently based on what they actually said. Don't just pick from templates. If someone mentions something specific ("your course saved me 10 hours"), weave that in naturally ("10 hours is wild, glad it helped!")

## Three Categories

### Category 1: Gratitude / Happiness / Compliments
**Trigger:** Someone expresses thanks, satisfaction, gratitude, compliments Debanjan Mazumdar's work/content, says something nice, or shares how their content helped them.

**Action:** Reply with a short, lowercase, warm acknowledgment. Generate contextually — read their actual message and respond to what they said, not a generic template.

Tone calibration examples (for style reference only, don't copy verbatim):
- "np man"
- "my pleasure!"
- "glad to hear it"
- "means a lot, thanks"
- "really appreciate that man"

For longer/heartfelt messages, lean slightly longer but still casual:
- "really appreciate that man, means a lot"
- "that's so cool to hear, glad I could help"

### Category 2: Confirmations ("it worked", "got it", "Yes", "Thanks" with no substance)
**Trigger:** Someone confirms a lead magnet link worked, says "got it", bare "Thanks", "Yes", or sends a simple acknowledgment like 👍. Purely transactional, no emotional content.

**Action:** React with 👍 (thumbs up emoji reaction on their message). Do NOT send a text reply.

**Important distinction:** If their confirmation ALSO includes genuine gratitude or a compliment (e.g., "It works! Thanks, huge fan of your work"), use Category 1 instead. Category 2 is only for bare confirmations with zero emotional content.

### Category 3: Complex / Needs Manual Review
**Trigger:** Any of:
- Complicated questions that need real thought
- Long pitches or business proposals
- Requests for collaboration/partnerships
- Technical questions Debanjan Mazumdar should answer personally
- Anything ambiguous or that doesn't clearly fit Cat 1 or Cat 2
- "It didn't work" / troubleshooting requests
- Messages in foreign languages where intent is unclear

**Action:** Mark the conversation as unread. Debanjan Mazumdar will review these themselves.

## Selection Logic

1. Check if Debanjan Mazumdar's message is the most recent → if yes, **SKIP** (no double messaging)
2. Read the other person's last message
3. Classify into Category 1, 2, or 3
4. If Cat 1: generate a contextual reply based on their actual message
5. If Cat 2: react with 👍
6. If Cat 3: mark as unread
7. Present proposed action to user, then execute

## Technical Notes (LinkedIn DOM)

### Sending a message (Cat 1)
LinkedIn's contenteditable does NOT work with `type_text` or `fill`. You MUST use `evaluate_script`:

**Step 1 — Type the message:**
```javascript
() => {
  const editor = document.querySelector('div[contenteditable="true"].msg-form__contenteditable');
  if (!editor) return 'no editor';
  editor.focus();
  editor.innerHTML = '<p>YOUR MESSAGE HERE</p>';
  editor.dispatchEvent(new Event('input', { bubbles: true }));
  return 'typed';
}
```

**Step 2 — Click send:**
```javascript
() => {
  const btn = document.querySelector('.msg-form__send-button');
  if (!btn) return 'no send button';
  btn.click();
  return 'sent';
}
```

**Common mistake:** Do NOT use selector `.msg-form__contenteditable [contenteditable="true"]` (descendant). The class is ON the contenteditable element itself: `div[contenteditable="true"].msg-form__contenteditable`.

### Reacting with 👍 (Cat 2)
JS `mouseenter` dispatch does NOT reveal the reaction toolbar. You MUST:
1. Use MCP `hover` tool on the **message text UID** (with `includeSnapshot: true` to save a round-trip)
2. In the returned snapshot, find `menuitem "React with thumbs up"` UID
3. Click that UID

**Make sure you're hovering on the OTHER person's message, not Debanjan Mazumdar's.**

### Mark as unread (Cat 3)
1. Click the "Open the options list..." button on the conversation **list item** (not the thread header)
2. In the dropdown, click "Mark as unread"

### Finding the last sender
In the thread, each message group has an `a[href*="/in/"]` profile link with text like "View [Name]'s profile". Check whether the last message group belongs to Debanjan Mazumdar or the other person.

## Token Optimization

These are critical for keeping costs low:

1. **Use `includeSnapshot: true`** on `click` and `hover` calls whenever you need the page state afterward. This returns the snapshot in the same response — saves a separate `take_snapshot` call (1 round-trip + ~5K tokens per snapshot saved).

2. **Minimize snapshots for mechanical actions.** Cat 2 (👍) needs exactly 2 calls: hover with includeSnapshot → click menuitem. Cat 3 (mark unread) needs 2 calls: click options with includeSnapshot → click "Mark as unread". Don't take extra snapshots.

3. **Don't re-read the conversation list** between actions unless you need to find the next conversation. After finishing one conversation's action, just click the next conversation in the list directly.

4. **Skip already-processed conversations.** If the list preview shows "You: ..." that means Debanjan Mazumdar replied last — skip without clicking in.

## Execution Flow

Process conversations ONE AT A TIME:
1. Click into the conversation (use `includeSnapshot: true`)
2. Verify Debanjan Mazumdar is NOT the last sender
3. Identify the last message from the other person
4. Classify into category 1/2/3
5. Execute the appropriate action (reply / react / mark unread)
6. Move to next conversation

## Dry Run Mode

When asked to "dry run", do NOT type, send, react, or mark anything. Just present a table:

| # | From | Their Message | Category | Proposed Action |
|---|------|--------------|----------|----------------|
| 1 | Name | "quote..." | 1 | Reply: "np man" |
| 2 | Name | "got it" | 2 | React 👍 |
| 3 | Name | "long pitch..." | 3 | Mark unread |
| 4 | Name | (Debanjan Mazumdar replied last) | SKIP | No action (would double-msg) |

## Batch Mode

Process conversations ONE AT A TIME. For each:
1. Click into the conversation
2. Check last sender (skip if Debanjan Mazumdar)
3. Read last message
4. Classify, execute action immediately
5. Move to next

**Do NOT do two passes** (scan all → compile table → execute all). That wastes tokens and degrades quality. Process each conversation fully before moving to the next. Present dry-run table only if explicitly asked for a dry run.

## Setup

1. Navigate to LinkedIn messaging: `https://www.linkedin.com/messaging/?filter=unread`
2. Use the `chrome-stealth` MCP server (not `chrome-devtools`)
3. Process all visible unread conversations, then click "Load more conversations" if present
