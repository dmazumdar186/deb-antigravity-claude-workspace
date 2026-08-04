# SECURITY_AUDIT.md — {{APP_SLUG}}

Two-pass security review, run before every store submission and after every dependency major bump. Aligned with the Nick Saraev "Claude Code Mobile App Dev" course's 2-pass audit pattern.

Pass 1 = **static** (grep + dependency scan + config review, no build).
Pass 2 = **runtime** (install signed build, exercise flows, watch network + logs).

Log each run below with date + auditor + pass/fail per checklist item.

---

## Pass 1 — Static audit

Run: `npm audit --production` + hand-review below. Log outcome under `## Audit runs`.

### Dependencies
- [ ] `npm audit` returns 0 high / 0 critical (medium acceptable if documented)
- [ ] No known-abandoned packages (last publish > 24 months) in `dependencies`
- [ ] Lockfile committed (`package-lock.json` or `pnpm-lock.yaml`)
- [ ] No `preinstall` / `postinstall` scripts in dependencies (surprise-code risk)

### Secrets + PII
- [ ] `.env` in `.gitignore` (verify: `grep -F .env .gitignore`)
- [ ] `git log --all -S "sk_" -S "SECRET" -S "PRIVATE_KEY"` returns nothing
- [ ] No secrets in `app.config.ts` extra block (public — bundled with the app)
- [ ] All `EXPO_PUBLIC_*` env vars are safe to bundle publicly (they WILL be in the JS bundle)
- [ ] Server-side secrets live only in paired backend `.env` / `wrangler secret` / Supabase env
- [ ] PII fields (email, name, phone, location) never logged via `console.log` — greppable
- [ ] Sentry `beforeSend` scrubs PII if enabled (`sentry.ts` sanitization block)
- [ ] Analytics event payloads scrub PII (`analytics.ts` capture wrapper)

### Auth (if applicable)
- [ ] Tokens stored via `expo-secure-store` (iOS Keychain / Android Keystore) — never AsyncStorage
- [ ] Token refresh handled with a mutex — no concurrent refresh races
- [ ] Logout clears BOTH secure-store tokens AND react-query cache (`queryClient.clear()`)
- [ ] No biometric-only auth without a password fallback (accessibility)

### Storage
- [ ] AsyncStorage keys namespaced (`{{APP_SLUG}}-...`) to avoid collision on shared devices
- [ ] SQLite (`expo-sqlite`) files encrypted if they contain PII (see SQLCipher variant)
- [ ] Cache TTLs make sense — no unbounded growth (`gcTime` set in query-client.ts)

### Network
- [ ] All API calls use HTTPS (grep: `http://` in `src/` should only appear in test fixtures / localhost dev URLs)
- [ ] Certificate pinning considered (production hardening — optional for MVP)
- [ ] No plaintext HTTP allowed in `app.config.ts:ios.usesNonExemptEncryption=false` unless intentional

### iOS-specific
- [ ] `NSPhotoLibraryUsageDescription`, `NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription` etc. included in `app.config.ts:ios.infoPlist` for every permission the app requests
- [ ] `ITSAppUsesNonExemptEncryption` set appropriately (defaults to false, meaning "no non-exempt crypto")
- [ ] URL scheme in `app.config.ts:scheme` is unique (not "app", "myapp", etc. — greppable on the store)

### Android-specific
- [ ] Required permissions in `app.config.ts:android.permissions` — nothing extra
- [ ] `usesCleartextTraffic` NOT enabled in production
- [ ] Intent filters (deep links) exclude wildcard hosts unless intentional
- [ ] Target SDK matches Play Store's current requirement (currently API 34+)

---

## Pass 2 — Runtime audit

Install a signed EAS **preview** build on a real device. Exercise every user-reachable flow. Watch: device network capture (Charles / mitmproxy), device logs, Sentry issues panel, Play Pre-launch Report.

### Network capture
- [ ] Every request has an `Authorization` header OR is genuinely public (health, boot manifest)
- [ ] No request body includes plaintext passwords / raw tokens
- [ ] No API endpoint returns more data than the UI needs (overfetch = exfil risk)
- [ ] Error responses do not leak stack traces / DB errors / internal URLs

### Device inspection
- [ ] `AsyncStorage` inspection (dev build only) reveals no tokens / raw PII
- [ ] Clipboard is not silently populated
- [ ] No background location / mic / camera without a visible in-app indicator
- [ ] Debug menu / dev-only screens are unreachable in production build

### Store pre-review
- [ ] `expo prebuild` succeeds with no plugin conflicts
- [ ] Play Pre-launch Report (Play Console) shows 0 crashes across the 5+ device matrix
- [ ] TestFlight external testing invite delivered to at least 1 external tester and app launches cleanly

---

## Audit runs

Log each pair (Pass 1 + Pass 2) here. Format:

```
### YYYY-MM-DD — auditor: <name/agent>
- Pass 1: PASS / FAIL — <link to notes or PR>
- Pass 2: PASS / FAIL — <link to notes or PR>
- Findings that landed: <list>
- Findings scoped-out with reason: <list>
```

_(no audit runs yet)_
