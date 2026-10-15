# Panel verdict — AlumnForce case deliverable (2026-10-12; final rounds 2026-10-13 and 2026-10-15)

**Round 5 (2026-10-15).** Status: recruiter panel CLEAR; lenses 1–11 CLEAR; visual QA PASS (qa27: 19 pages, qa_pres3: 8 pages); pipeline audit round 2: 7/7 PASS. Evidence: "Round 5 evidence" table at the end of this file and VERIFICATION.md "Round 5 additions".
- 48 vs 49: the slide-printed SQL lacked `ib analyst` and `chargé d''affaires`; measured 48 (1/4/43) vs 49 (1/5/43); keyword lists now identical (22 = 22), both return 49 (VERIFICATION.md).
- Capacity: `24–28 effective dev-weeks` ×1, `26 dev-week core` ×1 in deck.html; `36 dev` ×0 across deck, presentation, guide, briefing, README.
- Deliverable 1: `reliability_status` ×2, `terms aggregation` ×1, no new criterion type; `support ticket in Q1` ×1.
- Scope: duplicate report and relative-date operator Q2 (`duplicate report when it ships in Q2` ×1, `the duplicate report follows in Q2` ×1).
- Saved segments: `re-resolved by the shared list loader` ×1, `fixed date` ×2, `90-day-stale segment fixture` ×1, `Computed on 15/10/2026` ×1.
- Annex A: `two automated browser sessions` ×1, `by an agent on my instruction` ×1, `VERIFICATION.md` ×1.

**Round 4 (2026-10-13).** Recruiter panel and lenses 1–11 CLEAR; visual QA PASS on 19 pages. Items closed, each with a grep row below: naive-count basis (`3 without the tenure clause`), login basis (`89 % if the 60 future-dated`), `6` as current + to confirm (`of which 1 current`), `3 of 8 are doubtful`, contest flow (`10 business days`), autofit idempotency (identical md5 on repeated runs, VERIFICATION.md), guide alignment.

Roster: `.claude/memory/panel_roster.md`, all eleven lenses run as sub-agents on the deck, the SQL, the speaker guide and the CSV. Before the roster pass, six executive lenses (hiring panel, CEO, CTO, CSO, CMO, CIO) ran three rounds; their findings are folded into the same deck. Status per lens: CLEAR = no high or medium gap left after fixes; the honest gaps are what no lens could verify and the candidate must own.

| # | Lens | Highest finding | Fix applied | Status |
|---|------|-----------------|-------------|--------|
| 1 | Karpathy, measurement | Master Finance count wrong (21/50 vs 19/47), 69 % computed on undeduplicated rows, "latest date" false, targets without derivation | Figures recomputed on n = 500 after a corrected dedup; targets labelled "initial guess, reset on week-4 baseline"; demo count marked illustrative; coding of verbatims shown with coder = 1 | CLEAR (re-verified against the CSV) |
| 2 | Cherny, tooling craft | PDF not reproducible from README; auto-fit bake not idempotent | `tools/autofit.js`, `tools/measure.js`, `tools/build.sh` committed; bake strips before writing; README rebuild section; REGEXP dropped from snippet | CLEAR |
| 3 | D. Amodei, honesty and law | Annex A claimed verifications the candidate had not done; competitor claims unhedged; "scrubbed" stated as a guarantee; password in scratch scripts | Annex A rewritten to what AI did and what the candidate verifies before sending (present tense, commitments); checklist and disclosure in the speaker guide; claims hedged; DPO sentence softened; scripts, session cookies and screenshots deleted | CLEAR; Annex A is true only once the checklist in the speaker guide is done |
| 4 | Research rigor | Dedup rule collapsed Martin into Martinez (26 drops, 499 members); `promo <= 2026` fails on text import; bounds and null handling undefined; eval metrics and model pinning unspecified | Rule requires same start date (25 drops, 500 members, result still 49, verified on typed and text imports); half-open bounds; null → to reactivate; eval definitions, kappa, negative recall, model id, temperature 0, prompt version pinned | CLEAR (SQL re-run by the lens) |
| 5 | Hormozi, offer | Dream outcome and proof absent from slide 1; time delay understated | Outcome tile rewritten; 2 / 26 / 49 / 6 on slides 1 and 13; "one quarter plus four weeks of measurement"; add-on reverts to included under 10 % reactivation | CLEAR |
| 6 | Saraev, automation | Thresholds never validated against a manually graded list; reactivation text author unstated | Weeks 1–2 hand-grading of 100 members on 2 tenants, 80 % agreement gate; fixed tenant-editable template, no model copy; per-tenant config table with owner and change log | CLEAR |
| 7 | Daniela Amodei, people | Alerts without owners; one-way member contest; edit rate as surveillance | Owners on slide 10; contest SLA, 12-month freeze, one reactivation per quarter, suppression after "not me"; metrics aggregate, pseudonymised, disclosed at flag-on; member wording specified | CLEAR |
| 8 | Sutskever, failure modes | Wrong-but-valid filter sets bounded only by the admin; drift detection trigger-based | Sanity bounds in the validator (radius cap, type table, count-vs-tenant alert), diff view, hard timeout; nightly replay against the live endpoint with a 5-point alert; provider version logged; cannot-map share tracked | CLEAR |
| 9 | Murati, UX | "Cannot map" behaviour unspecified; member-facing wording absent; vocabulary drift | One rule for partial mapping (inline fragment, never blank); member copy "Profil mis current il y a 4 ans · Confirmer / Corriger"; two names only (Trusted Segments, Reliability); chips above the table; generated name example | CLEAR |
| 10 | Brockman, reliability | No locks, rollback, runbook, rotation or dead-man alarm | Annex D: per-tenant lock and watermark, 36 h dead-man, alias-swap reindex with canary, expand/contract migration, upsert backfill proven by double run, 90-day dual-key rotation, one-page runbook with owners | CLEAR |
| 11 | Hassabis, systems | Feedback edges ended in dashboards; nothing recalibrated | Annex D loop table: edits → eval candidates; "not me" → status flip and threshold calibration; cannot-map → roadmap; tenant overrides promoted globally; campaign outcomes stored by segment × status; flywheel metric named | CLEAR |

