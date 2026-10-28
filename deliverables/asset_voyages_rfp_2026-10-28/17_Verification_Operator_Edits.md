# 17 — Verification of operator-requested edits (28 Oct 2026, commit ef40e20)

Audit only, no edits. Scope: tone, naming, proposal timing, the one-PDF answer sheet, and regressions. Checked: the email (`01_`), 4 pages (local and live), `01b_`, `07_`, the PDF and DOCX. Method: grep, pypdf/python-docx parsing compared against the page and `01b_`, sha1 of live against local, and Playwright on the live site at iPhone 13 size.

## Evidence

| # | Check | Result |
|---|---|---|
| 1 | Condescension grep (plain/simple/easy/just/don't worry/obviously/basically; FR simplement/facile/ne vous inquiétez/en clair) on client-facing files | PASS. Only hits: "not just visits" (neutral) and "plain English" in internal `07_` rules line. A French office-management reader would find nothing that talks down. |
| 2 | Naming | PASS. EN first mention "Ms Veena Khatri" (email salutation, questions l.26), then "Ms Khatri". FR first mention « Mme Veena Khatri » (pour-asset l.23, console l.33), then « Mme Khatri ». The concept page names nobody. No bare "Veena" anywhere client-facing (lookbehind grep: 0 hits). |
| 3 | Dates | PASS. No "13 November"/"16 November" client-facing (only in `functional.mjs` as a negative assertion and in the internal proposal draft, see gaps). The chain is the same in the email, the 4 pages, `01b_`, `07_`, the PDF and the DOCX: 6 Nov answers; 24–48 h after answers, or by Tue 10 Nov if none; start within 5 working days of the signed proposal; ~12 weeks; no launch 21 Dec–1 Jan. The "18 November 2025" match is a past outage example, not a date in the plan. |
| 4a | PDF fields | PASS. 32 /Tx fields (q01–q30 + answered_by_name/role), 32 widgets, tooltips labelled. Fill test with « é » text saved and read back intact. |
| 4b | PDF/DOCX vs page | PASS. All 30 question texts and assumptions match the page exactly once whitespace is normalised. Answer first = 1, 2, 3, 5, 6, 9, 15, 18 on the page, in `01b_`, the PDF and the DOCX. The 30 labels make sense. Accents and « » extract correctly. The instructions say to return one PDF to debanjan@prodcraft.fyi by Friday 6 November 2026. The DOCX has 31 tables (name/role + 30 answer boxes). |
| 4c | Page vs `01b_` | Typography only: `01b_` uses "-" for "–" in Air France–KLM, and drops the quotes around "preferential fares", "Connexion Traveldoo", "Client login" and "Digital solutions" (Q18, 20, 23, 24). `01b_` is internal, so not blocking. |
| 4d | Live = local | PASS. The sha1 of the live PDF (b45c7749…), the live DOCX (b39e373e…) and all 4 pages matches local. |
| 4e | Playwright iPhone 13, /questions/ | PASS. Both download pairs (×2 on the page) are visible at 44 px tall, with no horizontal scroll (390/390). Tapping them downloads the PDF (101,385 B) and the DOCX (43,007 B). 0 console errors. The 19 targets under 24 px are inline links in body text, which WCAG 2.5.8 exempts. |
| 5 | Regression | No fees from ProdCraft. The only € figures are running costs, as before. No client names. No contradictions found across the email, the pages, `01b_` and `07_`. |

## Hostile-client reading of the changed sentences

- **"by Tuesday 10 November if no answers arrive by 6 November"**: bounded (a fixed date), so not an open-ended promise. OK.
- **"within 24–48 hours of receiving your answers"**: this one carries risk. The deadline is a Friday, so the most likely case is answers arriving Thursday or Friday, and 48 h then lands on Sunday. Answers sent after 6 Nov also start a fresh 48 h clock. For a solo founder that is a real chance of missing the first promise made to this client. Recommended wording: EN "within 24–48 hours (working days) of receiving your answers"; FR "dans les 24 à 48 heures ouvrées". Fri 6 Nov + 2 working days = Tue 10 Nov, which lines up with the no-answer date. This changes the operator's requested wording, so it is the operator's call.
- **FR "avant le vendredi 6 novembre 2026"** (pour-asset, Prochaines étapes): strictly this means "before", while EN says "by". Suggest "au plus tard le vendredi 6 novembre 2026". Low risk, because the misreading only moves answers earlier.
- **Email**: "Dear Ms Veena Khatri" follows the naming rule, though "Dear Ms Khatri" is the usual English salutation. "Ms Khatri's console" refers to the reader in the third person; it matches the page title. Both are optional.

## Honest gaps
- The tone judgement is one reviewer's reading, not tested with a native French reader.
- The PDF was not opened in Acrobat or Preview: there is no NeedAppearances flag, but the widgets carry /DA Helv. Filled values read back fine in pypdf.
- `proposal/ProdCraft_ASSET_Voyages_Proposal_v1.0_2026-10-28.md` l.198 still assumes a go-ahead on "Monday 16 November 2026". Add it to `16_Proposal_Carryover.md` before pricing. Not sent.

## Sign-off

| Panel | Verdict |
|---|---|
| 11-lens panel (`.claude/memory/panel_roster.md`) | **SIGN**. Dario/Daniela flag the weekend 48 h exposure as recommended, not blocking. |
| 5-expert panel (Senior UX/UI, Full-Stack, Solution Architect, PM, Product Designer) | **SIGN**. UX/Designer: downloads clear at 44 px on iPhone 13. Full-Stack: sheet generated from the page, live = local. PM: date chain consistent. |

**Overall: SEND.** Two optional wording tweaks (24–48 h working days; FR "au plus tard") are listed above for the operator.
