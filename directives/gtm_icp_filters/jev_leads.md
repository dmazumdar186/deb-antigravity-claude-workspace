# Jev Leads

**Script:** `execution/gtm_icp_filters/jev_leads.py` (skill `/jev-leads`; playbook `docs/reference/jev_leads_playbook.md`)

## Goal

Put a typed Jev gate (yes/no, choice, score) at every if/then step of the lead pipeline so only clean, non-suppressed, in-ICP, well-timed leads reach enrichment and Instantly, and replies/inbound forms are routed without an LLM. Jev gates; Claude generates copy; deterministic scripts move data. Replaces the Anthropic batch step of the classify-leads skill for qualification.

## Inputs

- Positional scenario: `qualify | signals | hygiene | suppress | replies | inbound | diff | factcheck | message_score`. `factcheck`/`message_score` are pre-send gates for Instantly copy: rows need a `draft` column (the first line / full message).
- `--input` CSV or JSON (lead rows; for replies/inbound, message rows with body/subject/from/form_fields).
- `--icp` JSON profile: copy `execution/gtm_icp_filters/icp_profiles/_template.json` (example: `example_b2b_saas.json`). Fields: offer, icp, personas, exclusions, timing, signals, customers, competitors. Optional `fit_weights` (default role_fit .35, likely_buyer .3, company_fit .25, seniority .1) and `fit_cutoffs` (`{"go": 70, "hold": 45}`). Keep it under ~400 tokens of prose. Ask the operator once for offer/ICP if unknown.
- `--min-confidence` (0.6), `--workers` (8), `--limit`, `--dry-run`, `--only-pass`, `--validate labels.csv` (`id,label`), `--snapshot` (diff only), `--output`, `--csv-out`, `--md`.
- `--fields a,b,c`: columns sent to Jev (default per-scenario allowlist in `DEFAULT_FIELDS`; phone/mobile/address/street/notes/linkedin_url are always dropped; linkedin_url is used locally for diff matching only).
- `--cache PATH` (default `.tmp/jev_leads_cache.json`, `none` disables): answers keyed by sha1(scenario, QUESTION_VERSION, ICP hash, sent fields); qualify/suppress/signals keys exclude name/email so the same title+company+context is asked once.
- env `OPENROUTER_API_KEY` (exit 2 if missing, unless `--dry-run`).

## Tools/Scripts

- Sourcing: scrape-leads skill (Apify `code_crafter/leads-finder` → `.tmp/*.json`), gmaps-leads skill, `execution/lead_sourcing/serper_maps_scraper.py`, `prospeo_leads.py`, `fr_instructor_finder.py` (has its own inline Jev classify), `instantly_lead_cleaner.py`.
- Enrichment (go rows only): `execution/enrichment/email_mx_verify.py` (keyless), `casualize_and_city_split.py`; `anymailfinder_lookup.py` and `million_verifier.py` are AM-locked: explicit operator go-ahead per run.
- Delivery: instantly-campaigns skill, `execution/google/google_sheets_writer.py`.
- Replies: `execution/modules/outputs/instantly.py` `fetch_replies` → JSON → `replies` scenario; instantly-autoreply skill drafts answers for `interested`/`question` rows.
- Validation: `execution/infrastructure/jev_validate.py` + `execution/modules/jev_eval.py`, spec `execution/infrastructure/jev_specs/lead_qualify.json`.
- Shared client: `execution/modules/jev_client.py`. Sibling scripts: `jev_comment_buyers.py`, `jev_customer_health.py`, `jev_recruitment_icp_filter.py`.

## Steps

1. Build or reuse the ICP profile.
2. `--dry-run` on the new file; read the printed state and questions.
3. `hygiene` → drop `drop` rows; fix `fix` rows with casualize_and_city_split.py or by hand.
4. `suppress` → remove `suppress` rows.
5. `qualify --only-pass` → `go` rows continue; `hold` rows go to a person or Claude; `skip` rows stop.
6. Enrich go rows; then `signals` to order outreach (`contact` first, `watch` later).
7. Push to Instantly / Sheet. Never send a `hold` or `review` row.
8. Standalone: `replies` hourly on fetch_replies output; `inbound` per form submission; `diff` monthly on a LinkedIn connections export vs last snapshot (save the new export as next month's snapshot).
9. First run per client: label 30-100 rows, run `--validate`, sweep thresholds with jev_validate.py, record the chosen `--min-confidence` in the Run log.

## Outputs

- JSON `{summary, rows, validation}`; summary has decisions per label, cost_usd, wall_s, errors, partial, review, cache_hits, model.
- qualify adds `jev_fit` (0-100 weighted mean of role_fit, likely_buyer, company_fit, seniority/4): `go` also needs fit >= cutoffs.go; fit >= cutoffs.hold prevents `skip`; `--md` sorts by fit. Rows get `jev_cached`; diff rows get `jev_diff` (new/changed).
- Decisions: signals/diff use recipe-02 `new_budget_owner`/`current_role_buys` (diff ignores `same_job_reworded`/`none`); replies `remove_request` >= minc forces `unsubscribe`; factcheck send|fix|block; message_score send|revise.
- `--csv-out`: all input columns plus `jev_*` (decision, per-question values, `_conf`, `jev_confidence`, `jev_review`, `jev_error`). `--md`: top-25 table.
- Ledger row in `.tmp/jev_ledger.jsonl` (`caller: jev_leads`).

## Edge cases

- **Partial answers:** any expected question missing from Jev's answers sets `jev_review=True`, `jev_error=partial_answer:<names>` (never a silent 0). `hold` rows are always `jev_review`.
- **Cache:** bump `QUESTION_VERSION` in the script whenever questions change; delete the cache file to force fresh answers.
- **Fail-open rows:** a failed call sets `jev_review=True` and `jev_error`; the row is never auto-sent, never silently dropped. Errors >5% of rows: stop and inspect.
- **429:** per-org rate limits (reported 40-80 req/s, figures conflict). `jev_client.decide` sleeps min(retry-after or 1 s, 5 s) and retries once, then fails open; keep `--workers 8`; batch questions per row in one call rather than splitting.
- **Long-context danger zone:** ~64k tokens/request, ~32k per question; fields are capped at 1,200 chars. Irrelevant context lowers accuracy: send only fields the scenario needs.
- **Thin context:** a bare title gives guesses (a 78-issue thin-context test matched only ~10 labels). Enrich before qualify.
- **Model pin:** client pins jev-1.13; jev-1.14 shipped 2026-10-14 (`~typesafe/jev-latest` alias). Re-validate on the labelled set before moving; never use the alias in production.
- **Threshold tuning:** no published calibration. Default 0.6 is a starting point; re-sweep when hold rate moves >10 points or validated accuracy drops.
- **PII:** prompt text goes to OpenRouter then TypeSafe. Send name/title/company only; no phone, address or notes from confidential lists. Confidential list: do not run, or strip to company-level fields.
- Multistep reasoning and numeric precision are weak spots: compute numbers (headcount bands, funding dates) in code and pass the result.

## Run log

- 2026-10-16: second pass: PII allowlist (`--fields`), partial-answer review, multi-key diff, 429 retry, 0-100 fit, cookbook timing/reply questions, cache, factcheck + message_score.
- 2026-10-16: built (script, skill, directive, playbook). Thresholds not yet validated on a labelled set.
