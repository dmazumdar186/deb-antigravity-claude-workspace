# Job Search Sheet v2 (directive)

**Paired script:** [execution/personal_workflows/job_search_v2/](../../execution/personal_workflows/job_search_v2/)
**Replaces:** `execution/personal_workflows/job_search_sheet.py` (v1) — see [JOB_SEARCH_SHEET_AUDIT.md](../../JOB_SEARCH_SHEET_AUDIT.md) for the v1 audit.
**Last synced to implementation:** 2026-09-10 (dedup hardening + domain filter + posting verifier, driven by 3 operator complaints: duplicate rows, ≥50% expired/closed/stale rows, hardware-domain PM/PO roles leaking through). Prior sync: 2026-09-01 (PM/PO-ONLY rework: engineer/consultant/freelance-builder roles removed end-to-end; scope = FR/BE/DE/PL/AT/LU + remote; tabs = PM / AI PM / PO / AI PO; automatic sheet-hygiene purge added to run.py).

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
- **CLI flags** (run.py): `--mode {live,fixture}`, `--dry-run`, `--sources`, `--max-pages`, `--posted-within-days`, `--no-location-filter`, `--no-ranker`, `--no-sonnet-rerank`, `--sonnet-rerank-top-n`, `--max-digest-jobs`, `--min-hours-between-emails`, `--no-acceptance`, `--no-verify` (skip Stage 3.8 posting verification, debugging only), `--max-age-days` (Stage 3.8 freshness window override; default from config `verification.max_age_days`, 7).
- **CLI flags** (`purge_irrelevant_rows.py`): `--dry-run`, `--tabs`, `--keep-obsolete-tabs`, `--dedup/--no-dedup` (default on), `--reverify/--no-reverify` (default on), `--max-age-days` (default 7), `--reverify-max-fetches` (default 400).
- **config** (`config/job_search_v2.json`): new `verification` block — `enabled`, `max_age_days` (7), `concurrency` (8).
- **profile.json:** new `domain_scope` (free text, software-only scope statement) and `hard_filters.skip_domain_anchors` (list of extra hardware-domain substrings unioned into `domain_filter.HARDWARE_TITLE_ANCHORS`).

## Tools / Scripts

- Orchestrator: `run.py`
- Sources: `sources/{france_travail,linkedin_guest_api,wttj_algolia,remoteok,weworkremotely,linkedin_gmail}.py` (live default) + dark/opt-in (`wttj,apec,indeed_gmail,hellowork_gmail,jobgether_gmail`)
- Normalizer + filters: `normalizer/{normalize,dedup,title_filter,location_filter,contract_filter,language_filter,domain_filter,posting_verifier}.py`
- Contracts: `contracts.py` — `compute_fingerprint`, `NormalizedJob.fingerprint`, `canonicalize_url`.
- Ranker: `ranker/{score,rubric.md,sonnet_rerank}.py`
- Notifier: `notifier/{email,sheet,health_score}.py`
- Maintenance: `trim_sheet_columns.py`, `purge_irrelevant_rows.py` (dedup + domain purge + reverify, see Stage 3.9)
- Acceptance gate: `tests/acceptance_job_search_v2.py`

---

## Prior art pass (2026-06-18, per `~/.claude/rules/prior-art-first.md`)

