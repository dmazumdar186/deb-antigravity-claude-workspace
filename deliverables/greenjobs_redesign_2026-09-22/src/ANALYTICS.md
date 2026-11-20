# GreenJobs analytics (GA4 + Search Console)

Build: `build_site.py --analytics production` (or `GJ_ANALYTICS=production`). Default `off` = staging: no tag, meta or script, robots unchanged.
Config: `src/analytics.json` (GA4 id, optional `gsc_token`, production hosts, sitemap origins). IE `G-ZQPJGM484J`, UK `G-ZFW03XQE2N`.

Consent: Consent Mode v2 defaults all denied; `gtag.js` is requested only after "Accept analytics" (or the Settings toggle) on a production host. "Essential only" and the saved choice (`localStorage gj-consent`) persist; changing it in Settings updates consent live.

Events (allow-listed params only: job_id, sector, region, src_page, apply_mode; never email/name/phone/employer):
- `apply_click` link-mode Apply button (job_id, sector, region)
- `apply_submit` email-mode on-site form submit (job_id only)
- `alert_signup` alert form; `newsletter_signup`; `job_view` on job pages (job_id, sector)

Search Console: DNS TXT (after the nameserver move) in Search Console, add Domain property, copy the TXT value into a record at the DNS host; no code needed. Optional meta: set `gsc_token` and rebuild. Sitemaps (`/sitemap.xml`, `/sitemap-jobs.xml`) are listed in robots.txt in production builds; submit both in Search Console.

CSP: an analytics build adds exactly the `csp_hosts` in analytics.json to the generated Pages `_headers` (`build_site.analytics_csp`; anything outside `GA4_CSP_ORIGINS` fails the build); staging `_headers` carry no Google host. Worker-rendered pages (`platform_worker/src/routes/board.js`, `render/pages.js analyticsCtx`) emit the same `_shell` analytics head, banner and `data-ev` attributes, but only when the request host is in `production_hosts` (workers.dev staging never). `job_view` fires on any page with the apply aside (static and Worker), after load so `analytics.js` has registered. Tests: `tests/greenjobs_redesign/test_analytics.py`, `tests/greenjobs_redesign/platform/board_wiring.test.mjs`.

Cutover note: robots `Disallow: /` and `noindex` remain until the DNS cutover (separate decision).
