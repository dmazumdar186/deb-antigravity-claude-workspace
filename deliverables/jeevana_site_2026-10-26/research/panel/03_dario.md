# Panel lens 3: Dario (safety, honesty, legal exposure)

**Verdict: SHIP AFTER FIXES.** The one real exposure is RGPD/LCEN plumbing.

## Findings
1. **Google Fonts loaded from Google's servers** (index.html:28-30, _headers CSP `fonts.googleapis.com`). This sends every visitor's IP to Google before any consent. Unlawful per LG München (2022). Self-host them; the CSP (otherwise strong: no unsafe-inline, HSTS, DENY) then shrinks to 'self'.
2. **No privacy notice and no mentions légales.** No link exists (index.html:232 footer). A French site must name its publisher (LCEN art. 6) and, under RGPD art. 13, state the controller, purpose, legal basis (consent), retention, recipients (Cloudflare as processor, US company, SCCs/DPF) and the rights to access, erase and complain to CNIL. Consent lines (i18n.js:68,77,133,142) are good but no substitute.
3. **Withdrawal is promised but not built.** "Unsubscribe at any time" (i18n.js:77) has no endpoint. subscribe.ts only writes. Add an unsubscribe link or mailto and a written deletion procedure.
4. **Data location.** KV (wrangler.toml:6) is global and replicated, with no EU pinning. Records keep no expiry (register.ts, subscribe.ts). Set a retention period, e.g. registrations 24 months.
5. **Unverified claims.** about.bio "group classes, private sessions and workshops, in a studio and outdoors" (i18n.js:51) and "Studio address shared on registration" (i18n.js:55) are not in the verified facts (brief.md:42 says the studio is not supplied). Soften these or add them to to_wire.md.
6. **Health copy is clean.** No cure or therapy claims.
7. **Cultural line is respected.** Sūtra 1.2 and 2.46, "8 limbs" and "4 chapters" are accurate. The 12 Sūrya mantras use the standard names, in order with standard glosses. They are framed as practice ("What the tradition says"). The site has no deity imagery and no proselytising.
8. **Photos.** These are the teacher's own photos and the daytime Eiffel Tower is public domain. Any future *night* shot shows the copyrighted illumination (SETE), so commercial use needs a licence.
9. **localStorage** (main.js:10, 22, 28) holds only the language and the dialog-dismissal flag. Strictly necessary under CNIL guidelines: no banner needed. The honeypot and the hashed-IP rate limit (_lib.ts:29-38) are also CNIL-safe.
10. **Export** (export.ts:21-26). It fails closed when the credentials are unset and compares in constant time, except that a length mismatch returns early. It has no rate limit, so Basic auth can be brute-forced. Add `rateLimited(env, request,'exp')` and use a long password.
11. **ProdCraft footer** (index.html:232) publishes debanjan@prodcraft.fyi: spam exposure only, honest and mandated.

## Honest gaps
- I did not verify the Cloudflare DPA, the region options, or whether Jeevana is the RGPD controller (she must be, not ProdCraft).
- Gloss lineages vary (Satyananda versus others); I checked no single canonical source.
- I did not inspect the PNGs or photo EXIF/location data, or the 404 page.