- **Public API:** LinkedIn jobs-guest (unauth), WTTJ Algolia (public referer-gated key), France Travail (OAuth2 REST), RemoteOK (`/api`, no auth), WeWorkRemotely (RSS). Cribbed from [sivad259-alt/job-scanner](https://github.com/sivad259-alt/job-scanner) (MIT) for the LinkedIn + WTTJ patterns.

---

## 5-layer architecture + filter pipeline

| Layer | Purpose | Files |
|---|---|---|
| 1. Sources | One adapter per origin → `list[SourceJob]`. | LIVE default: `france_travail`, `linkedin_guest_api`, `wttj_algolia`, `remoteok`, `weworkremotely`, `linkedin_gmail`. Dark/opt-in: `wttj`, `apec`, `*_gmail`. |
| 2. Normalize + FILTER | `SourceJob → NormalizedJob`, dedup, then 6 reject stages. | `normalize.py`, `dedup.py`, then **Stage 3.4 `title_filter`**, **3.5 `location_filter`**, **3.6 `contract_filter`**, **3.7 `language_filter`**, **3.75 `domain_filter`**, **3.8 `posting_verifier`**. |
| 3. Ranker | Two-track A/B/C/SKIP scoring. | `ranker/score.py` (Gemini chunked + heuristic fallback), `ranker/rubric.md`, `ranker/sonnet_rerank.py` (gated on ANTHROPIC credit). |
| 4. Notifier | Sheet (per-role tabs + Top Matches + human Summary), email digest. | `notifier/sheet.py`, `notifier/email.py`, `notifier/health_score.py`. |
| 5. Acceptance gate | Unskippable output check; run exits non-zero on junk. | `tests/acceptance_job_search_v2.py` (Stage 5b in run.py). |

### Pipeline order (run.py main)
1. Fetch sources in parallel (per-source fault isolation).
2. `batch_normalize` — SourceJob → NormalizedJob, **in-batch cross-source dedup by content_hash OR fingerprint** (2026-09-10: `_merge_into` backfills `also_seen_on`/posted_at/description from the merged dupe; first occurrence wins as the surviving record). Live 2026-09-10 smoke: 565 source jobs → 424 after this stage (141 cross-source duplicates collapsed).
3. `filter_new` — persistent cross-day dedup, SQLite seen.db, now matches on content_hash **OR fingerprint** (stats key `already_seen_by_fingerprint`; a `fingerprint` column + index was added via in-place `ALTER TABLE` migration so pre-existing DBs don't need `--reset`).
4. **3.4 title_filter** — RELEVANCE ALLOWLIST, **PM/PO-only since 2026-09-01**. Recall hardening (same date): a bare word-boundary "PO"/"PM" in the title is accepted (`accept:abbrev`) — FR ads abbreviate ("PO Data H/F") — UNLESS the title is also a project-manager hit ("Chef de Projet PM" stays rejected). Every rejected title+reason is kept in `stats.rejected_sample` (cap 300) → `pipeline_stats` → `run_log.jsonl` + the CI artifact, so a suspected missed job is auditable for 7 days, never invisible. A title must positively match a `RELEVANCE_ANCHORS` entry (Product Manager family, Product Owner family, or an AI-PM/AI-PO variant carrying the full "product manager"/"product owner" core) or it's rejected `not_relevant`. Engineer / consultant / advisor / automation / mobile anchors were REMOVED (they admitted "Full Stack AI Engineer" rows — the operator's 2026-09-01 complaint). Generic words alone ("consultant", "directeur", "engineer") do NOT pass. Also hard-rejects project-manager / internship / junior. Note: profile.json `targeted_titles` are UNIONED into this allowlist — keep profile.json PM/PO-only too, or the union re-opens the hole.
5. **3.5 location_filter** — accept FR + BE + DE + PL + AT + LU + remote; reject US/Canada/APAC/India/**Switzerland/UK**/etc. (CH/UK moved to priority-reject 2026-09-01 so "Remote — Switzerland" can't ride in on the generic "remote" accept.)
6. **3.6 contract_filter** — drop INTERNSHIP; drop UNKNOWN only when source is FR-aware AND location is FR (DE/BE/PL/AT/LU legitimately can't expose contract type).
7. **3.7 language_filter** — EN/FR only. Strips gender markers (m/w/d, H/F, M/W, all genders) before detection; deterministic tell-word screen (German/Dutch/Italian/Spanish/**Polish** stopwords) is authoritative for short titles; langdetect only allowed to REJECT when ≥60 chars (a real description) — short tell-free titles ACCEPT.
8. **3.75 domain_filter (new 2026-09-10)** — rejects PM/PO titles for a **non-digital product**: hardware, electronics, instrumentation, semiconductors/microchips, embedded/firmware, systems software, mechanical, medical devices, automotive/avionics hardware, etc. Operator complaint: real PM titles like "Product Manager — Semiconductor Test Solutions" or "Chef de Produit Instrumentation" passed title_filter (correct role family) but are the wrong industry — the CV is software-only (B2B SaaS, retail tech, GenAI/LLM/RAG). Design (`classify_domain` in `normalizer/domain_filter.py`): any `HARDWARE_TITLE_ANCHORS` hit (or profile.json `hard_filters.skip_domain_anchors` extra anchor) in the TITLE is a hard reject. Title-only nuance: an anchor that is ambiguous in prose (`_DESC_AMBIGUOUS_ANCHORS`: sensor, instrumentation, optics, mechanical, battery, RF, radar/lidar, kernel, robotics, HVAC) is rescued when the same title also carries a software-product word (platform / SaaS / software / cloud / data / analytics / app / API / digital) — "Product Manager – Sensor Data Platform" → `ok_title_software_product`; unambiguous anchors (hardware, firmware, semiconductor, PCB, embedded systems…) are never rescued. In the DESCRIPTION, distinct hits are counted by MATCHED TEXT (a profile anchor that overlaps a built-in one — "medical device" — counts once; live 2026-09-10 bug: it counted twice and rejected an SaMD software role) and ambiguous anchors are ignored (Proton's "instrumentation … optics" false positive). ≥2 distinct hardware terms reject UNLESS the description is software-dominant (no core-requirement phrase AND either ≥3 `SOFTWARE_CONTEXT_ANCHORS` hits or at least as many software hits as hardware terms) — rescued as `ok_mixed_software_dominant`; exactly 1 distinct anchor only rejects if it coincides with a `_CORE_REQUIREMENT_PATTERNS` phrase (e.g. "background in electrical engineering"), otherwise it's an incidental mention and kept as `ok_incidental`. All EN+FR, accent-stripped, word-boundary regex. Rejected sample kept (cap 300) in `stats.rejected_sample` → `pipeline_stats.domain_filter`. Live 2026-09-10 smoke: 7 of 155 rejected (MedTech / hardware / embedded).
9. **3.8 posting_verifier (new 2026-09-10)** — opens every surviving job's OWN page (`normalizer/posting_verifier.py`, `verify_jobs`/`verify_job`) at `config.verification.concurrency` (default 8) and reads the REAL posted date + liveness, rather than trusting the source's own `posted_at`. Date sources checked in order: JSON-LD `JobPosting.datePosted` → meta/`<time>` tags → relative/absolute EN/FR text ("posted 3 days ago", "il y a 2 jours", "publiée le 12/09/2026"). Closed detection: HTTP 404/410; a redirect landing on a listing/search page (incl. LinkedIn's `expired_jd_redirect` query marker); an EN/FR "no longer accepting applications"-class phrase; a soft-404 body (HTTP 200 "Error 404 / Page not found", observed live on WTTJ); JSON-LD `validThrough` in the past. Decisions: `ok` (fresh + verified), `ok_unverified_fresh` (page fetch blocked but source date is trusted/fresh — FRANCE_TRAVAIL and `*_gmail` sources are trusted-by-default), `closed` (dropped), `stale` (page date older than `--max-age-days`/config default 7, dropped), `age_unknown` / `unverifiable_no_date` (no date found anywhere, dropped). One retry (3s backoff) on HTTP 429/503/202-with-empty-body (WTTJ's anti-bot challenge answers 202 with an empty body; the real page comes back on retry). Disabled automatically outside `--mode live` (fixture URLs are frozen snapshots) and via `--no-verify` (debugging only, never in the cron). Per-run `verification.jsonl` written to the run dir; `pipeline_stats` keys `verification`, `verification_rejected_sample`, `after_verification`. A warning is logged/surfaced when one host blocks ≥80% of ≥5 fetch attempts (`unverifiable_ratio_by_host`). Live 2026-09-10 smoke: 148 in → 135 kept, 13 stale dropped, ~35s wall time; weworkremotely.com blocked 100% of page fetches (rows kept on the feed's own pubDate, stamped "unverified (source date)").
10. **3.85 ranker** → Sonnet shortlist rerank (gated) → sort + cap to `--max-digest-jobs` (default raised 25→60 on 2026-09-01: capped-out jobs are already in the dedup DB and NEVER resurface, and the 6-country scope can exceed 25/day — a too-low cap silently loses relevant jobs). Ranker recall floor: contract_fit bottoms at 0.2 (0.0 reserved for internships) so a mislabeled-contract PM/PO job lands in a low tier instead of being auto-SKIPped.
11. **3.9 sheet hygiene** (2026-09-01, extended 2026-09-10) — before appending, `purge_irrelevant_rows.purge_sheet()` now runs FOUR passes: (a) removes any existing sheet row failing the CURRENT title/language/**domain** gates or whose Country/Location matches the config reject list (title-only purge previously left 175 historical Geneva rows behind, run 33534144028); (b) **`dedup_rows`** — cross-tab exact/fuzzy duplicate purge, union-find over shared `_id` / canonical Link / fingerprint across ALL role tabs, winner = highest-ranked of (has a Status set > earliest First Seen > lowest row index) so an operator's `Applied`/`Saved` edit is never silently discarded for an untouched duplicate; (c) **`reverify_rows`** — opens every UNSTAMPED historical row's Link (rows written before the Verified column existed) and removes closed/stale/undatable rows or stamps the survivors, bounded to `reverify_max_fetches` (default 400) per run so a large backlog drains over several cron runs instead of one giant fetch storm; a blocked host keeps its rows with an "unverified" stamp rather than wiping the sheet; (d) deletes the retired `AI Automation` / `AI Mobile` / `AI Process` / `AI Consultant` tabs. All four are self-healing: a filter-tightening or a freshness sweep cleans the live sheet on the next cron run instead of tripping the acceptance gate forever. Best-effort (logged warning on failure; acceptance stays the enforcer). CLI (`purge_irrelevant_rows.py`): `--dedup/--no-dedup`, `--reverify/--no-reverify`, `--max-age-days`, `--reverify-max-fetches`.
12. Notify: append to per-role tabs **PM / AI PM / PO / AI PO** (column-by-name), **cross-tab dedup at append time** (`_discover_role_tabs` + `_collect_existing_keys_across_tabs` scan every role tab ONCE up front — not just the single tab a job routes into — and `_dedup_dicts` drops any incoming row whose `_id`/canonical Link/fingerprint already exists in that union or was already seen earlier in the same batch; stats in `notifier.sheet.LAST_APPEND_STATS`: `skipped_existing_id/link/fingerprint`, `skipped_in_batch`), refresh Top Matches, refresh human Summary (with health score), send/lock email.
13. **5b acceptance gate** — runs `tests/acceptance_job_search_v2.py` via subprocess; run exits code 3 if any sheet row is junk.

---

## Ranker (two-track, `ranker/score.py` + `rubric.md`)

- **rubric.md** scores each job against Track A or Track B (whichever fits better), with per-track high-signal cues and hard-NO list.
- **Gemini path:** chunked batches of 80 (was a single 445-job call that timed out — "Server disconnected"), 7s between chunks (10 RPM free tier), per-chunk 3-retry with `gemini-2.5-flash` → `gemini-2.5-flash-lite` fallback. Retry markers include 503/500/INTERNAL/disconnected/timeout.
- **GEMINI key fallback:** if `GEMINI_API_KEY` not in env, reads `Summary!F1` of the sheet (stopgap because the workflow YAML that plumbs the secret is local-only pending PAT `workflow` scope — see Deployment drift).
- **Heuristic fallback** (when Gemini unavailable): two-track, `score = max(track_a, track_b)`. Track A wants CDI; Track B wants Freelance + freelance-tell words in description.
- **Sonnet rerank:** refines top-N; silently no-ops on missing key / low credit (currently 400 credit-low — auto-activates on top-up).

## Notifier

- **sheet.py** — column-by-NAME writer (survives column reorder). Per-role tabs: `Company, Title, Country, Location, Contract, Link, Posted, Verified` (`Posted`/`Verified` re-added 2026-09-10; `_ensure_headers` auto-migrates any live tab missing them). `Posted` = the date read from the job's OWN page (Stage 3.8), falling back to the source date when verification is disabled/unavailable. `Verified` = the liveness stamp `verification_stamp()` produces, shape `"open · posted YYYY-MM-DD · checked YYYY-MM-DD"` or `"unverified (source date) · posted … · checked …"` when the page couldn't be fetched but the source date was trusted; the acceptance gate parses this shape. `append_jobs(..., verification=records)` takes the Stage 3.8 records dict (content_hash → VerificationRecord) to fill these columns. Top Matches: `Fit, Title, Company, Location, Contract, Source Tab, Link`. **Summary tab is HUMAN-READABLE** (2026-06-24): STATUS + health score, TODAY (new/added/strong/where), FILTERED OUT (and why, plain words), SOURCES, NEEDS ATTENTION (real issues only), all-time totals, then a compact technical footer. Preserves `D1` (email-lock state) and `F1` (GEMINI fallback key).
- **Cross-tab dedup at append (2026-09-10)** — `_discover_role_tabs()` finds every tab a job could route to (routing-config tabs + any worksheet with both a Title and Company column) plus dashboards excluded; `_collect_existing_keys_across_tabs()` reads each tab once and unions (`_id`, canonicalized Link, fingerprint); `_dedup_dicts()` drops an incoming row on the first key match (existing-tab match OR in-batch match), reporting which bucket in `LAST_APPEND_STATS`. Root cause fixed: the same posting landing in "PM" one day and "AI PM" the next (routing config tweak, borderline title) previously wasn't caught because only the single destination tab was checked.
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

## Acceptance gate (the "is this shippable?" definition) — 2026-06-24, extended 2026-09-10

`tests/acceptance_job_search_v2.py` is the single shippability gate. Layers:

1. **Frozen regression corpus** (no sheet needed; independent of pipeline logic): the operator's exact 19 flagged-wrong titles (+ 2 German) MUST classify as reject; 12 known-good (incl. langdetect false-positives like "Staff AI Engineer - M/W") MUST classify as keep. `MUST_REJECT_BY_DOMAIN` (2026-09-10) adds hardware/electronics/instrumentation-domain titles that MUST fail `classify_domain`, checked alongside `MUST_REJECT_BY_TITLE`/`MUST_REJECT_BY_LANGUAGE`. Guards against silently weakening the gate.
2. **Live-sheet check:** reads EVERY row in every role tab + Top Matches; HARD-FAILS if any row is irrelevant / non-EN-FR / out-of-scope-location / out-of-domain / broken-link. Reuses the pipeline's own `classify_title`/`classify_language`/`classify_domain` (single source of truth).
3. **`check_verified_stamp` (2026-09-10):** parses each row's Verified column against `STAMP_CORPUS` (shape fixtures); a violation is raised when the stamp is missing, unparsable, `closed`, has no readable posted date, or is stale-at-insert (age > `MAX_AGE_DAYS`, default 7). Top Matches rows are exempt (a derived dashboard, not a roster of record).
4. **L3 silent-degradation check:** fails a live run whose `pipeline_stats` show posting verification was skipped/disabled on a real (non-dry-run, non-fixture) invocation, and prints any `posting_verifier` warnings (e.g. a host blocking ≥80% of fetch attempts) into the acceptance output.

**Wired into run.py Stage 5b** — a run producing junk exits code 3 (FAIL), recorded as `acceptance` in the run-log. Per `~/.claude/rules/front-door-synthetic.md`, needs **5 consecutive PASS runs** against the live cron before "shippable". Known limitation (shared oracle): the live check shares classifier code with the pipeline, so it catches regressions + known classes but NOT a brand-new junk class on first appearance — that becomes a new corpus entry once seen.

Maintenance scripts: `purge_irrelevant_rows.py` (dedup + domain purge + relevance/language purge + reverify — see Stage 3.9), `trim_sheet_columns.py` (one-shot column migration).

---

## Cross-day dedup, Contracts

SQLite seen.db, `content_hash = sha256(title|company|canonical_url)`, TTL 60d, matched **OR by `fingerprint`** since 2026-09-10 (`already_seen_by_fingerprint` stat; `fingerprint` column added via in-place migration, no `--reset` needed for existing DBs). Pydantic v2 frozen contracts (`contracts.py`): SourceJob/NormalizedJob/RankedJob + enums incl. `JobSource.REMOTEOK` / `WEWORKREMOTELY`.

**`compute_fingerprint(title, company)` (2026-09-10 dedup hardening)** — SHA256 of `normalized(title)|normalized(company)`, a fuzzy cross-source dedup key that survives what `content_hash` misses (same posting, two boards, different tracking-param URLs): gender-marker suffixes (`h/f`, `m/w/d`, `all genders`, etc.), accents, punctuation, legal-entity suffixes (`sas`, `gmbh`, `ltd`, `group`…), and recruiter `"via X"` wrapping. Company-empty/unknown/confidential normalizes to a title-only fingerprint (paired with a literal sentinel so it can't collide with a real empty-company match). `NormalizedJob.fingerprint` is populated in `normalize.py`'s `to_normalized()`; defaults to `""` so pre-existing serialized JSONL (written before the field existed) still parses.

**`canonicalize_url` expanded tracking-param set + trailing-slash fix (2026-09-10)** — `_TRACKING_PARAMS` grew common job-board session/tracking params (`refId`, `trackingId`, `position`, `pageNum`, `originalSubdomain`, `origin`, `campaign`, `xkcb`, `xpse`, `vjs`, `advn`, `sjdu`, `utm_id`, `mkt_tok`, `_hsenc`, `_hsmi`, `hsCtaTracking`, `itm_source`, `itm_medium`) that vary per impression/click for an otherwise-identical posting; a trailing `/` on path/fragment is stripped so `/jobs/1` and `/jobs/1/` canonicalize identically. Deliberately NOT stripping `q` — some boards use it to identify the job itself, not for tracking.

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

## Strict verification mode (2026-09-14 — "would a manual tester sign this off?")

Panel audit (tester / skeptic / customer / sales / automation-boundaries) of the 2026-09-10 build found three ways an unconfirmed link could still reach a client: blocked hosts kept on the source date, dated pages without a positive "open" signal, and rows never re-checked after insertion. Strict mode closes all three and is the default (`config/job_search_v2.json` → `verification.strict: true`; `--lenient-verify` / purge `--lenient` are debugging-only and the acceptance gate fails a live run whose stats show `strict: false`).

- **Positive confirmation required.** A kept link must show a JobPosting JSON-LD block or an apply / postuler / candidater control on its own page. A page with a date but no open signal is re-fetched once (LinkedIn serves a lighter variant intermittently); still unconfirmed → dropped `unconfirmed_open`.
- **Blocked hosts get a browser, not a pass.** 403 / 429 / 999 / 5xx / empty body → one headless-Chromium retry (`normalizer/browser_fetch.py`, Playwright; the cron installs Chromium in `.github/workflows/job_search_daily.yml`). weworkremotely.com serves the full page to the browser. Still blocked → dropped `unverifiable_blocked`. `ok_unverified_fresh` exists only in lenient mode.
- **Re-confirmation every 3 days.** Stage 3.9 (`purge_irrelevant_rows.reverify_rows`) re-opens every stamped row whose last check is older than `verification.recheck_after_days` (3): closed → removed, open → `· rechecked YYYY-MM-DD` appended to the stamp, blocked (strict) → removed. Budget `verification.reverify_max_fetches` (600 pages/run) shared with the unstamped-row sweep; overflow drains on the next run (`remaining_recheck` in stats).
- **Acceptance gate** (`check_verified_stamp`): violation when the label is `unverified …` (strict), or the latest check (`rechecked`, else `checked`) is older than 2 × `recheck_after_days` (6 d — one missed cron day of slack), on top of the existing missing / closed / undated / stale-at-insert rules. `STRICT` and the limit are read from the config so gate and pipeline cannot drift.
- **Digest email** carries a "Verification" block: links opened, kept, dropped by reason (closed / stale / blocked / unconfirmed), sheet re-check counts and the mode — the cost of strictness is always visible.
- Sandbox note: the cloud sandbox sits behind a private-CA proxy; the browser fetcher only ignores TLS errors when `JOB_SEARCH_V2_INSECURE_TLS=1` (never set in production). `PLAYWRIGHT_CHROMIUM_PATH` overrides the Chromium binary.

## Edge cases / known constraints

- **WTTJ 202 anti-bot challenge:** WTTJ answers its anti-bot challenge with HTTP 202 + an empty body. `posting_verifier.fetch_page` retries once (3s backoff) on 202/429/503 or any 2xx body under 500 chars; leftovers after the retry become `ok_unverified_fresh` (source date trusted) rather than a false "no signal" drop.
- **WTTJ soft-404:** removed WTTJ jobs serve HTTP 200 with an "Error 404 / Page not found" body instead of a real 404 — `_detect_closed` includes soft-404 phrases (scripts/styles stripped first, so JS-bundle strings can't false-trigger) so these correctly classify as `closed`.
- **LinkedIn expired-job redirect:** an expired LinkedIn posting 200-redirects to `/jobs/<slug>-jobs?trk=expired_jd_redirect`; `_is_listing_redirect` matches the `expired_jd_redirect` query marker (primary signal) plus the `-jobs` slug-listing path shape (belt-and-braces).
- **LinkedIn rate limiting:** ~3% of LinkedIn fetches 429 at verifier concurrency 8; the one-retry-with-backoff absorbs most of these before falling back to `unverifiable`.
- **WTTJ posted_at is the UPDATED date, not posted date:** the WTTJ Algolia feed's `posted_at` field is when the listing was last updated; the job's own page JSON-LD `datePosted` is often days earlier. Stage 3.8 always prefers the page date over the source date when both exist, so some Algolia-"fresh" hits are correctly dropped as stale — this is intended, not a bug.
- **weworkremotely.com blocks page fetches ~100%:** verified live 2026-09-10 (148-job smoke). Rows are kept on the feed's own `pubDate` (trusted-source fallback) and stamped "unverified (source date)" rather than dropped — losing an entire source to one host's bot-blocking would be worse than trusting its own timestamp.
- **`reverify_max_fetches` backlog:** the historical-row reverify pass (Stage 3.9c) is capped at 400 fetches/run by default; a sheet with more unstamped legacy rows than that drains its backlog over several cron runs, not in one. `stats.remaining_unstamped` reports how many are still queued.
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

# Clean existing junk from the sheet (relevance/language/domain purge + cross-tab
# dedup + historical-row reverify, all default-on)
py execution/personal_workflows/job_search_v2/purge_irrelevant_rows.py --dry-run

# Skip the reverify pass (faster, dedup/domain purge still runs)
py execution/personal_workflows/job_search_v2/purge_irrelevant_rows.py --dry-run --no-reverify
```
