# Job Search Sheet v2 (directive)

**Paired script:** [execution/personal_workflows/job_search_v2/](../../execution/personal_workflows/job_search_v2/)
**Replaces:** `execution/personal_workflows/job_search_sheet.py` (v1) — see [JOB_SEARCH_SHEET_AUDIT.md](../../JOB_SEARCH_SHEET_AUDIT.md) for the v1 audit.
**Last synced to implementation:** 2026-09-01 (PM/PO-ONLY rework: engineer/consultant/freelance-builder roles removed end-to-end; scope = FR/BE/DE/PL/AT/LU + remote; tabs = PM / AI PM / PO / AI PO; automatic sheet-hygiene purge added to run.py).

---

## Goal

Produce a daily Google Sheet + one email of **genuinely relevant** jobs for Debanjan Mazumdar, scored against his real profile (below), with junk (wrong role / wrong language / wrong location / internship) filtered out BEFORE it reaches the sheet, and an unskippable acceptance gate that fails the run if any junk lands.

## Candidate profile — TWO tracks (single source of truth for the ranker)

**2026-09-01 operator rework: the scanner is PM/PO-ONLY.** The prior "Track B — Freelance AI Automation / Claude Code / React Native" identity is retired from this pipeline (it was the source of the "full stack AI engineer" noise the operator flagged). Extracted from CVs (`deliverables/cv_generic_pm/`, `deliverables/cv_ai_pm/`), LinkedIn, GitHub:

- **Track A — AI / Senior Product Manager (CDI).** AI PM / Senior/Lead/Principal/Staff/Group PM / Head of Product / Product Director, plus PM flavours: data, growth, technical, platform, functional. 15y, data-intensive, production GenAI (RAG, multi-agent, LLM evaluation, Claude/OpenAI, MCP).
- **Track B — Product Owner (CDI).** Product Owner / Senior Product Owner / AI Product Owner / Technical / Digital PO. Matches his Senior Data Product Owner (Pitney Bowes, Evolent) and Senior Technical Product Owner (Avaya) history.

**Hard constraints (operator-stated, enforced in code):**
- **Roles: Product Manager + Product Owner families ONLY.** Engineer / developer / consultant / advisor / architect / data-scientist roles are rejected at the title gate — however AI-flavoured the title ("Full Stack AI Engineer", "AI Consultant", "React Native Developer" are all `reject:not_relevant`).
- **Locations: France, Belgium, Germany, Poland, Austria, Luxembourg + remote.** Switzerland and the UK are now on the priority-reject list (a "Remote — Switzerland" row used to slip through the generic "remote" accept).
- **Language: English OR French only.** No German/Dutch/Italian/Spanish/Polish postings. (An English-language job *located* in DE/PL/AT is acceptable — the language gate, not the location gate, enforces this. Polish tell-words added 2026-09-01.)
- **Seniority:** no junior / intern / alternance / stagiaire / graduate. Plain "Product Manager"/"Product Owner" (no seniority marker) is acceptable — the ranker, not the filter, differentiates.
- **NOT his roles:** project manager / chef de projet, product *marketing* manager, pure data-analytics, any engineering role, cybersecurity, SEO, accounting (comptable), facilities, creative strategy.

---

## Inputs

- **env:** `FRANCE_TRAVAIL_CLIENT_ID/SECRET`, `GMAIL_SMTP_USER/APP_PASSWORD/NOTIFY_TO`, `SHEETS_SPREADSHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_PATH`, `GEMINI_API_KEY` (or Sheets-cell fallback, see below), optional `ANTHROPIC_API_KEY` (Sonnet rerank, gated on credit).
- **CLI flags** (run.py): `--mode {live,fixture}`, `--dry-run`, `--sources`, `--max-pages`, `--posted-within-days`, `--no-location-filter`, `--no-ranker`, `--no-sonnet-rerank`, `--max-digest-jobs`, `--min-hours-between-emails`, `--no-acceptance`.

## Tools / Scripts

- Orchestrator: `run.py`
- Sources: `sources/{france_travail,linkedin_guest_api,wttj_algolia,remoteok,weworkremotely,linkedin_gmail}.py` (live default) + dark/opt-in (`wttj,apec,indeed_gmail,hellowork_gmail,jobgether_gmail`)
- Normalizer + filters: `normalizer/{normalize,dedup,title_filter,location_filter,contract_filter,language_filter}.py`
- Ranker: `ranker/{score,rubric.md,sonnet_rerank}.py`
- Notifier: `notifier/{email,sheet,health_score}.py`
- Maintenance: `trim_sheet_columns.py`, `purge_irrelevant_rows.py`
- Acceptance gate: `tests/acceptance_job_search_v2.py`

---

## Prior art pass (2026-06-18, per `~/.claude/rules/prior-art-first.md`)

