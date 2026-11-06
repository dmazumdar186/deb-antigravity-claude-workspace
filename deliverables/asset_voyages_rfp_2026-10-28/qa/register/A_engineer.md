# Option A engineer register (unit, E2E, smoke, SAST, integration, performance, monkey)

Target: WordPress demo plugin `asset-congres-demo` in WordPress Playground. Unit, E2E, smoke and SAST rows come from the existing logs in `qa/A/logs/`; integration, performance and monkey rows were run on 2026-11-05/06 against the then-current plugin build (zip rebuilt with `build_zip.sh --local`) on a local Playground CLI 3.1.62 (fresh DB, port 9404; the Option A builder was changing the plugin in parallel, so results are for that build only). The `ViewTransition` page error does not occur in the plugin source (no `view-transition` string in `wp_demo/plugin`), so it likely comes from WordPress core or the theme; it was not isolated further with `qa/A/integration_A.mjs`, `perf_A.mjs`, `monkey_A.mjs` (shared helpers in `qa/A/common.mjs`). Local Playground (PHP-wasm + SQLite, 3 workers on 4 vCPU) is slower than real hosting; performance numbers are reported as measured.

ID | Type | Option | Story/gate | Steps | Expected | Actual | Evidence | Status | Run date
--- | --- | --- | --- | --- | --- | --- | --- | --- | ---
UNIT-A-001 | Unit | A | S3 | passagers 0, 1, 50, 51, -1, 'abc', '2.5', '', ' 7 ', '1e1' (cases 001-010) | 1..50 whole numbers accepted, all else rejected | 10/10 pass | qa/A/logs/unit.log (qa/A/unit/unit_A.php) | PASS | 2026-11-05
UNIT-A-002 | Unit | A | S3 | date_aller today ok, yesterday rejected, retour == aller ok, retour < aller rejected, 2026-02-30 rejected (011-015) | boundary dates enforced | 5/5 pass | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-003 | Unit | A | S3 | invalid e-mail, missing consent, nom 100/101, message 2000/2001, phone 5/6 digits (016-020) | both sides of each boundary | 5/5 pass | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-004 | Unit | A | S3 | array-typed field, valid input, script tag stripped, multibyte 100 chars (021-024) | no fatal, valid passes, HTML stripped | 4/4 pass | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-005 | Unit | A | S4 | CSV cell neutralises = + - @ TAB CR, plain unchanged, mid-string = untouched (025-032) | formula prefixes get a leading quote | 8/8 pass | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-006 | Unit | A | S5 | libsodium round trip, random nonce, no plaintext in ciphertext, tamper/garbage/short => null, empty and unicode (033-039) | encryption sound, tamper detected | 7/7 pass | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-007 | Unit | A | S5 | valid_code on DEMO-GME-4KQ7, 3/4/40/41 chars, lowercase, leading dash, trailing newline, spaces, empty (040-049) | format and length bounds enforced | 10/10 pass (047 documents PCRE `$` before trailing newline) | qa/A/logs/unit.log | PASS | 2026-11-05
UNIT-A-008 | Unit | A | S1/S4/S5 | roles and constants: contributeur cannot publish, equipe can, contrib subset of team, no GM&E/Demandes caps in congres map, 5 statuses, GM&E lifecycle, PAX 1..50 (050-056) | capability and state maps as designed | 7/7 pass | qa/A/logs/unit.log | PASS | 2026-11-05
E2E-A-001 | E2E | A | S2 | S2-F1 all 12 published upcoming congresses listed; past and draft are not | 12 listed | pass | qa/A/logs/e2e.log #1 | PASS | 2026-11-05
E2E-A-002 | E2E | A | S2 | S2-F2 keyword search: title, city, discipline, accent-insensitive | matches | pass | qa/A/logs/e2e.log #2 | PASS | 2026-11-05
E2E-A-003 | E2E | A | S2 | S2-F3 filters alone and combined, count, no-result, reset | works | pass | qa/A/logs/e2e.log #3 | PASS | 2026-11-05
E2E-A-004 | E2E | A | S2 | S2-F4 pagination keeps filters | works | pass | qa/A/logs/e2e.log #4 | PASS | 2026-11-05
E2E-A-005 | E2E | A | S2 | S2-F5 details page facts and prefilled enquiry form | all facts | pass | qa/A/logs/e2e.log #5 | PASS | 2026-11-05
E2E-A-006 | E2E | A | S2 | S2-F6 works with JavaScript off | server-rendered | pass | qa/A/logs/e2e.log #6 | PASS | 2026-11-05
E2E-A-007 | E2E | A | S2 gate E | S2-E1 find Cardiologie and open in <= 2 clicks | <= 2 clicks | pass | qa/A/logs/e2e.log #7 | PASS | 2026-11-05
E2E-A-008 | E2E | A | S2 gate E | S2-E2 at 390 px: no h-scroll, inputs >= 16 px, tap targets >= 44 px | holds | pass | qa/A/logs/e2e.log #8 | PASS | 2026-11-05
E2E-A-009 | E2E | A | S2 hostile | S2-H1 script/HTML and 5,000-char query escaped, no error | escaped | pass | qa/A/logs/e2e.log #9 | PASS | 2026-11-05
E2E-A-010 | E2E | A | S3 | S3-F1 all fields present, congress prefilled | present | pass | qa/A/logs/e2e.log #10 | PASS | 2026-11-05
E2E-A-011 | E2E | A | S3 | S3-E1 French errors next to fields, values kept, 1 click | holds | pass | qa/A/logs/e2e.log #11 | PASS | 2026-11-05
E2E-A-012 | E2E | A | S3 | S3-F2 valid submission stored, linked, reference shown | DV-2026-NNNN | pass | qa/A/logs/e2e.log #12 | PASS | 2026-11-05
E2E-A-013 | E2E | A | S3 | S3-F3 team notified (journal entry) | entry exists | pass | qa/A/logs/e2e.log #13 | PASS | 2026-11-05
E2E-A-014 | E2E | A | S3 | S3-F4 reload / replay creates no second enquiry | idempotent | pass | qa/A/logs/e2e.log #14 | PASS | 2026-11-05
E2E-A-015 | E2E | A | S3 hostile | S3-H1 invalid values rejected, no data change | rejected | pass | qa/A/logs/e2e.log #15 | PASS | 2026-11-05
E2E-A-016 | E2E | A | S3 hostile | S3-H2 honeypot, too-fast, missing nonce not stored | not stored | pass | qa/A/logs/e2e.log #16 | PASS | 2026-11-05
E2E-A-017 | E2E | A | S3 hostile | S3-H3 script/HTML in any field shown as text | escaped | pass | qa/A/logs/e2e.log #17 | PASS | 2026-11-05
E2E-A-018 | E2E | A | S1 | S1-E1 + F1 create and publish in <= 4 clicks, French labels, required marked | holds | pass | qa/A/logs/e2e.log #18 | PASS | 2026-11-05
E2E-A-019 | E2E | A | S1 | S1-E2 + F2 edit in <= 3 clicks, shows in admin and public | holds | pass | qa/A/logs/e2e.log #19 | PASS | 2026-11-05
E2E-A-020 | E2E | A | S1 | S1-F3 contributeur drafts and submits, cannot publish; Direction publishes | holds | pass | qa/A/logs/e2e.log #20 | PASS | 2026-11-05
E2E-A-021 | E2E | A | S1 hostile | S1-H1 end before start, invalid URL rejected, HTML in title as text | rejected | pass | qa/A/logs/e2e.log #21 | PASS | 2026-11-05
E2E-A-022 | E2E | A | S1 hostile | S1-H2 save without valid nonce changes nothing | unchanged | pass | qa/A/logs/e2e.log #22 | PASS | 2026-11-05
E2E-A-023 | E2E | A | S4 | S4-F1 S3 enquiry appears in Demandes, status Nouvelle | appears | pass | qa/A/logs/e2e.log #23 | PASS | 2026-11-05
E2E-A-024 | E2E | A | S4 | S4-F2 filter by status, search by name/reference | works | pass | qa/A/logs/e2e.log #24 | PASS | 2026-11-05
E2E-A-025 | E2E | A | S4 gate E | S4-E1 newest enquiry and status change in <= 3 clicks, counts update | holds | pass | qa/A/logs/e2e.log #25 | PASS | 2026-11-05
E2E-A-026 | E2E | A | S4 | S4-F3 status flow, owner, internal note saved | saved | pass | qa/A/logs/e2e.log #26 | PASS | 2026-11-05
E2E-A-027 | E2E | A | S4 | S4-F4 history append-only: who, when, from to; no edit/delete controls | holds | pass | qa/A/logs/e2e.log #27 | PASS | 2026-11-05
E2E-A-028 | E2E | A | S4 | S4-F5 CSV export, formula prefixes neutralised | holds | pass | qa/A/logs/e2e.log #28 | PASS | 2026-11-05
E2E-A-029 | E2E | A | S4 hostile | S4-H1 logged-out and contributeur cannot read or change enquiries | denied | pass | qa/A/logs/e2e.log #29 | PASS | 2026-11-05
E2E-A-030 | E2E | A | S5 | S5-F1 codes only in own table, encrypted, no plaintext in DB | holds | pass | qa/A/logs/e2e.log #30 | PASS | 2026-11-05
E2E-A-031 | E2E | A | S5 | S5-F2 + E1 equipe sees masked codes, requests with required reason in <= 2 clicks | holds | pass | qa/A/logs/e2e.log #31 | PASS | 2026-11-05
E2E-A-032 | E2E | A | S5 | S5-F3 + E1 direction approves in <= 2 clicks, refuses another | holds | pass | qa/A/logs/e2e.log #32 | PASS | 2026-11-05
E2E-A-033 | E2E | A | S5 | S5-F4 + E1 equipe reveals in <= 2 clicks, logged, journal Direction-only | holds | pass | qa/A/logs/e2e.log #33 | PASS | 2026-11-05
E2E-A-034 | E2E | A | S5 hostile | S5-F3 revoke at once; S5-H1 reveal after revoke / no nonce / no permission refused and logged | refused | pass | qa/A/logs/e2e.log #34 | PASS | 2026-11-05
E2E-A-035 | E2E | A | S5 | S5-F5 public pages say only « Tarif congrès négocié disponible » | no code | pass | qa/A/logs/e2e.log #35 | PASS | 2026-11-05
E2E-A-036 | E2E | A | S5 | S5-L2 codes never in HTML before reveal, never in logs, CSV, notifications | no leak | pass | qa/A/logs/e2e.log #36 | PASS | 2026-11-05
E2E-A-037 | E2E | A | S5 leak | S5-L1 + S4-F6 logged-out crawl (pages, feeds, sitemaps, search, REST routes, admin-ajax) | 0 leak | pass (6.3 min) | qa/A/logs/e2e.log #37 | PASS | 2026-11-05
E2E-A-038 | E2E | A | S5 leak | S5-L1 crawl as equipe without grant | 0 leak | pass (7.8 min) | qa/A/logs/e2e.log #38 | PASS | 2026-11-05
E2E-A-039 | E2E | A | S5 | S5-F1 after reveals DB still has no plaintext code | holds | pass | qa/A/logs/e2e.log #39 | PASS | 2026-11-05
E2E-A-040 | E2E | A | X1 | X1 zero console errors and zero failed requests on every tested screen | 0 errors | FAIL: "visitor HTTP 404: /congres/x" plus matching console 404 | qa/A/logs/e2e.log #40, error-context in wp_demo/.tmp/test-output | FAIL | 2026-11-05
E2E-A-041 | E2E | A | X2 | X2 visitor pages load no third-party scripts or requests | none | not run (skipped after X1 failure in serial mode) | qa/A/logs/e2e.log #41 | NOT RUN | 2026-11-05
E2E-A-042 | E2E | A | X3 | X3 all data fictional (« — exemple », @example.com, DEMO-GME-) | holds | not run (skipped) | qa/A/logs/e2e.log #42 | NOT RUN | 2026-11-05
E2E-A-043 | E2E | A | X4 | X4 re-seeding idempotent | no duplicates | not run (skipped) | qa/A/logs/e2e.log #43 | NOT RUN | 2026-11-05
E2E-A-044 | E2E | A | screens | Screens: visitor (1440 / 390 px) | captured | pass | qa/A/logs/e2e.log #44 | PASS | 2026-11-05
E2E-A-045 | E2E | A | screens | Screens: admin | captured | pass | qa/A/logs/e2e.log #45 | PASS | 2026-11-05
E2E-A-046 | E2E | A | S3 hostile | S3-H2 rapid repeat submissions rate-limited | limited | pass | qa/A/logs/e2e.log #46 | PASS | 2026-11-05
SMOKE-A-001 | Smoke | A | S2 | Hosted Playground, visitor blueprint: boots, catalogue shows 12 congresses | 12 results | boot 19.9 s, "12 congr", 18 cards | qa/A/logs/smoke_hosted.log, hosted-visitor.png | PASS | 2026-11-05
SMOKE-A-002 | Smoke | A | S4 | Hosted Playground, admin blueprint: logged in, opens on Demandes | admin bar + Demandes | boot 21.0 s, adminbar=1 | qa/A/logs/smoke_hosted.log, hosted-admin.png | PASS | 2026-11-05
SMOKE-A-003 | Smoke | A | build | php -l on every plugin file | no syntax errors | no syntax errors | qa/A/logs/phplint.log | PASS | 2026-11-05
SAST-A-001 | SAST | A | X security | Semgrep 596 rules on 12 tracked files | 0 findings | 3 findings, all `echoed-request` at includes/class-gme-admin.php lines 321, 328, 333 (log marks them blocking) | qa/A/logs/semgrep.log, semgrep.json | FAIL (open; reading the source at those lines shows values passed through esc_url/esc_attr/esc_html, so likely false positives, but no rule exemption is recorded) | 2026-11-05
SAST-A-002 | SAST | A | X security | grep pass: raw $wpdb queries | prepared or constant-only | reviewed list (interpolated {$table}/{$t} are internal constants, user values use prepare) | qa/A/logs/grep_sast.log (--wpdb) | PASS | 2026-11-05
SAST-A-003 | SAST | A | X security | grep pass: admin-post handlers, nonce checks, capability checks, eval/innerHTML | each handler listed with checks | listed; no eval/innerHTML sink flagged | qa/A/logs/grep_sast.log | PASS | 2026-11-05
INT-A-001 | Integration | A | S4 | Anonymous GET of Demandes screen (no redirect following) | 302 to wp-login, no data | 302 -> wp-login | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-002 | Integration | A | S5 | Anonymous GET of the three GM&E screens | 302, no code | 302 x3 | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-003 | Integration | A | S4 | Anonymous GET of CSV export (admin-post, with and without nonce) | refused, no CSV | 400, 400, no PII | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-004 | Integration | A | S2/S5 | Anonymous GET of catalogue | 200, no PII, no code | 200 clean | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-005 | Integration | A | S3 | Enquiry POST without nonce | refused, nothing stored | no confirmation, admin count unchanged (6) | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-006 | Integration | A | S3/S4 | Valid enquiry POST, then check in admin | record created, visible | DV-2026-0007, count 6 -> 7, listed with name | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-007 | Integration | A | S4 | Equipe changes status Nouvelle to Qualifiée | history gains a row, who and from to | rows 1 -> 2, "Nouvelle → Qualifiée", Équipe (démo) | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-008 | Integration | A | S5 | Equipe requests, direction approves (dashboard widget), equipe reveals | code shown for that congress only | DEMO-GME code displayed, masked before | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-009 | Integration | A | S5 | Direction revokes; equipe replays reveal POST | refused, no code, button gone, refusal logged | "aucune autorisation active", no code, refusal in journal | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-010 | Integration | A | S4 | Capability matrix Demandes: anon / contributeur / equipe / direction | 302 / 403 / 200 / 200 | as expected | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-011 | Integration | A | S5 | Capability matrix Codes GM&E | 302 / 403 / 200 / 200 | as expected | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-012 | Integration | A | S5 | Capability matrix Demandes d'accès | 302 / 403 / 403 / 200 | as expected | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-013 | Integration | A | S5 | Capability matrix Journal GM&E | 302 / 403 / 403 / 200 | as expected | qa/A/logs/integration.log | PASS | 2026-11-05
INT-A-014 | Integration | A | S1 | Capability matrix new congress page | 302 / 200 / 200 / 200 | as expected | qa/A/logs/integration.log | PASS | 2026-11-05
PERF-A-001 | Performance | A | X perf | Desktop 1440x900, catalogue, median of 3 (after warm-up) | LCP <= 2.5 s, CLS <= 0.1 | TTFB 977 ms, LCP 1044 ms, CLS 0.0000 | qa/A/logs/perf.log | PASS | 2026-11-05
PERF-A-002 | Performance | A | X perf | Desktop, congress page, median of 3 | same | TTFB 891 ms, LCP 968 ms, CLS 0.0000 | qa/A/logs/perf.log | PASS | 2026-11-05
PERF-A-003 | Performance | A | X perf | Pixel 7, slow-4G, 4x CPU, catalogue, median of 3 | same | TTFB 995 ms, LCP 1412 ms, CLS 0.0000 | qa/A/logs/perf.log | PASS | 2026-11-05
PERF-A-004 | Performance | A | X perf | Pixel 7, slow-4G, 4x CPU, congress page, median of 3 | same | TTFB 958 ms, LCP 1408 ms, CLS 0.0000 | qa/A/logs/perf.log | PASS | 2026-11-05
PERF-A-005 | Performance | A | X perf | 30 concurrent GET of catalogue | p95 <= 800 ms | p50 12511 ms, p95 13158 ms, 0 non-200. Local Playground CLI (3 PHP workers, wasm) serialises requests; not representative of hosting, so the target is not met locally | qa/A/logs/perf.log | FAIL (local environment) | 2026-11-05
MONKEY-A-001 | Monkey | A | X robustness | Seed 20261105, 300 actions logged out (clicks, typed unicode/5,000-char/`<script>`/`=HYPERLINK()`, submits, back/forward, resize 390-1440); assert no PHP Fatal/Warning/Notice/Deprecated, no 5xx, no page error, no DEMO-GME- | 0 violations | 0 failures in 300 actions | qa/A/logs/monkey_anon.log | PASS | 2026-11-06
MONKEY-A-002 | Monkey | A | X robustness | Same, contributeur | 0 violations | 8 failures, all "Transition was aborted because of invalid state. ViewTransition opt-in disabled" (uncaught page error when moving between admin and front pages); no PHP text, no 5xx, no code leak | qa/A/logs/monkey_contributeur.log, monkey_contributeur_failure_1..3.json (seed + last 20 actions) | FAIL | 2026-11-06
MONKEY-A-003 | Monkey | A | X robustness | Same, equipe | 0 violations | 9 failures, same ViewTransition page error only | qa/A/logs/monkey_equipe.log, monkey_equipe_failure_1..3.json | FAIL | 2026-11-06
MONKEY-A-004 | Monkey | A | X robustness + S5 | Same, direction | 0 violations | 13 failures, same ViewTransition page error only | qa/A/logs/monkey_direction.log, monkey_direction_failure_1..3.json | FAIL | 2026-11-06
MONKEY-A-005 | Monkey | A | S5 leak | DEMO-GME- in DOM (including input values) outside an authorised reveal, all four roles | none | 0 occurrences across 1,200 actions | qa/A/logs/monkey_*.log | PASS | 2026-11-06
