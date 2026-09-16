# ProdCraft med-spa pipeline, handoff (2026-09-16, session 2, round 2)

Branch: `claude/mobile-responsive-website-gup5d2` (all work committed and pushed; see `git log`).
Spec: `PROJECT_SPEC.md` (9.1 guarantee evidence clause is new). Build contracts: `CONTRACTS.md`. Panel roster
(eleven mandatory lenses, operator standing order): `.claude/memory/panel_roster.md`. Audit records:
`docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`, `docs/audits/prodcraft_medspa_audit_stack_2026-09-16.md`
(round 1 and round 2). Directive: `directives/personal_workflows/prodcraft_medspa_pipeline.md` (has the verbatim
"secrets set -> first live 5 sent" command block).

## State: the loop is automated end to end; only secrets and one config flag separate it from a real send

What runs unattended once armed (`.github/workflows/`):
- `prodcraft_medspa_daily.yml` (daily 14:00 UTC): install deps + Playwright Chromium -> `doctor.py --live`
  pre-check -> `run_metro.py` (discover or import, audit, enrich, preview) -> `preview_gate.py` (acceptance checks;
  approves only when `auto_approve_previews` is true) -> `daily.py` (advance, queue, draft, lint, **send**, scan) ->
  `sync_sheets.py` (always) -> Telegram on failure or cancel. Per-step timeouts, ~30-45 min expected.
- `prodcraft_medspa_replies.yml` (every 30 min): advance -> scan replies -> classify -> Telegram on positive,
  neutral and remove -> takedown on remove and on negative.
- `prodcraft_medspa_weekly.yml` (Monday 15:00 UTC): `fit_weights.py --report-telegram` (or "not enough data yet").

Guards that stand between the cron and a real prospect, in order: `PRODCRAFT_CRON_ENABLED`; doctor pre-check
(sender postal address must be real, R2 keys, Gmail send scope); config validation (`common/config_validate.py`,
fails loudly); `PRODCRAFT_RECIPIENT_OVERRIDE` (every send goes to you with a `[TEST to ...]` subject);
`live_send_confirmed` (false until `send.py --confirm-live-sends`); preview host guard (live sends refuse previews
that are not on `*.preview.prodcraft.fyi`); CAN-SPAM lint with placeholder-address rejection; warmup ramp
(2/day rising to `phase0.cap` over 14 days from the first live send); Phase 0 cap and 2 percent bounce halt.

## Live first-5 dry run (done in-session with connectors, no prospect emailed)

Store: `.tmp/prodcraft_medspa/live/store1` (gitignored). Nine real North Shore spas imported from a CSV built by
web search (`discovery/import_csv.py`), audited in degraded mode (no PSI, vision or screenshots), enriched with
`email_policy allow_unverified`, five previews built and hosted as private claude.ai artifacts, five emails sent
via the Gmail connector to the operator's address (message ids on the rows, `sent_via gmail_connector_session`),
both sheet tabs mirrored. After the round-2 audit the four spas above the new `min_score 25` floor were rebuilt on
template v2 and republished to the same artifact URLs (Version 4); all store patches were logged as
`manual_patch` events and the nine pre-fix audit rows flagged `superseded`.

Template v2 (operator request: no static 2010s brochure): scroll-scrubbed hero with four numbered states built
from each spa's data, sticky fanning service cards, a "Your visit" step drum, proof strip or honest hours fallback,
one opt-out sentence matching the email. Pure CSS + a single rAF scroll handler, reduced-motion and no-JS
fallbacks, acceptance checks for hero states, folio transforms and the fallback.

## Commands that must stay green

```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 -m pytest tests/prodcraft_medspa -q
cd execution/personal_workflows/prodcraft_medspa/template && npm test && npm run typecheck && npm run build
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/prodcraft_medspa/acceptance_template.py
cd execution/personal_workflows/prodcraft_medspa/preview/worker && npm test && npm run typecheck
cd execution/personal_workflows/prodcraft_medspa/dashboard && npm test && npm run typecheck
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers bash tests/prodcraft_medspa/test_suite_tiers.sh
R=.tmp/prodcraft_medspa/x/store
python3 execution/personal_workflows/prodcraft_medspa/db/apply_schema.py --store local --root $R
python3 execution/personal_workflows/prodcraft_medspa/scripts/run_metro.py --metro chicago_north_shore --mock --store local --store-root $R --auto-approve
python3 execution/personal_workflows/prodcraft_medspa/scripts/daily.py --mock --store local --store-root $R --recipient-override t@example.test
```
Mock chain DoD: 22 found -> 16 kept -> 16 audited -> 6 qualified -> 4 verified -> 4 previews -> 4 approved ->
4 drafted -> **4 sent** (mock .eml under `.tmp/prodcraft_medspa/sent/`); a second `daily.py` run sends 0.
Without `--recipient-override`, `daily.py --mock` sends 0 and reports `live_send_not_confirmed` by design.
Last full run this session: pytest 638 passed / 35 skipped (about 115 s); vitest 29; typecheck, build and
acceptance clean; `test_suite_tiers.sh` ALL CHECKS PASSED (pytest threshold raised to 180 s for the larger suite).
Never run two `run_metro`/`build_preview` processes
against the same checkout at once; the build lock serializes them.

