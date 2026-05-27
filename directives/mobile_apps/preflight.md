# Mobile App Preflight Checklist

## Goal

Verify every CLI, account, and `.env` key required to ship a mobile app is present **before** any phase work begins. Block Phase 4-5 (cloud deploy) when Apple enrollment is still pending. Output a green/red status per item so a sub-agent can decide what to fix vs. proceed with.

## Inputs

- `.env` at workspace root
- User shell with `node`, `npm`, `eas`, `wrangler`, `modal`, `py` on PATH
- `APPLE_ENROLLMENT_STATUS` env var = `pending` or `active`
- Active EAS / Cloudflare / Modal sessions (must be pre-logged-in by the user; preflight never logs in)

## Tools/Scripts

- `execution/mobile_apps/preflight.py` (future — currently the skill runs the checks inline as shell calls)
- `node --version`, `eas --version`, `wrangler --version`, `modal token current` — CLI presence
- `eas whoami`, `wrangler whoami` — session presence (read-only, never invoke `login`)
- `.env` parser — read keys without echoing values

## Steps

1. **Node ≥ 18 check.** Run `node --version`. Fail red if missing or < 18.0.0. `eas-cli` silently degrades on Node < 18 (build commands hang or post obscure errors); never rely on a Node 16 fallback.
2. **eas-cli installed.** Run `eas --version`. Fail red if not found. Install hint: `npm install -g eas-cli`.
3. **eas logged in.** Run `eas whoami`. Fail red on non-zero exit or "not logged in". Hint: `eas login`. Do NOT auto-run login.
4. **wrangler installed.** Run `wrangler --version`. Fail red if absent. Note v4+ behavior in `phase4a_cf_worker.md` (may ignore `--type javascript`).
5. **wrangler session present.** Run `wrangler whoami`. Fail red if logged out. **Do NOT attempt `wrangler login`** — the active wrangler session may be tied to Accessory Masters (locked) and a re-login could clobber it. If logged out, ask the user to log in manually in a separate shell.
6. **Modal token present.** Run `modal token current`. Fail red on non-zero exit. Hint: `modal token new`.
7. **Required `.env` keys.** Confirm presence (never values) of: `EXPO_TOKEN`, `OPENROUTER_API_KEY`, `FIRECRAWL_API_KEY`. Each missing key = red.
8. **Optional `.env` keys (Phase 4-5 iOS submit).** Note presence/absence of: `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`, `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH`. Missing = yellow until app #1 hits Phase 4.
9. **Apple enrollment gate.** Read `APPLE_ENROLLMENT_STATUS`. If `pending`, mark Phases 4-5 as blocked. If absent, treat as `pending`. Phases 1-3 are still green.
10. **Account provisioning summary.** Print one-line cost reminder per account (see Outputs).
11. **Aggregate.** Emit a final table: every item with `green` / `red` / `yellow` and the one-line remediation hint. Exit non-zero only if any required item is red.

## Outputs

Console table, one row per check:

```
[GREEN]  node --version           v20.10.0
[GREEN]  eas --version            14.2.0
[GREEN]  eas whoami               debanjan
[GREEN]  wrangler --version       3.85.0
[GREEN]  wrangler whoami          (logged in, scoped to <account>)
[GREEN]  modal token current      ak-xxxxxxxxxxxx
[GREEN]  .env EXPO_TOKEN          present
[RED]    .env OPENROUTER_API_KEY  MISSING — add to .env
[YELLOW] .env APPLE_ID            absent (needed for iOS submit only)
[BLOCK]  Phase 4-5                APPLE_ENROLLMENT_STATUS=pending
```

Account / cost reminder (printed once):

| Account | Cost | Required for |
|---|---|---|
| Apple Developer Program | **$99/yr** | iOS TestFlight + App Store submission |
| Google Play Console | **$25 one-time** | Android Play Store submission |
| Expo EAS | free 30 builds/mo, $19/mo Production | All iOS + Android cloud builds |
| OpenRouter | **~$5 to start** | Phase 5a LLM routing |

## Edge Cases

- **`node` returns 14.x or 16.x** — `eas-cli` install may "succeed" but builds fail mid-pipeline. Hard-fail; do not advance.
- **`wrangler whoami` shows wrong account** — surface the account name, ask the user to confirm it's the non-AM account before proceeding. Never silently use a wrong-scoped session.
- **`modal token current` works but Modal account is suspended** — preflight cannot detect; surfaces at deploy time. Document as a known false-positive.
- **`.env` exists but `EXPO_TOKEN` is an empty string** — treat as missing, not present. Check both key presence AND non-empty value.
- **Apple enrollment can take 24h–2 weeks.** Phase 1-3 must proceed unblocked during this window; flip `APPLE_ENROLLMENT_STATUS=active` in `.env` once Apple confirms.
- **OAuth keys (ASC private key) on Windows path with spaces** — must be quoted in `.env` (`ASC_PRIVATE_KEY_PATH="C:\Users\deban\OneDrive\path with space\key.p8"`); unquoted will silently truncate.
- **`eas whoami` flakes on cold network** — retry once with 5s backoff before marking red.

## Notes

- Preflight is the **gate** for every other directive. The `/mobile-app` skill runs it before any `new` / `phase` / `ship` command.
- Never `eas login` or `wrangler login` from preflight. Read-only checks only.
- If the user adds a new required env var to any phase directive, add it here too so preflight catches it.
