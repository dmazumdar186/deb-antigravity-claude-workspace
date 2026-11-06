# Client-eye gate report

Generated 2026-11-06T12:13:53.899Z. Commit 732d2eb6cc193b41077bca0daa8898b3f1d07513. Spec: `28_PreMortem_Client_Eye_Gate.md`. Machine-readable: `report.json`. Triage verdicts: `triage.json`. Register: `../register/CLIENT_EYE.md`.

## Targets and versions

- Hub: 5 tasks parsed, group section present; demo/index.html deployed = source, index.html deployed = source, js/demo.js deployed = source, css/demo.css deployed = source
- Option B Worker: dba3b6e7-d2ad-45c1-bfba-5132a304268a deployed 2026-11-06T10:55:45.590122Z; custom_demo/src last commit 0459ede 2026-11-06T10:54:46+00:00
- Option A: local Playground http://127.0.0.1:9460 built from the current wp_demo/ (zip b0fe713a2ce2); hosted zip b0fe713a2ce2
- Uncommitted source changes at run time: none
- States captured: 315; widths 320, 390, 768, 1280, 1440, 1920; roles A:visiteur, A:direction, A:contributeur, A:equipe, A-hosted:visiteur, B:visiteur, B:contributeur, B:equipe, B:voyageur, HUB:visiteur
- Part a: run 2026-11-06T12:10:39.981Z, logins 3, writing contexts 2
- Part ahosted: run 2026-11-06T12:11:22.680Z, logins 3, writing contexts 2
- Part b: run 2026-11-06T12:03:32.295Z, logins 3, writing contexts 2, own sandboxes 1
- Part hub: run 2026-11-06T11:59:10.634Z

## Per check

