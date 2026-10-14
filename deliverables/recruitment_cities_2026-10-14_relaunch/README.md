# Recruitment Cities campaign — cleaned relaunch list (2026-10-14)

Input: `Recruitment_Agencies-_City-_30_Sep_26.csv` (2501 rows) + Instantly bounce report (20 rows: 18 hard, 2 soft).
Output: `Recruitment_Cities_30_Sep_26_CLEAN_relaunch.csv` (977 rows, same columns, ready to upload as-is).

## Why the campaign bounced
The verifier columns already in the file predicted it: 12 of 18 hard bounces were `catch_all` rows, 5 were rows the verifier had already marked `invalid` (score 3), 1 was `accio.ae` whose domain no longer exists. Catch-all and invalid rows were uploaded anyway.

## Filters applied (in order)
| Rule | Rows dropped |
|---|---|
| Blank email | 272 |
| Hard-bounced in Instantly | 18 |
| Soft-bounced in Instantly | 2 |
| Same domain as a bounce (bad domain / policy block) | 1 |
| Verifier status catch_all | 721 |
| Verifier status unknown / unverified | 229 |
| Verifier status invalid | 109 |
| Disabled / role / disposable / spamtrap | 14 |
| Safe but flagged catch-all / role / score < 88 | 134 |
| Duplicate email | 24 |
| Live MX lookup failed (DNS-over-HTTPS, all 916 domains) | 0 |

Kept rows: status `safe`, is_safe_to_send `true`, score 93-98, not catch-all, MX verified live on 2026-10-14.

## Residual risk
No SMTP mailbox probe was possible (port 25 blocked in cloud; no Million Verifier key in env). One original bounce (`kyle@openreq.co`) was verifier-safe and still bounced, so expect a small residual rate (~0.5-1%), well under Instantly's 3% pause threshold. In Instantly, keep "Verify leads on upload" on and disable "Send to catch-all" for this campaign.

## City split (one file per campaign)

| City | Country | Leads | File |
|---|---|---|---|
| Dubai | United Arab Emirates | 287 | `by_city/dubai_LAUNCH.csv` |
| Singapore | Singapore | 248 | `by_city/singapore_LAUNCH.csv` |
| Seattle | United States | 147 | `by_city/seattle_LAUNCH.csv` |
| San Diego | United States | 125 | `by_city/san_diego_LAUNCH.csv` |
| Hong Kong | Hong Kong | 120 | `by_city/hong_kong_LAUNCH.csv` |
| Kuala Lumpur | Malaysia | 28 | `by_city/kuala_lumpur_LAUNCH.csv` |
| Shanghai | China | 22 | `by_city/shanghai_LAUNCH.csv` |

Total 977 = master file row count. Each file re-read after writing: unique emails, no overlap between files, zero overlap with the bounce list, every row verifier-safe and not catch-all.
