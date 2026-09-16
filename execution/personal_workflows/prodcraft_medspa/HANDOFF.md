# ProdCraft med-spa pipeline — handoff (2026-09-16)

Branch: `claude/mobile-responsive-website-gup5d2` (all work committed and pushed; HEAD `66e991f`).
Spec: `PROJECT_SPEC.md`. Build contracts: `CONTRACTS.md`. Panel pass (six lenses, decisions D1–D11):
`docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`. Directive: `directives/personal_workflows/prodcraft_medspa_pipeline.md`.
Panel roster (now includes Hormozi + Saraev): `.claude/memory/panel_roster.md`.

## What is built and green

`python3 -m pytest tests/prodcraft_medspa -q` → 330 passed, 18 skipped (Supabase-only, no env in cloud).

| Package | State | Tests |
|---|---|---|
| `common/` (config, models, Store Protocol + LocalStore + SupabaseStore, llm, notify, http, slug) | done | test_store, test_llm, test_slug, test_notify |
| `db/` (schema.sql, migrations, seeds, apply_schema) | done | via test_store |
| `discovery/` (Places tiling, dedupe, chain filter, 10 metro tile sets, verify_counts) | done | 28 |
| `audit/` (fetch, PSI, tech/booking detect, screenshots, vision, scoring, sample_audit, Wilson) | done | 106 |
| `enrich/` (7-step waterfall + MillionVerifier) | done | 33 |
| `preview/` python (extract_services, content_lint, R2 SigV4, publish/extend/takedown, build_preview) | done | 26 |
| `preview/worker/` (TS Worker: wildcard host, R2 serve, expiry cron, /remove, /api/publish) | done, typecheck + 15 vitest | |
| `template/` (Next.js 15 static export, mobile-first, booking demo, content lint) | done, 16 vitest + build + acceptance both viewports | |
| `dashboard/` (Pages Functions + Basic Auth + vanilla UI: queue, previews, stats, config) | done, typecheck + vitest | |
| `outreach/` (state machine, daily_queue, draft_email, lint_draft, gmail_drafts, scan_replies, advance, transition) | done | 61 |
| `deals/` | done | 13 |
| `scripts/` (run_metro, daily, doctor, fit_weights, sync_sheets) | done | test_scripts |
| `prompts/` (vision, extract_services, fuzzy_variables, 3 touch-1 variants, touches 2–4, classify_reply, CAN-SPAM checklist, LLM fixtures) | done | |
| `.github/workflows/prodcraft_medspa_ci.yml`, `prodcraft_medspa_replies.yml` (30-min reply scan, gated on repo var) | done | |

## Open items, in order (this is the work the next context does)

1. **Cross-package fixture alignment (blocking the gap-free claim).** `scripts/run_metro.py --mock` runs clean but the
   data does not flow: discovery's fixture hosts (`example-medspa-glow.test`, `-northshore`, …) are not in
   `audit/fixtures/mock_map.json` (which uses `example-medspa-01..20.test`), so every sampled site scores 100 as
   "no website"; `enrich/fixtures/*` are keyed on the `-01..` domains too, so all businesses fall to
   `generic_inbox` with `email_status=unknown`; preview then builds 0. Fix: make discovery's fixture the canonical
   synthetic dataset and re-key `audit/fixtures/mock_map.json`, `enrich/fixtures/contact_pages/*`,
   `enrich/fixtures/millionverifier/results.json`, `apollo/`, `findymail/`, `hunter/`, `gbp_reviews/` to those
   hosts and names. Target mock funnel: 22 found → 16 kept → 16 audited → ~6 qualified → ~5 owner found →
   ~4 verified → ~4 previews built → daily_queue shows them. Keep every package's own tests green.
2. **`run_metro.py` stage selection bug.** `--sample-n N` replaces the full audit with `sample_audit` (only N rows
   audited, rest `not_yet_audited`). It must run `audit.audit_site` always and `audit.sample_audit` additionally
   when `--sample-n` is given (sample_audit only writes `metro_stats`).
