# Panel lens 1 — Karpathy (measurement) — verdict: WARN

Measured by me (wc, md5sum, Pillow, WCAG 2.x luminance formula on CSS hex). Asserted = taken from harness JSON, not re-run.

## Findings
1. **Sizes reproduce exactly.** `wc -c`: index.html 24,072; styles.css 35,319; main.js 22,824; i18n.js 14,654; backdrop.js 4,926 = functional.json `sizes`. Measured.
2. **43/43 pass is self-reported.** functional.json has 43 results, all `ok:true`; I did not re-run them (no browser). 1 of 43 (`mobile bottom bar appears`) carries no `info`; four console checks carry empty `info`, so a pass is indistinguishable from "listener never attached".
3. **"0 console errors"** sample = desktop, mobile, iPhone 13, newsletter, pitch (functional.json) + 75 screenshots with `consoleErrors: []` (screens.json). Brief asked desktop + Pixel 7 + iPhone 13: no Pixel 7 console assertion exists. Local CSP server only; no production URL, no Safari/WebKit-real device. Falsifier: any error on the deployed origin or real iOS Safari.
4. **"Within three scrolls"** — page heights are asserted, not measured by me: desktop 6,465 px (≤ 7,000 budget), mobile 4,844 (≤ 9,000). "Three scrolls" is defined as three tracks, not three viewport-heights: 6,465 px at a 900 px viewport ≈ 7.2 screens. Falsifier: a user-count of wheel/flick gestures to reach Contact > 3 on a stated viewport — never measured.
5. **Image frames are duplicated.** md5: sn-02 = sn-11, sn-03 = sn-10, sn-05 = sn-08 (both desktop and -m). The "12-frame sequence" has 9 unique frames. 52 raster assets dimensioned; desktop 9:16 at 900x1600, mobile 562x1000; photo-01 is 330 KB (largest).
6. **Contrast (computed):** ink/paper 15.05, ink-2 9.48, muted/paper 4.77, muted/card 5.51, sun-text kicker 4.72, numerals (sun-text) 4.72 — PASS. Rail on cover gradient: cream 13.6–16.3, cream-2 9.2–11.0, `#E9B26F` 8.3–9.9 — PASS. **Rail label `--amber #B07A1C` on `#2A211A` = 4.24 (FAIL for 10–13 px text)**; 5.06 on `#14110E`. Over the photo, the rail scrim (`rgba(15,12,10,.62)` fading to 0) gives worst-case cream-2 3.25 at full scrim and ~1.2 mid-fade over a bright sky. `#C4731A` and amber on paper are 3.1–3.2 — must stay marks-only.

## Honest gaps
- No browser run by me; every runtime number (heights, 43 passes, console) is trust-the-harness.
- Contrast over the photo depends on actual pixels under the rail; I computed bounds, not per-frame samples. Falsifier: sample hero frame luminance under the rail box per breakpoint.
- One sample per viewport, one run; no variance, no real devices, no throttled network.
