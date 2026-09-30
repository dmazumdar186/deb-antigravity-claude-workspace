# Human-eye run r1 (2026-09-29) — consolidated defects. Owner: fix everything not marked "accept".
Screenshots: .tmp/human_eye/r1/<file>. Both editions unless stated.

## P1
1. Package table on phones (≤700px card layout) shows "Standard ✓ · Premium: ask us" — old names via CSS generated content / data attributes. Must read "Premium posting ✓ · Membership: ask us" (ie_employers-table_390_*, uk_employers-table_390_*; functional walk B2 FAIL).
2. Map side list at 1440/1024: chips clipped to "Ec…", "Mi", "Se"; some chips show only "£"/"€" or a bare dot (ie_jobs-map_1440_*). Cause: nowrap+ellipsis rule at narrow widths + fx glyph chip when label empty. Fix: in the map list render location badge + ONE full sector chip on its own line (allow the chip text to wrap, dot fixed), never a currency glyph without a label.
3. Insights vs salary guide disagree: 29 disclosed (33%) vs 27 (31%), band counts differ (ie_insights_1024_*). Cause: guide excludes the 2 unverified roles, insights does not. One rule everywhere (exclude unverified) and one shared computation.
4. Unverified job page (ie/jobs/11496364): Scotland role shows € with the caveat only in the sidebar; description shows raw "*" bullets; closed state only in sidebar. Fix: caveat line directly under the salary chip in the header; render "* " lines as a list; "Closed" chip in the header.

## P2 (new features)
5. Employers page sticky header: page heading text bleeds through behind the logo at 1024/1440 — make the header background opaque (ie/uk_employers-preview_1024/1440).
6. At 1024 the Post-a-job form squeezes: file input "No …sen", title "nior Hydrogeologist" — stack the row at ≤1100px, file input full row.
7. Table: check icons sit below the "Included" baseline — vertically centre; header row hidden under the sticky site header when scrolled (add scroll-margin/top offset); "Ask us" in both columns on two rows reads unfinished — add a one-line footnote under the table: "Featured employer and newsletter sponsorship are quoted per campaign."
8. "See your vacancy as candidates will" → "See your vacancy as candidates see it". Preview heading font must match the site display font.
9. Long-JD example text: the fill example must match the title/salary (no "Senior Ecologist" text under a "Senior Hydrogeologist" title, no Lorem ipsum) — the plan's test text is ours, but make the built-in example consistent; description renderer: normalise CRLF, split paragraphs on /\n\s*\n/, render lines starting with "•", "-", "*" as <ul>.
10. Employers page hero buttons at 390 are three different widths — full width, same height; orange arrow → text colour.
11. Reply draft / labels: "candidates see it exactly as written" → "shown as plain text, paragraphs and bullet lines kept" (label + brief §9).

## P2 (rest of site)
12. Dark theme: List/Map/Saved active tab has no highlight (ie/uk_jobs_*_dark).
13. 404 page ignores dark theme (root_404_*_dark).
14. Jobs page intro "Everything you set lives in the address bar…" is developer voice → "Filter by sector, county, salary and more. Your filters stay in the link, so you can share or bookmark a search."
15. Sector select truncates "Sustainable infrastructu" — allow the select to size or use a shorter option label with title.
16. Toolbar: "Quick job match" and "Jump to ⌘K" float apart — group them right-aligned; "Mid-level" chips wrapping alone at 1440 (make .row__meta inline wrap with consistent chip height; the card heights vary at 1024).
17. Job pages at 390: salary chip wraps and splits "£4.4k–/5.1k"; sticky bar squeezes salary into 4 lines — sticky bar shows the short "£45k–55k" only; chip text must not break inside a range (use non-breaking hyphen/en dash + nowrap on the range span).
18. Job card meta: orphaned "·" at line end (uk_jobs_390) — keep the separator with the following item (nowrap span).
19. "UK/ Ireland" spacing in a title (source data) → normalise "UK/ Ireland" → "UK/Ireland" at import.
20. Carousel edge fade on dark theme is a light smear — mask must fade to transparent (mask-image is fine; the fallback gradient uses paper colour: use currentColor/var(--bg)).
21. Reduced-motion carousel fallback: two grids with a short centred row; at 390 single column — one grid, 2 columns at 390, 3 at 768, 6 at 1440, no gap between halves.
22. UK home hero: turbine blade cuts through the sub-line "Search environmental…" and poles run through the stats strip — the drawn scene must sit behind a paper scrim under text (raise z-index of copy, add subtle backdrop to the stats strip).
23. Subscribe modal note "Job alerts… available on greenjobs.ie today: sign up on greenjobs.ie" reads doubled — "Job alerts are available today on greenjobs.ie (link)." Cookie bar must hide while a modal is open.
24. Cookie settings: Analytics "Not used on this site" and bare "Marketing: Off" look pointless — show only Essential (on) and Analytics (off, "reported once analytics is connected"); drop Marketing.
25. Landing pages intro reads like SEO copy ("…in EUR", "led by Dublin, Cork", "rebuilt from the live board") → plain language, ≤60 words, no build talk.
26. Sectors treemap: labels cut ("Environment…"), two count formats ("Waste 6" vs "12 roles") — one format "12 roles", hide labels under 90px (legend carries them); 390 list second-line indent.
27. Sectors intro "No empty categories." → delete.
28. Insights: dark theme bars lack a track; € labels misaligned with bars; stat line repeats the subtitle; empty band card area; y-axis labels 15/8 → nice ticks; "100k+" empty band hidden when 0.
29. Guides page: content column narrower than header; numbers not right-aligned under "Roles".
30. Dashboard: second tile row leaves a 2-slot gap (make rows even), "Advertised window (median days)" label wraps → "Advertised window, days".
31. Compass dark: A–F letter badges lose their background.
32. UK job page (uk/jobs/11490688): no logo while other pages show one → monogram placeholder; euro job description: every line bold with big gaps (source formatting) → normalise imported description: strip <strong> wrapping whole lines, collapse >1 blank line; two location chips saying the same → dedupe.
33. Home stats strip: "Snapshot of 22 September 2026" pill overruns the bar at 1440 light — fit inside or wrap.
34. Job alerts strip on uk_home_1024_light captured blurred (fade-in mid-animation) — ensure the strip is not animated on load.
35. ie_jobs_1440_light: dark strip along the bottom edge — find and remove.

## Harness / tests (rigor lens)
36. human_eye_shots.cjs: log line must include the h1 condition; overflow check should also inspect body/inner scroll containers; the functional walk must open the mobile preview toggle and filter sheet before filling (walk.js crashed twice on hidden controls).
37. Add test_adbuilder_desc_renders_and_escapes (node): "<script>" → "&lt;script&gt;", single newline → <br>, blank line → 2 <p>, bullet lines → <ul>.