- **Public API:** LinkedIn jobs-guest (unauth), WTTJ Algolia (public referer-gated key), France Travail (OAuth2 REST), RemoteOK (`/api`, no auth), WeWorkRemotely (RSS). Cribbed from [sivad259-alt/job-scanner](https://github.com/sivad259-alt/job-scanner) (MIT) for the LinkedIn + WTTJ patterns.

---

## 5-layer architecture + filter pipeline

| Layer | Purpose | Files |
|---|---|---|
| 1. Sources | One adapter per origin → `list[SourceJob]`. | LIVE default: `france_travail`, `linkedin_guest_api`, `wttj_algolia`, `remoteok`, `weworkremotely`, `linkedin_gmail`. Dark/opt-in: `wttj`, `apec`, `*_gmail`. |
| 2. Normalize + FILTER | `SourceJob → NormalizedJob`, dedup, then 4 reject stages. | `normalize.py`, `dedup.py`, then **Stage 3.4 `title_filter`**, **3.5 `location_filter`**, **3.6 `contract_filter`**, **3.7 `language_filter`**. |
| 3. Ranker | Two-track A/B/C/SKIP scoring. | `ranker/score.py` (Gemini chunked + heuristic fallback), `ranker/rubric.md`, `ranker/sonnet_rerank.py` (gated on ANTHROPIC credit). |
| 4. Notifier | Sheet (per-role tabs + Top Matches + human Summary), email digest. | `notifier/sheet.py`, `notifier/email.py`, `notifier/health_score.py`. |
| 5. Acceptance gate | Unskippable output check; run exits non-zero on junk. | `tests/acceptance_job_search_v2.py` (Stage 5b in run.py). |

### Pipeline order (run.py main)
1. Fetch sources in parallel (per-source fault isolation).
2. `batch_normalize` (in-batch cross-source dedup via content_hash).
3. `filter_new` (persistent cross-day dedup, SQLite seen.db).
4. **3.4 title_filter** — RELEVANCE ALLOWLIST, **PM/PO-only since 2026-09-01**. Recall hardening (same date): a bare word-boundary "PO"/"PM" in the title is accepted (`accept:abbrev`) — FR ads abbreviate ("PO Data H/F") — UNLESS the title is also a project-manager hit ("Chef de Projet PM" stays rejected). Every rejected title+reason is kept in `stats.rejected_sample` (cap 300) → `pipeline_stats` → `run_log.jsonl` + the CI artifact, so a suspected missed job is auditable for 7 days, never invisible. A title must positively match a `RELEVANCE_ANCHORS` entry (Product Manager family, Product Owner family, or an AI-PM/AI-PO variant carrying the full "product manager"/"product owner" core) or it's rejected `not_relevant`. Engineer / consultant / advisor / automation / mobile anchors were REMOVED (they admitted "Full Stack AI Engineer" rows — the operator's 2026-09-01 complaint). Generic words alone ("consultant", "directeur", "engineer") do NOT pass. Also hard-rejects project-manager / internship / junior. Note: profile.json `targeted_titles` are UNIONED into this allowlist — keep profile.json PM/PO-only too, or the union re-opens the hole.
5. **3.5 location_filter** — accept FR + BE + DE + PL + AT + LU + remote; reject US/Canada/APAC/India/**Switzerland/UK**/etc. (CH/UK moved to priority-reject 2026-09-01 so "Remote — Switzerland" can't ride in on the generic "remote" accept.)
6. **3.6 contract_filter** — drop INTERNSHIP; drop UNKNOWN only when source is FR-aware AND location is FR (DE/BE/PL/AT/LU legitimately can't expose contract type).
7. **3.7 language_filter** — EN/FR only. Strips gender markers (m/w/d, H/F, M/W, all genders) before detection; deterministic tell-word screen (German/Dutch/Italian/Spanish/**Polish** stopwords) is authoritative for short titles; langdetect only allowed to REJECT when ≥60 chars (a real description) — short tell-free titles ACCEPT.
8. **3.7 ranker** → **3.75 sonnet_rerank** (gated) → **3.8 sort + cap to --max-digest-jobs** (default raised 25→60 on 2026-09-01: capped-out jobs are already in the dedup DB and NEVER resurface, and the 6-country scope can exceed 25/day — a too-low cap silently loses relevant jobs). Ranker recall floor: contract_fit bottoms at 0.2 (0.0 reserved for internships) so a mislabeled-contract PM/PO job lands in a low tier instead of being auto-SKIPped.
9. **3.9 sheet hygiene (2026-09-01)** — before appending, `purge_irrelevant_rows.purge_sheet()` removes any existing sheet row failing the CURRENT title/language gates and deletes the retired `AI Automation` / `AI Mobile` / `AI Process` / `AI Consultant` tabs. Self-healing: a filter-tightening cleans the live sheet on the next cron run instead of tripping the acceptance gate forever. Best-effort (logged warning on failure; acceptance stays the enforcer).
10. Notify: append to per-role tabs **PM / AI PM / PO / AI PO** (column-by-name), refresh Top Matches, refresh human Summary (with health score), send/lock email.
11. **5b acceptance gate** — runs `tests/acceptance_job_search_v2.py` via subprocess; run exits code 3 if any sheet row is junk.

---

## Ranker (two-track, `ranker/score.py` + `rubric.md`)

- **rubric.md** scores each job against Track A or Track B (whichever fits better), with per-track high-signal cues and hard-NO list.
- **Gemini path:** chunked batches of 80 (was a single 445-job call that timed out — "Server disconnected"), 7s between chunks (10 RPM free tier), per-chunk 3-retry with `gemini-2.5-flash` → `gemini-2.5-flash-lite` fallback. Retry markers include 503/500/INTERNAL/disconnected/timeout.
- **GEMINI key fallback:** if `GEMINI_API_KEY` not in env, reads `Summary!F1` of the sheet (stopgap because the workflow YAML that plumbs the secret is local-only pending PAT `workflow` scope — see Deployment drift).
- **Heuristic fallback** (when Gemini unavailable): two-track, `score = max(track_a, track_b)`. Track A wants CDI; Track B wants Freelance + freelance-tell words in description.
- **Sonnet rerank:** refines top-N; silently no-ops on missing key / low credit (currently 400 credit-low — auto-activates on top-up).

## Notifier

- **sheet.py** — column-by-NAME writer (survives column reorder). Per-role tabs: `Company, Title, Country, Location, Contract, Link`. Top Matches: `Fit, Title, Company, Location, Contract, Source Tab, Link`. **Summary tab is HUMAN-READABLE** (2026-06-24): STATUS + health score, TODAY (new/added/strong/where), FILTERED OUT (and why, plain words), SOURCES, NEEDS ATTENTION (real issues only), all-time totals, then a compact technical footer. Preserves `D1` (email-lock state) and `F1` (GEMINI fallback key).
- **email.py** — short dashboard digest (~14 lines): per-source, tier breakdown, top-5 picks, sheet link. Subject: `Job Search — N new jobs for YYYY-MM-DD`. **Triple email lock** (run.py): state in Sheets `Summary!D1` → seen.db meta → local file; any one answers the dual-cron dedup so only ONE email/day even if the cache key is broken.
- **health_score.py** — 0-100 outcome-focused score: match_quality 35% (A/B ratio among post-filter ranked), strong_volume 25%, relevance_guard 15% (gate active = healthy; high block count is GOOD not bad), coverage 15%, freshness 5%, delivery 5%. Confidence HIGH/MED/LOW from sample≥50 + fresh<25h + sources≥3. **Measures output quality, NOT filter pass-rates** — a high rejection rate is the filters working, not a problem.

---

## New sources (2026-06-24)

### RemoteOK (`sources/remoteok.py`)
- `GET https://remoteok.com/api` (no auth, send identifying User-Agent). Filters to PM/AI/automation/engineering tags + title substrings, maps to SourceJob. ~10-20 relevant/day after location filter.

### WeWorkRemotely (`sources/weworkremotely.py`)
- RSS feeds (product / programming / devops). No auth. Titles often "Company: Role" — split on colon. ~5-15 relevant/day.

(France Travail / LinkedIn jobs-guest / WTTJ Algolia / *_gmail source notes unchanged — see git history of this directive pre-2026-06-24 for the full per-source ingest details.)

### Keyword sets (PM/PO-only as of 2026-09-01; EN/FR only since 2026-06-24)
All source keyword sets (`linkedin_guest_api`, `wttj_algolia`, `hellowork`) now carry ONLY PM/PO terms: product manager / senior product manager / AI product manager / product owner / senior product owner / head of product / chef de produit / responsable produit. Engineer/consultant/builder keywords (AI engineer, AI automation, claude code, react native, consultant IA…) were REMOVED — they were the source of the full-stack-AI-engineer noise. `france_travail` now runs 3 queries (product manager / product owner / chef de produit) France-wide (was: 1 query, Paris dept 75). `linkedin_guest_api` fans out over 6 geoIds (FR country-wide, DE, BE, PL, AT, LU — CH dropped, IDF widened to FR). `wttj_algolia` queries country codes FR/BE/DE/LU/AT/PL. `remoteok` matches only product tags/titles; `weworkremotely` reads only the remote-product-jobs feed (programming + devops feeds dropped).

---

## Acceptance gate (the "is this shippable?" definition) — 2026-06-24

`tests/acceptance_job_search_v2.py` is the single shippability gate. Two layers:

1. **Frozen regression corpus** (no sheet needed; independent of pipeline logic): the operator's exact 19 flagged-wrong titles (+ 2 German) MUST classify as reject; 12 known-good (incl. langdetect false-positives like "Staff AI Engineer - M/W") MUST classify as keep. Guards against silently weakening the gate.
2. **Live-sheet check:** reads EVERY row in every role tab + Top Matches; HARD-FAILS if any row is irrelevant / non-EN-FR / out-of-scope-location / broken-link. Reuses the pipeline's own `classify_title`/`classify_language` (single source of truth).

**Wired into run.py Stage 5b** — a run producing junk exits code 3 (FAIL), recorded as `acceptance` in the run-log. Per `~/.claude/rules/front-door-synthetic.md`, needs **5 consecutive PASS runs** against the live cron before "shippable". Known limitation (shared oracle): the live check shares classifier code with the pipeline, so it catches regressions + known classes but NOT a brand-new junk class on first appearance — that becomes a new corpus entry once seen.

Maintenance scripts: `purge_irrelevant_rows.py` (removes existing sheet rows failing relevance+language), `trim_sheet_columns.py` (one-shot column migration).

---

## Cross-day dedup, Contracts

(Unchanged — SQLite seen.db, content_hash = sha256(title|company|canonical_url), TTL 60d. Pydantic v2 frozen contracts: SourceJob/NormalizedJob/RankedJob + enums incl. new JobSource.REMOTEOK / WEWORKREMOTELY.)

---

## Deployment drift (gap, documented per 2026-06-24 honesty pass)

**The workflow YAML at origin diverges from intent.** Two fixes are committed LOCALLY only and cannot be pushed — the operator's PAT lacks `workflow` scope (rejected by `git push`, Contents API, and Git Data API ref-update):
- single 07:00 UTC cron (collapse dual-fire)
- plumb `GEMINI_API_KEY` + fix the dead `$(date)` cache key

**Mitigations already in place at the app layer** so prod is not broken by the drift:
- Dual-email → neutralized by the triple email lock (Sheets D1 survives the broken cache key).
- Missing GEMINI in cron env → neutralized by the `Summary!F1` key fallback.

**Full closure requires one operator action:** `gh auth refresh -s workflow,repo`, then ask to push. Until then, status is "documented + app-layer-mitigated", not "resolved".

---

## Edge cases / known constraints

- **Gemini 503:** Google-side outages happen; chunked retry → heuristic fallback keeps the dashboard populated. `ranker_model=heuristic` in the run-log signals this.
- **langdetect on short titles** is unreliable — handled by the gender-marker strip + tell-word-first + 60-char threshold (see language_filter). Regression corpus pins the known false-positives.
- **Don't run the live pipeline >2-3×/session** — LinkedIn jobs-guest starts 999-blocking on repeated identical fetches.
- **Windows cp1252:** run.py spawns the acceptance test via subprocess with `encoding="utf-8", errors="replace"`. Any new subprocess must do the same.
- **OneDrive + SQLite:** seen.db is under OneDrive; opened autocommit to avoid lock races.
- **eval_gold_set.json drift (2026-09-01):** `tests/fixtures/eval_gold_set.json` still contains Track-B-freelance items from the pre-rework profile. It is only consumed by the manual `tests/eval_ranker_precision.py` (needs GEMINI key, not in cron/CI). Regenerate with `profile/generate_eval_set.py` (prompt already updated to PM/PO) before the next precision eval.
- **Cron runs `main`:** `.github/workflows/job_search_daily.yml` checks out the default branch. The PM/PO rework takes effect on the live cron only after the `claude/job-scanner-cron-filter-jjihia` branch is merged to main. The first post-merge run auto-purges the sheet's stale engineer rows and deletes the 4 retired tabs (Stage 3.9).

---

## Exit Criteria (current)

- `tests/acceptance_job_search_v2.py` passes **5 consecutive runs against the live cron** (run-log `acceptance=PASS`). Currently run 1/5.
- Frozen regression corpus stays green (no gate weakening).
- ≥2 sources contribute and `total_fetched ≥ 5` per run (per fixture-synthetic-≠-green rule).
- Email digest sends exactly once/day (triple lock).
- No row in any role tab or Top Matches is irrelevant / non-EN-FR / out-of-scope (the acceptance gate enforces this).

## Verification commands

```bash
# Acceptance gate (the shippability check)
py tests/acceptance_job_search_v2.py

# Full live run (acceptance gate runs automatically at the end; exits 3 on junk)
py execution/personal_workflows/job_search_v2/run.py --mode live --max-pages 1

# Comprehensive synthetic (8 live-sheet dimensions)
py tests/comprehensive_synthetic_job_search_v2.py

# Clean existing junk from the sheet
py execution/personal_workflows/job_search_v2/purge_irrelevant_rows.py --dry-run
```
