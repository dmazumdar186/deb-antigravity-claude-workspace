# Android Deploy — EAS Cloud Build + Play Console (20-tester / 14-day gate)

## Goal

Build a production Android `.aab` via EAS cloud, submit to Google Play Console, and manage the **mandatory 20-tester / 14-day** closed-testing gate for new Play Console developer accounts (effective Nov 2023+). Production submission is blocked until the gate clears.

## Inputs

- Phases 1-3 complete (app is functional locally)
- Google Play Console account ($25 one-time, paid)
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH` in `.env` — path to a service account JSON with Play Developer API access (created in Play Console → Setup → API access)
- App slug + Android package in registry (`android_package`, e.g. `com.debanjan.<slug>`)
- `eas.json` with a `production` Android profile

## Tools/Scripts

- `eas build --platform android --profile production` — cloud build, produces `.aab`
- `eas submit --platform android` — uploads to Play Console (requires service account JSON)
- `execution/mobile_apps/play_console_tester_gate.py` — **date-math reader only**, tracks gate state from registry, zero Google API calls
- `execution/mobile_apps/eas_build_helper.py` — wraps `eas build`, captures logs

## The 20-tester / 14-day gate (read first)

**For new Play Console developer accounts**, Google requires a closed-testing phase before production submission unlocks:

- **≥20 unique testers** must opt in to the closed test
- **They must keep the app installed for ≥14 consecutive days**
- Both conditions must be met simultaneously, not cumulatively
- Apply only **after** the gate clears

This applies to the **developer account**, not per-app — once cleared once, future apps from the same account submit directly to production.

## Pre-submission content checklist (per Nick transcript chapter 35)

Play Console blocks submission without these. Verify before running step 1:

- **Web-accessible privacy policy** at a URL on a domain you control (e.g. `https://yourdomain.com/<slug>/privacy`). Play Console asks for this URL in the Data Safety form. Same pattern as iOS: have Claude generate the text from Play's content guidelines and host on the same domain as your support email. REQUIRED.
- **Web-accessible support page** at the same domain. REQUIRED for any app that handles user data.
- **App icon** at `assets/icon.png` — `1024x1024` PNG.
- **Adaptive icon assets** (Play requires; per Nick chapter 35):
  - `assets/android-icon-foreground.png` — foreground image (logo only)
  - `assets/android-icon-background.png` — solid colour or pattern background
  - `assets/android-icon-monochrome.png` — single-colour version for themed icons (Android 13+)
- **Splash screen** at `assets/splash.png`.
- **`app.json` fields** — `expo.name`, `expo.android.package` (Java reverse-DNS, e.g. `com.debanjan.<slug>`), `expo.version`, `expo.android.versionCode` (integer, must increment per build).
- **Data Safety form** — Play Console UI walks you through which data your app collects. REQUIRED before any submission. Account for Supabase auth (email collected) and any AI/analytics SDKs.
- **Content rating questionnaire** — Play Console UI.
- **Business email recommended** (per Nick): a Google Workspace email on your domain (~$6/mo) significantly speeds Google's developer-account verification, since the domain is already verified.
- **Android device to verify on** — Google requires you to confirm access to an Android phone during account setup. The tester gate (below) also requires real installs.

If any of the above is missing, fix first; `eas submit` will fail late and the closed-testing track will reject the build.

## Steps

1. **Confirm gate state.** `py execution/mobile_apps/play_console_tester_gate.py --slug <slug>`. Reads `play_tester_gate_started_at` + `play_tester_count_manual` from registry and prints:
   ```
   Slug: my-app
   Gate started: 2026-05-13 (14 days ago)
   Manual tester count: 18 / 20 required
   Days remaining: 0
   Status: BLOCKED — need 2 more testers
   ```
   If status is `CLEARED`, proceed to step 8. Otherwise, fall into closed-testing flow (steps 2-7).
2. **Build the `.aab`.**
   ```
   py execution/mobile_apps/eas_build_helper.py --slug <slug> --platform android --profile production
   ```
3. **Create / update the Play Console listing.** In Play Console UI:
   - App name, description, screenshots, feature graphic, category, content rating questionnaire, data safety form, privacy policy URL
   - Closed testing track → create a "Closed test" release
4. **Submit the build to closed testing.**
   ```
   eas submit --platform android --profile production --latest --track alpha
   ```
   The EAS CLI's `--track` accepts `internal | alpha | beta | production` only — there is no `closed` value. Play Console's UI label "Closed testing" maps to the **`alpha`** track in the CLI (or `beta` for a wider closed pool). The service account must have Release-manager permission on whichever track you pick.
