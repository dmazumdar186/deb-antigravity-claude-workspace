# GreenJobs.ie zero-downtime cutover verification — evidence report
Run: 2026-10-12, from a cloud container (egress via TLS-inspecting proxy). Resolvers: Google DoH (dns.google) and Cloudflare DoH (cloudflare-dns.com). SOA serial observed: 2026101203 (zone edited today).

## PHASE 1 — who controls what

### 1.1 greenjobs.ie apex records (both resolvers agreed on every value)
| Record | Value | TTL (authoritative, as seen on first uncached resolver) | Zone owner |
|---|---|---|---|
| NS | ns1/ns2/ns3.webhostingireland.ie, ns4.webhostingireland.eu | 86400 | Web Hosting Ireland zone (Hosting Ireland) |
| SOA | ns1.webhostingireland.ie admins.hostingireland.ie serial 2026101203 refresh 86400 retry 7200 expire 3600000 min 86400 | 86400 | Web Hosting Ireland |
| A | 212.250.3.80 (RIPE STRATEGIES-1, PTR www-redirection.strategiesuk.net) | **14400** | WHI zone, points at Strategies |
| AAAA | none | — | — |
| MX | 10 filter1.webhostingireland.ie, 20 filter2.webhostingireland.ie | 3600 | WHI |
| TXT/SPF | `v=spf1 ip4:185.43.232.13 include:spf.webhostingireland.ie ip4:81.17.241.90 +mx +a +include:spf.strategiesuk.net -all` | 14400 | WHI zone; **authorises Strategies to send as @greenjobs.ie** |
| CAA | none | — | any CA may issue (good for cutover) |
| _dmarc TXT | **NXDOMAIN — no DMARC** | — | — |
| default._domainkey TXT | DKIM1 rsa 2048-bit key present | 14400 | WHI zone. Owner of private key UNKNOWN (cPanel on jade.webhostingireland.ie is the likely signer; Strategies' own domains greenjobs.co.uk / strategies.co.uk have NO `default` selector, so this key is not a Strategies-wide key) |
| strategies/k1/google/selector1/selector2/mail/dkim/s1/s2 ._domainkey | NXDOMAIN | — | — |

### 1.2 www chain
www.greenjobs.ie CNAME → www-greenjobs-ie.cname.strategiesuk.net (TTL **14400** in WHI zone) → A 64.253.47.65 (TTL 300, in Strategies' strategiesuk.net zone, SOA soa.strategiesuk.net; PTR 64-253-47-65.pool.strategiesuk.net; RIPE UK-PCCWGLOBALNETWORK 64.253.32.0/19). Both resolvers identical.

### 1.3 Subdomains
crt.sh returned HTTP 502 on four attempts (service down); Certspotter used instead. Certspotter names on certs for greenjobs.ie: `*.greenjobs.ie`, `www.greenjobs.ie`, `www.blog.greenjobs.ie`, and a shared SAN cert also covering Strategies' other boards (agency.strategies.co.uk, www.greenjobs.co.uk, www.renewableenergyjobsuk.com, www.solarjobsuk.com, www.windjobsuk.com, www.wastejobsuk.com, www.waterjobsuk.com, www.environmentaljobsuk.com, www.itarchitectjobs.com, www.servocaeducation.com, www.thirdsolutions.co.uk, www.mynqtyear.com, www.abenefit2u.com, www.academicsltd.co.uk, www.mbmtravelexecutives.co.uk, www.myfacilitiesmanagementjobs.co.uk, mail.greenjobs.co.uk). **Meaning: the live TLS certificate for www.greenjobs.ie is issued to and controlled by Strategies.** The new host must obtain its own cert; CAA absence permits this. Live cert chain could not be inspected directly (proxy re-signs TLS); Certspotter is the evidence.

Brute-forced common labels (36 tried, no wildcard: random label → NXDOMAIN):
| Host | A | Owner | Flag |
|---|---|---|---|
| www | CNAME → strategiesuk.net → 64.253.47.65 | Strategies | **FLAG 64.253.32.0/19** |
| @ (apex) | 212.250.3.80 | Strategies | **FLAG 212.250.3.0/24** |
| blog | 174.120.117.60 (theplanet.com/SoftLayer static, TTL 14400) | UNKNOWN third host; https resets, http UNKNOWN | not Strategies |
| mail, webmail, ftp, cpanel, autodiscover, autoconfig, old | 185.43.232.13 (jade.webhostingireland.ie) | Web Hosting Ireland cPanel | not Strategies |
| www.blog | on cert only; DNS not tested beyond proxy 502 | UNKNOWN | — |
Nothing other than apex and www points at Strategies.

### 1.4 Registrant / registrar (IEDR web WHOIS, 2026-10-12 12:08 UTC, via headless Chromium on weare.ie; saved whois/greenjobs_ie_registry_whois.txt)
- Registrant: **Greenjobs Limited** (Registry Registrant ID 382762-IEDR; name published ⇒ company).
- Registrar: **Hosting Ireland / Team Blue Internet Services IE Ltd** (hostingireland.ie) — confirmed from the Registrar field, not inferred from NS. Web Hosting Ireland and Hosting Ireland are the same registrar brand.
- Created 15/05/2008; expires 16/05/2027; updated 27/06/2026; status Registered; DNSSEC unsigned.
- Strategies appears nowhere in the registry record. RDAP (rdap.weare.ie) and port-43 whois were blocked from this container; the web WHOIS is the evidence.

### 1.5 Email
- MX: Web Hosting Ireland filters → mail hosted at WHI (jade.webhostingireland.ie). **No mailbox traffic flows through Strategies.**
- SPF: includes `spf.strategiesuk.net` = `ip4:212.250.3.0/24 ip4:154.59.141.0/24 ip4:45.33.124.95 ip4:64.253.47.0/24 -all` (TTL 900). So Strategies' platform **does send outbound mail as @greenjobs.ie** (job alerts, application forwards, registration mails) and is authorised by the current SPF. Also authorised: 185.43.232.13 (WHI jade), 81.17.241.90 (Blacknight colo — purpose UNKNOWN), WHI's include.
- DKIM: only `default` selector exists; signer UNKNOWN. Strategies' outbound mail is very likely SPF-only (no Strategies selector anywhere, and `_dmarc.strategies.co.uk` is p=none).
- DMARC: none on greenjobs.ie → no enforcement, no reporting; sender-reputation of the new platform starts from zero.
- Real job-alert headers: **UNKNOWN** — no mail from greenjobs.ie / strategiesuk.net exists in the connected Gmail account; nobody has supplied a sample.
- Comparison: greenjobs.co.uk (Strategies-owned sister) uses MX mail.greenjobs.co.uk → 185.43.232.13 (also WHI jade!) and SPF `+a +mx include:spf.strategiesuk.net`. So WHI hosts mail for both brands.

### 1.6 Records that must change at cutover
| Record | Current value | TTL now | Zone owner (who edits) | Change |
|---|---|---|---|---|
| greenjobs.ie A | 212.250.3.80 | 14400 | WHI panel (client) | → new host IP (or ALIAS/flatten). **Note: current apex serves HTTP 301 only; HTTPS on bare domain resets the connection — new host should fix this.** |
| www.greenjobs.ie CNAME | www-greenjobs-ie.cname.strategiesuk.net | 14400 | WHI panel (client) | → new host CNAME/A |
| greenjobs.ie TXT SPF | …+include:spf.strategiesuk.net… | 14400 | WHI panel | remove Strategies include, add new mail sender (e.g. Postmark/SES/Resend include), keep WHI include while mailboxes stay at WHI |
| default._domainkey (or new selector) | WHI/cPanel key | 14400 | WHI panel | add new sender's DKIM selector(s) |
| _dmarc | absent | — | WHI panel | add `v=DMARC1; p=none; rua=…` ≥14 days before cutover to see who sends |
| blog.greenjobs.ie | 174.120.117.60 | 14400 | WHI panel | decide: keep / redirect / retire (host UNKNOWN) |
| MX, mail/webmail/ftp/cpanel/autodiscover | WHI | 3600 / 14400 | WHI | no change |
All records are in the Web Hosting Ireland zone; Strategies controls only the target of the CNAME (strategiesuk.net zone) and the TLS cert.

## PHASE 4 — cutover rehearsal runbook (output only, not executed)
Gates are PASS only with a saved artefact (dig output, screenshot, email .eml) and tester + UTC timestamp.

| T | Step | Gate (PASS / FAIL) |
|---|---|---|
| T-21d | Add `_dmarc` TXT `v=DMARC1; p=none; rua=mailto:dmarc@…` in WHI panel. | Aggregate reports after 7 days show every source sending as @greenjobs.ie (expect 64.253.47.0/24 or 212.250.3.0/24 from Strategies, 185.43.232.13 WHI). FAIL if unknown sources appear and are unexplained. |
| T-14d | In WHI panel lower TTL on apex A and www CNAME from 14400 → 300. Record old values: A 212.250.3.80, CNAME www-greenjobs-ie.cname.strategiesuk.net, SPF string verbatim. | After 24 h: `dig @8.8.8.8` and `dig @1.1.1.1` both show TTL ≤300 for both names (SOA serial incremented). FAIL if either resolver still caches 14400. |
| T-14d | Request export from Strategies (see 3). Written confirmation of format, fields, delivery date. | Strategies replies in writing; FAIL if no reply in 5 working days → escalate, assume no hashes. |
| T-7d | New site live on new.greenjobs.ie (A record in WHI zone), valid cert (CAA absent so any CA issues). | Full Phase 2 parity checklist executed on staging; every row has tester + timestamp + evidence; zero FAIL rows on revenue functions (apply, employer login/post, alerts). |
| T-7d | Export received. Row counts: candidates, employers, live jobs, expired jobs (for 301 map), applications, alert subscriptions, invoices/credits, CV files count vs. DB rows. | Counts match Strategies' admin figures ±0; CV file count = CV rows; every candidate has e-mail. Password hashes present? If NO → stage forced-reset mail; send to one Gmail + one Outlook test account from staging: SPF PASS, DKIM PASS, DMARC aligned, lands in Inbox. FAIL if any header fails. |
| T-7d | 301 map loaded on new host for every pattern in Phase 3; test with the full urls.txt (expected ≥95% 301 to 200, 0 chains >1 hop, 0 loops). | Automated run saved as CSV. |
| T-1d | Decide: **freeze** job postings on old site (preferred: Strategies disables employer posting, or client announces freeze) OR plan delta export at T+2h. State chosen option in runbook. Default stated here: **freeze at T-24h + delta export of jobs/applications/registrations created after the main export, as CSV, at T0+2h**, since Strategies' willingness to disable posting is UNKNOWN. | Freeze confirmed in writing, or delta-export procedure tested once on staging. |
| T-1d | Re-verify TTLs still 300; re-verify old values documented; new host firewall allows all; monitoring (uptime check on / , /jobboard/cands/candLogin.asp, one job URL) armed. | All green. |
| T0 | In WHI panel: apex A → new IP; www CNAME → new host; SPF → remove `include:spf.strategiesuk.net`, add new sender include; add new DKIM selector. Do NOT touch MX / mail hosts. | Within 10 min: `dig` from 3 geographies (e.g. EU, US, APAC probes via DoH 8.8.8.8, 1.1.1.1, 9.9.9.9 or globalping) all return new values. Cert valid for both greenjobs.ie and www.greenjobs.ie (SAN both), no mixed content on home, job page, login, apply. HSTS: do NOT send HSTS until rollback window closes (T+7d), then add with short max-age. FAIL on any stale answer >10 min → wait, do not proceed to T+1h tests. |
| T0+1h | Smoke test every Phase 2 function on production as a real user: register, login, reset, save job, apply with CV, employer login, post job, buy credits (test card), newsletter, banner redirect, aggregator feed URLs 200, GA G-ZQPJGM484J firing, both GSC verification metas present. Real job-alert email to one Gmail and one Outlook address: Inbox not Spam, SPF/DKIM/DMARC all pass in headers, unsubscribe link on greenjobs.ie. | All rows PASS with evidence; any FAIL on apply / employer post / alerts → rollback decision within 30 min. |
| Rollback | In WHI panel restore: A 212.250.3.80; CNAME www-greenjobs-ie.cname.strategiesuk.net; SPF original string; delete new DKIM selector (optional). Old site is untouched because Strategies has NOT been given notice. | Both resolvers show old values within 5 min (TTL 300); https://www.greenjobs.ie serves old ASP site (ASPSESSIONID cookie present) within 15 min total. FAIL if >15 min → TTL step was not done. Precondition: HSTS not yet enabled. |
| T+7d clean | No sev-1, mail deliverability stable, GSC no coverage spike, 301 report clean. | Then and only then: give Strategies notice; request final delta export; archive old data; ask Strategies to keep redirect host alive 30 days (UNKNOWN whether they will). |

# PHASE 2 — live site inventory (worker report, verbatim; raw evidence in phase2/raw/, URL list phase2/urls.txt, 1,167 URLs)

## greenjobs.ie — Phase 2 read-only audit (2026-10-12)

Method: 89 read-only GETs via curl (`-A "Mozilla/5.0" -m 30`, 0.5–2 s apart, TLS verified via proxy). Raw bodies + response headers for every request are in `raw/<name>.html` / `raw/<name>.hdr`. No forms submitted, no accounts, no email. robots.txt disallowed paths (`/images/`, `/contact-us.cms.asp`, `/privacy.cms.asp`, `/terms.cms.asp`, `/jobboard/error-pages/`) were not fetched, except that the server itself 302'd several of our requests into `/jobboard/error-pages/banned.asp` (see §0.3) — we followed none of those redirects; one direct GET of `banned.asp` was made to classify the page (403) before the robots rule was re-checked; noted here for transparency.

Platform: footer on every page: `<a href="https://www.strategies.co.uk/job-board-software/">Job Board website by Strategies` (raw/home.html). Static assets from `https://sjbimg.com/jobboardv3/...?bn=3.1.3` (Strategies CDN, "jobboardv3" build 3.1.3).

## 0. Transport / headers / robots

| Check | Result | Evidence |
|---|---|---|
| `http://www.greenjobs.ie/` | 301 → `https://www.greenjobs.ie/` | raw/home_http.hdr |
| `http://greenjobs.ie/` | 301 → `https://www.greenjobs.ie/` (single hop to www+https) | raw/bare_http.hdr: `location: https://www.greenjobs.ie/` |
| `https://greenjobs.ie/` | **No TLS service**: `curl: (35) Recv failure: Connection reset by peer` | shell output; raw/bare_https.hdr empty |
| Server headers (all 200 pages) | `server: nginx`, `content-type: text/html; Charset=UTF-8`, `cache-control: private`, `x-xss-protection: 1`, `x-frame-options: DENY`, `x-content-type-options: nosniff`, HTTP/2 | raw/home.hdr, raw/jobdetail2.hdr |
| `X-Robots-Tag` | ABSENT on every response (grep over all 89 .hdr files: 0 hits) | raw/*.hdr |
| `Strict-Transport-Security`, CSP, `X-Powered-By` | ABSENT | raw/*.hdr |
| robots.txt (200) | `Sitemap: http://www.greenjobs.ie/sitemap.xml`; blocks Jobrapido UAs; `User-agent: * Disallow: /images/ /contact-us.cms.asp /privacy.cms.asp /terms.cms.asp /jobboard/error-pages/ /404.asp /404.htm`; a malformed `Allow:` line for Jooblebot | raw/robots.html |
| `<meta name="robots">` | ABSENT on homepage, job detail, cms pages | grep raw/home.html, jobdetail2.html, aboutus.html |

### 0.1 Canonical tags (platform bug: multiple canonicals per page)
- Homepage `/` (200): NO self-canonical; instead four stray canonicals from embedded CMS blocks: `<link rel="canonical" href="/all-energy.cms.asp" />`, `/international-hydrogen-and-fuel-cell-conference.cms.asp`, `/responsible-business-summit.cms.asp`, `/wastewater-innovation.cms.asp` (raw/home.html).
- Job detail `/jobs/11506159/principal-senior-sustainability-consultant-republic-of-ireland.asp` (200): `<link rel="canonical" href="/jobs/11506159/principal-senior-sustainability-consultant-republic-of-ireland.asp" />` appears TWICE, plus the same four stray cms canonicals (raw/jobdetail2.html). `/jobboard/cands/jobView.asp?v=11506159` (200) carries the same `/jobs/11506159/...` canonical (raw/jobview.html) — the SEO URL is canonical, jobView.asp is the legacy alias.
- cms page `/about-us.cms.asp` (200): NO self-canonical; the same four stray canonicals (raw/aboutus.html). `/companies/arup` (200): correct self-canonical `href="/companies/arup"` (raw/companies_arup.html).
- Canonical hrefs are relative (no scheme/host).

### 0.2 Cookies
Only one cookie ever set, on every response including 302s and 404s:
`set-cookie: ASPSESSIONIDSSETSTBR=<24 upper-case chars>; secure; path=/` — no `HttpOnly`, no `SameSite`, no `Domain` (host-only www.greenjobs.ie), session-scoped (raw/home.hdr, raw/candlogin.hdr, raw/jobapply.hdr; 58+ occurrences). Client-side JS sets `EUCookie=1` for 365 days (`createCookie("EUCookie",1,365)` in raw/cookiepolicy.html / home.html). Cookie policy page lists: ASPSESSIONID, EUCookie, Google Marketing Platform/Google Analytics, Constant Contact (raw/cookiepolicy.html).

### 0.3 Rate limiting / bot ban observed
At ~0.5 s spacing, after ~20 requests the server began answering `302 → /jobboard/error-pages/banned.asp` for arbitrary URLs (`/latest-jobs/`, `/browse-jobs/ecologist/`, `/jobs/11493300/...`, `/feed`, `/sitemap.asp`, `/sitemap_index.xml`, `/job-distribution-partners.cms.asp`, `/green-trade-shows.cms.asp`; raw/latest.hdr etc.). Also `/jobboard/cands/joblistings.asp` → 302 `/jobboard/error-pages/newBan.asp`. `banned.asp` itself returns **403** with an IIS-style "403 - Forbidden: Access is denied." body (raw/errorpages_banned.html) — the origin behind nginx is IIS/ASP classic. Re-fetching the same URLs at 2 s spacing returned 200. Treat the ban as intermittent per-session throttling; so some "302 banned" results below for probe paths are UNKNOWN rather than confirmed.

## 1. URL inventory

- `https://www.greenjobs.ie/sitemap.xml` → **404** (raw/sitemap_https.hdr). `http://...sitemap.xml` → 301 to the https URL (→404). `/sitemap_index.xml`, `/sitemap.asp` → 302 banned (UNKNOWN, hit during throttling). **No sitemap exists despite robots.txt advertising one.** Fallback: crawled links from homepage + every linked page fetched (depth ≈ 2–3) + the platform XML job feed.
- Raw list: `urls.txt` (1,167 lines: 1,044 distinct internal paths from crawled HTML + 122 jobview URLs from the XML feed; 1 comment line). Intermediates: `urls_internal.txt`, `urls_feed_jobview.txt`.

Counts (distinct paths seen in crawled HTML, `urls_internal.txt`):

| Pattern | Count | Notes / evidence |
|---|---|---|
| `/browse-jobs/<slug>/` | 511 | 441 on homepage alone (sector/keyword/company landing pages, e.g. `/browse-jobs/ecologist/` 200, `/browse-jobs/gaia-talent` as adredirect target) |
| `/jobs/<numeric id>/<slug>.asp` | 84 | Job detail SEO URLs, e.g. `/jobs/11506159/principal-senior-sustainability-consultant-republic-of-ireland.asp` 200. Legacy alias `/jobboard/cands/jobView.asp?v=<id>` 200. Live job count **122** ("122 Jobs found, viewing matches 1 - 10", raw/jobresults.html; `<job>` ×122 in XML feed) |
| `*.cms.asp` | 57 | Full list in urls_internal.txt; includes 20+ aggregator pages (`/broadbean.cms.asp`, `/idibu.cms.asp`, `/jooble.cms.asp`, `/linkedin.cms.asp`, `/logic-melon.cms.asp`, `/trovit.cms.asp`, `/jobrapido.cms.asp`, `/neuvoo.cms.asp`, `/simplyhired.cms.asp`, `/gigajob.cms.asp`…) all 200 where fetched |
| `/job-index/<slug>/jobs/` | 219 | SEO category index; `/job-index/` 200, `/job-index/advisor/jobs/` 200 |
| `/company-az` (+`?` variants) | 30 | `/company-az/` 200 → links to `/companies/<slug>` |
| `/companies/<slug>` | 10 | `/companies/arup` 200, self-canonical |
| `/featured-jobs/` | 6 variants | 200, 10 job links |
| `/latest-jobs/` | 5 variants | 200 (after retry), 10 job links |
| `/jobboard/cands/JobResults.asp?...` | 63 | county/region search links from homepage |
| `/jobboard/cands/*` total | 90 | candidate area |
| `/jobboard/clients/*` | 2 | `clientLogin.asp`, `lostlogin.asp` |
| `/jobboard/scripts/vbs/adredirect.asp?b=<id>&u=<url>` | 12 | banner click tracker |

## 2. Functional inventory

Legend: EXISTS = page fetched 200 with form/feature in body; NOT FOUND = 404; UNKNOWN = could not verify read-only.

### Candidate (jobseeker) accounts — all under `/jobboard/cands/`
- **Register — EXISTS.** `/jobboard/cands/candRegister.asp` 200. `<form name="frmCandRegister" action="candRegister.asp" method="post" autocomplete="off">` fields: `strName, strEmail, strEmail2, strPassword1, strPassword2, radHTMLEmail, chkMarketing, chkPrivacy, {E75CE029-140B-4A3E-A0A1-07049F2FC257} (checkbox honeypot), CaptchaAnswer, CaptchaID, strCandEm (honeypot text), pwdid, t, v, wl, ov, cmdSave`. Text: "Your password must be at least 8 characters, contain upper and lower-case letters and at least 1 number"; "you must confirm your email address by clicking on the relevant link in your membership registration email" (double opt-in). `/fastCandRegister.asp` → 301 to candRegister.asp. CAPTCHA is platform-native (`g-formCaptcha` ids), not reCAPTCHA.
- **Login — EXISTS.** `/jobboard/cands/candLogin.asp` 200. `<form name="frmCandLogin" action="candLogin.asp" method="post">` fields `v, r, strCandLoginEmail, strCandLoginPassword, login, cmdLogin`. Protected pages redirect here: `/candregisteredit.asp` → 302 `candLogin.asp?r=/jobboard/cands/candregisteredit.asp`; `/jobboard/cands/` → 302 candLogin.asp.
- **Password reset — EXISTS.** Link on login page: `<a href="/jobboard/cands/lostlogin.asp">reset password`. `/jobboard/cands/lostlogin.asp` 200: `<form name="frmLostLogin" action="LostLogin.asp" method="post">` fields `strEmail, t, cmdSave`. (`candForgotPassword.asp`, `forgottenPassword.asp`, `candPasswordReminder.asp` → 404.)
- **Account deletion / unsubscribe — EXISTS (behind login).** `/membership-cancellation.asp` 200: "When you have logged into your Membership Account ... click on the section called - Jobs by Email Subscriptions & Delete Account Form - and you can choose which information that you want to permanently delete or unsubscribe from".

### Job alerts by email — EXISTS
- `/jobboard/cands/jobsbyemail.asp` 200. `<form action="/jobboard/cands/jobresults.asp" method="POST" name="frmJobsByEmail">` fields: `strSendMeCandEmail (type=email), strKeywords, lstJobType, lstIndustrySector, lstJobCategory, lstRegion, lstVicinity, lstPreferredSalary, chkPrivacy, {E75CE029-...} honeypot, c=1, strJobseekerEm (honeypot), hidSendMe=1, submit`. Posts to the platform's jobresults.asp (alert = saved search).
- **Frequency: daily.** "Any new jobs added to our website that meet your specific criteria will be emailed to you on a daily basis" / "Receive new jobs by email each day by creating and saving Job Alerts by Email" (raw/jobsbyemail.html).
- **Sender address: UNKNOWN** (not in page text). RSS feed image URL `https://www.greenjobs.ie/images/email/email_logo.gIf` suggests platform-sent HTML mail branded from greenjobs.ie.
- **Unsubscribe link domain: UNKNOWN** (no alert email captured). JobApply page states for marketing mail: "you can remove yourself permanently from receiving these emails by clicking the unsubscribe button on any of these emails or by contacting us".
- Job search widget JS (raw/sitemin.html) references `frmJobsByEmail` / `chkJobsByEmail`.

### Saved jobs / wishlist — EXISTS (login-gated)
`/jobboard/cands/jobWishList.asp` → 302 `candLogin.asp?r=jobWishList.asp`. Nav text "Your Saved Jobs"; job results page has buttons `cmdRegAndAddToWishListTop/Bot` and checkbox `v` per job (raw/jobresults.html); job detail links `href="/jobboard/cands/jobWishList.asp"`.

### CV upload / apply flow — EXISTS, posts to platform
- Job detail: `<form name="frmJob11506159" action="/jobboard/cands/JobApply.asp?v=11506159&ov=v%3D11506159" method="post">` with `cmdApply` submit (raw/jobdetail2.html, same on raw/jobdetail1b.html).
- `/jobboard/cands/JobApply.asp?v=11506159&ov=v%3D11506159` 200: `<form name="frmJobApply11506159" action="/jobboard/cands/JobApply.asp?v=11506159&ov=v%3D11506159&a=1" method="post" enctype="multipart/form-data">` fields: `ov, qry, v, ca, bRetry, strName, strEmail, strEmail2, strCoveringNote (textarea), strCVPath (type=file), chkSaveCV, chknew_marketing, chkTerms, {E75CE029-...} honeypot, tt, win, cmdApply`. Client validation `custommsg:"Please attach your CV"` (CV required).
- **Stored on platform (confirmed) AND an account is auto-created:** "Tick this box if you would like to save this application CV to your Membership Account"; "(Full name, Email etc) to apply for this role will be saved to your Membership Account"; "A membership confirmation email containing your login details will be sent to the email address that you input below when making your application on this website".
- **Emailed to employer: UNKNOWN from page text** (no explicit "forwarded to the employer" sentence). Indirect evidence it is email-routed: the XML feed exposes per-job `<contactEmail>` addresses, 31 of 122 being Broadbean/aplitrak tracking addresses, e.g. `<contactEmail><![CDATA[amf.89576.2377@mattinson.aplitrak.com]]>` (raw/p_jobfeed_xml.html) — aplitrak addresses only work if applications are emailed. Some jobs instead instruct off-site application in the description ("To Apply Please send a CV and covering letter to careers@arthian…", raw/jobdetail2.html).
- Marketing checkbox text: "I would like to receive your weekly jobs newsletters AND occasional career related emails".
- `emailToFriend.asp` 404; "Email to a friend" link exists in page but its handler was not resolved (UNKNOWN).

### Employer / recruiter
- **Login — EXISTS.** `/jobboard/clients/clientLogin.asp` 200: `<form action="clientLogin.asp" method="post">` fields `strClientLoginUsername, strClientLoginPassword, login, r, cmdLogin`. `/jobboard/clients/` → 302 `clientLogin.asp?cv=`.
- **Password reset — EXISTS.** `/jobboard/clients/lostlogin.asp` 200: `<form name="frmLostLogin" action="/jobboard/clients/LostLogin.asp" method="post">` fields `strEmail, t, cmdSave`.
- **Self-serve registration — NOT FOUND.** `clientRegister.asp` 404. Onboarding is via enquiry form only.
- **Job posting — EXISTS behind login (text evidence only).** `/for-employers.asp` 200: "if you purchase a membership package you will be given free access to our employer management system that will allow you to manage your job postings (e.g. Post, edit, copy, renew job postings etc) and you will also be given telephone training". `jobPost.asp` 404 (guessed path). Actual post URL UNKNOWN.
- **Pricing / credit packages — EXISTS as sales text, NO price list online.** `/recruiter-zone-advertising.cms.asp` 200: "Job Posting Packages/Memberships Discounted rates are available for multiple job postings and annual memberships"; logo "displayed for up to 6 Weeks". `/pricing.asp` 404. No € amounts anywhere in fetched HTML. Enquiry form `/recruiter-zone-advertising-form.asp` 200: `<form name="frmAdvertising" action="" method="post">` (posts to itself) fields `compType, companyName, address1/2, addressTown/County/Country/Postcode, contactName, jobTitle, emailAddress, telephoneNumber, mobileNumber, bannerAd, emailCamp, companyProfile, featEmployerBtn, featuredJob, jbeAlert, weeklyJob, discountJobs, membership, singleJobPost, sponsorOpp, studentCampaign, newsJobWeek, weeklyNews, enquiryMessage, hearAbout, other2, CaptchaAnswer, CaptchaID, strCandEm, t` — the checkbox names enumerate the product catalogue (banner ad, email campaign, company profile, featured employer button, featured job, JBE alert, weekly job, discount jobs, membership, single job post, sponsorship, student campaign, news/jobs-of-the-week, weekly news).
- **Payment processor — NOT FOUND.** grep for `stripe|paypal|sagepay|worldpay|opayo|braintree|adyen` across all 95 fetched bodies and headers: 0 hits. Payment is presumably offline/invoice (UNKNOWN).

### Newsletter signup — EXISTS, third party (Constant Contact)
`/newsletter-signup.asp` 200: `<script id="signupScript" src="//static.ctctcdn.com/js/signup-form-widget/current/signup-form-widget.min.js" async defer>` and `<div class="ctct-inline-form" data-form-id="b9343e67-d1e4-4ed6-bece-f48dbc2087bf">`. No native form on the page. Cookie policy names Constant Contact. Subscriber list therefore lives in Constant Contact, not Strategies.

### Grievance form — EXISTS (platform-hosted, file upload)
`/grievance-form.asp` 200: `<form name="frmSendCV" action="grievance-form.asp" method="post" enctype="multipart/form-data">` ~45 fields incl. `type="file" name="cvfile"` (reused CV-upload template).

### Banner ad redirect tracking — EXISTS
`/jobboard/scripts/vbs/adredirect.asp?b=<bannerId>&u=<urlencoded target>`; 12 distinct on homepage (b=10468,10469,10473,5825,23057,23215,23832,23919,23949…). Probe: `adredirect.asp?b=23057&u=...gaia-talent` → **302** `location: https://www.greenjobs.ie/browse-jobs/gaia-talent` (raw/adredir_head.hdr). Click counts are therefore stored on the platform. No JS script contains "adredirect" (anchor hrefs only).

### Aggregator feeds
| URL | Status | Evidence |
|---|---|---|
| `/jobboard/xmlfeeds/jobfeed.asp?type=RSS` | 200, RSS 2.0, 119 `<link>` items, `<ttl>60</ttl>`, links `jobview.asp?v=<id>&rcode=RSS` | linked from homepage `<a href="/jobboard/xmlfeeds/jobfeed.asp?type=RSS" class="starter">RSS Feed`; raw/rssfeed.html |
| `/jobboard/xmlfeeds/jobfeed.asp` and `?type=XML` | 200, 760 KB, root `<GreenJobsIEJobFeed>`, 122 `<job>` with `companyName, companyType, contactEmail, recruiterLogoURL, jobRef, title, guid (…&rcode=XML), featured, premium, description…` | raw/p_jobfeed_xml.html |
| `/jobboard/xmlfeeds/jobfeed.asp?type=Indeed` | 200, 473 KB, Indeed schema `<source><publisher>GreenJobs IE</publisher>…<job><referencenumber>…<url>…&rcode=Indeed` | raw/p_jobfeed_indeed.html |
| `/jobboard/xmlfeeds/` | 200, empty body (0 bytes) | raw/p_xmlfeeds.hdr |
| `/rss.asp`, `/jobs.xml`, `/indeed.xml`, `/xml/`, `/jobboard/xml/`, `/sitemap_jobs.xml` | 404 | raw/p_*.hdr |
| `/feed` | 302 → banned.asp (UNKNOWN, throttled) | raw/p_feed.hdr |
Note the `type=` parameter is open (`rcode` tag per consumer) — Jooble/Trovit/etc. likely use further `type=` values (UNKNOWN). The feed leaks recruiter contact emails publicly (64 `@gaiatalent.com`, 31 `@mattinson.aplitrak.com`, plus slrconsulting, mottmac, tetratech, wsp, jacobs, arup, aecom…).
Partner pages (all 200): `/job-distribution-partners.cms.asp` (links to `/broadbean.cms.asp`, `/idibu.cms.asp`, `/logic-melon.cms.asp`, `/jobmate.cms.asp`); `/broadbean.cms.asp` ("Broadbean is the global leader in providing sophisticated… candidate attraction tools"), `/idibu.cms.asp`, `/logic-melon.cms.asp` ("Multiple Job Posting and Applicant Tracking"), `/jooble.cms.asp` (links `https://uk.jooble.org`), `/trovit.cms.asp`, `/linkedin.cms.asp`. These are descriptive pages; they confirm multiposting inbound (Broadbean/idibu/LogicMelon → platform) and aggregator outbound (Jooble/Trovit via XML feed), but no integration credentials are visible. Homepage footer text mentions "LinkedIn" and "RSS" only; no indeed/broadbean strings on the homepage itself.

### Verification / analytics tags (homepage and all pages)
- Google Search Console: `<meta name="google-site-verification" content="8TXHu9YS5z2Hvs3L7lRqUscFF83S9XDkTYdLAW_dmAE" />` and `<meta name="google-site-verification" content="ZEUDHG3aZ7w_xjbp3k1Zs3lbxDZqz9LPGa2jUw1FIw8" />` (two owners/properties).
- GA4: `<script async src="https://www.googletagmanager.com/gtag/js?id=G-ZQPJGM484J"` — measurement ID **G-ZQPJGM484J** (gtag, not a GTM container).
- NOT FOUND (0 hits across all pages): `UA-`, `GTM-`, `AW-`, Facebook pixel (`fbq`), Hotjar, LinkedIn Insight (`_linkedin_partner_id`), Microsoft Clarity. (`platform.linkedin.com/in.js` on one page is a share button, not Insight.)
- No JSON-LD / `JobPosting` schema on job detail pages (0 hits) — not eligible for Google for Jobs.

## 3. Third-party hosts and cookies

External `<script src>` / `<link href>` / iframe hosts seen (counts = pages):
| Host | Use |
|---|---|
| `www.googletagmanager.com` | `gtag/js?id=G-ZQPJGM484J` (51 pages) |
| `ajax.googleapis.com` | jQuery 1.11.0 (51 pages, protocol-relative) |
| `fonts.googleapis.com` | Roboto/Lato CSS |
| `sjbimg.com` | Strategies CDN: `/jobboardv3/scripts/JS/bootstrap.min.js`, `JobboardGlobal.js` (36 pages) |
| `www.greenjobs.co.uk` | favicon `GreenJobsFavicon.png`, cross-links, `candRegister.asp` cross-site link (sister site, same platform) |
| `static.ctctcdn.com` | Constant Contact signup widget (newsletter page) |
| `platform.linkedin.com` | `in.js` share button (http://, mixed content) on one page |
| `player.vimeo.com`, `www.youtube.com` | lightbox embed templates in JS (http://) |
| `blog.greenjobs.co.uk` | nav link (http://) |
Set-Cookie: only `ASPSESSIONIDSSETSTBR=<value>; secure; path=/` (see §0.2). No `_ga` cookie from server; GA sets its own client-side.

## 4. State held only on the Strategies platform (export requirements)

| Data set | Evidence it lives on the platform | Export to require |
|---|---|---|
| Candidate accounts + password hashes | `candRegister.asp` posts `strPassword1/2` to `candRegister.asp`; `candLogin.asp` authenticates `strCandLoginEmail/Password`; password policy text; double-opt-in confirmation; marketing flag `chkMarketing`, HTML-mail flag `radHTMLEmail`, privacy consent `chkPrivacy` | CSV/JSON: id, name, email, email_confirmed flag+timestamp, password_hash + **hash algorithm & salt scheme (UNKNOWN — must be stated; if unexportable, plan forced reset)**, created/last-login, marketing & privacy consent flags with timestamps, HTML-mail pref |
| CVs | `JobApply.asp` `strCVPath` file upload (required) + `chkSaveCV` "save this application CV to your Membership Account"; grievance form `cvfile` | File bundle (original filenames + MIME) keyed to candidate id and application id; CSV manifest |
| Applications | `JobApply.asp` multipart POST with `strName, strEmail, strCoveringNote, strCVPath`, `v` (job id), `ca`; "will be saved to your Membership Account" | CSV/JSON: application id, job id, candidate id/email, covering note, CV file ref, timestamp, source `rcode`, delivery status to recruiter (UNKNOWN whether recorded) |
| Saved jobs / wishlist | `jobWishList.asp` (login-gated), `cmdRegAndAddToWishList*` on results | CSV: candidate id, job id, added timestamp |
| Job alert subscriptions | `jobsbyemail.asp` POST (`strSendMeCandEmail` + 7 criteria fields, `hidSendMe=1`); daily send; cancellation inside "Jobs by Email Subscriptions & Delete Account Form" | CSV/JSON: subscription id, candidate email/id, keywords, job type, sector, category, region, vicinity, salary band, created, last-sent, active flag |
| Employer (client) accounts | `clientLogin.asp` (`strClientLoginUsername/Password`), `clients/lostlogin.asp`, "employer management system" text; no self-registration (clientRegister 404) → records created by Strategies/admin | CSV/JSON: client id, company, users (username, email, password_hash + algorithm UNKNOWN), logo files (`/jobboard/public/5104/clientlogos/Logo_18157.jpg` pattern), company profile pages `/companies/<slug>` HTML/markdown |
| Jobs (live + archived) | 122 live jobs in feed with `jobRef`, `contactEmail`, `featured`, `premium`, `companyType`; expired jobs UNKNOWN count | JSON/XML full dump incl. expired, with apply-routing email, posting/expiry dates, category/region taxonomies (`lstJobType, lstIndustrySector, lstJobCategory, lstRegion, lstVicinity` option lists from searchCriteria.asp) |
| Job credits / memberships / invoices | Only sales text ("purchase a membership package", "Job Posting Packages/Memberships", enquiry checkboxes `membership, singleJobPost, discountJobs…`); no online payment processor found → billing is offline; whether credit balances are tracked in the platform is UNKNOWN | CSV: client id, package, credits purchased/used/remaining, expiry, invoice refs (request; may not exist) |
| Banner ads + click stats | `adredirect.asp?b=<id>` 302 tracker, 12 banner ids on homepage | CSV: banner id, client, creative file, target URL, impressions/clicks, schedule |
| CMS pages | 57 `*.cms.asp` pages, `Jobboard.CMSEditorDisplay="Lightbox"` in `/conf/localsystem.js` | HTML export of each page + images |
| SEO landing taxonomies | 511 `/browse-jobs/`, 219 `/job-index/` pages generated from taxonomy | taxonomy tables (CSV) to regenerate URLs + 301 map |
| Newsletter subscribers | NOT on Strategies — Constant Contact form id `b9343e67-d1e4-4ed6-bece-f48dbc2087bf` | export from Constant Contact directly |
| Analytics / GSC | Google-owned (G-ZQPJGM484J, two GSC tokens) — transfer property ownership, not an export | — |

## Files
- `REPORT.md` (this), `urls.txt` (1,167 URLs), `urls_internal.txt`, `urls_feed_jobview.txt`, `raw/` (95 response bodies + headers).

# PHASE 3 — SEO exposure (worker report, verbatim; artefacts in phase3/)

## greenjobs.ie — SEO exposure audit (phase 3)

Date: 2026-10-12. Method: read-only GETs via `curl -A "Mozilla/5.0" -m 30` through the session proxy (TLS verified), plus WebSearch/WebFetch. Raw headers/bodies saved alongside this file as `hdr_*.txt` / `body_*.html` / `links_*.txt`.

**Credentials disclaimer:** no Google Search Console, Bing Webmaster Tools, Ahrefs or Semrush access was available. Every item that needs them (true index count, top-ranking URLs, click/impression data, backlink counts) is marked **UNKNOWN**, not estimated.

**Caveat on crawling:** after ~10 requests in ~1 minute the site began answering some URLs with `302 -> /jobboard/error-pages/banned.asp` (that page returns `HTTP/2 403`, body "403 - Forbidden: Access is denied."). `/jobboard/cands/joblistings.asp` returned `302 -> /jobboard/error-pages/newBan.asp`. Requests spaced 15-20 s apart succeeded again. The Jobweb platform rate-bans; any migration crawler must throttle.

---

## 1. Indexed URL estimate

| Engine | Query | Count shown | Verdict |
|---|---|---|---|
| Google (WebSearch tool) | `site:greenjobs.ie` | tool exposes no total | **UNKNOWN** |
| Google (WebSearch tool) | `site:www.greenjobs.ie` | tool exposes no total | **UNKNOWN** |
| Bing (curl `https://www.bing.com/search?q=site%3Agreenjobs.ie`) | HTTP 200; `class="sb_count">About 224,000 results` but the only `<cite>` on the page was `https://www.microsoft.com › en-us` — a consent/redirect shell, not a real SERP | **UNKNOWN** (count not trustworthy) |
| Bing (WebFetch) | "About 33,000 results", but every result was about bars in Denver; zero greenjobs.ie URLs; page said "Some results have been removed" | **UNKNOWN** (proxy geo garbage) |
| DuckDuckGo HTML (`https://html.duckduckgo.com/html/?q=site%3Agreenjobs.ie`) | HTTP 200, 14,162-byte body containing `anomaly` / `challenge`; no results | **UNKNOWN** (bot challenge) |

Observed indexed URLs (WebSearch, three queries; tool does not strictly honour `site:`, unrelated Wikipedia hits omitted). 16 distinct URLs, grouped by pattern:

**Homepage (1)** — https://www.greenjobs.ie/ ("GreenJobs, Environmental Jobs and Renewable Energy Jobs in Ireland")

**Browse root (1)** — https://www.greenjobs.ie/browse-jobs/ (indexed title is literally "in Ireland")

**Browse single facet `/browse-jobs/<category>/` (11)** — /consultancy/, /planning/, /conservation-jobs/, /fundraising/, /compliance/, /sustainability-jobs/, /accounting/, /green-jobs/, /environmental-jobs/ (+2 repeats across queries)

**Browse multi-facet `/browse-jobs/<type>/<cat>/<subcat>/` (1)** — /browse-jobs/permanent/emissions-jobs/policy/ ("Permanent, Emissions Jobs, Policy in Ireland")

**Browse category+region+county (1)** — /browse-jobs/biodiversity-jobs/ireland/sligo/

**`/jobs/<id>/<slug>.asp`:** 0 seen. **`*.cms.asp`:** 0 seen.

Takeaway: visible search exposure is overwhelmingly `/browse-jobs/...` facet pages. WebSearch's own summary noted one indexed homepage snapshot "is roughly four years old" (Mattinson Partnership branding, old counts) — Google's copy may be stale.

## 2. Top-ranking URLs and inbound links

- Top URLs by clicks/impressions: **UNKNOWN** (no Search Console).
- Most frequent pattern in results: `/browse-jobs/<category>/` (9 of 16), then multi-facet browse, then homepage. No job-detail or cms page surfaced.
- Third-party pages mentioning/linking greenjobs.ie (WebSearch `"greenjobs.ie"`, `"www.greenjobs.ie"`):
  - https://ie.linkedin.com/company/greenjobs — "The GreenJobs Network of Websites", lists "www.greenjobs.ie"
  - https://www.facebook.com/GreenJobsIreland/ — "contact info@greenjobs.ie, greenjobs.ie"
  - https://x.com/greenjobsirl — @GreenJobsIRL
  - https://www.onrec.com/directory/job-boards/green-jobs-ireland — "GreenJobs is a job board wholly dedicated to recruitment in the green industry sector... Launched in 2008"
  - https://ukrecruiter.co.uk/directory-ukrecruiter/listing/greenjobs-ireland/
- Not found: no Wikipedia, gov.ie or university career-page links in three searches (`greenjobs.ie site:ie OR site:wikipedia.org OR site:gov.ie OR site:ucd.ie OR site:tcd.ie` returned only the site itself plus noise). Absence here is not proof; backlink totals **UNKNOWN** without Ahrefs/Semrush.

## 3. Redirect map requirement — URL pattern inventory

Examples are live URLs observed in page source (`links_*.txt`) or fetched. "1:1" = deterministic 301 per old URL feasible.

| # | Pattern | Example old URL | Observed | Proposed new shape | 1:1 301? | Notes |
|---|---|---|---|---|---|---|
| 1 | Homepage | `/` | 200 | `/` | YES | |
| 2 | Job detail with slug | `/jobs/11491400/senior-environmental-consultant-environmental-compliance-and-circular-economy.asp` | 200 (first try 302 → banned.asp) | `/jobs/<id>/<slug>` | YES while live; **NO for expired IDs** | Map on numeric ID, ignore slug. Dead IDs today are **soft 200**: `/jobs/10000000/` → `HTTP/2 200`, `<title>- \| GreenJobs IE`. New site must 404/410 them; the historical ID list is needed. |
| 3 | Job detail, no slug | `/jobs/11490816/` | 200, canonical `/jobs/11490816/senior-waste-...-compliance.asp` | as 2 | YES | |
| 4 | Legacy job view | `/jobboard/cands/jobview.asp?v=11491400` (template link `jobview.asp?v=##ID##`) | linked, not fetched | `/jobs/<id>` | YES | Rewrite on `v=`. |
| 5 | Browse root | `/browse-jobs/` | 200 | `/jobs/` | YES | |
| 6 | Browse single facet (category/location/type/employer) | `/browse-jobs/consultancy/`, `/browse-jobs/carlow/`, `/browse-jobs/contract/`, `/browse-jobs/gaia-talent` (no slash, also 200) | 200 | `/jobs/<facet>/` | YES | 300+ facet slugs in `links_browse.txt`; map slash and no-slash variants. |
| 7 | Browse multi-facet | `/browse-jobs/permanent/emissions-jobs/policy/`, `/browse-jobs/biodiversity-jobs/ireland/sligo/` | indexed | replicate facets, or 301 to primary facet | PARTIAL | Combinatorial; 1:1 only if new site keeps same facet combinatorics; otherwise many-to-one. |
| 8 | Browse pagination | `/browse-jobs/page-2/`, `/browse-jobs/consultancy/page-2/` | 200, `rel=prev/next` | 301 to page 1 | NO | Contents shift daily. |
| 9 | Listing hubs | `/latest-jobs/`, `/featured-jobs/`, `/company-az/`, `/job-index/` | 200 | `/jobs/latest`, `/jobs/featured`, `/employers/`, `/jobs/index` | YES | `/latest-jobs/`, `/featured-jobs/` render `<title>in Ireland` — duplicate content today. |
| 10 | CMS pages | `/about-us.cms.asp`, `/all-energy.cms.asp`, `/green-job-sectors.cms.asp`, `/partners-and-links.cms.asp`, `/the-greenjobs-network-of-websites.cms.asp`, `/privacy.cms.asp`, `/terms.cms.asp`, `/contact-us.cms.asp` (~20 seen) | 200 | `/<slug>/` | YES | Static list. |
| 11 | Non-CMS top-level .asp | `/for-employers.asp`, `/grievance-form.asp`, `/newsletter-signup.asp`, `/membership-cancellation.asp`, `/recruiter-zone-advertising-form.asp` | linked | `/employers/`, forms | YES | |
| 12 | Search results (query string) | `/jobboard/cands/JobResults.asp?c=1&lstRegion=Ireland&lstVicinity=Cork` | 200, `<meta name="ROBOTS" content="NOINDEX, FOLLOW">`, `rel=next ...&pg=2` | `/jobs/ireland/cork/` for the ~45 footer region/vicinity combos; all else → `/jobs/` | NO in general | Already noindex. `jobResults.asp?sbt=qs&bj=1` and free-text → generic search. |
| 13 | Candidate area | `candRegister.asp`, `candLogin.asp?r=/jobboard/cands/candregisteredit.asp`, `fastCandRegister.asp`, `jobWishList.asp`, `jobsbyemail.asp`, `searchCriteria.asp`, `cookie-policy.asp`, `tellafriend.asp?v=<id>`, `candRegister.asp?wl=1&v=<id>&ov=...` | candRegister 200 (self-canonical), jobsbyemail 200, `/jobboard/cands/login.asp` 404, `joblistings.asp` 302 → newBan.asp | `/account/register`, `/account/login`, `/alerts` | YES for static entry points; NO for `?r=`/`?v=`/`?ov=` | Session/return-path params must be dropped. |
| 14 | Client area | `/jobboard/clients/clientLogin.asp` | linked | `/employers/login` | YES | |
| 15 | Ad click tracker | `/jobboard/scripts/vbs/adredirect.asp?b=23057&u=https%3A%2F%2Fwww.greenjobs.ie%2Fbrowse-jobs%2Fgaia-talent` (10 on homepage) | linked | 301 to decoded `u=` | NO (unbounded `b`) | Rule-based on `u`. |
| 16 | XML feed | `/jobboard/xmlfeeds/jobfeed.asp` | **HTTP/2 500** | `/feed/jobs.xml` | YES | Broken today. |
| 17 | Sitemap | `http://www.greenjobs.ie/sitemap.xml` | 301 → `https://www.greenjobs.ie/sitemap.xml` → **404** (`content-length: 16469`) | `/sitemap.xml` | YES | None exists today. |
| 18 | Error pages | `/jobboard/error-pages/banned.asp` (403), `newBan.asp`, `/404.asp`, `/404.htm` | 403 / robots-disallowed | none | n/a | |
| 19 | Blog host | `http://blog.greenjobs.ie/` | DNS `174.120.117.60`; http `503 Service Unavailable` (plain text, 114 bytes); https `curl: (35) Recv failure: Connection reset by peer` | `/blog/<slug>` if recoverable | **UNKNOWN** | Dead host; no post URLs enumerable. Check Wayback. |
| 20 | Bare http | `http://greenjobs.ie/` | 301 → `https://www.greenjobs.ie/` | keep | YES | |
| 21 | Bare https | `https://greenjobs.ie/` | **`curl: (35) Recv failure: Connection reset by peer`** — confirmed | serve cert + 301 to www | n/a | |
| 22 | Static assets | `/css/main.css?bn=3.1.3`, `/jobboard/css/...`, `/images/...` | linked | n/a | NO | `/images/` robots-disallowed. |

Cannot be mapped 1:1: 7 (facet combos unless replicated), 8 (pagination), 12 (query-string search), 13 (session/return params), 15 (ad redirector), 2 for expired IDs (soft-200 today; historical ID set UNKNOWN without Search Console), 19 (blog dead).

## 4. On-site technical checks (quoted artefacts)

**robots.txt** — `https://www.greenjobs.ie/robots.txt` → `HTTP/2 200`, `content-type: text/plain`, `content-length: 678`:
```
Sitemap: http://www.greenjobs.ie/sitemap.xml

User-agent: Mozilla/5.0 (compatible; Jobrapido/1.1; +http://www.jobrapido.com)
Disallow: /
User-agent: "Mozilla/5.0 (compatible; Jobrapido/1.1; +http://www.jobrapido.com)"
Disallow: /
User-agent: Mozilla/5.0 (JobRapido WebPump)
Disallow: /
User-agent: *
Allow: "Mozilla / 5.0 (compatible; Jooblebot / 2.0; ...)"      <- malformed Allow line
User-agent: *
Disallow: /images/
Disallow: /contact-us.cms.asp
Disallow: /privacy.cms.asp
Disallow: /terms.cms.asp
Disallow: /jobboard/error-pages/
Disallow: /404.asp
Disallow: /404.htm
```
Sitemap URL is http. Verified chain: `http://www.greenjobs.ie/sitemap.xml` → `HTTP/1.1 301 ... location: https://www.greenjobs.ie/sitemap.xml` → `HTTP/2 404`. **No sitemap exists on either scheme.**

**Canonical tags.** Every template's `<head>` contains an HTML-commented, inert block (body_home.html lines 96-100):
```
<!-- Events SEO -->
<!--        <link rel="canonical" href="/all-energy.cms.asp" />
        <link rel="canonical" href="/international-hydrogen-and-fuel-cell-conference.cms.asp" />
        <link rel="canonical" href="/responsible-business-summit.cms.asp" />
        <link rel="canonical" href="/wastewater-innovation.cms.asp" />-->
```
Live canonicals:

| Page | Canonical | Scheme/host |
|---|---|---|
| Homepage `/` | **none** | — |
| Job detail `/jobs/11491400/...asp` and `/jobs/11490816/` | `<link rel="canonical" href="/jobs/11491400/senior-environmental-consultant-environmental-compliance-and-circular-economy.asp" />` (emitted twice) | **relative** — no scheme/host |
| Browse `/browse-jobs/consultancy/` | **none**; `<link rel="next" href="/browse-jobs/consultancy/page-2/" />` | — |
| Browse `/browse-jobs/page-2/` | none; `rel="next" /browse-jobs/page-3/`, `rel="prev" /browse-jobs/` | — |
| CMS `/about-us.cms.asp` | **none** | — |
| `/company-az/` | `<link rel="canonical" href="https://www.greenjobs.ie/company-az" />` (twice) | absolute **https + www**, no trailing slash (URL has one) |
| `/jobboard/cands/candRegister.asp` | `<link rel="canonical" href="/jobboard/cands/candRegister.asp" />` | relative |

**X-Robots-Tag:** absent on every captured response (`grep -il x-robots hdr_*.txt` matched only the DuckDuckGo header file). Headers seen: `server: nginx`, `cache-control: private`, `set-cookie: ASPSESSIONID...; secure; path=/`, `x-frame-options: DENY`, `x-content-type-options: nosniff`, `x-xss-protection: 1`.

**Meta robots:** only on search results — `JobResults.asp?c=1&lstRegion=Ireland&lstVicinity=Cork` → `<meta name="ROBOTS" content="NOINDEX, FOLLOW">`. Homepage, job detail, browse, cms, company-az: none.

**hreflang:** none on any fetched page (grep → 0).

**Structured data:** job detail page has no `JobPosting` / `application/ld+json` — no Google for Jobs eligibility today.

**Redirects:**
- `http://www.greenjobs.ie/` → `HTTP/1.1 301 Moved Permanently`, `location: https://www.greenjobs.ie/` — **301 verified**.
- `http://greenjobs.ie/` → `HTTP/1.1 301 Moved Permanently`, `location: https://www.greenjobs.ie/` — **301 verified**, single hop.
- `https://greenjobs.ie/` → `curl: (35) Recv failure: Connection reset by peer` — **confirmed broken**.
- `https://www.greenjobs.ie/` → `HTTP/2 200`.

**Titles / status:** `/browse-jobs/`, `/latest-jobs/`, `/featured-jobs/` all `<title>in Ireland`; cms and 404 pages share `<title>GreenJobs | Environmental Jobs and Renewable Energy Jobs in Ireland`. `/does-not-exist-xyz` → `HTTP/2 404` (correct); unknown job IDs → 200 (soft 404).

## Open items (UNKNOWN without credentials)
- Google/Bing index counts; coverage report.
- Top URLs by impressions/clicks; historical job IDs that earned links.
- Backlink profile (referring domains, anchors).
- Whether blog.greenjobs.ie ever had indexed posts.

# PHASE 5 — Verdict

| Question | Answer | Evidence |
|---|---|---|
| Can the DNS switch be done without Strategies? | **YES.** Every record (apex A, www CNAME, SPF, DKIM, blog) lives in the Web Hosting Ireland zone (NS/SOA ns1.webhostingireland.ie, serial 2026101203); registrar is Hosting Ireland and registrant is Greenjobs Limited (IEDR WHOIS 2026-10-12). Strategies controls only the CNAME *target* in strategiesuk.net and the shared SAN TLS cert, neither of which is needed after the switch. CAA absent, so a new CA can issue. | §1.1, §1.2, §1.4, Certspotter list |
| Can it be rolled back in under 15 minutes? | **NO today, YES after the T-14d step.** Apex A and www CNAME TTLs are 14400 s (4 h) on both resolvers now; a revert would take up to 4 h to propagate. After lowering to 300 s and waiting ≥24 h, revert propagates in ≤5 min. Precondition: do not enable HSTS before T+7d. Old site keeps serving because Strategies gets no notice until T+7d. | §1.1 TTL column, §1.6, runbook Rollback row |
| What data cannot be migrated without Strategies' cooperation? | Candidate accounts + password hashes (algorithm UNKNOWN), stored CVs and applications, wishlists, daily job-alert subscriptions, employer (client) accounts (no self-registration, admin-created), expired-job archive, credit/membership balances if tracked, banner creatives + click stats, 57 CMS pages. Live jobs (122) and recruiter contact emails are scrapeable from the public feed `/jobboard/xmlfeeds/jobfeed.asp` without Strategies; newsletter list is on Constant Contact; GA4/GSC are Google-owned. | Phase 2 §4 table |
| What functionality, if missing on day 1, loses money the same day? | (1) Apply flow with CV upload and routing to the recruiter contact email (Broadbean/aplitrak addresses in feed) — paying clients' job adverts stop producing applicants. (2) Employer login and job posting (`clients/clientLogin.asp`) — clients cannot post what they paid for. (3) Daily job-alert emails to existing subscribers, with SPF/DKIM passing — the main traffic driver to adverts. (4) 301 map for `/browse-jobs/<facet>/` (the only pattern seen indexed) and `/jobs/<id>/` — organic traffic to adverts. (5) Aggregator feed URLs (Indeed/RSS/XML) — partner distribution the client sells. Banner `adredirect.asp?b=` 302 tracking is sold inventory too. No online payment exists (billing is offline), so no card-flow loss. | Phase 2 §2, Phase 3 §3 |
| Single biggest unverified assumption? | **That Strategies will hand over the candidate/employer database at all, in a usable format, with password hashes and CVs.** Nothing on the live site, in DNS, or in the registry gives the client any technical path to that data; it is purely contractual. Second: outbound mail from the new platform will inbox at Gmail/Outlook with zero prior DMARC history (no DMARC record, DKIM signer UNKNOWN, no sample alert email available to inspect). Third: the whole shared-cert/CNAME setup means Strategies could also redirect or kill the old host at any time once they notice traffic drop; the rollback target is theirs. | §1.5, §1.3, Phase 2 §4 |

## Checks that could NOT be run (never marked passed)
- crt.sh: HTTP 502 ×4 (Certspotter substituted).
- RDAP/port-43 whois for .ie: blocked by the container proxy (web WHOIS via headless browser substituted).
- Live TLS certificate chain of www.greenjobs.ie: proxy re-signs TLS; Certspotter log is the evidence.
- Real job-alert email From/Reply-To/DKIM headers: no sample exists in the connected Gmail; UNKNOWN.
- Google indexed count, Search Console top URLs, Ahrefs/Semrush: no credentials, engines blocked bots; UNKNOWN.
- blog.greenjobs.ie content: http 503, https reset; host appears dead; owner UNKNOWN.
- Employer-side job posting, credits and payment screens: behind login, not tested; price list absent from public site.
- Whether applications are emailed to employers or only stored: UNKNOWN (feed contact emails suggest email routing).
