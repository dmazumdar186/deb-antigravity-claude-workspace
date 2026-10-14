# Instantly Lead Cleaner

## Goal
Turn a dirty lead export (Google-Maps titles / studio names sitting in the "First name" column, duplicate emails, unverified websites) into a CSV Instantly can ingest where `Bonjour {{firstName}}` reads like a personal email. A wrong first name is worse than a blank one: the script blanks anything it cannot defend.

## Inputs
- `--input` CSV (utf-8-sig). Required columns: `First name`, `City`, `Email`, `Website`, `Found on`, plus email-verifier columns (`email`, `status`, `overall_score`, `is_safe_to_send`, `is_valid_syntax`, `is_disabled`, …). Any extra columns are passed through.
- `--output` path for the cleaned CSV; `report.json` is written next to it.
- `--workers` (16) threads for website fetches; `--limit N` for a test slice; `--no-llm` for deterministic heuristics only.
- Env: `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOEKN`), optional `REQUESTS_CA_BUNDLE` when behind a TLS-intercepting proxy.
- Deps: `requests`, `openai` (used by `modules.llm_client`), optional `beautifulsoup4` (regex fallback otherwise).

## Tool
`execution/lead_sourcing/instantly_lead_cleaner.py`

```
python3 execution/lead_sourcing/instantly_lead_cleaner.py --input .tmp/yoga_fr/input.csv \
    --output .tmp/yoga_fr/Yoga_Teachers_France_instantly_ready.csv --workers 16
```

## Steps (what the script does)
1. Load CSV, normalise email (lower/strip).
2. Fetch every website once (cached by URL, 12 s timeout, one retry on timeout, browser UA). `website_status`: `live` (2xx, same domain), `redirect` (2xx, final domain differs; `website_final` filled), `dead` (4xx/5xx/timeout/DNS).
3. Build name candidates from the raw name (`Claire Gómez - Professeure…` → Claire), the page title/og:title/headings (only when corroborated by the email or URL), the URL slug (`/equipe/audrey-aveline/` → Audrey) and the email username (`anna.zingarelli@` → Anna; stoplist for contact/hello/info/…).
4. LLM pass (`anthropic/claude-sonnet-5.5`, 10 leads per call, ~$0.30 per 230 leads; then `--deep` (default on) crawls up to 4 about/team/professeur pages per still-blank live site and asks again "who runs this studio", accepting confidence ≥0.6 as `name_source=website_deep`, ~$0.30 more; `--no-deep` skips it) returns `first_name`, casual `company`, `confidence`. Results are cached in `.tmp/instantly_lead_cleaner_llm_cache.json` keyed on email+raw name, so re-runs after heuristic tweaks cost nothing. Post-rules: a strong raw "First Last - …" pattern overrides an LLM nickname (Lucie beats luzi@); a bare raw given name is accepted only if it appears in the email username or URL path; a final sanitiser blanks studio words, multi-word strings and ALL-CAPS leftovers.
5. `send_recommended = yes` when verifier status ∈ {safe, role_account, catch_all}, syntax valid, not disabled, and the domain is not a directory/booking platform (trainme, feverup, prontopro, lesmedecinesdouces, webador, readymag, bookday, …) or a placeholder (exemple@monsite.com, johndoe@email.fr, jean.dupont@gmail.com, …).
6. Dedupe on email. Keeps the row with a first name > verifier `safe` > live website > earliest; `dup_count` and `merged_from` (other raw names joined by ` | `) record the merge.

## Outputs
- Cleaned CSV, columns: `first_name, company, city, email, website, website_status, website_final, email_status, overall_score, is_safe_to_send, send_recommended, name_source (llm/website/email/raw/none), name_confidence, original_name, dup_count, merged_from, found_on`, then every remaining input column.
- `report.json`: rows in/out, duplicates removed, names found/blank, website live/redirect/dead, send_recommended yes/no, LLM token/cost estimate, and the list of blank-first-name rows.

## Edge cases / lessons
- **Instantly dedupes on email**: the output has exactly one row per email; never re-add duplicates downstream.
- **Blank names**: in Instantly use the fallback syntax `{{firstName|there}}` → e.g. `Bonjour {{firstName|}}` collapses to `Bonjour` (trim the double space in the template: `Bonjour{{firstName| }}`? — simplest is a second campaign/sequence for the blank-name segment, filtered on `first_name` empty). Roughly half of a Maps-sourced yoga list is studios with no identifiable person.
- **Website `dead` may be bot-blocked** (Cloudflare/Wix 403) or a timeout under the proxy; it is not proof the business is gone. Check `website_final` for redirects to a new domain before discarding.
- **Platform emails** (serviceclient@lesmedecinesdouces.fr, hello@trainme.co, support@webador.fr) reach the directory, not the teacher — the name may be right but `send_recommended` is `no`.
- Generic studio mailboxes (contact@studio.fr) with a teacher found on the page are kept with the teacher's name at reduced confidence; filter on `name_confidence >= 0.8` for a stricter personal segment.
- Verifier `unknown` / `invalid` / `disabled` → `send_recommended = no` even when a name was found.
- LLM output is non-deterministic at the margins (confidence 0.5–0.6 rows differ between runs); the cache freezes a run so the CSV is reproducible.
- The LLM only sees the first ~800 chars of page text; multi-teacher studios are deliberately blanked.

## Cost
- Websites: free. LLM: ~85k input / ~4k output tokens for 229 leads ≈ $0.31 on Sonnet 5.5 (cached afterwards).
- **Confidence cap**: any LLM/deep name not corroborated by the email username, URL path or listing name is capped at `name_confidence = 0.6` so it stays visible for spot-checks; deep-pass names are therefore almost always 0.6. Filter `>= 0.8` for the safest personal segment.
- Company names are post-processed to collapse 3+ repeated letters (LLM stutter: "Yogaaa" → "Yoga").
