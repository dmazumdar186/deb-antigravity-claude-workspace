# Audit stack — ProdCraft med-spa pipeline, gap-free mock chain (2026-09-16)

Subject: `execution/personal_workflows/prodcraft_medspa/` on branch `claude/mobile-responsive-website-gup5d2`,
after HANDOFF items 1-5 landed. Every lens below ran as a real sub-agent (pipeline-auditor on Fable,
code-reviewer on Opus, six panel lenses on Sonnet), each ending with Honest gaps. Findings marked
**[FIXED]** were closed in the same session before the final verification pass; **[OPEN]** items are
carried into HANDOFF.md.

## Verification pass after fixes

| Check | Result |
|---|---|
| `python3 -m pytest tests/prodcraft_medspa -q` | 405 passed, 35 skipped (Supabase-env and live-API skips) |
| worker / dashboard / template vitest + typecheck | 15 / 38 / 16 passed, typechecks clean |
| `template: npm run build` then `acceptance_template.py` (390x844 + 1440x900) | 0 failures, expired page ok |
| `apply_schema -> run_metro --mock -> daily.py --mock` | 22 found -> 16 kept -> 16 audited -> 6 qualified -> 6 owner -> 4 verified -> 4 previews -> 4 approved -> queue 4 drafted, 0 lint failures |
| second `run_metro --mock` on the same store | previews 4 (skipped_unchanged 4), approve in 0, row counts unchanged |

## Pipeline-auditor (Fable) — PASS with warnings

All 16 audit scores recomputed by hand from fixture HTML/PSI match the stored rows; every drop carries a
reason; funnel reproduced in an isolated run; Wilson interval for `--sample-n 8` recomputed by hand and
matches; `--reuse-audits` prevents double audits.
- **[FIXED]** Chain filter was a substring match: pattern `ulta` dropped "Consultation Skin Clinic", `elase`
  would drop "Release Spa". Now word-bounded (`discovery/places_search.py`, test added).
- **[FIXED]** Concurrent `run_metro` processes clobbered `template/` (only an in-process lock). Added a
  cross-process file lock on `template/.build.lock` and a post-build assertion that the export contains the
  intended business name (`preview/build_preview.py`, tests added). Run-record filenames now carry a uuid.
- **[FIXED]** `--mock` audits still opened Playwright against `*.test` hosts (network). Screenshots are
  skipped under mock.
- **[FIXED]** `--mock` was accepted with `--store supabase` by several CLIs; email_status None was labelled
  "unknown"; the queue table's preview column was inferred from the subject rather than the body.
- **[OPEN]** Qualified count depends on the constant vision fixture (dated_score 8 for every site); with
  `--skip-vision` the mock funnel ends at 2 previews. Mock-fidelity limitation, documented.
- **[OPEN]** IL state-registry fixture returns the same owner for every IL business; fuzzy-variable fixture
  is one constant blob. Mock-only.

## Code-reviewer (Opus) — FAIL before fixes, all four criticals closed

- **[FIXED]** C1 PostgREST filter keys/values interpolated unencoded into URLs: now `requests` params
  tuples plus a `[a-z_][a-z0-9_]*` key allowlist on every column/order key.
- **[FIXED]** C2 no pagination in `SupabaseStore.list_rows` (1000-row cap): pages with Range headers.
- **[FIXED]** C3 `doctor.py` crashed on an unconfigured Supabase store: guarded, reports a row.
- **[FIXED]** C4/M1 `--mock` and `--auto-approve` could reach a live store: every store-touching CLI rejects
  `--mock --store supabase`; `--auto-approve` is local-store only; `approve.py` needs
  `--yes-i-reviewed-them` for a live bulk approve; `MOCK_SENDER` also requires a `LocalStore`.
- **[FIXED]** M2 `publish extend` wrote an invalid `status="active"`; M3 `load_chains` overwrote the table;
  M4 retry loop hid status codes, slept after the last attempt and blind-retried inserts (inserts now carry
  client ids and merge-duplicates; events never retry on 5xx); M5 id-based accessors on id-less tables
  (`ID_TABLES`); minors (mixed-type sort, events id, vacuous test, takedown lost-update, O(n^2) funnel).
- **[OPEN]** All Supabase-side behaviour (Range pagination, `on_conflict=id`, 409 on slug collisions) is
  asserted from PostgREST documentation and unit-tested with a monkeypatched request; never observed live.

## Karpathy — PASS-WITH-CHANGES

