# iOS Deploy — EAS Cloud Build + TestFlight

## Goal

Build a production iOS `.ipa` via EAS cloud (no Xcode, no Mac), submit it to App Store Connect, invite testers to TestFlight. Works on Windows; falls back to a GitHub Actions macOS runner only if `eas credentials configure` fails interactively.

## Inputs

- Phases 1-3 complete (app is functional locally)
- `APPLE_ENROLLMENT_STATUS=active` in `.env` — preflight blocks this directive otherwise
- `.env` keys: `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`
- App slug + bundle id in registry (`ios_bundle_id`, e.g. `com.debanjan.<slug>`)
- `eas.json` in the app repo with a `production` profile

## Tools/Scripts

- `eas build --platform ios --profile production` — cloud build
- `eas submit --platform ios` — App Store Connect upload
- `execution/mobile_apps/testflight_invite.py` — adds testers via ASC API (JWT auth)
- `execution/mobile_apps/eas_build_helper.py` — wraps `eas build`, captures logs (utf-8), posts status

## Steps

1. **Preflight gate.** Confirm `APPLE_ENROLLMENT_STATUS=active`. If `pending`, refuse — `eas submit` will fail and a build is non-trivial cost ($).
2. **Confirm `eas.json` has a production profile.** Minimal example:
   ```json
   {
     "build": {
       "production": {
         "ios": { "resourceClass": "m-medium" },
         "distribution": "store"
       }
     },
     "submit": {
       "production": {
         "ios": {
           "appleId": "$APPLE_ID",
           "ascAppId": "<numeric app id from App Store Connect>",
           "appleTeamId": "$APPLE_TEAM_ID"
         }
       }
     }
   }
   ```
3. **First-time credentials.** `eas credentials configure --platform ios`. EAS generates + stores the distribution cert + provisioning profile on its servers.
   - **Interactive Apple ID 2FA required.** Works on any browser (Edge / Chrome on Windows is fine).
   - **If 2FA fails on Windows for any reason** (rare; some Apple SSO flows misbehave), use the **macOS-runner fallback** (see Fallback section).
4. **Run the cloud build.**
   ```
   py execution/mobile_apps/eas_build_helper.py --slug <slug> --platform ios --profile production
   ```
   The helper invokes `eas build`, streams logs with utf-8 encoding (Windows-safe), and writes the build URL + status into the registry.
5. **Wait for build (10-30 min typical).** Helper polls until done. On success: download URL appears, `.ipa` is in EAS storage.
6. **Submit to App Store Connect.**
   ```
   eas submit --platform ios --profile production --latest
   ```
   `--latest` picks the most recent successful build for this profile.
7. **TestFlight processing.** ASC takes 10-30 min to process the binary. Status is visible at https://appstoreconnect.apple.com. Tester invites blocked until processing completes.
8. **Invite testers.**
   ```
   py execution/mobile_apps/testflight_invite.py --slug <slug> --emails alice@example.com,bob@example.com --group "internal"
   ```
   Uses the ASC API with JWT auth (`ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`). Adds testers to the named group; group must exist in ASC (create once via UI).
9. **Verify on a real device.** Tester accepts the email, installs TestFlight, app appears. Confirm core flow works.
10. **Update registry.** Append `last_build_sha`, `last_build_url`, `testflight_submitted_at` to the app's entry.
11. **Commit.** Any `eas.json` or version bumps in the app repo.

## Fallback: GitHub Actions macOS runner (only if Windows path fails)

If `eas credentials configure` cannot complete on Windows (rare Apple-SSO issue):

1. Push the app repo to GitHub (public repo → free macOS runner; private → 2000 min/mo free).
2. Add `.github/workflows/ios-credentials.yml`:
   ```yaml
   on: workflow_dispatch
   jobs:
     setup:
       runs-on: macos-latest
       steps:
         - uses: actions/checkout@v4
         - uses: expo/expo-github-action@v8
           with: { eas-version: latest, token: ${{ secrets.EXPO_TOKEN }} }
         - run: eas credentials configure --platform ios --non-interactive
   ```
3. Run the workflow manually. The macOS runner completes the credential dance; EAS stores the result on its servers.
4. Subsequent `eas build` calls from Windows work normally — credentials are server-side.

Alternative: **MacInCloud** rental ($1-2/hr) for a 1-hour session if GitHub Actions is unavailable.

## Outputs

- Built `.ipa` in EAS cloud storage (download URL persisted to registry)
- App available in TestFlight under the configured ASC app id
- Testers receive invite emails
- Registry: `last_build_sha`, `last_build_url`, `testflight_submitted_at`, `testflight_testers_count`

## Edge Cases

- **`APPLE_APP_SPECIFIC_PASSWORD` mismatch.** Apple rotates these silently if you create a new one without deleting the old. If submit fails with auth error, regenerate at https://appleid.apple.com/account/manage and update `.env`.
- **Bundle ID conflict.** Two apps can't share `com.debanjan.<slug>` in the same Apple team. Pick unique slugs; registry's `ios_bundle_id` field is the canonical record.
- **ASC processing stuck > 1h.** Apple's binary processing occasionally hangs. Email Apple Dev Support; no client-side fix.
- **Build minute cap (EAS).** Free tier = 30 builds/mo total across all apps. Heavy debugging hits this in days. Upgrade to Production ($19/mo) before a launch sprint.
- **Tester email already on App Store.** ASC silently skips re-invites. `testflight_invite.py` should log + treat as success.
- **2FA loop.** If Apple 2FA bounces the EAS login, generate an app-specific password (https://account.apple.com → Sign-In and Security → App-Specific Passwords) and use that instead of the iCloud password.
- **First submission requires manual app metadata.** App Store Connect needs name, description, screenshots, category, age rating — set via the ASC web UI before `eas submit`. `testflight_invite.py` cannot fill these.
- **Privacy nutrition labels.** Required for ASC submission. Fill via the ASC web UI; declare every SDK that collects data (analytics, crash reporting).

## Notes

- EAS Build fully supports Windows for iOS. The fallback (GitHub macOS runner) is rare — most builds work first-try.
- `eas build` minutes count against the EAS plan, not Apple's quotas.
- For TestFlight-only MVPs, App Store review is NOT required — internal/external testing is sufficient for personal projects.
