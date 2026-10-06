# Jev Inquiry Triage

## Purpose

Put a cheap, typed decision layer in front of the support inbox. Instead of paying a large
language model to read every message, Jev (TypeSafe, via OpenRouter's Decisions API) tags
each inquiry with a category, an urgency level and a needs-human probability in one call,
and tells you how sure it is. Anything Jev is not sure about goes straight to a person.
Reference scale from the source video: 217 call transcripts sorted in 13 s for 7 cents.

## When to invoke

- Operator asks to "triage", "sort", "tag" or "route" a batch of support emails, tickets,
  chat messages or call transcripts.
- A CRM/helpdesk export needs category labels before an automation or canned reply runs.
- Operator wants to measure how good the labels are against a hand-labelled sample.

Operator copy-paste prompt:

```
Triage the inquiries in <path.json|csv> with Jev (directives/crm_and_pm/jev_inquiry_triage.md).
Threshold 0.6, default categories. Give me the summary and the human-route rows.
```

## Inputs

- `--input`: `path` — JSON list of `{id, subject?, body, from?, channel?}` or CSV with those headers.
- `--categories`: `str` — comma list, optionally `key=description`. Default six:
  billing, bug, question, feature_request, complaint, spam.
- `--min-confidence`: `float` — route to `human` below this (default 0.6).
- `--workers`: `int` — parallel threads (default 8). `--limit N`, `--dry-run`.
- `--validate`: `path` — CSV `id,category` ground truth; prints accuracy + mismatches.
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- `--output`: `path` — JSON (default `<input>.triage.json`) with `summary`, `rows[]`
  (category, confidence, probabilities, urgency 0-2 + label, needs_human, route, cost_usd,
  error) and `validation` when requested. `--csv-out` writes a flat CSV.
- stdout summary: counts per category, per route, cost USD, wall time.
- Ledger row appended to `.tmp/jev_ledger.jsonl` (`caller: jev_inquiry_triage`).

## Routing rule

`route = human` when `confidence < --min-confidence` OR `needs_human >= 0.5` OR the tag
is `spam` with confidence below 0.8 (never auto-bin something Jev is unsure is junk).
Otherwise `automation`. Failed calls (no key, timeout, HTTP error) always route `human`.

Tuning note: start at 0.6. If the `human` queue is swamped with rows a person agrees with,
**lower** the threshold (0.5). If `--validate` shows wrong labels sliding into `automation`,
**raise** it (0.7) and sharpen the category descriptions first — descriptions move accuracy
more than the threshold does.

## Exit Criteria (declarative)

- Output JSON exists; `len(rows) == min(input_count, --limit)`.
- Every row has `route in {human, automation}`; every row with `error` routes `human`.
- `summary.errors / summary.count <= 0.05` on a live run (otherwise check the key / network).
- With `--validate`: accuracy printed and every mismatch listed with its confidence.

## Scripts (Layer 3)

- `execution/crm_and_pm/jev_inquiry_triage.py`
- `execution/modules/jev_client.py` (shared client; the only way to call Jev)
- `tests/test_jev_inquiry_triage.py` (offline, monkeypatched `decide_many`)

## Edge cases

- Bodies are truncated to 6,000 chars; the client caps state at 100k chars (32k-token context).
- Jev fails open: a row with `error` has empty category and routes `human`; cost still counted.
- `--categories "billing,bug"` without descriptions falls back to the built-in description for
  known keys, else the key itself; always pass descriptions for custom keys.
- Multi-issue messages typically show spread probabilities -> low confidence -> human. Intended.
- Pricing is input-only ($0.042/MTok on 2026-10-06); a 300-word inquiry costs ~$0.00002.

## Changelog

- 2026-10-06: Created (RoboNuggets Jev use case 2, with use case 8 validate pattern).
