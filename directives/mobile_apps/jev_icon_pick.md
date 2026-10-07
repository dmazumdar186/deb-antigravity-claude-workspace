# Jev Icon Picking — icon from what the user types (use case 17)

## Goal
In any app that labels items with icons (habit tracker, mood journal, expense categories), pick the icon
from the user's free text with Jev instead of an LLM (costly, slow) or regex keyword matching (weak).
"drink more water" -> `droplet`; "barely slept, dragged myself through the day" -> `battery-low`.

## Operator prompts
- **"Add Jev icon picking to <app>"** -> export the app's icon set as `{name: one-line description}` JSON,
  run `pick` on 5-10 real inputs with `--icons`, run `bench` if the app ships a labelled set, then copy
  `execution/mobile_apps/jev_icon_pick.rn.tsx` into the app repo and wire `JEV_URL` to the proxy route.
- **"Which icon for: <text>"** -> `python3 execution/mobile_apps/jev_icon_pick.py pick "<text>"` (add `--mode mood` for feelings).

## Inputs
- Free text; icon set (default `DEFAULT_ICONS`, ~80 Lucide names, plus implicit `none`); `--mode habit|mood|generic`;
  `--min-confidence` (default 0.4 -> below it the answer is `none`); env `OPENROUTER_API_KEY`.

## Tools/Scripts
- `execution/mobile_apps/jev_icon_pick.py` — `pick_icon()` importable; CLI `pick`, `bench [--compare-regex]`.
- `execution/infrastructure/jev_specs/icon_bench.json` — 24 labelled inputs (4 mood, 2 `none`).
- `execution/mobile_apps/jev_icon_pick_demo.html` — browser demo (habit + mood tabs), key in localStorage.
- `execution/mobile_apps/jev_icon_pick.rn.tsx` — `useJevIcon(text, icons)` hook (debounce 250 ms, abort on new input).
- Tests: `tests/test_jev_icon_pick.py` (offline).

## Outputs
`{icon, confidence, alternatives[top_k], cost, latency_ms, error}`; ledger caller `jev_icon_pick`.

## Key handling (mobile) — hard rule
The OpenRouter key never ships in an app bundle or `EXPO_PUBLIC_*` var. The app calls a proxy route that
injects the key server-side (`execution/infrastructure/api-proxy/` — AM-locked, see `CLAUDE.local.md`;
request a route, do not clone or edit it). The HTML demo's localStorage key is for local demos only.

## Edge cases
- More than 40 options: split into batches of 39 + `none`, top-3 of each batch go to a final call
  (~4 calls, ~1.3 s for 80 icons). Keep app sets <= 39 for one ~0.3-0.6 s call.
- Gibberish/unrelated text: Jev may still pick something for on-topic-sounding nonsense; raise
  `--min-confidence` if false icons are worse than no icon.
- Mood mode with the default set restricts to the 10 mood icons.
- Errors fail open: `icon=None`, `error` set; the UI shows nothing and the user picks manually.

## Benchmarks (2026-10-07, jev-1.13, default 80-icon set)
Jev 96% acc / 96% top-3, 1.3 s mean (two-stage), $0.0033 per 24 inputs. Regex baseline 62% / 71%.
Only miss: "the mitochondria is the powerhouse of the cell" -> `zap` (expected `none`).

## Changelog
- 2026-10-07 — Created (RoboNuggets use case 17): picker, bench, regex baseline, HTML demo, RN hook.
