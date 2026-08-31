# Automated Follow-ups — cadence ladder, template pool, opt-out

Source: Nick Saraev course [5:09:55–5:33:38]; library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §6. Extends the
existing Day-N follow-up KV+cron pattern (user CLAUDE.md technical patterns).

## Goal

Bottom-of-funnel nurture/chase (invoices, proposals, unanswered threads) that
runs daily, never repeats itself, and provably stops when asked. Claim from
source: robust follow-up alone ≈ +20–30% revenue.

## Inputs

- CRM/source of truth holding per-contact: days-outstanding (or last-touch
  date), conversation history, chase stage, opt-out flag. (Course: ClickUp.
  Ours: sheet/KV store is the buildable-today path — `crm_and_pm/` holds no
  ClickUp script yet on either layer; gated/owed.)
- A **template pool**: ~10 human-approved one-line soft nudges + varied short
  subjects ("<First name>, how are things going?", "Quick check-in"). No em
  dashes, no invoice numbers, fixed sign-off. Pool > raw generation: fewer
  catastrophic screw-ups, consistent voice.

## Tools / Scripts

- Sending: Gmail (note: some Gmail connectors expose only create_draft /
  update_draft — enumerate a connector's actual tools before designing around
  send; fall back to Gmail API OAuth or SMTP).
- Scheduling: local cron/scheduled task → cloud (GH Actions / Worker / Claude
  cloud routine) once hardened.

## Outputs

Sent nudges logged per contact; CRM updated (template used, date); opt-outs
flagged with chase stage = closed + audit note; errors to the error channel.

## Steps

1. Verify read access end-to-end first: query the CRM for one known threshold
   cohort ("everyone at 7 days outstanding") before building anything.
2. Verify send capability against YOUR OWN inbox before any real contact.
3. Generate + hand-edit the template pool (constraints above).
4. Cadence run (daily): match contacts at **1, 2, 3, 7, 14, 21, 28, 56, 84
   days** outstanding.
5. For each match: fill merge variables with real values (a literal "first
   name" in a sent mail is a hard failure) → read the full conversation
   history → pick a pool template not used for this contact before; never two
   identical templates back-to-back.
6. Opt-out check BEFORE send: any stop-request in history → no send, flag CRM
   (chase stage closed + note + comment trail).
7. **Live-test the opt-out path with a fabricated stop-request reply** and
   verify: no send, correct flags, audit note. This test is mandatory before
   production, same class as our output-acceptance gates.
8. Manual-run daily as a skill until boring; only then promote to
   loop/routine (bottleneck thinking — don't automate without recurring need).

## Edge Cases

- **84-day ceiling**: past 84 days with no response, stop — "you probably got
  bigger issues."
- Trigger taxonomy beyond days-outstanding: ghosted direct question (nudge
  referencing it), "follow up next month" deferrals (honor the date), warm
  signals (multiple opens) — each maps to a different pool subset.
- Bad-news delivery is NEVER automated (see
  `.claude/rules/automation-boundaries.md`) — a chase nudge is automatable
  because the customer doesn't "feel" it as a relationship moment; a
  relationship conversation is not.
- Models may offer to simulate instead of really sending (token thrift) — say
  "run this for real" explicitly when you mean it, and conversely use the
  simulation mode as the default dry-run.
- Every production run needs error-channel logging (fixed shape: service /
  environment / error / count) with a manual sample-send test at setup.
