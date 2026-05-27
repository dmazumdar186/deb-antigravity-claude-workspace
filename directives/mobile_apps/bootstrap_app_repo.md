# Bootstrap App Repo — Clone Template + Register

## Goal

Create a new per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\` from the workspace template, replace slug placeholders, initialize git, append to the registry. Idempotent: fail-fast on duplicate slug or existing target dir unless `--force`. Supports `--dry-run` and `--remove` for cleanup.

## Inputs

- App slug (kebab-case, 3-32 chars, alphanumeric + hyphens only)
- `_template/` repo present at `C:\Users\deban\dev\mobile-apps\_template\` (cloned once, manually, before app #1). **Remote backup**: https://github.com/dmazumdar186/deb-mobile-template (public). If the local dir is missing, clone with `git clone https://github.com/dmazumdar186/deb-mobile-template C:\Users\deban\dev\mobile-apps\_template` then continue. Bootstrap script always reads from the local path for speed.
- `execution/mobile_apps/registry.json` exists (initialized as `{"apps": []}` on first run)

## Tools/Scripts

- `execution/mobile_apps/bootstrap_mobile_app.py` — the one and only tool for this directive
- `git` — for `git init` + repo init
- `_template/.template-version` — semver pinned per-app at clone time

## Steps

1. **Validate slug.**
   - Regex: `^[a-z][a-z0-9-]{2,31}$` (kebab-case, starts with letter, 3-32 chars).
   - Reject reserved names: `_template`, `registry`, `__pycache__`, anything starting with `.`.
   - **Path-traversal guard** (CLAUDE.md hardening rule #3): `(parent / slug).resolve().is_relative_to(parent.resolve())`. Reject slugs with `..`, `/`, `\`, absolute paths.
2. **Check registry for duplicate.** Read `registry.json`. If any entry has `slug == <input>`, fail with `slug already registered` unless `--force`.
3. **Check target dir.** If `C:\Users\deban\dev\mobile-apps\<slug>\` exists, fail with `target dir exists` unless `--force`.
4. **Dry-run check.** If `--dry-run`, print planned filesystem ops and exit 0 WITHOUT writing to disk or registry. (Verification step in the master plan relies on this.)
5. **Copy template.** `shutil.copytree('_template', '<slug>')`. Preserves `tsconfig.json`, `package.json`, `app.json`, `src/`, `.gitignore`, `.template-version`, `.env.example`, `eas.json`, `CLAUDE.md`.
6. **Replace placeholders.** In every text file under the new repo, replace:
   - `__SLUG__` → `<slug>`
   - `__BUNDLE_ID__` → `com.debanjan.<slug>` (default; user can override later)
   - `__APP_NAME__` → human-readable name (Title Case version of slug)
   Use UTF-8 read + write (`encoding="utf-8", errors="replace"` per CLAUDE.md hardening rule #1 — even for file I/O, not just subprocess).
7. **Initialize git.** `cd <new repo> && git init && git add . && git commit -m "initial commit from template"`. Subprocess calls use `encoding="utf-8", errors="replace"`.
8. **Append to registry.** Atomic write — read full registry, append new entry, write to `registry.json.tmp`, `os.replace()` to `registry.json`. Guard with `threading.Lock` per hardening rule #2 if any future caller goes parallel.
   New entry shape:
   ```json
   {
     "slug": "<slug>",
     "repo_path": "C:\\Users\\deban\\dev\\mobile-apps\\<slug>",
     "ios_bundle_id": "com.debanjan.<slug>",
     "android_package": "com.debanjan.<slug>",
     "eas_project_id": null,
     "last_build_sha": null,
     "health_url": null,
     "play_tester_gate_started_at": null,
     "play_tester_count_manual": 0,
     "template_version": "<read from .template-version>",
     "created_at": "<ISO timestamp>"
   }
   ```
9. **Print next-steps.** Echo to user:
   ```
   cd C:\Users\deban\dev\mobile-apps\<slug>
   npx expo start
   ```
   Confirms Expo Go boot before committing more code.

## `--remove <slug>` cleanup path

For smoke-test rollback or fully retiring an app:

1. Read `registry.json`, locate slug. If missing, fail.
2. **Git safety check** (unless `--force-remove`):
   - `git status --porcelain` in target repo → if non-empty, refuse (uncommitted changes).
   - `git log @{u}..HEAD` → if any unpushed commits, refuse.
3. Delete the repo dir.
4. Remove the registry entry; atomic write.
5. Confirm to user: `removed <slug>` + paths cleaned.

## Outputs

- `C:\Users\deban\dev\mobile-apps\<slug>\` — populated repo with initial git commit
- `registry.json` — appended entry
- Console: next-step command to verify (`npx expo start`)

## Edge Cases

- **Slug starts with a digit.** Regex rejects (must start with `[a-z]`). Common mistake when slug looks like `2025-app`.
- **OneDrive sync conflict.** The workspace is OneDrive-synced (per CLAUDE.local.md). Brief 1-2s delay between file writes and OneDrive picking them up is fine. **But** `C:\Users\deban\dev\mobile-apps\` is OUTSIDE OneDrive — per the plan, app repos live outside the workspace. Verify path before write.
- **`_template/` missing.** First-run error. User must manually create the template once before app #1; document as a hard prerequisite.
- **Placeholder collision.** If the slug contains the literal string `__SLUG__` (impossible per regex, but defensive), step 6 corrupts. Regex pre-check is the guard.
- **Git init on a path with spaces.** `C:\Users\deban\dev\mobile-apps\my-app` has no spaces by convention. But if a user creates `_template` under `OneDrive\Documents\...` once, the path has spaces. Quote all subprocess arg lists; never use `shell=True`.
- **Registry corruption mid-write.** `os.replace` is atomic on Windows + Linux — partial writes impossible. But: if the JSON is malformed (manual edit), reads throw. Wrap the read in try/except, log, and refuse the write — never auto-recover by overwriting.
- **`--force` semantics.** Overwrites the dir AND the registry entry. Destructive. Confirm with user before passing.
- **`--remove` race with an open VS Code session.** Windows may hold file locks. Refuse with a clear error; user closes editors and retries.

## Notes

- The script must inherit all 5 Python-on-Windows hardening rules (subprocess encoding, threading lock, path validation, no bare except). Reference `C:\Users\deban\dev\anneal\src\anneal\` for hardened patterns.
- After bootstrap, ALWAYS re-run `py execution/generate_registry.py` so `REGISTRY.md` reflects the new entry.
- This directive is invoked by the `/mobile-app new <slug>` skill sub-command.
