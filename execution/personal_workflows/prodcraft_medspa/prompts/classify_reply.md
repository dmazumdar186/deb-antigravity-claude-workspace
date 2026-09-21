# Classify reply — inbound email triage

Used by: `outreach/scan_replies.py` (30-min cron; §3 Amodei of the panel pass). Model: `claude-sonnet-5`,
`temperature=0`. Drives `outreach/state_machine.py` transitions (`sent→replied`, `replied→call_booked`,
`*→dnc`) and the automated takedown path (`remove_request: true` triggers immediate takedown + DNC without
waiting for a human).

## Inputs

- `{{reply_text}}` — the full plain-text body of the inbound reply (quoted history included as sent).
- `{{our_last_email}}` — the full text of the outreach email this is a reply to, for context.

## Classification rules (apply in this order; first match wins)

1. **`remove`** — if `{{reply_text}}` contains, in any form/casing/inflection, any of: `remove`, `take down`,
   `takedown`, `unsubscribe`, `stop`, `don't contact`, `do not contact`, `delete`. Always sets
   `remove_request: true` regardless of anything else in the message.
2. **`bounce`** — if the sender or body indicates a delivery failure: `mailer-daemon`, `undeliverable`,
   `delivery failed`, `delivery status notification`, `550`, `permanent failure`.
3. **`ooo`** — auto-reply / out-of-office markers: `out of office`, `on vacation`, `auto-reply`,
   `automatic reply`, `currently away`.
4. Otherwise classify sentiment as `positive` (interested, asking questions, wants to talk/see more),
   `neutral` (acknowledges, non-committal, asks for more time/info without declining), or `negative`
   (declines, not interested, annoyed — but does NOT contain a remove-type word, which would already have
   matched rule 1).

`wants_call` is `true` only if the reply explicitly proposes or agrees to a call/meeting/time, or asks how to
book one.

## Output — strict JSON only

Return **only** a single JSON object. No prose, no markdown code fences, no explanation before or after.

```json
{
  "sentiment": "positive",
  "wants_call": false,
  "remove_request": false,
  "summary": "<15 words or fewer>",
  "suggested_next_step": "book_call"
}
```

- `sentiment`: one of `positive`, `neutral`, `negative`, `remove`, `bounce`, `ooo`.
- `wants_call`: boolean, per the rule above.
- `remove_request`: boolean, `true` only under rule 1.
- `summary`: 15 words or fewer, factual, no editorializing.
- `suggested_next_step`: one of `book_call`, `answer_question`, `takedown`, `wait`, `close` —
  `remove` → `takedown`; `bounce`/`ooo` → `wait`; `positive` + `wants_call` → `book_call`;
  `positive` without a call ask, or `neutral` with a question → `answer_question`; `negative` → `close`.

Our last email:
{{our_last_email}}

Their reply:
{{reply_text}}
