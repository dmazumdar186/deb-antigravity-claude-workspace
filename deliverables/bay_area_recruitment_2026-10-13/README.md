# Bay Area recruitment list, finalized 2026-10-13

Source export: 1,900 rows. 5 duplicate emails removed. Every row carries `email_status` (MX check: `mx_ok` keep,
`no_mx` drop), `Short Company Name` (legal suffixes stripped), `Personalized Name` (one friendly brand word, every
word taken from the original name), and the ICP flag columns `icp_category`, `icp_on_target`, `icp_confidence`, `icp_reason`.

## Launch files (person in the city, company HQ in the same metro, classified as recruitment / staffing / HR consulting)
- `san_francisco_LAUNCH.csv`
- `seattle_LAUNCH.csv`
- `san_diego_LAUNCH.csv`

## hq_outside_metro/
On-target companies whose contact sits in the city but whose HQ is elsewhere (New York, LA, London, Bengaluru...).
Kept apart so no launch file mixes markets. Use at your discretion.

## flagged_off_target/
Everything the classifier judged not to be a recruitment / staffing / HR-consulting services firm: HR software
(`hr_tech`), IT / management / marketing consultancies (`other_consulting`), VCs, healthcare, coaches, research
(`other`). Rows are flagged, not deleted; `icp_confidence` is the probability the company is on-target.
Rows with confidence 0.40 to 0.50 are borderline (talent marketplaces, hiring platforms).

Verification is domain-level only (no mailbox verifier key in the cloud session). Run `million_verifier.py`
locally before a large send.