5. **Recruit ≥20 testers.** Add their email addresses to a Google Group OR use Play Console's "Opt-in URL" → share the URL, anyone who joins counts. Tester opt-in is **not** automated; user does this manually.
6. **Track the count.** User manually reads tester count from Play Console (Testers tab → count of opted-in users) and updates `registry.json`:
   ```
   py execution/mobile_apps/play_console_tester_gate.py --slug <slug> --set-count 22
   ```
   This is the **only** write path; no Google API call. (Future: real Play Developer API integration if it becomes a bottleneck.)
7. **Wait 14 days.** Gate script computes `gate_started_at + 14 days` from the registry timestamp. The script does NOT verify that the 20 testers remained installed (Google doesn't expose this cleanly without API integration); user confirms via Play Console UI.
8. **Once cleared: submit to production.**
   ```
   eas submit --platform android --profile production --latest --track production
   ```
   Play Console review takes 1-7 days typically.
9. **Update registry.** Append `last_build_sha`, `last_build_url`, `play_submission_track` (`closed` or `production`), `play_gate_cleared_at`.
10. **Commit.**

## Outputs

- `.aab` in EAS cloud storage
- Play Console listing populated
- Closed testing release live with tester opt-in URL
- Registry: gate state (`play_tester_gate_started_at`, `play_tester_count_manual`, optional `play_gate_cleared_at`)

## Edge Cases

- **Service account JSON wrong scope.** If `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH` points at a file without Play Developer API scope, `eas submit` fails with 403. Re-create in Play Console → Setup → API access, grant "Release manager" role.
- **App not in Play Console yet.** First submission requires the app to be created manually (Play Console UI → "Create app"). `eas submit` cannot create.
- **Closed-testing release rejected.** Common reasons: missing privacy policy, missing data safety form, target SDK below Play's current floor. Fix in Play Console UI, re-submit.
- **20 testers but installs dropped below 20 before day 14.** The clock effectively resets — you need 20 *simultaneous* installed testers across the full 14 days. Re-recruit if drop-off happens.
- **Manual count drift.** User forgets to update `play_tester_count_manual` for a week → gate script says blocked when it's actually clear. Cross-check Play Console UI before final submit.
- **Package name conflict.** Two apps can't share `com.debanjan.<slug>` in Play Console even after deletion. Pick a fresh package name if you ever need to start over.
- **AAB vs APK.** Play Console requires AAB for new apps since Aug 2021. Don't try to upload an APK.
- **Internal vs Closed vs Open testing.** Internal testing (up to 100 users) does NOT count toward the 20/14 gate — must be a **Closed** track (Play Console label), which is `--track alpha` or `--track beta` in the EAS CLI. `--track internal` does NOT clear the gate. Verify in Play Console UI which track the build is on.

## Exit Criteria

The directive is "done" when ALL of these hold (each must be machine-verifiable):

- Pre-submission content checklist complete: privacy policy URL live, support page live, `assets/icon.png` 1024x1024 PNG, adaptive icon assets present (`android-icon-foreground.png`, `android-icon-background.png`, `android-icon-monochrome.png`), `app.json` has `expo.android.package` and `expo.android.versionCode`.
- `py execution/mobile_apps/eas_build_helper.py --slug <slug> --platform android --profile production` exits with code 0 and produces an `.aab`.
- `execution/mobile_apps/registry.json` entry for `<slug>` has non-null `last_build_sha` and `last_build_url`.
- `eas submit --platform android --profile production --latest --track alpha` exits with code 0 (build on closed-testing track confirmed in Play Console UI).
- `py execution/mobile_apps/play_console_tester_gate.py --slug <slug>` prints gate status; if `CLEARED`, `play_gate_cleared_at` is non-null in registry.
- For production submission: `eas submit --platform android --profile production --latest --track production` exits with code 0 AND Play Console submission track shows `production` (not `alpha`/`beta`).
- `registry.json` entry has non-null `play_submission_track` and (once gate is cleared) `play_gate_cleared_at`.

If any predicate fails, fix before claiming Android deploy complete. Do NOT submit to production track until `play_console_tester_gate.py` prints `Status: CLEARED`.

## Notes

- The 20/14 gate is enforced by Google's Play Console UI, not by Wrangler or EAS. The gate script is a **reader / reminder**, never a blocker — Google blocks the actual submit.
- If the user already cleared the gate for a previous app on this account, the gate is account-wide cleared; the script's `--clear-gate` flag marks this in registry.
- Future: integrate the Play Developer API to read tester counts directly. Defer until manual updating becomes painful (estimate: after 3+ apps).
