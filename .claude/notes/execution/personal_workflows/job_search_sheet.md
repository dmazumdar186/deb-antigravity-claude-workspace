# job_search_sheet.py Notes

Captured from .claude/upgrades/personal_workflows.md on 2026-06-12.

- [learned] Jooble blocked: Jooble is blocked by reCAPTCHA as of Phase 1a (2026-06-09). `jooble_jobs.py` is in the repo but the source is effectively disabled. Do not attempt to re-enable without a headless-browser or API-key workaround.
- [technical] Adzuna auto-signup: Adzuna API was auto-signed-up via Firecrawl REST during Phase 1a. The API key is in `.env`. No manual Adzuna portal login was needed.
- [technical] Gmail MCP account: The Gmail MCP server is connected to `debanjan186@gmail.com`, NOT `debolshop@gmail.com`. Job alert emails from Adzuna/other sources will arrive at `debanjan186`. Use this account when reading job notification emails via Gmail MCP.
- [constraint] SA JSON pending: Google Sheets write requires a service-account JSON key. As of Phase 1a in-flight, the SA JSON was the last pending credential. Confirm `credentials.json` is present and has Sheets + Drive API scope before running the sheet-write stage.
- [technical] Sequential fan-out: Stage 1 is `for geo in active_geos: for title in active_titles: for source in sources`. Phase 1a = 1 geo × 5 titles × 2 sources = 10 serial calls. Phase 1b adds more geos (20+ calls). When Phase 1b activates, add `ThreadPoolExecutor(max_workers=4)` with a `threading.Lock()` on `all_raw_jobs.extend`.
- [constraint] No canary: Deployed as GH Actions cron. `--dry-run` flag exists, but no synthetic canary monitors for silent empty runs (exit 0 but 0 jobs written).

## See also

- .claude/upgrades/personal_workflows.md
- .claude/notes/execution/personal_workflows/job_search_llm_gate.md
- C:\Users\deban\.claude\projects\c--Users-deban-OneDrive-Documents-AntiGravity-Project-Space\memory\project_job_search_sheet.md