Wilson math verified; fit_weights refuses under 50 sends and never mutates weights; Phase 0 gate is
config-driven; reply rate per touch is a real division.
- **[OPEN]** The vision golden regression test is inert without `ANTHROPIC_API_KEY`; in cloud it only proves
  the fixture files exist. Labelled honestly in HANDOFF.
- **[FIXED]** `fit_weights.py` docstring claimed "exact" mirroring; it now names its two simplifications.

## Cherny — PASS-WITH-CHANGES

Store boundary grep empty; both store backends agree on filters, ordering, null placement and
`updated_at`; registry lists `preview/approve.py`.
- **[FIXED]** The two red must-stay-green commands (template build ENOENT, acceptance name mismatch) were
  the cross-process clobbering above; both pass in isolation now.
- **[FIXED]** `--mock`/`--store` not universal: added to `deals.py`, `transition.py`, `scoring.py`;
  CONTRACTS.md now names the pure-function CLIs that take neither.
- **[OPEN]** `events` grows on every run by design (append-only log).

## Amodei — PASS-WITH-CHANGES

Takedown path is mechanical end to end (quoted history stripped before classification); forbidden-term
lists agree between Python and TS; booking demo sends nothing; CAN-SPAM linter matches the checklist 1:1;
no em-dash in any email template; fixtures are synthetic.
- **[FIXED]** The "about 78% of med spa bookings still come in by phone" statistic had no citation anywhere
  in the repo. Softened to "most med spa bookings still start with a phone call" in touch-1 variants a/c
  and the fallback proof line. A sourced number belongs in `config.proof_lines`, which takes precedence.
- **[FIXED]** `--auto-approve` live footgun (see code-reviewer C4/M1).

## Research team — PASS-WITH-CHANGES

Scoring matches CONTRACTS exactly; model ids pinned, temperature 0, prompt hash and four token counts
recorded; state machine table matches and the test enumerates every legal and illegal pair.
- **[FIXED]** Mock LLM envelopes were indistinguishable from live: `mock: true/false` is now in every
  envelope. Outreach LLM envelopes were discarded: persisted in `outreach.notes.llm`.
- **[FIXED]** Slug uniqueness is now enforced by `LocalStore.upsert_business` as well as the schema.
- **[OPEN]** `scan_replies.py` still keeps only the classification, not the full envelope, on the row.
- **[OPEN]** `sent -> closed_lost` timing guard lives in `advance.py`, not inside `transition()`.

## Hormozi — PASS-WITH-CHANGES

Founding tier, measured baseline and computed `guarantee_met` confirmed; touch-4 deadline reads the real
`expires_at` and the Worker cron enforces it; the mobile preview reads as a credible lead magnet.
- **[FIXED]** `publish extend` could silently falsify an already-sent touch-4 deadline: it now logs
  `after_touch4_sent` and prints a correction warning.
- **[FIXED]** Dashboard showed sends-per-reply with no threshold: `reply_rate_health` (insufficient_data,
  on_track >= 10%, below_target, below_platform_average < 4%) added to the stats API and UI.
- **[OPEN]** `baseline_online_bookings_30d = 0` makes the "double your bookings" guarantee trivially met;
  a floor clause is an offer decision for the operator.
- **[OPEN]** No quantified proof exists until the first founding clients produce a before/after number.

## Saraev — PASS

Phase 0 gate has exactly two write paths (real transitions, human dashboard override with a reason); no
customer-facing message is ever sent by code (drafts only; takedown is the one customer-requested action);
two named fuzzy variables inside human-written templates; error channel shape correct with 13 call sites.
- **[OPEN]** The "3 recurrences" self-healing rule is a standing instruction with no counter.
- **[OPEN]** `notify.py --sample` has never been observed in the Telegram channel (needs secrets).

---

# Round 2 (same day, after the automated loop, the live first-5 dry run and template v2)

Subject: the fully automated loop (import/discover -> audit -> enrich -> preview -> queue -> **send** -> scan ->
Telegram), the live first-5 dry run to the operator's own inbox (store `.tmp/prodcraft_medspa/live/store1`, not in
git), and the scroll-driven template v2. Eleven lenses plus pipeline-auditor and code-reviewer, every one a real
sub-agent ending with Honest gaps. Fixes landed in commits 49cac2a, 1290b1e, d32b88e, fa7d256, ee8041f and the
send-path follow-up (see HANDOFF.md for the final verification pass).