| Check | Type | What | REAL | FALSE-POSITIVE | UNTRIAGED | Status |
|---|---|---|---|---|---|---|
| A1 | auto | E-mail draft: one short https link, 200, no Playground URL | 0 | 0 | 0 | PASS |
| A2 | auto | Boot time shown next to each Option A button; boot screen never blank (hosted boot measured) | 0 | 0 | 0 | PASS |
| A3 | auto | Text blacklist (will appear here, REPLACE, TODO, lorem, undefined, NaN, null, [object Object], {{, %s, XXX) in text and attributes | 0 | 0 | 0 | PASS |
| A4 | auto | Every anchor, src, href, poster, video source answers 200 (or 30x to 200) with the right content type; no mixed content | 0 | 0 | 0 | UNVERIFIED |
| A5 | auto | Videos: poster, controls, playsinline, preload=metadata, < 25 MB, faststart, decoded frames > 0 | 0 | 0 | 0 | PASS |
| A6 | auto | Meaningful <title> and a favicon that answers 200 | 0 | 0 | 0 | PASS |
| A7 | decision | Address bar shows « debanjan186 »: operator decision | 0 | 0 | 0 | OPERATOR DECISION |
| B1 | auto | No English in French screens (fr-FR and en-GB browsers); hub French only inside « » | 0 | 0 | 0 | PASS |
| B2 | auto | No ISO/US dates; jj/mm/aaaa valid; Paris time; 00:05 Paris clock probe | 0 | 0 | 0 | PASS |
| B3 | auto | Plural agreement after 0, 1, 2 and many | 0 | 0 | 0 | PASS |
| B4 | auto | No mid-word breaks, no line starting with » ; : ! ? or ending with «, no orphan « — exemple » (320/390/768/1280/1440/1920) | 2 | 0 | 0 | FAIL |
| B5 | auto | Spell check fr + en (pyspellchecker) with a reasoned allowlist | 0 | 1 | 4 | FAIL |
| B6 | auto | Glossary of key labels: same names in the hub and both UIs | 0 | 1 | 5 | FAIL |
| B7 | auto | Missing accents / capitals on known words | 0 | 0 | 0 | PASS |
| C1 | auto | No 4xx/5xx, console or page errors in normal use; styled French error pages reached only on purpose | 0 | 0 | 2 | FAIL |
| C2 | auto | Every visible non-submit button changes something within 2 s; submit buttons exercised by the journeys | 0 | 0 | 0 | PASS |
| C3 | auto | No empty box: every 0-item list shows a sentence | 0 | 0 | 0 | PASS |
| C4 | auto | CLS ≤ 0.02 per page | 1 | 0 | 0 | FAIL |
| C5 | auto | One body family, one display family, one button style family, one accent colour per surface | 1 | 1 | 0 | FAIL |
| C6 | auto | No horizontal overflow (six widths); anchors not under the sticky header | 0 | 0 | 0 | PASS |
| C7 | auto | Expired session shows « Session expirée » + login link; purge only idle > 24 h; hub says private + 24 h reset | 0 | 0 | 0 | PASS |
| C8 | auto | No technical residue (errors, stack, JSON braces, wp: markup, hex runs ≥ 16) in visible text | 0 | 0 | 0 | PASS |
| C9 | auto | No test residue in the sample data (fresh browsers) | 0 | 0 | 0 | PASS |
| C10 | auto | Instruction replay: each hub step followed literally by visible labels | 3 | 0 | 8 | FAIL |
| D1 | auto | Every « Works in the demo » cell backed by evidence; « Built during the project » not faked by UI | 0 | 0 | 5 | FAIL |
| D2 | auto | Fictional people: @example.com, fiction phone ranges, no real congress names | 0 | 0 | 0 | PASS |
| D3 | auto | Every number on the hub is a week, a date, our demo data, or traced to a source line | 0 | 0 | 2 | FAIL |
| D4 | auto | No GM&E code in DOM, attributes or inputs outside an approved reveal | 0 | 0 | 0 | PASS |
| E1 | auto | Report names the commit and deployed versions; hub links checked against live versions | 0 | 0 | 0 | PASS |
| E2 | process | Full suites twice green after every change; this gate runs last | 0 | 0 | 0 | HUMAN/PROCESS |
| E3 | auto | Screenshots taken by this run from fresh contexts on the deployed sites | 0 | 0 | 0 | PASS |
| E4 | n/a | WebKit and Firefox | 0 | 0 | 0 | N/A |
| E5 | auto | Every check at 390 and 1440; B4/C6 at six widths | 0 | 0 | 0 | PASS |

Gate errors: 1

## Check notes

- **E4** N/A: Only Chromium is installed (.links, chromium, chromium-1243, chromium_headless_shell-1243, ffmpeg-1011); Firefox and WebKit are not, and the brief forbids installing them. Recorded N/A, never PASS.
- **A7** OPERATOR DECISION: Option B's address is https://asset-voyages-demo.debanjan186.workers.dev (contains « debanjan186 »). Accepted unless the operator asks for a custom domain.
- **E2** HUMAN/PROCESS: The suites (wp_demo/tests/run_all.sh, custom_demo playwright) must run twice green after the last change; this gate does not run them. It runs last, on the deployed versions named above.
- **E3** PASS: 247 screenshots, all written by this gate from fresh browser contexts on the deployed hub and Option B and the local Option A build.
- **E5** PASS: A: 320/390/768/1280/1440/1920; A-hosted: 1440; B: 320/390/768/1280/1440/1920; HUB: 320/390/768/1280/1440/1920. The hosted Option A boot is one boot per link at 1440 by design (brief).

## Findings

### A4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| CE-A4-001 | UNVERIFIED | HUB | https://www.sft.fr/global/gene/link.php?doc_id=882&edit_lang=fr · `a « 2025 survey »` | HTTP 403 | https://asset-voyages-redesign.pages.dev/questions/ · visiteur ·  |  | sft.fr answers 403 to scripted clients and to a real Chromium tab from this sandbox (a browser user-agent probe was refused by the auto-mode classifier). Needs one click from an ordinary browser. |
| CE-A4-001 | UNVERIFIED | HUB | https://www.sft.fr/docs/2024164729_sft-2022-enquete-traduction.pdf · `a « French translators’ union (SFT) 2022 sur »` | HTTP 403 | https://asset-voyages-redesign.pages.dev/questions/ · visiteur ·  |  | sft.fr answers 403 to scripted clients and to a real Chromium tab from this sandbox (a browser user-agent probe was refused by the auto-mode classifier). Needs one click from an ordinary browser. |

### B4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| CE-B4-005 | REAL | A | Responsable · `th#responsable` | mid-word | http://127.0.0.1:9460/wp-admin/admin.php?page=asset-demandes · direction · 1280 (2×) |  | A word is split across two lines without a hyphen (« d’ophtalmologie » in the Demandes table at 1280). |
| CE-B4-002 | REAL | HUB | ncontres d’ophtalmologie — exemple · `table.tbl > tbody > tr > td` | orphan-dash | https://asset-voyages-redesign.pages.dev/console/ · visiteur · 320/390/768 (4×) | out/shots/0004-HUB-visiteur-320-hub-console.png | Concept pages (/ and /console/) show sample titles whose « — exemple » wraps alone onto the next line at 320–768. |

### B5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| e6f632fb2d | UNTRIAGED | A | autrice · `fr` | unknown fr word in « Auteur/autrice » (14×) | http://127.0.0.1:9460/wp-admin/edit.php?post_type=page · direction · 1440 |  |  |
| 5812c2538c | FALSE-POSITIVE | A | equipe · `fr` | unknown fr word in « equipe » (2×) | http://127.0.0.1:9460/wp-admin/profile.php · equipe · 1440 |  | The login name shown in the « Identifiant » field of the profile screen: correct as typed. |
| 731a17e08b | UNTRIAGED | A | Policy · `fr` | unknown fr word in « Privacy Policy — Brouillon, Page de politique de confidentialité » (8×) | http://127.0.0.1:9460/wp-admin/edit.php?post_type=page · direction · 1440 |  |  |
| 319b036515 | UNTRIAGED | A | Privacy · `fr` | unknown fr word in « Privacy Policy — Brouillon, Page de politique de confidentialité » (8×) | http://127.0.0.1:9460/wp-admin/edit.php?post_type=page · direction · 1440 |  |  |
| 4327d6325c | UNTRIAGED | A | Reconnectez-vous · `fr` | unknown fr word in « Votre session a expiré. Reconnectez-vous. » (1×) | http://127.0.0.1:9460/wp-login.php?redirect_to=http%3A%2F%2F127.0.0.1%3A9460%2Fwp-admin%2Fadmin.php%3Fpage%3Dasset-demandes&reauth=1 · direction · 1440 |  |  |

### B6

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 12b3732ae8 | UNTRIAGED | A | access log | none of « Journal GM&E / Journal / Journal d’accès » seen in the A UI | glossary · visiteur ·  |  |  |
| de4f377ae3 | FALSE-POSITIVE | A | sign out | none of « Se déconnecter » seen in the A UI | glossary · visiteur ·  |  | WordPress shows « Se déconnecter » only in the account menu that opens on hover; the inventory records what is visible without hovering. The C10 replay hovered and clicked it (T5.2). Not tightened: the inventory stays « visible without interaction », the term is checked by C10. |
| 4726616861 | UNTRIAGED | B | approve | none of « Approuver (24 h) / Approuver pour 24 h / Approuver » seen in the B UI | glossary · visiteur ·  |  |  |
| 9635e26009 | UNTRIAGED | B | show the code | none of « Révéler le code / Afficher le code » seen in the B UI | glossary · visiteur ·  |  |  |
| 791f5c3260 | UNTRIAGED | B | access log | none of « Journal GM&E / Journal / Journal d’accès » seen in the B UI | glossary · visiteur ·  |  |  |
| fd5d699400 | UNTRIAGED | B | access requests | none of « Demandes d’accès » seen in the B UI | glossary · visiteur ·  |  |  |

### C1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 6985d60d80 | UNTRIAGED | B | 403 document https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/3 · `http` | during /console/demandes/3 | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/3 · contributeur · 1440 |  |  |
| 7b772f3a12 | UNTRIAGED | B | Failed to load resource: the server responded with a status of 403 (Forbidden) · `console` | during /console/demandes/3 | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes/3 · contributeur · 1440 |  |  |

### C4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| CE-C4-001 | REAL | A | CLS 0.048 · `DIV.drag-drop-inside+P.upload-flash-bypass+P.max-upload-size@1402ms=0.0482` | layout shift above 0.02 | http://127.0.0.1:9460/wp-admin/media-new.php · direction · 1440 (3×) | out/shots/0196-A-direction-1440-direction-wp-admin-media-new-php.png | WordPress admin screens shift after load: 0.02–0.07 (post-new 0.06–0.07 at 390, media-new 0.048, our Demandes detail 0.027 and Accès GM&E 0.022). Mostly core admin; the two plugin screens are ours. |
| CE-C4-001 | REAL | A | CLS 0.034 · `DIV.admin-ui-navigable-region.interface-interface-skeleton__sidebar+DIV.editor-h` | layout shift above 0.02 | http://127.0.0.1:9460/wp-admin/post-new.php?post_type=page · direction · 1440 (2×) | out/shots/0198-A-direction-1440-direction-wp-admin-post-new-php-post-type-page.png | WordPress admin screens shift after load: 0.02–0.07 (post-new 0.06–0.07 at 390, media-new 0.048, our Demandes detail 0.027 and Accès GM&E 0.022). Mostly core admin; the two plugin screens are ours. |
| CE-C4-001 | REAL | A | CLS 0.070 · `TEXTAREA#content.wp-editor-area+DIV#submitdiv.postbox+TABLE#post-status-info@200` | layout shift above 0.02 | http://127.0.0.1:9460/wp-admin/post-new.php?post_type=asset_congres · contributeur · 390 | out/shots/0260-A-contributeur-390-contributeur-390-wp-admin-post-new-php-post-type-asset-congr.png | WordPress admin screens shift after load: 0.02–0.07 (post-new 0.06–0.07 at 390, media-new 0.048, our Demandes detail 0.027 and Accès GM&E 0.022). Mostly core admin; the two plugin screens are ours. |
| CE-C4-001 | REAL | A | CLS 0.061 · `TEXTAREA#content.wp-editor-area+DIV#submitdiv.postbox+DIV.inside@1995ms=0.061` | layout shift above 0.02 | http://127.0.0.1:9460/wp-admin/post-new.php?post_type=asset_congres · equipe · 390 (2×) | out/shots/0266-A-equipe-390-equipe-390-wp-admin-post-new-php-post-type-asset-congres.png | WordPress admin screens shift after load: 0.02–0.07 (post-new 0.06–0.07 at 390, media-new 0.048, our Demandes detail 0.027 and Accès GM&E 0.022). Mostly core admin; the two plugin screens are ours. |

### C5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| a9d28ea061 | FALSE-POSITIVE | A-admin | -apple-system \| radius 2px (login page «  »); -apple-system \| radius 0px (C10 T1.1 « Options de l’écran »); dashicons \| radius 2px (C10 T1.2 | 4 button style families | A-admin · visiteur ·  |  | The extra families are WordPress core chrome (« Options de l’écran » tab, login page), not our buttons. Kept visible in the report; the plugin's own buttons are one family. |
| CE-C5-001 | REAL | hub | Inter \| radius 2px (hub/demo/ « Open the demos »); ui-monospace \| radius 4px (hub/ « ESPACE CLIENT »); Inter \| radius 4px (hub/ « ‹ »); Inte | 4 button style families | hub · visiteur ·  |  | Buttons on the concept pages (/ and /console/) are uppercase monospace, on the demos hub Inter sentence case: the five pages linked from the hub do not share one button style. |

### C10

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| b0321fd61a | UNTRIAGED | A | T5 step 1: Signed in as equipe, open « Codes GM&E › Codes »: the codes are hidden. Click « Demander l’accès » and give a reason. · `instruction replay` | label « Codes GM&E › Codes » not visible | http://127.0.0.1:9460/wp-admin/index.php · equipe · 1440 | out/shots/0235-A-equipe-1440-C10-T5-1.png |  |
| 72778b19b2 | UNTRIAGED | A | T5 step 2: Sign out, sign in as direction, open « Codes GM&E › Demandes d’accès », and click « Approuver pour 24 h » or « Refuser ». · `instruction replay` | label « Approuver (24 h) » not visible | http://127.0.0.1:9460/wp-admin/index.php · direction · 1440 | out/shots/0236-A-direction-1440-C10-T5-2.png |  |
| CE-C10-001 | REAL | A | T5 step 3: Sign in as equipe again and open « Codes GM&E › Codes ». The code stays hidden until you click « Afficher le code »: that click i · `instruction replay` | label « Accès GM&E » not visible | http://127.0.0.1:9460/wp-admin/index.php · equipe · 1440 | out/shots/0253-A-equipe-1440-C10-T5-3.png | Hub A task 5 step 3 says « the code is shown »; the reader must still click « Révéler le code » (one extra click the hub does not mention). |
| e73398e863 | UNTRIAGED | B | T1 step 2: Open the list of congresses and click « Ajouter un congrès », or open an existing one to change it. · `instruction replay` | step text changed: re-map the replay | https://asset-voyages-demo.debanjan186.workers.dev/console/congres · contributeur · 1440 | out/shots/0090-B-contributeur-1440-C10-T1-2.png |  |
| 48d10ba69c | UNTRIAGED | B | T1 step 3: Send it for review. Sign in as direction to check it and publish it. · `instruction replay` | no « review » button: label « Envoyer pour relecture » not visible | https://asset-voyages-demo.debanjan186.workers.dev/console/congres · contributeur · 1440 | out/shots/0091-B-contributeur-1440-C10-T1-3.png |  |
| 53044d8685 | UNTRIAGED | B | T3 step 3: Click « Envoyer ma demande ». You receive a reference number on screen. · `instruction replay` | label « Envoyer la demande » not visible | https://asset-voyages-demo.debanjan186.workers.dev/congres/journees-d-oncologie-digestive-cg-0112 · contributeur · 1440 | out/shots/0102-B-contributeur-1440-C10-T3-3.png |  |
| f7eac3700f | UNTRIAGED | B | T4 step 2: Open your enquiry from task 3 and change its status. Each change is kept in its history. · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · equipe · 1440 | out/shots/0109-B-equipe-1440-C10-T4-2.png |  |
| 5851bd10fa | UNTRIAGED | B | T4 step 3: Click « Exporter en CSV » to download the list as a spreadsheet file. « Journal des notifications » shows the message your team w · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · equipe · 1440 | out/shots/0110-B-equipe-1440-C10-T4-3.png |  |
| CE-C10-002 | REAL | B | T5 step 1: In the team console, sign in as equipe and open « Codes GM&E › Codes »: the codes are hidden. Click « Demander l’accès » and give · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · equipe · 1440 | out/shots/0111-B-equipe-1440-C10-T5-1.png | Hub B task 5 says open « Codes GM&E »; in the console that text is a non-clickable group heading, the link under it says « Codes ». |
| c6ddbd9782 | UNTRIAGED | B | T5 step 2: Sign out, sign in as direction, open « Codes GM&E › Demandes d’accès », and click « Approuver pour 24 h » or « Refuser ». · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · equipe · 1440 | out/shots/0112-B-equipe-1440-C10-T5-2.png |  |
| CE-C10-003 | REAL | B | T5 step 3: Sign in as equipe again and open « Codes GM&E › Codes ». The code stays hidden until you click « Afficher le code »: that click i · `instruction replay` | exception: locator.click: Timeout 5000ms exceeded. | https://asset-voyages-demo.debanjan186.workers.dev/console/demandes · equipe · 1440 | out/shots/0113-B-equipe-1440-C10-T5-3.png | Hub B task 5 step 3 says « the code is shown »; the reader must still click « Afficher le code ». |

### D1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| b551d64dd6 | UNTRIAGED | A | 5. GM&E codes protected: Works in the demo Codes hidden, access asked with a reason, 24-hour approval, a  · `table.cmp` | this run: C10 T5 FAIL · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 | demo/#compare · visiteur ·  |  |  |
| 3d3944fa1c | UNTRIAGED | B | 1. Create and edit congresses: Works in the demo In the team console, with review before publishing. · `table.cmp` | this run: C10 T1 FAIL · custom_demo/README.md: `s1_congress.spec.mjs` 5/5 pass | demo/#compare · visiteur ·  |  |  |
| bb66c57546 | UNTRIAGED | B | 3. Flight enquiry form: Works in the demo Every field is checked before sending; you get a reference. · `table.cmp` | this run: C10 T3 FAIL · custom_demo/README.md: `s3_enquiry.spec.mjs` 7/7 pass | demo/#compare · visiteur ·  |  |  |
| 28def1b383 | UNTRIAGED | B | 4. Receive, view, track and update enquiries: Works in the demo Statuses, history of changes, export to a spreadsheet (CSV). · `table.cmp` | this run: C10 T4 FAIL · custom_demo/README.md: `s4_team.spec.mjs` 7/7 pass | demo/#compare · visiteur ·  |  |  |
| a2cd02abc4 | UNTRIAGED | B | 5. GM&E codes protected: Works in the demo Codes hidden, access asked with a reason, 24-hour approval, a  · `table.cmp` | this run: C10 T5 FAIL · custom_demo/README.md: `s5_gme.spec.mjs` 11/11 pass | demo/#compare · visiteur ·  |  |  |

### D3

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| f5941be923 | UNTRIAGED | HUB | one · `rdPress starts fresh each time you open ⟨one⟩ of these links, so nothing from an` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 7bd7b4fa2a | UNTRIAGED | HUB | 24 · `their browser. Trials are cleared after ⟨24⟩ hours without use. ⏎  ⏎ 2 Try it yo` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (2×) |  |  |

### GATE

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 77ade27cb2 | UNTRIAGED | B | locator.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for getByLabel('E-mail')[22m  | B phone journeys aborted |  · visiteur ·  |  |  |

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
| A | T3.3 | yes | 1 | visiteur |  | Click « Envoyer ma demande ». You receive a reference number on screen. |
| A | T4.1 | yes | 3 | equipe |  | In the same tab as task 3, click « Espace équipe » and sign in as equipe. Open « Demandes »: your enquiry is at the top. |
| A | T4.2 | yes | 3 | equipe |  | Open it and change its status, for example from « Nouvelle » to « Qualifiée ». Each change is kept in its history. |
| A | T4.3 | yes | 3 | equipe |  | Click « Exporter en CSV » to download the list as a spreadsheet file. « Journal des notifications » shows the message your team would have r |
| A | T5.1 | NO | 0 | equipe | label « Codes GM&E › Codes » not visible | Signed in as equipe, open « Codes GM&E › Codes »: the codes are hidden. Click « Demander l’accès » and give a reason. |
| A | T5.2 | NO | 2 | direction | label « Approuver (24 h) » not visible | Sign out, sign in as direction, open « Codes GM&E › Demandes d’accès », and click « Approuver pour 24 h » or « Refuser ». |
| A | T5.3 | NO | 2 | equipe | label « Accès GM&E » not visible | Sign in as equipe again and open « Codes GM&E › Codes ». The code stays hidden until you click « Afficher le code »: that click is needed. E |
| B | T1.1 | yes | 1 | contributeur |  | Open the team console and sign in as contributeur. |
| B | T1.2 | NO | 0 | contributeur | step text changed: re-map the replay | Open the list of congresses and click « Ajouter un congrès », or open an existing one to change it. |
| B | T1.3 | NO | 0 | contributeur | no « review » button: label « Envoyer pour relecture » not visible | Send it for review. Sign in as direction to check it and publish it. |
| B | T2.1 | yes | 1 | contributeur |  | Open the visitor site and go to the congress catalogue. |
| B | T2.2 | yes | 1 | contributeur |  | Type a word in the search box, or narrow the list by discipline, country or month. |
| B | T2.3 | yes | 1 | contributeur |  | Open a congress to see its details page: dates, city, venue and discipline. |
| B | T3.1 | yes | 0 | contributeur | form already open on the page (0 clicks) | On a congress details page, find « Demander un devis vol ». |
| B | T3.2 | yes | 0 | contributeur |  | Enter your contact details, departure city, travel dates and number of passengers. |
| B | T3.3 | NO | 0 | contributeur | label « Envoyer la demande » not visible | Click « Envoyer ma demande ». You receive a reference number on screen. |
| B | T4.1 | yes | 2 | equipe |  | Open the team console, sign in as equipe and open « Demandes ». |
| B | T4.2 | NO | 0 | equipe | exception: locator.click: Timeout 5000ms exceeded. | Open your enquiry from task 3 and change its status. Each change is kept in its history. |
| B | T4.3 | NO | 0 | equipe | exception: locator.click: Timeout 5000ms exceeded. | Click « Exporter en CSV » to download the list as a spreadsheet file. « Journal des notifications » shows the message your team would have r |
| B | T5.1 | NO | 0 | equipe | exception: locator.click: Timeout 5000ms exceeded. | In the team console, sign in as equipe and open « Codes GM&E › Codes »: the codes are hidden. Click « Demander l’accès » and give a reason. |
| B | T5.2 | NO | 0 | equipe | exception: locator.click: Timeout 5000ms exceeded. | Sign out, sign in as direction, open « Codes GM&E › Demandes d’accès », and click « Approuver pour 24 h » or « Refuser ». |
| B | T5.3 | NO | 0 | equipe | exception: locator.click: Timeout 5000ms exceeded. | Sign in as equipe again and open « Codes GM&E › Codes ». The code stays hidden until you click « Afficher le code »: that click is needed. E |
| B | G.1 | yes | 0 | equipe |  | Open enquiry DV-2026-0001 in the Option B console (new tab) and sign in as equipe, password demo-asset. |
| B | G.2 | yes | 1 | equipe |  | Choose the « Groupe » tab. Three fictional travellers have already answered. |
| B | G.3 | yes | 1 | equipe |  | Under « Lien de groupe », copy the link and open it in another tab. This is the traveller’s page. |
| B | G.4 | yes | 0 | equipe |  | Send an answer, then go back to the « Groupe » tab: it is in the list. |
| Ahosted | T1.1 | yes | 0 | Bonjour, Direction (démo) | signed in as « Bonjour, Direction (démo) » | Open the admin. You are already signed in. |
| Ahosted | T1.2 | yes | 2 | Bonjour, Direction (démo) |  | In the left-hand menu, choose « Congrès », then « Ajouter un congrès ». |

## D1 claims

| Function | Option | Cell | OK | Evidence |
|---|---|---|---|---|
| 1. Create and edit congresses | A | Works in the demo In the standard WordPress editor, with review before | yes | this run: C10 T1 functional PASS · wp_demo/README.md: S1-F1, S1-F2, S1-F3, S1-E1, S1-E2, S1-H1, S1-H2 |
| 1. Create and edit congresses | B | Works in the demo In the team console, with review before publishing. | NO | this run: C10 T1 FAIL · custom_demo/README.md: `s1_congress.spec.mjs` 5/5 pass |
| 2. Public catalogue with search, filters and details page | A | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · wp_demo/README.md: S2-F1, S2-F2, S2-F3, S2-F4, S2-F5, S2-F6, S2-E1, S2-E2, S2-H1 |
| 2. Public catalogue with search, filters and details page | B | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · custom_demo/README.md: `s2_catalogue.spec.mjs` 9/9 pass |
| 3. Flight enquiry form | A | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · wp_demo/README.md: S3-F1, S3-F2, S3-F3, S3-F4, S3-E1, S3-H1, S3-H2, S3-H3 |
| 3. Flight enquiry form | B | Works in the demo Every field is checked before sending; you get a ref | NO | this run: C10 T3 FAIL · custom_demo/README.md: `s3_enquiry.spec.mjs` 7/7 pass |
| 4. Receive, view, track and update enquiries | A | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · wp_demo/README.md: S4-F1, S4-F2, S4-F3, S4-F4, S4-F5, S4-F6, S4-E1, S4-H1 |
| 4. Receive, view, track and update enquiries | B | Works in the demo Statuses, history of changes, export to a spreadshee | NO | this run: C10 T4 FAIL · custom_demo/README.md: `s4_team.spec.mjs` 7/7 pass |
| 5. GM&E codes protected | A | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | NO | this run: C10 T5 FAIL · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 |
| 5. GM&E codes protected | B | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | NO | this run: C10 T5 FAIL · custom_demo/README.md: `s5_gme.spec.mjs` 11/11 pass |
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
| Editing all the site’s pages | A | Works in the demo The standard WordPress page editor: sign in as direc | yes | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP 200 · no earlier test ID in wp_demo/README.md |
| Editing all the site’s pages | B | Built during the project A page editor added to the team console. | yes | no UI label pretends it works |
| Group link (#group) | B | Works in the Option B demo | yes | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») |

## A2 hosted boots

- visitor: first screen after 15.676 s; samples 1s:content, 3s:content, 6s:content, 10s:content, 15s:content
- admin: first screen after 16.635 s; samples 1s:content, 3s:content, 6s:content, 6s:content, 10s:content, 15s:content

## B6 glossary

| Term | A | B | Hub quotes |
|---|---|---|---|
| congress menu | Congrès | Congrès | Congrès |
| add a congress | Ajouter un congrès | Ajouter un congrès | Ajouter un congrès |
| list of congresses | Tous les congrès / Congrès | Congrès | Tous les congrès / Congrès |
| enquiries | Demandes / Toutes les demandes | Demandes / Toutes les demandes | Demandes |
| status new | Nouvelle | Nouvelle | Nouvelle |
| status qualified | Qualifiée | Qualifiée | Qualifiée |
| notification log | Journal des notifications | Journal des notifications | Journal des notifications |
| quote form title | Demander un devis vol | Demander un devis vol | Demander un devis vol |
| send the enquiry | Envoyer ma demande | Envoyer ma demande | Envoyer ma demande |
| team area link | Espace équipe | Espace équipe | Espace équipe |
| GM&E codes screen | Codes GM&E / Codes | Codes GM&E / Codes |  |
| ask for access | Demander l’accès | Demander l’accès | Demander l’accès |
| approve | Approuver pour 24 h |  |  |
| show the code | Afficher le code |  | Afficher le code |
| access log |  |  |  |
| access requests | Demandes d’accès |  |  |
| CSV export | Exporter en CSV | Exporter en CSV | Exporter en CSV |
| sign out |  | Se déconnecter |  |
| sign in | Se connecter | Se connecter |  |
| dashboard | Tableau de bord | Tableau de bord |  |
| public catalogue | Catalogue des congrès | Catalogue des congrès |  |
| group tab |  | Groupe | Groupe |
| group link card |  | Lien de groupe | Lien de groupe |
| group export |  | Exporter pour cotation (CSV) | Exporter pour cotation (CSV) |

## Notes

- hosted admin signed in as: Bonjour, Direction (démo)
- traveller phone sandbox cookie: JrD-RFqn1sWuCyK0dfZDzI3l
