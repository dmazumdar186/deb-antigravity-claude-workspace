# Client-eye gate report

Generated 2026-11-06T09:14:59.672Z. Commit 8a0aeeb4afdd49ef3716350888f39a0c87b103c5. Spec: `28_PreMortem_Client_Eye_Gate.md`. Machine-readable: `report.json`. Triage verdicts: `triage.json`. Register: `../register/CLIENT_EYE.md`.

## Targets and versions

- Hub: 5 tasks parsed, group section present; demo/index.html deployed = source, index.html deployed = source, js/demo.js deployed = source, css/demo.css deployed = source
- Option B Worker: 9fdd6cb6-04fa-4d3a-a7ea-b2b7617bca32 deployed 2026-11-06T07:50:09.302386Z; custom_demo/src last commit d1c1942 2026-11-06T07:32:28+00:00
- Option A: local Playground http://127.0.0.1:9437 built from the current wp_demo/ (zip f2db344e4d84); hosted zip f2db344e4d84
- Uncommitted source changes at run time: ?? deliverables/asset_voyages_rfp_2026-10-28/site/demo/media/wp-walkthrough.jpg; ?? deliverables/asset_voyages_rfp_2026-10-28/site/demo/media/wp-walkthrough.mp4
- States captured: 336; widths 320, 390, 768, 1280, 1440, 1920; roles A:visiteur, A:direction, A:contributeur, A:equipe, A-hosted:visiteur, B:visiteur, B:contributeur, B:direction, B:equipe, B:voyageur, HUB:visiteur
- Part a: run 2026-11-06T09:10:01.998Z
- Part ahosted: run 2026-11-06T09:12:23.072Z
- Part b: run 2026-11-06T08:46:59.089Z, logins 9, writing contexts 2, own sandboxes 2
- Part hub: run 2026-11-06T09:04:59.284Z

## Per check