## Honest gaps (open after round 2)

- **No live path has run from code.** Places, PSI, Anthropic, Gmail OAuth, Telegram, Supabase (migrations 0003 and
  0004 unapplied), R2 and the Worker are all verified from fixtures and monkeypatched seams; connectors stood in
  for them during the dry run. First live run happens on the operator's machine after `doctor.py --live` is green.
- **Degraded mode is the common case today**, not the edge: without PSI, vision and screenshots at most 40-60 of
  100 points are measurable and every real site scored 22-33. `audits.mode` now records this and `fit_weights`
  defaults to full-mode rows, but the first real audits must run with PSI and Anthropic keys before any score is
  trusted.
- **Hours and reviews were unknown for 5 of 5 live spas** (no Places details in cloud); the template falls back
  honestly, but a real send should carry real hours.
- **Legal question, not a code fix**: publishing a look-alike site using a business's name and re-displaying Places
  data before consent, plus Illinois PIPA / CCPA exposure for scraped owner PII. Retention policy and purge path
  exist; the operator should confirm the approach with counsel before the first real send.
- **Reply classifier has no gold set**; the keyword mock mirrors the prompt but live LLM labels are unmeasured.
  Every remove is now Telegram-notified so mis-classifications are visible.
- **Sample Telegram send never observed** (no token in cloud); the error channel is not "wired up" by the rule in
  `automation-boundaries.md` until the operator sees one.
- **Copy decisions left to the operator**: CTA softness, subject-line variety, proof lines (none until a founding
  client yields a before/after number).
- `scan_replies` takes a negative reply's preview down through `take_down_preview` and then reverts the
  `do_not_contact` flag that helper sets; a `dnc=False` parameter on the helper would be the clean fix.
- Prompts and README/CONTRACTS prose contain em-dashes; customer-facing email text contains none (checked for U+2014).

## 7. Operator-only (cannot be done in cloud, no secrets)

- Supabase project; `db/apply_schema.py --store supabase` (schema.sql includes migrations 0001-0004).
- R2 bucket + KV namespace + Worker secrets + `npm run deploy`; **R2 S3 API token** -> `R2_ACCESS_KEY_ID`,
  `R2_SECRET_ACCESS_KEY`; wildcard DNS `*.preview.prodcraft.fyi`; dashboard with Basic Auth secrets.
- Gmail OAuth token with `gmail.send` scope on the aged Workspace inbox; SPF/DKIM/DMARC on the sending domain
  (`doctor.py --live` reports SPF/DMARC best-effort).
- Telegram bot token + chat id; run `notify --sample` and confirm receipt.
- Google Places, PageSpeed, Anthropic, Apollo/Findymail/MillionVerifier keys (enrich degrades without them).
- `config.sender` with a **real street address** (the lint now rejects placeholders such as "operator to confirm").
- Decide `auto_approve_previews` (default false: you approve in the dashboard or `preview/approve.py`).
- Then the verbatim block in the directive: `doctor --live` -> `run_metro` -> approve or gate -> `daily.py
  --recipient-override you@...` -> read every email -> `send.py --confirm-live-sends` -> clear the override ->
  `PRODCRAFT_CRON_ENABLED=true`.

## Session constraints learned

- Cloud env: Python 3.11, Node 22, Chromium at `/opt/pw-browsers` (never `playwright install`), no pipeline
  secrets; the safety hook blocks `rm -rf`; `pip install -r execution/personal_workflows/prodcraft_medspa/requirements.txt`
  and `npm ci` in the three Node packages are needed in a fresh container.
- Sub-agents: at most 3-4 concurrent; a 429 session limit killed workers twice (work on disk survives; respawn with
  the same brief). Workers must own disjoint files; a mid-task message from the coordinator can be mistaken for
  injected content, so give every worker its full brief up front.
- Artifact hosting of a Next.js export needs `_next` -> `nx`, manifests without a leading underscore, the polyfills
  chunk dropped, and every asset path relative (including inside the RSC payload, hence the Hero fix ee8041f).
