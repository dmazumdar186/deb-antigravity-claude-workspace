# Yoga teachers, France — Instantly-ready list (2026-10-14)

Source: `Yoga_Teachers_with_Email_-_France.csv` (229 rows, 10 cities). Built by
`execution/lead_sourcing/instantly_lead_cleaner.py` (directive: `directives/lead_sourcing/instantly_lead_cleaner.md`).

| File | Rows | Use |
|---|---|---|
| `Yoga_Teachers_France_instantly_ready.csv` | 195 | Everything, one row per email, all flags |
| `upload_named_and_sendable.csv` | 83 | Upload this for the personalised "Bonjour {{firstName}}" sequence |
| `upload_no_name_sendable.csv` | 62 | Studio mailboxes, no person found: use a sequence without a first name (or `{{firstName|there}}`) |
| `excluded_not_sendable.csv` | 50 | Invalid/disabled emails, placeholders, directory platforms (trainme, feverup, superprof pages…) |

Columns: `first_name` (given name only, blank if unknown), `company` (casual studio name), `website_status`
(live/redirect/dead), `send_recommended`, `name_source` (llm / website_deep / raw), `name_confidence`
(≤0.6 = not corroborated by email or URL, glance before sending), `original_name`, `dup_count`, `merged_from`.

Duplicates: 34 rows shared an email with another row (21 emails), e.g. one studio listed per location.
Instantly rejects those; they are merged (`merged_from` keeps the other listing names).
