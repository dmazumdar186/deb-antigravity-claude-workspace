# bootstrap_mobile_app.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

- [technical] AM api-proxy lockdown: The `execution/infrastructure/api-proxy/` directory is AM-locked per `CLAUDE.local.md`. The mobile_apps Phase 4a Worker is scaffolded from scratch via `wrangler init <slug>-api --yes` — NEVER cloned from api-proxy. See CLAUDE.md "AM-locked path" section.
- [technical] wrangler v4 session-scoping: `wrangler whoami` can return the wrong account if multiple Cloudflare accounts are configured. Always verify the active account before `wrangler deploy`. Pass `--config wrangler.toml` explicitly if the CWD doesn't contain the right config.
- [technical] OneDrive --force flag: When re-bootstrapping an existing app slug on an OneDrive-synced path, the `--force` flag may trigger a Windows read-only bit conflict (OneDrive locks files during sync). `_rmtree_force` handles this via chmod before rmtree.
- [pattern] Hardening verified clean: All 5 Windows hardening rules pass: subprocess encoding, threading.Lock on registry writes, resolve().is_relative_to() path guard, no pricing table (no LLM), no bare swallows.
- [constraint] Template version pinning: Template version is pinned per-app in `.template-version`. Do not auto-upgrade existing apps when the template changes — the pin is intentional.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/bootstrap_app_repo.md
- .claude/notes/execution/mobile_apps/eas_build_helper.md
