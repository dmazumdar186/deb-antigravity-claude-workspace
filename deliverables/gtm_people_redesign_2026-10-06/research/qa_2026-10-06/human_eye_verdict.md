# Human-eye test verdict — GTM People redesign (live), 2026-10-06

Target: https://gtm-people-redesign.pages.dev/ (`/` scroll-story, `/deck/` tabbed cut, `/for-ian/` pitch).
Tooling: Playwright 1.x / Chromium 1194, real fonts (live URL). Scripts and raw data in this folder:
`shots.cjs` (tier 2+3), `walk.cjs` + `probe2.cjs` (tier 5 probes), `shots_log.json`, `shots_log_d1440.json`, `walk_log.json`, `tier1_site_check.txt`.
127 PNGs in this folder (gitignored). Nothing was fixed; nothing committed.

**Verdict: FAIL — not releasable.** 3 × P1, 12 × P2, 8 × P3 (23 defects, all open). The operator-reported numeral/title overlap on the roles stack is reproduced and root-caused below; reduced-motion mode is broken outright; the roles stack puts pricing 47 screens below the fold.

---

## Tier results

| Tier | Result | Count |
|---|---|---|
| 1 Automated (`site_check.mjs` + URL smoke) | PASS | 26/26 checks ok (desktop, pixel7, iphone13, pixel7-reduced: no overflow, reveals shown, tap targets, inputs ≥16px, bottom bar clear, console clean). Smoke: `/`, `/deck/`, `/for-ian/`, `/css/styles.css`, `/js/main.js` → 200. |
| 2 Layout regression (live geometry probes, 3 viewports) | FAIL | 3 viewports × 9 probes. Fails: numeral/text intersection on 10 of 25 role cards at 1440×900 (0 at 1024); tier-card heights unequal at 1024 (416/438) and 390 (438/461); smallest `.btn` 41 px at 1440 (header CTA). Pass: h-overflow 0, chip heights uniform 44, imgs-without-alt 0, one h1, console 0 errors/warnings on all 8 contexts. No committed pixel baseline exists → pixel-drift check could not run (gap). |
| 3 Screenshot matrix | DONE | 127 PNGs: `/` × {1440, 1440 reduced-motion, 1024, 390} × 24–26 states; `/deck/` × {1440, 390} × hero + 10 tabs; `/for-ian/` × 2; motion 3 frames × 2 (hero canvas, folio); 7 functional-walk shots; 2 proof-section shots. |
| 4 Human-eye review | FAIL | All 127 PNGs read by a reviewer (this agent; the Agent tool was unavailable in this sandbox, so reviewer fan-out was serial, one reviewer — see gaps). 89 PASS, 38 carry at least one defect row. |
| 5 Functional walk (3 personas) | FAIL | 11 oddities logged (below). Contact form demo-submit works (`Concept — not wired` shows, button disables). Deck tabs: 10/10 switch, hash persists on reload. |
| 6 Panel (scoped 3-lens: UX, honesty, rigor) | FAIL | Text below. |
| 7 Verdict | this file | — |

---

## Friction numbers (from `shots_log.json` / `walk_log.json`)

Scroll distances from page top until the element is at the top of the viewport (= fully in view for pinned sections). Screens = px ÷ viewport height.

| Measure | 1440×900 | 1024×768 | 390×844 | 1440×900 reduced-motion |
|---|---|---|---|---|
| Total page height | **52,285 px = 58.1 screens** | 45,577 px = 59.3 screens | 27,861 px = 33.0 screens | 44,191 px = 49.1 screens |
| Pinned hero height | 6,300 px (7 screens) | 5,376 (7) | 4,220 (5) | 2,304 |
| Specialisms stack | 4,500 px (5 screens) | 3,840 (5) | 352 (carousel) | 2,309 |
| Approach drum | 3,600 px (4 screens) | 3,072 (4) | 1,873 | 1,693 |
| Roles heading top | 18,043 px = 20.0 screens | 15,793 = 20.6 | 11,253 = 13.3 | 9,949 = 11.1 |
| Can filter roles (chips fully in view, i.e. chips bottom − vh) | **17,803 px = 19.8 screens** | 15,522 = 20.2 | 11,013 = 13.0 | 9,687 = 10.8 |
| Roles stack: first card fully in view (folio top) | **18,729 px = 20.8 screens** | 16,316 = 21.2 | 11,889 = 14.1 | 10,635 = 11.8 |
| Roles stack height (25 cards) | **22,500 px = 25 screens** (900 px of scroll per card) | 19,200 = 25 | 494 (carousel) | 22,500 — but only 8,907 px holds cards; **13,593 px blank** |
| Pricing top | **42,791 px = 47.5 screens** | 36,808 = 47.9 | 13,963 = 16.5 | 34,697 = 38.6 |
| Contact top | 50,396 px = 56.0 screens | 43,763 = 57.0 | 24,262 = 28.7 (12,880 px below the roles heading) | 42,302 |
| After filter "Sales" (14 roles) | folio 12,600 px, page 42,385 | folio 10,752 | — | — |

