# HARDENING.md — {{APP_SLUG}}

Living document. Updated whenever a HARDENING item lands or a new gap surfaces.

---

## Release gate status

| Gate | Status | Owner | Notes |
|---|---|---|---|
| Apple Developer Program enrollment | [ ] not started / [ ] pending / [ ] active | operator | `APPLE_ENROLLMENT_STATUS` in `.env` gates Phase 4-5 |
| iOS bundle identifier registered | [ ] | operator | Fill `IOS_BUNDLE_ID` in `.env` before first EAS build |
| App Store Connect app record created | [ ] | operator | Needs `ascAppId` in `eas.json:submit.production.ios` |
| TestFlight tester group configured | [ ] | operator | Min 1 internal tester for smoke |
| App Store review status | [ ] not submitted / [ ] in review / [ ] approved / [ ] rejected | operator | |
| Google Play Console app created | [ ] | operator | |
| Play Console 12-tester gate (Personal Developer) | [ ] 0/12 / [ ] N/12 / [ ] 14-day count started at YYYY-MM-DD | operator | See `execution/mobile_apps/play_console_tester_gate.py` |
| android bundle uploaded to Internal Testing | [ ] | operator | |
| Google Play review status | [ ] not submitted / [ ] in review / [ ] approved / [ ] rejected | operator | |

**Do NOT write "shipped/live/ready" in HANDOFF.md until BOTH stores are `approved` AND the front-door synthetic (`tests/front_door_{{APP_SLUG}}.sh`) has passed 5 consecutive days against production.**

---

## Reliability thresholds

Established at release. Alert when breached.

| Metric | Threshold | Source | Action on breach |
|---|---|---|---|
| Crash-free session rate | ≥ 99.5% | Sentry / EAS Update crash reports | Roll back OTA via `eas update:republish` |
| ANR rate (Android) | ≤ 0.47% (Play "bad behavior" threshold) | Play Console Vitals | Investigate + patch within 48h |
| p95 cold-start time | ≤ 3s | Sentry performance / manual | Investigate render + init blocking |
| /api/health uptime (paired backend) | ≥ 99.9% (30d) | UptimeRobot / cron probe | Backend team investigates |
| /api/health p95 latency | ≤ 500ms | UptimeRobot / manual | Investigate backend cold-start / cache |

---

## Rollback plan

1. **OTA regression** (JS-only change caused the issue): `eas update:republish --branch production --update-id <previous-good-update-id>`. Users get the old JS bundle on next app launch. Full docs: https://docs.expo.dev/eas-update/rollbacks/
2. **Native regression** (native module change, only fixable in a new binary): submit a hotfix build to TestFlight / Play Internal Testing. Meanwhile: publish an OTA update that disables the affected feature via a client-side flag (`extra.featureFlags.<name> = false` in `app.config.ts`).
3. **Backend regression** (paired backend broken): the mobile app has offline-persistent cache via react-query. Users see stale-but-usable UI until the backend recovers. If the outage exceeds the `gcTime` (24h), first-launch users see the empty state — coordinate a status message via a native banner or Sentry-triggered alert channel.

---

## Cost estimates (EUR)

Per `~/.claude/rules/currency-eur.md`, all budget figures in EUR.

| Line item | Monthly cost | Notes |
|---|---|---|
| Apple Developer Program | ~€9/mo (~€99/yr) | Required for App Store distribution |
| Google Play Console | ~€2/mo (one-time €22 signup) | Required for Play distribution |
| EAS Cloud builds | €0 (free tier: 30 iOS + 30 Android builds/mo) | Overages billed per build |
| EAS Update | €0 (free tier: 1k monthly active users) | Then paid per MAU |
| Sentry (Team plan free tier) | €0 (up to 5k errors/mo, 10k performance events) | |
| PostHog (free tier) | €0 (up to 1M events/mo, 5k session recordings) | |
| Cloudflare Workers (paired backend, cf_modal track) | €0 (10M req/day free tier) | |
| Supabase (paired backend, supabase track) | €0 (free tier: 500MB DB, 50k monthly active users) | |

Free-tier baseline for a personal-scale app: ~€11/mo (Apple + Play). Overages start when app crosses free tiers on any provider.

---

## Post-mortems

_Append incidents here. Format: `## YYYY-MM-DD — one-line title`, then Root cause / Fix / Guardrail added._

_(none yet)_

---

## Owed follow-ups

_Backlog of hardening items surfaced but not yet actioned. Move to Post-mortems once resolved._

- [ ] Sentry source-map upload wired into `eas-build.yml` (needs `SENTRY_AUTH_TOKEN` secret)
- [ ] Maestro flow expanded beyond smoke to critical-path (once first feature ships)
- [ ] Choose backend track (`cf_modal` or `supabase`) — fill in `registry.json:apps[<slug>].backend_stack`
