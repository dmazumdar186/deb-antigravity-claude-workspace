# Panel lens 6: Saraev (automation maturity and boundaries)

**Verdict: FIX BEFORE LAUNCH.** Capture works and is hardened. Nothing tells anyone that a capture happened. Rung 1: KV store, pull-only.

## Findings
1. **Operator gap.** `register.ts:128` writes `reg:<ts>-<rand>` and returns. Nothing notifies her: no email, webhook or digest. The only read path is `export.ts:75-98`, a Basic-auth CSV that returns 401 until `EXPORT_USER`/`EXPORT_PASS` are set (`export.ts:76`, `to_wire.md:13`). Today a registration is invisible to Jeevana.
2. **Customer gap and a broken promise.** `i18n.js:70/135` tells the visitor "Jeevana will reply by email". She never hears about the registration, so the reply cannot happen. No confirmation email is sent either. This step is felt by the customer and has no human in it.
3. **Manual output not proven.** The directive (`jeevana_site.md:27-28,41`) and HANDOFF.md:4 cover deploying and setting secrets. They never cover how Jeevana handles a registration from arrival to reply. Prove that by hand first, then automate.
4. **Bottleneck.** Her attention, not throughput. Pull CSV is the wrong shape.
5. **Smallest next rung, with no third party.** Bind a Cloudflare Email Routing `send_email` binding (destination verified as jeevanagogula.gj22@gmail.com). Then `register.ts` sends one plain notice per registration after the KV put, best-effort. A failed send must not fail the visitor's request. **With a third party:** Brevo transactional, which is also the double opt-in path `to_wire.md:15` already calls for. A daily digest (Cron Trigger over `reg:` keys) is the fallback if per-registration mail is too noisy. Don't send a visitor confirmation email until the notice works.
6. **No error channel.** The catch at `register.ts:130` and `subscribe.ts:158` returns 500 with nothing logged. `_lib.ts:38-42` also runs outside the try block: if the KV read/put throws, the function throws unhandled. Add `console.error`, which Workers Logs captures. A visitor who sees a 429 or 500 should be shown the WhatsApp number as a fallback (needs checking in `main.js`).
7. **Proportionality.** The honeypot (`register.ts:111`) plus 5 requests per 10 minutes per hashed IP (`_lib.ts:9-10`) is fine for this traffic. The read-modify-write in KV is not atomic, which is harmless at this scale. Shared NAT (studio wifi) could rate-limit a group signing up together. Acceptable.
8. **No change log.** Nothing records what changed in an operations behaviour. Add one line per change to the directive.

## Honest gaps
- I didn't check whether the Email Routing destination is verified, or whether the Pages project allows `send_email`.
- I didn't trace how `main.js` shows a 429 or 500 to the visitor.
- I didn't test any live endpoint.
