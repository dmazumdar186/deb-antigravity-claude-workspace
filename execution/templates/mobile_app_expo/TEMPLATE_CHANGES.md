# TEMPLATE_CHANGES.md

Delta vs. the pre-existing `C:\Users\deban\dev\mobile-apps\_template\` and vs. `create-expo-app --template blank-typescript`.

---

## Prior-art synthesis (per `~/.claude/rules/prior-art-first.md`)

**Public options surveyed:**

- **`create-expo-app --template blank-typescript`** — minimal TS starter (App.tsx + tsconfig + Expo config). No testing infrastructure, no CI, no observability, no audit stack. Great baseline; missing everything downstream.
- **`obytes/react-native-template-obytes`** — comprehensive community template (i18n via i18next, react-query, react-hook-form, NativeWind/Tailwind, Storybook, EAS Update, Sentry, jest + Maestro). Well-maintained but opinionated on styling (NativeWind lock-in) and coupled to obytes' own project shape. Would require heavy pruning.
- **`infinitered/ignite`** — MobX-State-Tree + MMKV + generators. Opinionated on state management (MobX not chosen by the operator historically). Heavy.
- **Existing `C:\Users\deban\dev\mobile-apps\_template\`** — Expo SDK 56 minimal starter used by `bootstrap_mobile_app.py`. No tests, no CI, no HARDENING.md.

**Recommended architecture (adopted):**

Neither community template ships the workspace-specific layer this workspace requires (Python acceptance gates hitting a paired backend's `/api/health`, `mobile_apps/registry.json` integration, workspace SAST alignment, audit-stack HARDENING template, Nick-Saraev 2-pass security audit). Building a workspace-native template on the same shape as the existing `_template` (SDK 56 + TS + minimal deps) and overlaying (a) testing infra (b) CI (c) observability scaffolds (d) audit templates gives a strict superset of `_template` without the ideological baggage of obytes/ignite. Operators who want NativeWind/i18n/etc. can layer them on afterward.

Time cost of the pass: ~10 minutes (memory + prior workspace context).

---

## Additions vs `_template`

**New directories:**
- `src/screens/`, `src/components/`, `src/lib/`, `src/hooks/`, `src/services/` — conventional structure so screens don't sprawl at repo root.
- `tests/unit/`, `tests/e2e/` — jest + Maestro respectively.
- `.github/workflows/` — CI.

**New files:**
- `app.config.ts` — TypeScript config over static `app.json`; reads env vars for Sentry/PostHog wiring, exposes `extra` block.
- `eas.json` — extended from `_template`'s version: adds `preview` iOS simulator build, `production` auto-increment, `submit` profiles for Apple + Google.
- `.gitignore` — adds EAS build artifacts (`.easignore`, `dist/`, `web-build/`), `.env`, coverage.
- `.env.example` — required + optional env vars with inline docs.
- `jest.config.js` + `jest.setup.ts` — jest-expo preset, React Native Testing Library helpers.
- `tsconfig.json` — extends `expo/tsconfig.base`, strict mode on, path aliases (`@/*` → `src/*`).
- `src/services/api.ts` — reference client for calling paired backend (matches Phase 4a web template's `functions/api/` shape).
- `src/lib/analytics.ts` — PostHog stub, env-gated (no-op when `EXPO_PUBLIC_POSTHOG_KEY` absent).
- `src/lib/notifications.ts` — Expo Notifications scaffold with permission flow.
- `src/lib/deeplinks.ts` — Linking prefixes + config example.
- `src/lib/query-client.ts` — react-query with AsyncStorage persistence for offline-first behavior.
- `src/lib/sentry.ts` — env-gated Sentry init.
- `src/hooks/useApiHealth.ts` — reference react-query hook consuming `api.ts`.
- `src/screens/HomeScreen.tsx` — starter screen wiring `useApiHealth` to demonstrate the whole stack.
- `App.tsx` — replaces `_template`'s minimal App.tsx; sets up QueryClientProvider + Sentry + Navigation stub.
- `tests/unit/HomeScreen.test.tsx` — starter jest test proving the whole stack renders.
- `tests/e2e/flow.yaml` — Maestro spec (Maestro chosen over Detox: no native build required, Windows-friendly, YAML flows).
- `tests/e2e/README.md` — Maestro install + run instructions, tradeoff vs Detox documented.
- `tests/acceptance_{{APP_SLUG}}.py` — Python-based acceptance gate: `curl /api/health` on paired backend + validate the data-shape the mobile app depends on. Per the `output-acceptance-gate` rule.
- `tests/front_door_{{APP_SLUG}}.sh` — hits deployed backend + validates OTA update channel returning the expected manifest.
- `.github/workflows/preflight.yml` — on every PR: `npm ci` + `npm run typecheck` + `npm run test:unit` + `npx expo doctor` + `npx expo lint`.
- `.github/workflows/eas-build.yml` — on tag push (`v*`): kicks off EAS build for iOS + Android production profiles.
- `HARDENING.md` — mobile-specific sections: App Store review status, TestFlight tester status, Play Console gate, crash-free rate threshold, ANR rate threshold, OTA rollback plan, cost estimates in EUR.
- `HANDOFF.md` — explicit note: **do not** write "shipped/live/ready" until submitted AND accepted by reviewers.
- `SECURITY_AUDIT.md` — 2-pass checklist (dependency + runtime + PII + auth + storage + network + iOS-specific + Android-specific).
- `README.md` — template README (this file's sibling).

**Modified files (vs `_template`):**
- `package.json` — adds jest, `@testing-library/react-native`, `@testing-library/jest-native`, `jest-expo`, `@sentry/react-native`, `posthog-react-native`, `@tanstack/react-query`, `@tanstack/query-async-storage-persister`, `@tanstack/react-query-persist-client`, `expo-linking`, `expo-notifications`, `expo-constants`. Adds test/lint/typecheck scripts.

---

## Rationale for specific choices

- **Maestro over Detox** — Detox requires native builds and a macOS-side CI runner for iOS. Maestro runs YAML flows against installed builds and is Windows-friendly. Tradeoff: less introspection than Detox, no direct access to app internals. Fine for smoke/critical-path flows.
- **Expo SDK 56 + RN 0.85.3 + React 19** — matches existing `_template` versions so both scaffolders produce apps on the same runtime. When operator wants to upgrade, upgrade both scaffolders in lockstep.
- **`app.config.ts` over `app.json`** — TypeScript config gives type-safety, env-var interpolation, and conditional Sentry/PostHog wiring without JSON gymnastics.
- **react-query with AsyncStorage persistence** — offline-first default. Cache survives app restarts. Users see stale-but-usable UI while refetches happen in the background.
- **EAS Cloud builds only** — the operator is on Windows. No Xcode. EAS Cloud handles both iOS and Android from a Windows dev machine. Preview builds distribute via `expo-dev-client`; production via TestFlight + Play Internal Testing.

---

## Deliberately NOT included

- **State management library** (Redux, Zustand, MobX) — pick per-app. Adding one to the template locks operators in.
- **Styling library** (NativeWind, styled-components, Tamagui) — pick per-app.
- **i18n scaffold** — most first-app builds don't need it. Add on demand.
- **Auth scaffold** — depends heavily on backend (Supabase Auth ≠ custom JWT ≠ Firebase). The scaffolder's `--backend-stack` flag lets follow-up directives layer auth appropriately.
- **Storybook** — heavy; per-app decision.
- **NativeWind / Tailwind** — obytes template locks this in; we don't.

If a specific app needs any of the above, layer it after scaffolding — the template intentionally leaves style / state / auth choices to the app author.
