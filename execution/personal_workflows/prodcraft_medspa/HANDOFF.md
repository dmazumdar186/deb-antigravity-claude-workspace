# ProdCraft med-spa pipeline — handoff (2026-09-16, session 2)

Branch: `claude/mobile-responsive-website-gup5d2` (all work committed and pushed; see `git log`).
Spec: `PROJECT_SPEC.md`. Build contracts: `CONTRACTS.md`. Panel pass (six lenses, decisions D1–D11):
`docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`. Audit stack for this session (pipeline-auditor,
code-reviewer, six lenses, verdicts + fixed/open findings): `docs/audits/prodcraft_medspa_audit_stack_2026-09-16.md`.
Directive: `directives/personal_workflows/prodcraft_medspa_pipeline.md`. Panel roster: `.claude/memory/panel_roster.md`.

## State: the mock chain is gap-free end to end

```
R=.tmp/prodcraft_medspa/x/store
python3 execution/personal_workflows/prodcraft_medspa/db/apply_schema.py --store local --root $R
python3 execution/personal_workflows/prodcraft_medspa/scripts/run_metro.py --metro chicago_north_shore --mock --store local --store-root $R
python3 execution/personal_workflows/prodcraft_medspa/scripts/daily.py --mock --store local --store-root $R
```
yields: found 22 -> kept 16 (chain 2, not_operational 1, too_small 2, no_name 1) -> audited 16 -> qualified 6
(borderline 6, skip 4) -> owner found 6 -> email verified 4 (risky 1, no_email 1) -> previews built 4 (real Next.js
builds) -> approved 4 (mock-only auto-approve) -> daily queue 4 enqueued, 4 drafted, 0 lint failures, 4 mock Gmail
drafts. A second run on the same store changes no row counts (`skipped_unchanged 4`). Every number was recomputed
by hand from fixtures by the pipeline-auditor.

Green set: `pytest tests/prodcraft_medspa` 405 passed / 35 skipped; worker 15, dashboard 38, template 16 vitest +
clean typechecks; `template: npm run build` + `acceptance_template.py` 0 failures on both viewports.

## What changed this session (items 1-6 of the previous handoff, all done)

1. **Fixtures aligned** to discovery's 22 canonical hosts (`audit/fixtures/mock_map.json`, `enrich/fixtures/*`);
   vision golden PNGs are now tracked (root `.gitignore` negation) and the test self-heals via `make_golden.py`.
2. **`run_metro.py`** always runs the full audit; `--sample-n N` adds `sample_audit --reuse-audits` (metro_stats
   only, nothing audited twice); `--sample-only` is the cheap Phase 0 step 7; `--auto-approve` (implied by `--mock`,
   local store only) appends the `approve` stage; run-record filenames carry a uuid.
3. **Store boundary**: `list_rows/get_row/update_row/list_previews/list_outreach/load_chains` on the Protocol and both
   backends; no caller touches `_read`/`_request`. Hardened after review: params-encoded PostgREST filters with a key
   allowlist, Range pagination, `ID_TABLES`, idempotent inserts (client ids + merge-duplicates), no blind retries,
   `load_chains` merges, slug uniqueness enforced locally.
4. **Template**: `build` runs `gen-stock` (stock PNGs are gitignored); acceptance asserts the full watermark sentence
   and that the sticky mobile bar clears the footer remove link. Cross-process build lock (`template/.build.lock`,
   gitignored) + post-build business-name assertion in `build_preview.py`.
5. **Directive** documents `preview.publish extend`, `preview/approve.py`, the sender-config step (6a), and the
   `--sample-only` Phase 0 command. `execution/REGISTRY.md` regenerated.
6. **Audit stack run and findings fixed** (details in the audit-stack doc): word-bounded chain filter, no network
   under `--mock` (screenshots skipped), `--mock` never combines with `--store supabase` in any CLI, `MOCK_SENDER`
   only with `--mock` on a LocalStore, `preview/approve.py` needs `--yes-i-reviewed-them` for a live bulk approve,
   `doctor.py` checks `config.sender` and never crashes, `publish extend` keeps a valid status and warns when a
   touch-4 deadline email already went out, owner-name regex no longer matches lowercase words after "owner",
   LLM envelopes carry `mock: true/false` and are persisted on outreach rows, dashboard shows `reply_rate_health`,
   the unsourced "78%" phone-booking statistic was softened to a qualitative sentence.

