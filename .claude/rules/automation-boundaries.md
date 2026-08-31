# Automation Boundaries (load when designing any GTM / client-facing automation; referenced from the personalization, gtm, and content directives)

Adopted 2026-08-31 from Nick Saraev's Claude Code Marketing course
[5:35:45–6:01:33] (library doc
`docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §1.12–1.14).
Complements — never overrides — the workspace's existing gates.

## The decision filter (run before automating any process)

Ask: **does the customer actually feel this process? Is a relationship at
risk?**
- No → automate it.
- Yes → AI may draft; a human QAs and delivers. Do not fully automate.

**OK to automate**: data entry, first-draft copy/creative, reporting
mechanics, scheduling (with a caveat — see the customer-must-feel-valued item
below).

**NOT OK to automate**:
- Production of the final creative asset — AI is an ideation/spec tool; a
  human picks, upgrades, and ships.
- Bad-news delivery — a dashboard's anomaly "signals" must never auto-send a
  lead-flow collapse to a client. A human sits down with the client.
- Anything where a paying customer must feel valued — e.g. appointment-setting
  should not be "here's my calendar link, book yourself"; even an automated
  flow should ask a human-feeling question ("does 2pm work for you?").
- The singular activity that is the actual source of revenue, for a marginal
  time saving ("effectiveness beats efficiency" — never trade the core
  revenue-generating hour for automation convenience).

Principle: automation buys more time WITH people; it must not replace the time
with people. Field observation from the source: "people will overautomate
tremendously."

## Self-healing standing instruction (for every skill/loop/routine we ship)

Append to long-running automations, adapted to taste:

> If the same error recurs more than 3 times, assume something has materially
> changed in the external system. Investigate with full autonomy, fix it, then
> update this skill/routine's own instructions with a change-log entry
> (problem, solution, what was updated). Append to the change log on every
> future occurrence.

Caveats: not foolproof — a transient rate limit can trigger a wrong
self-rewrite; keep the change log so bad rewrites are auditable and
revertable. **Scope limit**: the automation may rewrite only its OWN
skill/routine instruction file; workspace directives, rules, and execution
scripts still require operator approval per CLAUDE.md. This is the lightweight cousin of the workspace's self-anneal
loop; for code, the anneal audit loop remains the stronger gate.

## Error-channel minimum bar (production routines)

Every unattended production automation logs failures to a dedicated channel
where the operator already communicates (Slack/Discord/WhatsApp/Telegram),
fixed shape: `service / environment / error / count`. Wire-up is not done
until a manual sample-send has been observed in the channel. Rationale:
time-to-detect — a 5:59am failure caught at 6am leaves hours of buffer before
the deliverable is due. (Our canary/dead-man + `/api/health` rules cover the
probe side; this rule covers the notification side.)

## Template-pool rule (customer-facing message automation)

Automated recurring messages draw from a pre-approved human-written template
pool (rotated, never repeated back-to-back per recipient) rather than free
generation. Fewer catastrophic screw-ups, consistent voice. Fuzzy variables
(`directives/personalization/fuzzy_variables.md`) fill the slots; the pool
stays human-authored.
