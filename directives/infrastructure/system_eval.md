# System Evaluation (10-day self-audit of built systems)

## Goal
Every 10 days, score each registered system on six measurable lenses plus its behavioural targets, compare with the previous run, flag degradation, and hand the operator a report readable in under 2 minutes (audience: CTO/CIO/CDO/chief system designer). The script measures and writes; it never sends mail and never changes a system.

## Inputs
- `config/system_eval.json` — the registry (systems, code globs, directive, tests, ops source, secrets allow-list, behavioural targets).
- `--facts facts.json` — `{system: {fact: value}}` for things the script cannot measure (scheduled-task state, Drive snapshot dates, per-day counts). Missing facts score as "unknown", never as failures. Optional `fixes: [{situation, task, action, result}]` per system adds a STAR block.
- env `GITHUB_TOKEN` (or `GH_TOKEN`) — GitHub REST reads of workflow runs; `GITHUB_REPOSITORY` optional (else from `git remote`). `--no-network` skips it.
- CLI: `run [--systems a,b] [--facts f] [--no-network] [--timeout 600] [--date YYYY-MM-DD] [--email-body]`, `report [--date] [--email-body]`, `compare [--systems]`.
- Tools used if present (fail soft to n/a): `ruff`, `pytest`, `pip-audit`, `git`.

## Tools / Scripts
- `execution/infrastructure/system_eval.py`

## Outputs
- `docs/reference/system_eval/<system>/latest.json` (baseline: scores, evidence, raw metrics, targets), `previous.json`, `history/<date>.json`.
- `docs/reference/system_eval/<system>/REPORT_<date>.md` and combined `docs/reference/system_eval/REPORT_<date>.md` (≤ 350 words for two systems).
- `--email-body` prints the combined report as plain text (headings unmarked, table separator rows dropped) for the caller to email.
- Exit code 0 always unless the script itself crashes. Degradation is a word in the report, not an exit code.

## Steps
1. Build the facts file (`.tmp/system_eval_facts.json`) for systems whose ops are not observable from code: for `linkedin_connect`, read the three slot tasks + the 20:00 report task and the newest Drive `ledger_*.csv` date; omit what you cannot verify.
2. `python3 execution/infrastructure/system_eval.py run --facts .tmp/system_eval_facts.json` (add `--no-network` when `GITHUB_TOKEN` is absent).
3. Read the combined `REPORT_<date>.md`; for every DEGRADED line decide: real regression (open a fix) or measurement drift (adjust the registry and say so in the commit).
4. `python3 execution/infrastructure/system_eval.py report --email-body` → email body to the operator (cadence section below).
5. Commit and push `docs/reference/system_eval/**` (and any registry change) to `main`.

## Report shape (contract — do not add prose)
Title `System evaluation — <date>`; one line per system `<system>: <overall x/5> — no degradation | DEGRADED (names)`; a 6-row table per system (lens, score, prev, delta, one-phrase evidence); `Behavioural targets` bullets (met/unmet/unknown); a STAR block (Situation/Task/Action/Result, ≤ 25 words each) only when a lens moved or a fix was supplied; `Next check: <date+10>`.

