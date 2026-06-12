# app_store_research.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

- [technical] Firecrawl markdown UTF-8 assumption: `parse_listings()` does string manipulation on Firecrawl markdown responses with no encoding guard. Firecrawl returns UTF-8 in practice, but App Store pages contain emoji and special chars that could misbehave on a non-UTF-8 Firecrawl response. Low severity today; note for hardening if this becomes a production path.
- [pattern] Single-threaded serial scraper: The current script makes one Firecrawl call per competitor URL. For 10 competitors × 2 stores = 20 serial calls (~2 minutes). When building a new app's competitive analysis, consider running the script 8–10 times manually in parallel terminal tabs rather than waiting for the serial loop.
- [technical] Dynamic Workflow candidate: The fan-out shape (N competitor URLs, each independent) is a natural `ultracode:` target. The workflow file `.claude/workflows/aso-research.md` should be created when first doing a real competitive analysis pass (not before). Defer until Phase 0 of the first app.
- [constraint] No LLM calls: The script uses Firecrawl only (fixed-cost API). No `--mode` flag is needed unless an LLM summarization step is added later.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/app_design.md