| Lens | Verdict | Blocking findings -> status |
|---|---|---|
| Pipeline-auditor (Fable) | WARNINGS | emailed preview links were private artifact URLs -> **[FIXED]** send-time `preview_not_public` guard (live sends without override refuse non-r2 / wrong-host previews); `build_preview` logged orphan built/published events with a never-stored uuid and the merge downgraded approved -> review -> **[FIXED]** returned-row id + sticky-status merge guard; unlogged manual store patches -> **[FIXED]** `Store.manual_patch` and `redraft` transition; 9 stale pre-fix audit rows -> **[FIXED]** flagged `superseded` with a logged event; `min_score 20` admitted a skip-bucket site -> **[FIXED]** validation floor 25 (Perlis dropped from the rebuilt set) |
| Code-reviewer (Opus) | FAIL -> fixed | missing Supabase columns -> **[FIXED]** migrations 0003/0004; override silently unset -> **[FIXED]** banner + stat + `live_send_confirmed` gate; own outbound message classified as a reply -> **[FIXED]**; day-2 queue starvation -> **[FIXED]** with a two-day simulation test; no live approval path -> **[FIXED]** `preview_gate.py` (opt-in `auto_approve_previews`, default false); `chr(ord("A")+n)` -> **[FIXED]**; header injection / From header / RFC 2822 dates / PII in logs / silent excepts -> **[FIXED]** |
| Karpathy | PASS-WITH-CHANGES | fit_weights counted dry-run rows -> **[FIXED]** `test_recipient` exclusion |
| Cherny | PASS-WITH-CHANGES | `--date not-a-date` leaked a traceback -> **[FIXED]** both parsers; REGISTRY missing two scripts -> **[FIXED]** regenerated; HANDOFF stale -> **[FIXED]** rewritten |
| Dario Amodei | PASS-WITH-CHANGES | placeholder postal address passed lint -> **[FIXED]** `sender_address_is_valid`; no enforced live gate -> **[FIXED]** `live_send_confirmed` + `--confirm-live-sends` |
| Research team | PASS-WITH-CHANGES | config validation, None-signal handling, seed recording, sanctioned `redraft`, CONTRACTS None semantics -> **[FIXED]** |
| Hormozi | PASS-WITH-CHANGES | zero-baseline guarantee trivially met -> **[FIXED]** `ZERO_BASELINE_FLOOR = 5`; Phase 0 should pick by score -> **[FIXED]** score ordering until `phase0.passed`; CTA/subject variety -> **[OPEN]** operator copy decision |
| Saraev | PASS-WITH-CHANGES | no List-Unsubscribe header -> **[FIXED]**; no warmup ramp -> **[FIXED]** 2 -> 5 over 14 days from the first live send; SPF/DMARC never checked -> **[FIXED]** best-effort in doctor; sample Telegram send never observed -> **[OPEN]** needs secrets; auto-send vs automation-boundaries -> **[FIXED]** reconciled in the directive |
| Daniela Amodei | PASS-WITH-CHANGES | takedown lived only in daily.py -> **[FIXED]** state machine takes down on DNC itself; no PII purge path -> **[FIXED]** `Store.purge_pii` + `scripts/purge_pii.py` + retention policy; forgotten override could go live -> **[FIXED]** `live_send_confirmed`; Places ToS / look-alike site legal question -> **[OPEN]** operator/counsel |
| Sutskever | PASS-WITH-CHANGES | degraded and full audits indistinguishable -> **[FIXED]** `audits.mode` + `max_measurable`; fit_weights mixed regimes -> **[FIXED]** `--mode` filter (CLI default full); variant outcome never analysed -> **[FIXED]** variant table; remove classified by LLM alone -> **[FIXED]** Telegram notify on every remove with `remove_source`; no gold set for the classifier -> **[OPEN]** |
| Murati | PASS-WITH-CHANGES | placeholder address in sent test emails -> **[FIXED]** (lint); all five drafts on variant c -> **[FIXED]** per-business hash; two opt-out verbs -> **[FIXED]** one sentence, "reply 'no'"; hero copy identical across spas -> **[FIXED]** template v2 states built from each spa's data; hours unknown for 5 of 5 -> **[OPEN]** needs Places details live |
| Brockman | FAIL -> fixed | cron never approved previews -> **[FIXED]** `preview_gate.py` step; Playwright never installed in CI -> **[FIXED]**; no doctor pre-check -> **[FIXED]**; R2 access keys invisible to doctor/config -> **[FIXED]**; single 60-minute job -> **[FIXED]** per-step timeouts, sync always, Telegram on failure or cancel; R2 token setup step and verbatim command block missing -> **[FIXED]** directive |
| Hassabis | PASS-WITH-CHANGES | cost not durably stored -> **[FIXED]** `audits.llm_cost_usd`; learning loop never scheduled -> **[FIXED]** weekly workflow + Telegram report; recompute diffs not stored -> **[FIXED]** `score_recompute_diff` events; guarantee unverifiable -> **[FIXED]** `--evidence-ref` required, PROJECT_SPEC 9.1; metro-blind fitting -> **[FIXED]** `--metro`; zero-sends-with-no-alert -> **[FIXED]** notify on zero sent with blocked previews |

