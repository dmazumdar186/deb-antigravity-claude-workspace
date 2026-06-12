# eas_build_helper.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

- [technical] EAS account vs project ID: EAS build minutes are counted against the Expo account, not the project. If Debanjan has multiple EAS accounts, always verify `eas whoami` matches the account owning the project before triggering a build. Wrong account = minutes charged to the wrong quota.
- [technical] Build profile env hierarchy: EAS build profile env vars (in `eas.json`) override local `.env` for cloud builds. Secrets must be added via `eas secret:create --scope project --name KEY --value VALUE`, not just in `.env`. Local `.env` works for `expo start` only.
- [technical] MOBILE_BUILD_WEBHOOK_URL: The `MOBILE_BUILD_WEBHOOK_URL` registry field is used to post-build status callbacks. If not set, build completion is silent (no notification). Set this to a Modal webhook or n8n webhook URL before triggering production builds.
- [technical] Registry SHA tracking: `last_build_sha` in `registry.json` is updated by `eas_build_helper.py` after a successful build. If a build fails mid-way, the SHA may not be updated — always check the EAS dashboard for the actual last build status rather than relying solely on the registry value.
- [pattern] Hardening verified clean: All 5 Windows hardening rules pass: subprocess encoding, `_REGISTRY_WRITE_LOCK` on all registry writes, no LLM path validation needed (repo_path from registry, not LLM), no pricing table, no bare swallows.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/phase4a_cf_worker.md
- .claude/notes/execution/mobile_apps/bootstrap_mobile_app.md
