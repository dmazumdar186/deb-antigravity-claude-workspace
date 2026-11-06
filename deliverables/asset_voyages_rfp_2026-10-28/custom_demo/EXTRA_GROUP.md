# Extra: « Le lien de groupe » (Option B)

Built from the winning idea in `../23_Overdeliver_Idea_Research.md` (§4 debate, §6 demo spec). Not part of the five stories and not in the quotation. Fictional data only.

## What it does

When an enquiry has 2 or more passengers, the team creates one link for it. The team sends that link to the travellers. Each traveller opens it on a phone and enters their own travel details: name as on the ID document, e-mail, departure city, outbound and return dates, plus a consent box. The enquiry gets a « Groupe » tab with a live list of who has answered (« 3 répondus / 6 attendus »), the mix of departure cities and an « Exporter pour cotation (CSV) » button. Nobody re-keys names from e-mails, and nobody has to chase replies to a spreadsheet.

## User journey (4 steps)

1. **Create (Équipe or Direction).** Console › Demandes › the enquiry › « Lien de groupe » card › « Créer le lien ». That is 2 clicks from the list. The link `/g/<token>` appears with « Copier le lien » and its expiry date (30 days).
2. **Send.** The advisor pastes the link into the reply to the client. No e-mail is sent by the demo.
3. **Answer (each traveller, phone).** The page shows the congress name and dates only. The traveller fills in 5 fields, ticks consent and taps « Envoyer mes informations » (1 click). The confirmation shows their own entry only. Sending again with the same e-mail updates that entry and never creates a duplicate.
4. **Follow and export (team).** Open the enquiry, then the « Groupe » tab (2 clicks from the list). The list refreshes itself every 15 s while the tab is open. A hint appears when the count nears the internal setting « Seuil groupe (à confirmer) » (default 10; it shows from 2 answers, or 20 %, below the setting). The team can export the CSV, revoke the link or create a new one.

The seed has the journey already under way: DV-2026-0001 (6 passengers) has an active link and 3 fictional delegates (`@example.com`) have answered.

## How it is built

