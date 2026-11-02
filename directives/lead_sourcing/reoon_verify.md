# Reoon Email Verification SOP

## Goal
Independently verify every email in a leads CSV before it goes to Instantly, so bounce rate stays under 1% and no spam traps reach a sending domain. Vendor "verified" flags are not enough: on 2026-11-02, Reoon rejected 67 of 436 LeadOcean-"verified" emails (26 unknown, 5 spamtrap, 2 invalid, 1 role, 33 catch-all).

## Tools/Scripts
`execution/lead_sourcing/reoon_verify.py`

```bash
python3 execution/lead_sourcing/reoon_verify.py --balance
python3 execution/lead_sourcing/reoon_verify.py --src leads.csv --out leads_verified.csv [--workers 8]
```

## Inputs
- `--src` CSV with an `email` column (any other columns pass through untouched).
- Env `REOON_API_KEY` or `REOON_TOKEN` (falls back to `.env`).

## Outputs
- `--out` CSV = input + `reoon_status`, `reoon_score`, `reoon_catch_all`, `reoon_safe`, `send_bucket`.
- `send_bucket`: `main` (status safe, score >= 90, not role) | `catchall` (separate low-volume campaign, <= 10% of daily volume, stop above 2% bounce) | `drop`.
- Cache `.tmp/reoon/cache.jsonl`: one row per email; re-runs only verify new emails. Errors are not cached, so a re-run retries them.

## Steps
1. Check credits: `--balance` (one instant credit per new email).
2. Run `--src <leads.csv> --out <leads_verified.csv>`.
3. Load only `send_bucket=main` rows into the main Instantly campaigns.
4. Load `send_bucket=catchall` rows into a separate low-volume campaign on 2 dedicated inboxes.
5. Delete `drop` rows; never send to them.

## API notes (learned 2026-11-02)
- Single verify: `GET https://emailverifier.reoon.com/api/v1/verify?email=&key=&mode=power` (SMTP-level, ~2-10 s each). 8 workers handled 750 emails in a few minutes with no 429s.
- Balance: `GET /api/v1/check-account-balance/?key=` (free). Power mode spends instant credits (one per email).
- Statuses seen: safe, catch_all, unknown, invalid, spamtrap, role_account. `unknown` can be retried after 72 h; the script treats it as drop.

## Consumers
- `execution/lead_sourcing/leadocean_leads.py` reads the cache: a LeadOcean `untested` / `catch_all` email that Reoon rated safe (score >= 90) is rescued at hygiene instead of rejected.

## Edge cases
- Verify within 7 days of sending; statuses drift.
- Never send to `spamtrap`, even once.
