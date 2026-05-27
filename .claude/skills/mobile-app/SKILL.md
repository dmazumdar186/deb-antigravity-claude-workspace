---
name: mobile-app
description: |
  Scaffold and ship cross-platform mobile apps (Expo + React Native) from
  zero to TestFlight / Play Store on a Windows machine. Wraps Nick Saraev's
  5-phase build (local stack -> network -> SQLite -> CF Worker + Modal cron
  -> OpenRouter AI) with sub-agent decomposition and per-phase anneal audit
  loops. All iOS/Android builds go through EAS cloud (no Xcode required).

  Triggers on: "build a mobile app", "new expo app", "/mobile-app",
  "ship to TestFlight", "ship to Play Store", "scaffold a mobile app".

  Sub-commands: `preflight`, `new {slug}`, `phase {n}` (1, 2, 3, 4a, 4b, 5a,
  5b), `ship ios`, `ship android`.
---

# Mobile App

Orchestrates the workspace's mobile-app pipeline. Directives live in
`directives/mobile_apps/`, execution scripts in `execution/mobile_apps/`,
and per-app source repos at `C:\Users\deban\dev\mobile-apps\{slug}\`
(cloned from `_template\`). Registry of all apps:
`execution/mobile_apps/registry.json`.

## Always run preflight first

Before any `new` or `phase` command, run `preflight`. If preflight is red,
stop and show the user exactly what to fix. Never proceed past a red
preflight without explicit user override.

## Sub-commands

Parse the user's invocation as `/mobile-app <subcmd> [args]`. Default to
`preflight` if no subcommand was given but the user said "build a mobile
app" or similar.

### `preflight`

Spawn a `general-purpose` sub-agent that walks
`directives/mobile_apps/preflight.md` and returns a green/red report.

What the agent checks:
- `node --version` >= 18 (block all phases if older — print upgrade
  instructions and stop)
- `eas-cli` installed (`eas --version`)
- `eas whoami` returns a logged-in account
- `wrangler whoami` (verify only — do NOT log in; AM session must not be
  touched per `CLAUDE.local.md`)
- `modal token current`
- Required `.env` keys present: `EXPO_TOKEN`, `APPLE_ID`,
  `APPLE_TEAM_ID`, `ASC_KEY_ID`, `ASC_ISSUER_ID`,
  `ASC_PRIVATE_KEY_PATH`, `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH`,
  `OPENROUTER_API_KEY`
- `APPLE_ENROLLMENT_STATUS` — `pending` or `active`

**Gate behavior**:
- `APPLE_ENROLLMENT_STATUS=pending` -> allow phases 1-3, block phases 4-5
  with: "Apple enrollment still pending. Finish enrollment at
  developer.apple.com before phases 4-5."
- `node --version` < 18 -> block all phases with upgrade instructions.

### `new {slug}`

1. Run `preflight` (abort on red unless user overrides).
2. Run the bootstrap script:
   ```
   py execution/mobile_apps/bootstrap_mobile_app.py <slug>
   ```
   Pass `--dry-run` first if the user wants a preview.
3. Confirm registry write + repo creation at
   `C:\Users\deban\dev\mobile-apps\<slug>\`.
4. Walk the user through phases 1 -> 5 interactively, asking after each
   phase whether to proceed. Auto-`--app <slug>` on every `phase` call.

### `phase {n}` (n in {1, 2, 3, 4a, 4b, 5a, 5b})

Auto-detect the current app from the cwd (match against
`registry.json`). Fall back to `--app <slug>` if the user passes it.

**Before spawning the phase agent**, snapshot the current commit SHA in
the app repo — anneal adversarial mode needs it as a positional base ref:
```
git -C C:\Users\deban\dev\mobile-apps\<slug> rev-parse HEAD
```
Save as `<base-ref-sha>`.

**Spawn a fresh-context `general-purpose` sub-agent** per phase. Each
agent must fit the ~3-4 min / ~6-8 file budget. If `pipeline-auditor`
sub-agent type is registered, use it for audit agents only — otherwise
fall back to `general-purpose`.

| Phase | Directive | Agent | Anneal mode |
|---|---|---|---|
| 1 | `directives/mobile_apps/phase1_local_standalone.md` | `general-purpose` | classic |
| 2 | `directives/mobile_apps/phase2_network_layer.md` | `general-purpose` | classic |
| 3 | `directives/mobile_apps/phase3_local_db.md` | `general-purpose` | classic |
| 4a | `directives/mobile_apps/phase4a_cf_worker.md` | `general-purpose` | adversarial |
| 4b | `directives/mobile_apps/phase4b_modal_cron.md` | `general-purpose` | adversarial |
| 5a | `directives/mobile_apps/phase5a_openrouter_routing.md` | `general-purpose` | adversarial |
| 5b | `directives/mobile_apps/phase5b_vision_pipeline.md` (created on demand — see below) | `general-purpose` | adversarial |

Phase 4a scaffolds the per-app Cloudflare Worker from scratch with:
```
wrangler init <slug>-api --yes --type javascript
```
The `--yes` flag is critical — without it the CLI hangs on interactive
prompts. Never copy from `execution/infrastructure/api-proxy/` (AM-locked
per `CLAUDE.local.md`).

**Phase 5b** only runs if the app is vision/video-based. If the directive
file does not exist, create it on demand at
`directives/mobile_apps/phase5b_vision_pipeline.md` covering frame dedup
+ 3x3 tile + adversarial anneal audit (pattern reference:
`C:\Users\deban\dev\anneal\src\anneal\` + the YouTube analyzer). If the
app is not vision/video, skip 5b silently.

### After each phase — run anneal as a script (NOT a sub-agent)

`cd` into the anneal repo first, then invoke its CLI directly. Verified
against `C:\Users\deban\dev\anneal\src\anneal\cli.py` (lines 72, 141-192,
529):

**Classic (phases 1-3)** — takes a pre-generated patch file:
```
cd C:\Users\deban\dev\anneal
py -m anneal.cli classic --diff-file <patch> --repo C:\Users\deban\dev\mobile-apps\<slug>
```
Generate the patch beforehand:
```
git -C C:\Users\deban\dev\mobile-apps\<slug> diff <base-ref-sha> HEAD > <patch>
```

**Adversarial (phases 4-5)** — does NOT accept `--diff-file` (`cli.py:529`
hard-codes `diff_path=None`). Pass the snapshotted base-ref SHA as a
positional argument:
```
cd C:\Users\deban\dev\anneal
py -m anneal.cli adversarial <base-ref-sha> --repo C:\Users\deban\dev\mobile-apps\<slug>
```

**Never** invoke `python -m anneal --diff ...` — there is no
`__main__.py`. The only correct entrypoint is `py -m anneal.cli`.

If anneal returns findings, report them to the user and ask whether to
spawn a fixer sub-agent or skip.

### `ship ios` / `ship android`

Auto-detect app from cwd. Verify `APPLE_ENROLLMENT_STATUS=active` (iOS)
or that the Play Console signup is paid (Android). Invoke the directive:

- iOS: `directives/mobile_apps/ios_deploy.md`
  (runs `eas build --platform ios` + TestFlight invite via
  `execution/mobile_apps/testflight_invite.py`)
- Android: `directives/mobile_apps/android_deploy.md`
  (runs `eas build --platform android` + starts the mandatory 20-tester
  / 14-day gate via `execution/mobile_apps/play_console_tester_gate.py`)

If `APPLE_ENROLLMENT_STATUS=pending`, refuse the iOS deploy with: "Apple
enrollment still pending. Finish at developer.apple.com first."

## Example invocations

```
/mobile-app preflight