3. **Store boundary refactor (Cherny lens).** Add `list_rows(table, **filters, order_by=, descending=, limit=)`,
   `get_row`, `update_row`, `list_previews(business_id)`, `list_outreach(business_id)` to the `Store` Protocol and
   both implementations; refactor callers so this grep is empty:
   `grep -rln "_read(\|_request(" execution/personal_workflows/prodcraft_medspa --include=*.py | grep -v common/store.py`
   (currently: sync_sheets, fit_weights, run_metro, outreach/_store_helpers, db/apply_schema, preview/{takedown,
   publish,build_preview,r2}). Add contract tests; update CONTRACTS.md. (An agent was assigned this and was killed
   by a rate limit before editing anything.)
4. **Template visual fixes (partially done, interrupted by rate limit).** Done: watermark bar wraps on mobile
   (`components/WatermarkBar.tsx`), footer "Remove this preview" link. Not verified: `scripts/gen-stock.mjs` was
   rewritten for richer hero art, but the mobile screenshot has not been re-inspected (regenerate with
   `npm run gen-stock && npm run build && python3 tests/prodcraft_medspa/acceptance_template.py`, then look at
   `.tmp/prodcraft_medspa/acceptance/mobile-390x844.png`; the old hero read as an empty pale box). Not done:
   `package.json` `build` must run `gen-stock` (idempotent) before `next build` because `public/stock/*.png` is
   gitignored; add an acceptance assertion that the full watermark sentence is in the bar's innerText and that the
   sticky mobile bar does not cover the footer remove link.
5. **Directive reconciliation.** `preview.extend` has no module; the CLI is `python3 -m ...preview.publish extend
   --preview-id ID --days 30`. Update the directive's Steps. Then `python3 execution/generate_registry.py`.
6. **Audit stack before any "done" claim** (mandatory): spawn `pipeline-auditor` (Fable) on the mock funnel numbers
   vs. fixtures, `code-reviewer` (Opus) on the diff, and the six panel lenses as real sub-agents, each ending with
   Honest gaps. Fix findings. Then run `/test-suite`.
7. **Operator-only (cannot be done in cloud, no secrets):** create Supabase project and run `db/schema.sql`; create
   R2 bucket + KV namespace, set Worker secrets, deploy Worker, wildcard DNS `*.preview.prodcraft.fyi`; deploy
   dashboard with Basic Auth secrets; Gmail OAuth token; Telegram error channel (`notify.py --sample`); set the
   GitHub repo var `PRODCRAFT_CRON_ENABLED=true` and the secrets named in the workflow; then
   `python3 execution/personal_workflows/prodcraft_medspa/scripts/doctor.py --live` must be green before the
   first real `run_metro.py --metro chicago_north_shore`.

## Commands that must stay green

```
python3 -m pytest tests/prodcraft_medspa -q
cd execution/personal_workflows/prodcraft_medspa/preview/worker && npm test && npm run typecheck
cd execution/personal_workflows/prodcraft_medspa/dashboard && npm test && npm run typecheck
cd execution/personal_workflows/prodcraft_medspa/template && npm run typecheck && npm test && npm run build
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/prodcraft_medspa/acceptance_template.py
R=.tmp/prodcraft_medspa/x/store; python3 execution/personal_workflows/prodcraft_medspa/db/apply_schema.py --store local --root $R \
  && python3 execution/personal_workflows/prodcraft_medspa/scripts/run_metro.py --metro chicago_north_shore --mock --store local --store-root $R \
  && python3 execution/personal_workflows/prodcraft_medspa/scripts/daily.py --mock --store local --store-root $R
```

## Session constraints learned

- Cloud env: Python 3.11, Node 22, Chromium at `/opt/pw-browsers` (do not `playwright install`), no pipeline
  secrets; the `safety-guard` hook blocks `rm -rf` (use fresh `.tmp` subdirs instead).
- Parallel Sonnet sub-agents hit the account's session limit after ~10 concurrent long builds; run at most 3–4 at a
  time and commit after each lands.
- Template stock images are procedurally generated (no downloaded photos, licensing-clean); they are gitignored
  and must be regenerated at build time.
