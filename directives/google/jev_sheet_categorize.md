# Jev Sheet Categorize — fill a category column with typed decisions

## Purpose

Turn "I have a sheet / bank export that needs a category column" into a one-command job.
Jev (TypeSafe, via OpenRouter's Decisions API) answers one `choice` question per row and can
only pick from the operator's option list, so it never invents a category. Low-confidence
rows get `?` for human review instead of a guess. Cost is ~$0.00002 per row.

## When to invoke

- Operator says "categorize column X of sheet Y into A/B/C using Jev" (or a CSV path).
- A bank/transaction/lead export needs a new label column (category, intent, tier, region).
- Backfilling blank cells in an existing label column.

Copy-paste operator prompt:

> Categorize column `category` of sheet `<SHEET_ID>` tab `<TAB>` into Groceries/Rent/Transport/Income/Other using Jev

## Inputs

- `--csv PATH` **or** `--sheet-id ID --tab NAME`: source rows. CSV mode needs no Google creds. Sheet mode reuses `google_sheets_writer.get_client()` (env `GOOGLE_SERVICE_ACCOUNT_PATH`).
- `--column NAME`: `str` — target column; created if missing; only blank cells filled unless `--overwrite`.
- `--options "A,B,C"` or `"A=desc,B=desc"`: `str` — required, the closed option list.
- `--question`: `str` — instructions; default built from the column name and options.
- `--source-cols a,b,c`: `str` — columns that form each row's state (default: all except target).
- `--min-confidence 0.55`: `float` — below it the cell gets `?` and counts as needs-review.
- `--limit N`, `--dry-run`, `--workers 8`, `--output PATH` (CSV mode; default `<input>.jev.csv`), `--json`.
- Env: `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- CSV mode: `<input>.jev.csv` (or `--output`) with the column filled.
- Sheet mode: the column written in place on the tab (header added at the end if new).
- stdout summary: `rows=... filled=... needs_review=... errors=...`, `cost_usd=... wall_s=...`, per-option counts.
- One ledger row in `.tmp/jev_ledger.jsonl` with `caller: jev_sheet_categorize`.

## Exit Criteria (declarative — read this before claiming "done")

- Every eligible row's target cell is either one of the `--options` keys (exact spelling) or `?`.
- No cell contains a value outside the option list.
- `filled + needs_review == eligible` in the summary.
- Summary printed with cost in USD; ledger row appended.
- `--dry-run` leaves the source untouched.

## Scripts (Layer 3)

- `execution/google/jev_sheet_categorize.py`
- `execution/modules/jev_client.py` (shared client; `decide_many`, `choice` builder)
- Tests: `tests/test_jev_sheet_categorize.py` (offline, monkeypatched `decide_many`)

## Edge cases

- Jev echoes an option in different case -> matched case-insensitively and written with the operator's spelling.
- Jev returns a value not in the list, an error, or empty answers (fail-open client) -> `?`, counted under `needs_review` (+ `errors` when the client reported one).
- Confidence below `--min-confidence` -> `?`. Raise the threshold for money columns, lower it for low-stakes tags.
- Option descriptions matter: `Other=anything that fits no other option` reduces false positives. Add `Other`/`none` when abstaining is valid.
- State is capped at 100k chars by the client; keep `--source-cols` to the informative columns on wide sheets.
- Sheet mode writes the whole column (RAW) in one `ws.update`; rows beyond the limit keep their existing value.
- No key -> exit 2 before reading anything.

## Changelog

- 2026-10-06: Created (RoboNuggets "Jev in Google Sheets" use case 1). CSV + Sheets modes, min-confidence review path, ledger row.
