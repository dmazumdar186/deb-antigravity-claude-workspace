# play_console_tester_gate.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

<!-- TODO: The audit card rates this script "well-hardened, right abstraction,
     no change needed." Deep Play Console-specific gotchas were not surfaced in
     the audit. Extend this file next session if the 20-tester / 14-day gate
     mechanics produce unexpected behavior in practice. -->

- [technical] Pure date math, no API calls: `play_console_tester_gate.py` is a pure date-math script — it computes whether the internal tester requirement (20 testers × 14 days) has been satisfied. Zero API calls, zero subprocess, zero LLM.
- [technical] Registry-write lock: `_REGISTRY_WRITE_LOCK` is present on all registry writes. Hardening rule 2 satisfied.
- [pattern] Canary integration: The expected exit shape is `gate_open: True/False`. The `android_deploy.md` directive exit criteria should call `play_console_tester_gate.py --app <slug>` and assert `gate_open: True` before proceeding to production submission.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/android_deploy.md