| Check | Type | What | REAL | FALSE-POSITIVE | UNTRIAGED | Status |
|---|---|---|---|---|---|---|
| A1 | auto | E-mail draft: one short https link, 200, no Playground URL | 0 | 0 | 0 | PASS |
| A2 | auto | Boot time shown next to each Option A button; boot screen never blank (hosted boot measured) | 0 | 0 | 1 | FAIL |
| A3 | auto | Text blacklist (will appear here, REPLACE, TODO, lorem, undefined, NaN, null, [object Object], {{, %s, XXX) in text and attributes | 0 | 0 | 0 | PASS |
| A4 | auto | Every anchor, src, href, poster, video source answers 200 (or 30x to 200) with the right content type; no mixed content | 0 | 0 | 43 | FAIL |
| A5 | auto | Videos: poster, controls, playsinline, preload=metadata, < 25 MB, faststart, decoded frames > 0 | 0 | 0 | 0 | PASS |
| A6 | auto | Meaningful <title> and a favicon that answers 200 | 0 | 0 | 0 | PASS |
| A7 | decision | Address bar shows « debanjan186 »: operator decision | 0 | 0 | 0 | OPERATOR DECISION |
| B1 | auto | No English in French screens (fr-FR and en-GB browsers); hub French only inside « » | 0 | 0 | 0 | PASS |
| B2 | auto | No ISO/US dates; jj/mm/aaaa valid; Paris time; 00:05 Paris clock probe | 0 | 0 | 16 | FAIL |
| B3 | auto | Plural agreement after 0, 1, 2 and many | 0 | 0 | 0 | PASS |
| B4 | auto | No mid-word breaks, no line starting with » ; : ! ? or ending with «, no orphan « — exemple » (320/390/768/1280/1440/1920) | 0 | 0 | 33 | FAIL |
| B5 | auto | Spell check fr + en (pyspellchecker) with a reasoned allowlist | 0 | 0 | 150 | FAIL |
| B6 | auto | Glossary of key labels: same names in the hub and both UIs | 0 | 0 | 10 | FAIL |
| B7 | auto | Missing accents / capitals on known words | 0 | 0 | 0 | PASS |
| C1 | auto | No 4xx/5xx, console or page errors in normal use; styled French error pages reached only on purpose | 0 | 0 | 6 | FAIL |
| C2 | auto | Every visible non-submit button changes something within 2 s; submit buttons exercised by the journeys | 0 | 0 | 0 | PASS |
| C3 | auto | No empty box: every 0-item list shows a sentence | 0 | 0 | 3 | FAIL |
| C4 | auto | CLS ≤ 0.02 per page | 0 | 0 | 7 | FAIL |
| C5 | auto | One body family, one display family, one button style family, one accent colour per surface | 0 | 0 | 4 | FAIL |
| C6 | auto | No horizontal overflow (six widths); anchors not under the sticky header | 0 | 0 | 0 | PASS |
| C7 | auto | Expired session shows « Session expirée » + login link; purge only idle > 24 h; hub says private + 24 h reset | 0 | 0 | 6 | FAIL |
| C8 | auto | No technical residue (errors, stack, JSON braces, wp: markup, hex runs ≥ 16) in visible text | 0 | 0 | 0 | PASS |
| C9 | auto | No test residue in the sample data (fresh browsers) | 0 | 0 | 1 | FAIL |
| C10 | auto | Instruction replay: each hub step followed literally by visible labels | 0 | 0 | 5 | FAIL |
| D1 | auto | Every « Works in the demo » cell backed by evidence; « Built during the project » not faked by UI | 0 | 0 | 4 | FAIL |
| D2 | auto | Fictional people: @example.com, fiction phone ranges, no real congress names | 0 | 0 | 29 | FAIL |
| D3 | auto | Every number on the hub is a week, a date, our demo data, or traced to a source line | 0 | 0 | 1 | FAIL |
| D4 | auto | No GM&E code in DOM, attributes or inputs outside an approved reveal | 0 | 0 | 1 | FAIL |
| E1 | auto | Report names the commit and deployed versions; hub links checked against live versions | 0 | 0 | 0 | PASS |
| E2 | process | Full suites twice green after every change; this gate runs last | 0 | 0 | 0 | HUMAN/PROCESS |
| E3 | auto | Screenshots taken by this run from fresh contexts on the deployed sites | 0 | 0 | 0 | PASS |
| E4 | n/a | WebKit and Firefox | 0 | 0 | 0 | N/A |
| E5 | auto | Every check at 390 and 1440; B4/C6 at six widths | 0 | 0 | 0 | PASS |

## Check notes

- **E4** N/A: Only Chromium is installed (.links, chromium, chromium-1243, chromium_headless_shell-1243, ffmpeg-1011); Firefox and WebKit are not, and the brief forbids installing them. Recorded N/A, never PASS.
- **A7** OPERATOR DECISION: Option B's address is https://asset-voyages-demo.debanjan186.workers.dev (contains « debanjan186 »). Accepted unless the operator asks for a custom domain.
- **E2** HUMAN/PROCESS: The suites (wp_demo/tests/run_all.sh, custom_demo playwright) must run twice green after the last change; this gate does not run them. It runs last, on the deployed versions named above.
- **E3** PASS: 268 screenshots, all written by this gate from fresh browser contexts on the deployed hub and Option B and the local Option A build.
- **E5** PASS: A: 320/390/768/1280/1440/1920; A-hosted: 1440; B: 320/390/768/1280/1440/1920; HUB: 320/390/768/1280/1440/1920. The hosted Option A boot is one boot per link at 1440 by design (brief).

## Findings

### A2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 3ce3c17ff3 | UNTRIAGED | A-hosted | not ready after 120 s | admin link never showed its first screen | https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json · visiteur · 1440 |  |  |

### A4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| c9a5600558 | UNTRIAGED | A | https://example.com/congres/cg-0112 · `a « example.com »` | HTTP 404 | http://127.0.0.1:9437/congres/journees-mediterraneennes-doncologie-exemple/ · visiteur ·  |  |  |
| 794dc7cdea | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=36&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| d107eaec2b | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=38&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 7f2f397415 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=39&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 804cb88d6a | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=40&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| c8cba200c1 | UNTRIAGED | A | https://example.com/congres/cg-0101 · `a « example.com »` | HTTP 404 | http://127.0.0.1:9437/congres/congres-europeen-de-cardiologie-exemple/ · visiteur ·  |  |  |
| f7cf0a2ba8 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=43&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 8ac911efe5 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=44&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 9d9af78d76 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=45&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 8ba36be5d8 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=42&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 2876580dc3 | UNTRIAGED | A | http://127.0.0.1:9437/?post_type=asset_congres&p=46&preview=true · `a « Prévisualiser (ouvre un nouvel onglet) »` | HTTP 404 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · visiteur ·  |  |  |
| 4636c24bf9 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=cardiologie · `a « Cardiologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 2ea8ef3f2c | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=dermatologie · `a « Dermatologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 71d6627c47 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · `a « ASSET Voyages — démonstration »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 5ddb40509b | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/wp-login.php?redirect_to=https%3A%2F%2Fwpsandbox.wordpress.net%2Fscope%3Attxa-uyim-tjij · `a « Espace équipe »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 1ae383c934 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=diabetologie · `a « Diabétologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| de3f9d0bf4 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=finance · `a « Finance »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 2998e50bb6 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=hematologie · `a « Hématologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| ae120a39fa | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=neurologie · `a « Neurologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 8b96262ff3 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=pneumologie · `a « Pneumologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| ab76db9ef4 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=oncologie · `a « Oncologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 594b749b68 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=ophtalmologie · `a « Ophtalmologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 3d663b3699 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=ressources-humaines · `a « Ressources humaines »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 71f5578ebc | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?discipline=radiologie · `a « Radiologie »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 696c6168d0 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-europeen-de-radiologie-exemple/ · `a « Congrès européen de radiologie — exemple »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 0ac101e8eb | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/journees-francophones-de-diabetologie-exemple/ · `a « Journées francophones de diabétologie —  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 750a488555 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/forum-europeen-des-ressources-humaines-exemple/ · `a « Forum européen des ressources humaines — »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 4c728fc968 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-international-de-pneumologie-exemple/ · `a « Congrès international de pneumologie — e »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| f4544940c7 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-europeen-de-cardiologie-exemple/ · `a « Congrès européen de cardiologie — exempl »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| d3bd1c73ed | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-europeen-de-dermatologie-exemple/ · `a « Congrès européen de dermatologie — exemp »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 2908d55a90 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/journees-mediterraneennes-doncologie-exemple/ · `a « Journées méditerranéennes d’oncologie —  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| d1759d3755 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-dophtalmologie-de-paris-exemple/ · `a « Congrès d’ophtalmologie de Paris — exemp »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 0ce3221eaa | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/congres/congres-europeen-de-neurologie-exemple/ · `a « Congrès européen de neurologie — exemple »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| fd9b344526 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/wp-content/themes/twentytwentyfive/style.min.css?ver=0.2.0 · `link:stylesheet «  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| d326bcebdc | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/?pg=2 · `a « 2 »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| c412305721 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/wp-content/plugins/asset-congres-demo/assets/css/public.css?ver=0.2.0 · `link:stylesheet «  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| b695aa69e1 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/wp-json/ · `link:https://api.w.org/ «  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 853315e039 | UNTRIAGED | A-hosted | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/xmlrpc.php?rsd · `link:EditURI «  »` | HTTP 404 | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur ·  |  |  |
| 71a41e6fe7 | UNTRIAGED | B | https://www.example.org/congres/cg-0112 · `a « www.example.org/congres/cg-0112 »` | HTTP 404 | https://asset-voyages-demo.debanjan186.workers.dev/congres/journees-d-oncologie-digestive-cg-0112 · visiteur ·  |  |  |
| 12317546a0 | UNTRIAGED | B | https://www.example.org/relecture · `a « www.example.org/relecture »` | HTTP 404 | https://asset-voyages-demo.debanjan186.workers.dev/congres/congres-de-relecture-8yyd-cg-0114 · visiteur ·  |  |  |
| 52da26a502 | UNTRIAGED | B | https://www.example.org/congres/cg-0108 · `a « www.example.org/congres/cg-0108 »` | HTTP 404 | https://asset-voyages-demo.debanjan186.workers.dev/demande · visiteur ·  |  |  |
| 16cea18f91 | UNTRIAGED | HUB | https://www.sft.fr/docs/2024164729_sft-2022-enquete-traduction.pdf · `a « French translators’ union (SFT) 2022 sur »` | HTTP 403 | https://asset-voyages-redesign.pages.dev/questions/ · visiteur ·  |  |  |
| eeca7f2a74 | UNTRIAGED | HUB | https://www.sft.fr/global/gene/link.php?doc_id=882&edit_lang=fr · `a « 2025 survey »` | HTTP 403 | https://asset-voyages-redesign.pages.dev/questions/ · visiteur ·  |  |  |

### B2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 3eb0730482 | UNTRIAGED | A | $last                 = gmdate( 'Y-m-t', (int) strtotime( $first . ' 12:00:00 UTC' ) ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-catalogue.php:203 · visiteur ·  |  |  |
| 22968a85f1 | UNTRIAGED | A | header( 'Content-Disposition: attachment; filename="demandes-asset-' . gmdate( 'Ymd' ) . '.csv"' ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-demandes-admin.php:410 · visiteur ·  |  |  |
| e17c6b0432 | UNTRIAGED | A | return gmdate( 'Y-m-d H:i:s' ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-gme.php:262 · visiteur ·  |  |  |
| 9846433327 | UNTRIAGED | A | $data['expires_at'] = gmdate( 'Y-m-d H:i:s', time() + self::GRANT_HOURS * HOUR_IN_SECONDS ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-gme.php:414 · visiteur ·  |  |  |
| b3d337363e | UNTRIAGED | A | $when = gmdate( 'Y-m-d H:i:s', time() - $r[12] * DAY_IN_SECONDS ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-seed.php:313 · visiteur ·  |  |  |
| 0a0699a2fd | UNTRIAGED | A | Asset_CD_Demandes::add_history( $id, 'owner', '0', (string) $r[11], '', $r[11], gmdate( 'Y-m-d H:i:s', strtotime( $when ) + 3600 ) ); · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-seed.php:346 · visiteur ·  |  |  |
| 70ab645147 | UNTRIAGED | A | Asset_CD_Demandes::add_history( $id, 'status', $prev, $s, '', $r[11] ? $r[11] : $eq, gmdate( 'Y-m-d H:i:s', strtotime( $when ) + ( $i + 2 )  · `source` | PHP date()/gmdate() uses UTC, not Europe/Paris: one day off near midnight if shown or compared to a Paris date | wp_demo/plugin/asset-congres-demo/includes/class-seed.php:352 · visiteur ·  |  |  |
| f42da6f53c | UNTRIAGED | B | const t = today(); · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/public.js:39 · visiteur ·  (3×) |  |  |
| 3fe656b2aa | UNTRIAGED | B | export const gmeOnSale = (c, t = today()) => c.gme_status === 'approuve' && (!c.gme_from \|\| c.gme_from <= t) && (!c.gme_to \|\| c.gme_to >= t) · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/public.js:113 · visiteur ·  |  |  |
| 09c512880f | UNTRIAGED | B | export function validateEnquiry(get, t = today()) { · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/public.js:181 · visiteur ·  |  |  |
| 54250dccb5 | UNTRIAGED | B | if (!c \|\| c.end_date < today()) return htmlResponse(errorPage({ status: 404, title: 'Congrès introuvable', text: 'Ce congrès n’est pas ou pl · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/public.js:220 · visiteur ·  |  |  |
| 31fd4818ad | UNTRIAGED | B | headers: { 'content-type': 'text/csv; charset=utf-8', 'content-disposition': `attachment; filename="demandes-${today()}.csv"`, ...NO_STORE } · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/console.js:477 · visiteur ·  |  |  |
| ff1458f0f2 | UNTRIAGED | B | headers: { 'content-type': 'text/csv; charset=utf-8', 'content-disposition': `attachment; filename="groupe-${r.ref}-${today()}.csv"`, ...NO_ · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/console.js:742 · visiteur ·  |  |  |
| 03d674c52a | UNTRIAGED | B | export const linkExpiry = (fromIso = today()) => addDays(String(fromIso).slice(0, 10), LINK_DAYS) + 'T23:59:59Z'; · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/group.js:34 · visiteur ·  |  |  |
| b5da0f2d60 | UNTRIAGED | B | export function validateDelegate(get, congress, t = today()) { · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/group.js:67 · visiteur ·  |  |  |
| 9aa7ec4c27 | UNTRIAGED | B | return { state: state === 'active' && congress.end_date < today() ? 'ended' : state, env: scoped, link, enquiry, congress, mac }; · `source` | at 00:05 Paris (2026-11-06T23:05:00Z) today() = 2026-11-06 but the Paris date is 2026-11-07 | custom_demo/src/group.js:139 · visiteur ·  |  |  |

### B4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| a28d8ccedf | UNTRIAGED | A | terranéennes d’oncologie — exemple		 · `section#devis > p.asset-quote__for` | orphan-dash | http://127.0.0.1:9437/congres/journees-mediterraneennes-doncologie-exemple/ · visiteur · 320/768/1280/1440/1920 (6×) |  |  |
| 3ab292336d | UNTRIAGED | A | s européen de radiologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/ · visiteur · 390/768 (3×) | out/shots/0003-A-visiteur-390-catalogue.png |  |
| ae7db8f78c | UNTRIAGED | A | s européen de neurologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/ · visiteur · 390/768/1440 (5×) | out/shots/0003-A-visiteur-390-catalogue.png |  |
| adaa5499a7 | UNTRIAGED | A |  européen de cardiologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/ · visiteur · 390/768/1280/1440/1920 (18×) | out/shots/0003-A-visiteur-390-catalogue.png |  |
| 93ccbd461d | UNTRIAGED | A | d’ophtalmologie de Paris — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/ · visiteur · 768/1280/1440/1920 (6×) |  |  |
| b791b017d6 | UNTRIAGED | A | européen de dermatologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/ · visiteur · 1280/1440/1920 (5×) |  |  |
| 99618d36fa | UNTRIAGED | A | nternational d’oncologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/?pg=2 · visiteur · 1440 (2×) | out/shots/0020-A-visiteur-1440-page-2.png |  |
| 963c2fa98e | UNTRIAGED | A |  la finance d’entreprise — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | http://127.0.0.1:9437/?pg=2 · visiteur · 1440 (2×) | out/shots/0020-A-visiteur-1440-page-2.png |  |
| b33045af5a | UNTRIAGED | A | ongrès de relecture u2lc — exemple · `tr#post-36 > th.title.column-title > strong > a.row-title` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 (5×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| 6127db1056 | UNTRIAGED | A | ongrès de relecture 5cjf — exemple · `tr#post-25 > th.title.column-title > strong > a.row-title` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 (5×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| 197e6d6fe8 | UNTRIAGED | A | rnational de pneumologie — exemple · `tbody > tr > td > strong` | orphan-dash | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · direction · 1440/390/1280/1920 (10×) | out/shots/0045-A-direction-1440-direction-wp-admin-admin-php-page-asset-gme.png |  |
| f7a7b86343 | UNTRIAGED | A | atologie, édition passée — exemple · `tr#post-16 > th.title.column-title > strong > span` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · contributeur · 390/1920 (5×) | out/shots/0095-A-contributeur-390-contributeur-390-wp-admin-edit-php-post-type-asset-congres.png |  |
| a2afba3c65 | UNTRIAGED | A | américain de cardiologie — exemple · `tr#post-14 > th.title.column-title > strong > span` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · contributeur · 390/1920 (5×) | out/shots/0095-A-contributeur-390-contributeur-390-wp-admin-edit-php-post-type-asset-congres.png |  |
| bf5e9714b0 | UNTRIAGED | A | d’ophtalmologie · `tbody#the-list > tr > td.congres.column-congres` | mid-word | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1280 |  |  |
| a714bbc974 | UNTRIAGED | A |  rhumatologie, brouillon — exemple · `tr#post-17 > th.title.column-title > strong > a.row-title` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1280 |  |  |
| 77b442af30 | UNTRIAGED | A |  des ressources humaines — exemple · `tr#post-12 > th.title.column-title > strong > a.row-title` | orphan-dash | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1280 |  |  |
| f1d080dae3 | UNTRIAGED | A-hosted | d’ophtalmologie de Paris — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur · 1440 | out/shots/0146-A-hosted-visiteur-1440-hosted-visitor-first-screen.png |  |
| 40e8188284 | UNTRIAGED | A-hosted |  européen de cardiologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur · 1440 | out/shots/0146-A-hosted-visiteur-1440-hosted-visitor-first-screen.png |  |
| 8b84b9723b | UNTRIAGED | A-hosted | européen de dermatologie — exemple · `ul.asset-grid > li.asset-card > h2.asset-card__title > a` | orphan-dash | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur · 1440 | out/shots/0146-A-hosted-visiteur-1440-hosted-visitor-first-screen.png |  |
| cd266b3a95 | UNTRIAGED | B | voyer aux 6 participants : chacun r · `section#lien-groupe > p.quiet` | line-starts-with-: | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1 · equipe · 390 (2×) |  |  |
| 59381427af | UNTRIAGED | B | voyer aux 4 participants : chacun r · `section#lien-groupe > p.quiet` | line-starts-with-: | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/6 · equipe · 390 | out/shots/0173-B-equipe-390-equipe-console-demandes-6-390.png |  |
| 84680100f5 | UNTRIAGED | HUB | s européen de radiologie — exemple · `ul.rows > li.row > div > p.row__t` | orphan-dash | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 | out/shots/0002-HUB-visiteur-320-hub.png |  |
| 166e9eb7e8 | UNTRIAGED | HUB | ès mondial de neurologie — exemple · `ul.rows > li.row > div > p.row__t` | orphan-dash | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 | out/shots/0002-HUB-visiteur-320-hub.png |  |
| 118cb66805 | UNTRIAGED | HUB | montre ce que fait ASSET : la deman · `main > section.cover > p` | line-starts-with-: | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 | out/shots/0003-HUB-visiteur-320-hub-pour-asset.png |  |
| 57b72b16cc | UNTRIAGED | HUB |  quelle que soit », « voyages d’affaires · `article#doc > p` | line-ends-with-« | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320/390 (3×) | out/shots/0003-HUB-visiteur-320-hub-pour-asset.png |  |
| 0726f80e7e | UNTRIAGED | HUB | la carte « Voyages d’affaires · `table.cmp > tbody > tr > td` | line-ends-with-« | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320/390/768/1280/1440/1920 (8×) | out/shots/0003-HUB-visiteur-320-hub-pour-asset.png |  |
| 8d1d888fba | UNTRIAGED | HUB | la carte « Meetings & Events  · `table.cmp > tbody > tr > td` | line-ends-with-« | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320/390/768/1280/1440/1920 (8×) | out/shots/0003-HUB-visiteur-320-hub-pour-asset.png |  |
| add1fe7ffc | UNTRIAGED | HUB | is « ©2020 » et « © 2026 » · le chi · `table.cmp > tbody > tr > td` | line-starts-with-» | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320/390 (3×) | out/shots/0003-HUB-visiteur-320-hub-pour-asset.png |  |
| 52ce199602 | UNTRIAGED | HUB | ncontres d’ophtalmologie — exemple · `table.tbl > tbody > tr > td` | orphan-dash | https://asset-voyages-redesign.pages.dev/console/ · visiteur · 320/390/768 (4×) | out/shots/0004-HUB-visiteur-320-hub-console.png |  |
| 10c60a708d | UNTRIAGED | HUB | a free-text « Précisions » box. · `li#q22 > span > span.qa` | line-starts-with-» | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 | out/shots/0005-HUB-visiteur-320-hub-questions.png |  |
| d9a5ad0aa8 | UNTRIAGED | HUB | écran, sans rien envoyer ; en produ · `article#doc > ul > li` | line-starts-with-; | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 768 | out/shots/0013-HUB-visiteur-768-hub-pour-asset.png |  |
| b775cc08de | UNTRIAGED | HUB | s go in a free-text « Précisions » box. · `li#q22 > span > span.qa` | line-ends-with-« | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 768 | out/shots/0015-HUB-visiteur-768-hub-questions.png |  |
| fa88f052d6 | UNTRIAGED | HUB | e affiche à la fois « ©2020 » et « © 202 · `table.cmp > tbody > tr > td` | line-ends-with-« | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 1280/1440/1920 (4×) | out/shots/0018-HUB-visiteur-1280-hub-pour-asset.png |  |

### B5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 9329d98650 | UNTRIAGED | A | admin · `fr` | unknown fr word in « admin » (1×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes&action=view&id=41 · equipe · 1440 |  |  |
| 34965dcb35 | UNTRIAGED | A | Allemagne · `fr` | unknown fr word in « Allemagne » (83×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| 899a1eda13 | UNTRIAGED | A | Amsterdam · `fr` | unknown fr word in « Amsterdam, Pays-Bas » (32×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| ff624ee9c4 | UNTRIAGED | A | Band · `fr` | unknown fr word in « Assignez un terme parent pour créer une hiérarchie. Le terme Jazz, par exemple, serait le parent de Bebop et Big Band. » (10×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| db36f58496 | UNTRIAGED | A | Bebop · `fr` | unknown fr word in « Assignez un terme parent pour créer une hiérarchie. Le terme Jazz, par exemple, serait le parent de Bebop et Big Band. » (10×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| aa91c97a14 | UNTRIAGED | A | Berlin · `fr` | unknown fr word in « Berlin, Allemagne » (16×) | http://127.0.0.1:9437/?pg=2 · visiteur · 390 |  |  |
| 928d14cd30 | UNTRIAGED | A | Bernard · `fr` | unknown fr word in « Julien Bernard julien.bernard @example.com Laboratoire Fictif SA » (8×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 6d3644f982 | UNTRIAGED | A | Big · `fr` | unknown fr word in « Assignez un terme parent pour créer une hiérarchie. Le terme Jazz, par exemple, serait le parent de Bebop et Big Band. » (10×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| d131cec5bb | UNTRIAGED | A | Bruxelles · `fr` | unknown fr word in « Bruxelles » (8×) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 |  |  |
| 2bfdd585bf | UNTRIAGED | A | Camille · `fr` | unknown fr word in « Camille Martin camille.martin @example.com Clinique Exemple » (27×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 89093e003c | UNTRIAGED | A | Chicago · `fr` | unknown fr word in « Chicago, États-Unis » (28×) | http://127.0.0.1:9437/?s_congres=cardiologie&q=cardiologie · visiteur · 390 |  |  |
| b244194340 | UNTRIAGED | A | cjf · `fr` | unknown fr word in « Congrès de relecture 5cjf — exemple — Brouillon » (37×) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 |  |  |
| f81ed77364 | UNTRIAGED | A | cliquez · `fr` | unknown fr word in « Rédigez un congrès puis cliquez sur « Soumettre pour relecture » : la Direction le publie. » (2×) | http://127.0.0.1:9437/wp-admin/index.php · contributeur · 1440 |  |  |
| 05841c4072 | UNTRIAGED | A | diabetologie · `fr` | unknown fr word in « diabetologie » (3×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| d4592e138a | UNTRIAGED | A | Dubois · `fr` | unknown fr word in « Dernière demande : DV-2026-0007 · Claire Dubois (exemple) · Congrès européen de cardiologie — exemple » (52×) | http://127.0.0.1:9437/wp-admin/index.php · direction · 1440 |  |  |
| fa544a2b09 | UNTRIAGED | A | démo · `fr` | unknown fr word in « Bonjour, Direction (démo) » (216×) | http://127.0.0.1:9437/wp-admin/index.php · direction · 1440 |  |  |
| 79d2399517 | UNTRIAGED | A | e-mail · `fr` | unknown fr word in « Toutes les données sont fictives : congrès, personnes, adresses e-mail en @example.com et codes GM&E factices. Aucun e-m » (268×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| 0056431f6e | UNTRIAGED | A | English · `fr` | unknown fr word in « English (United States) » (12×) | http://127.0.0.1:9437/wp-login.php · visiteur · 390 |  |  |
| 5812c2538c | UNTRIAGED | A | equipe · `fr` | unknown fr word in « equipe » (2×) | http://127.0.0.1:9437/wp-admin/profile.php · equipe · 1440 |  |  |
| 71a3afff37 | UNTRIAGED | A | etats-unis · `fr` | unknown fr word in « etats-unis » (3×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_pays&post_type=asset_congres · direction · 1440 |  |  |
| 8e752c7ca7 | UNTRIAGED | A | Events · `fr` | unknown fr word in « Codes tarifaires Air France-KLM Global Meetings & Events (codes fictifs de démonstration). Ils sont chiffrés, masqués pa » (43×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · direction · 1440 |  |  |
| fc422d679f | UNTRIAGED | A | Fresh · `fr` | unknown fr word in « Par défaut Fresh Lumineux Bleu Café Ectoplasme Minuit Océan Lever du soleil » (7×) | http://127.0.0.1:9437/wp-admin/profile.php · direction · 1440 |  |  |
| 32ab34ab54 | UNTRIAGED | A | Genève · `fr` | unknown fr word in « Genève » (8×) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 |  |  |
| f53781ed71 | UNTRIAGED | A | Gravatar · `fr` | unknown fr word in « Vous pouvez changer votre image de profil sur Gravatar. » (7×) | http://127.0.0.1:9437/wp-admin/profile.php · direction · 1440 |  |  |
| 5cedda81a6 | UNTRIAGED | A | hematologie · `fr` | unknown fr word in « hematologie » (3×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| 52941d21c2 | UNTRIAGED | A | https · `fr` | unknown fr word in « https:// » (9×) | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · direction · 1440 |  |  |
| 3364a77802 | UNTRIAGED | A | Hugo · `fr` | unknown fr word in « Hugo Laurent hugo.laurent @example.com Cabinet Exemple » (20×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| cb198efd8f | UNTRIAGED | A | Julien · `fr` | unknown fr word in « Julien Bernard julien.bernard @example.com Laboratoire Fictif SA » (8×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| cee5e6b3de | UNTRIAGED | A | Laurent · `fr` | unknown fr word in « Hugo Laurent hugo.laurent @example.com Cabinet Exemple » (27×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 0cfa4b6797 | UNTRIAGED | A | Lisbonne · `fr` | unknown fr word in « Lisbonne, Portugal » (41×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| 9a6f94bb23 | UNTRIAGED | A | Londres · `fr` | unknown fr word in « Londres, Royaume-Uni » (16×) | http://127.0.0.1:9437/?pg=2 · visiteur · 390 |  |  |
| fdef84ef2c | UNTRIAGED | A | Lyon · `fr` | unknown fr word in « Lyon, France » (63×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| a44677b312 | UNTRIAGED | A | Léa · `fr` | unknown fr word in « Léa Moreau lea.moreau @example.com » (29×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 31e3b2a78a | UNTRIAGED | A | Madrid · `fr` | unknown fr word in « Madrid, Espagne » (51×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| 70771ca71c | UNTRIAGED | A | Marseille · `fr` | unknown fr word in « Marseille, France » (96×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| c6a1da497b | UNTRIAGED | A | Martin · `fr` | unknown fr word in « Camille Martin camille.martin @example.com Clinique Exemple » (151×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| de18a07e4b | UNTRIAGED | A | Moreau · `fr` | unknown fr word in « Léa Moreau lea.moreau @example.com » (30×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 2c05cafe0f | UNTRIAGED | A | multi-fichiers · `fr` | unknown fr word in « Vous utilisez l’outil de téléversement multi-fichiers. Si vous rencontrez des problèmes, essayez plutôt la méthode du na » (5×) | http://127.0.0.1:9437/wp-admin/media-new.php · direction · 1440 |  |  |
| 3411300bd9 | UNTRIAGED | A | Nantes · `fr` | unknown fr word in « Nantes » (22×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 6e2fff1d3a | UNTRIAGED | A | Nice · `fr` | unknown fr word in « Nice » (22×) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 |  |  |
| e6330501ed | UNTRIAGED | A | Oncologie · `fr` | unknown fr word in « Oncologie » (456×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| e72da19c65 | UNTRIAGED | A | Pneumologie · `fr` | unknown fr word in « Pneumologie » (202×) | http://127.0.0.1:9437/ · visiteur · 320 |  |  |
| 8e0eb045b9 | UNTRIAGED | A | Prévisualiser · `fr` | unknown fr word in « Prévisualiser » (9×) | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · direction · 1440 |  |  |
| 4cbfa8bb6c | UNTRIAGED | A | Pseudo · `fr` | unknown fr word in « Pseudo (nécessaire) » (7×) | http://127.0.0.1:9437/wp-admin/profile.php · direction · 1440 |  |  |
| 703c9bb858 | UNTRIAGED | A | recontacte · `fr` | unknown fr word in « Un conseiller ASSET vous recontacte avec une proposition (démonstration : aucun e-mail n’est réellement envoyé). » (3×) | http://127.0.0.1:9437/congres/congres-europeen-de-cardiologie-exemple/?asset_ok=440962b6c0763690303421fe15c390b7#devis · visiteur · 1440 |  |  |
| ebafbff969 | UNTRIAGED | A | rhumatologie · `fr` | unknown fr word in « Congrès de rhumatologie, brouillon — exemple — Brouillon » (86×) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440 |  |  |
| 28bd4dcc83 | UNTRIAGED | A | single-asset · `fr` | unknown fr word in « single-asset_congres » (9×) | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · direction · 1440 |  |  |
| 0ed0b40d6d | UNTRIAGED | A | Slug · `fr` | unknown fr word in « Slug » (32×) | http://127.0.0.1:9437/wp-admin/edit-tags.php?taxonomy=asset_discipline&post_type=asset_congres · direction · 1440 |  |  |
| 056bcfba2d | UNTRIAGED | A | Sophie · `fr` | unknown fr word in « Sophie Dubois sophie.dubois @example.com » (18×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 2903ed7345 | UNTRIAGED | A | States · `fr` | unknown fr word in « English (United States) » (12×) | http://127.0.0.1:9437/wp-login.php · visiteur · 390 |  |  |
| 7db240947d | UNTRIAGED | A | suiteModifier · `fr` | unknown fr word in « Publier tout de suiteModifier » (6×) | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · direction · 1440 |  |  |
| 7c209f75ee | UNTRIAGED | A | Thomas · `fr` | unknown fr word in « Thomas Petit thomas.petit @example.com Groupe hospitalier Exemple » (8×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 387a3d67e1 | UNTRIAGED | A | Toulouse · `fr` | unknown fr word in « Toulouse » (19×) | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · direction · 1440 |  |  |
| 60f21c42c6 | UNTRIAGED | A | téléversement · `fr` | unknown fr word in « Vous utilisez l’outil de téléversement multi-fichiers. Si vous rencontrez des problèmes, essayez plutôt la méthode du na » (10×) | http://127.0.0.1:9437/wp-admin/media-new.php · direction · 1440 |  |  |
| 1c98111fdd | UNTRIAGED | A | Téléverser · `fr` | unknown fr word in « Téléverser un média » (10×) | http://127.0.0.1:9437/wp-admin/media-new.php · direction · 1440 |  |  |
| b9bb97b7c4 | UNTRIAGED | A | United · `fr` | unknown fr word in « English (United States) » (12×) | http://127.0.0.1:9437/wp-login.php · visiteur · 390 |  |  |
| 899b4aa873 | UNTRIAGED | A | web · `fr` | unknown fr word in « Site web » (7×) | http://127.0.0.1:9437/wp-admin/profile.php · direction · 1440 |  |  |
| a2e6f821c1 | UNTRIAGED | A | XML-RPC · `fr` | unknown fr word in « Les mots de passe d’application autorisent l’authentification via des systèmes non-interactifs tels que XML-RPC ou l’API » (7×) | http://127.0.0.1:9437/wp-admin/profile.php · direction · 1440 |  |  |
| a196079f1c | UNTRIAGED | B | Alice · `fr` | unknown fr word in « Alice Martin (exemple) » (11×) | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1/groupe · equipe · 1440 |  |  |
| d1fe5839a3 | UNTRIAGED | B | Ariane · `fr` | unknown fr word in « Fil d’Ariane » (42×) | https://asset-voyages-demo.debanjan186.workers.dev/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |
| 6a118a346f | UNTRIAGED | B | avr · `fr` | unknown fr word in « 13 au 14 avr. 2027 » (33×) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 320 |  |  |
| 032b764ef1 | UNTRIAGED | B | Benali · `fr` | unknown fr word in « Karim Benali, Équipe ASSET : congrès et demandes ; codes GM&E masqués, accès sur demande. » (115×) | https://asset-voyages-demo.debanjan186.workers.dev/console/connexion · visiteur · 390 |  |  |
| 0c28a8448b | UNTRIAGED | B | Bruno · `fr` | unknown fr word in « Bruno Leroy (exemple) » (11×) | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1/groupe · equipe · 1440 |  |  |
| b1f11ffd8d | UNTRIAGED | B | Chloé · `fr` | unknown fr word in « Chloé Petit (exemple) » (11×) | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1/groupe · equipe · 1440 |  |  |
| 943423e38c | UNTRIAGED | B | Durand · `fr` | unknown fr word in « Sophie Durand (exemple) » (9×) | https://asset-voyages-demo.debanjan186.workers.dev/g/twruHve8KdaRoY4dFPkE2iRL4n38WnpDROeWbeF1xXw/merci?d=qludSw0YUJNe.1793958293.eeVVPcb3hXmlBW2VAmMk-B5ht3ydRnRi6TZ_IRlDRpQ · voyageur · 1440 |  |  |
| e84738c66c | UNTRIAGED | B | févr · `fr` | unknown fr word in « 24 au 28 févr. 2027 » (28×) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 320 |  |  |
| cf19ae3b1d | UNTRIAGED | B | Garnier · `fr` | unknown fr word in « Léa Garnier (exemple) » (21×) | https://asset-voyages-demo.debanjan186.workers.dev/console · direction · 1440 |  |  |
| b4de9f91a3 | UNTRIAGED | B | Gastro-entérologie · `fr` | unknown fr word in « Gastro-entérologie » (8×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres/nouveau · contributeur · 1440 |  |  |
| c43e3419e6 | UNTRIAGED | B | Hélène · `fr` | unknown fr word in « Hélène Martin, Direction ASSET : tout, y compris les codes GM&E et les autorisations. » (117×) | https://asset-voyages-demo.debanjan186.workers.dev/console/connexion · visiteur · 390 |  |  |
| b4dfb8e4ce | UNTRIAGED | B | interventionnelle · `fr` | unknown fr word in « Imagerie diagnostique et interventionnelle, intelligence artificielle en radiologie. Fiche d’exemple pour la démonstrati » (2×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres/108 · direction · 1440 |  |  |
| fb2dacaa40 | UNTRIAGED | B | Inès · `fr` | unknown fr word in « Inès Moreau (exemple) » (22×) | https://asset-voyages-demo.debanjan186.workers.dev/console · direction · 1440 |  |  |
| 9ec94c5812 | UNTRIAGED | B | janv · `fr` | unknown fr word in « 28 au 30 janv. 2027 » (72×) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 320 |  |  |
| 37ba5eb062 | UNTRIAGED | B | juil · `fr` | unknown fr word in « 5 au 7 juil. 2027 » (13×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres · direction · 1440 |  |  |
| 6b4c8ad66f | UNTRIAGED | B | Julie · `fr` | unknown fr word in « Julie Roux, contributrice : prépare des brouillons et les soumet à relecture, sans publier. » (23×) | https://asset-voyages-demo.debanjan186.workers.dev/console/connexion · visiteur · 390 |  |  |
| 7729905fa7 | UNTRIAGED | B | Karim · `fr` | unknown fr word in « Karim Benali, Équipe ASSET : congrès et demandes ; codes GM&E masqués, accès sur demande. » (115×) | https://asset-voyages-demo.debanjan186.workers.dev/console/connexion · visiteur · 390 |  |  |
| fb6d96a7a1 | UNTRIAGED | B | Lefebvre · `fr` | unknown fr word in « Paul Lefebvre (exemple) » (21×) | https://asset-voyages-demo.debanjan186.workers.dev/console · direction · 1440 |  |  |
| 9030e169cb | UNTRIAGED | B | Leroy · `fr` | unknown fr word in « Bruno Leroy (exemple) » (11×) | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1/groupe · equipe · 1440 |  |  |
| 1e1e084cc4 | UNTRIAGED | B | Lille · `fr` | unknown fr word in « Départ de Lille 27/01/2027 au 31/01/2027 6 passagers » (52×) | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · direction · 1440 |  |  |
| 8a9a1a46d4 | UNTRIAGED | B | Nathan · `fr` | unknown fr word in « Nathan Roux (exemple) » (22×) | https://asset-voyages-demo.debanjan186.workers.dev/console · direction · 1440 |  |  |
| 63cbe47411 | UNTRIAGED | B | nov · `fr` | unknown fr word in « 13 au 16 nov. 2027 » (15×) | https://asset-voyages-demo.debanjan186.workers.dev/?q=cardiologie · visiteur · 390 |  |  |
| 015190111f | UNTRIAGED | B | oct · `fr` | unknown fr word in « 29 sept. au 2 oct. 2027 » (28×) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 320 |  |  |
| 8ad38e8d29 | UNTRIAGED | B | Paul · `fr` | unknown fr word in « Paul Lefebvre (exemple) » (21×) | https://asset-voyages-demo.debanjan186.workers.dev/console · direction · 1440 |  |  |
| 5cf3422791 | UNTRIAGED | B | Pharo · `fr` | unknown fr word in « Palais du Pharo — exemple » (10×) | https://asset-voyages-demo.debanjan186.workers.dev/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |
| df5b8dd32f | UNTRIAGED | B | Réf · `fr` | unknown fr word in « Réf. » (24×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres · contributeur · 1440 |  |  |
| b9074fd554 | UNTRIAGED | B | Urologie · `fr` | unknown fr word in « Urologie » (8×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres/nouveau · contributeur · 1440 |  |  |
| ecfc90db07 | UNTRIAGED | B | yyd · `fr` | unknown fr word in « Congrès de relecture 8yyd — exemple » (8×) | https://asset-voyages-demo.debanjan186.workers.dev/console/congres/114?ok=cree-review · contributeur · 1440 |  |  |
| a983ea8af0 | UNTRIAGED | HUB | add-ons · `en` | unknown en word in « The version of today’s site, its add-ons and any custom code. » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| a510a3ac69 | UNTRIAGED | HUB | admin · `en` | unknown en word in « Open the admin, signed in » (120×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| 86e26dd8e9 | UNTRIAGED | HUB | agences · `en` | unknown en word in « “Plus de 122 agences”. The Selectour Affaires figure on your site is undated. Your brief asks for claims to be checked b » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| da934ca5b7 | UNTRIAGED | HUB | Analytics · `en` | unknown en word in « Cloudflare Web Analytics » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 436eb09a19 | UNTRIAGED | HUB | anti-spam · `fr` | unknown fr word in « L’envoi des formulaires. Les formulaires valident et confirment à l’écran, sans rien envoyer ; en production : enregistr » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 985de3f6f8 | UNTRIAGED | HUB | app · `en` | unknown en word in « Two-step login for staff, only for named work email addresses: either your work email account (Microsoft 365 or Google W » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| db270e774c | UNTRIAGED | HUB | Approx · `en` | unknown en word in « Approx. per month » (4×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 1280 |  |  |
| 4f2709d3b6 | UNTRIAGED | HUB | Aujourd · `fr` | unknown fr word in « Aujourd’hui / concept » (48×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 4ca77c2e7d | UNTRIAGED | HUB | authorised · `en` | unknown en word in « Only if you lack authorised photos. Example: a stock-photo plan with 10 images a month » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 405af55135 | UNTRIAGED | HUB | Brevo · `en` | unknown en word in « Brevo (French), backup Resend » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| a077631d50 | UNTRIAGED | HUB | brief · `fr` | unknown fr word in « 01 Le brief » (88×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| aee985bdd9 | UNTRIAGED | HUB | clics · `fr` | unknown fr word in « Dans la maquette : toutes les offres et tous les formulaires accessibles sans quitter la page, en 1 à 2 clics depuis le  » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 990a5629af | UNTRIAGED | HUB | cliquable · `fr` | unknown fr word in « Une maquette cliquable de la refonte d’asset-voyagesdaffaires.com, construite à partir de votre consultation (version 0. » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| a9f0a4438b | UNTRIAGED | HUB | colours · `en` | unknown en word in « 10Do you have brand guidelines (logo files, colours, fonts)? Is the logo fixed, or is a light refresh welcome? » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d0677a7231 | UNTRIAGED | HUB | Commons · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 7c2d19da00 | UNTRIAGED | HUB | Connexion · `en` | unknown en word in « Client login. Your current client area says “Connexion Traveldoo”, while the brief mentions Wondermiles. Is Wondermiles  » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 1bb5eee6df | UNTRIAGED | HUB | Directus · `en` | unknown en word in « The alternative. A ready-made content editor such as Directus, installed on a rented server. It is a sound product and w » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 69bb595528 | UNTRIAGED | HUB | docx · `en` | unknown en word in « Word version (.docx) » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 9a9942af1f | UNTRIAGED | HUB | déc · `fr` | unknown fr word in « oct. – déc. 2027 » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| e2fe4abe60 | UNTRIAGED | HUB | démos · `fr` | unknown fr word in « Offres Congrès Contact Note pour ASSET Nos questions Les deux démos Haut de page ↑ » (16×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 20bd825f00 | UNTRIAGED | HUB | Eiffel · `fr` | unknown fr word in « Panorama de Paris avec la tour Eiffel et le dôme des Invalides » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 04ccf1fde6 | UNTRIAGED | HUB | export · `fr` | unknown fr word in « L’envoi des formulaires. Les formulaires valident et confirment à l’écran, sans rien envoyer ; en production : enregistr » (24×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 0129ae2dc7 | UNTRIAGED | HUB | fillable · `en` | unknown en word in « Download the answer sheet (fillable PDF) » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 2ad01bb712 | UNTRIAGED | HUB | filtrable · `fr` | unknown fr word in « Catalogue filtrable, fiche par congrès, devis vol pré-rempli ; les statuts internes ne sont jamais affichés » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| f9fcd20efd | UNTRIAGED | HUB | Gandi · `en` | unknown en word in « Estimates, prices checked 28 October 2026, excluding VAT, paid to the providers, not to us. The domain name, hosting and » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d3eb0002ea | UNTRIAGED | HUB | Google · `fr` | unknown fr word in « Un concept publié à une adresse de test, non référencé : il n’apparaît pas sur Google et n’est lié depuis aucun site pub » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| ceaa94d7ac | UNTRIAGED | HUB | Géolocalisation · `fr` | unknown fr word in « Géolocalisation » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| b1a73ecca2 | UNTRIAGED | HUB | HubSpot · `en` | unknown en word in « Only if you choose one. Free plans exist (HubSpot: free for up to 2 users); paid plans start around $7–20 per user » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 4c17c972cd | UNTRIAGED | HUB | import · `fr` | unknown fr word in « L’administration réelle. La Console est une maquette : gestion des pages, rôles, import de tableur, versions et journal  » (16×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| a7d1734a0c | UNTRIAGED | HUB | incentive · `fr` | unknown fr word in « Séminaire, incentive, groupe » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 41ed136c8e | UNTRIAGED | HUB | incentives · `fr` | unknown fr word in « MICE · séminaires, incentives, groupes » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| b4e343d038 | UNTRIAGED | HUB | Issy-les-Moulineaux · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (24×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 1c3f7e679f | UNTRIAGED | HUB | Khatri · `fr` | unknown fr word in « ASSET Voyages — direction, et Mme Veena Khatri (coordination) » (72×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 7c2d22d04e | UNTRIAGED | HUB | Khatri · `en` | unknown en word in « ASSET Voyages management, and Ms Veena Khatri (coordination) » (128×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d4dbd57bdd | UNTRIAGED | HUB | LinkedIn · `en` | unknown en word in « 7Could you give us read-only access to Google Analytics and Search Console? Which trackers (LinkedIn, Meta) and ad campa » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 075fc43d13 | UNTRIAGED | HUB | logins · `en` | unknown en word in « The console asks you to sign in with one of the logins below. » (16×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| aabf7528dc | UNTRIAGED | HUB | Mme · `fr` | unknown fr word in « ASSET Voyages — direction, et Mme Veena Khatri (coordination) » (72×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| b444046a9b | UNTRIAGED | HUB | multi-segments · `fr` | unknown fr word in « « […] nous trouvons la meilleure combinaison tarifaire pour les billets complexes, comme les multi-segments ou les tours » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2256cbea37 | UNTRIAGED | HUB | PME-PMI · `fr` | unknown fr word in « Nous proposons aux PME-PMI ainsi qu’aux TPE des solutions sur mesure pour gérer et optimiser vos déplacements profession » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2e5af2964e | UNTRIAGED | HUB | PME-TPE · `fr` | unknown fr word in « Offre PME-TPE » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 652be275ad | UNTRIAGED | HUB | programme · `en` | unknown en word in « 18 Answer first Does ASSET already work with Air France–KLM’s Global Meetings and Events programme? How do the event cod » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 8596de7d32 | UNTRIAGED | HUB | reporting · `fr` | unknown fr word in « « Un reporting complet et personnalisé des voyages d’affaires de vos collaborateurs. » » (16×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 18a9e03df8 | UNTRIAGED | HUB | revérifier · `fr` | unknown fr word in « « Avec plus de 122 agences et plateaux d’affaires en France, Selectour Affaires constitue le premier réseau dédié aux vo » (12×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 964998c528 | UNTRIAGED | HUB | screenshots · `en` | unknown en word in « 24Who is your contact at Wondermiles? What may we show about Wondermiles on the “Digital solutions” page (logo, screensh » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d13aa551a7 | UNTRIAGED | HUB | searchable · `en` | unknown en word in « The congress catalogue is the biggest new value. It does not exist today. A searchable list, one page per congress, and  » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 41aa2d93bd | UNTRIAGED | HUB | Selectour · `fr` | unknown fr word in « ASSET Voyages est une agence de voyages d’affaires à taille humaine, membre du réseau Selectour Affaires. » (48×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 8c9b9f6d01 | UNTRIAGED | HUB | Selectour · `en` | unknown en word in « “Plus de 122 agences”. The Selectour Affaires figure on your site is undated. Your brief asks for claims to be checked b » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 85d360ce07 | UNTRIAGED | HUB | Smart · `fr` | unknown fr word in « Domaine actuel asset-voyagesdaffaires.com, alors que la consultation cite www.assetvoyages.com · l’espace client actuel  » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 9ea38c843c | UNTRIAGED | HUB | Sojka · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| ea323b163a | UNTRIAGED | HUB | Stabilisation · `en` | unknown en word in « Stabilisation » (8×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| 7912aa51f0 | UNTRIAGED | HUB | Timbaud · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (20×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 59809ee364 | UNTRIAGED | HUB | travel · `fr` | unknown fr word in « PME · TPE · travel managers » (16×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 6b96abe794 | UNTRIAGED | HUB | Traveldoo · `fr` | unknown fr word in « Domaine actuel asset-voyagesdaffaires.com, alors que la consultation cite www.assetvoyages.com · l’espace client actuel  » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| b53d86d63d | UNTRIAGED | HUB | Traveldoo · `en` | unknown en word in « Client login. Your current client area says “Connexion Traveldoo”, while the brief mentions Wondermiles. Is Wondermiles  » (32×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 0d34ecfd61 | UNTRIAGED | HUB | UptimeRobot · `en` | unknown en word in « UptimeRobot » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 22e8028f7b | UNTRIAGED | HUB | Veena · `fr` | unknown fr word in « ASSET Voyages — direction, et Mme Veena Khatri (coordination) » (16×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 2b75701f23 | UNTRIAGED | HUB | Veena · `en` | unknown en word in « ASSET Voyages management, and Ms Veena Khatri (coordination) » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d13d2796ee | UNTRIAGED | HUB | Voyagesdemos · `en` | unknown en word in « ASSET Voyagesdemos prepared by ProdCraft » (5×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 768 |  |  |
| c21afe556f | UNTRIAGED | HUB | Wikimedia · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 8f491514f4 | UNTRIAGED | HUB | Wireframes · `en` | unknown en word in « Wireframes (page outlines), then desktop and mobile mock-ups, with two rounds of changes at each stage. » (8×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| d700817d62 | UNTRIAGED | HUB | Wladyslaw · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 9699a48c82 | UNTRIAGED | HUB | Wondermiles · `fr` | unknown fr word in « Domaine actuel asset-voyagesdaffaires.com, alors que la consultation cite www.assetvoyages.com · l’espace client actuel  » (16×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 06a9867f09 | UNTRIAGED | HUB | Wondermiles · `en` | unknown en word in « Ready for later, not dependent on it. Links with Wondermiles or Air France–KLM can come later. The launch must not wait  » (96×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 500d481425 | UNTRIAGED | HUB | Word · `fr` | unknown fr word in « Vos réponses écrites aux 30 questions (page en anglais, section 08), sur la fiche de réponses à télécharger (PDF à rempl » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |

### B6

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| e18336fe3d | UNTRIAGED | A | ask for access | none of « Demander l’accès / Demander l'accès » seen in the A UI | glossary · visiteur ·  |  |  |
| de4f377ae3 | UNTRIAGED | A | sign out | none of « Se déconnecter » seen in the A UI | glossary · visiteur ·  |  |  |
| d881e388fd | UNTRIAGED | A+B | add a congress: A « Ajouter un congrès » vs B « Nouveau congrès / Ajouter » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| 1c7ffad3d7 | UNTRIAGED | A+B | notification log: A « Journal des notifications » vs B « Notifications » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| 27d9b4cdf8 | UNTRIAGED | A+B | quote form title: A « Demander un devis vol » vs B « Demande de devis vol » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| 1169251339 | UNTRIAGED | A+B | send the enquiry: A « Envoyer ma demande » vs B « Envoyer la demande » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| adb31744d2 | UNTRIAGED | A+B | approve: A « Approuver (24 h) / Approuver » vs B « Approuver pour 24 h » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| 99ca0dfeeb | UNTRIAGED | A+B | show the code: A « Révéler le code » vs B « Afficher le code » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| ef8ada7fbb | UNTRIAGED | A+B | access log: A « Journal GM&E » vs B « Journal / Journal d’accès » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |
| cbe795aa72 | UNTRIAGED | A+B | CSV export: A « Exporter en CSV » vs B « Exporter (tableur CSV) / Exporter » | the same thing has different names in the two demos | glossary · visiteur ·  |  |  |

### C1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| cbc5449331 | UNTRIAGED | A | 400 xhr http://127.0.0.1:9437/wp-admin/admin-ajax.php?action=wp-compression-test&test=no&_ajax_nonce=60e8541146&1793955755359 · `http` | during C10 T5.2 | http://127.0.0.1:9437/wp-admin/admin-ajax.php?action=wp-compression-test&test=no&_ajax_nonce=60e8541146&1793955755359 · direction · 1440 |  |  |
| 718fab98c8 | UNTRIAGED | A | Failed to load resource: the server responded with a status of 400 (Bad Request) · `console` | during C10 T5.2 | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · direction · 1440 |  |  |
| 249472ba92 | UNTRIAGED | A | 403 document http://127.0.0.1:9437/wp-admin/edit.php?post_type=page · `http` | during errors | http://127.0.0.1:9437/wp-admin/edit.php?post_type=page · equipe · 1440 |  |  |
| 41408b82ae | UNTRIAGED | A | Failed to load resource: the server responded with a status of 403 (Forbidden) · `console` | during errors | http://127.0.0.1:9437/wp-admin/edit.php?post_type=page · equipe · 1440 |  |  |
| 70c1f4b91b | UNTRIAGED | A | 400 xhr http://127.0.0.1:9437/wp-admin/admin-ajax.php?action=wp-compression-test&test=2&_ajax_nonce=d71a4edec6&1793956019720 · `http` | during equipe 390 http://127.0.0.1:9437/wp-admin/index.php | http://127.0.0.1:9437/wp-admin/admin-ajax.php?action=wp-compression-test&test=2&_ajax_nonce=d71a4edec6&1793956019720 · equipe · 390 |  |  |
| 0372fa5378 | UNTRIAGED | A | Failed to load resource: the server responded with a status of 400 (Bad Request) · `console` | during equipe 390 http://127.0.0.1:9437/wp-admin/index.php | http://127.0.0.1:9437/wp-admin/profile.php · equipe · 390 |  |  |

### C3

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 5596fce01e | UNTRIAGED | A | 938×25 px empty · `div#titlediv > div.inside` | visible container with no text or media | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · direction · 1440 (5×) | out/shots/0034-A-direction-1440-C10-T1-2.png |  |
| 831a239966 | UNTRIAGED | A | 1062×25 px empty · `div#titlediv > div.inside` | visible container with no text or media | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · equipe · 1440 | out/shots/0067-A-equipe-1440-equipe-wp-admin-post-new-php-post-type-asset-congres.png |  |
| 237f45724a | UNTRIAGED | A | 368×25 px empty · `div#titlediv > div.inside` | visible container with no text or media | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · contributeur · 390 (3×) | out/shots/0096-A-contributeur-390-contributeur-390-wp-admin-post-new-php-post-type-asset-congr.png |  |

### C4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 0e5b7b4e16 | UNTRIAGED | A | CLS 0.048 · `DIV.drag-drop-inside+P.upload-flash-bypass+P.max-upload-size@1341ms=0.0482` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/media-new.php · direction · 1440 (2×) | out/shots/0038-A-direction-1440-direction-wp-admin-media-new-php.png |  |
| 991ff4bac4 | UNTRIAGED | A | CLS 0.030 · `DIV.asset-cols+TABLE.widefat.striped+P@2990ms=0.0298` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes&action=view&id=41 · equipe · 1440 | out/shots/0061-A-equipe-1440-C10-T4-2.png |  |
| 11e7fc2ddd | UNTRIAGED | A | CLS 0.059 · `DIV.drag-drop-inside+P.upload-flash-bypass+P.max-upload-size@1522ms=0.0585` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/media-new.php · equipe · 1440 | out/shots/0065-A-equipe-1440-equipe-wp-admin-media-new-php.png |  |
| 5377bcd715 | UNTRIAGED | A | CLS 0.022 · `DIV.wrap@2837ms=0.022` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/index.php?msg=approve · direction · 1440 | out/shots/0075-A-direction-1440-C10-T5-2.png |  |
| 79444b1878 | UNTRIAGED | A | CLS 0.021 · `TABLE.widefat.striped+P.description@1589ms=0.0215` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · equipe · 1440 | out/shots/0089-A-equipe-1440-C10-T5-3.png |  |
| da5b63ffbf | UNTRIAGED | A | CLS 0.070 · `TEXTAREA#content.wp-editor-area+DIV#submitdiv.postbox+TABLE#post-status-info@365` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · contributeur · 390 | out/shots/0096-A-contributeur-390-contributeur-390-wp-admin-post-new-php-post-type-asset-congr.png |  |
| 5280834967 | UNTRIAGED | A | CLS 0.061 · `TEXTAREA#content.wp-editor-area+DIV#submitdiv.postbox+DIV.inside@2488ms=0.061` | layout shift above 0.02 | http://127.0.0.1:9437/wp-admin/post-new.php?post_type=asset_congres · equipe · 390 (2×) | out/shots/0102-A-equipe-390-equipe-390-wp-admin-post-new-php-post-type-asset-congres.png |  |

### C5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 59adcfb4bd | UNTRIAGED | A-admin | -apple-system \| radius 2px (login page «  »); -apple-system \| radius 0px (C10 T1.1 « Options de l’écran »); dashicons \| radius 2px (C10 T1.2 | 3 button style families | A-admin · visiteur ·  |  |  |
| 58df5f7ea0 | UNTRIAGED | A-public | hue 30 (catalogue button « Rechercher » rgb(154, 71, 5)); hue 210 (search zero link rgb(13, 48, 72)) | 2 accent colours | A-public · visiteur ·  |  |  |
| 41b4bf5573 | UNTRIAGED | B-console | EB Garamond (login page); Inter (direction /console/notifications) | 2 display font families | B-console · visiteur ·  |  |  |
| af434992f4 | UNTRIAGED | hub | Inter \| radius 4px (hub/demo/ « Open the demos »); ui-monospace \| radius 4px (hub/ « ESPACE CLIENT »); Inter \| radius 2px (hub/ « Parler à u | 4 button style families | hub · visiteur ·  |  |  |

### C7

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 7897250496 | UNTRIAGED | A | Se connecter \| Propulsé par WordPress \| Identifiant ou adresse e-mail  | after the session ends the reader lands on the login page with no « Session expirée » message | http://127.0.0.1:9437/wp-login.php?redirect_to=http%3A%2F%2F127.0.0.1%3A9437%2Fwp-admin%2Fadmin.php%3Fpage%3Dasset-demandes&reauth=1 · equipe · 1440 | out/shots/0091-A-direction-1440-C7-expired-session-admin-reload.png |  |
| ec6902d336 | UNTRIAGED | B | Aller au contenu \| ASSET \| Voyages \| Démonstration avec des données fictives | after the session ends, a form sent from an open tab shows no « Session expirée » message | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/6 · equipe · 390 | out/shots/0174-B-equipe-390-C7-expired-session-stale-form-submitted.png |  |
| aa7b325632 | UNTRIAGED | B | Aller au contenu \| ASSET \| Voyages | session cookie __Host-av_session gone: the reader is sent to the login page with no « Session expirée » message | https://asset-voyages-demo.debanjan186.workers.dev/console/connexion?next=%2Fconsole%2Fdemandes · equipe · 390 | out/shots/0175-B-equipe-390-C7-expired-session-next-navigation.png |  |
| 4005f28b67 | UNTRIAGED | B | SELECT id FROM sandboxes WHERE created_at < ?1 ORDER BY created_at LIMIT ${PURGE_SANDBOXES} · `source` | the 03:00 UTC purge selects sandboxes CREATED more than 24 h ago, not sandboxes IDLE for more than 24 h: a trial in use at 03:00 is wiped if it started the day before | custom_demo/src/data.js:298 · visiteur ·  |  |  |
| 751798daf3 | UNTRIAGED | HUB |   Same requirements, fictional data and codes, sandboxes that reset themselves. | the hub does not say that each trial is private | demo/ · visiteur ·  |  |  |
| ffdd3e5a8b | UNTRIAGED | HUB |   Same requirements, fictional data and codes, sandboxes that reset themselves. | the hub does not say the trial is reset after 24 h | demo/ · visiteur ·  |  |  |

### C9

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 895b50665f | UNTRIAGED | A | Test de lecture. · `table.widefat.striped > tbody > tr > td` | test: « Test » | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme-acces · direction · 1440/390 (6×) | out/shots/0046-A-direction-1440-direction-wp-admin-admin-php-page-asset-gme-acces.png |  |

### C10

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 15ea91caac | UNTRIAGED | A | T4 step 3: Export the list as a spreadsheet file (CSV). « Journal des notifications » shows the message your team would have received. · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-demandes · equipe · 1440 | out/shots/0062-A-equipe-1440-C10-T4-3.png |  |
| 5292925de5 | UNTRIAGED | A | T5 step 1: Signed in as equipe, open « Accès GM&E »: the codes are hidden. Ask for access and give a reason. · `instruction replay` | no reason field | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · equipe · 1440 | out/shots/0074-A-equipe-1440-C10-T5-1.png |  |
| 795bc19783 | UNTRIAGED | A | T5 step 3: Sign in as equipe again: the code is shown, and the access record lists it. · `instruction replay` | hub says « the code is shown » after signing in; the reader must still click « Révéler le code » | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · equipe · 1440 | out/shots/0089-A-equipe-1440-C10-T5-3.png |  |
| bcc4c7a2cc | UNTRIAGED | B | T5 step 1: In the team console, sign in as equipe and open « Codes GM&E »: the codes are hidden. Ask for access and give a reason. · `instruction replay` | hub label « Codes GM&E »: label « Codes GM&E » is visible (p) but is not a link or a button | https://asset-voyages-demo.debanjan186.workers.dev/console/gme?ok=demande · equipe · 1440 | out/shots/0117-B-equipe-1440-C10-T5-1.png |  |
| eea018a792 | UNTRIAGED | B | T5 step 3: Sign in as equipe again: the code is shown, and the access record lists it. · `instruction replay` | hub says « the code is shown » after signing in; the reader must still click « Afficher le code » | https://asset-voyages-demo.debanjan186.workers.dev/console/gme/112/afficher · equipe · 1440 | out/shots/0120-B-equipe-1440-C10-T5-3.png |  |

### D1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| e6cce1fcd8 | UNTRIAGED | A | 4. Receive, view, track and update enquiries: Works in the demo Statuses, history of changes, export to a spreadsheet (CSV). · `table.cmp` | this run: C10 T4 FAIL · wp_demo/README.md: S4-F1, S4-F2, S4-F3, S4-F4, S4-F5, S4-F6, S4-E1, S4-H1 | demo/#compare · visiteur ·  |  |  |
| b551d64dd6 | UNTRIAGED | A | 5. GM&E codes protected: Works in the demo Codes hidden, access asked with a reason, 24-hour approval, a  · `table.cmp` | this run: C10 T5 FAIL · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 | demo/#compare · visiteur ·  |  |  |
| de74d55922 | UNTRIAGED | A | Editing all the site’s pages: Works in the demo The standard WordPress page editor; your current pages are mov · `table.cmp` | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP 403 · no earlier test ID in wp_demo/README.md | demo/#compare · visiteur ·  |  |  |
| 9266a5db64 | UNTRIAGED | B | Works in the Option B demo | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») | demo/#group · visiteur ·  |  |  |

### D2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| a143491658 | UNTRIAGED | A | Congrès européen de radiologie — exemple · `div.asset-cd.asset-catalogue > ul.asset-grid > li.asset-card > h2.asset-card__ti` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://127.0.0.1:9437/ · visiteur · 390/1440 (24×) | out/shots/0003-A-visiteur-390-catalogue.png |  |
| 889783e068 | UNTRIAGED | A | Modifier « Congrès européen de radiologie — exemple » · `th.title.column-title > div.row-actions > span.edit > a` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440/390 (6×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| a3a1bac465 | UNTRIAGED | A | Modifier rapidement « Congrès européen de radiologie — exemple » en ligne · `th.title.column-title > div.row-actions > span.inline.hide-if-no-js > button.but` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440/390 (6×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| 6df04364bc | UNTRIAGED | A | Déplacer « Congrès européen de radiologie — exemple » dans la corbeille · `th.title.column-title > div.row-actions > span.trash > a.submitdelete` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440/390 (6×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| a6f8af3819 | UNTRIAGED | A | Afficher « Congrès européen de radiologie — exemple » · `th.title.column-title > div.row-actions > span.view > a` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://127.0.0.1:9437/wp-admin/edit.php?post_type=asset_congres · direction · 1440/390 (8×) | out/shots/0035-A-direction-1440-C10-T1-3.png |  |
| b7d50bc29e | UNTRIAGED | A-hosted | Congrès européen de radiologie — exemple · `div.asset-cd.asset-catalogue > ul.asset-grid > li.asset-card > h2.asset-card__ti` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://wpsandbox.wordpress.net/scope:ttxa-uyim-tjij/ · visiteur · 1440 | out/shots/0146-A-hosted-visiteur-1440-hosted-visitor-first-screen.png |  |
| ed34769f19 | UNTRIAGED | B | Congrès européen de radiologie — exemple · `li.row > a.row__a > span.row__main > span.row__t` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 390/1440 (33×) | out/shots/0043-B-visiteur-390-catalogue.png |  |
| c3cf241814 | UNTRIAGED | B | Congrès mondial de neurologie — exemple · `li.row > a.row__a > span.row__main > span.row__t` | matches a real congress name « congres mondial de neurologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/ · visiteur · 390/1440 (11×) | out/shots/0043-B-visiteur-390-catalogue.png |  |
| 366f3a475a | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0006 Congrès : Congrès international d’oncologie — exemple (C · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 06 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| 758a709e2b | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0005 Congrès : Rencontres d’ophtalmologie — exemple (CG-0107) · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 05 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| 25aa23b767 | UNTRIAGED | B | Nouvelle demande DV-2026-0004 : Congrès européen de radiologie — exemple · `main#main > ol.mails > li.card.mail > h2.h4` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| 9d67d05a8a | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0004 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 04 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| d729e5e7e8 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0004 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| 4128df0104 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0003 Congrès : Congrès européen de cardiologie — exemple (CG- · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 03 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| add580994c | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0002 Congrès : Journées françaises de diabétologie — exemple  · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 02 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| dcd5757ebb | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0001 Congrès : Journées d’oncologie digestive — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 01 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · direction · 1440/390 (5×) | out/shots/0096-B-direction-1440-direction-console-notifications.png |  |
| 40ad4ededf | UNTRIAGED | B | 01 23 45 67 03 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 03 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/3 · direction · 1440 | out/shots/0102-B-direction-1440-direction-console-demandes-3.png |  |
| d9c61236fd | UNTRIAGED | B | 01 23 45 67 01 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 01 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/1 · equipe · 1440/390 (2×) | out/shots/0121-B-equipe-1440-C10-G-1.png |  |
| b2d6ade1c6 | UNTRIAGED | B | E-mail : Cette adresse e-mail n’est pas valide (exemple : prenom.nom@societe.fr). · `div#form-errors > ul > li` | real-looking e-mail « prenom.nom@societe.fr » | https://asset-voyages-demo.debanjan186.workers.dev/demande · visiteur · 390 | out/shots/0159-B-visiteur-390-enquiry-errors-390.png |  |
| 0f9810b903 | UNTRIAGED | B | Congrès européen de radiologie — exemple, 24 au 28 févr. 2027 · `aside#demande > form.form > div.field.field--full > p.form__cg-v` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/demande · visiteur · 390 | out/shots/0159-B-visiteur-390-enquiry-errors-390.png |  |
| d8d07bb291 | UNTRIAGED | B | Cette adresse e-mail n’est pas valide (exemple : prenom.nom@societe.fr). · `p#f-email-e` | real-looking e-mail « prenom.nom@societe.fr » | https://asset-voyages-demo.debanjan186.workers.dev/demande · visiteur · 390 | out/shots/0159-B-visiteur-390-enquiry-errors-390.png |  |
| d4567b5cf3 | UNTRIAGED | B | Demande de devis vol pour Congrès européen de radiologie — exemple. Un conseiller ASSET vous recontacte avec une proposition ; gardez cette  · `main#main > section.thanks > p` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/demande/confirmation?ref=DV-2026-0007&k=-SBJreGT73heuu4jBTu4dW · visiteur · 390 | out/shots/0160-B-visiteur-390-enquiry-confirmation-390.png |  |
| f5a5a12b6f | UNTRIAGED | B | Nouvelle demande DV-2026-0007 : Congrès européen de radiologie — exemple · `main#main > ol.mails > li.card.mail > h2.h4` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · equipe · 390 (2×) | out/shots/0169-B-equipe-390-equipe-390-console-notifications.png |  |
| 127fb4fb39 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0007 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-demo.debanjan186.workers.dev/console/notifications · equipe · 390 (2×) | out/shots/0169-B-equipe-390-equipe-390-console-notifications.png |  |
| abee61f38a | UNTRIAGED | B | 01 23 45 67 06 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 06 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/6 · equipe · 390 | out/shots/0173-B-equipe-390-equipe-console-demandes-6-390.png |  |
| 760a3afa82 | UNTRIAGED | HUB | Congrès européen de radiologie — exemple · `ul.rows > li.row > div > p.row__t` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (8×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| 8722218e55 | UNTRIAGED | HUB | Congrès mondial de neurologie — exemple · `ul.rows > li.row > div > p.row__t` | matches a real congress name « congres mondial de neurologie » (marked as an example in the same text) | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (4×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| 4fd467697d | UNTRIAGED | HUB | 01 55 57 29 00 · `section#contact > div.contact__grid > div.contact__side` | phone « 01 55 57 29 00 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (4×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| 04559125b8 | UNTRIAGED | HUB | 58, rue Jean-Pierre Timbaud 92130 Issy-les-Moulineaux 01 55 57 29 00 · `footer.ftr > div > p` | phone « 01 55 57 29 00 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (4×) | out/shots/0007-HUB-visiteur-390-hub.png |  |

### D3

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 9e825e84b8 | UNTRIAGED | HUB | five · ` which then wait for review ⏎ 2 Try it in ⟨five⟩ minutes ⏎  ⏎ Your five requirem` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |

### D4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| b0d269a16f | UNTRIAGED | A | DEMO-GME-XXXX · `DOM (text/attributes/inputs)` | GM&E code present without an approved reveal | http://127.0.0.1:9437/wp-admin/admin.php?page=asset-gme · direction · 1440/390 (3×) | out/shots/0045-A-direction-1440-direction-wp-admin-admin-php-page-asset-gme.png |  |

## C10 instruction replay

| Option | Task.step | OK | Clicks | Role | Why | Hub text |
|---|---|---|---|---|---|---|
| A | T1.1 | yes | 1 | direction | local: signed in as direction through wp-login (hosted link checked separately) | Open the admin. You are already signed in. |
| A | T1.2 | yes | 2 | direction |  | In the left-hand menu, choose « Congrès », then « Ajouter un congrès ». |
| A | T1.3 | yes | 2 | direction |  | Fill in the name, dates, city and discipline, then publish. To change one, open it from « Tous les congrès ». |
| A | T1.tip | yes | 0 | contributeur |  | Sign in as contributeur instead and your congress waits for review before it goes live. |
| A | T2.1 | yes | 0 | visiteur | local: visitor site root | Open the visitor site and go to the congress catalogue. |
| A | T2.2 | yes | 1 | visiteur |  | Type a word in the search box, or narrow the list by discipline, country or month. |
| A | T2.3 | yes | 1 | visiteur |  | Open a congress to see its details page: dates, city, venue and discipline. |
| A | T3.1 | yes | 0 | visiteur |  | On a congress details page, find « Demander un devis vol ». |
| A | T3.2 | yes | 0 | visiteur |  | Enter your contact details, departure city, travel dates and number of passengers. |
| A | T3.3 | yes | 1 | visiteur |  | Send it. You receive a reference number on screen. |
| A | T4.1 | yes | 3 | equipe |  | In the same tab as task 3, click « Espace équipe » and sign in as equipe. Open « Demandes »: your enquiry is at the top. |
| A | T4.2 | yes | 3 | equipe |  | Open it and change its status, for example from « Nouvelle » to « Qualifiée ». Each change is kept in its history. |
| A | T4.3 | NO | 2 | equipe | exception: locator.click: Timeout 5000ms exceeded. | Export the list as a spreadsheet file (CSV). « Journal des notifications » shows the message your team would have received. |
| A | T5.1 | NO | 1 | equipe | no reason field | Signed in as equipe, open « Accès GM&E »: the codes are hidden. Ask for access and give a reason. |
| A | T5.2 | yes | 3 | direction |  | Sign out, sign in as direction, and approve for 24 hours or refuse. |
| A | T5.3 | NO | 4 | equipe | hub says « the code is shown » after signing in; the reader must still click « Révéler le code » | Sign in as equipe again: the code is shown, and the access record lists it. |
| B | T1.1 | yes | 1 | contributeur |  | Open the team console and sign in as contributeur. |
| B | T1.2 | yes | 2 | contributeur |  | Open the list of congresses and add a new one, or open an existing one to change it. |
| B | T1.3 | yes | 6 | direction |  | Send it for review. Sign in as direction to check it and publish it. |
| B | T2.1 | yes | 1 | direction |  | Open the visitor site and go to the congress catalogue. |
| B | T2.2 | yes | 1 | direction |  | Type a word in the search box, or narrow the list by discipline, country or month. |
| B | T2.3 | yes | 1 | direction |  | Open a congress to see its details page: dates, city, venue and discipline. |
| B | T3.1 | yes | 0 | direction | form already open on the page (0 clicks) | On a congress details page, open the flight enquiry form. |
| B | T3.2 | yes | 0 | direction |  | Enter your contact details, departure city, travel dates and number of passengers. |
| B | T3.3 | yes | 1 | direction |  | Send it. You receive a reference number on screen. |
| B | T4.1 | yes | 2 | equipe |  | Open the team console, sign in as equipe and open the enquiries. |
| B | T4.2 | yes | 2 | equipe |  | Open your enquiry from task 3 and change its status. Each change is kept in its history. |
| B | T4.3 | yes | 3 | equipe | CSV demandes-2026-11-06.csv | Export the list as a spreadsheet file (CSV), and see the log of notifications your team would have received. |
| B | T5.1 | NO | 2 | equipe | hub label « Codes GM&E »: label « Codes GM&E » is visible (p) but is not a link or a button | In the team console, sign in as equipe and open « Codes GM&E »: the codes are hidden. Ask for access and give a reason. |
| B | T5.2 | yes | 4 | direction |  | Sign out, sign in as direction, and approve for 24 hours or refuse. |
| B | T5.3 | NO | 4 | equipe | hub says « the code is shown » after signing in; the reader must still click « Afficher le code » | Sign in as equipe again: the code is shown, and the access record lists it. |
| B | G.1 | yes | 0 | equipe |  | Open enquiry DV-2026-0001 in the Option B console (new tab) and sign in as equipe, password demo-asset. |
| B | G.2 | yes | 1 | equipe |  | Choose the « Groupe » tab. Three fictional travellers have already answered. |
| B | G.3 | yes | 1 | equipe |  | Under « Lien de groupe », copy the link and open it in another tab. This is the traveller’s page. |
| B | G.4 | yes | 0 | equipe |  | Send an answer, then go back to the « Groupe » tab: it is in the list. |

## D1 claims

| Function | Option | Cell | OK | Evidence |
|---|---|---|---|---|
| 1. Create and edit congresses | A | Works in the demo In the standard WordPress editor, with review before | yes | this run: C10 T1 functional PASS · wp_demo/README.md: S1-F1, S1-F2, S1-F3, S1-E1, S1-E2, S1-H1, S1-H2 |
| 1. Create and edit congresses | B | Works in the demo In the team console, with review before publishing. | yes | this run: C10 T1 functional PASS · custom_demo/README.md: `s1_congress.spec.mjs` 5/5 pass |
| 2. Public catalogue with search, filters and details page | A | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · wp_demo/README.md: S2-F1, S2-F2, S2-F3, S2-F4, S2-F5, S2-F6, S2-E1, S2-E2, S2-H1 |
| 2. Public catalogue with search, filters and details page | B | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · custom_demo/README.md: `s2_catalogue.spec.mjs` 9/9 pass |
| 3. Flight enquiry form | A | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · wp_demo/README.md: S3-F1, S3-F2, S3-F3, S3-F4, S3-E1, S3-H1, S3-H2, S3-H3 |
| 3. Flight enquiry form | B | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · custom_demo/README.md: `s3_enquiry.spec.mjs` 7/7 pass |
| 4. Receive, view, track and update enquiries | A | Works in the demo Statuses, history of changes, export to a spreadshee | NO | this run: C10 T4 FAIL · wp_demo/README.md: S4-F1, S4-F2, S4-F3, S4-F4, S4-F5, S4-F6, S4-E1, S4-H1 |
| 4. Receive, view, track and update enquiries | B | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · custom_demo/README.md: `s4_team.spec.mjs` 7/7 pass |
| 5. GM&E codes protected | A | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | NO | this run: C10 T5 FAIL · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 |
| 5. GM&E codes protected | B | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | yes | this run: C10 T5 functional PASS · custom_demo/README.md: `s5_gme.spec.mjs` 11/11 pass |
| Email notifications | A | Built during the project The demo shows a log of the messages instead  | yes | no UI label pretends it works |
| Email notifications | B | Built during the project The demo shows a log of the messages instead  | yes | no UI label pretends it works |
| Importing about 300 congresses from a spreadsheet | A | Built during the project With duplicate checks, and a trial run first. | yes | no UI label pretends it works |
| Importing about 300 congresses from a spreadsheet | B | Built during the project With duplicate checks, and a trial run first. | yes | no UI label pretends it works |
| English version | A | Built during the project Pages and congresses in English alongside Fre | yes | no UI label pretends it works |
| English version | B | Built during the project Pages and congresses in English alongside Fre | yes | no UI label pretends it works |
| Two-step login for staff | A | Built during the project A password plus a second check, for every sta | yes | no UI label pretends it works |
| Two-step login for staff | B | Built during the project Staff sign in with a code sent to their email | yes | no UI label pretends it works |
| Backups and restore | A | Built during the project Regular backups, and a tested way to restore  | yes | no UI label pretends it works |
| Backups and restore | B | Built during the project Regular backups, and a tested way to restore  | yes | no UI label pretends it works |
| Editing all the site’s pages | A | Works in the demo The standard WordPress page editor; your current pag | NO | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP 403 · no earlier test ID in wp_demo/README.md |
| Editing all the site’s pages | B | Built during the project A page editor added to the team console. | yes | no UI label pretends it works |
| Group link (#group) | B | Works in the Option B demo | NO | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») |

## A2 hosted boots

- visitor: first screen after 15.688 s; samples 1s:content, 3s:content, 3s:content, 6s:content, 10s:content, 15s:content
- admin: first screen after TIMEOUT s; samples 1s:content, 3s:content, 6s:content, 10s:content, 15s:content, 20s:content, 30s:content

## B6 glossary

| Term | A | B | Hub quotes |
|---|---|---|---|
| congress menu | Congrès | Congrès | Congrès |
| add a congress | Ajouter un congrès | Nouveau congrès / Ajouter | Ajouter un congrès |
| list of congresses | Tous les congrès / Congrès | Congrès | Tous les congrès / Congrès |
| enquiries | Demandes / Toutes les demandes | Demandes / Toutes les demandes | Demandes |
| status new | Nouvelle | Nouvelle | Nouvelle |
| status qualified | Qualifiée | Qualifiée | Qualifiée |
| notification log | Journal des notifications | Notifications | Journal des notifications |
| quote form title | Demander un devis vol | Demande de devis vol | Demander un devis vol |
| send the enquiry | Envoyer ma demande | Envoyer la demande |  |
| team area link | Espace équipe | Espace équipe | Espace équipe |
| GM&E codes screen | Accès GM&E / Codes GM&E / Codes | Codes GM&E / Codes | Accès GM&E / Codes GM&E |
| ask for access |  | Demander l’accès |  |
| approve | Approuver (24 h) / Approuver | Approuver pour 24 h |  |
| show the code | Révéler le code | Afficher le code |  |
| access log | Journal GM&E | Journal / Journal d’accès |  |
| access requests | Demandes d’accès | Demandes d’accès |  |
| CSV export | Exporter en CSV | Exporter (tableur CSV) / Exporter |  |
| sign out |  | Se déconnecter |  |
| sign in | Se connecter | Se connecter |  |
| dashboard | Tableau de bord | Tableau de bord |  |
| public catalogue | Catalogue des congrès | Catalogue des congrès |  |
| group tab |  | Groupe | Groupe |
| group link card |  | Lien de groupe | Lien de groupe |
| group export |  | Exporter pour cotation (CSV) | Exporter pour cotation (CSV) |

## Notes

- D4 reveal state C10 T5.3 (equipe) shows DEMO-GME-4KQ7
- D4 reveal state B equipe reveal (equipe) shows DEMO-GME-4821
- D4 reveal state C10 T5.3 (equipe) shows DEMO-GME-4821
- traveller phone sandbox cookie: DQE5szIuXdv7E1q1s6qHiq_p
