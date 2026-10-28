# Panel lens 4 — research rigor (2026-10-26)

**Verdict: PASS with fixes.** The weak spot is definitions. Several thresholds live as unnamed literals, and one test name contradicts the code it tests.

## Findings
1. **Test name contradicts the code.** `research/functional.mjs:75` claims beats change "at 25/50/75%". But the probes are `[0.05, 0.3, 0.7]` (`:12`), and `site/js/main.js:122` maps beats over `coverP / 0.6`. With 3 beats the boundaries fall at 0.20 and 0.40. Rename the test, or make the code match the claim.
2. **"Body >= 60 %" holds only on landscape.** `main.js:55` says ">= ~60 %", but `:60` uses `0.5` for portrait, with a zoom cap of 1.3 when H < 760 (`:62`). The anchors `0.62`/`0.94` (`:63`) and the default box `[0,0.2,1,0.8]` (`:59`) are not named.
3. **The "empty band > 25 %" threshold does not exist in functional.mjs.** The fold-entry check (`:109`) uses `bodyOpacity >= 0.85` and a "last 20 %" in its label, with no named constant.
4. **Unnamed timing literals in main.js:** the 900 ms autoplay step (`:113`), cover end `0.8` (`:125`), `--body` ramp `0.75/0.25` (`:134`), fold open `0.9` (`:149`), cover out `0.2` and mbar `0.5` (`:150-151`), the 2500 ms reveal fallback (`:376`), the 1200 ms deck delay (`:323`). The 35 s timer (`:319`) and `NEWS_KEY='jv-news-seen'` are documented. `jv-lang` appears only in `screens.mjs:24`.
5. **Autoplay runs one cycle and holds** (`main.js:109`, N=12, about 9.9 s). This is not stated anywhere in the brief or HANDOFF.
6. **hero.json fps/seconds are duplicated** as `FPS = 30, SEC = 11` in `main.js:357`, not read from the manifest, so the two can drift.
7. **Body-box method (`ingest_photos.py:48-78`) is deterministic** but hard-coded: 90x160 downsample, a colour-distance cutoff of `60`, mass percentiles 6/94, centroid clamps 0.2-0.8 / 0.3-0.7. WebP `quality=82, method=6` (`:41`) and LANCZOS (`:40`) are pinned. The Pillow version is not.
8. **Viewport matrix** is defined once (`screens.mjs:34`, 18 entries). `functional.mjs:43` re-declares 1440x900 separately. `'mobile': 'Pixel 7'` depends on the Playwright version, which is not pinned.
9. **glm_log.md does not record** temperature, seed, a prompt hash or the prompt text. The 2133 completion tokens cannot be reproduced. Hand edits are not diffed. `compatibility_date` 2026-10-01 is pinned, with no rationale.

## Honest gaps
- I did not run either test script, so the beat boundaries are inferred from the code, not observed.
- HANDOFF "design jury, review round 1, H33" was not checked against `review_round1.md`.
- to_wire.md's "KV created 2026-10-26" and the WhatsApp number cite only "operator". No message or source is linked.
