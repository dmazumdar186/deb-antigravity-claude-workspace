# Acceptance gates: the five stories ASSET asked to see (5 Nov 2026)

Source: Veena Khatri's email of 5 Nov 2026 (demonstration request). These five stories, word for word, are the contract for both demos: Option A (WordPress plugin `wp_demo/`) and Option B (custom platform `custom_demo/`). A story passes only if **every** gate below passes on **both** options, on the **deployed** URLs, at 1440 px and at 390 px.

| # | Story (client's words) |
|---|---|
| S1 | Create and edit a congress in WordPress. |
| S2 | Display it in a public catalogue with search, filters and a details page. |
| S3 | Submit a flight enquiry with contact details, departure city, travel dates and passenger count. |
| S4 | Allow our team to receive, view and track the enquiry and update its status. |
| S5 | Protect private GM&E codes and provide access through an appropriate authorisation process. |

## Gate types

- **F (function):** does it work, end to end, with the server as the judge (not just the page).
- **E (ease):** a non-technical person completes the journey within the click budget, with no instructions beyond the on-screen labels. Clicks are counted from the stated start screen; typing into fields does not count as a click.
- **H (hostile):** an attempt to break it fails safely, with a clear message and no data change.
- **L (leak):** something that must never appear, doesn't appear anywhere.

## S1: create and edit a congress

Start: the team's admin home (WordPress dashboard / console « Tableau de bord »), logged in.

| Gate | Pass when |
|---|---|
| S1-F1 | A new congress with title, start/end dates, city, country, discipline, venue, official website and verification date is saved. |
| S1-F2 | Editing it (e.g. the city) and saving shows the new value in admin AND on the public page. |
| S1-F3 | A contributor can draft and submit it for review but cannot publish; Direction/admin publishes; a draft is not visible publicly (404 / absent from the catalogue). |
| S1-E1 | Create and publish in ≤ 4 clicks from admin home (menu → new → fill → publish). Every field has a visible French label; required fields are marked. |
| S1-E2 | Edit an existing congress in ≤ 3 clicks (menu → congress → save). |
| S1-H1 | End date before start date is rejected with a message; invalid URL rejected; HTML/script in the title is shown as text, never executed. |
| S1-H2 | Saving without a valid nonce / CSRF token changes nothing. |

## S2: public catalogue, search, filters, details page

Start: the catalogue page, logged out.

| Gate | Pass when |
|---|---|
| S2-F1 | All published, upcoming congresses are listed (12 seeded); past and draft ones are not. |
| S2-F2 | Keyword search matches title, city and discipline, accent-insensitive (« vienne » finds « Vienne », « diabetologie » finds « Diabétologie »). |
| S2-F3 | Filters for discipline, country and month work alone and combined; result count is shown; a no-result search shows a helpful message and a reset. |
| S2-F4 | Pagination works and keeps the active filters. |
| S2-F5 | The details page shows dates, city, country, discipline, venue, official website and verification date, and the enquiry form prefilled with this congress. |
| S2-F6 | Works with JavaScript off (server-rendered GET form). |
| S2-E1 | From the catalogue, find « Cardiologie » congresses and open one in ≤ 2 clicks (choose filter → open). |
| S2-E2 | At 390 px: no horizontal scroll, text ≥ 16 px in inputs, tap targets ≥ 44 px. |
| S2-H1 | Script/HTML in the search box is escaped in the page; very long query (5,000 chars) doesn't error. |

## S3: flight enquiry

Start: a congress details page, logged out.

| Gate | Pass when |
|---|---|
| S3-F1 | Fields present: name, email, phone, company (optional), departure city, outbound date, return date, passengers, message, privacy consent; congress prefilled. |
| S3-F2 | A valid submission is stored server-side, linked to the congress, and the visitor sees a reference (DV-2026-NNNN). |
| S3-F3 | The team is notified (demo: a notification log entry; production: email). |
| S3-F4 | Reloading the confirmation page does not create a second enquiry. |
| S3-E1 | Submit in 1 click after filling the form; errors appear next to the field in plain French and keep what was typed. |
| S3-H1 | Rejected with a message: passengers 0, 51, « abc »; return before outbound; past dates; bad email; missing consent. |
| S3-H2 | Honeypot filled or form sent too fast → not stored; rapid repeat submissions from one address are rate-limited. |
| S3-H3 | Script/HTML in any field is stored and shown as text only. |