## Honest gaps (kept, not papered over)

- Dev-week estimate (36 core), token cost, 80k-instance backfill duration, and the "~45 criteria / 31 lists" demo observations rest on one session and one estimate; the Lead Developer's numbers win.
- Competitor claims (Hivebrite, Graduway) are hedged, not verified.
- Legal positions are what the candidate would check with a DPO, not advice; the tenant decides its basis.
- The 2 y / 4 y / 1 y thresholds are initial and lopsided on this synthetic file (43 of 49 to reactivate); hand-grading in weeks 1–2 is the test.
- The eval set (100 + 30) is a gate, not a drift detector; nightly replay covers drift, but p95 latency and the scrub false-flag rate are unmeasured until built.
- Whether the demo instance's terms permit automated access was not checked; one empty list was created and deleted under the candidate's account.
- Annex A now lists what the candidate must verify personally; until they do, those lines are commitments, not facts.
- Visual QA was done by an agent reading rendered pages at 55 dpi; slides 6, 8, 9 and 13 are dense (body text at 85–88 % of base size).

## Evidence (commands run on 2026-10-13, outputs verbatim)

| Command | Output |
|---|---|
| `md5sum deck.html` before, after run 1 and after run 2 of `node tools/autofit.js` on a copy | `838c9939e454` / `838c9939e454` / `838c9939e454` (idempotent) |
| `node tools/measure.js \| grep -c OVER` | `0` |
| `python3 -c "import pypdf;print(len(pypdf.PdfReader('deck.pdf').pages))"` | `19` |
| README Annex B snippet with `python3 -I` on profils-exercice-PM.csv | `rows: 49`, split `{'C': 43, 'B': 5, 'A': 1}`, sources `{'finance:declared': 24, 'finance:employer': 17, 'finance:title': 8}`, members after dedup `500`, naive `2`, normalised no dedup `26`, ids identical to annexB_result.csv `True` |
| `grep -c` of fix phrases in deck.html: "Trusted Segments" / "To reactivate" / "36 dev-week core" / "nightly replay" / "10 business days" / "radius cap" / "flake budget 2 %" / "same start date" / "89 % if the 60 future-dated" / "3 of 8 are doubtful" / "Add this criterion by hand" / "Profile last updated 4 years ago" | 3 / 2 / 1 / 3 / 2 / 2 / 1 / 2 / 1 / 1 / 1 / 1 (all present) |
| `grep -rl "<demo password>" .` and `ls \| grep -c png` in the committed folder | `0` and `0` (no credential, no screenshot) |
| `python3 execution/infrastructure/workspace_sast.py --changed --quiet` | exit 0, no findings |
| Visual reviewer on qa20 renders (19 pages, 55 dpi plus 130 dpi crops of page 18) | PASS: no cut text, no footer collision, Annex C status, backfill and failure-mode lines fully visible |
| Demo instance, read-only session | 45 criteria in 9 groups; no last-login or profile-update criterion; "Campagne de mise à jour" present under Communication; 31 lists; no test list dated 12/10/2026 |

