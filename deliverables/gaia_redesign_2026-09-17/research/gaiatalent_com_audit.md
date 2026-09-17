# Gaia Talent (gaiatalent.com) - Research Report

All raw files saved in this folder: homepage.html, sitemap.xml + 9 sub-sitemaps, page_*.html (raw HTML per page), extracted_page_*.txt (meta/headings/schema per page), text_page_*.txt (clean body text per page), light.css, hd-style.css, headers_homepage.txt, pagespeed_mobile.json (quota error - see section 5).

Fetched via curl (custom UA through the environment's HTTPS proxy) since Firecrawl MCP tools returned "Unauthorized: Invalid token" and Anthropic's own WebFetch tool got HTTP 403 (Cloudflare bot-blocked) on every gaiatalent.com URL tried.

---

## 1. SITE MAP

Robots.txt (/robots.txt, 200 OK) - standard Yoast SEO block, Disallow: empty (everything crawlable), points to /sitemap_index.xml.

Sitemap index at /sitemap.xml lists 9 sub-sitemaps:

- post-sitemap.xml - lastmod 2022-09-23 - 130 URLs (blog/news posts; index frozen since 2022 despite newer content dates)
- page-sitemap.xml - lastmod 2025-04-30 - 8 static pages
- team-sitemap.xml - lastmod 2025-05-01 - 5 team member profile URLs
- jobs-sitemap.xml - lastmod 2026-09-15 - 64 URLs (live job postings, actively maintained)
- category-sitemap.xml - lastmod 2022-09-23 - 9 blog categories
- job_location-sitemap.xml - lastmod 2026-09-15 - 15 location taxonomy pages
- job_category-sitemap.xml - lastmod 2026-09-15 - job category taxonomy
- job_type-sitemap.xml - lastmod 2026-09-15 - 2 URLs: contract, permanent
- job_sector-sitemap.xml - lastmod 2026-09-15 - 34 sector taxonomy pages

Static/core pages (page-sitemap.xml):
- https://gaiatalent.com/ (home)
- /about/
- /services/
- /team/
- /jobs/ (live jobs listing/board)
- /gaia-jobs/ (job search landing page - separate from /jobs/)
- /contact/
- /callback/ (Request a Callback form)
- /privacy-policy/

Team member pages (team-sitemap.xml): /team/keith/, /team/gian/, /team/isadora/, /team/diana-lupu/, /team/eva-obrien/

Blog categories: artificial-intelligence, biodiversity, clean-energy, climate-change, ecology, hydrogen, offshore-wind, oil-and-gas, uncategorized.

Job sector taxonomy pages (34, full list): arborist, building-infrastructure, building-jobs, building-services-engineering, circular-economy, circular-economy-environmental-engineering, circular-economy-environmental-infrastructure, civil-structural-engineering, civil-engineering, civil-engineering-infrastructure, civil-infrastructure, construction-civil-engineering, ecological-jobs, ecology, energy, energy-renewables, environment-planning, environmental-engineering-consultancy, environmental-consultancy, environmental-engineering, environmental-jobs, geotechnical, infrastructure-jobs, landscape-architecture, planning-infrastructure, project-management, rail-infrastructure-programme-management, renewable-energy, renewable-energy-sustainable-infrastructure, structural-engineering, structural-engineering-design, sustainable-infrastructure, transportation-infrastructure, waste, water, water-wastewater-infrastructure.

Job location taxonomy pages (15): Carlow, Cavan, Cork, Dublin, Galway, Hybrid, Ireland-nationwide, Kilcoole, Kildare, Kingscourt, Limerick, Louth, Meath, Newbridge, Wexford.

Live jobs sample (64 total, first 20, all confirmed HTTP 200): senior-health-safety-consultant, senior-ecologist, hydrogeologist, senior-engineer-team-lead-design-build-water-utilities, lvia-specialist-landscape-planner, senior-project-manager, senior-building-services-engineer, senior-resident-engineer, divisional-project-engineer, senior-civil-engineer-roads-and-transportation, senior-environmental-consultant-environmental-compliance-circular-economy, principal-eia-consultant, senior-environmental-engineer, design-project-senior-structural-engineer, senior-ecologist-freshwater-aquatic-specialist, project-manager-building-infrastructure, resident-engineer-all-levels, senior-project-planner, project-hydrogeologist-environment-planning, energy-practice-lead-renewables-and-infrastructure (also found via WebSearch). The /jobs/ listing page itself shows 11 jobs above the fold: landfill-manager, senior-lvia-consultant, principal-digital-graphic-artist-planning, project-engineer-renewable-energy, project-manager, project-manager-renewable-energy, arborist, senior-project-manager, senior-building-services-engineer, principal-eia-consultant, senior-flood-risk-consultant, senior-civil-engineer-roads-transportation.

Blog posts sample (130 total, first 12, listing order, no visible publish dates on the page itself):
1. "Ireland launches children and young people's assembly on biodiversity loss"
2. "Climate Action Plan highlights the opportunities that come with a net zero Ireland"
3. "Critical action is needed for Ireland to achieve its 2030 clean energy goal"
4. "How new data can enhance the knowledge of Irish peatlands"
5. "Conservation grazing generating positive returns for the biodiversity of Ireland"
6. "How Ireland's electricity industry can still reach its 2030 climate targets"
7. "Climate Committee highlights the far-reaching consequences of Biodiversity Targets for Ireland"
8. "The importance of AI technology in tackling the biodiversity challenge in Ireland"
9. "Office of Public Works announces new Biodiversity Action Strategy"
10. "Planning a future that protects Irish heritage"
11. "Conference to address the biodiversity challenge in Ireland"
12. "How can hydrogen support a green future in Ireland?"

News index is paginated 1-11 (/news/page/2/ through /page/11/, confirmed page/2 = HTTP 200). Content references "National Biodiversity Conference 2022" (still-live post referencing an event 4 years in the past as of 2026) - see section 4.

No broken internal links found in the sample tested (all nav links, footer links, taxonomy pages, team pages, and a sampled job/post URL returned HTTP 200; /wp-content/plugins/formidable - not a real page - correctly 301-redirected).

---

## 2. EXACT CONTENT INVENTORY

### Homepage (verbatim)
- Title tag: "Ecology & Green Recruitment in Ireland & the UK | Gaia Talent"
- Meta description: "Gaia Talent is a specialist environmental & ecology recruitment consultancy and career management to the green industry in UK & Ireland."
- H1 (hero headline): "Connecting People with Purpose" (rendered across 3 stacked lines: "Connecting" / "People with" / "Purpose")
- H2: "Specialist recruitment"
- Body copy under H2: "Gaia Talent is a specialist recruitment consultancy that provides recruitment and career management services to the following sectors"
- H3 sector tags: "Environmental", "Engineering", "Sustainability", "Renewable energy"
- CTA section: H3 "Let's talk" / subcopy "Schedule a confidential one to one chat"
- A theme toggle control ("Dark / Light") is present on every page.
- The rendered homepage body is otherwise very sparse in static HTML (43 non-empty lines total) - most visual richness is delivered via GSAP/ScrollTrigger animation of a handful of text blocks and Sirv-hosted hero images, not extensive copy.

### Navigation (identical on every page, exact order)
Home (logo) - Live Jobs - Services - About - News - Contact
(the nav appears to render twice in the DOM - a desktop bar + a mobile/overlay menu with identical items)

### Footer (verbatim, identical on every page)
Home / About / Services / Register a CV / Send us a job / Request a Callback / Gaia Talent / Dublin office: +353 1 211 8940 / Clare office: +353 65 672 9020 / Email: [obfuscated via Cloudflare email-decode] / (c) 2026 Gaia Talent. / Privacy Policy / Web Design by Hidden Depth

### About page (/about/)
- Title: "About | Ecology Recruitment in Ireland & the UK - Gaia Talent"
- Meta description: "Gaia Talent is a specialist recruitment agency in Ireland covering permanent and contract roles across the Green Industry Sectors."
- H1: "About us"
- First paragraph (= also H2): "Gaia Talent is a specialist consulting practice and our delivery team has over 35 years recruitment experience covering permanent (contingency and retained/search) and contract roles across the Green Industry Sectors."
- Full body text (verbatim): "We believe that the Green Industry sector is not just one of the most exciting and dynamic areas of work but the most important. Our goal is to provide the highest level of service to our candidates and clients and assist them in making the biggest impact possible in their chosen area of expertise. We truly believe that putting the right people in the right positions is the best way we can make the biggest difference as an organisation. Our goal is not just to be a recruitment and staffing business but a company that helps facilitate significant change. We know that through excellent service and delivery we not only succeed as a business but effect positive impact and change at a societal level. This is a key part of our core values and is reflected in the commitment and drive our staff have to deliver the best service possible. This starts with proper engagement and gaining a deep understanding of clients needs and their culture and goals as an organisation. From there we can properly and successfully identify, through our expertise and excellent vetting and screening process, the ideal candidates for our clients. We use our extensive market knowledge and utilise sophisticated candidate identification techniques supported with targeted advertising we identify allowing us to present the best candidates available in the market. This coupled with our extensive network and database of Green Industry professionals is why our delivery rates are so high, particularly in candidate short markets."
- "Meet the team" heading, followed by: "At GaiaTalent our service ethos is always to the fore and both our clients and candidates know they can trust us to handle the recruitment process and their needs with the utmost professionalism, honesty, transparency and integrity and we take great pride in building and maintaining relationships for the long term."
- No specific founding year, no numeric placement stats, no client logos or testimonials found anywhere on the site. The "35 years recruitment experience" claim refers to the team's cumulative experience, not the company's age. UNVERIFIED on-site: exact founding date. Per WebSearch (CRO aggregators), Gaia Talent Limited was incorporated 24 November 2017 (Company No. 615983) - see section 6.

### Team (/team/ + /about/)
Exact names and titles as shown (verbatim):
- Keith - Managing Director
- Isadora - Senior Recruitment Specialist
- Gian - Recruitment Specialist
- Eva O'Brien - Senior Recruitment Consultant
- Diana Lupu - Finance Administrator

Each name links to "LinkedIn". IMPORTANT FINDING: the individual profile pages (/team/keith/, /team/gian/, /team/isadora/, /team/diana-lupu/, /team/eva-obrien/) all return HTTP 200 but their <main> content is completely empty in the raw HTML - just an empty container div, no bio text, no H1, no photo alt text, nothing extractable server-side. The page <title> is only e.g. "Keith - Gaia Talent". This means either (a) bios are meant to be injected by client-side JS that requires a full browser to render, or (b) the content blocks were simply never populated. Either way these are effectively blank/thin-content pages for any crawler or non-JS client. By contrast, job pages (e.g. /jobs/senior-ecologist/) ARE fully server-rendered with rich text, proving the theme is capable of full SSR - team bios simply aren't using it.

Per WebSearch (LinkedIn, not site content): Keith's surname is Molony - "Keith Molony - Founder, Gaia Talent | Certified B Corp" (LinkedIn) and "Managing Director" (RocketReach). The website itself never uses the surname "Molony" in visible marketing copy - it appears only once, in the Privacy Policy, naming him Data Protection Officer: "...via an email to our Data Protection Officer, Keith Molony at [email]..." (verbatim, appears twice in the privacy policy text). UNVERIFIED: whether he is "Founder" (per LinkedIn/RocketReach, external only) vs. just "Managing Director" (the only title the site itself ever uses).

### Services (/services/)
- Title: "Environmental Recruitment Services in Ireland & the UK - Gaia Talent"
- Meta description: "We have years of experience in delivering excellent environmental recruitment services to our clients operating in Ireland and the UK."
- H1: "Our Services"
- Intro (verbatim): "Our continued and ever-growing success and effectiveness is down to our core teams years of experience delivering excellent recruitment solutions to our clients"
- Body: "We have developed innovative recruitment and HR services, coupled with deep professional relationships based on trust, service and delivery and reflective of our skills and market knowledge. Our mission is to provide our clients and candidates with the best recruitment service experience possible and help further facilitate and enhance their success and growth."
- Service 1 - "Recruitment Search Solutions" (verbatim, includes a live grammatical error): "At Gaia Talent, we truly understand the getting the right person at the right time is crucial to your success and make it our mission to do so. We excel at finding out what you want and getting it. Let Gaia Talent make the hiring process easier for you. Talk to us about your requirements and we can provide you with the appropriate solution be it Contract, full Retained Search, standard Contingency Search or a Bespoke Solution. Our recruitment team works closely with our Finance and Operations teams, to ensure clients receive excellent service throughout the full recruitment life cycle."
- Service 2 - "Insights and Market Mapping" (verbatim): "If you want to understand the availability of talent in your market, what you need to offer to retain and attract the quality of individuals you need and what benefits are considered attractive Gaia Talents market knowledge and networks will help you gain insight and answers to these questions and more in detail. We continually conduct market research to understand our client's and candidate's needs and future market trends and make this valuable information readily available to our clients." Sub-list "Market insights include:" Emerging Employment Trends / Salary Survey / Relocation Guides / Future Ways of Working
- CTA: H3 "Find out more" -> "Contact us today"

### Job Search / Gaia Jobs (/gaia-jobs/)
- H1: "JOB SEARCH"
- Fullest sector list found on-site (verbatim): "Built Environment, Carbon Management, Circular Economy, Climate Change, Conservation, Corporate Social Responsibility, Energy, Energy Efficiency, Energy from Waste, Energy Storage, Engineering, Environmental, ESG & Responsible Investment, Green Start-ups, Health & Safety, Hydropower & Onshore Wind, Renewable Energy, Solar Energy, Sustainable Transport, Utilities, Waste Management & Recycling, Water & Flood Risk, Wave & Tidal Energy." Confirms: solar, onshore wind/hydropower, wave & tidal covered; no explicit mention of nuclear or grid/transmission anywhere on-site (only implied via "Utilities"/"infrastructure" taxonomy terms).

### Jobs board (/jobs/)
- H1: "Opportunities"
- Filters: "Filter jobs" / Search / Location / Sector / Role
- Job cards show title, sector tag, location, employment type (Permanent/Contract) - no salary shown on listing page.
- Individual job pages (tested senior-ecologist) ARE fully server-rendered with complete descriptions, e.g. verbatim excerpt: "SENIOR ECOLOGIST - Great opportunity for an ambitious and experienced ecologist to bring field and technical expertise to a progressive multi-disciplinary team... Our client is a long-established professional consultancy with offices in Cork and Dublin..." Each job page shows an assigned recruitment consultant (photo/name/title/LinkedIn link, e.g. "Isadora - Senior Recruitment Specialist") and an "Apply now" CTA.
- No JobPosting schema.org markup found on job pages (checked raw HTML for the literal string "JobPosting" - zero matches) - a missed opportunity for Google for Jobs rich results.

### Contact (/contact/)
- H1: "Contact"
- Contact form fields (verbatim order): "I am *" (radio: An Employer / A Candidate) -> First name* -> Last name* -> Email* -> Phone -> Job title* -> Company* -> "Attach document (E.G. CV or job spec)" (drag/drop or Choose File, max 10MB) -> "How did you hear about us?" -> Message -> honeypot ("If you are human, leave this field blank.") -> Submit
- Contact details block: "Dublin office: +353 1 211 8940" / "Clare office: +353 65 672 9020" / Email (Cloudflare-obfuscated) / "Connect with us on LinkedIn"
- No physical street address published anywhere on the site (only office-city labels + phone numbers). Per WebSearch/company registry, the registered address is Co. Clare, V95 VW74, Ireland (IrishTalents.com listing) - UNVERIFIED on-site.

### Callback (/callback/)
- H1: "Request a callback"
- Fields: "Best time to call? *" (AM/PM) -> Your name* -> Your phone number* -> honeypot -> "Send Request"

### Privacy Policy (/privacy-policy/)
- Governed by GDPR; states data-controller role; names Keith Molony as Data Protection Officer (only place his surname appears on-site) with his email for data-subject rights requests.
- CSR partnership disclosed: "Hometree" - verbatim: "We use Hometree to plant a tree for every candidate we place as part of our climate action strategy. When we place a candidate with our clients, we also plant 10 trees in their name." This genuine, quotable trust claim is not surfaced anywhere else on the site (not on homepage or About) - a missed marketing opportunity.
- States: "Data is held in Ireland using a single secure server and our secure CRM platform, Vincere." - confirms their recruitment CRM/ATS is Vincere (not Recruit CRM, Bullhorn, or JobAdder).
- No company registration number, no registered legal address stated in the privacy policy itself (checked full text - absent).

### Statistics/claims found on-site (exhaustive list)
1. "over 35 years recruitment experience" (cumulative team experience, About page)
2. "10 trees" planted per candidate placement via Hometree partnership (Privacy Policy only)
3. B Corp logo asset (b-corp-logo.png) referenced from Sirv and linked from the homepage's image set - no accompanying text/claim explaining the certification anywhere found in fetched page text. B Corp status independently confirmed via WebSearch (bcorporation.net: Certified B Corp, B Impact Score 87.3).
No client logos, no testimonials, no numeric "X placements made" stat, and no "since [year]" founding claim or awards/memberships list appear anywhere in the fetched static content.

### Legal/company pages
Only one legal page found: /privacy-policy/ (dateModified 2025-01-15). No separate Terms of Service, standalone Cookie Policy page (cookie consent is handled via the WebToffee Cookie Consent plugin banner, not a page), or Modern Slavery Statement found.
Company registration: not stated on-site. Per WebSearch (Vision-Net / CompanyCheck / SoloCheck Ireland): Gaia Talent Limited, CRO No. 615983, incorporated 24 November 2017, industry "Other professional, scientific and technical activities n.e.c.", status "Normal". Licensed as an employment agency by the Workplace Relations Commission (WRC), reference EA4906 (per IrishTalents.com directory listing). UNVERIFIED directly against a primary CRO filing - sourced from third-party company-check aggregators via WebSearch only.

---

## 3. TECH STACK

- CMS: WordPress (wp-content/wp-includes paths confirmed), with Elementor 4.2.3 page builder active (meta generator tag) alongside a fully custom bespoke theme named "gaiatalent" (wp-content/themes/gaiatalent/) - not a generic Elementor/Divi template site; theme and animation layer were purpose-built.
- SEO plugin: Yoast SEO (sitemap XSL stylesheet reference + standard Yoast robots.txt block).
- Forms plugin: Formidable Forms.
- Other plugins detected: latest-post-shortcode, sirv (image CDN/optimization), webtoffee-cookie-consent (GDPR cookie banner, v3.5.3), wp-paginate.
- Analytics/tracking: Site Kit by Google 1.186.0 plugin active (meta generator tag present), which typically wires up GA/Search Console - but no live gtag()/GTM container script or GA4 measurement ID (G-XXXXXXX) was found actually firing in the raw HTML; only a dns-prefetch hint for www.googletagmanager.com and references inside the WebToffee cookie-consent script's "Analytics" category - i.e. analytics tags appear to be consent-gated and only load after cookie opt-in. UNVERIFIED: exact GA4/GTM ID.
- Animation/interaction stack: GSAP 3.12.5 + ScrollTrigger (cdnjs.cloudflare.com), Lenis 1.0.19 smooth-scroll (cdn.jsdelivr.net), split-type 0.3.3 (unpkg.com) for text-splitting animation, jQuery 3.7.1 + jquery-migrate 3.4.1 (WP core), Font Awesome (brands/regular/solid, self-hosted), Vimeo Player API script present (player.vimeo.com/api/player.js - suggests embedded video somewhere not found on pages fetched).
- Image hosting/CDN: Sirv (gaiatalent.sirv.com + scripts.sirv.com/sirvjs/v3/sirv.js with lazyimage,video,gallery,model modules) - dedicated image-optimization/CDN service, separate from WP media library.
- Fonts: Google Fonts - Nunito only (variable weight 200-1000, italic+regular), loaded via fonts.googleapis.com.
- Colour palette (from theme CSS custom properties in light.css):
  --b1: #39b54a (brand green, primary accent)
  --b2: #0f2132 (dark navy, headings/dark backgrounds)
  --b3: #2c3e3f (dark teal-grey secondary)
  Greyscale ramp --cc-0 through --cc-8: #ffffff, #f5f5f5, #e2e2e2, #c0c0c0, #909090, #666666, #404040, #202020, #000000
  Semantic: --c-red: #f20000, --c-green: #16a34a, --highlighter: hsl(58, 92%, 75%) (pale yellow)
  From hd-style.css also: #111/#171718 (near-black), #0077b5 (LinkedIn blue, used for "LinkedIn" links), #1c6ea4/#00486f (secondary blues), #d0e4f5 (pale blue tint), plus standard Bootstrap-like greys (#f8f9fa, #dee2e6, #6c757d).
- Job board mechanics: custom WordPress custom-post-type ("jobs") with custom taxonomies job_location, job_category, job_type, job_sector (confirmed via sitemap structure) - a bespoke/self-built job board, not a third-party ATS widget embed (no Recruit CRM, Bullhorn, or JobAdder iframe/script detected). The actual candidate/CRM backend, per the Privacy Policy, is Vincere - used internally, not surfaced as a public embed.
- Hosting/CDN: Cloudflare in front of origin (server: cloudflare, cf-ray, cf-cache-status: DYNAMIC, HTTP/2, HTTP/3 via alt-svc: h3). Two unusual custom response headers observed on every response: "pre-cognitive-push: Enabled" and "quantum-flux-capacity: Omega" - not part of any known Cloudflare/WordPress product signature found via research; likely a custom Cloudflare Worker or reverse-proxy layer added by the developer. UNVERIFIED what these actually do.
- Email obfuscation: Cloudflare's automatic email obfuscation (/cdn-cgi/scripts/.../email-decode.min.js + /cdn-cgi/l/email-protection#...) hides the contact email from scrapers - literal email address could not be extracted from static HTML (working as intended, not a bug).
- Security headers present: Strict-Transport-Security: max-age=31536000 (HSTS), X-Frame-Options: SAMEORIGIN, X-Content-Type-Options: nosniff, X-XSS-Protection: 1; mode=block, Referrer-Policy: strict-origin-when-cross-origin. HTTPS enforced. No mixed-content issues observed.
- Page weight: homepage.html raw = 138,630 bytes (135 KB). Main theme stylesheet hd-style.css = 304,638 bytes (298 KB, single monolithic CSS file, no per-page code-splitting). light.css (CSS variable overrides only) = 384 bytes. Homepage contains 23 <script> tags and 3 <link rel="stylesheet"> references, plus 3 external third-party script hosts (cdnjs, jsdelivr, unpkg) in addition to self-hosted theme/plugin JS.
- Sample image weights (via curl -sI, all served by Sirv CDN as JPEG/PNG, no WebP/AVIF negotiated by default at these URLs):
  home-hero-1.jpg: image/jpeg, 242,368 bytes (237 KB)
  hero-4.jpg: image/jpeg, 99,313 bytes (97 KB)
  contact-gaia-talent.jpg: image/jpeg, 94,118 bytes (92 KB)
  cta-1.jpg: image/jpeg, 78,463 bytes (77 KB)
  Biodiversity.jpg: image/jpeg, 44,451 bytes (43 KB)
  b-corp-logo.png: image/png, 9,322 bytes
  logo-light.svg: image/svg+xml, self-hosted vector (negligible size)
  A ~237 KB unoptimized-looking JPEG for a hero image (no srcset/responsive size negotiated at that exact URL) is a real performance flag, though Sirv does support on-the-fly resizing/format negotiation via query params not exercised at this URL.
- Copyright year in footer: "(c) 2026 Gaia Talent." - correctly updated to the current year, no stale-copyright issue.
- Builder credit line: exact footer text - "Web Design by Hidden Depth." Hidden Depth is a Dublin web design agency (confirmed via WebSearch: "Gaia Talent Web Design Project - Dublin - Hidden Depth" at hiddendepth.ie/made/gaia-talent/).
- Viewport meta: width=device-width, initial-scale=1.0 present on every page fetched - correctly configured.

---

## 4. PROBLEM AUDIT (evidence-based)

1. Blank team-member profile pages (content bug, not just thin content): /team/keith/, /team/gian/, /team/isadora/, /team/diana-lupu/, /team/eva-obrien/ all return HTTP 200 with a valid page shell, correct nav/footer, and a page <title> (e.g. "Keith - Gaia Talent"), but the <main> element's inner content is empty in the raw server response - no H1, no bio paragraph, no role text, nothing. Raw HTML: <main id="main-content" data-scroll-container> <div class="container pb-8"> ... </div></main> with no text content between. Job pages (e.g. /jobs/senior-ecologist/) ARE fully server-rendered with rich text - proving the theme/CMS is capable of full SSR; team bios simply are not using it. This wastes 5 indexed, sitemap-listed URLs.

2. No JobPosting structured data: checked every fetched job page's raw HTML for the string "JobPosting" (schema.org) - zero matches, despite Yoast SEO otherwise emitting WebPage/BreadcrumbList/WebSite JSON-LD everywhere. This blocks eligibility for Google's "Jobs" rich-result carousel - a direct, fixable traffic/candidate-acquisition gap for a recruitment site whose core product is job listings.

3. Weak, generic homepage value proposition with almost no server-rendered copy: the homepage's entire static body text is 43 lines, much of it repeated nav/footer. The pitch is just "Connecting People with Purpose" / "Specialist recruitment" / four one-word sector tags / "Let's talk." No stat, no client logo, no testimonial, no case study, no "500+ placements" or "since 2017" claim anywhere.

4. Content staleness on the blog: post-sitemap.xml's own <lastmod> is frozen at 2022-09-23. Multiple still-live, still-linked posts reference stale events, e.g. verbatim from the /news/ index (viewed 2026): "Conference to address the biodiversity challenge in Ireland - The National Biodiversity Conference 2022 is critical for Ireland's public consultation..." - a 2022 conference framed in present/future tense, four years later, with no visible publish date shown anywhere on the post cards themselves (a design choice that hides how old the content is, which then backfires when the copy itself reveals the staleness).

5. Copy-quality/proofreading error on a client-facing services page: /services/, verbatim: "At Gaia Talent, we truly understand the getting the right person at the right time is crucial to your success..." - a grammatical error live on a page pitching recruitment expertise to enterprise clients.

6. No physical address published anywhere on-site: Contact page gives two phone numbers ("Dublin office" / "Clare office") and an obfuscated email, but no street address for either office - a trust-signal gap given a real registered Co. Clare address exists per third-party registries. No Google Business Profile embed, no map.

7. Missing standard trust/legal pages: only /privacy-policy/ exists; no visible Terms of Service, no standalone Cookie Policy page, no accessibility statement, and no company registration/CRO number displayed anywhere on-site - despite the privacy policy itself explicitly framing the company as a GDPR Data Controller.

8. Buried/undersold trust signals: B Corp certification and the "10 trees planted per placement" Hometree partnership are genuinely differentiated claims, but neither is rendered prominently on the homepage; the Hometree claim is buried three screens deep inside the Privacy Policy's data-sharing section, not featured as a marketing/trust element anywhere.

9. Analytics likely under-firing without consent, and wiring is opaque: Site Kit by Google plugin is active, dns-prefetch for googletagmanager.com is present, but no live GA4/GTM ID could be found actually firing in raw HTML - tracking appears gated behind the cookie-consent banner's "Analytics" category (correct GDPR practice), but this also means engagement data may be significantly under-collected if most visitors don't opt in.

10. Heavy, unoptimized-format hero imagery: home-hero-1.jpg alone is 237 KB as a plain JPEG served without responsive srcset/format negotiation at the referenced URL (despite Sirv CDN being capable of WebP/AVIF and on-the-fly resizing) - a straightforward Core Web Vitals/LCP risk on the homepage's largest visual element, especially on mobile.

11. Monolithic, unsplit CSS: a single 298 KB hd-style.css loads on every page regardless of that page's actual needs - no per-template code-splitting, so even /privacy-policy/ downloads the full stylesheet.

12. Non-standard/unexplained response headers: "pre-cognitive-push: Enabled" and "quantum-flux-capacity: Omega" appear on every response - not part of any known Cloudflare, WordPress, or CDN product signature found via research; worth a direct question to Hidden Depth about what these do, since unexplained custom headers on a production site are at minimum unusual and at most a leftover debug/joke header.

13. No broken links found in the sample tested (nav, footer, all taxonomy pages, sampled jobs/posts, all team pages) - a POSITIVE finding: link hygiene appears solid.

14. HTTPS/security posture is good, not a problem area: HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, and Referrer-Policy are all correctly set; Cloudflare TLS termination; no mixed content detected. This contradicts a generic "outdated/insecure site" assumption.

15. Modern animation stack contradicts a "2010s" visual-design assumption: GSAP + ScrollTrigger + Lenis smooth-scroll + split-type text animation is a current front-end animation toolkit, not dated jQuery-plugin-era tech (jQuery is still loaded only for WP core compatibility). A redesign pitch built purely on "your site looks dated" would be factually weak - the more accurate critique is thin/incomplete content and missing structured data, not visual dated-ness.

16. Accessibility spot-check: full contrast/focus audit not possible without a rendered browser (no Playwright per task constraints), but at the HTML level the empty team-bio <main> blocks mean zero accessible name/content for those 5 pages for screen-reader users - a concrete, confirmed accessibility failure, not a maybe.

17. Conversion path: reasonably clear for candidates (Jobs board -> individual job page -> "Apply now" + named consultant contact) and for clients (Services -> "Contact us today" / dedicated /callback/ request-a-callback form + /contact/ form with an "I am: Employer/Candidate" branch) - a functioning, sensibly-segmented dual funnel, not a problem area. The main conversion weakness is upstream of the funnel: the homepage itself doesn't strongly sell why to enter it (see #3).

---

## 5. PageSpeed Insights API

Attempted: curl -s "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https://gaiatalent.com/&strategy=mobile"

Result: HTTP 429 - quota exceeded. Full API error: {"error":{"code":429,"message":"Quota exceeded for quota metric 'Queries' and limit 'Queries per day' of service 'pagespeedonline.googleapis.com' for consumer 'project_number:583797351490'.","status":"RESOURCE_EXHAUSTED"}}

This environment has no PageSpeed Insights API key configured (or the shared/anonymous quota for this proxy project is already exhausted for the day), so no Lighthouse performance/accessibility/SEO/best-practices scores or "top opportunities" could be retrieved. Saved raw response: pagespeed_mobile.json. Recommend re-running this exact curl command with a valid key= parameter (a free Google Cloud API key with PageSpeed Insights API enabled) to get numeric scores. The manual findings in section 4 (large hero JPEG, monolithic CSS, multiple third-party script origins, jQuery + GSAP both loaded) are directionally consistent with a mobile performance score in the "needs improvement" range, but this is an inference, not a measured score - flagged UNVERIFIED pending API access.

---

## 6. WebSearch findings (external facts, cited)

Query: "Gaia Talent Ireland recruitment renewable energy"
Gaia Talent is described (aggregated across search snippets) as a specialist recruitment/career-management consultancy for the Green Industry sector across Ireland and the UK, covering Built Environment, Carbon Management, Circular Economy, Climate Change, Conservation, Energy, Energy Efficiency, Energy from Waste, Energy Storage, Engineering, Environmental, Green Start-ups, Hydropower & Onshore Wind, Renewable Energy, Solar Energy, Sustainable Transport, Utilities, Waste Management & Recycling, Water & Flood Risk, and Wave & Tidal Energy - matches (and slightly extends) the on-site sector list in section 2.
Sources:
- Gaia Talent | LinkedIn - https://ie.linkedin.com/company/gaia-talent
- GAIA TALENT LIMITED - Company Check Ireland - https://companycheck.ie/company/615983
- Ecology & Green Jobs in Ireland and the UK - Gaia Talent - https://gaiatalent.com/gaia-jobs/
- Energy Practice Lead (Renewables and Infrastructure) - Gaia Talent - https://gaiatalent.com/jobs/energy-practice-lead-renewables-and-infrastructure/
- Gaia Talent, Power Jobs, Ireland - ecologyjobsuk.com - https://www.ecologyjobsuk.com/browse-jobs/gaia-talent/power-jobs/ireland/renewable-energy-engineering/
- Ecology & Green Recruitment in Ireland & the UK | Gaia Talent - https://gaiatalent.com/
- Gaia Talent, Scotland - greenjobs.ie - https://www.greenjobs.ie/browse-jobs/gaia-talent/scotland/renewable-energy-engineering/
- GreenJobs company page - https://www.greenjobs.ie/companies/gaia-talent
- Gaia Talent in Ireland - greenjobs.ie - https://www.greenjobs.ie/browse-jobs/gaia-talent/
- Jobs - Gaia Talent - https://gaiatalent.com/jobs/

Query: "Keith Molony Gaia Talent founder"
Gaia Talent described externally as "Ireland's first specialist recruitment business for the Renewable and Environmental sector" (UNVERIFIED superlative, sourced only from a search snippet, not confirmed against a primary source). Keith Molony currently listed as Managing Director at Gaia Talent; separately his own LinkedIn headline reads "Founder, Gaia Talent | Certified B Corp." Holds a Post Grad in Business & Entrepreneurial Studies from UCD Michael Smurfit Graduate Business School (1997-1998) per search snippet (UNVERIFIED, not cross-checked directly against LinkedIn by this session). NOTE: a different person, "Keith Connellan - Head Of Research - Gaia Talent," also surfaced - do not conflate Keith Molony with Keith Connellan.
Sources:
- Keith Molony - Founder, Gaia Talent | Certified B Corp - LinkedIn - https://ie.linkedin.com/in/keith-molony-3715473
- Keith Connellan - Head Of Research - Gaia Talent - LinkedIn - https://ie.linkedin.com/in/keith-connellan-409703175
- Keith Molony's Post - LinkedIn - https://www.linkedin.com/posts/keith-molony-3715473_live-roles-with-gaia-talent-health-safety-activity-7208797179975512065-lUAo
- Gaia Talent Web Design Project - Dublin - Hidden Depth - https://hiddendepth.ie/made/gaia-talent/
- Keith Molony Email & Phone - RocketReach - https://rocketreach.co/keith-molony-email_78316347
- Gaia Talent Management Team | Org Chart - RocketReach - https://rocketreach.co/gaia-talent-management_b45abc12fc643a57
- Team - Gaia Talent - https://gaiatalent.com/team/

Query: "Gaia Talent" Limited company registration number Ireland CRO
Company Registration Number: 615983. Gaia Talent Limited set up Friday 24 November 2017. Registered address partially given as "Clare." Industry: "Other professional, scientific and technical activities n.e.c." Status: "Normal." Additionally: "Gaia Talent Ltd is a recruitment agency based in Co. Clare V95 VW74, Ireland, licensed by the Workplace Relations Commission (WRC) under reference EA4906." All of this is third-party-sourced (company-check aggregators), not confirmed directly against cro.ie or on gaiatalent.com itself - flagged UNVERIFIED at the primary-source level even though multiple independent aggregators agree.
Sources:
- Gaia Talent Limited - Vision-Net - https://www.vision-net.ie/Company-Info/Gaia-Talent-Limited-615983
- GAIA TALENT LIMITED - Company Check Ireland - https://companycheck.ie/company/615983
- Gaia Talent Ltd - SoloCheck - https://www.solocheck.ie/Irish-Company/Gaia-Talent-Limited-615983
- Gaia Talent | LinkedIn - https://ie.linkedin.com/company/gaia-talent
- Gaia Talent Ltd | Licensed Employment Agency in Clare - IrishTalents - https://irishtalents.com/recruitment-agencies/gaia-talent-ltd
- CRO.ie - https://cro.ie/

Query: "Gaia Talent LinkedIn employees B Corp Ireland recruitment"
Confirmed: Gaia Talent is a Certified B Corporation, B Impact Score 87.3 (vs. median 50.9 for ordinary businesses completing the assessment). LinkedIn company page exists and actively posts openings (e.g., "Junior Recruitment Consultant" role found via LinkedIn Jobs). Indeed also lists a Gaia Talent employer/careers profile. Headcount: UNVERIFIED - no specific employee count surfaced in any snippet; the on-site team page lists only 5 named staff (section 2), likely not the full headcount given the volume of live roles (64) being managed.
Sources:
- Gaia Talent - Certified B Corporation - B Lab - https://www.bcorporation.net/en-us/find-a-b-corp/company/gaia-talent/
- Gaia Talent | LinkedIn - https://ie.linkedin.com/company/gaia-talent
- 3 Gaia Talent jobs in Ireland - Dublin - LinkedIn - https://ie.linkedin.com/jobs/gaia-talent-jobs?start=0&count=25&trk=jobs_jserp_pagination_1
- Gaia Talent Careers and Employment | Indeed.com - https://ie.indeed.com/cmp/Gaia-Talent
- Junior Recruitment Consultant - Gaia Talent - LinkedIn - https://ie.linkedin.com/jobs/view/junior-recruitment-consultant-at-gaia-talent-3960758643
- Environmental Recruitment Services in Ireland & the UK - Gaia Talent - https://gaiatalent.com/services/
- Ecology & Green Recruitment in Ireland & the UK | Gaia Talent - https://gaiatalent.com/
- Gaia Talent - greenjobs.ie - https://www.greenjobs.ie/companies/gaia-talent
- Gaia Talent in Ireland - greenjobs.ie - https://www.greenjobs.ie/browse-jobs/gaia-talent/
- Team - Gaia Talent - https://gaiatalent.com/team/

Not found / not verified via WebSearch in this session: Glassdoor reviews, Google reviews/star rating, specific headcount number, exact founding narrative (vs. the CRO incorporation date), and any notable/viral LinkedIn posts from Keith Molony beyond the one job-ad post link surfaced above. A targeted follow-up search (e.g. "Gaia Talent Glassdoor reviews", "Gaia Talent Google reviews") would be needed if required.

---

## Files in this folder
homepage.html, sitemap.xml, robots.txt, page-sitemap.xml, team-sitemap.xml, jobs-sitemap.xml, category-sitemap.xml, job_location-sitemap.xml, job_category-sitemap.xml, job_type-sitemap.xml, job_sector-sitemap.xml, post-sitemap.xml, page_about.html, page_services.html, page_team.html, page_team_keith.html, page_team_gian.html, page_team_isadora.html, page_team_diana-lupu.html, page_team_eva-obrien.html, page_contact.html, page_gaia-jobs.html, page_jobs.html, page_privacy-policy.html, page_callback.html, page_news.html, job_senior-ecologist.html, light.css, hd-style.css, headers_homepage.txt, pagespeed_mobile.json, extracted_*.txt (per-page meta/heading/schema dumps), text_*.txt (per-page clean body text), extract.py/dump_text.py (extraction scripts used).
