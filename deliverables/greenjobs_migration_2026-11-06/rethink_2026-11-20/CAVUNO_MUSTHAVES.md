# Cavuno must-have verification (read-only, 2026-11-20)

Method: public cavuno.com pages only, fetched via a read-only fetch tool (page text summarised by a small model, so quotes are as returned by it, not byte-checked). No signup, no payment. Not blocked anywhere. Note: the RFP blog page text ended with an embedded instruction aimed at the reader; ignored.

## Verdicts

| # | Must-have | Verdict |
|---|-----------|---------|
| 1 | Per-job apply email OR external URL, both on one board | **YES (with a caveat)** |
| 2 | Job alerts to candidates + subscriber import | **YES** |
| 3 | Two boards on own domains from one account | **YES**; 8 sector sites as filtered views: **NO** (redirect only) |
| 4 | CSV import jobs + companies; users | Jobs/companies **YES**; apply email and expiry column **NO/UNVERIFIED**; candidate import **UNVERIFIED** |
| 5 | EU residency / DPA | DPA+SCCs **YES**; EU-only residency **NO** (US hosting); the exact "not currently offer" sentence **UNVERIFIED** (not found) |
| 6 | Recurring feed from WordPress | XML/RSS-channel feed **YES**; JSON (/wp-json) **NO** |

## 1. Apply method per job: YES
- https://cavuno.com/docs/managing-jobs/create-job-posting : "enter an external URL (like `https://company.com/apply`) or email address" to send candidates elsewhere; "Choose **Native applications** to collect applications directly on your board".
- https://cavuno.com/docs/your-job-board/posting-a-job : "The public form asks for an external application email or URL." Native apps need Starter+, candidate accounts, and the employer dashboard; "These are different posting surfaces". Page does not explicitly say both coexist on one board (implied).
- https://cavuno.com/docs/board-setup/job-form-settings : "Apply method is locked because a job without one cannot be applied to."
- Caveat: the per-job selector wording is thinner than asked; confirm email-per-job on a trial board.

