# Keith's change list (Greenjobs_update.docx, received 2026-09-28) — working checklist

Status key: [ ] open · [x] done · [~] partial (say why) · [-] not done (say why)
Every item ticked only after the build validator, unit tests and the item's own test case pass.

## A. Positioning & hero (both editions)
- [ ] A1 Replace h1 "Work that puts the planet on the payroll" with "Work that works for the planet." plus plain-English sub-line: IE "Find environmental, sustainability, renewable-energy and nature careers across Ireland." UK "Search environmental, ecology, sustainability, renewable-energy and low-carbon careers across the UK."
- [ ] A2 Remove "N employers" from the IE hero facts. Replace with credibility markers: "Specialist green job network since 2008", "10 specialist job sites", "Roles across N sectors", "Certified B Corporation". UK keeps "19 employers hiring now" (its scale is a credibility asset).
- [ ] A3 B Corp badge gets a one-line explainer everywhere it appears.
- [ ] A4 Employer logos on IE only if each employer has a live role (already enforced by validator) — keep.

## B. Classification & data accuracy
- [ ] B1 Sector mapping: highways/road/infrastructure roles no longer land in "Sustainability & net zero" or "Built environment". Add sectors: Environmental engineering; Sustainable infrastructure & transport (incl. active travel); Climate & carbon; Health, safety & environment; Nature recovery & biodiversity (fold into Ecology name). Taxonomy consistent across salary explorer and sector stats.
- [ ] B2 Salaries always shown in the advertised currency; never converted. Add "salary paid in euros" / "paid in sterling" label when currency ≠ edition currency, with an approximate equivalent in brackets.
- [ ] B3 Every role carries a location class: Ireland / UK / Northern Ireland / Remote / Cross-border (IE & UK) / International. Shown as a badge on cards and job pages.
- [ ] B4 IE board: "Ireland only" toggle (excludes UK-only roles). UK board: "UK only" toggle.
- [ ] B5 UK edition inclusion rule: show a role only if located in the UK (incl. NI), fully remote, or explicitly IE+UK. Dublin-only roles off the UK home and headline counts. Headline = genuine UK availability.
- [ ] B6 Explain multi-county / multi-sector roles: a note where totals are shown ("a role in three counties counts in each").
- [ ] B7 Northern Ireland is a first-class region on the UK map/list.

## C. Homepage (both editions) — shorten and reorder
- [ ] C1 IE order: Hero+search → Latest roles → Browse by sector → Salary insight → Why GreenJobs → Employer proposition → Email alerts. UK order: Search+headline → Latest UK roles → Sector → Region → Salary → Why → Employers → Alerts.
- [ ] C2 Remove duplicates: county/region appears once, sector once, salary once; the CV-match panel lives on the jobs page only.
- [ ] C3 Reduce "Map, Pay, Sectors" film to one compact insights section.
- [ ] C4 UK region heading: "See where green employers are hiring" + "Explore current vacancies by UK region, including nationwide and remote opportunities." (replaces "Every region, counted").

## D. Candidate experience (jobs page + job page)
- [ ] D1 New filters: Workplace type (office/hybrid/remote/site-based), Career level, Salary range, Contract (permanent/contract/fixed-term/full-time/part-time), Ireland-only / UK-only toggle, Closing date, Direct employer vs recruitment agency.
- [ ] D2 "Similar jobs" block on each vacancy page.
- [ ] D3 Rename "Your fit in ten seconds" → "Quick job match"; add beside the input: "Your information is processed on your device and is not uploaded or stored." and "This is keyword matching, not an assessment of your suitability."
- [ ] D4 UK match examples: ecologist Bristol · sustainability consultant London · flood risk engineer Manchester · renewable energy Scotland (no "ecologist dublin" on UK).

## E. Employer conversion
- [ ] E1 "Request advertising rates" CTA (no prices are published).
- [ ] E2 Audience & reach block: candidate audience, newsletter reach, LinkedIn/network distribution (only figures in brief.md/data; otherwise labelled "supplied at launch").
- [ ] E3 Organisations that have recruited through GreenJobs (from live employer list).
- [ ] E4 Comparison table: Standard / Premium / Membership.
- [ ] E5 Network positioning: "Advertise once. Reach candidates across the GreenJobs specialist network…" prominent on employers page and home employer section.
- [ ] E6 Vacancy preview: demo explanation shortened to "Preview exactly how your vacancy will appear to candidates."
- [ ] E7 UK-specific credibility signals (testimonial slots, placements, network coverage, rate-card CTA).

## F. Copy & credibility
- [ ] F1 Remove builder-speak: "Career level read from title", "Tagged by what its description actually says", "The send button is honest" → "Every vacancy is classified consistently, making it easier to compare roles, sectors and salaries."
- [ ] F2 Salary framing: "Compare disclosed salaries and identify employers committed to greater pay transparency." (no repeated "competitive" jabs).
- [ ] F3 UK footer contact: "Calling from the UK: +44 28 4303 2055 · Calling from Ireland: (01) 912 5247". IE keeps Ireland-first wording.

## G. SEO & technical
- [ ] G1 JobPosting structured data on every job page (exists; verify currency/validity), canonical URLs, IE/UK hreflang pairs.
- [ ] G2 Dedicated SEO landing pages: "Ecology Jobs Ireland", "Environmental Jobs Dublin", "Renewable Energy Jobs Ireland" (+ UK equivalents), built from live data.
- [ ] G3 Content hub scaffold: salary guides, market reports, career advice (index page + first salary guide generated from data).
- [ ] G4 Keyboard access, reduced-motion and mobile performance test cases for map, animations, interactive tools (documented and run).

## H. Over-delivery: KPI dashboard (not asked for)
- [ ] H1 `/dashboard/` page per edition: KPIs derived from live data now, wired-for-analytics later.
- [ ] H2 Test cases + evidence page entry.

## I. Gates
- [ ] I1 Build validator green, unit + node tests green, new tests for every item above.
- [ ] I2 Panel pass (11 lenses), system audit, fixes applied.
- [ ] I3 Commit + push branch and main; Cloudflare deploy if token present.
