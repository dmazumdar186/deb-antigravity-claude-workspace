# Panel verdict — AlumnForce case deliverable (2026-10-12, final round 2026-10-13)

**Final round (2026-10-13): recruiter panel (CPO + Lead Developer) and all eleven roster lenses returned CLEAR on the current deck, with low-only notes; visual QA PASS on all 19 pages.** Items closed in that round: naive-count basis defined (2 with the tenure clause on the file as delivered, 3 without), 77 % login figure footnoted with the 89 % basis, "6" stated as current + to confirm with 1 current, 3 of 8 doubtful keyword matches, contest freezes status (10 business days) and never downgrades, autofit made idempotent (identical md5 on repeated runs), speaker guide aligned with the deck on permissions, dev-weeks and dedup.

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

- Dev-week estimate (36 core), token cost, 80k-instance backfill duration, and the "~43 criteria / 31 lists" demo observations rest on one session and one estimate; the Lead Developer's numbers win.
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
| `grep -rl "Test@1234" .` and `ls \| grep -c png` in the committed folder | `0` and `0` (no credential, no screenshot) |
| `python3 execution/infrastructure/workspace_sast.py --changed --quiet` | exit 0, no findings |
| Visual reviewer on qa20 renders (19 pages, 55 dpi plus 130 dpi crops of page 18) | PASS: no cut text, no footer collision, Annex C status, backfill and failure-mode lines fully visible |
| Demo instance, read-only session | 45 criteria in 9 groups; no last-login or profile-update criterion; "Campagne de mise à jour" present under Communication; 31 lists; no test list dated 12/10/2026 |
