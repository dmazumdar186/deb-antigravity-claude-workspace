# E2E tests (Maestro)

**Choice: Maestro over Detox.**

- **Maestro** — YAML flows, black-box, runs against installed builds (dev-client / preview / production APKs). No native build required from the test runner. Windows-friendly.
- **Detox** — grey-box, native, requires `react-native run-ios` / `run-android` from a Mac / Linux CI runner. iOS testing from Windows is impractical.

Tradeoff: Maestro cannot inspect internal React state; it drives what a human user drives (tap, swipe, text input, screen matching). For deeper unit-level guarantees, rely on the jest suite; for smoke + critical-path flows on a real device / simulator, Maestro is the right layer.

## Install (per-workstation)

```bash
# Windows: use WSL or Git Bash + Java 11+ installed
curl -Ls "https://get.maestro.mobile.dev" | bash
maestro --version
```

Docs: https://maestro.mobile.dev/

## Run

```bash
# 1. Build + install a dev-client build (Android)
npx expo run:android --variant=release
# 2. Launch it, then:
maestro test tests/e2e/flow.yaml
```

For iOS: EAS-build a preview `.app` file, install to a simulator, then `maestro test tests/e2e/flow.yaml`.

## CI integration

Maestro Cloud (paid) runs the yaml against real devices. For local-only + free, run against a headless Android emulator on any Linux CI runner. iOS CI runs are out of scope for the free path — smoke iOS locally, gate release on TestFlight review.