Via nav: clicking "Roles" (desktop) lands at scrollY 17,881 with the chips visible but the first card 1,078 px below the viewport top → one more screen before any role is seen. After clicking a chip, `scrollIntoView` moves the folio to the top and the chips scroll off-screen (chips top at −91 px).

---

## Defects (all status: open)

### P1

**D-01 · Role-card index numeral overlaps meta line and title (operator report — reproduced).**
Files: `home_d1440_roles_card01.png` (card 01 "Strategic Account Manager / Engagement Manager": "01" over "NEW YORK, NY (HYBRID)" and "Strategic"), `home_d1440_roles_card08.png` (card 06 "Enterprise Account Executive (Founding Hire)"), `home_d1440_roles_card20.png` (card 07 "Partner Implementation Manager"), `motion_folio_f3.png` (card 02: meta reads "N W YO K, N (ON-SITE)" because the numeral paints over it).
Measured at 1440×900 (`shots_log_d1440.json → overlap`): numeral `.card__n` occupies y 25–140 px inside the card (font-size 115.2 px = 8vw); `.card__body` starts at y 29 px on card 01 (3-line title), 85–89 px on 2-line titles, 123–187 px on 1-line titles. Numeral∩h3 > 0 on cards 1, 2, 6, 7, 9, 10, 15, 19, 21, 25 (10/25); numeral∩body > 0 on 12/25 (adds 18, 22; 23 when scaled). Also present in the London filter (cards 2, 4, 9, 11). Not present at 1024×768 (numeral 82 px, body top ≥151 px) nor on mobile (numeral is static there).
Selectors: `#roles .folio--roles .card` → `.card__n` (absolute, `top:24px`) vs `.card__body > .card__meta` and `.card__body > h3`.
CSS cause (`site/css/styles.css` L101–104): `.card{height:min(440px,62vh); padding:clamp(28px,4vw,56px); display:grid; align-content:end; overflow:hidden}` fixes the card at 440 px and bottom-anchors the body, while `.card__n{position:absolute; top:24px; font-size:clamp(60px,8vw,120px)}` is taken out of flow, so nothing reserves its 115 px. Content box is 440 − 2×56 = 328 px; a 2–3-line `h3` at `clamp(30px,4vw,60px)` (57.6 px → 120–181 px tall) + meta (≈35 px) + comp block (≈95 px) + equity (≈27 px) = 290–355 px, so the body rises to the top padding and under the numeral. Because `.card__body` has `opacity:calc(...)` it forms a stacking context painted before the positioned numeral, so the numeral is drawn **on top of** the text (hence illegible meta in `motion_folio_f3.png`). `main.js` L150 renders the same markup for every card, so every long-titled card inherits it.
Proposed fix (pick one, or combine): (a) put the numeral in flow — `.card{grid-template-rows:auto 1fr; align-content:stretch}` with `.card__n{position:static; line-height:.85}` and `.card__body{align-self:end}`; or (b) keep it absolute but reserve its box: `.card__body{padding-top:calc(clamp(60px,8vw,120px) + 8px)}` and let the card grow (`height:auto; min-height:min(440px,62vh); max-height:80vh`) with `h3{font-size:clamp(28px,3vw,48px); text-wrap:balance}`; and in all cases `.card__n{z-index:0; pointer-events:none}` + `.card__body{position:relative; z-index:1}` so text always paints above the numeral. Re-run the overlap probe in `shots.cjs` (expect 0/25 at 1440 and in reduced-motion).