## Scoring formulas (each lens 0–5; overall = mean of scored lenses, n/a lenses excluded)
1. **Architecture** — +1 directive exists; +1 directive's last commit is within 30 days of the newest code commit; +2 × (env keys read by the code that appear in the directive's `## Inputs`, `/`-shorthand such as `X_ID/SECRET` expanded) / total keys; +1 no `json.dumps(` or ```` ```ledger ```` inside functions named `*email*|*report*|*digest*` in `deliverable_files`.
2. **Data** — checks = `schema_grep` (constants present) + each `data.commands` entry passes (rc 0). Score = 5 × passed / known checks.
3. **Code health** — start at 5; ruff (`E9,F63,F7,F82,F401,F841,B`; `py_compile` fallback) findings: −1, −2 if ≥ 10; bare `except:` / `except Exception: pass`: −1, −2 if > 5; any function > 120 lines: −1; TODO/FIXME > 10: −1.
4. **Operations** — `github_workflow`: last N runs: success rate ≥ 0.9 → +2 (≥ 0.7 → +1); last success ≤ 36 h → +2 (≤ 72 h → +1); median duration ≤ 60 min → +1. `facts`: Drive snapshot age ≤ 1 d → +2 (≤ 3 d → +1); report-email age ≤ 1 d → +2 (≤ 2 d → +1); last-day sent/quota ≥ 0.9 → +1. Unknown items are dropped from the denominator and listed as gaps; nothing known → n/a.
5. **Algorithm** — `algorithm.command` (ranker/filter/verifier/cap tests or the system's eval): 5 × passed / total parsed from the output; no parse → 5 if rc 0 else 0.
6. **Security** — 5 − 2 per secret finding (AKIA, `sk-`, `gh?_`, AIza, private keys, long hex/base64 assigned to `*KEY*|*SECRET*|*TOKEN*|*PASSWORD*`, minus allow-listed literals with a reason); −1 if `pip-audit` reports any vulnerability (n/a when not installed or `--no-network`). Env keys and connectors are listed as exposure, not scored.

**Degradation** = any lens delta ≤ −1 vs `latest.json` of the previous run, or any behavioural target `unmet`. First run has no deltas.

## Behavioural targets (from the registry)
- `job_search_v2`: email body is one table (table header present, no "Top 5" in the email builder); daily workflow success ≥ 90 % over the last 10 runs; ≥ 1 WTTJ job per day (fact `wttj_jobs_last_day`).
- `linkedin_connect`: report is one table (`| # | First name | Name | Company | Position | LinkedIn ID |`, no ledger block); slots/day = 3 (fact `slots_per_day`); one email/day at 20:00 (fact `report_email_time`).

## Cadence — cloud scheduled task, days 1/11/21 at 09:00 Europe/Paris
Cron `CRON_TZ=Europe/Paris 0 9 1,11,21 * *`, fresh session each fire, Gmail connector attached. Prompt, in order:
1. `python3 execution/infrastructure/system_eval.py run --facts .tmp/system_eval_facts.json` (build the facts file first from the linkedin_connect scheduled tasks and the latest Drive `ledger_*.csv` snapshot date; omit a fact rather than guess it).
2. Email the output of `python3 execution/infrastructure/system_eval.py report --email-body` to debanjan1cr06@gmail.com, subject `System evaluation — <date>`, body verbatim.
3. Commit `docs/reference/system_eval/**` (latest.json, previous.json, history, REPORTs) to `main` with message `chore(system_eval): <date> — <verdict per system>` and push.
The 10-day gap is the registry's `cadence_days`; `Next check` in the report is date + 10. First baseline: 2026-10-26.

## How to add a system
Add one object under `systems` in `config/system_eval.json`: `code` globs, `directive`, `deliverable_files`, `data.schema_grep` + `data.commands`, `algorithm.command`, `ops` (`github_workflow` with `workflow_file`, or `facts`), `security.allow` (literal + reason) and `security.connectors`, `targets` (kinds `grep`, `ops_success_rate_min`, `fact` with `equals`/`min`). No code change needed. Pass its facts under the same key in `--facts`.

## Edge cases / learnings
- `pytest tests -k ...` is interrupted by unrelated collection errors (missing optional deps such as `langdetect`); register explicit test files and `--continue-on-collection-errors` instead (2026-10-26).
- Other workers may be editing a system while it is evaluated; scores reflect the working tree at run time, not the last commit.
- `GMAIL_NOTIFY_TO`, `GITHUB_TOKEN`, `LINKEDIN_CONNECT_DIR` were read by code but absent from the directives' Inputs on the first run; the fix is a directive edit, not an allow-list.
- The WTTJ Algolia search key is public and referer-gated; it is the only allow-listed literal. Any new allow-list entry needs a `reason`.
- GitHub run duration uses `updated_at − run_started_at`; queued time is excluded, so median duration measures the job, not platform lag.
- All subprocesses decode UTF-8 with `errors="replace"`; per-check `--timeout` (default 600 s) turns a hang into an n/a with a note.
