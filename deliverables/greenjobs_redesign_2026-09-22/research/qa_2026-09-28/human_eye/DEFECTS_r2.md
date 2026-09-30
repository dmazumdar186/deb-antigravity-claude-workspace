# Human-eye run r2 — remaining defects after fix round 1 (2026-09-29). Fix all; both editions.
Round-1 items confirmed fixed: package table Premium/Membership on all viewports incl. phone cards; preview description paragraphs/bullets/escaping; sticky header opaque; check icons centred; insights = guides (27/31%); List tab dark; 404 dark; subscribe note; cookie bar under dialogs; sterling chip one line; unverified caveat + Closed chip; jobs intro copy; UK fields at 1024; logos on every job; job alerts strip; all rates links are mailtos.

## P1
1. uk_jobs_390: card meta wraps to a line starting with "· Hertfordshire" — the separator must travel with the following item (wrap the "· item" pair in one nowrap span; the round-1 fix kept the dot with the wrong side).

## P2
2. Carousel edge fade on DARK still a grey→white smear on the edge tiles (ie_home-carousel_1440/1024/390_dark). The mask must be a pure alpha mask on the .marq element (mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)); remove any overlay gradient element/pseudo-element or paper-coloured fade; verify by screenshot on dark.
3. Cookie settings Analytics row "Off; reported once analytics is connected" → "Off. Helps us see which pages are useful." Dashboard copy in visitor voice everywhere: remove "edition switch in the header keeps you on this page", "reported once an analytics provider is connected" → "Reported once analytics is switched on", "set from the full listing text by the same rule as the board's Workplace filter" → "Roles whose advert mentions remote or hybrid working". Move "Top employer share" and "Agency share" tiles out of the first row (after the salary tiles) — data stays.
4. Package table: first column header "Included" → "What you get"; header cells padded like row cells; Membership column: per brief.md, a membership is a bundle of Premium postings at a discounted rate with the self-management system, so every row that is Included for Premium is also Included for Membership (tick them), plus the two membership-only rows; keep "Ask us" only where Premium is "Ask us". Footnote: "Membership: a bundle of Premium postings at a discounted rate, with the self-service posting system and telephone training."
5. Sterling job page (ie/jobs/11500760): "Apply on greenjobs.ie" is right (the role is listed there); change the salary-source line to "Salary figure taken from the same advert on greenjobs.co.uk, where it is advertised in sterling." so the two lines don't look contradictory.
6. Map (ie_jobs-map_1440): Northern Ireland label lines overlap — single line "Northern Ireland" with the "see greenjobs.co.uk" as a title attribute; hide "0" count labels on the map.
7. UK euro job page (uk/jobs/11501639) description: opening block still renders as five bold lines with gaps — normalisation must unwrap <strong>/<b> that wraps an entire short line AND lines that are bold + followed by a line break; render "Label: value" openings as a compact list. Also dedupe "Ireland & UK" chip vs location chip on this page.
8. Home hero: B Corp card is translucent and the solar-panel drawing shows through the text (ie/uk_home_1440/1024) — opaque card (paper/dark surface) with a subtle border. Turbine blades cross the sub-line in dark (uk_home_1440_dark) — the hero copy block gets a dark scrim too; at 390 hide turbine stubs under the button.
9. Sectors treemap: the three smallest tiles have no label or count; Policy tile uses dark text while others use light — every tile ≥ 48px gets "Name · N" in one text colour (auto light/dark by luminance), smaller tiles get a title attribute and appear in the legend below (legend exists).
10. Preview headings on the employers page: use the site display font at the same weight as page h2/h3 (reviewer still sees a heavier serif); min and max salary inputs identical (both type=number with the same appearance).
11. Fill-with-example text: add a three-line bullet block ("• Lead site investigations…", etc.) so the preview demonstrates the list rendering.

## P3
12. 404 light: remove the extra "Choose an edition" button (the two cards are the choice); footer shows a double rule — single.
13. Insights 390: band axis labels too small (≥ 11px).
14. Unverified job page: "The Role" style plain-text headings (short bold line without trailing period) → render as h3.
15. Landing page card meta: "Commonland  Dublin" needs the same "·" separator as the jobs list.
16. Jobs-fit: 12px more space between the "Quick job match" heading and its intro. Compass 1440: intro aligned to the quiz column.
17. Home 1024 (both editions): snapshot pill wraps alone to a second row — let it sit inline (smaller) or right-align.
18. uk_insights: "Median by sector" bars end unevenly because the value label width varies — fixed-width value column.
19. Job cards at 1024: heights differ when the salary chip wraps — chip row min-height/consistent wrap.
20. Employers preview at 390: large gap between location and chips on the board card.
