# FACTS — every on-screen figure and claim, traced (internal; never shown)

Full fact sheet with blocklist: `.tmp/gtm_pipeline/system_facts.md` (not committed; blocklist reproduced in QA step).

| On-screen claim | Source |
|---|---|
| 12 emails a day, by hand | directives/gtm_client_workflows/accessory_masters_prd.md:15 ("maybe a dozen emails a day by hand"); operator 2026-11-10 ("10 to 12") |
| Then 800 a day · 32 inboxes | accessory_masters_prd.md:17, :25; directives/infrastructure/domain_inbox_management.md:46 ("32 inboxes x 25 = 800/day") |
| 32 at launch → 64 → later 96 inboxes | 32: accessory_masters_prd.md:17; 64 / later 96: operator statement, session 2026-11-10 (no repo record; flagged) |
| +$128K in revenue in 3 months | operator statement, session 2026-11-10 (no repo record; flagged). Not the modeled "$1M+ pipeline" in metrics_canonical.md:15 |
| Find the right people | accessory_masters_gtm.md:36, :44-45 (Maps search + contact enrichment) |
| Verify every address | accessory_masters_prd.md:234; HANDOFF.md:47-48 (AnymailFinder → Million Verifier; only verified pass) |
| Send from many inboxes, every day | accessory_masters_gtm.md:4 (Instantly upload); daily pipeline run |
| Every interested lead is logged in the CRM | api-proxy/src/index.js:517-519 (hot + positive → GoHighLevel contact + opportunity); operator 2026-11-10 |
| AI reads every reply: hot · interested · neutral · not interested | index.js:35-54 (hot_positive, positive, neutral, negative) |
| Hot lead → a person takes over, and the client's phone pings | index.js:522, :525-541, :729-733 (hot → human takeover; Telegram alert) |
| Interested → a reply within minutes, and a call on the calendar | index.js:89-96, :525-541, :729-738 (positive → auto-reply with call ask, 2–10 min queued delay, sent on the 30-min cron); booking: operator 2026-11-10 (Calendly booking page + GHL calendar; config/accessory_masters.json:96, website/signup.html:164-167) |
| lemo-opuscar (MIT) · CC0 samples | lemo-opuscar LICENSE; core/audio/sampler.py (vsco2ce, vcsl CC0) |