## S4: team receives, views, tracks, updates status

Start: the team's admin home, logged in as `equipe`.

| Gate | Pass when |
|---|---|
| S4-F1 | The enquiry from S3 appears in « Demandes » with reference, date, congress, contact, departure city, dates, passengers, status « Nouvelle ». |
| S4-F2 | Filter by status and search by name/reference work. |
| S4-F3 | Status changes Nouvelle → Qualifiée → Devis envoyé → Gagnée/Perdue are saved; owner can be assigned; internal notes saved. |
| S4-F4 | History is append-only: each change shows who, when, from → to; it cannot be edited or deleted from the UI. |
| S4-F5 | CSV export contains the enquiries; a name starting with `=`, `+`, `-` or `@` is neutralised. |
| S4-F6 | Enquiries are never public: not in the catalogue, search, feeds, sitemap or any public API. |
| S4-E1 | From admin home, open the newest enquiry and change its status in ≤ 3 clicks; the counts on the home screen update. |
| S4-H1 | A logged-out or contributor user cannot read or change enquiries (direct URL and POST both refused). |

## S5: GM&E codes protected, access by authorisation

Start: logged in as `equipe` (no access), then as `direction`.

| Gate | Pass when |
|---|---|
| S5-F1 | Codes are stored only in their own store, encrypted; the database holds no plaintext code. |
| S5-F2 | `equipe` sees codes masked; asks for access with a reason (reason required). |
| S5-F3 | `direction` sees pending requests and approves (24 h) or refuses; approval can be revoked at once. |
| S5-F4 | After approval, `equipe` can reveal a code; every reveal is recorded (who, congress, when) in a log only Direction can see. After revocation or expiry, reveal is refused. |
| S5-F5 | Public pages say only « Tarif congrès négocié disponible » for approved codes, never the code. |
| S5-E1 | `equipe`: request access in ≤ 2 clicks. `direction`: approve in ≤ 2 clicks from admin home. `equipe` after approval: reveal in ≤ 2 clicks. |
| S5-H1 | Reveal request without permission, without nonce/CSRF, or replayed after revocation → refused, logged, no code returned. |
| S5-L1 | Logged out and as `equipe` without a grant: a crawl of every reachable URL, feed, sitemap, search result and API route (WordPress REST, admin-ajax; custom routes) contains zero seeded dummy codes. |
| S5-L2 | Codes never appear in page HTML for authorised users until they explicitly reveal; never in logs, CSV exports or notification text. |

## Cross-cutting gates (both options)

| Gate | Pass when |
|---|---|
| X1 | Zero console errors and zero failed requests on every tested screen. |
| X2 | Visitor pages load no third-party scripts (WordPress Playground itself excepted, as the host). |
| X3 | All data fictional: titles end « — exemple », emails @example.com, codes `DEMO-GME-…`. No real client, congress or code. |
| X4 | Reset: the sandbox can be restored to the seed state (Playground: reload; custom: Direction reset + nightly cron); re-seeding creates no duplicates. |
| X5 | Hallmark gate: zero FAIL on the hub page and custom demo pages; waivers recorded. |
| X6 | Eye review: an independent reviewer reads the screenshots of every story at 1440 and 390 and returns PASS or a defect list. |

## Loop

1. Builders run their suites until every gate passes locally, then on the deployed URL.
2. Independent `qa` agent re-runs the gates from this file on the deployed URLs and counts clicks for the E gates. It reports a gate-by-gate table with evidence.
3. Adversarial pass (`pipeline-auditor` and a hostile-input worker) tries to break S3–S5 and to find a leaked code.
4. Fix, then repeat 2–3 until there are no FAILs. Results go in `22_Acceptance_Results.md`.
5. Outward text (hub page, email) goes through `/redteam`: four blind lenses must PASS on the exact text.
