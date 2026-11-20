# Live public snapshot, 2026-11-20 (internal)

## Status: LIVE CRAWL NOT RUN
The first request to https://www.greenjobs.ie/ from this sandbox returned HTTP 403 (nginx). I did not retry with other
headers or a browser User-Agent. The crawler is built and tested offline; run it from a machine the site accepts:

    python3 execution/gtm_client_workflows/greenjobs_redesign/scrape_greenjobs.py --snapshot --sleep 1.0
    (--snapshot --dry-run prints the plan and makes no request)

It writes jobs_uk.json, jobs_ie.json, employers.json and redirect_map.json here (JSON only). The files jobs_*.json and
employers.json in this folder are NOT_RUN placeholders and hold no job data. No count below comes from the live site.

## What exists now
- Crawl: robots.txt honoured, sitemap(s), homepage facets, every results page until no new ids (count from source
  `numResultsTop`, mismatch recorded in `errors`), every job page; <= 1 req/s; UA `GreenJobsMigrationSnapshot/1.0`.
- Apply mode per job (evidence kept): hidden `strAppLink` is the rule. mailto -> `email`; external https host -> `link`
  (host recorded); otherwise e-mail in description near an apply word -> `email`; else the site's own
  `JobApplyLink.asp` form -> `onsite_form`. On the 5 recorded pages (Sept 2026 corpus): 5/5 `link` (mottmac.com x2,
  Oracle Cloud, aecom.jobs, careers.jacobs.com). Unproven: how an email job looks (no recorded example).
- Feed markers: Broadbean, Idibu, LogicMelon, JobG8 and other multiposters searched in apply URL, job ref, hidden fields and
  page source; tracking params and job-ref shape recorded. An employer ATS host alone is not a feed. On the 5 recorded
  pages: 0 vendor hits. Verdict on "is a feed still live?": INCONCLUSIVE (5 pages, 2 months old; needs the full crawl).
- Employer class from the employer field: gaia / chm_recruit / mattinson / third_party. Caveat: if Gaia posts under a
  client's name, the field cannot show it.

## Redirect map (offline, from the 28 Sept snapshot; NOT live)
redirect_map.json: IE 616 old URLs, 100 mapped, 516 unmapped; UK 590, 110 mapped, 480 unmapped.
Mapped: job pages -> `/{ed}/jobs/{id}/` (ids not live -> `/{ed}/jobs/`), results paging -> `/{ed}/jobs/`, `/for-employers.asp`,
`/recruiter-zone-advertising.cms.asp`, `/company-az/` -> `/{ed}/employers/`, `/green-job-sectors.cms.asp` -> `/{ed}/sectors/`,
and 6 `/browse-jobs/{slug}/` per site that feed the 4 landing pages (ecology, renewable/solar/wind, sustainability,
Dublin or London).
Unmapped patterns (proposed target):
- `/browse-jobs/{slug}/` sector, category, region, job-type and employer pages (IE 505, UK 469): the build has no such
  pages. Proposed `/{ed}/jobs/` (employer slugs: `/{ed}/employers/`). Each needs a decision, or a board filter URL.
- 11 static pages (about-us, contact-us, client-testimonials, cv-writing-service, job-distribution-partners,
  join-our-social-media-network, newsletter-signup, one-percent-for-the-planet-member, partners-and-links,
  talent-finder-network, the-greenjobs-network-of-websites): no equivalent. Proposed `/{ed}/`.
- Not yet inventoried because they need a live crawl: sitemap URLs, candidate account pages (login, register, wish list),
  banner redirects, `jobview.asp?v=` and `JobResults.asp?lstRegion=` variants (rules are coded and tested).
- Target prefix: the build puts editions under `/ie/` and `/uk/`; whether production serves them at the domain root is a
  cutover decision.

## Counts vs Keith's team
Told: 105 UK / 133 IE live. Observed 16 Nov: 78 UK / 145 IE. Sept snapshot: 98 UK / 88 IE. The 20 Nov live count is not
known. Nothing here contradicts the 16 Nov review; nothing here confirms it either.

## Tests
`tests/greenjobs_redesign/test_snapshot.py` (28 tests, offline fixtures); `test_scrape.py` 103 pass; `run_tests.sh` ALL GREEN.
