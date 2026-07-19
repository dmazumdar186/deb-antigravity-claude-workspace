# Weekly Sunday Ritual — self_outbound_v2

**Cadence**: Every Sunday 20:00 Europe/Paris.
**Duration target**: 30 minutes.
**Owner**: operator (Debanjan).
**Claude prep**: draft the review report in `.tmp/self_outbound/weekly_review_YYYY-MM-DD.md` by Sunday 18:00 with the KPI table pre-filled.

Nick Saraev's iteration doctrine says Sunday is when copy anneals: kill losers, keep winners, generate 2x-different alternatives for the next week. Never miss more than 2 consecutive Sundays without acting on the metrics.

---

## 1. Metrics pull (5 min)

Claude auto-pulls before Sunday 18:00:

- **Instantly dashboard export**: sends / replies / bounces / spam-complaints for the week
- **Per-mailbox health**: mail-tester scores for 5 rotating mailboxes (auto-scheduled)
- **Reply classification**: positive / neutral / decline / not-interested / spam-report / autoresponder
- **Campaign KPIs**: reply rate, positive-reply share, meeting-booked rate this week
- **Weekly cost**: Instantly + Primeforge + Litemail + domains + warmup — actual vs plan
- **Suppression list growth**: how many entries added this week + reasons breakdown

Report lives at `.tmp/self_outbound/weekly_review_YYYY-MM-DD.md`.

---

## 2. KPI table check (5 min)

Compare against Section 10 KPI thresholds in the plan:

| Metric | This week | Threshold | Action if red |
|---|---|---|---|
| Bounce rate | X% | ≤ 3% | Kill mailbox(es) with highest bounce contribution |
| Spam-complaint rate | X% | ≤ 0.5% | Pause pool, investigate copy trigger |
| Reply rate | X% | ≥ 0.3% at 3k sends | Kill worst variant, rewrite |
| Positive-reply share | X% of replies | ≥ 20% | ICP or offer wrong — consider pivot |
| Meeting-booked rate | X% of positive replies | ≥ 40% | CTA or Cal.com flow broken |
| mail-tester score drift | Δ per mailbox | ≤ 1 point WoW | Auto-pause mailbox with drop >1 |
| Instantly warmup score | Any mailbox <50? | Never | Auto-pause + investigate |

Any red = written kill/pivot decision in the review report.

---

## 3. Kill / keep on variants (10 min)

Rule (Nick canonical, adapted to Debanjan's ICP): retire any variant with **<0.3% reply at ≥500 sends**. Keep any variant ≥0.5%. Marginal (0.3-0.5%) = one more week to decide.

For each variant, log:
- Total sends this week
- Reply rate
- Positive-reply share
- Meeting-booked rate
- Decision: **KEEP** / **RETIRE** / **MARGINAL** (one more week)

---

## 4. Copy anneal (5 min)

For each RETIRED variant, generate 2 "2x-different" alternatives per Nick's annealing schedule (3x → 2x → 1x → 0.5x):

- Different opening angle (e.g., pain-first vs curiosity-hook)
- Different offer shape (e.g., "30 days fixed price" vs "14-day paid pilot")
- Different CTA (e.g., "reply with 2 times" vs "book direct link")

Claude drafts alternatives; operator picks 2 to add. Commit to `tone.json`.

---

## 5. Pool health + cost review (5 min)

- **Retire dud mailboxes**: any Pool A / Pool B mailbox that has:
  - Failed mail-tester 2 weeks in a row
  - Bounce rate >5% own
  - Spam complaint >1 in the week
  → Request replacement from Primeforge/Litemail
- **Cost check**: monthly total vs. plan. If drifting: investigate (Warmforge running when Instantly bundled should suffice? Pool A over-provisioned?)
- **Domain reputation**: check MXToolbox for any blacklist entries on the 10 domains. Flag if any.

---

## 6. Log to HANDOFF (5 min)

Append 3-bullet weekly note to `execution/personal_workflows/self_outbound_system/HANDOFF_PHASE_3.md` (or successor):

```
## Week of YYYY-MM-DD
- **What changed**: [copy variant retired X, added Y; mailbox Z replaced; ...]
- **What's owed**: [operator needs to do W by day of month]
- **What's decided**: [next-week focus is A; scaling decision B deferred to date]
```

---

## Rhythm rules

- **Never miss > 2 consecutive Sundays**. If missed, catch up before the third.
- **If away (vacation)**: pre-generate the report Friday, decisions can wait 1 week max.
- **If the KPI table is all green** for 3 weeks straight: consider scaling to 45 or 60 mailboxes (only after Karpathy benchmark #4 payback data validates ROI).
- **If the KPI table is all red** for 2 weeks straight: pivot — either ICP, offer, or copy. Not more infra.

---

## Escalation triggers to break-glass

Any of these means: don't wait for Sunday, act NOW:
- Bounce rate >5% overnight → immediate mailbox investigation
- Spam-complaint rate >1% overnight → immediate pause via kill switch
- Any mailbox reports a Google Workspace security lockout → escalate to Primeforge/Litemail immediately
- CNIL complaint received → activate `cnil_response_playbook.md`
- Front-door synthetic fails 2 consecutive runs → investigate before next send batch