- **Tables** (schema v8): `group_links` holds one row per enquiry and sandbox (`origin_sbx`, `token_mac`, `tok_salt`, `expires_at`, `revoked_at`) plus an index on `token_mac`. `group_delegates` is keyed on `(sbx, enquiry_id, email_norm)`, so a second answer with the same e-mail is an upsert. `settings` holds the threshold. All three follow the row-level copy-on-write overlay, and the reset and nightly purge clear them like every other sandbox table.
- **Token:** a 128-bit random salt is stored. The URL token is `HMAC(group-v1, 'tok|'+salt)` (43 characters) and the lookup column is `HMAC(group-v1, 'id|'+token)`. `group-v1` is a new HKDF label from `GME_KEY`. A database dump without the Worker secret gives no working URL, and the stored MAC is not itself a valid token (G-H2). Keeping the salt is a deliberate choice: it lets the console show and copy the link again later. If links could only ever be shown once, we would store the MAC alone.
- **Sandboxes:** the token resolves to a sandbox on the server. A link created in sandbox X sends every traveller's answer into X, whichever browser sends it. Those writes count against X's write budget (`claim()`: global wall, then X's per-sandbox throttle). The traveller's browser gets no sandbox of its own (checked in G-I1). The seed link works like the rest of the seed: an answer from a browser lands in that browser's own sandbox.
- **Public route guards:** signed form token bound to the link (form-v1, purpose `group:<mac>`), same-origin check, 3 s minimum fill time, honeypot, 32 KB body cap, length limits, dates neither in the past nor more than 30 days from the congress, return on or after outbound, consent required. Limits: 20 accepted answers per IP every 10 min, stored in D1. Unknown tokens are cut off after 60 per IP every 10 min; that counter lives in memory and costs no write. At most max(10, 2 × passengers) distinct people per enquiry, capped at 100. The test key skips the per-IP limits only, as it does elsewhere.
- **Cost:** one answer writes 1 row, plus 1 for the IP counter for a real visitor (G-X1 meters this at 2 rows or fewer).
- **Files:** `src/group.js` (public side and pure helpers), `src/console.js` (« Lien de groupe » card, « Groupe » tab, CSV, actions), `src/data.js` (schema and seed), `public/assets/app.js` (copy button, live refresh, return date never before outbound), `app.css` (four small rules).

## Demo vs production

| Working in the demo | Needs work for production |
|---|---|
| Link creation, copy, 30-day expiry, revoke, a new link replaces the old one | Expiry chosen per file (e.g. congress start − 45 days), several links per enquiry if wanted |
| Public form, validation, upsert by e-mail, own-entry confirmation (signed, valid 1 h) | E-mail check of the address (a confirmation link) before an answer can replace an existing one |
| Live list, counter, departure mix, CSV with formula escaping | Per-delegate status (reçu / à préciser / confirmé), reminders sent by e-mail, notification log line |
| Internal threshold setting with hint | Threshold agreed with ASSET per carrier and per file; no carrier rule is shown or cited |
| Per-IP and per-sandbox limits, crawl cut-off | Cloudflare rate-limiting rules or Turnstile on `/g/*`, monitoring of refusals |
| Privacy note on the page (example address) | Wording validated by ASSET's DPO, record in the processing register, retention and erasure procedure |

## Privacy notes

- Data minimisation is built in: there is no passport number, date of birth, diet, health or free-text field. The form says so.
- The consent is single-purpose: organising this group's travel. Nothing is published or resold. The page names who is responsible and gives a contact address for access and erasure (an example address).
- A traveller never sees anyone else. The form page carries no enquiry data: no contact, company, reference, passenger count, threshold, fare or code. The confirmation reads that traveller's own row through a signed reference. G-L1 and G-L2 check this, including the response headers and a crawl of 50 random tokens and probes.
- Pages are `no-store` and `noindex`. The CSP and the other security headers are the same as everywhere else. The URL token never reaches a third party (`Referrer-Policy: same-origin`, no third-party requests).
- In the demo everything is fictional and wiped with the sandbox (nightly, or by « Réinitialiser la démo »).

## Honest limits

- **Anyone holding the link can overwrite an answer by typing that person's e-mail.** They never see the stored entry: the confirmation only echoes what they typed (G-L1). Production would send a confirmation link to the e-mail before replacing an existing row.
- **The link is a bearer secret.** Anyone it is forwarded to can answer. Revoking it stops that at once.
- **A confirmation URL shows that delegate's own entry to whoever has it, for one hour.**
- **Sandbox semantics:** in a demo browser, answers sent to the seed link are visible only in that same browser. To show the full journey on two devices, create a new link from your console and open it on the phone.
- **The miss counter is per Worker isolate** (in memory). It slows a crawl down but is not a hard global limit; the tokens are 128-bit, so guessing is not a practical risk anyway.
- **Schema v8** rebuilds the database on first start after deploy. Every existing sandbox is reset, as with earlier schema changes.

## Tests

- `tests/extra_group.spec.mjs` covers 14 gates: G-F1 to G-F5, G-E1 to G-E3 (inside G-F2), G-H1 to G-H4, G-L1, G-L2, G-I1 (inside G-F2), and G-X1 to G-X3 (write cost, 390 px, Hallmark sloplint). G-H1 and G-H4 run locally only, because they need a direct write to local D1 and a forged per-IP header.
- `../qa/B/unit_group.test.mjs` has 12 unit tests (token, MAC, expiry, validation boundaries, threshold, hint, plurals, cap, CSV escaping, token format). Run it with `node --test qa/B/unit_group.test.mjs`.
- Sloplint on the new pages (form, confirmation, « Lien introuvable », the « Groupe » tab, enquiry with and without a link): **0 FAIL, 0 WARN**. The only NOTEs are the « — exemple » dash in the seeded titles, which is verbatim and required by gate X3, and the length of two short paragraphs.
- Changed existing tests: FIX4-5 now lists `group-v1` among the allowed MAC purposes. `qa/B/unit_B.test.mjs` UNIT-B-014 was stale since FIX4-5 (it called `hmac` without a purpose) and now uses the current form-token MAC.
