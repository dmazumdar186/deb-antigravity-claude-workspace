# GreenJobs redesign — requirements traceability matrix v2 (2026-09-28, build in working tree, served at http://localhost:8795/)

Re-scored from scratch against the current `deliverables/greenjobs_redesign_2026-09-22/site` build: text dumps of every page type, grep on the built HTML/CSS/jobs.json, and Playwright (Chromium) DOM probes + screenshots in `.tmp/trace2/shots/`. Statuses were not copied from v1.

| Status | v1 | v2 |
|---|---|---|
| DONE | 89 | 96 |
| PARTIAL | 14 | 7 |
| NOT DONE | 2 | 1 |
| NEEDS CLIENT INPUT | 7 | 7 |
| INTERPRETED DIFFERENTLY | 2 | 3 |
| **Total** | 114 | 114 |

Rows whose status changed since v1: **8** (R009 NOT DONE → INTERPRETED DIFFERENTLY, R012 PARTIAL → DONE, R036 PARTIAL → DONE, R042 PARTIAL → DONE, R044 PARTIAL → DONE, R055 PARTIAL → DONE, R077 PARTIAL → DONE, R087 PARTIAL → DONE).

## Rows not DONE

| id | status | requirement | evidence | delta |
|---|---|---|---|---|
| R006 | INTERPRETED DIFFERENTLY | Roles across 10 sectors | Hero strip now reads "Roles across 14 sectors" on both editions (was 15/14); computed from sectors with >=1 live role | Client wrote 10; site shows the live count 14. Still needs the client to confirm which number |
| R009 | INTERPRETED DIFFERENTLY | UK-only roles also appear prominently on the Irish board with salaries converted into euros. | Per Keith's 28-Sept rule (KEITH_CHANGES_CHECKLIST B5) the IE board keeps UK-only roles, labelled "UK", with the toggle doing the excluding. jobs.json IE: 62 ie / 23 uk / 3 cross; 21 of the 23 UK roles now show advertised sterling "£62k–67k (paid in sterling, about €72.5k–78.4k)" (/ie/ first card, /ie/jobs/11501460/) | Was NOT DONE. Prominence is now a client decision; 2 UK-only roles (11497629 Associate Civil Engineer London €70–75k, 11496364 Planner Scotland €30–40k) still carry euro figures with no "Salary source" row |
| R010 | PARTIAL | Improve sector mapping. | 14-sector taxonomy; Highways Civil Engineer (uk 11501402) and Assistant Road Engineer now single-tagged infrastructure; Design Coordinator – Rail, Principal Engineer – Transportation, Civil Engineering Technician all "Sustainable infrastructure & transport" | Associate Civil Engineer (ie 11497629) still also tagged "Built environment & energy efficiency"; Principal Project Manager – Civil & Environmental sits under Environmental engineering + Waste |
| R011 | PARTIAL | Retain salaries in their original advertised currency. | UK: /uk/jobs/11501639/ "€5.1k–6k/mo (paid in euros, about £4.4k–5.1k/mo)". IE: /ie/jobs/11500760/ Salary "£45,000 to £55,000 per annum (paid in sterling, about €52.7k–64.3k)" + "Salary source: Advertised in sterling on the greenjobs.co.uk listing"; IE jobs.json cur: 21 GBP, 8 EUR, 59 none | Improved: 21/23 IE sterling roles restored. 2 UK-located roles (11497629, 11496364) still show € figures; scraped from greenjobs.ie with no UK twin, so the original currency is unverified |
| R039 | NEEDS CLIENT INPUT | Candidate audience and newsletter reach | "Audience and reach" block reads "Thousands of visitors every month…" then "Monthly visitor figures are published at launch." / "Subscriber numbers are published at launch." | Placeholder wording softened but figures still missing; client must supply |
| R040 | NEEDS CLIENT INPUT | LinkedIn and network distribution figures | "Network and LinkedIn distribution" ends "Network and follower numbers are published at launch." | Client must supply |
| R041 | PARTIAL | Examples of organisations that have recruited through GreenJobs | UK: 12 logo tiles in the marquee (Arup, Commonland, Dacorum, ESS, Gaia, Grundon, Haskoning, Jacobs…). IE: Mattinson logo + text-only tiles "Commonland", "Gaia Talent" (crop ie_home_employers); EirGrid/Power NI/Veolia dropped | IE tiles still text-only; only organisations with live roles are shown now |
| R043 | PARTIAL | “Employer branding” and “Packages and memberships” currently feel like headings rather than fully developed pr | Headings replaced by "Audience and reach", "Compare the options", "Post a job"; Membership column is 11×"Ask us" + 2 Included | Products remain thin; needs client content |
| R051 | PARTIAL | Add salary guides, market reports and career advice to build repeat traffic | /ie/guides/: "Green salary guide for Ireland" + 4 job-market pages; empty "Career advice and market reports" heading removed, replaced by "More guides follow as the data grows." | No career-advice or market-report content yet |
| R058 | PARTIAL | mobile performance | /ie/jobs/index.html 300 KB, /uk/jobs/index.html 271 KB (inline JSON); ie/data/jobs.json duplicated at 219 KB; no Lighthouse/field data | Unchanged since v1 |
| R059 | NEEDS CLIENT INPUT | Replace “3 employers” with employer logos only if each relationship and permission to display the logo are cur | IE strip shows only the 3 organisations with live roles (Mattinson logo, Commonland/Gaia text); UK strip 12 logos from listings | Text tiles for Commonland/Gaia; permissions still to be confirmed by client |
| R072 | PARTIAL | Northern Ireland is absent. | Map has a Northern Ireland region (aria "Northern Ireland: 0 roles"); region list now includes "Northern Ireland 0" and the datalist has an "Northern Ireland" option (uk/jobs/index.html) | Improved: NI is a filter option now. NI still renders as a dark hole on the map (crop uk_home_map) — see visual #12 |
| R086 | NEEDS CLIENT INPUT | A GB number could also help. A Northern Ireland number may make some English employers assume the business pri | Only +44 28 (NI) number on /uk/ | Client must provide a GB number |
| R090 | INTERPRETED DIFFERENTLY | Transport and active travel | Merged into "Sustainable infrastructure & transport"; no standalone transport/active-travel sector | Client to confirm the merge |
| R095 | NEEDS CLIENT INPUT | UK employer testimonials | /uk/employers/ "Trusted across the UK — Client testimonials are being collected for launch." | Client must supply quotes |
| R097 | NEEDS CLIENT INPUT | Candidate and email audience figures | "Monthly visitor figures are published at launch." / "Subscriber numbers are published at launch." |  |
| R098 | NEEDS CLIENT INPUT | LinkedIn distribution | "Network and follower numbers are published at launch." |  |
| R099 | NOT DONE | Examples of UK placements or campaigns | No placement or campaign example on /uk/employers/ or /uk/ (grep "placement", "campaign": 0) | Unchanged; needs client case material |

