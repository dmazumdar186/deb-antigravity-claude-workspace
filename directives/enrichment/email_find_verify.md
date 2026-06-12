# Email Find & Verify

## Goal
Find the business owner's email for each sourced lead using AnymailFinder, then verify deliverability using Million Verifier. Only verified emails pass through to the personalization stage.

## When to Use
After the sourcing stage has produced a lead list. This is always the second stage in the pipeline.

## Inputs
- `--input`: Path to sourced leads JSON (default: `.tmp/serper_leads.json`)
- `--output`: Output path (default: `.tmp/enriched_leads.json` for finder, `.tmp/verified_leads.json` for verifier)
- `--min-confidence`: Minimum AnymailFinder confidence to keep (default: 50)
- `--accept`: Comma-separated Million Verifier results to accept (default: `ok,catch_all`)
- `--mock`: Use mock enrichment data
- Env vars: `ANYMAILFINDER_API_KEY`, `MILLION_VERIFIER_API_KEY`

## Tools/Scripts
- `execution/enrichment/anymailfinder_lookup.py` — email finder
- `execution/enrichment/million_verifier.py` — email verifier
- `execution/modules/pipeline_utils.py` — shared utilities

## Outputs
- `.tmp/enriched_leads.json` — leads with `owner_name`, `owner_email`, `email_confidence`, `email_type`, `enriched_at` added
- `.tmp/verified_leads.json` — same list filtered to only verified emails, with `email_verified`, `email_verification_result`, `email_quality_score`, `verified_at` added

## Steps
1. Read sourced leads from input JSON
2. For each lead with a domain: call AnymailFinder API
3. Store `owner_name`, `owner_email`, `email_confidence`, `email_type`
4. Skip leads where AnymailFinder returns no result or confidence < threshold
5. Save enriched leads to `.tmp/enriched_leads.json`
6. For each enriched lead: call Million Verifier API with `owner_email`
7. Store `email_verified` (bool), `email_verification_result`, `email_quality_score`
8. Filter: keep only leads where result is in the accept list (default: "ok" or "catch_all")
9. Mark passing leads as `status="verified"`, failing as `status="email_invalid"`
10. Save all leads to `.tmp/verified_leads.json` (both valid and invalid, for audit trail)
11. Log: total processed, emails found, verified, rejected, skipped

## Edge Cases
- **AnymailFinder confidence scores**: Configurable threshold (default 50). Below threshold = skip, don't waste Million Verifier credits on low-confidence emails.
- **Generic emails (info@, contact@)**: Mark `email_type` as "generic". Still enrich but flag — generic emails have lower reply rates.
- **Million Verifier "catch_all" domains**: These accept all addresses. Keep them by default (configurable) — they may still be valid.
- **Million Verifier "unknown" result**: Treat as unverifiable. Discard by default (configurable).
- **No domain on lead**: Cannot do email lookup. Mark `status="no_domain"`, skip.
- **Rate limiting**: Both APIs have rate limits. Use `@retry_with_backoff`. Log warnings.
- **Cost awareness**: AnymailFinder charges per lookup. Million Verifier is ~$0.0004/email. Filter aggressively at the AnymailFinder stage to reduce MV costs.

## Exit Criteria

- `.tmp/enriched_leads.json` exists and is a non-empty valid JSON array; each element contains `owner_email`, `email_confidence`, and `email_type` fields.
- `.tmp/verified_leads.json` exists and every element with `status == "verified"` has `email_verified == true` and `email_verification_result` in the accepted list (default: `["ok", "catch_all"]`).
- No element in `.tmp/verified_leads.json` has an empty string for `owner_email`.
- `ANYMAILFINDER_API_KEY` and `MILLION_VERIFIER_API_KEY` are present in `.env` (confirmed by running with `--mock` flag exiting `0` and no `missing key` error in real mode).
- Log output includes the summary line with `total processed`, `emails found`, `verified`, `rejected`, and `skipped` counts — none of which are `None` or negative.

## Changelog
| Date | Change |
|------|--------|
| 2026-04-29 | Created — initial directive for Accessory Masters pipeline |
