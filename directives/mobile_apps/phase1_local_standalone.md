# Phase 1 — Local Standalone Expo App

## Goal

Ship a runnable Expo TypeScript app on the user's phone via Expo Go in under an hour. State is local (AsyncStorage + React Context), zero network, zero external deps beyond Expo defaults + `@react-native-async-storage/async-storage`. This is the foundation every later phase builds on.

## Inputs

- App slug (kebab-case, from `bootstrap_mobile_app.py`)
- App spec from user — one paragraph naming: domain (notes? habit tracker? recipe log?), 2-4 core screens, what state each screen reads/writes
- Already-cloned per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\` (Expo blank TypeScript template via `bootstrap_app_repo.md`)

## Tools/Scripts

- `execution/mobile_apps/bootstrap_mobile_app.py` — must have already run; this directive assumes the repo exists
- `npx expo start` — launches Metro bundler + QR code
- Expo Go (user's phone) — scan QR, no native build needed
- `@react-native-async-storage/async-storage` — only third-party dep allowed in Phase 1

## Steps

1. **Confirm repo state.** `cd C:\Users\deban\dev\mobile-apps\<slug>` ; verify `package.json`, `app.json`, `tsconfig.json`, `src/state/Context.tsx` are present from the template.
2. **Install AsyncStorage.** `npx expo install @react-native-async-storage/async-storage`. Use `expo install` not `npm install` so the version matches the Expo SDK.
3. **Define the state shape.** In `src/state/types.ts` declare a TS interface for the app's persistent state (e.g. `interface AppState { tasks: Task[]; lastOpenedAt: string }`). Keep it flat — Phase 3 migrates to SQLite for anything nested.
4. **Wire the Context provider.** `src/state/Context.tsx` exports `<AppStateProvider>` + `useAppState()` hook. Provider:
   - On mount: `AsyncStorage.getItem('app_state')` → JSON.parse → set state. If null or parse-fail, use initial state.
   - On every state change: debounced (300ms) `AsyncStorage.setItem('app_state', JSON.stringify(state))`. Never write on every keystroke.
5. **Wrap the app.** `App.tsx` mounts `<AppStateProvider>` around the root navigator.
6. **Add screens.** One file per screen in `src/screens/<ScreenName>.tsx`. Use the user's app spec to name them. Each screen: imports `useAppState`, reads/writes its slice, renders a minimal RN UI (`<View>`, `<Text>`, `<TextInput>`, `<Pressable>`).
7. **Navigation.** If the app has > 1 screen, `npx expo install @react-navigation/native @react-navigation/native-stack react-native-screens react-native-safe-area-context`. Stack navigator only; no tabs/drawers in Phase 1.
8. **Local boot test.** `npx expo start`. Scan QR with Expo Go. Confirm every screen renders, state persists across kill/relaunch.
9. **Commit.** `git add . && git commit -m "phase 1 — local standalone with AsyncStorage"`.

## Outputs

- Running app reachable via Expo Go (QR scan)
- `src/state/Context.tsx` + `src/state/types.ts` — single source of state truth
- `src/screens/<*>.tsx` — one file per screen
- AsyncStorage key `app_state` populated on first run
- Phase 1 commit in the app repo

## Edge Cases

- **Offline mode.** AsyncStorage is local; nothing to handle. Just ensure no fetch calls leak into Phase 1.
- **App restart preserves state.** Tested in step 8 — kill app, reopen, confirm last state intact.
- **AsyncStorage size limit** is ~6 MB on Android, larger on iOS. Phase 1 apps with photo storage or large text logs will exceed this fast → migrate to Phase 3 SQLite earlier than expected.
- **Debounce drop on rapid kill.** If user types 10 chars and immediately force-quits, the 300ms debounce may not have flushed. Acceptable for Phase 1; Phase 3 fixes via per-mutation SQLite writes.
- **`JSON.parse` failure on corrupted AsyncStorage.** Wrap in try/catch, fall back to initial state, log to console — never silently swallow. The `except Exception: pass` ban from CLAUDE.md applies in JS too.
- **Expo Go SDK mismatch.** If the user has an older Expo Go on their phone, the QR scan will say "this project requires SDK X". Either pin the SDK in `app.json` to match Expo Go, or have the user update Expo Go.
- **Hot reload eats state.** When Metro hot-reloads, the Context provider re-mounts and re-reads from AsyncStorage — usually fine, but state-mid-typing can flash. Acceptable for dev; never ship hot-reload to TestFlight.

## Notes

- This phase is the **single fastest** in the pipeline. If the sub-agent spends more than 30 minutes here, something is wrong — pause and ask.
- Do not introduce a state library (Redux, Zustand, Jotai) in Phase 1. Context + AsyncStorage is sufficient for ≤4 screens. Phase 3 SQLite supersedes Context for larger data.
- Anneal classic mode runs after this phase via the `/mobile-app` skill.