/mobile-app new receipt-scanner

/mobile-app phase 1 --app receipt-scanner

/mobile-app phase 4a   # cwd is C:\Users\deban\dev\mobile-apps\receipt-scanner

/mobile-app ship ios

/mobile-app ship android
```

## When NOT to use this skill

- The user has an existing native iOS/Android codebase (Swift, Kotlin) —
  this skill is Expo + React Native only.
- Web-only project — use a regular Next.js / Vite setup, not Expo.
- The user wants to publish to platforms other than TestFlight / Play
  Store (Amazon Appstore, F-Droid, etc.) — out of scope; build the EAS
  artifact manually.
- Trivial single-screen demos that don't need a backend — bootstrap
  manually with `npx create-expo-app` instead of paying the
  registry/phase tax.

## Common follow-up tasks

After shipping a phase the user may want to:
- Add the app's `/api/health` URL to the canary registry — already
  handled by `bootstrap_mobile_app.py` writing the `health_url` field;
  `py execution/mobile_apps/mobile_app_canary.py` will pick it up.
- Track Play Console 20-tester gate — `py
  execution/mobile_apps/play_console_tester_gate.py --app <slug>` reads
  `play_tester_gate_started_at` + `play_tester_count_manual` from the
  registry (user updates `play_tester_count_manual` manually from the
  Play Console; no Google API calls).
- ASO research on a competitor listing — `py
  execution/mobile_apps/app_store_research.py <listing-url>` (thin
  Firecrawl wrapper).
- Trigger a fresh EAS build with custom logs — `py
  execution/mobile_apps/eas_build_helper.py --platform ios --app <slug>`.

## Cost reference (1 active app)

| Item | Cost |
|---|---|
| Apple Developer Program | $99/yr ($8.25/mo) |
| Google Play Console | $25 one-time |
| Expo / EAS Production tier | $19/mo (free tier = 30 builds/mo — easy to exhaust during debug) |
| OpenRouter (AI features) | ~$5 starter, then pay-as-you-go |
| Cloudflare Worker | $0 (free tier sufficient) |
| **Recurring total** | **~$32/mo** |

Defer paid signups until the first concrete app idea is committed —
preflight will prompt at app #1 bootstrap time.