## Per-lens evidence: fix phrases present in deck.html (or file present), counted with grep on 2026-10-13

| Lens | Phrase or file | Count |
|---|---|---|
| 1 Karpathy | `89 % if the 60 future-dated` | 1 |
| 1 Karpathy | `3 of 8 are doubtful` | 1 |
| 1 Karpathy | `n = 500 after deduplication` | 1 |
| 1 Karpathy | `initial guess, reset on the week-4 baseline` | 1 |
| 2 Cherny | `tools/autofit.js` | 1 |
| 2 Cherny | `tools/build.sh` | 1 |
| 3 D. Amodei | `What I verify myself before sending` | 1 |
| 3 D. Amodei | `to my knowledge` | 1 |
| 3 D. Amodei | `residual hits in the question are logged` | 1 |
| 4 Rigor | `same start date` | 2 |
| 4 Rigor | `CAST(promo AS INTEGER)` | 1 |
| 4 Rigor | `Cohen's kappa` | 1 |
| 4 Rigor | `temperature 0` | 1 |
| 4 Rigor | `[0, 2 y)` | 1 |
| 5 Hormozi | `2 → 26 → 49 → 6` | 1 |
| 5 Hormozi | `plus four weeks of measurement` | 1 |
| 5 Hormozi | `reverting to included if reactivation stays under 10 %` | 1 |
| 6 Saraev | `CS grades 100 members on 2 tenants` | 1 |
| 6 Saraev | `fixed, tenant-editable text` | 1 |
| 6 Saraev | `assistant config table` | 1 |
| 7 Daniela | `10 business days` | 2 |
| 7 Daniela | `one reactivation per member per quarter` | 2 |
| 7 Daniela | `aggregate and pseudonymised` | 1 |
| 7 Daniela | `Profile last updated 4 years ago` | 1 |
| 8 Sutskever | `radius cap` | 2 |
| 8 Sutskever | `replayed nightly against the live endpoint` | 1 |
| 8 Sutskever | `cannot-map share` | 1 |
| 8 Sutskever | `hard timeout` | 1 |
| 9 Murati | `Add this criterion by hand` | 1 |
| 9 Murati | `Finance · London · classes 2015-2018` | 1 |
| 9 Murati | `Reactivate 27 members` | 1 |
| 9 Murati | `Trusted Segments` | 3 |
| 10 Brockman | `dead-man alarm` | 1 |
| 10 Brockman | `Alias-swap` | 1 |
| 10 Brockman | `dual-key rotation` | 1 |
| 10 Brockman | `Runbook` | 1 |
| 11 Hassabis | `weekly eval candidates` | 1 |
| 11 Hassabis | `recalibrates the 2 y / 4 y thresholds` | 1 |
| 11 Hassabis | `promoted to the global table` | 1 |
| 11 Hassabis | `Flywheel metric` | 1 |

## Round 5 evidence: grep counts in deck.html (2026-10-15)

| Lens | Phrase | Count |
|---|---|---|
| recruiter panel | `reliability_status` | 2 |
| recruiter panel | `terms aggregation` | 1 |
| recruiter panel | `support ticket in Q1` | 1 |
| recruiter panel | `26 dev-week core` | 1 |
| recruiter panel | `24–28 effective dev-weeks` | 1 |
| lens 5 / 11 (duplicate report Q2) | `duplicate report when it ships in Q2` | 1 |
| lens 5 / 11 (duplicate report Q2) | `the duplicate report follows in Q2` | 1 |
| lens 5 / 11 (duplicate report Q2) | `two variants compared on update rate` | 1 |
| lens 8 / 9 (saved-segment dates) | `re-resolved by the shared list loader` | 1 |
| lens 8 / 9 (saved-segment dates) | `fixed date` | 2 |
| lens 8 / 9 (saved-segment dates) | `Computed on 15/10/2026` | 1 |
| lens 8 / 9 (saved-segment dates) | `90-day-stale segment fixture` | 1 |
| lens 3 (Annex A honesty) | `two automated browser sessions` | 1 |
| lens 3 (Annex A honesty) | `by an agent on my instruction` | 1 |
| lens 3 (Annex A honesty) | `VERIFICATION.md` | 1 |
| lens 10 (mapping rides reindex) | `ride the alias-swap reindex` | 1 |
| tooling | md5 of committed deck.html | `7869b531793a` |
| guide | `operator, first` occurrences | 0 |
| guide | `duplicate report is Q2` in developer split | 1 |
