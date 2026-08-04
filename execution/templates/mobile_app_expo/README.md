# mobile_app_expo — workspace-native Expo template

Phase 4b of workspace hardening. This is the **source of truth** template for scaffolding new mobile apps in this workspace. Ships with the workspace's audit stack baked in.

## What this is

A React Native + Expo (SDK 56) + TypeScript starter that includes:

- **Testing infra** — jest + React Native Testing Library (unit), Maestro (E2E), Python acceptance gate + shell front-door probe.
- **CI** — GitHub Actions `preflight.yml` (typecheck + unit + `expo doctor` + lint) and `eas-build.yml` (tag-triggered iOS + Android builds via EAS Cloud).
- **Observability + safety** — Sentry, PostHog analytics, deep links, push notifications, react-query with persistence — all env-gated so they no-op locally when creds absent.
- **Audit stack templates** — `HARDENING.md` + `HANDOFF.md` + `SECURITY_AUDIT.md` (2-pass, Nick-Saraev-course-aligned).
- **Backend pairing pattern** — `src/services/api.ts` reference implementation for calling a paired backend (CF Worker or Supabase — either backend track from `directives/mobile_apps/`).

## How to use

**Do not use this template directly.** Invoke the scaffolder:

```bash
py execution/templates/scaffold_mobile_app.py my-app-slug --backend-stack cf_modal
```

The scaffolder copies this tree to `C:\Users\deban\dev\mobile-apps\my-app-slug\` (per the CLAUDE.md convention that mobile app source lives outside the workspace), replaces `{{APP_SLUG}}` placeholders, adds a registry entry to `execution/mobile_apps/registry.json`, and initializes git.

## Relationship to `C:\Users\deban\dev\mobile-apps\_template\`

The pre-existing `_template` directory outside this workspace is the legacy starter used by `execution/mobile_apps/bootstrap_mobile_app.py`. This workspace-native template is a **superset** that is discoverable via git and version-controlled with the rest of the workspace hardening. Both scaffolders remain valid:

- `bootstrap_mobile_app.py` — legacy path, uses `_template` (Windows dev repo).
- `scaffold_mobile_app.py` — this file's scaffolder, uses this workspace-tracked template. Preferred going forward.

See `TEMPLATE_CHANGES.md` for the delta.

## Hard constraints baked in

- **Windows-friendly CI** — no `xcodebuild` or macOS-only commands; all builds go through EAS Cloud.
- **No secrets in template files** — `.env.example` only; real values live in `.env` (gitignored).
- **Currency: EUR** — cost estimates in HARDENING.md and HANDOFF.md use €, not $.
- **Prior-art-first** — see `TEMPLATE_CHANGES.md` for the synthesis paragraph justifying this template over `create-expo-app --template` or community alternatives.

## Next steps after scaffolding

1. `cd C:\Users\deban\dev\mobile-apps\<slug>`
2. `npm install` (or `pnpm install`)
3. Fill `.env` with your Sentry / PostHog / API base URL (or leave blank — everything env-gates to a no-op).
4. `npx expo start` for local dev.
5. Install EAS CLI (`npm i -g eas-cli`), then `eas init` to link the app to your Expo account. Copy the returned `projectId` back into `execution/mobile_apps/registry.json` for this app.
6. **Before Phase 4-5**: run `py execution/mobile_apps/preflight.py` — it gates on Apple Developer Program enrollment (`APPLE_ENROLLMENT_STATUS=active` in `.env`) and Google Play Console tester setup.
