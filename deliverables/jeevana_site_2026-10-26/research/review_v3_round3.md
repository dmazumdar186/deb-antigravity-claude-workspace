# v3 jury round 3 (2026-10-26) — "nearly there". Three items + confirmation-pass items. Assertion per item.
1. cover-s3: rail says 04 Aśva Sañcālanāsana / inhale while the film still shows Praṇāmāsana → the film time and the state
   are out of step. Root-cause (eased seek not settled at capture? state index off by one vs `keyframes_s`? beat windows
   15/70/15 mapping?). Assert at every state screenshot after settle: |currentTime − keyframes_s[state]| ≤ 0.3 s AND the
   rail state equals the state derived from currentTime; screenshots are taken only after `seeked` fires and the time
   is within tolerance.
2. Banding in the desktop sky (horizontal stripes in the purple, worst 150–450 px and behind the rail) → dither: an SVG
   feTurbulence noise overlay at 5–7 % over the whole stage (not only the window), the stage gradient built from the
   plate's stops with ≥ 12 stops (no 3-stop CSS gradient), and the film re-encoded with `-crf 20` and `-tune grain` (or
   `-x264-params aq-mode=3`) so the sky in the video does not band. Assert: on 1440p-s0 the stage column at x = 200 has no
   run of ≥ 12 identical rows between y 150 and 450 (sample luminance).
3. dialog sheet: hard top edge slicing the chapter still at y≈518 → feather the sheet's top edge (mask-image 64 px) or
   start it below the still; assert no luminance step > 6 % along the sheet's top edge.
