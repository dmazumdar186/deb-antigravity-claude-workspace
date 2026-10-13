# Email MX pre-verification (keyless)

**Script:** `execution/enrichment/email_mx_verify.py`

## Goal
Cheap first-pass deliverability check on a lead list when no paid verifier key is in the environment (cloud sessions have no `MILLION_VERIFIER_API_KEY`). Drops syntactically broken and dead-domain addresses before a campaign; flags generic role mailboxes.

## Inputs
- `--input` CSV or JSON with an `Email`/`email` column (`--column` to override)
- `--output` CSV or JSON path

## How it works
1. Syntax regex.
2. Disposable-domain blocklist.
3. MX lookup through DNS-over-HTTPS (`dns.google/resolve`); falls back to an A record (implicit MX). Local resolvers in cloud sessions return no MX answers and port 25 is blocked, which is why neither plain DNS nor SMTP probing is used.
4. Role-address flag (`contact@`, `info@`, `bonjour@`...). For sole-trader instructors these usually reach the owner, so keep them, just tag them.

## Outputs
Rows + `email_status` ∈ {`mx_ok`, `role`, `no_mx`, `bad_syntax`, `disposable`} + `mx_host`. Summary counts on stdout.

## Limits
`mx_ok` means the domain accepts mail, not that the mailbox exists. Run `million_verifier.py` locally (key in `.env`) before a large send; expect a few percent extra bounces otherwise.

## Run log
- 2026-10-13 yoga FR list (229 emails): 114 mx_ok, 114 role, 1 no_mx. ~20 s with 12 threads.
