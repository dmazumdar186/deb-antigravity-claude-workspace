# ProdCraft med-spa — round 4 audit stack (2026-09-21)

Branch `claude/upbeat-edison-epu2cz`, base `75f14df` (PR #15 merge). Scope: the five round-3 open items
(back-card headline clip, weeks-to-first-call in the spec, sends-vs-cap as code, `take_down_preview(dnc=)`,
one-command Loom recording for touch 2) plus the panel fixes below. Eleven lenses ran as four real sub-agents
(rigor 1/4/8, engineering 2/10, people 3/7/9, strategy 5/6/11), each with an Honest gaps list; the fix pass
ran as a fifth sub-agent; the six-tier suite ran in the same checkout.

## Lens verdicts on the pre-fix head (8e61868)

| # | Lens | Verdict | Finding that mattered |
|---|------|---------|-----------------------|
| 1 | Karpathy | PASS | `sends_vs_cap` reuses the send gate's counter and `effective_cap`; spec 2.1 arithmetic reproduces; "calls_to_pass" line ignored the +1 week reply lag |
| 2 | Cherny | PASS | `set_loom --touch` undocumented; duplicate URL validation; bounce path still used full-row upsert |
| 3 | Dario Amodei | WARN | Watermark promises "reply 'no' and this preview comes down", so a negative reply is a CAN-SPAM opt-out; the round-3 `dnc=False` request would have left no `do_not_contact` backstop |
| 4 | Anthropic research | WARN | Loom validator strict on hosts; `set_loom` redrafted on an unchanged URL; cascade semantics changed without a change-log line |
| 5 | Hormozi | WARN | Year-1 value / acquisition effort clears 3x (4.6x pessimistic, ~15x optimistic) only if Looms are recorded; section 2's 5 closes/month is unreachable under the 5/day cap |
| 6 | Saraev | WARN | Routine rung reached before any live output; touch-2 redraft after `set_loom` is auto-sent; sends-vs-cap line was a report, not an error-shaped alert |
| 7 | Daniela Amodei | PASS | Operator surface does not grow; one owner and a quiet path for parked touch-2 rows |
| 8 | Sutskever | WARN | With `dnc=False` sibling touch rows stayed open, got drafted, dropped at send and consumed a cap slot permanently; no second email could reach the person (two gates) |
| 9 | Murati | WARN | Exiting card body ghosted through the front card mid-exit; mid-word ellipsis at 800-1200px |
| 10 | Brockman | PASS | `fit_weights.main()` and `send.py --stats` could die without a Telegram page; local-vs-UTC day window |
| 11 | Hassabis | WARN | sends-vs-cap fed no decision; round 5 must not tune cap/ramp/weights before live data |

## Fix pass (applied, head after this commit)

- Negative reply is an opt-out: `scan_replies` takes the preview down with `dnc=True`, stamps `do_not_contact`
  even when no preview exists or the takedown fails, and cancels sibling touches. The `dnc` parameter stays for
  other callers. CONTRACTS.md carries the change-log line.
- Cron paths page on failure: `fit_weights.main()` and `send.py --stats` wrapped in `notify.error` + raise.
- UTC day window for `--stats` and the weekly line. Bounce path uses `update_row` (no lost update).
- Under-send alert: live only, cap > 0, 7-day sent < 50% of cap, shape `prodcraft_medspa / env / under_send_7d /
  sent=S cap=C / 1`, deduped per day.
- `set_loom.py`: single validation path, redraft only when the URL changed; `--touch` documented in the directive.
- PROJECT_SPEC: cap caveat (about 37 prospects/month gives 0.4-1.8 closes/month until the cap is raised after
  Phase 0), calls-to-pass corrected to weeks 5-6, "fully-touched" defined as touch 2 sent with a Loom URL.
- Template: exiting card body fades within the first 30% of its exit; front-card headline wraps to two lines at
  800-1200px; reduced-motion and no-JS paths unchanged.

## Evidence

| Check | Result |
|-------|--------|
| `pytest tests/prodcraft_medspa -q` | 674 passed, 35 skipped (184 s) |
| template `npm test` / typecheck / build | 33 passed; clean; exit 0 |
| `acceptance_template.py` | in 4, out 4, no failures, motion checks clean |
| worker and dashboard `npm test` + typecheck | pass after `npm ci` |
| mock chain, fresh store | 22 found, 16 kept, 6 qualified, 4 verified, 4 previews, 4 sent; rerun sends 0 |
| six-tier suite (pre-fix head) | all checks pass except 4 missing-`npm ci` tiers (pass on rerun) and pytest wall-clock 183 s vs 180 s; threshold raised to 240 s for the 29 added tests |

## Honest gaps

- Still no live path has run from code; every external service is fixture-verified. First live run needs the
  operator's secrets (HANDOFF section 7).
- The under-send alert and `notify_dedupe` are verified on LocalStore only.
- The two-line headline is applied by a JS attribute; no-JS keeps the single-line ellipsis. No 800-1200px
  screenshot in acceptance.
- Six-tier suite was not rerun after the fix pass on an idle machine; components were rerun individually.
- Reply classifier still has no gold set; a literal "no" that the LLM buckets as `negative` now opts out like
  `remove`, which is the safe direction.
- Section 2 of the spec still states a monthly target the Phase-0 cap cannot meet; the caveat is stated rather
  than the target rewritten.
