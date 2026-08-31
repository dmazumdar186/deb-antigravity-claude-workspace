# Speed to Lead (S2L) — respond to intent in ~30 seconds

Source: Nick Saraev course [4:06:22–4:36:37]; library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §5.
**Status: provisioning-gated** — no Formspree/Qo/Twilio accounts held; see
Edge Cases before promising delivery.

## Goal

When a lead shows intent (form fill, inbound email/SMS/call), respond within
~30 seconds on two channels (email + SMS, optionally live call-merge) with a
short personalized message, before the lead's in-the-moment motivation decays.
Source claims: 300–400% revenue lift; home-services case $3M→$9M/mo.

## Inputs

- An intent event source. Cheapest demo rail: HTML form → Formspree (free
  form→email) → inbox. Our production rail: CF Worker webhook receiver +
  Gmail polling fallback every N minutes (dual-path, existing workspace
  pattern).
- Templates (human-written, AI fills only the paraphrase slot):
  - Email — subject `Re: <first name> <service>`; body: greeting, ≤10–15-word
    paraphrase of their request, "I or someone on my team will call you in the
    next 5 minutes", persona signature.
  - SMS — same shape compressed to a **160-char budget with safety margin**
    (long names/content must not overflow).

## Tools / Scripts

- Event intake: `execution/infrastructure/` Worker patterns (webhook secret,
  idempotency sentinel, dedup KV).
- Sending: Gmail API/SMTP (email); Twilio or Qo/OpenPhone (SMS — both require
  US A2P 10DLC registration, 2–14 days, can be rejected).
- Trigger the responder via API POST with a bearer token on event arrival —
  event-driven beats polling loops.

## Outputs

Per lead: one email + one SMS sent within the pacing window, dedup-logged so a
lead is never double-messaged; failures to the error channel.

## Steps

1. Build the intake and verify a test submission lands (front-door first).
2. Poll/receive, parse, and dedup new leads ("seconds since sent" metric).
3. Generate the paraphrase slot (execution tier model), constrained: ≤10–15
   words, casual format, "do not stray from this template."
4. **Pacing**: never respond in ≤5 seconds — instant replies read as
   automated/fake. Delay ~30s; small human imperfections ("just got back to
   the office, give me 3 minutes") raise perceived authenticity.
5. Send email + SMS near-simultaneously; log both against the lead.
6. End-to-end test with fabricated leads to your own addresses/phone before
   any real traffic.
7. Optional full layer: automatic call-merge — a third-party number rings lead
   and rep simultaneously, first to answer connects.

## Edge Cases

- **Provisioning gaps (blockers for live SMS)**: no Qo/Twilio account, no A2P
  registration, no Formspree. Email-only S2L is buildable today on existing
  Gmail rails.
- SMS overflow: enforce the 160-char cap at generation time with a hard check,
  not hope.
- Persona: sign with a consistent persona name; don't switch mid-flow.
- Dispositions/CRM handoff after the touch is out of scope here (sales side).
- The responder is customer-facing: apply LLM output guard rails (max words,
  no exclamation storms, empty-response fallback) and an output-acceptance
  check on the exact rendered email/SMS.
