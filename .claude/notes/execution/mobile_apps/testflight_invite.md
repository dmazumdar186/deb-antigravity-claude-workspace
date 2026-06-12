# testflight_invite.py Notes

Captured from .claude/upgrades/mobile_apps.md on 2026-06-12.

- [technical] ASC JWT TTL max 1200s: Apple App Store Connect JWTs have a hard maximum TTL of 1200 seconds (20 minutes). If the JWT is generated and the API calls take longer than 20 minutes (unlikely but possible for large tester lists), subsequent calls will get 401 Unauthorized. Regenerate the JWT if the script runs long.
- [technical] ES256 key format: The ASC private key (`ASC_PRIVATE_KEY_PATH`) must be a PEM file in ES256 (ECDSA P-256) format as downloaded from App Store Connect. Do not convert or re-encode — Apple's API rejects modified key formats.
- [technical] Silent re-invite skip: The script skips re-inviting testers already in the beta group. This is intentional dedup behavior. If a tester claims they didn't get the invite, check the ASC dashboard directly — the script may have seen them as already-invited from a prior run.
- [technical] Theoretical 5xx unicode gap: `asc_post()` returns `resp.text` for ALL status codes including 5xx. If Apple returns a malformed error page (non-JSON, non-ASCII), `resp.text` could raise a UnicodeDecodeError on Windows. Low severity (ASC is consistently well-behaved JSON), but noted for future hardening if 5xx responses are ever encountered in practice.
- [constraint] key_path from env var, not LLM: Rule 3 (LLM path validation) is N/A here. The path comes from `ASC_PRIVATE_KEY_PATH` env var. The script does check `if not private_key_path.exists(): raise SystemExit(...)` before reading.

## See also

- .claude/upgrades/mobile_apps.md
- directives/mobile_apps/ios_deploy.md
