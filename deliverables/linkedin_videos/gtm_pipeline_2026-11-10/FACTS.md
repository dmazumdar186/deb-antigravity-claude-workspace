# FACTS — every on-screen figure and claim, traced (internal; never shown)

Full fact sheet with blocklist: `.tmp/gtm_pipeline/system_facts.md` (not committed; blocklist reproduced in QA step).

| On-screen claim | Source |
|---|---|
| 12 emails a day, by hand | directives/gtm_client_workflows/accessory_masters_prd.md:15 ("maybe a dozen emails a day by hand"); operator 2026-11-10 ("10 to 12") |
| Then 800 a day · 32 inboxes | accessory_masters_prd.md:17, :25; directives/infrastructure/domain_inbox_management.md:46 ("32 inboxes x 25 = 800/day") |
| 64, then 96 inboxes | operator statement, session 2026-11-10 (no repo record; flagged) |
| +$128K in revenue in 3 months | operator statement, session 2026-11-10 (no repo record; flagged). Not the modeled "$1M+ pipeline" in metrics_canonical.md:15 |
| Find the right people | accessory_masters_gtm.md:36, :44-45 (Maps search + contact enrichment) |
| Verify every address | accessory_masters_prd.md:234; HANDOFF.md:47-48 (AnymailFinder → Million Verifier; only verified pass) |
| Send from many inboxes, every day | accessory_masters_gtm.md:4 (Instantly upload); daily pipeline run |
| Log every lead in the CRM | api-proxy/src/index.js:517-519 (GoHighLevel contact + opportunity) |
| AI reads every reply: hot · interested · neutral · not now | index.js:35-54 (hot_positive, positive, neutral, negative) |
| Hot lead → a person takes over, and the client's phone pings | index.js:522, :525-541, :729-733 (hot → human takeover; Telegram alert) |
| Interested → a reply asking for a call, within minutes | index.js:89-96, :525-541 (positive → auto-reply with call ask, 2–7 min delay) |
| lemo-opuscar (MIT) · CC0 samples | lemo-opuscar LICENSE; core/audio/sampler.py (vsco2ce, vcsl CC0) |
