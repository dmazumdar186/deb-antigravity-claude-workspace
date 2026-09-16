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
