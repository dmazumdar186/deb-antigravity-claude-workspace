# mobile_app_canary.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

- [technical] Alert dedup deferred: The directive (Step 6) specifies alert dedup via `.tmp/canary_state.json` — only alert on state change. As of 2026-06-11, `mobile_app_canary.py` does NOT write to `.tmp/canary_state.json` and does NOT send alerts. The script exits with a status JSON summary only. Alert + dedup is the Phase 2 of the canary, not yet built.
- [constraint] Canary alerting is Phase 4a-gated: The `--alert` flag and `.tmp/canary_state.json` dedup should be added at Phase 4a time (when the first real app is deployed). Adding it now without an actual app in `registry.json` has no validation path.
- [technical] httpx not requests: `mobile_app_canary.py` uses `httpx` (not `requests`) for async-capable HTTP. The dependency is `httpx`, not `requests`. Add to `requirements.txt` or `pyproject.toml` if setting up a fresh environment.
- [technical] threading.Lock on results: The canary uses `ThreadPoolExecutor` to probe apps in parallel. `results_lock = threading.Lock()` guards the shared `results` dict — this is the correct hardening pattern. Verify the lock is still present before adding new parallel health checks.
- [pattern] --dry-run semantics: `--dry-run` prints what the canary would assert without making HTTP calls. Use this to validate registry.json shapes before any app is deployed.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/canary.md
- .claude/notes/execution/mobile_apps/bootstrap_mobile_app.md