## 2. Job alerts + subscriber import: YES
- https://cavuno.com/docs/job-alerts : "Job alerts are automated weekly email digests sent to subscribers when new jobs match their saved filters." Weekly only.
- https://cavuno.com/docs/import-export/csv-import-export : subscriber CSV fields Email (required), Sign-up date, Status. Imported people are "Pending confirmation" and get an email asking them to confirm; if unconfirmed after 60 days they show Unsubscribed. Skips role addresses (info@, noreply@), duplicates, previously unsubscribed. Must confirm "permission to send job alerts to every imported address". Pending people do not count toward the subscriber cap until confirmed. IMPACT: re-consent step loses part of any existing list; check lawful basis.
- Subscriber caps (https://cavuno.com/pricing): Starter 1,000; Basic 5,000; Grow 15,000.

## 3. Multiple domains
- Pricing https://cavuno.com/pricing : "Multiple job boards, run from one account." https://cavuno.com/docs/billing/plans-and-pricing : no limit on boards per account; each board has its own subscription; only one board can be unpaid (Free/trial) at a time; Starter trial once per person. Custom domain on every paid plan (and during trial).
- https://cavuno.com/docs/board-setup/connect-custom-domain : more than one domain can be connected to one board, but other active domains "permanently redirect to the primary domain, keeping the path and query string." Page says nothing on multiple boards per account or domain limits. "Domain already in use" -> contact support.
- Filtered view of a board on an extra domain: NO documented. Nothing found on docs index. Sector sites would be redirects (OK as fallback) or separate small boards (each = its own paid subscription, from $29/mo annual), or headless SDK frontend (https://cavuno.com/docs/sdk, Cloudflare Workers guide) which is build effort, not a feature.

## 4. Import
- https://cavuno.com/docs/import-export/job-import : "CSV and XML files up to 10 MB". Columns: "title, company, location, description, salary, employment type, application URL, and external ID." External ID mapping "recommended but optional"; it is the job identity, re-import "updates the existing listing instead of creating a duplicate." Salary: yes. Apply email: not documented (only application URL). Expiry column: none documented; imported jobs "expire if the apply link is dead"; changelog 20 Aug 2026 "Automatic job expiry now covers imports."
- Companies: https://cavuno.com/docs/import-export/csv-import-export : "Only the 'name' field is required." "Optional fields are website, summary, description, logo, linkedinUrl, xUrl, and facebookUrl." No row limits stated.
- Candidates/users: not documented as importable (UNVERIFIED, likely NO); they export only (https://cavuno.com/docs/import-export/data-export: Jobs, Companies, Job seekers, Job alert subscribers, blog tables; up to 200,000 rows CSV).

## 5. Data residency and DPA
- https://cavuno.com/docs/legal/sign-dpa : "The DPA is an Article 28 GDPR agreement with Wollemia Pty Ltd, trading as Cavuno." "The EU Standard Contractual Clauses are built in: Module 2 when you are a controller and Module 3 when you are a processor." UK Addendum and Swiss amendments included. Subprocessors at /subprocessors.
- https://cavuno.com/dpa (DPA text): Annex III "US (AWS)" (Convex DB); Hetzner "United States; entity in Germany"; Cloudflare "storage in US and EEA". "When the Services end, or on the Customer's written request, Cavuno will delete Customer Personal Data without undue delay." (cl. 10.2). 7 days' notice of new subprocessors (cl. 6.2). Breach notice "without undue delay" (cl. 8.1). No EU-only residency commitment.
- https://cavuno.com/security : infrastructure "is located in the United States"; AES-256 at rest; backups 7 days.
- https://cavuno.com/gdpr : "We store most data in the United States."
- https://cavuno.com/subprocessors : 24 subprocessors incl. OpenAI, Anthropic, xAI, Alibaba Cloud (Singapore), DeepSeek (China), Xiaomi MiMo. AI processing of imported job data / CV parsing goes to US and Asian vendors: DPIA concern.
- The sentence "not currently offer EU-only data residency": **UNVERIFIED**. Not found on /docs/legal/sign-dpa, /dpa, /gdpr, /security, RFP blog or site search. Substance (no EU-only residency) is supported by the above pages. Possibly in the Privacy Policy/Terms, not fetched.

## 6. Recurring feed + plan/trial
- https://cavuno.com/docs/import-export/recurring-xml-feeds : "Every 1, 3, 6, 12, or 24 hours" (default 6h). Public "`http` or `https` XML; gzip is supported"; "JSON and web pages are rejected". RSS not named there, but job-import page says XML can be "a flat feed or an RSS-style channel feed". Required mapping: title, company, application URL or email; mapping editable and stored. Dedupe by external ID, else application URL + title. "created or updated in place". Expire: "missing for two consecutive successful runs"; "empty or unparseable feed never expires anything"; >~40% missing pauses expiry. "up to 10 feeds per board."
- So gaiatalent.com/jobs/feed/ (RSS XML) is plausible; /wp-json/wp/v2/jobs (JSON) is rejected. Must test the real feed: WP RSS usually lacks company/apply URL fields and needs custom elements.
- Plan: https://cavuno.com/pricing : "New accounts get a 14-day Starter trial with no credit card"; board goes private again after trial unless subscribed. Import, recurring feeds, Google for Jobs, CSV export, unlimited team members listed as on every plan including Starter. Plan gating of feeds is not stated on billing page, pricing page says every plan.
- Prices (monthly / annual per month): Starter $39 / $29 (500 jobs, 1,000 subscribers); Basic $105 / $79 (1,500 jobs, 5,000 subs, custom email domain, branding removal); Grow $249 / $199 (5,000 jobs, 15,000 subs, 90-day audit log).
- Minimum plan for all six: Starter per board, but custom email sender domain (alert emails from greenjobs.ie) needs Basic ($79/mo annual). Two boards = 2 subscriptions; 8 sector boards would be 8 more.

## Extras
- Employer self-posting: YES. https://cavuno.com/docs/your-job-board/employer-accounts : "An employer signs up through the employer sign-up page, which is available when employer accounts are enabled."; employer approval can be Manual (changelog 18 Nov 2026).
- Staff roles: YES. https://cavuno.com/docs/team/manage-roles : Owner, Admin, Editor; unlimited team members (pricing).
- Google for Jobs: YES. https://cavuno.com/docs/job-board-seo/google-for-jobs : "Every published job listing on your Cavuno board includes `JobPosting` structured data."
- Data export: YES. CSV of any dashboard table, API JSON/CSV (https://cavuno.com/docs/import-export/data-export). Applications not in tables; coordinated return via hi@cavuno.com (https://cavuno.com/docs/legal/ownership-and-termination).

## Biggest blockers
1. Sector domains cannot be filtered views; only redirects or separate paid boards.
2. Hosting is US-only; no EU-only residency; AI subprocessors in China/Singapore.
3. Alerts: weekly digest only; imported subscribers must re-confirm.
4. Jobs import has no documented apply-email or expiry column.
