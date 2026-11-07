# GreenJobs platform: red-team checklist

**Frozen 2026-11-07. Future audits run against this list only, for at most 2 rounds; adding an item needs the operator's word.**

Each item is one testable check. "Platform tests" means `tests/greenjobs_redesign/platform/*` (Worker unit tests
and `features/*.feature`, run by `run_tests.sh` tier 3). "Import tests" means
`tests/greenjobs_redesign/test_strategies_import.py` (tier 2).

| # | Check | Pass criterion | Covered by |
|---|---|---|---|
| 1 | Admin routes with no Access JWT, a forged signature, `alg: none`, wrong `aud`, expired token, or an email not in `STAFF_EMAILS` | Every case returns 401 or 403; no D1 write | Platform tests |
| 2 | CSRF on admin writes and apply | A write from an origin outside `ALLOWED_ORIGINS` / the board host is refused | Platform tests |
| 3 | IDOR on job ids: other-site id, draft or closed id on public routes; apply to a closed job | 404 on read; apply refused server-side even when the static page still shows the job | Platform tests |
| 4 | Rate limits on apply and admin | Request over `RATE_APPLY_PER_10MIN` / `RATE_ADMIN_PER_MIN` returns 429; works with and without the optional `RATE` / `APPLY_LIMITER` bindings | Platform tests |
| 5 | Honeypot field filled, or form timestamp too fast or too old | Rejected with no row stored and no mail | Platform tests |
| 6 | CV upload: wrong extension, wrong MIME, correct MIME with wrong magic bytes, over `MAX_CV_BYTES`, zero bytes | All rejected before any R2 write | Platform tests |
| 7 | R2 key and path traversal: filename `../x`, `%2e%2e%2f`, double-encoded, null byte, absolute path | Stored key is Worker-generated; user filename never forms any part of the key | Platform tests |
| 8 | SQL injection in every field and query param | Only prepared statements with bound params (`d1/upserts.sql` shapes); no string-built SQL anywhere (grep and test) | Platform tests; `SAST_REPORT.md` |
| 9 | Stored XSS in job title, description, employer name (console and import) | Rendered escaped on the static page and in `/admin/`; `<script>` and `on*=` never execute | Platform tests; `build_site.py` tests |
| 10 | Header injection: CR/LF in name, email or job title placed into mail headers | CR/LF stripped or rejected; one recipient only | Platform tests |
| 11 | Formula injection: cells starting `=`, `+`, `-`, `@`, tab, CR in import CSVs and in any CSV the validator writes (`--csv` report) | Stored as text; written CSV cells are neutralised | Import tests |
| 12 | Prompt-injection text in imported or posted job text | Flagged in the validator report; never executed (no LLM in the request path) | Import tests |
| 13 | Dry-run default and spend | Fresh deploy with no vars has `DRY_RUN="1"`; live only with `DRY_RUN="0"` and `LIVE_CONFIRM="send-applications"`; test run sends nothing, spend 0.00 | Platform tests |
| 14 | Idempotency on the API: replayed `Idempotency-Key`, double submit of the same application, closing a closed job | One row, one mail, one `audit_log` row | Platform tests |
| 15 | Idempotency on import: same CSV twice; console-edited or closed job in a later import | Second run skipped via `import_batches`; console rows not overwritten; closed jobs stay closed | Import tests; tier 1 of `run_tests.sh` |
| 16 | No PII in logs, reports or git | Logs and validator reports hold counts, ids and field names only; `audit_log.detail_json` has no values | Platform tests; import tests |
| 17 | CSVs never in the repo or `.tmp/`; `--emit-sql` path inside the repo | No CSV under the migration deliverable; emitter refuses a path inside the repo | `run_tests.sh` tier 4; import tests |
| 18 | Secrets only as Worker secrets | `RESEND_API_KEY`, `BUILD_TOKEN`, `DEPLOY_HOOK_URL` absent from wrangler config, code, logs and git | `SAST_REPORT.md`; secret scan |
| 19 | Cloud without `.env` | `run_tests.sh` passes with no `.env` and no network | `run_tests.sh` |
| 20 | Empty and None inputs: empty body, missing fields, empty CSV, header-only CSV, empty job list | Clear 4xx or zero-row report; no crash, no partial write | Platform tests; import tests |
| 21 | Resend timeout, 4xx and 5xx | `delivery_status='failed'`, ops alert raised, application and CV kept | Platform tests |
| 22 | Pagination of `GET /api/jobs` and `GET /api/export/jobs` | Page size bounded; walking every page returns every live job exactly once | Platform tests |
| 23 | DNS rollback rehearsed | Rehearsal on staging done before T-2 with times recorded; saved rollback values checked by two people | `CUTOVER_RUNBOOK.md` §4 |
| 24 | MX untouched by the web switch | `dig +short MX` equals the T-7 inventory before, during and after the switch; test mail both ways | `CUTOVER_RUNBOOK.md` §2, §3 |
| 25 | Windows vs Linux CSVs: CRLF line ends, cp1252 encoding, UTF-8 BOM | Parsed the same as LF UTF-8; non-UTF-8 detected and decoded or rejected with evidence | Import tests |
