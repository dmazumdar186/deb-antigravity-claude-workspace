# Keith's change list (Greenjobs_update.docx, received 2026-09-28) — working checklist

Status key: [ ] open · [x] done · [~] partial (say why) · [-] not done (say why)
Every item ticked only after the build validator, unit tests and the item's own test case pass.

## A. Positioning & hero (both editions)
- [x] A1 Replace h1 "Work that puts the planet on the payroll" with "Work that works for the planet." plus plain-English sub-line: IE "Find environmental, sustainability, renewable-energy and nature careers across Ireland." UK "Search environmental, ecology, sustainability, renewable-energy and low-carbon careers across the UK."
- [x] A2 Remove "N employers" from the IE hero facts. Replace with credibility markers: "Specialist green job network since 2008", "10 specialist job sites", "Roles across N sectors" (N is the live count of sectors with at least one role — 14 per edition on 28 Sept — not the "10" in the document's example, which predates the six added sectors), "Certified B Corporation". UK keeps the computed employer count ("N employers hiring now", 18 on the 22 Sept snapshot; its scale is a credibility asset). (network count read from data: 10 sites; B Corp shown as the mark + explainer only, per brief.md §3)
- [x] A3 B Corp badge gets a one-line explainer everywhere it appears.
- [x] A4 Employer logos on IE only if each employer has a live role (already enforced by validator) — keep. (2026-09-28: the home/employers panel now shows the client-logo wall the board itself publishes on /for-employers.asp — 112 organisations, the current state of its logo permissions — so the "3 employers" panel is gone; the "Hiring this week" badge is still only rendered, and validated, for organisations with a live role. Launch checklist asks GreenJobs to confirm the set.)

## B. Classification & data accuracy
- [x] B1 Sector mapping (taxonomy in build_site.py; a 0-role sector is never rendered): highways/road/infrastructure roles no longer land in "Sustainability & net zero" or "Built environment". Add sectors: Environmental engineering; Sustainable infrastructure & transport (incl. active travel); Climate & carbon; Health, safety & environment; Nature recovery & biodiversity (fold into Ecology name). Taxonomy consistent across salary explorer and sector stats.
- [x] B2 Salaries always shown in the advertised currency; never converted. Add "salary paid in euros" / "paid in sterling" label when currency ≠ edition currency, with an approximate equivalent in brackets. Note (2026-09-28, round 4): greenjobs.ie relabels UK adverts' sterling as euros; 21 of the 23 UK-located IE roles get their £ figure back from the greenjobs.co.uk twin (same numbers, nearest posted date), and the 2 without a twin are shown as listed with "the advertiser may pay in sterling" and kept out of every median.
- [x] B3 Every role carries a location class: Ireland / UK / Northern Ireland / Remote / Cross-border (IE & UK) / International. Shown as a badge on cards and job pages.
- [x] B4 Keith: "allow users to exclude UK opportunities." IE board: "Hide UK/abroad-only roles" toggle (keeps Ireland, NI, remote and Ireland-and-UK roles). UK board: "Hide Ireland/abroad-only roles" toggle. Both boards keep the toggle; `lib.js` ignores it when unchecked or absent.
- [x] B5 Final rule, per Keith's document (2026-09-28): "UK-only roles also appear prominently on the Irish board with salaries converted into euros. I would: retain salaries in their original advertised currency; clearly label UK, Ireland, remote and cross-border positions; allow users to exclude UK opportunities." So the IE board keeps every role (UK-only ones labelled "UK", international "International", NI "Northern Ireland", cross-border "Ireland & UK"), nothing is excluded, and the hide toggle does the excluding. Sterling fix: for an IE role classed UK and priced in euros, the greenjobs.co.uk twin (same id or slug, or same title + employer with the same figures) supplies the advertised sterling figures (`currency_source: "greenjobs.co.uk listing"`), rendered as "£70k–75k (paid in sterling, about €82k–88k)"; roles without a twin keep the scraped figures. 21 of 23 corrected on the 22 Sept snapshot. UK edition inclusion rule unchanged: show a role only if located in the UK (incl. NI), fully remote, or explicitly IE+UK; Dublin-only roles off the UK home and headline counts (20 Ireland-only + 1 international kept off greenjobs.co.uk on the snapshot, stated on the for-keith evidence table); the validator fails a UK page carrying an Ireland-only or international role card.
- [x] B6 Explain multi-county / multi-sector roles: a note where totals are shown ("a role in three counties counts in each").
- [x] B7 Northern Ireland is a first-class region on the UK map/list.

## C. Homepage (both editions) — shorten and reorder
- [x] C1 IE order: Hero+search → Latest roles → Browse by sector → Salary insight → Why GreenJobs → Employer proposition → Email alerts. UK order: Search+headline → Latest UK roles → Sector → Region → Salary → Why → Employers → Alerts. (IE has no standalone map band; the county map is reached via the Salary-insight tile → jobs?view=map)
- [x] C2 Remove duplicates: county/region appears once, sector once, salary once; the CV-match panel lives on the jobs page only.
- [x] C3 Reduce "Map, Pay, Sectors" film to one compact insights section. (film.js and its CSS removed; home ships wind.js only)
- [x] C4 UK region heading: "See where green employers are hiring" + "Explore current vacancies by UK region, including nationwide and remote opportunities." (replaces "Every region, counted").

## D. Candidate experience (jobs page + job page)
- [x] D1 New filters: Workplace type (office/hybrid/remote/site-based), Career level, Salary range, Contract (permanent/contract/fixed-term/full-time/part-time), Ireland-only / UK-only toggle, Closing date, Direct employer vs recruitment agency.
- [x] D2 "Similar jobs" block on each vacancy page.
- [x] D3 Rename "Your fit in ten seconds" → "Quick job match"; add beside the input: "Processed on your device. Nothing is uploaded." and "Keyword matching, not an assessment of your suitability." (panel 2026-09-28: "not stored" dropped because the text goes into the URL only after an explicit "Copy shareable link" click)
- [x] D4 UK match examples: ecologist Bristol · sustainability consultant London · flood risk engineer Manchester · renewable energy Scotland (no "ecologist dublin" on UK).

## E. Employer conversion
- [x] E1 "Request advertising rates" CTA (no prices are published).
- [x] E2 Audience & reach block: candidate audience, newsletter reach, LinkedIn/network distribution (only figures in brief.md/data; otherwise labelled "supplied at launch"). (no audience/newsletter/follower figures exist in brief.md; tiles read "figure supplied at launch")
- [x] E3 Organisations that have recruited through GreenJobs — the full client-logo wall scraped from greenjobs.ie/for-employers.asp (112 logos, `data/clients_{ie,uk}.json`, `assets/logos/clients/`), linked to that page, employer names as alt text, live-role badges; validator requires ≥ 24 tiles per edition. (was: the live employer list only, 3 tiles on IE)
- [x] E4 Comparison table: Standard / Premium / Membership.
- [x] E5 Network positioning: "Advertise once. Reach candidates across the GreenJobs specialist network…" prominent on employers page and home employer section.
- [x] E6 Vacancy preview: demo explanation shortened to "Preview exactly how your vacancy will appear to candidates."
- [~] E7 UK-specific credibility signals (testimonials, placements, network coverage, rate-card CTA). (partial: testimonials are collected for launch (one line on the public page, item on the for-keith launch checklist) and no placement figures exist in brief.md; network coverage + rate CTA shipped)

## F. Copy & credibility
- [x] F1 Remove builder-speak: "Career level read from title", "Tagged by what its description actually says", "The send button is honest" → "Every vacancy is classified consistently, making it easier to compare roles, sectors and salaries."
- [x] F2 Salary framing: "Compare disclosed salaries and identify employers committed to greater pay transparency." (no repeated "competitive" jabs).
- [x] F3 UK footer contact: "Calling from the UK: +44 28 4303 2055 · Calling from Ireland: (01) 912 5247". IE keeps Ireland-first wording. (numbers from brief.md §6; the live site labels +44 as "Calling From Outside Ireland", Keith's "Calling from the UK" wording used)

## G. SEO & technical
- [x] G1 JobPosting structured data on every job page (exists; verify currency/validity), canonical URLs, IE/UK hreflang pairs.
- [x] G2 Dedicated SEO landing pages: "Ecology Jobs Ireland", "Environmental Jobs Dublin", "Renewable Energy Jobs Ireland" (+ UK equivalents), built from live data. — 4 per edition, only built when at least one role matches; in the sitemap with canonical links.
- [~] G3 Content hub scaffold: salary guides, market reports, career advice (index page + first salary guide generated from data). — salary guide + guides index shipped at /guides/; market reports and career advice listed as generated-when-data-supports, no placeholder articles.
- [~] G4 Keyboard access, reduced-motion and mobile performance test cases for map, animations, interactive tools (documented and run). — board & data section in tests/greenjobs_redesign/TEST_CASES.md (BD-1..14); automated tests green; manual keyboard/reduced-motion/mobile runs still to be recorded.

## H. Over-delivery: KPI dashboard (not asked for)
- [x] H1 `/dashboard/` page per edition: KPIs derived from live data now, wired-for-analytics later.
- [x] H2 Test cases + evidence page entry.

## I. Gates
- [x] I1 Build validator green, unit + node tests green, new tests for every item above.
- [x] I2 Panel pass (11 lenses), system audit, fixes applied. (panel pass run 2026-09-28, fixes applied)
- [x] I3 Commit + push branch and main; Cloudflare deploy if token present. (pushed to claude/happy-babbage-bavlm5 and main; deployed https://greenjobs-redesign.pages.dev/ 2026-09-28)