## Full matrix

| id | section | edition | status | changed | evidence | delta |
|---|---|---|---|---|---|---|
| R001 | Proposition | IE+UK | DONE |  | /ie/ and /uk/ hero h1 text = "Work that works for the planet." (grep ie/index.html, uk/index.html; shots ie_home_1440_light, uk_home_1440_dark) |  |
| R002 | Proposition | IE | DONE |  | /ie/ hero subheading is the exact sentence (ie/index.html text dump) |  |
| R003 | Remove “3 employers” | IE | DONE |  | /ie/ hero strip = "88 live roles · Specialist green job network since 2008 · 10 specialist job sites · Roles across 14 sectors · Snapshot of 22 September 2026"; no employer count in the strip | Count still appears lower on /ie/ and /ie/employers/: "3 of them have live roles on greenjobs.ie this week" (grep "3 of them") |
| R004 | Remove “3 employers” | IE+UK | DONE |  | Both hero strips contain "Specialist green job network since 2008" |  |
| R005 | Remove “3 employers” | IE+UK | DONE |  | Both hero strips contain "10 specialist job sites" |  |
| R006 | Remove “3 employers” | IE+UK | INTERPRETED DIFFERENTLY |  | Hero strip now reads "Roles across 14 sectors" on both editions (was 15/14); computed from sectors with >=1 live role | Client wrote 10; site shows the live count 14. Still needs the client to confirm which number |
| R007 | Remove “3 employers” | IE+UK | DONE |  | Header badge now has a text label "Certified B Corp" (span.hdr__bcorp) + hero pill "Certified B Corporation. Independently verified for…" on both editions (crop ie_home_hero) | Label added since v1 |
| R008 | Classification | IE+UK | DONE |  | "Sustainability & net zero" appears in no page except the for-keith evidence quote; Assistant Road Engineer / Highways Civil Engineer tagged "Sustainable infrastructure & transport" only (jobs.json) |  |
| R009 | Classification | IE | INTERPRETED DIFFERENTLY | NOT DONE → INTERPRETED DIFFERENTLY | Per Keith's 28-Sept rule (KEITH_CHANGES_CHECKLIST B5) the IE board keeps UK-only roles, labelled "UK", with the toggle doing the excluding. jobs.json IE: 62 ie / 23 uk / 3 cross; 21 of the 23 UK roles now show advertised sterling "£62k–67k (paid in sterling, about €72.5k–78.4k)" (/ie/ first card, /ie/jobs/11501460/) | Was NOT DONE. Prominence is now a client decision; 2 UK-only roles (11497629 Associate Civil Engineer London €70–75k, 11496364 Planner Scotland €30–40k) still carry euro figures with no "Salary source" row |
| R010 | Classification | IE+UK | PARTIAL |  | 14-sector taxonomy; Highways Civil Engineer (uk 11501402) and Assistant Road Engineer now single-tagged infrastructure; Design Coordinator – Rail, Principal Engineer – Transportation, Civil Engineering Technician all "Sustainable infrastructure & transport" | Associate Civil Engineer (ie 11497629) still also tagged "Built environment & energy efficiency"; Principal Project Manager – Civil & Environmental sits under Environmental engineering + Waste |
| R011 | Classification | IE+UK | PARTIAL |  | UK: /uk/jobs/11501639/ "€5.1k–6k/mo (paid in euros, about £4.4k–5.1k/mo)". IE: /ie/jobs/11500760/ Salary "£45,000 to £55,000 per annum (paid in sterling, about €52.7k–64.3k)" + "Salary source: Advertised in sterling on the greenjobs.co.uk listing"; IE jobs.json cur: 21 GBP, 8 EUR, 59 none | Improved: 21/23 IE sterling roles restored. 2 UK-located roles (11497629, 11496364) still show € figures; scraped from greenjobs.ie with no UK twin, so the original currency is unverified |
| R012 | Classification | IE+UK | DONE | PARTIAL → DONE | Chips "UK", "Ireland", "Ireland & UK", "Remote"; Commonland roles now "Dublin · Ireland & UK" on /ie/ and /ie/jobs/ (was "Dublin · Ireland"); /ie/jobs/11500760/ facts panel "Where: UK" | Cross-border labelling fixed since v1 |
| R013 | Classification | IE | DONE |  | /ie/jobs/ checkbox "Hide UK/abroad-only roles — Keeps Ireland, Northern Ireland, remote and Ireland-and-UK roles; hides roles advertised only in the UK or abroad." |  |
| R014 | Classification | IE+UK | DONE |  | /ie/ "A role listed in more than one county or sector counts in each; salary figures use the midpoint…"; /ie/jobs/, /ie/sectors/, salary guide carry the same note |  |
| R015 | Shorten the homepage | IE | DONE |  | /ie/ has one county mention: stat tile "14 counties with live roles"; no county map on home |  |
| R016 | Shorten the homepage | IE+UK | DONE |  | One "Browse by sector" section per home page (9 cards + "All sectors") |  |
| R017 | Shorten the homepage | IE+UK | DONE |  | One "Salary insight" section per home; sector cards carry only a median/disclosure line |  |
| R018 | Shorten the homepage | IE+UK | DONE |  | "Quick job match" only on /ie/jobs/ and /uk/jobs/ (grep home pages: 0) |  |
| R019 | Shorten the homepage | IE | DONE |  | /ie/ order: hero+search → Latest roles → Browse by sector → Salary insight → Why GreenJobs → Employer proposition → Email alerts (text dump) |  |
| R020 | Shorten the homepage | IE | DONE |  | /ie/ "Latest roles" (8 cards) second |  |
| R021 | Shorten the homepage | IE | DONE |  | /ie/ "Browse by sector" third |  |
| R022 | Shorten the homepage | IE | DONE |  | /ie/ "Salary insight" fourth |  |
| R023 | Shorten the homepage | IE | DONE |  | /ie/ "Why GreenJobs" fifth |  |
| R024 | Shorten the homepage | IE | DONE |  | /ie/ "Employer proposition" sixth |  |
| R025 | Shorten the homepage | IE | DONE |  | /ie/ "Email alerts: the week's green roles, in your inbox" last |  |
| R026 | Shorten the homepage | IE+UK | DONE |  | IE home: sector sparklines + 3 stat tiles; UK home: one region map + 3 stat tiles (shots ie_home_1440_light, uk_home_1440_dark) |  |
| R027 | Candidate experience | IE+UK | DONE |  | /uk/jobs/ Workplace: Office-based, Hybrid, Remote, Site-based, Not stated; /ie/jobs/ omits Office-based (jobs.json IE has 0 office roles) |  |
| R028 | Candidate experience | IE+UK | DONE |  | Career level select: Graduate/Early career, Mid-level, Senior/Principal, Director/Associate (both editions) |  |
| R029 | Candidate experience | IE+UK | DONE |  | "Salary, EUR/GBP a year" Minimum/Maximum + "Salary disclosed only" + note "Ranges are compared per year in EUR; every role still shows the salary in the currency it was advertised in." |  |
| R030 | Candidate experience | IE+UK | DONE |  | Single "Contract" select: Permanent, Contract, Fixed-term, Full-time (+Part-time, Volunteer on UK). The overlapping "Job type" select is gone (grep "Job type": 0) | Duplicate select removed since v1 |
| R031 | Candidate experience | IE | DONE |  | /ie/jobs/ "Hide UK/abroad-only roles" checkbox |  |
| R032 | Candidate experience | IE+UK | DONE |  | Closing date select: Any / within 7 / 14 / 30 days + "Hide closed roles" |  |
| R033 | Candidate experience | IE+UK | DONE |  | "Advertised by": Employers and agencies / Direct employer / Recruitment agency; job pages show "Advertised by: Recruitment agency" |  |
| R034 | Candidate experience | IE+UK | DONE |  | /ie/jobs/11500760/, /ie/jobs/11501460/, /uk/jobs/11501639/, /uk/jobs/11501402/ each have "Similar roles — Same sector first, then the same area, then similar pay" with 4 cards |  |
| R035 | Candidate experience | IE+UK | DONE |  | h2 "Quick job match" on both jobs pages; "Your fit in ten seconds" only in the for-keith quote |  |
| R036 | Candidate experience | IE+UK | DONE | PARTIAL → DONE | Both jobs pages: "Your information is processed on your device and is not uploaded or stored." rendered in bold beside (right of) the textarea at 1440 (crop ie_jobsmap_top) | Exact sentence and placement fixed since v1 |
| R037 | Candidate experience | IE+UK | DONE |  | Directly under it: "Keyword matching, not an assessment of your suitability." |  |
| R038 | Employer conversion | IE+UK | DONE |  | /ie/employers/ and /uk/employers/: "Request advertising rates →" in hero, above the table and in the form; "Prices are not published. Rates are supplied by the team…" |  |
| R039 | Employer conversion | IE+UK | NEEDS CLIENT INPUT |  | "Audience and reach" block reads "Thousands of visitors every month…" then "Monthly visitor figures are published at launch." / "Subscriber numbers are published at launch." | Placeholder wording softened but figures still missing; client must supply |
| R040 | Employer conversion | IE+UK | NEEDS CLIENT INPUT |  | "Network and LinkedIn distribution" ends "Network and follower numbers are published at launch." | Client must supply |
| R041 | Employer conversion | IE+UK | PARTIAL |  | UK: 12 logo tiles in the marquee (Arup, Commonland, Dacorum, ESS, Gaia, Grundon, Haskoning, Jacobs…). IE: Mattinson logo + text-only tiles "Commonland", "Gaia Talent" (crop ie_home_employers); EirGrid/Power NI/Veolia dropped | IE tiles still text-only; only organisations with live roles are shown now |
| R042 | Employer conversion | IE+UK | DONE | PARTIAL → DONE | "Compare the options" table renders as a proper 4-column grid with green "Included" ticks and muted "Ask us" (crop ie_emp_table); at 390 it collapses to one card per row (crop ie_emp390_table) | Rendering fixed since v1. New defect: .cmpwrap max-height 648px hides the last two rows (the Membership "Included" rows) at 1440×900 with no scroll cue — see visual_issues_v2 N1 |
| R043 | Employer conversion | IE+UK | PARTIAL |  | Headings replaced by "Audience and reach", "Compare the options", "Post a job"; Membership column is 11×"Ask us" + 2 Included | Products remain thin; needs client content |
| R044 | Employer conversion | IE+UK | DONE | PARTIAL → DONE | Lede "Preview exactly how your vacancy will appear to candidates."; remaining form note is "Preview only. Rates and posting are handled by the GreenJobs team." (no "Posting opens at launch", grep 0) | Launch disclaimer removed since v1 |
| R045 | Copy and credibility | IE+UK | DONE |  | grep across site HTML: only in for-keith evidence quote (noindex) |  |
| R046 | Copy and credibility | IE+UK | DONE |  | grep: only in for-keith quote; dashboard says "each role is tagged to the sectors its description talks about" |  |
| R047 | Copy and credibility | IE+UK | DONE |  | grep: only in for-keith quote |  |
| R048 | Copy and credibility | IE+UK | DONE |  | Exact sentence on /ie/, /uk/ "Browse by sector" and /ie/sectors/, /uk/sectors/ |  |
| R049 | Copy and credibility | IE+UK | DONE |  | Exact sentence on home "Salary insight", /ie/insights/, /uk/insights/ and both salary guides |  |
| R050 | Additional improvements | IE+UK | DONE |  | Hero pill (2 lines at 1440, crop ie_home_hero) + footer line + header title attribute | Wrap fixed since v1 |
| R051 | Additional improvements | IE+UK | PARTIAL |  | /ie/guides/: "Green salary guide for Ireland" + 4 job-market pages; empty "Career advice and market reports" heading removed, replaced by "More guides follow as the data grows." | No career-advice or market-report content yet |
| R052 | Additional improvements | IE+UK | DONE |  | /ie/ecology-jobs-ireland/, /ie/environmental-jobs-dublin/, /ie/renewable-energy-jobs-ireland/, /ie/sustainability-jobs-ireland/ + UK equivalents all 200 | IE ecology page lists 2 London Mattinson roles labelled "UK" (kept per Keith rule) |
| R053 | Additional improvements | IE+UK | DONE |  | <script type="application/ld+json"> JobPosting with Organization, Place, PostalAddress, MonetaryAmount(currency GBP on IE 11500760, EUR on UK 11501639) |  |
| R054 | Additional improvements | IE+UK | DONE |  | <link rel="canonical"> on every fetched page | Still points at greenjobs-redesign.pages.dev/…/index.html and every page is noindex,nofollow (demo) |
| R055 | Additional improvements | IE+UK | DONE | PARTIAL → DONE | hreflang en-IE / en-GB / x-default now on landing pages (/ie/ecology-jobs-ireland/ ↔ /uk/ecology-jobs-uk/), guides, salary guide, dashboard; job pages carry canonical only (no twin) | Landing/guide pairs added since v1 |
| R056 | Additional improvements | IE+UK | DONE |  | Playwright: UK map regions role=button tabindex=0 aria-label ("East Midlands: 0 roles", "Northern Ireland: 0 roles"); 404 and dialogs keyboard-closable (data-sheet-close, dialog close) |  |
| R057 | Additional improvements | IE+UK | DONE |  | css/styles.css has 4 prefers-reduced-motion blocks; marquee pauses on hover/focus-within (.marq:focus-within … animation-play-state:paused) |  |
| R058 | Additional improvements | IE+UK | PARTIAL |  | /ie/jobs/index.html 300 KB, /uk/jobs/index.html 271 KB (inline JSON); ie/data/jobs.json duplicated at 219 KB; no Lighthouse/field data | Unchanged since v1 |
| R059 | Additional improvements | IE+UK | NEEDS CLIENT INPUT |  | IE strip shows only the 3 organisations with live roles (Mattinson logo, Commonland/Gaia text); UK strip 12 logos from listings | Text tiles for Commonland/Gaia; permissions still to be confirmed by client |
| R060 | UK: geography | UK | DONE |  | uk/data/jobs.json: 77 = 74 uk + 3 cross; 0 ie-only |  |
| R061 | UK: geography | UK | DONE |  | /uk/ Latest UK roles: 8 cards, none Dublin-only; Gaia role shown as "Dublin, United Kingdom (UK) · Ireland & UK" |  |
| R062 | UK: geography | UK | DONE |  | No "Ireland & abroad" bucket (grep 0); headline 77; "13 roles are not on the map: UK-wide / remote (13)" |  |
| R063 | UK: geography | UK | DONE |  | uk jobs.json loc_class: 74 uk |  |
| R064 | UK: geography | UK | DONE |  | 7 remote-workplace roles in UK dataset; Workplace filter has Remote |  |
| R065 | UK: geography | UK | DONE |  | 3 "cross" roles labelled "Ireland & UK" |  |
| R066 | UK: geography | UK | DONE |  | /uk/ "77 live green roles across the UK this week" |  |
| R067 | UK: geography | UK | DONE |  | /uk/ card: "€5.1k–6k/mo" chip + separate "paid in € ≈ £4.4k–5.1k/mo" chip (crop uk_home_marquee_after3s) | Long chip split in two since v1; no mid-value wrap at 390 (crop uk_home390_mid) |
| R068 | UK: geography | UK | DONE |  | "(paid in euros, about £4.4k–5.1k/mo)" on the job page; "paid in €" chip on cards |  |
| R069 | UK: geography | UK | DONE |  | "about £4.4k–5.1k/mo" |  |
| R070 | UK: geography | UK | DONE |  | UK dataset: 46 GBP, 1 EUR (labelled), 30 undisclosed |  |
| R071 | UK: geography | UK | DONE |  | "Every region, counted" only in for-keith quote; section h2 "See where green employers are hiring" |  |
| R072 | UK: geography | UK | PARTIAL |  | Map has a Northern Ireland region (aria "Northern Ireland: 0 roles"); region list now includes "Northern Ireland 0" and the datalist has an "Northern Ireland" option (uk/jobs/index.html) | Improved: NI is a filter option now. NI still renders as a dark hole on the map (crop uk_home_map) — see visual #12 |
| R073 | UK: geography | UK | DONE |  | Region list shows "East Midlands 0"; map region aria "East Midlands: 0 roles" | Listed at 0 since v1 |
| R074 | UK: geography | UK | DONE |  | Only "UK-wide / remote (13)" as the off-map group |  |
| R075 | UK: geography | UK | DONE |  | "13 roles are not on the map: UK-wide / remote (13)" link beside the map |  |
| R076 | UK: geography | UK | DONE |  | /uk/ h2 + lede are the exact sentences |  |
| R077 | UK: geography | UK | DONE | PARTIAL → DONE | "Northern Ireland" appears in the region list (0) and in the /uk/jobs/ region datalist (grep count 5) | Was PARTIAL; option added since v1 |
| R078 | UK: matching examples | UK | DONE |  | /uk/jobs/ examples: no Dublin; placeholder ends "…EIA chapters, Bristol" |  |
| R079 | UK: matching examples | UK | DONE |  | "Try:" chip "ecologist Bristol" |  |
| R080 | UK: matching examples | UK | DONE |  | chip "sustainability consultant London" |  |
| R081 | UK: matching examples | UK | DONE |  | chip "flood risk engineer Manchester" |  |
| R082 | UK: matching examples | UK | DONE |  | chip "renewable energy Scotland" |  |
| R083 | UK: contact | UK | DONE |  | "Calling From Outside" only in for-keith quote |  |
| R084 | UK: contact | UK | DONE |  | /uk/ footer first line "Calling from the UK: +44 28 4303 2055" |  |
| R085 | UK: contact | UK | DONE |  | /uk/ footer second line "Calling from Ireland: (01) 912 5247"; IE footer lists Ireland first |  |
| R086 | UK: contact | UK | NEEDS CLIENT INPUT |  | Only +44 28 (NI) number on /uk/ | Client must provide a GB number |
| R087 | UK: sector classification | UK | DONE | PARTIAL → DONE | /uk/jobs/11501402/ Sector row = "Sustainable infrastructure & transport" only; jobs.json sectors ["Sustainable infrastructure & transport"] | Built-environment tag dropped since v1 |
| R088 | UK: sector classification | IE+UK | DONE |  | IE "Environmental engineering" (8 roles); UK 0 roles so hidden ("No empty categories") |  |
| R089 | UK: sector classification | IE+UK | DONE |  | "Sustainable infrastructure & transport" (IE 33 / UK 18) |  |
| R090 | UK: sector classification | IE+UK | INTERPRETED DIFFERENTLY |  | Merged into "Sustainable infrastructure & transport"; no standalone transport/active-travel sector | Client to confirm the merge |
| R091 | UK: sector classification | IE+UK | DONE |  | "Climate & carbon" (IE 1 / UK 5) |  |
| R092 | UK: sector classification | IE+UK | DONE |  | "Health, safety & environment" (IE 11 / UK 8) |  |
| R093 | UK: sector classification | IE+UK | DONE |  | "Ecology, nature recovery & biodiversity" (IE 10 / UK 17) |  |
| R094 | UK: sector classification | IE+UK | DONE |  | Same 14-name taxonomy on jobs filter, sectors page, salary explorer, salary guide, dashboard and alert form (text dumps) |  |
| R095 | UK: credibility signals | UK | NEEDS CLIENT INPUT |  | /uk/employers/ "Trusted across the UK — Client testimonials are being collected for launch." | Client must supply quotes |
| R096 | UK: credibility signals | UK | DONE |  | /uk/employers/ + /uk/ marquee: Arup, Commonland, Dacorum BC, Environmental Standards Scotland, Gaia Talent, Grundon, Haskoning, Jacobs, … (12 logos) |  |
| R097 | UK: credibility signals | UK | NEEDS CLIENT INPUT |  | "Monthly visitor figures are published at launch." / "Subscriber numbers are published at launch." |  |
| R098 | UK: credibility signals | UK | NEEDS CLIENT INPUT |  | "Network and follower numbers are published at launch." |  |
| R099 | UK: credibility signals | UK | NOT DONE |  | No placement or campaign example on /uk/employers/ or /uk/ (grep "placement", "campaign": 0) | Unchanged; needs client case material |
| R100 | UK: credibility signals | UK | DONE |  | /uk/employers/ "Network coverage: conservationjobsuk.com … windjobsuk.com" (10) and "The network" chips on home |  |
| R101 | UK: credibility signals | UK | DONE |  | "Request advertising rates →" ×3 on /uk/employers/ |  |
| R102 | UK: credibility signals | UK | DONE |  | /uk/ hero strip "18 employers hiring now" (live count) |  |
| R103 | UK: proposition | UK | DONE |  | /uk/ hero subheading is the exact sentence |  |
| R104 | UK: homepage order | UK | DONE |  | /uk/: one region section, one sector section, one salary section |  |
| R105 | UK: homepage order | UK | DONE |  | /uk/ hero with search first |  |
| R106 | UK: homepage order | UK | DONE |  | "Latest UK roles" second |  |
| R107 | UK: homepage order | UK | DONE |  | "Browse by sector" third |  |
| R108 | UK: homepage order | UK | DONE |  | "See where green employers are hiring" (region map) fourth |  |
| R109 | UK: homepage order | UK | DONE |  | "Salary insight" fifth |  |
| R110 | UK: homepage order | UK | DONE |  | "Why GreenJobs" sixth |  |
| R111 | UK: homepage order | UK | DONE |  | "Employers and advertising" seventh |  |
| R112 | UK: homepage order | UK | DONE |  | "Job alerts: the week's green roles, in your inbox" last |  |
| R113 | UK: homepage order | UK | DONE |  | No animated Map/Pay/Sectors sequence; static region map + salary tiles |  |
| R114 | UK: network positioning | IE+UK | DONE |  | Exact text as h1 + lede on /uk/employers/ and /ie/employers/, and as the home employer section lede |  |
