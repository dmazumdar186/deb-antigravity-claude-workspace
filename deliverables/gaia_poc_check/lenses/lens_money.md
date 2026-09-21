# Shortlist Check — money lenses (TOBIN/AtkinsRéalis + sceptical CFO)

Sources: `deliverables/gaia_poc_check/PLAN.md`, `deliverables/gaia_2026-09-10/transcript_2026-09-10_fathom.md`,
`deliverables/gaia_2026-09-10/call_brief_2026-09-10.md`, `deliverables/gaia_2026-09-10/radar_final_spec.md`,
`deliverables/gaia_poc_check/check_results.json`, `execution/gtm_client_workflows/gaia_sourcing/eval/time_value.py`.
No number below is invented; every "not in the repo" is flagged as such.

---

## A. TOBIN / AtkinsRéalis lens (the end client receiving CVs)

**What a wrong CV costs the agency relationship, in the repo's own words**

The repo does not contain a TOBIN/AtkinsRéalis quote about relationship cost — there is no transcript with the client, only with Keith. What the repo grounds this in is Keith's own framing of what a bad list does to *his* side of the relationship, which is the proxy for client cost:

- Call brief §1: "Underneath both [seniority, residence]: the sources we searched … are senior by construction." The 20 August list was 13/13 wrong against the eventual brief (check_results.json summary: 0 pass, 13 out on today's rules); every one of those 13 was a name Keith could have put in front of TOBIN/AtkinsRéalis on his own judgment before the gate existed.
- Call brief §2, objection list: "My consultants won't use it" and the honesty clause ("Role 2 needs new sources, not new filters") show the operator already treating a bad shortlist as a credibility cost with the client, not just wasted hours — but the brief never states a euro or reputational figure for a bad CV reaching TOBIN. **Not in the repo — ask Keith** (or ask him for a TOBIN contact) what actually happens when a CV is wrong: does it cost a slot in the next req, a probation-period conversation, or nothing measurable.
- Radar spec's bottleneck framing ("Gaia's constraint is precision and consultant follow-up capacity, not sourcing volume") is Prodcraft's inference from Keith's words ("cut the wheat from the chaff," "speed and accuracy are the two most important elements") — again Keith's proxy for the client relationship, not a TOBIN statement.

**What would make TOBIN/AtkinsRéalis prefer Gaia over a competitor agency**

Inferred from the check's own design, not stated by a client:
- An honest rejected count on every list (PLAN.md: "an honest rejected count" is one of the six things Recruit CRM does not do) — a competitor agency sending an unfiltered dump has no equivalent transparency device.
- Verifiable chartership + residence with quote and source on every CV, versus a 0-100 similarity score with no evidence trail (Recruit CRM comparison, PLAN.md "Why this and not something Keith already pays for").
- **Not in the repo — ask Keith**: whether TOBIN/AtkinsRéalis has ever explicitly compared Gaia to a competitor agency, or what they've said (if anything) makes them stay with Gaia.

**What TOBIN/AtkinsRéalis would want on a CV cover note**

Directly derivable from the check's own evidence contract (`check_results.json` rows schema, PLAN.md contract): each PASS row carries `evidence: [{dimension, quote, source_url}]` and a `contact` label. So the natural cover-note fields, in the repo's own vocabulary, are:
- "Chartered: [verbatim quote] — [source URL]" (gate `chartered`, Engineers Ireland CEng/MIEI/FIEI stated in a public source)
- "Resident in the Republic of Ireland: [verbatim quote] — [source URL]" (gate `located_ie`; a project or firm-office mention explicitly does not count per the 11 Sep gate fix)
- "Grade/seniority: [years or title evidence] — [source URL]" (gates `seniority` / `seniority_ceiling`)
- "Contact: verified | catch-all | guess | none" (contact label, never silently omitted)
- One "rejected count" line at the bottom of the shortlist itself (not per-CV): "N considered, N passed, N rejected and why" — this is the check's headline device, not currently a per-CV field.
No repo file states TOBIN asked for these fields; they are Prodcraft's construction from the gate/evidence contract. **Confirm the actual cover-note preference with Keith or TOBIN directly — not in the repo.**

**Five questions TOBIN/AtkinsRéalis would ask if told "every name is checked against the public record before we call"**

1. "Checked against which public sources, exactly — and what happens when the evidence is silent (project mention, no residence statement)?" (the repo's own gate treats silence as fail by default — `treat_unknown_as: fail` in check_results.json — worth being able to say plainly.)
2. "How many names did you reject to get to this shortlist, and why?" (answerable today: the August-list machinery already tracks pass/near-miss/out counts and by-rule breakdown.)
3. "Is the chartership check against the actual Engineers Ireland register, or against the person's own claim?" (Honest answer per PLAN.md item 4/call brief §6: register terms are unverified, so today it's "the person's own post-nominals and their employer's page" — the card says which. This is a real gap, not spin.)
4. "What's your false-positive rate — how often has a 'PASS' from this check turned out wrong once we interviewed them?" **Not in the repo** — no post-hire audit trail exists yet; the September re-run was "audited four times" (0 of 2 wrong) but that is Gaia's own audit, not client feedback.
5. "Does this replace your consultants' judgment or does a human still decide who gets called?" (Answerable from the design: the check gates before the call, a consultant still decides; PLAN.md explicitly keeps "checked by hand" language and never claims full automation.)

---

## B. Sceptical CFO / Keith's accountant lens

**(1) Placement-fee-at-risk argument**

Placement fee: EUR 14-20k (18% of EUR 80-110k) — call brief §3, "Cost per role." One wrong CV reaching a client at minimum risks the *time* to that fee (a slower cycle, a burned req) and at maximum risks the relationship producing that fee at all if it happens repeatedly (August: 13 of 13 wrong on today's brief). Per-role cost of the check itself is ~EUR 100-120 (LLM + OCR + people-data + search, call brief §3) run against a EUR 14-20k fee — a >100x ratio on the cost side alone, before counting time saved. This is the strongest lever available: the check's own operating cost is two orders of magnitude below the fee it protects.

**(2) Consultant-hours argument, with the 15-minute assumption flagged**

`time_value.py` computes this deterministically; **`minutes_per_manual_check = 15` is Prodcraft's stated assumption, not something Keith has confirmed** (PLAN.md day-2 decision (b): "Keith gave no figure … the minutes question is asked live on the follow-up call"). At `names_per_week = 40` (conservative against Keith's stated ambition of 50-100 live jobs — call brief/transcript), `hourly_cost_eur = 45`:

| minutes/check | hours/week | EUR/week | EUR/month |
|---|---|---|---|
| 5 min | 3.33 | 150.00 | 650.00 |
| 10 min | 6.67 | 300.00 | 1,300.00 |
| 15 min (assumed default) | 10.00 | 450.00 | 1,950.00 |

The monthly figure moves 3x across the plausible 5-15 minute range — the CFO should treat "EUR ~650 to ~1,950/month in consultant time" as the honest band, not a single number, until Keith gives a real figure.

**(3) Cost of a wrong list, using the August list**

August list: 13 names, 0 pass today's brief (check_results.json summary), 4 emails sent to people who could never be placed on the brief (an editable assumption in `Assumptions.emails_written`, sourced from the operator's own note, not derived from a logged field — flagged in the module's own docstring as such). Consultant hours burned on that list at the 15-minute assumption: 13 × 15/60 = 3.25 hours (`august_list()` output), or 1.08 hours at 5 minutes / 2.17 hours at 10 minutes. In euros at EUR 45/hr: EUR 146 (15 min) down to EUR 49 (5 min) — small in isolation, but the real cost of that list was zero of 13 being placeable and 4 emails to unplaceable contacts, i.e. a 100% miss rate on a list Keith believed was gradeable ("I recognize a lot of the candidates" — but "too senior" on all ten Role-1 names, call brief).

**(4) Pricing shapes that fit, and which a 5-person agency would accept**

Shapes present in the repo:
- **Per verified name / per check** — closest to Recruit CRM's own credit-metered model Keith already accepts (PLAN.md, "credit-metered" AI Sourcing); usage scales with volume Keith controls directly, easy to explain, easy to cancel a month with fewer roles.
- **Per role/pilot** — the call brief's actual proposal rung B: "Pilot, 30 days, 3 live roles… suggested EUR 1,500-2,500, under 15% of one placement," success-linked, "no fee if missed." Explicitly reasoned in the brief: "Success-linked beats flat monthly for a five-person agency."
- **Per niche per month** (Radar spec's later-stage offer): "For EUR X per niche per month… less than one Recruit CRM Business seat, against one EUR 14-20k placement… Cancel any month… if you don't get three approved candidates in the first 30 days you pay nothing." This is the Radar (ongoing sourcing) product, not the check alone — the repo explicitly separates them (PLAN.md open item 6: "Pricing rung for the check alone… versus the Radar subscription").
- **Own it / build fee** (rung C, EUR 6-9k build + ~EUR 200-300/month maintenance) — explicitly "not raised on this call," a later stage only.

Recommended shape for a 5-person agency, per the repo's own stated reasoning: **success-linked pilot pricing (rung B), not a flat monthly fee**, because the brief states outright that "success-linked beats flat monthly for a five-person agency" — a shop this size cannot absorb a fixed cost with no guaranteed output, but will accept a small fee gated to a stated, falsifiable outcome (10 approved candidates, 2 first conversations per role) with "no fee if missed."

**(5) Six questions the CFO asks, and the answers**

1. "What does this cost to run per name?" — EUR 0 on cached names (already-checked pool), roughly EUR 0.10-0.30 for discovery on a new name (PLAN.md "The demo that costs nothing" / open item 3).
2. "What does this cost to run per role, all-in?" — about EUR 100-120 (LLM ~EUR 13, OCR EUR 5-15, people data ~EUR 60-80/300 profiles, Prospeo ~EUR 2, search ~EUR 5 — call brief §3).
3. "What's the payback if it prevents even one bad placement?" — the placement fee at risk is EUR 14-20k; the check's per-role cost is <1% of that fee.
4. "How confident are we in the 'hours saved' number?" — not very, yet: 15 minutes/check is an unconfirmed assumption; the honest range is EUR 650-1,950/month depending on the real number, and Keith has not been asked for it (deliberately deferred to the follow-up call per PLAN.md day-2 decision (b)).
5. "What happens if we stop paying?" — the check layer sits in front of the call, not inside Recruit CRM or Maddie's screener (PLAN.md "Who reads what" / integration design); nothing else breaks, and the pilot pricing structure (rung B) is explicitly no-fee-if-missed and cancel-any-month for the niche-based Radar offer.
6. "Is the August-list evidence real or cherry-picked?" — it's the actual list Keith already received and holds (PLAN.md: "the exact list Keith already holds, offline, zero model spend"), re-run against today's brief with the same code path that would run any future list; the September re-run (0 of 2 wrong) was independently audited four times.

**(6) Strongest vs weakest numbers on Keith's page, under scrutiny**

Strongest: the **placement-fee-at-risk ratio** (EUR 100-120 cost vs EUR 14-20k fee, >100x) and the **August list's 0-of-13-pass / 4-emails-to-unplaceable-contacts** count — both are counted from source (the fee band from the pricing model, the 0/13 from a deterministic gate re-run on Keith's own list), not assumptions.

Weakest: the **15-minute-per-check assumption** feeding every euro-per-month figure — it is explicitly unconfirmed (PLAN.md: "Keith gave no figure... the 15 minutes stays an assumption until he sets it"), swings the monthly value claim 3x (EUR 650 to EUR 1,950), and a sceptical CFO will immediately ask where it came from. Close behind: `emails_written = 4` is also an editable assumption sourced from the operator's own recollection, not a logged count (flagged in the module's own docstring) — small in isolation but part of the same "assumption dressed as fact" family the CFO should probe.

---

## Answer for the caller (also below, per instructions)

**Strongest single value argument**: the placement-fee-at-risk ratio — the check costs ~EUR 100-120 per role to run against a EUR 14-20k placement fee (18% of EUR 80-110k), a >100x cost-to-risk ratio, reinforced by the August list's own record (13 names, 0 pass today's brief, 4 emails to people who could never be placed).

**Weakest number on the page**: the 15-minutes-per-manual-check assumption — Keith has never confirmed it, and it alone swings the monthly consultant-hours value claim from ~EUR 650/month (5 min) to ~EUR 1,950/month (15 min), a 3x range built on an unconfirmed input.

**Recommended pricing shape**: success-linked pilot pricing (per-role/30-day pilot, small fixed fee, no fee if the stated outcome is missed) rather than a flat monthly fee — because the repo's own reasoning states a five-person agency will accept an outcome-gated small fee but not an unconditional fixed cost, and this is the shape Keith has already been offered in the call brief's proposal rung B.
