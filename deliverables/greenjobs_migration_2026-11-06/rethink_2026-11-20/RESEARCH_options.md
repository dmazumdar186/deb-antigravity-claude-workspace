# RESEARCH: hosted job-board options for GreenJobs (2026-11-20)

All figures were read from live pages or search results on 2026-11-20. "UNVERIFIED" means no first-party page confirmed it. Prices are USD unless stated; none was taken from memory.

## 1. SaaS comparison (2 boards, zero custom code)

| Option | Price for 2 boards | 2 boards / 1 admin | Custom domain | CSV import | Feed import | Google for Jobs | Alerts | Export | EU hosting |
|---|---|---|---|---|---|---|---|---|---|
| Cavuno | One plan per account; Starter $39/mo ($348/yr), Basic $105/mo ($948/yr), Grow $249/mo ($2,388/yr) | Yes: "Run a network of job boards from a single account", all plans | All plans | Jobs and companies, CSV or XML, all plans; job-alert subscribers from CSV; candidates not importable | Recurring XML feed URL, all plans | All plans | Count against the subscriber cap: Starter 1,000, Basic 5,000, Grow 15,000 | CSV from every dashboard table, incl. candidates | No: the DPA says it "does not currently offer EU-only data residency" (SCCs on request) |
| Niceboard | Pricing page shows one "Custom" plan, no price (book a demo). Third-party sites give conflicting prices; treat as UNVERIFIED | Not mentioned on page: UNVERIFIED | Yes | Not mentioned (export only) | "XML import (120 import runs / mo)" | Yes | 10,000 subscribers | One-click export | UNVERIFIED |
| JBoard | Basic $149/mo ($119 annual), Standard $249, Advanced $449, Scale $849 | Not mentioned: UNVERIFIED | From Basic | Not mentioned | XML importers from Advanced ($449/mo; $359 on annual billing) | SEO on Basic; rapid indexing from Advanced | 3,000 to 50,000 by plan | XML feed export only on the page | Not stated |
| JobBoard.io | Search results: Basic $449/mo, Professional $649/mo (a third-party page shows a conflicting $100 tier). First-party page returned 403, so UNVERIFIED | UNVERIFIED | Basic (secondary source) | CSV importer on Basic (secondary source) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Job Board Fire | Essential $250/mo (Cavuno comparison page quoting them; first-party page not read) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | Up to 5,000 | UNVERIFIED | UNVERIFIED. White-label listed as "No"; demo required before access |
| SmartJobBoard | No prices on its page (contact sales or book a demo) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Jobbio | A recruitment-marketing platform that distributes jobs to partner sites, not a white-label board. Sources conflict on price (EUR199, $199, $104). Poor fit | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| WordPress + WP Job Manager | Core plugin free. Official add-on bundle "from $159 per year" (single site; developer licence covers more). Applications from $79/yr, Job Alerts from $49/yr, Resume Manager from $49/yr. Plus hosting, and WP All Import Pro for CSV and feed imports (price NOT found) | Two separate WordPress sites (or Multisite), not one admin | Yes | Via the WP All Import add-on (Pro needed for custom fields) | WP All Import Pro can run recurring imports from a feed | Needs a plugin or custom schema (Yoast is on the Gaia site; not tested for WPJM) | Alerts add-on | Full (you own the database) | Your choice of host |

Sources: niceboard.co/pricing; jboard.io/pricing; cavuno.com/pricing; cavuno.com/dpa and cavuno.com/gdpr (via search); wpjobmanager.com/shop; wordpress.org/plugins/wp-job-manager-xml-csv-listings-import; cavuno.com/compare/job-board-fire-vs-jobiqo; Capterra/SaaSWorthy via search. Fetched 2026-11-20.

### Not verified for any vendor
- Per-job apply by email versus external URL. Cavuno mentions external apply links and native applications; its page does not mention email apply.
- Candidate import with passwords or consent flags. Cavuno exports candidates but does not import them.
- Time to set up. No vendor states one.
- Whether the two boards can share the same jobs, or syndicate to each other. Cavuno's "network from a single account" is the closest claim; the mechanism is not shown.
- GDPR terms for Niceboard, JBoard, JobBoard.io, Job Board Fire and SmartJobBoard.

## 2. Gaia's own jobs: machine-readable feed (read-only, honest UA, no 403)

- `https://gaiatalent.com/wp-json/wp/v2/types` returned 200 and lists a `jobs` post type.
- `https://gaiatalent.com/wp-json/wp/v2/jobs?per_page=100` returned 200. `X-WP-Total: 83` jobs, one page, JSON with title, content, link, dates.
- `https://gaiatalent.com/jobs/feed/` and `/feed/?post_type=jobs` both returned 200 as RSS 2.0, about 36 KB.
- `robots.txt` returns `Disallow:` (empty, so all paths are allowed) and lists `/sitemap_index.xml`. `/sitemap.xml` returned 301.
- Conclusion: a machine-readable feed exists, open, with no auth.

Vincere (Gaia's CRM):
- Vincere help article "Post jobs to Indeed from Vincere" says Vincere "does not provide XML feeds directly to users". The same article also says jobs reach Indeed "via XML feed", so it contradicts itself. The native integration is a built-in Indeed toggle.
- Vincere also integrates with Broadbean (multiposting) and Access Volcanic (website). The Volcanic article's endpoint is for candidate data.
- No public Vincere jobs XML feed or general job-board API was found. Ask Vincere support or the Vincere Marketplace. UNVERIFIED.
- Diana says no jobs currently go via Broadbean. Gaia's WordPress site is already the best machine-readable source.

SaaS that can ingest a feed automatically:
- Cavuno: recurring XML feed URL on every plan.
- Niceboard: XML import, 120 runs a month.
- JBoard: XML feed importers from Advanced.
- WPJM: WP All Import Pro recurring import. The Gaia feed is RSS or JSON, so field mapping would be needed (not tested).

## 3. Double posting: Gaia's jobs on gaiatalent.com versus GreenJobs

Sources: `gaiatalent.com/wp-json/wp/v2/jobs`; `greenjobs.co.uk/jobboard/xmlfeeds/jobfeed.asp?type=RSS`; `greenjobs.ie/jobboard/xmlfeeds/jobfeed.asp?type=RSS`. Both RSS feeds are public, linked from the sites' footers, and returned 200. `greenjobs.ie/jobs` returned 404, but the home page and feed work.

- Gaia has 83 jobs (79 unique titles).
- greenjobs.ie RSS has 145 items. 73 of Gaia's 79 unique titles appear on greenjobs.ie (90 items match by normalised title).
- greenjobs.co.uk RSS has 85 items. 11 of Gaia's titles appear (13 items). The UK board mostly carries other employers' jobs.
- Text check (weak, since RSS descriptions are truncated): of 77 title-matched Gaia jobs, 22 matched an opening text snippet on greenjobs.ie. That is a lower bound, not a precise rate.
- Conclusion: most of Gaia's jobs on greenjobs.ie are the same jobs as on gaiatalent.com, so they are being posted twice by hand. This is verified by title overlap and partial text match. Whether Gaia posts them to GreenJobs first or to its own site first was not checked.
- The 78 UK and 145 IE live counts from FACTS match the RSS counts (85 and 145), so the RSS feed is a usable source of the live jobs.
- Consequence: if greenjobs.ie ingested the Gaia feed, up to about 73 of the 145 IE jobs would no longer need posting by hand. Not verified: the 6 unmatched Gaia titles, and apply method per job.
