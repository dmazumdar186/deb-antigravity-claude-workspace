# Phase 1 — Local Standalone Expo App

## Goal

Ship a runnable Expo TypeScript app on the user's phone via Expo Go in under an hour, then validate it across the 3-tier testing protocol (Chrome web → mirror → real phone). State is local (AsyncStorage + React Context), zero network, zero external deps beyond Expo defaults + `@react-native-async-storage/async-storage`. This is the foundation every later phase builds on.

## Inputs

- App slug (kebab-case, from `bootstrap_mobile_app.py`)
- **App spec** at `C:\Users\deban\dev\mobile-apps\<slug>\APP_SPEC.md` — produced by `directives/mobile_apps/app_design.md` (5-principle framework). If missing, run the design directive first; this phase does not handle ideation.
- Already-cloned per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\` (Expo blank TypeScript template via `bootstrap_app_repo.md`)

## Tools/Scripts

- `execution/mobile_apps/bootstrap_mobile_app.py` — must have already run; this directive assumes the repo exists
- `npx expo start` — launches Metro bundler + QR code (mobile testing)
- `npx expo start --web` — launches the same app in Chrome (fast iteration, no phone needed; Nick's preferred dev loop per transcript chapter 14)
- Expo Go (user's phone) — scan QR, no native build needed
- iPhone mirroring app (macOS) or scrcpy (Windows → Android) — second testing tier between web and real phone
- `@react-native-async-storage/async-storage` — only third-party dep allowed in Phase 1
- `react-native-web`, `react-dom`, `@expo/metro-runtime` — required for `expo start --web`; pre-installed in the template per `_template/package.json`

## Steps

1. **Confirm repo state.** `cd C:\Users\deban\dev\mobile-apps\<slug>` ; verify `package.json`, `app.json`, `tsconfig.json`, `src/state/Context.tsx` are present from the template. Read `APP_SPEC.md` — every later step references it.
2. **Install AsyncStorage.** `npx expo install @react-native-async-storage/async-storage`. Use `expo install` not `npm install` so the version matches the Expo SDK.
3. **Define the state shape.** In `src/state/types.ts` declare a TS interface for the app's persistent state (e.g. `interface AppState { tasks: Task[]; lastOpenedAt: string }`). Keep it flat — Phase 3 migrates to SQLite for anything nested.
4. **Wire the Context provider.** `src/state/Context.tsx` exports `<AppStateProvider>` + `useAppState()` hook. Provider:
   - On mount: `AsyncStorage.getItem('app_state')` → JSON.parse → set state. If null or parse-fail, use initial state.
   - On every state change: debounced (300ms) `AsyncStorage.setItem('app_state', JSON.stringify(state))`. Never write on every keystroke.
5. **Wrap the app.** `App.tsx` mounts `<AppStateProvider>` around the root navigator.
6. **Add screens.** One file per screen in `src/screens/<ScreenName>.tsx`. Take screen names directly from `APP_SPEC.md` § Surface Area (≤7 screens). Each screen: imports `useAppState`, reads/writes its slice, renders a minimal RN UI (`<View>`, `<Text>`, `<TextInput>`, `<Pressable>`).
7. **Navigation.** If the app has > 1 screen, `npx expo install @react-navigation/native @react-navigation/native-stack react-native-screens react-native-safe-area-context`. Stack navigator only; no tabs/drawers in Phase 1.
8. **3-tier test protocol** (per Nick transcript chapter 14 + 25 — do not skip tiers):
   - **Tier 1 — Chrome web.** `npx expo start --web`. Open in Chrome, set device resolution to mobile in DevTools. Fast iteration loop — zoom way in, click through every screen, watch the console for warnings. Most layout/logic bugs are caught here in seconds.
   - **Tier 2 — Mirror.** macOS: iPhone mirroring app. Windows: `scrcpy` for Android, or just have the user sit next to the laptop with their phone. Catches navigation/touch-target issues you missed on a mouse-driven viewport.
   - **Tier 3 — Real phone.** `npx expo start` (no `--web`). Scan QR with Expo Go on the user's actual phone. Confirm every screen renders, state persists across kill/relaunch, haptics fire (if the core loop spec includes them), no swipe-only flows are hidden.
9. **`/init` the per-app `CLAUDE.md`.** Per Nick chapter 11: now that real code exists in `src/`, the template's placeholder `CLAUDE.md` is stale. In the Claude Code pane inside the app repo, run `/init`. Then `/clear` to reset token usage before Phase 2.
10. **Commit.** `git add . && git commit -m "phase 1 — local standalone with AsyncStorage"`.
11. **Push to GitHub.** Per Nick chapter 15 — version control is the safety net for AI-driven edits in Phase 2+. In Claude Code: ask "create a GitHub repo for this and push, include a README". This opens the GitHub auth flow if needed and pushes the Phase 1 commit. Confirm the repo URL is reachable; if the user prefers private, set visibility before push. (If the user is uncomfortable putting the code on GitHub, `git init` alone is fine — but every later phase assumes a remote exists for rollback.)

## Outputs

- Running app reachable via Expo Go (QR scan) AND Chrome (`expo start --web`)
- `src/state/Context.tsx` + `src/state/types.ts` — single source of state truth
- `src/screens/<*>.tsx` — one file per screen
- AsyncStorage key `app_state` populated on first run
- Per-app `CLAUDE.md` regenerated by `/init` (replaces the template placeholder)
- Phase 1 commit pushed to GitHub remote (rollback safety net)

## Edge Cases

- **Offline mode.** AsyncStorage is local; nothing to handle. Just ensure no fetch calls leak into Phase 1.
- **App restart preserves state.** Tested in step 8 tier 3 — kill app, reopen, confirm last state intact.
- **Web tier shows bug that mirror/phone hide (or vice versa).** Don't skip the failing tier. Web tier exposes React rendering bugs; phone tier exposes haptic / camera / push-notification issues web can't simulate. If a bug is web-only, suspect `react-native-web` polyfill drift (e.g. `Pressable` event semantics).
- **`/init` regenerates `CLAUDE.md` that contradicts the template's.** Trust `/init` — the template's was placeholder text and the regenerated one reflects real code. If the regenerated one omits something important (e.g. notes about EAS Build), add it back manually.
- **User skipped GitHub push.** Phase 2 onward will still work, but rollback after a bad AI edit becomes "delete the whole working tree and re-bootstrap". Flag this once and proceed.
- **AsyncStorage size limit** is ~6 MB on Android, larger on iOS. Phase 1 apps with photo storage or large text logs will exceed this fast → migrate to Phase 3 SQLite earlier than expected.
- **Debounce drop on rapid kill.** If user types 10 chars and immediately force-quits, the 300ms debounce may not have flushed. Acceptable for Phase 1; Phase 3 fixes via per-mutation SQLite writes.
- **`JSON.parse` failure on corrupted AsyncStorage.** Wrap in try/catch, fall back to initial state, log to console — never silently swallow. The `except Exception: pass` ban from CLAUDE.md applies in JS too.
- **Expo Go SDK mismatch.** If the user has an older Expo Go on their phone, the QR scan will say "this project requires SDK X". Either pin the SDK in `app.json` to match Expo Go, or have the user update Expo Go.
- **Hot reload eats state.** When Metro hot-reloads, the Context provider re-mounts and re-reads from AsyncStorage — usually fine, but state-mid-typing can flash. Acceptable for dev; never ship hot-reload to TestFlight.

## Notes

- This phase is the **single fastest** in the pipeline. If the sub-agent spends more than 30 minutes here, something is wrong — pause and ask.
- Do not introduce a state library (Redux, Zustand, Jotai) in Phase 1. Context + AsyncStorage is sufficient for ≤4 screens. Phase 3 SQLite supersedes Context for larger data.
- Anneal classic mode runs after this phase via the `/mobile-app` skill.
