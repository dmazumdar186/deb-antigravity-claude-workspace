# Jev Feed Filter Extension (use case 12)

## Goal
A Manifest V3 Chrome extension that asks Jev "is this AI slop?" for every post as it loads on X / LinkedIn
and folds the slop away, plus an optional Unclutter mode that hides ads, cookie banners and promo overlays
on any page.

## Operator prompt
"Install the Jev feed filter extension"

## Inputs
- OpenRouter key (`OPENROUTER_API_KEY`), pasted once into the extension Options page (`chrome.storage.local`).
- Toggles: slop filter (default on), unclutter (default off), threshold (default 0.70).

## Tools
- `execution/infrastructure/jev_feed_filter_extension/` - the extension (no build step). `jev_api.js` is the
  shared batching / question-building module; README has the details.
- `execution/infrastructure/jev_feed_filter_extension/test/smoke.mjs` - unit + live + Playwright smoke.
- `tests/test_jev_feed_filter_extension.py` - manifest validation + `node test/smoke.mjs --offline`.

## Steps (install)
1. `chrome://extensions` -> Developer mode -> Load unpacked -> the extension folder.
2. Options: paste the OpenRouter key, set toggles/threshold, Save.
3. Open x.com; folded posts show "Folded by Jev (p) - show".

## Outputs
Collapsed posts / hidden elements in the browser; session counters (checked, folded, cost) in the popup.

## Edge cases
- Fail-open everywhere: missing key or any API error hides nothing.
- One Jev call per batch of <= 20 items; ~$0.0001 per 20 posts. Cache by text hash (memory only).
- Headless testing: Playwright's `chromium-headless-shell` cannot load extensions; use `channel: "chromium"`.
  `page.route` does not see service-worker fetches, so the test stubs `self.fetch` inside the worker.
- Privacy: post text goes to OpenRouter/TypeSafe.

## Changelog
- 2026-10-07: Created. Live 6-post check: slop 0.97/0.88/0.97, genuine 0.05/0.03/0.02 (cost $0.00005).