**D-02 · Reduced-motion mode is broken on both card stacks.**
Files: `home_d1440-rm_specialisms_mid.png` ("04"/"05"/"06" painted over "Sales Development", "GTM Leadership", "Revenue Operations"), `home_d1440-rm_roles_card01.png`, `home_d1440-rm_roles_filter_london.png`, `home_d1440-rm_roles_filter_sales.png` (numeral over meta+title on every card; card widths 469–1296 px, ragged), `home_d1440-rm_roles_after_last_card.png` and `home_d1440-rm_roles_card08.png`, `home_d1440-rm_roles_card20.png`, `home_d1440-rm_roles_folio_middle.png` (entirely blank viewports).
Measured (`walk_log.json → reducedMotion`): all 25 role cards have numeral∩h3 ≥ 5,369 px² (body top 57 px vs numeral bottom 140 px); card widths `[1296, 870, 743, 517, 599, 1293, 978, 667, …]`; roles folio height 22,500 px with inline `min-height: 2500svh`, last card bottom at 8,907 px → **13,593 px (15 screens) of empty page** between the last card and "Why TaaS". Specialisms stack: widths uniform (712) but numeral overlap identical.
Cause: `@media (prefers-reduced-motion:reduce)` (styles.css L346–354) sets `.card{position:relative;width:auto;height:auto}` inside `.folio__sticky{display:grid}` whose base rule keeps `place-items:center` → cards shrink-wrap to their content width; the absolute numeral still has no reserved space. `main.js` L155 `folio.style.minHeight = mobile() ? '' : \`${rows.length*100}svh\`` ignores `reduced`, so the 25-screen runway is kept with no pinning to use it.
Fix: in L155 use `(mobile() || reduced) ? '' : …`; in the RM block add `.folio__sticky{place-items:stretch}` and `.card{width:min(760px,86vw);margin-inline:auto}`; apply the D-01 numeral fix (it covers RM too).

**D-03 · Scroll friction — the roles stack and pricing are buried (operator complaint quantified).**
Files: `shots_log.json → friction`, `walk_a_after_nav_roles.png`, `walk_a_london_sales_card1.png`.
At 1440×900 the first role card is 20.8 screens from the top, the stack itself is 25 screens (one full screen of wheel per card), pricing starts at screen 47.5 and the page is 58 screens long; at 1024 it is 59 screens. The nav "Roles" link lands on chips with no card in view. For comparison the deck cut shows roles as a sortable table one tap away and pricing in ~2 screens.
Fix options: cap the roles runway (`Math.min(rows.length, 8) * 60svh`) and show the rest as a list/table under the stack; or drop pinning for roles entirely and keep it for the hero + specialisms only; add a "Skip to pricing" anchor on the roles head.

### P2

**D-04 · Filtering hides the filters.** `walk_a_london_sales_card1.png`, `shots_log.json`. After a chip click `main.js` L163 scrolls the folio to the top; the chips end at −91 px, so the user cannot see which filter is active or change it without scrolling up. Fix: scroll to `#roles .stack__head` (or make the chips sticky under the header).

**D-05 · "Roles" nav lands on an empty screen.** `walk_a_after_nav_roles.png`. Heading + chips visible, first card 1,078 px below. Fix: reduce `.stack__head` padding / `.folio{margin-top}` so chips + first card share one screen at 900 px.

