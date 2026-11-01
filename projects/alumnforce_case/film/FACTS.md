# Film fact sheet — the only numbers and quotes the film may use

Source of truth: `../VERIFICATION.md`, `../README.md`, `../presentation.html` (reference date 2026-10-12, computed on the 500 members after deduplication unless stated). Any on-screen number or narrated number not in this table is a defect.

| id | Fact | Value | Source |
|---|---|---|---|
| F01 | The brief's example sentence | "Graduates working in finance in London for more than three years" | presentation slide 3 |
| F02 | Rows in the file vs members announced | 525 rows, 500 members | VERIFICATION §2 |
| F03 | Duplicate persons | 25 (M0501–M0525) | VERIFICATION §2 |
| F04 | Spellings of London | 8 | VERIFICATION §2 |
| F05 | Spellings of the UK / missing countries | 3 / 41 | README key numbers |
| F06 | Members with no declared sector | 174 | README key numbers |
| F07 | Naive filter (file as delivered, with tenure) | 2 | VERIFICATION §1 |
| F08 | Normalised (8 London spellings, 3 sector labels merged), no dedup | 26 | VERIFICATION §1 |
| F09 | Full logic (dedup + employer + job title as finance signals) | 49 | VERIFICATION §1 |
| F10 | Finance sources among the 49 | declared 24, employer 17, title 8 | VERIFICATION §1 |
| F11 | Reliability split of the 49 | current 1, to confirm 5, to reactivate 43 | VERIFICATION §1 |
| F12 | Worth contacting today | 6 (1 to send, 5 to confirm) | presentation slide 3 ("6 worth e-mailing today: profile or login recent enough to trust"); slide 4 (send / confirm / reactivate). Not "can be e-mailed": consent and opt-out are not in the selection. |
| F13 | Profiles untouched for 2+ years | 68 % | README key numbers |
| F14 | No login for 12+ months | 77 % (89 % if the 60 future-dated logins are treated as unknown) | README key numbers |
| F15 | Median delay between job start and profile update | 112 days | presentation slide 4 |
| F16 | Verbatims not about speed | 8 of 12 | presentation slide 2 |
| F17 | Verbatim quote (truth) | "340 London expats. Twenty had moved back years ago. Two unsubscribed." | presentation slide 2 |
| F18 | Verbatim quote (proof) | "'Roughly' does not pass a board." | presentation slide 2 |
| F19 | Product line | "Describe your audience in one sentence. Get a segment you can trust. No member record ever leaves the platform." | presentation slide 1 |
| F20 | Member-facing prompt | "Profile last updated 4 years ago · Confirm / Correct" | presentation slide 4 |
| F21 | Status words | Current · To confirm · To reactivate | presentation slide 4 |
| F22 | Insight | "Three years in post" and "three years without an update" are the same signal | presentation slide 4 |
| F23 | Product name | Trusted Segments | presentation slide 1 |
| F24 | Thesis (dream outcome) | "The administrator's problem is not building the list. It is believing it." | presentation slide 8 |
| F25 | Status actions | send · confirm · reactivate | presentation slide 4 ("Three words, three actions") |
| F26 | Real record for the loupe close-up (ID + city only, both from the result file) | M0271 · "Londres (Royaume-Uni)" | `../annexB_result.csv` row M0271 |
| F27 | The ask | Fund one quarter plus four weeks of measurement | presentation slide 8 |

## Hard rules for the film

- No member names, e-mails, employers next to a person, or any row-level personal data on screen. Member IDs (e.g. "M0502") may appear as anonymous record stubs; job titles may appear only without a name.
- No AlumnForce logo or trademark artwork (we don't have the assets or the rights). The words "AlumnForce" and "Trusted Segments" in plain type are fine.
- Numbers are shown exactly as above: no rounding, no "nearly 50".
- Background record cards carry no member ID (an ID next to an invented city is a false record). Only F26 may show an ID, with its real city.
- Every drawn label is paired with its own value on every frame (no label from step N over the value of step N-1).
- The end card carries the disclosure and credits: made in code by an AI agent with lemo-opuscar (MIT); synthetic voice (Kokoro, Apache 2.0); piano "Salamander Grand Piano V3" by Alexander Holm, CC BY 3.0 (with its URL); strings and mallets CC0 (Versilian Studios); IBM Plex fonts (OFL).
- Known gap: the raw CSV is not in the repo, so F13–F15 can only be re-verified on the operator's machine (see `../VERIFICATION.md`).