## Live first-5 dry run evidence (operator inbox only, no prospect emailed)

- Five emails sent through the Gmail connector to the operator's address with `[TEST to <owner_email>]` subjects;
  Gmail message ids and `test_recipient` recorded on the outreach rows; `daily_log` and `pipeline` tabs mirrored to
  the connected Google Sheets.
- Previews hosted as private claude.ai artifacts (no R2 secrets in cloud); rebuilt on template v2 and republished
  to the same URLs (Version 4) for four spas; the fifth (score 22, skip bucket) is excluded by the new floor.
- Every live path the loop needs (Places, PSI, Anthropic, Gmail OAuth, Telegram, Supabase, R2) is still
  unexercised from code; connectors stood in for them in-session.

---

# Round 3 (2026-09-17, final head re-verification)

The operator asked whether the project was ship ready. Round 2 had judged a mid-day state, so every lens
re-ran against the final head, each re-verifying its own round-2 findings and then reading with fresh eyes.
Fixes landed in 8632a59, 6eef986, c7b60c3, 0122d6c and 898f4c6.

| Lens | Round-2 findings | New findings -> status |
|---|---|---|
| Pipeline-auditor (Fable) | all mock-chain and guard claims re-executed and PASS | redraft wrote a nonexistent column -> **[FIXED]**; daily.py swallowed send.py's banner -> **[FIXED]**; stale watermark sentence in the RSC payload -> **[FIXED]** at the source (content_lint); live store had triplicate preview rows and an approved preview for the excluded spa -> **[FIXED]** (deduped, demoted, logged) |
| Code-reviewer (Opus) | n/a | FAIL: touch-2 drafts failed lint forever on the Loom placeholder, lint-failed rows starved the cap, one reply processed once per sent touch, PII in CI logs, purge left notes and drafts, racy cap, unfailable secret step, silent live switch, layout thrash, observer leak -> **all [FIXED]** |
| Brockman | 8 of 8 FIXED | replies cron lacked R2 keys for takedowns -> **[FIXED]** |
| Cherny | all FIXED | one test stale against the worker's in-flight tree -> **[FIXED]** |
| Daniela Amodei | 4 of 4 FIXED | failed takedown had no retry -> **[FIXED]** reconcile_takedowns each daily run |
| Dario Amodei | 2 of 2 FIXED | double-send race -> **[FIXED]** Store.claim_row; silent zero-send weeks -> **[FIXED]**; malformed classifier response aborted the scan -> **[FIXED]** |
| Karpathy | FIXED | audit stamped "full" when screenshot capture failed -> **[FIXED]** derive_mode |
| Murati | 4 of 4 FIXED, all four previews checked live at both widths | back-card headline clips under the front card corner -> **[OPEN]** cosmetic |
| Hormozi | 4 of 4 FIXED (CTA softness stays an operator copy decision) | `[[LOOM URL]]` could reach a prospect -> **[FIXED]** send.py needs_operator_input guard; weeks-to-first-call not stated in PROJECT_SPEC -> **[OPEN]** doc |
| Saraev | 6 of 6 FIXED | none |
| Sutskever | 5 of 5 FIXED | negative takedown silent -> **[FIXED]**; right-censoring only on events -> **[FIXED]** row column; Phase 0 passed on one call -> **[FIXED]** calls_to_pass |
| Hassabis | 6 of 6 FIXED | "sends vs cap" weekly number is a hand query -> **[OPEN]** |
| Research team | 5 of 6 FIXED, 1 clarified | score_at_send prose said "on send" -> **[FIXED]** documented as enqueue-time snapshot matching fit_weights' join; claim_row added to the Store interface |

Coordinator's own day-4 mock run (not found by any lens): touch 2 to 4 rows were never drafted because the
already-drafted check keyed on the inherited subject; redraft left the old body; the park flag never
cleared after a Loom URL was recorded; re-renders overwrote prior notes. All **[FIXED]** with
`tests/prodcraft_medspa/test_round3.py`.

Final verification on 898f4c6: pytest 645 passed / 35 skipped; vitest 29; typecheck, build, acceptance
(including the new mobile card-opacity check) clean; `test_suite_tiers.sh` ALL CHECKS PASSED; mock chain
day 1 sends 4, day 4 drafts 4 touch-2 rows, parks them, sends the one with a recorded Loom URL.