**D-06 · Outgoing card ghost.** `home_d1440_roles_card08.png` (card 05's meta "NEW YORK, NY (HYBRID) HYBRID SEED SALES" peeks above card 06, cut by the card edge), `home_d1440_roles_card20.png`, `motion_folio_f1.png`, `motion_folio_f2.png`. `folioFrame()` keeps `--o:1` until `d < −0.9`, so the previous card sits 44 px higher, fully opaque, with its first text line showing. Fix: fade from `d < −0.3` (`--o: clamp(0, 1 + d/0.6, 1)`) or translate the outgoing card up by its full height.

**D-07 · Hero cross-fade shows two states at once.** `motion_hero_f1.png` ("We hire your founding GTM team." legible behind "360 sellers approached."), `motion_hero_f2.png`, `motion_hero_f3.png`. Every frame has the previous headline + lede at ~35 % opacity under the new one. Fix: sequence out→in (outgoing opacity reaches 0 before incoming starts) or shorten the overlap window in `heroFrame`.

**D-08 · Pricing toggle changes monthly but not annual.** `home_d1440_pricing_toggle_on.png`, `home_d1024_pricing_toggle_on.png`, `home_m390_pricing_toggle_on.png`, `home_d1440-rm_pricing_toggle_on.png`. With "Recruitment + Intelligence" Launchpad reads £750/mo but still "£5,000 / year" (Scaleup £1,500/mo vs £10,000 / year; Unicorn £3,750/mo vs £30,000 / year). Either the annual line must move to £7,500 / £15,000 / £45,000 or be hidden in Intelligence mode. (Honesty.)

**D-09 · Footer legal line breaks into orphan "·" lines.** `home_d1440_footer.png`, `home_d1024_footer.png`, `home_m390_footer.png`, `home_d1440-rm_footer.png`. "Privacy Policy" / "·" / "Terms of Use" / "·" / "TaaS Terms" and "Notes for Ian →" / "·" / "Compact version" each on their own line. Cause: `.site-footer div a{display:block}` (specificity 0,1,2) beats `.site-footer__meta a{display:inline}` (0,1,1). Fix: `.site-footer .site-footer__meta a{display:inline;padding:0}`.

**D-10 · Developer placeholders visible to the client.** `walk_a_form_submitted.png` (main `#insights`: three cards "ARTICLE — To wire — live feed"), `deck_d1440_tab_insights.png` ("To wire — live feed … Article slot 1 · pulled from the GTM Hiring Blog at build time"). Replace with three real article titles from gtm-people.com/insights or remove the column.

**D-11 · No candidate path.** `walk_b_sdr_ny_empty.png`, `home_d1440_contact_filled.png`, `walk_log.json → candidate`. Role cards have no link/CTA (0 anchors in `[data-roles-list]`); "Register your interest →" and "Looking for a role?" both point at the employer form (Company*, Funding stage, "What are you hiring?"). A New York SDR gets "No roles match" and no way to register. Add a candidate form variant (name, email, LinkedIn, target role/location, CV link) or a "Register as candidate" button that switches the form's fields.

**D-12 · Two-authors feel between `/` and `/deck/`.** `deck_d1440_hero.png` vs `home_d1440_hero_0.png`: different logo lockup ("GTM. PEOPLE" stacked vs "GTM People" inline), violet display headings vs ink, pill-badge eyebrow vs letter-spaced eyebrow, different nav set (Specialisms · Open Roles · About) and different footer. If both cuts are shown to Ian, share one header/footer/type system.

**D-13 · Partner count disagrees across pages.** Main lists 28 partner rows; `deck_d1440_tab_partners.png` says "26 partners"; `/for-ian/` says "the 28 partners". Fix the deck count (or compute it).

**D-14 · Salary guide is UK-only while 11 of 25 roles are USD/EUR.** `home_d1440_salary.png`, `deck_d1440_tab_salary.png`. The FAQ already carries US bands; a NY candidate or US founder gets no benchmark. Add a GBP/USD toggle or a US column.

**D-15 · Mobile filter keeps the old horizontal scroll position.** `home_m390_roles_filter_london.png` (after "London" the carousel shows card 11 of 11, not 01), `home_m390_roles_filter_sales.png` (card 11 of 14). `render()` replaces `innerHTML` but the `.folio__sticky` `scrollLeft` persists. Fix: `list.scrollLeft = 0` after render on mobile.

### P3

**D-16 · Founder quote block is ~45 % empty.** `home_d1440_founder.png`, `home_d1024_founder.png`, `home_m390_founder.png`, `home_d1440-rm_founder.png`: ~400 px (desktop) / ~600 px (mobile) of flat dark purple above the quote in the first viewport. Reduce top padding or centre the quote.

**D-17 · Hero "HIRE" state: headline runs through the mint ring graphic.** `home_d1440_hero_80.png`, `home_d1024_hero_80.png` ("replacement guarantee." over the rings and the node line). Offset the ring cluster right of `max-width:min(1000px,80vw)` or lower its opacity behind text.

**D-18 · Mobile TaaS compare has a lone header.** `home_m390_taas.png`: a solitary "✓ GTM PEOPLE TAAS" header sits above the stacked rows, each of which repeats its own labels. Hide the header row below 800 px.

**D-19 · Uneven tier-card heights and one sub-44 px button.** Tier-2 probe: `.tier` heights 416/416/438/438 at 1024 and 438/461/461/438 at 390 (`home_d1024_pricing_toggle_off.png`, `home_m390_pricing_toggle_off.png`); `.header__nav .btn` is 41 px tall at 1440 (`min-height:40px`). Set `align-items:stretch` on the tier grid and `min-height:44px` on the header button.

**D-20 · Deck mobile tables clip/wrap.** `deck_m390_tab_roles.png` (LOCATION column cut at "New York, NY (On-si"; no visible scroll affordance), `deck_m390_tab_salary.png` ("£28k – £45k" wraps to three lines). Collapse to cards below 600 px or allow `white-space:nowrap` with an explicit scroller.

**D-21 · Deck mobile pricing: two cards highlighted.** `deck_m390_tab_pricing.png` — Launchpad and Scaleup both carry the violet border; only "Most Popular" should.

**D-22 · Proof counters read "0+ / 0+ yrs / 0+ / 0 days" until scrolled into view.** `walk_log.json → ian.proofClaims` (DOM read before scroll). Visually fine (`home_d1440_proof.png` shows 2,000+ / 20+ yrs / 100+ / 5 days) but crawlers and screen readers that do not fire IntersectionObserver see zeros. Render the final numbers in HTML and animate from 0 only visually.

**D-23 · Mobile hero has no primary CTA in the first viewport.** `home_m390_hero_0.png`: headline + lede + "BRIEF" step; "Start hiring →" / "Browse open roles" only appear at the SCALE state (`home_m390_proof.png`). The bottom bar's "Hire" is the only route. Consider showing the CTA pair under the lede on mobile.

---

## Tier 5 — functional walk log

**(a) Series A founder, desktop, wants a London AE.**
1. Hero → "Start hiring →" goes to #contact (fine). Scrolls instead: 7 screens of hero, 5 of specialisms, 4 of drum, founder, then roles at screen 20 (D-03). *More than one screen to goal: yes, ~20.*
2. Clicks nav "Roles": chips visible, no card (D-05).
3. London + Sales → 8 roles, card "Sales Executive £60k–£75k / OTE £35k–£40k" (OTE lower than base — data as published, but reads as an error to a founder; consider "+£35k–£40k variable"). Chips scroll off (D-04). Seven more screens of cards; no "enquire about this role" on a card (D-11).
4. Pricing is 8,852 px (9.8 screens) below after filtering. Toggle on/off: annual mismatch (D-08). Calculator £100k · Unicorn → £15,000 vs £30,000, fine; fee details open, fine.
5. Contact: fills form, submit → "Concept — not wired", button disabled, no false success. OK.
6. External footer links (privacy, terms, taas-terms, insights, resources, candidate-portal, partners, LinkedIn) all point at gtm-people.com — not probed (outbound).

**(b) Candidate SDR in New York, mobile 390.**
1. Bottom bar "Roles" → lands at the roles heading (scrollY 11,101); chips 498–756 px in view, first card below the fold. OK-ish.
2. SDR/BDR + New York → 0 roles, "No roles match. Try another filter or register your interest." (`walk_b_sdr_ny_empty.png`). Any type + New York → 8 roles, 5 of them engineering/"Other". SDR anywhere → 1 role (London). *Honest, but the only SDR role is in London and nothing says "we'll alert you".*
3. "Register your interest →" → employer form 12,880 px (15 screens) below, asks Company* and "What are you hiring?" (D-11).
4. Salary guide: UK only (D-14). Menu: 8 links, Escape closes, OK (`walk_b_menu_open.png`).
5. Horizontal card carousel keeps position across filters (D-15).

**(c) Ian checking his agency's pitch, desktop.**
1. `/for-ian/`: one h1, links `../`, `../deck/`, mailto all resolve (200). Copy claims "the 28 partners" — matches `/` (28 rows), contradicts `/deck/` "26 partners" (D-13).
2. Claims "I invented no quotes, prices, testimonials or article titles" — true as far as the probe can tell, but the Insights column shows "To wire — live feed" placeholder cards on both cuts (D-10) which Ian will read as unfinished.
3. `/deck/`: loads on Specialisms; the other 9 panels hidden; each tab click sets the hash and the tab survives reload (`tab-pricing`). Visual system differs from `/` (D-12). Footer carries "Concept by ProdCraft — not affiliated with GTM People" on both cuts — good.
4. `/` footer: both disclosure lines present; broken "·" layout (D-09) sits right under the legal text he will read first.
5. Proof strip DOM reads zeros before scroll (D-22).

---

## Tier 6 — scoped panel (UX · honesty · rigor)

**UX.** The scroll-story idea is sound for the hero and the six specialisms, but applying the same one-screen-per-card pin to 25 job cards turns the page into 58 screens and makes pricing — the thing a founder came for — a 47-screen scroll. The pinned stack also has the three worst visual bugs on the page (D-01, D-02, D-06). Recommendation: pin only hero + specialisms; present roles as the deck's table (or a 3-up grid) with sticky chips; keep the folio treatment for at most the first 5–6 roles. Secondary: D-04/D-05 so "Roles" and filtering land on content.

**Honesty.** Numbers are copied from the live site and the "Concept — not affiliated" lines are present on every cut. Three statements are currently untrue or inconsistent: the annual price under the Intelligence toggle (D-08), "26 partners" in the deck vs 28 everywhere else (D-13), and "To wire — live feed" shown as if it were content (D-10). The "Sales Executive … OTE £35k–£40k" card reproduces a source-data ambiguity (OTE lower than base) without a label; worth a footnote ("variable, on top of base") or a data fix upstream. The salary guide's "UK market rates" header is honest but leaves 44 % of the listed roles without a benchmark (D-14).

**Rigor.** Reduced-motion was clearly never viewed (D-02: 15 blank screens, every card overlapping). The folio code has no guard for `reduced` on the min-height it sets, and no test asserts text-vs-numeral geometry; `site_check.mjs` passed 26/26 while shipping D-01 and D-02 — the gate needs an "overlapping text" probe (added here as `overlapProbe` in `shots.cjs`) and a reduced-motion desktop pass. No pixel baseline exists for tier 2. Counters render zeros server-side (D-22).

---

## Coverage

- Pages × viewports: `/` at 1440×900, 1440×900 reduced-motion, 1024×768, 390×844 (mobile emulation, DPR 2); `/deck/` at 1440 and 390; `/for-ian/` at 1440 and 390 (top) + 1440 bottom.
- `/` states: hero 0/40/80 %, proof, specialisms mid, drum mid, founder, roles card 1/8/20 (desktop) or carousel positions 1/8/20 (mobile) + bottom bar over roles, filter London, filter Sales, Why TaaS, pricing toggle off/on, calculator £100k · Unicorn, fee details open, salary, FAQ (first item open), partners (row 2 hovered on desktop), contact filled, contact submitted (1440), footer; reduced-motion extra: after-last-card and folio-middle.
- `/deck/`: hero + all 10 tabs (specialisms, how, roles, pricing, salary, about, faq, partners, insights, contact) at both viewports.
- Motion: 3 frames at 700 ms during continuous scroll of the hero canvas (`motion_hero_f1–3.png`) and of the roles folio (`motion_folio_f1–3.png`).
- Functional: nav → roles, filters (London, Sales, SDR/BDR, New York, Remote, All), pricing toggle, calculator defaults, fee details, contact form fill + submit, newsletter form presence, mobile bottom bar tap, mobile menu open, deck tab switching + reload persistence, for-ian link resolution.
- Console: 0 errors/warnings in all 8 browser contexts.

## Gaps (what could not be exercised)

1. **Reviewer fan-out**: the Agent tool was not available in this sandbox, so one reviewer (this agent) read all 127 PNGs serially instead of ≤40-image parallel reviewers; a second independent pass is still owed per the skill's fix loop.
2. **Pixel-drift vs committed baseline**: no baseline exists for this product; tier 2 ran geometry/contrast/console probes only.
3. **Mobile screenshots of fixed elements**: in Chromium mobile emulation two shots (`home_m390_roles_filters.png`, `home_m390_contact_filled.png`) show the fixed header drawn mid-viewport; this is a Playwright visual-viewport artefact after `scrollIntoView`, not a site defect, and is excluded from the counts.
4. **Dark theme**: the site has no dark theme; not applicable.
5. **Outbound links** to gtm-people.com, LinkedIn and partner sites were not fetched.
6. **Real device touch** (iOS Safari `svh`, scroll-snap carousel feel) not tested; emulation only.
7. **Calculator slider at values other than £100k** and tiers other than Unicorn were not screenshotted (values read from DOM only).
8. **1440 non-reduced "card 08/20" shots** were re-captured after a harness bug (a runaway scroll interval in the first run); `shots_log_d1440.json` is the authoritative 1440 run, `shots_log.json` covers the rest.
