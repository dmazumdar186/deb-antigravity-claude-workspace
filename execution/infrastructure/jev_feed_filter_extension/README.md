# Jev Feed Filter (Chrome extension, MV3)

Folds AI slop on X / LinkedIn and (optionally) hides ads and cookie banners on any page (Unclutter).
Every decision is a Jev `noul` answer from OpenRouter's Decisions API (`typesafe/jev-1.13`).

## Install (load unpacked)
1. `chrome://extensions` -> enable **Developer mode** -> **Load unpacked** -> pick this folder.
2. Right-click the toolbar icon -> **Options**: paste your OpenRouter key (`sk-or-...`), set toggles
   (slop filter default on, unclutter default off) and the threshold (default 0.70). Save.
3. Open x.com or linkedin.com/feed. Slop posts collapse into a "Folded by Jev (0.91) - show" bar; click to expand.
4. Popup: toggles, session counters (checked / folded / cost) and **Undo all on this tab**.

## How it works
- `content_feed.js` watches `article[data-testid="tweet"]` (X) and `div.feed-shared-update-v2` (LinkedIn)
  with a MutationObserver, dedupes, and sends text (<= 600 chars) in a 300 ms debounced batch.
- `content_unclutter.js` (when enabled) describes fixed/sticky, cookie/banner/promo, `aside`, ad iframes as
  `{tag,id,class,text<=200,position}` and hides those >= threshold (`display:none`, `data-jev-hidden` marker, reversible).
- `background.js` caches per text hash, batches up to 20 items into ONE Jev request
  (`state={items:[{i,text}]}`, questions `slop_<i>` / `junk_<i>`), and tracks `usage.cost`.
- `jev_api.js` is a chrome-free ES module (shared with the Node smoke test).

## Cost
One request covers 20 posts; a live 6-post call cost ~$0.00005, so ~$0.0001-0.0002 per 20 posts.
Repeat posts hit the in-memory cache (cleared when the service worker sleeps).

## Privacy
Post text (and, in Unclutter, element tag/id/class/text) is sent to OpenRouter / TypeSafe. The key is
stored in `chrome.storage.local` on this machine only. Nothing else leaves the browser.

## Limits
- Fail-open: no key, HTTP error or bad answer -> nothing is hidden.
- Selectors track today's X/LinkedIn DOM; they will drift.
- Unclutter is heuristic: at most 40 candidates per pass, two passes (load + 2.5 s).
- Folding never removes nodes; it only sets `display:none` behind a bar.

## Test
`node test/smoke.mjs` (unit + one live Jev call + headless Chromium with the extension loaded;
OpenRouter is stubbed inside the service worker). `--offline` skips the live call.
