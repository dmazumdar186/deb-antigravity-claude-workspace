# FR Instructor Finder

## Goal
Find independent instructors in France (yoga, pilates, méditation, languages, music, tutoring, dance, fitness) who advertise on Superprof, Google Maps or Meetup, so we can email them a website offer.

## Inputs
- `--disciplines` comma list (default: yoga,pilates,méditation,anglais,espagnol,piano,guitare,maths,danse,fitness)
- `--cities` comma list (default: top 30 French cities)
- `--sources` superprof,maps,meetup (default superprof,maps)
- `--pages` Serper pages per Superprof query (default 3); `--limit` cap on leads
- `--enrich` find website/email/socials; `--jev` classify; `--sheet SPREADSHEET_ID`; `--out` (default `.tmp/fr_instructors.json`, CSV written next to it); `--mock`
- Env: `SERPER_API_KEY`, `OPENROUTER_API_KEY` (or `_TOKEN`/`_TOEKN`), optional `GOOGLE_SERVICE_ACCOUNT_PATH`

## Tool
`execution/lead_sourcing/fr_instructor_finder.py`

## Steps
1. Smoke test: `python3 execution/lead_sourcing/fr_instructor_finder.py --mock`.
2. Small live run: `--disciplines yoga --cities Lyon --pages 1 --enrich --jev --limit 15`.
3. Scale by discipline/city; dedup is on (name, city, discipline).
4. Filter: `jev_independent == True`, `email_source == website`, `jev_web_presence` below `own_site` = best prospects for a website offer.
5. Next step: `instantly-campaigns` skill with the CSV.

## Outputs
JSON + CSV with columns source, name, first_name, discipline, city, price_eur_h, students, website, email, email_source, website_source, instagram, facebook, phone, address, rating, reviews, category, members, organizer, profile_url, snippet, jev_*.

## Costs
- Serper: $1 / 1000 queries. Per (discipline, city): superprof = pages, maps = 2, enrich = 1 per lead without own site. Lyon/yoga/1 page/limit 15 used 14 queries ($0.014).
- Jev: ~$0.00003 per lead.
- Full default grid (10 x 30 x (3+2)) ≈ 1,500 queries before enrichment ≈ $1.50 + enrichment.

## Edge cases / learnings
- superprof.fr returns 403 to direct fetch — never fetch it; only Serper `site:` search. Titles look like `Alban - Prof de yoga à Lyon - 40€/h - 3 élèves accompagnés`; `/cours/...` URLs are listings and are skipped.
- Superprof and Meetup never expose emails, so `--enrich` is required for outreach. Superprof gives first names only, so enrichment by `"{first_name}" discipline city` is a guess: rows with `website_source=serper_enrich` must be checked before sending. Directories/booking platforms (olybe, wellhub, momoyoga, planity...) are blocklisted in `BLOCKED_DOMAINS`; extend it as new ones appear.
- `email_source=website_offdomain` means the email domain differs from the site domain (usually the directory's address) — don't email those.
- Placeholder emails (utilisateur@domaine.com, example.com, sentry, wixpress) are filtered.
- Meetup find pages are JS-rendered: needs Playwright + Chromium (`/opt/pw-browsers` in cloud; do not run `playwright install`). Any Meetup failure is logged and skipped. Selectors are best-effort and may need updating.
- Jev `noul` answers have no confidence field; P(independent) ≥ 0.6 → True, ≤ 0.4 → False, else blank. Segment uses the chosen option's probability ≥ 0.6.
- `--sheet` without `GOOGLE_SERVICE_ACCOUNT_PATH` logs a warning and skips (cloud sessions).

## Run log

- **2026-10-13 — yoga × 10 cities** (Paris, Lyon, Marseille, Toulouse, Nice, Nantes, Bordeaux, Lille, Montpellier, Strasbourg), `--pages 3 --sources superprof,maps --enrich --jev --workers 10`: 674 raw → 535 deduped leads (263 Superprof, 272 Maps), 494 with a site, 299 with an email (139 same-domain), 307 Serper queries ≈ $0.31, ~8 min wall clock. Sheet export: 510 rows after name+city dedup, 229 usable emails.
- First attempt was serial and died at the 30-min background limit with nothing saved → enrichment is now a 8-10 thread pool with a checkpoint to `--out` every 25 leads; `--resume <json>` skips scraping and continues enrich/Jev from a checkpoint.

## Outreach workbook

`execution/lead_sourcing/instructor_sheet_export.py --input .tmp/yoga_fr.json --out .tmp/yoga_teachers_fr.xlsx` → one tab per city, columns `First name | Last name | Email | Website exists (yes/no/not sure) | Website | Found on`. Rules: Superprof gives first names only; Maps business names stay whole in column A unless they look like a person; social-only presence = "no" (the pitch); a site found by first-name search = "not sure"; an off-domain email on a guessed site is dropped. In the cloud session (no service account) upload the .xlsx through the Google Drive connector; Drive converts it to a Google Sheet and keeps the tabs. Locally, `--sheet <id>` pushes a flat tab via the service account instead.
- 2026-10-13 — outreach sheet "Yoga Teachers with Email" (Drive folder "Yoga Teachers in France"): 229 of 510 teachers had an email (181 Maps, 48 Superprof); after `email_mx_verify.py` 228 deliverable (114 personal, 114 generic role addresses, 1 dead domain). Columns: First name, City, Email, Email status, Website exists, Website, Found on.
