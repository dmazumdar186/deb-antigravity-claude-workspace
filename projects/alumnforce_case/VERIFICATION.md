# Verification record — the five checks Annex A commits the presenter to

Run on 2026-10-13 by the delegated agent acting in Debanjan's role, on the operator's instruction that no human is in the loop. Each step records what was run, what was observed, and whether it matches the deck.

## 1. Re-run Annex B on the CSV — PASS

Ran the README snippet with `python3 -I` on `profils-exercice-PM.csv` (the delivered file, 525 rows) and the committed `annexB.sql`.

| Check | Observed | Deck says |
|---|---|---|
| Result rows | 49 | 49 |
| Reliability split | C 43, B 5, A 1 | To reactivate 43, to confirm 5, current 1 |
| Finance sources | declared 24, employer 17, title 8 | 24 / 17 / 8 |
| Members after dedup | 500 | 500 |
| Naive filter, file as delivered, with tenure | 2 | 2 |
| Normalised, no dedup | 26 | 26 |
| Member ids identical to committed annexB_result.csv | yes | — |

## 2. Open the CSV — PASS

| Check | Observed | Deck says |
|---|---|---|
| Rows, columns | 525, 15 | 525 rows |
| London spellings | 8: Greater London, LONDON, London, London - Canary Wharf, London, UK, Londres, Londres (Royaume-Uni), london | 8 |
| Ids above M0500 | 25, M0501 to M0525 | 25 apparent duplicates |
| Example pair | M0148 Camille Roux / M0502 Camille ROUX: same job (M&A Associate, Amundi), same start date 2015-12-06, gmail address on the duplicate | matches the description on slide 4 |

## 3. Read the twelve verbatims and the brief — PASS

Re-read in full. Coding on slide 3 confirmed as the presenter's judgement: speed V1, V2, V7; truth V3, V5, V9; proof V4, V10, V12; data V8, V11; not for me V6. One alternative reading noted: V7 (Yessica) is about adoption rather than speed; it does not change the "eight of twelve" count because it stays outside truth, proof and data either way.

## 4. Open the demo instance — PASS (read-only session, nothing created)

Logged in as the presenter's admin account; opened the existing list "Tous les alumni" in edit mode and its criteria picker.

| Check | Observed | Deck says |
|---|---|---|
| Criteria picker | 45 criteria under 9 group headers (Account, Preferences, Dues, Education, Mentoring, Mentoring programmes, Company forums, Professional situation, Geographic situation) | corrected from "~43 in 10" to "~45 in 9" |
| Last login / last profile update criterion | none; the only "last" item is "Last activity (Mentoring)" | none |
| Profile Update Campaign module | present under Communication | present |
| Saved lists | 31 ("1-25 of 31", "26-31 of 31"); newest "List - 10/10/2026 - 16:29"; no test list from 12/10/2026 | 31 |

## 5. Read every slide once as the presenter — PASS with four fixes applied

Full read of the rendered text. Positions, exclusions, thresholds and stop criteria stand as written. Defects found and fixed in the same pass:
- Annex C code block had two unescaped "less than" characters that swallowed the status definitions, the backfill line and the failure-mode line in the PDF. Escaped; the rendered page now shows them in full (confirmed by the visual reviewer at 130 dpi).
- "Master Finance" header on slide 4 made consistent with "Master in Finance".
- "Statistiques module" on slide 14 translated to "Statistics module".
- Slide 11 demo-ending line aligned with the rest of the deck: "6 current or to-confirm you can e-mail".

## Disclosure

The demo instance was explored twice by automated browser sessions under the presenter's account. The first session created one empty test list and deleted it; the second was read-only. The demo password should be changed.
