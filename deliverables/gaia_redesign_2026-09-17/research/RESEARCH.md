# Gaia Talent website redesign — research synthesis (2026-09-17)

Companion files in this folder: `gaiatalent_com_audit.md` (full 17-finding audit with raw evidence),
`reference_demo_teardown.md` (motion mechanics of the sample site), `brief.md` (facts and verbatim copy),
`build_spec.md` (the panel-synthesised build decisions). Hidden Depth findings are summarised below;
the raw page dumps live in the session scratchpad only.

Everything marked UNVERIFIED must be confirmed before it is said to Keith.

## 1. What is actually wrong with gaiatalent.com

The operator's read was "very 2010s". The evidence says the *technology* is current and the
*content* is what dates it. Pitching "your site is old tech" would be wrong and Keith (or Hidden
Depth) could disprove it in a minute. Pitch content, proof and conversion instead.

| # | Finding | Evidence | Severity |
|---|---|---|---|
| 1 | All five team bio pages are blank. `/team/keith/` etc. return 200 with an empty `<main>` | raw HTML in audit §2 | Critical (trust, SEO, accessibility) |
| 2 | No JobPosting structured data on any of the 63 live roles, so no Google for Jobs eligibility | zero `JobPosting` matches across job pages; Yoast emits other schema | High |
| 3 | Homepage has ~43 lines of copy and no proof: no stats, logos, testimonials, founding year | homepage dump | High |
| 4 | B Corp (Impact Score 87.3) and Hometree ("a tree for every candidate we place… ten more in their name") exist but are logo-only or buried in the privacy policy | privacy policy text, bcorporation.net | High (best asset unused) |
| 5 | Blog frozen since 2022; a live post still frames "National Biodiversity Conference 2022" in present tense | post-sitemap lastmod 2022-09-23 | Medium |
| 6 | Services page typo: "we truly understand the getting the right person" | /services/ | Medium (undermines "accuracy") |
| 7 | No physical address, no CRO number, no terms or cookie page | site-wide | Medium |
| 8 | Hero is a 237 KB stock abstract JPEG served without responsive negotiation; 298 KB monolithic CSS on every page; 23 script tags | asset HEADs | Medium (unmeasured: PageSpeed API quota blocked) |
| 9 | Two odd custom response headers (`pre-cognitive-push`, `quantum-flux-capacity`) | headers dump | Low (ask the builder) |

What is *good* and must not be criticised: Cloudflare + HTTP/3 + HSTS and proper security headers;
GSAP/ScrollTrigger/Lenis motion stack; no broken links found; a sensible dual funnel
(Employer/Candidate) on the contact form; 63 live roles maintained weekly (sitemap 15 Sep 2026).

## 2. The builder: Hidden Depth (hiddendepth.ie)

Dublin, founded 2009 by Dave Meier, 2–9 people, WordPress specialist with an in-house theme
framework ("Omnia"; every inspected client site shares the same `hd--` / `hdanim-` component
classes: Gaia Talent, Kerry College, Liberties College, BHP Insurance). Published fee range
€5,000–€50,000, 40% deposit, typical timeline 40 working days (15–20 fast-track). Six-stage
linear process. Motion is GSAP + ScrollTrigger + Split-Type on every site. Clutch lists 0 reviews;
the only verifiable award is a 2011 Awwwards nomination. No published outcome metrics.

They are competent. The honest 10x is not "better platform" but:
speed (days, not 40 working days), a bespoke motion language rather than a shared kit,
copy written from Gaia's actual facts, conversion architecture with proof on the page,
structured data for jobs, a strict performance budget, and iteration in hours.

## 3. The reference sample (evolution-exhibits-v4.pages.dev)

No libraries. ~13 KB JS, ~37 KB CSS, system fonts. Fixed pill header that solidifies with a
page-progress bar; a sticky hero stage inside a tall track where scroll scrubs through N states
with crossfading copy and a step rail; a pinned card stack; a 3D drum stepper; IntersectionObserver
reveals; native `<dialog>` lightbox; complete reduced-motion / no-JS / <800px degrade ladders.
The scroll-state mechanic is the "flow" the operator wants, generalised here from video to a
generative canvas landscape moving through Gaia's real sectors.

## 4. Panel (Saraev, Hormozi, Karpathy, Cherny, a creative director, and Keith as buyer)

Converged on:
- Fix the blank team pages first; use the five real portraits and exact titles; never invent bios.
- Only real live roles, each linking to its gaiatalent.com page, stamped "as of 15 September 2026",
  every link HEAD-checked before publishing. A single dead or invented role would end the pitch.
- Surface B Corp 87.3, Hometree, 35 years combined experience, 63 live roles. No fabricated proof;
  logos, testimonials and placement counts are Keith's to supply.
- Keep Gaia's own lines ("Schedule a confidential one to one chat", "Connecting People with Purpose")
  and phone-first contact. No chatbot, no self-serve calendar, no AI wording anywhere public.
- Do not slag Hidden Depth. The note to Keith says their build is solid and this is about content.
- One signature motion moment (the sector flow), one pinned sequence (how a search runs), a live-roles
  rail. Cut the 3D drum, the dark/light toggle, count-up tiles.
- Committed colour strategy on Gaia's own navy and green (navy as base, green as the single accent,
  amber only for the "live" rail); Archivo + Public Sans; cool light sections between navy ones.
- Static, relative-path bundle: works from a folder, under a GitHub Pages sub-path, and on
  gaiatalent.com unchanged. `noindex` while it lives on the demo domain so it cannot compete with
  Gaia's real site in search.
- Honest engineering claims only: bytes measured by the build script; no Lighthouse score unless run.

Disagreements resolved by the orchestrator: web fonts kept (distinctiveness outweighs ~60 KB);
dark hero and proof bands alternated with light sections rather than an all-dark site, so it reads
as a firm and not a product; the CRO number stays off the public page (third-party sourced).

## 5. Facts that only Keith can confirm (ask, do not assume)

Founder vs Managing Director wording; CRO 615983 and the Clare registered address; a contact email
for the form; whether any client may be named; any placement count; team bios in their own words;
whether Isadora should appear as consultant on every role (the site currently does this).

## 6. Data captured

63 live roles parsed from gaiatalent.com on 17 Sep 2026: 62 permanent, 1 contract; Dublin 21,
Carlow 9, Cork 9, Galway 6; 7 disclose a salary (not shown on the redesign); all list Isadora.
Files: `src/data/jobs.json`, `sectors.json`, `consultants.json` in the deliverable.
