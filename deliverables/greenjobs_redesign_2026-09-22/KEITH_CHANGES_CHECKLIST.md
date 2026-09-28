# Keith's change list (Greenjobs_update.docx, received 2026-09-28) — working checklist

Status key: [ ] open · [x] done · [~] partial (say why) · [-] not done (say why)
Every item ticked only after the build validator, unit tests and the item's own test case pass.

## A. Positioning & hero (both editions)
- [x] A1 Replace h1 "Work that puts the planet on the payroll" with "Work that works for the planet." plus plain-English sub-line: IE "Find environmental, sustainability, renewable-energy and nature careers across Ireland." UK "Search environmental, ecology, sustainability, renewable-energy and low-carbon careers across the UK."
- [x] A2 Remove "N employers" from the IE hero facts. Replace with credibility markers: "Specialist green job network since 2008", "10 specialist job sites", "Roles across N sectors", "Certified B Corporation". UK keeps "19 employers hiring now" (its scale is a credibility asset). (network count read from data: 10 sites; B Corp shown as the mark + explainer only, per brief.md §3)
- [x] A3 B Corp badge gets a one-line explainer everywhere it appears.
- [x] A4 Employer logos on IE only if each employer has a live role (already enforced by validator) — keep.

## B. Classification & data accuracy
- [x] B1 Sector mapping (taxonomy in build_site.py; a 0-role sector is never rendered): highways/road/infrastructure roles no longer land in "Sustainability & net zero" or "Built environment". Add sectors: Environmental engineering; Sustainable infrastructure & transport (incl. active travel); Climate & carbon; Health, safety & environment; Nature recovery & biodiversity (fold into Ecology name). Taxonomy consistent across salary explorer and sector stats.
- [x] B2 Salaries always shown in the advertised currency; never converted. Add "salary paid in euros" / "paid in sterling" label when currency ≠ edition currency, with an approximate equivalent in brackets.
- [x] B3 Every role carries a location class: Ireland / UK / Northern Ireland / Remote / Cross-border (IE & UK) / International. Shown as a badge on cards and job pages.
- [x] B4 IE board: "Ireland only" toggle (excludes UK-only roles). UK board: "UK only" toggle.
- [x] B5 UK edition inclusion rule: show a role only if located in the UK (incl. NI), fully remote, or explicitly IE+UK. Dublin-only roles off the UK home and headline counts. Headline = genuine UK availability.
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
- [x] D3 Rename "Your fit in ten seconds" → "Quick job match"; add beside the input: "Your information is processed on your device and is not uploaded or stored." and "This is keyword matching, not an assessment of your suitability."
- [x] D4 UK match examples: ecologist Bristol · sustainability consultant London · flood risk engineer Manchester · renewable energy Scotland (no "ecologist dublin" on UK).

## E. Employer conversion
- [x] E1 "Request advertising rates" CTA (no prices are published).
- [x] E2 Audience & reach block: candidate audience, newsletter reach, LinkedIn/network distribution (only figures in brief.md/data; otherwise labelled "supplied at launch"). (no audience/newsletter/follower figures exist in brief.md; tiles read "figure supplied at launch")
- [x] E3 Organisations that have recruited through GreenJobs (from live employer list).
- [x] E4 Comparison table: Standard / Premium / Membership.
- [x] E5 Network positioning: "Advertise once. Reach candidates across the GreenJobs specialist network…" prominent on employers page and home employer section.
- [x] E6 Vacancy preview: demo explanation shortened to "Preview exactly how your vacancy will appear to candidates."
- [~] E7 UK-specific credibility signals (testimonial slots, placements, network coverage, rate-card CTA). (partial: testimonial slots are labelled placeholders and no placement figures exist in brief.md; network coverage + rate CTA shipped)

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
- [ ] H1 `/dashboard/` page per edition: KPIs derived from live data now, wired-for-analytics later.
- [ ] H2 Test cases + evidence page entry.

## I. Gates
- [ ] I1 Build validator green, unit + node tests green, new tests for every item above.
- [ ] I2 Panel pass (11 lenses), system audit, fixes applied.
- [ ] I3 Commit + push branch and main; Cloudflare deploy if token present.