New mock-only shortcuts, both refused on a Supabase store: `run_metro --mock` auto-approves previews; `draft_email
--mock` substitutes a clearly labelled synthetic sender when `config.sender` is empty.

## Commands that must stay green

```
python3 -m pytest tests/prodcraft_medspa -q
cd execution/personal_workflows/prodcraft_medspa/preview/worker && npm test && npm run typecheck
cd execution/personal_workflows/prodcraft_medspa/dashboard && npm test && npm run typecheck
cd execution/personal_workflows/prodcraft_medspa/template && npm run typecheck && npm test && npm run build
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/prodcraft_medspa/acceptance_template.py
(the apply_schema -> run_metro --mock -> daily.py --mock chain above; expect 4 previews and a 4-row drafted queue)
```
Do not run two `run_metro` processes against the same checkout at once during verification; the build lock
serializes them, so the second waits (up to 15 minutes) rather than failing.

## Honest gaps (open after the audit stack)

- **Nothing live has been exercised.** Every Supabase, Places, PSI, Claude, Apollo, Findymail, MillionVerifier,
  R2/Worker, Gmail and Telegram path runs against fixtures only. PostgREST behaviours added this session (Range
  pagination, `on_conflict=id` upserts, 409 on slug collisions) are asserted from docs and unit-tested with a
  monkeypatched request, never observed. First live run: operator machine, after `doctor.py --live` is green.
- **Mock fidelity**: the vision fixture scores every site "dated" (+15), which is what lifts the two WordPress
  sites to qualified; `--skip-vision --mock` ends at 2 previews. The IL state-registry fixture returns one owner
  name for every IL business; the fuzzy-variables fixture is one constant blob. The mock chain proves plumbing,
  schema and gating, not LLM output quality.
- **Vision golden regression test is inert in cloud** (skips without `ANTHROPIC_API_KEY`); it only proves the six
  synthetic PNGs exist. Operator labels 20 real screenshots before trusting the 15-point signal.
- **No quantified proof in the emails** until the first founding clients yield a before/after booking number for
  `config.proof_lines`. The "78%" statistic was removed for lack of a citation; restore it there with a source.
- **Guarantee edge**: `baseline_online_bookings_30d = 0` makes `guarantee_met` trivially true; a floor clause is an
  offer decision (Hormozi lens).
- `scan_replies.py` persists only the classification, not the full LLM envelope, on the outreach row.
- The self-healing "3 recurrences" rule is a standing instruction; nothing counts recurrences.
- `events` grows on every run by design (append-only log); the other tables are idempotent.
- Prompts, templates and README/CONTRACTS prose still contain em-dashes; the customer-facing email templates
  and rendered drafts contain none (checked for U+2014).

## 7. Operator-only (cannot be done in cloud, no secrets) — unchanged plus one item

- Create the Supabase project and run `db/schema.sql` (`db/apply_schema.py --store supabase`).
- Create the R2 bucket + KV namespace, set Worker secrets, deploy the Worker, wildcard DNS `*.preview.prodcraft.fyi`.
- Deploy the dashboard with Basic Auth secrets.
- Gmail OAuth token; Telegram error channel (`notify.py --sample`, then confirm the message arrived).
- **Set `config.sender` (name + postal address)** via the dashboard Config tab or `store.set_config("sender", ...)`;
  until then every live draft fails the CAN-SPAM lint on purpose (directive step 6a; `doctor.py --stages outreach`
  reports it).
- Set the GitHub repo var `PRODCRAFT_CRON_ENABLED=true` and the secrets named in `prodcraft_medspa_replies.yml`.
- `python3 execution/personal_workflows/prodcraft_medspa/scripts/doctor.py --live` green, then the first real
  `run_metro.py --metro chicago_north_shore --stages discovery,audit --sample-n 40 --sample-only`.

## Session constraints learned

- Cloud env: Python 3.11, Node 22, Chromium at `/opt/pw-browsers` (never `playwright install`), no pipeline secrets;
  the safety hook blocks `rm -rf` (use fresh `.tmp` subdirs). `pip install pytest python-dotenv requests playwright
  anthropic pillow` and `npm ci` in the three Node packages are needed in a fresh container.
- Run at most 3-4 Sonnet sub-agents concurrently; commit after each lands. Agents that run the mock chain at the same
  time used to break each other's Next.js build; the process lock now makes them queue instead.
