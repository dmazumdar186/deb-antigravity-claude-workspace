# custom_scrapers — Known Blockers Notes

Captured from .claude/upgrades/other_categories.md on 2026-06-12.

- [learned] Jooble reCAPTCHA blocked: `jooble_jobs.py` is blocked by Jooble's reCAPTCHA as of Phase 1a (2026-06-09). The directive exists (`directives/custom_scrapers/jooble_jobs.md`) but the scraper cannot be used without a headless-browser or official API key workaround. Status: DEFERRED. Do not re-enable without resolving the reCAPTCHA issue.
- [learned] APEC session-cookie required: `apec_jobs.py` requires a valid APEC session cookie to fetch job listings. The cookie is not an API key — it must be manually extracted from a browser session logged into apec.fr. Session cookies expire; re-extract if the scraper returns empty results or 403.
- [learned] Indeed rate-limited: `indeed_jobs.py` is subject to Indeed's aggressive rate-limiting and bot detection. The scraper may return empty results or get temporarily blocked after repeated calls. Use with low frequency and a User-Agent rotation strategy if needed.
- [pattern] All 7 scrapers are structurally identical: fetch → normalize → save JSON. They are called sequentially by `job_tracker_pm_france.py`. When adding a new job board, follow the same fetch/normalize/save pattern to stay consistent.
- [technical] Dynamic Workflow candidate: All 7 scrapers are fully independent — a fan-out wrapper would cut wall-clock time ~4–6×. When `job_tracker_pm_france.py` is upgraded for parallelism, add `threading.Lock()` on the shared `per_board_raw` dict.

## See also

- .claude/upgrades/other_categories.md
- .claude/notes/execution/personal_workflows/job_search_sheet.md (Jooble entry)
- directives/custom_scrapers/jooble_jobs.md
- directives/custom_scrapers/apec_jobs.md
- directives/custom_scrapers/indeed_jobs.md
