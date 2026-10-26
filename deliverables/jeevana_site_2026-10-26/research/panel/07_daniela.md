# Panel lens 7: Daniela Amodei (operations, people & trust)

**Verdict: FIX BEFORE SHARING.** The tone is respectful: the pop-up shows once, after 35 s, never on the cover, and is labelled "close this and nothing happens". FR matches EN. What is missing is ownership: no privacy notice, no deletion or unsubscribe mechanism, and no recorded consent from Jeevana for publishing her personal phone number.

## Findings
1. **Jeevana's phone is published five times, all in plain text that scrapers can read.** It appears in JSON-LD `telephone` (index.html:33), in the tel and WhatsApp rows (207-208), in the footer (229) and in the mobile bar (237). The only source is "operator, 2026-10-26" (research/to_wire.md:18). Nothing records that Jeevana agreed to this. The quieter option: keep the WhatsApp link only, take the number out of the JSON-LD and the footer, and get her written OK.
2. **Her personal Gmail is in JSON-LD (33) and appears four more times as mailto links (196, 209, 228).** Same scraper exposure. Fix: an alias or the form.
3. **There is no privacy notice anywhere.** Visitors are not told what is stored (name, email, phone, message, language, source URL: register.ts:28, subscribe.ts:20), where it is stored (Cloudflare KV), or for how long. Nothing sets an expiry on these records (only the rate-limit keys have a TTL, _lib.ts:42). GDPR requires a controller name and retention period.
4. **"I can unsubscribe at any time" (i18n.js:77/142) has no mechanism behind it.** There is no unsubscribe endpoint and no delete endpoint. Deletion "by email" (reg.consent, i18n.js:68/133) relies on Jeevana deleting KV keys by hand, and nobody has shown her how.
5. **Nobody owns new registrations.** register.ts only writes to KV, with no notification to anyone. Jeevana has to pull /api/export (export.ts) with credentials that may not be set (every request returns 401 until EXPORT_USER/EXPORT_PASS exist). Visitors who register will hear nothing back.
6. **The pop-up form still accepts a phone number** (subscribe.ts:2, HANDOFF.md:3). That collects more than the newsletter needs. Drop it.
7. **The footer credit is proportionate** (one line, small, after ©). But `debanjan@prodcraft.fyi` is a plain mailto (index.html:232), so scrapers can harvest it, and the prodcraft.fyi link has no `rel`. Drop the email, keep the link, and add `rel="noopener"` for consistency. Findings 1-5 also reflect on his name.
8. **The site has no owner named.** HANDOFF.md does not say who renews the domain, rotates the export credentials or answers data requests.

## Honest gaps
- I could not check whether Jeevana approved her photos or her number. Only the operator can confirm that.
- I did not test the live deployment or the CSP headers.
- I did not check whether the "subscribe" sentence counts as valid consent under CNIL rules.
