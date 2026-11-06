# Client-eye gate report

Generated 2026-11-06T08:22:27.230Z. Commit f88dc8e3179d6d5b7fc87de09eae7f3892e38cb4. Spec: `28_PreMortem_Client_Eye_Gate.md`. Machine-readable: `report.json`. Triage verdicts: `triage.json`. Register: `../register/CLIENT_EYE.md`.

## Targets and versions

- Hub: 5 tasks parsed, group section present; demo/index.html deployed = source, index.html deployed = source, js/demo.js deployed = source, css/demo.css deployed = source
- Option B Worker: 9fdd6cb6-04fa-4d3a-a7ea-b2b7617bca32 deployed 2026-11-06T07:50:09.302386Z; custom_demo/src last commit d1c1942 2026-11-06T07:32:28+00:00
- Option A: local Playground  built from the current wp_demo/ (zip f2db344e4d84); hosted zip ad48baa5759e
- Uncommitted source changes at run time: none
- States captured: 40; widths 320, 390, 768, 1280, 1440, 1920; roles HUB:visiteur
- Part hub: run 2026-11-06T08:22:14.347Z

## Per check

| Check | Type | What | REAL | FALSE-POSITIVE | UNTRIAGED | Status |
|---|---|---|---|---|---|---|
| A1 | auto | E-mail draft: one short https link, 200, no Playground URL | 0 | 0 | 0 | PASS |
| A2 | auto | Boot time shown next to each Option A button; boot screen never blank (hosted boot measured) | 0 | 0 | 0 | PASS |
| A3 | auto | Text blacklist (will appear here, REPLACE, TODO, lorem, undefined, NaN, null, [object Object], {{, %s, XXX) in text and attributes | 0 | 0 | 0 | PASS |
| A4 | auto | Every anchor, src, href, poster, video source answers 200 (or 30x to 200) with the right content type; no mixed content | 0 | 0 | 10 | FAIL |
| A5 | auto | Videos: poster, controls, playsinline, preload=metadata, < 25 MB, faststart, decoded frames > 0 | 0 | 0 | 0 | PASS |
| A6 | auto | Meaningful <title> and a favicon that answers 200 | 0 | 0 | 0 | PASS |
| A7 | decision | Address bar shows « debanjan186 »: operator decision | 0 | 0 | 0 | OPERATOR DECISION |
| B1 | auto | No English in French screens (fr-FR and en-GB browsers); hub French only inside « » | 0 | 0 | 0 | PASS |
| B2 | auto | No ISO/US dates; jj/mm/aaaa valid; Paris time; 00:05 Paris clock probe | 0 | 0 | 16 | FAIL |
| B3 | auto | Plural agreement after 0, 1, 2 and many | 0 | 0 | 0 | PASS |
| B4 | auto | No mid-word breaks, no line starting with » ; : ! ? or ending with «, no orphan « — exemple » (320/390/768/1280/1440/1920) | 0 | 0 | 12 | FAIL |
| B5 | auto | Spell check fr + en (pyspellchecker) with a reasoned allowlist | 0 | 0 | 87 | FAIL |
| B6 | auto | Glossary of key labels: same names in the hub and both UIs | 0 | 0 | 60 | FAIL |
| B7 | auto | Missing accents / capitals on known words | 0 | 0 | 3 | FAIL |
| C1 | auto | No 4xx/5xx, console or page errors in normal use; styled French error pages reached only on purpose | 0 | 0 | 0 | PASS |
| C2 | auto | Every visible non-submit button changes something within 2 s; submit buttons exercised by the journeys | 0 | 0 | 5 | FAIL |
| C3 | auto | No empty box: every 0-item list shows a sentence | 0 | 0 | 0 | PASS |
| C4 | auto | CLS ≤ 0.02 per page | 0 | 0 | 0 | PASS |
| C5 | auto | One body family, one display family, one button style family, one accent colour per surface | 0 | 0 | 3 | FAIL |
| C6 | auto | No horizontal overflow (six widths); anchors not under the sticky header | 0 | 0 | 0 | PASS |
| C7 | auto | Expired session shows « Session expirée » + login link; purge only idle > 24 h; hub says private + 24 h reset | 0 | 0 | 2 | FAIL |
| C8 | auto | No technical residue (errors, stack, JSON braces, wp: markup, hex runs ≥ 16) in visible text | 0 | 0 | 0 | PASS |
| C9 | auto | No test residue in the sample data (fresh browsers) | 0 | 0 | 0 | PASS |
| C10 | auto | Instruction replay: each hub step followed literally by visible labels | 0 | 0 | 0 | PASS |
| D1 | auto | Every « Works in the demo » cell backed by evidence; « Built during the project » not faked by UI | 0 | 0 | 2 | FAIL |
| D2 | auto | Fictional people: @example.com, fiction phone ranges, no real congress names | 0 | 0 | 5 | FAIL |
| D3 | auto | Every number on the hub is a week, a date, our demo data, or traced to a source line | 0 | 0 | 20 | FAIL |
| D4 | auto | No GM&E code in DOM, attributes or inputs outside an approved reveal | 0 | 0 | 0 | PASS |
| E1 | auto | Report names the commit and deployed versions; hub links checked against live versions | 0 | 0 | 1 | FAIL |
| E2 | process | Full suites twice green after every change; this gate runs last | 0 | 0 | 0 | HUMAN/PROCESS |
| E3 | auto | Screenshots taken by this run from fresh contexts on the deployed sites | 0 | 0 | 0 | PASS |
| E4 | n/a | WebKit and Firefox | 0 | 0 | 0 | N/A |
| E5 | auto | Every check at 390 and 1440; B4/C6 at six widths | 0 | 0 | 0 | PASS |

## Check notes

- **E4** N/A: Only Chromium is installed (.links, chromium, chromium-1243, chromium_headless_shell-1243, ffmpeg-1011); Firefox and WebKit are not, and the brief forbids installing them. Recorded N/A, never PASS.
- **A7** OPERATOR DECISION: Option B's address is https://asset-voyages-demo.debanjan186.workers.dev (contains « debanjan186 »). Accepted unless the operator asks for a custom domain.
- **E2** HUMAN/PROCESS: The suites (wp_demo/tests/run_all.sh, custom_demo playwright) must run twice green after the last change; this gate does not run them. It runs last, on the deployed versions named above.
- **E3** PASS: 40 screenshots, all written by this gate from fresh browser contexts on the deployed hub and Option B and the local Option A build.
- **E5** PASS: HUB: 320/390/768/1280/1440/1920. The hosted Option A boot is one boot per link at 1440 by design (brief).

## Findings

### A4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 78e64f9895 | UNTRIAGED | HUB | mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot&body=Proposed%20slot%3A%20Thursday%2012%2 · `a[href^=mailto]` | malformed mailto | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  (2×) |  |  |
| 1ede3d8396 | UNTRIAGED | HUB | mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot&body=Proposed%20slot%3A%20Friday%2013%20N · `a[href^=mailto]` | malformed mailto | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  |  |  |
| e6327b1669 | UNTRIAGED | HUB | mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot&body=Proposed%20slot%3A%20Monday%2016%20N · `a[href^=mailto]` | malformed mailto | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  (2×) |  |  |
| e6dbacb112 | UNTRIAGED | HUB | mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot&body=Proposed%20slot%3A%20Tuesday%2017%20 · `a[href^=mailto]` | malformed mailto | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  (2×) |  |  |
| 2ad4d9786b | UNTRIAGED | HUB | https://asset-voyages-redesign.pages.dev/demo/media/wp-walkthrough.mp4 · `a` | answers 200 but as « text/html; charset=utf-8 » (missing file served as a page) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  |  |  |
| b833ea41dd | UNTRIAGED | HUB | https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json · `a « Open the admin, signed in to Option A (n »` | blueprint is not valid JSON | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  |  |  |
| a4299b20ae | UNTRIAGED | HUB | https://playground.wordpress.net/?mode=seamless&login=no&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-vis · `a « Open the visitor site of Option A (new t »` | blueprint is not valid JSON | https://asset-voyages-redesign.pages.dev/demo/ · visiteur ·  |  |  |
| cf202b618a | UNTRIAGED | HUB | https://commons.wikimedia.org/wiki/File:Paris-pano-wladyslaw.jpg · `a` | answers 200 but as « text/html; charset=UTF-8 » (missing file served as a page) | https://asset-voyages-redesign.pages.dev/ · visiteur ·  |  |  |
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
| a983ea8af0 | UNTRIAGED | HUB | add-ons · `en` | unknown en word in « The version of today’s site, its add-ons and any custom code. » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| a510a3ac69 | UNTRIAGED | HUB | admin · `en` | unknown en word in « Open the admin, signed in » (120×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| 86e26dd8e9 | UNTRIAGED | HUB | agences · `en` | unknown en word in « “Plus de 122 agences”. The Selectour Affaires figure on your site is undated. Your brief asks for claims to be checked b » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 2fe7b82d27 | UNTRIAGED | HUB | Allemagne · `fr` | unknown fr word in « Allemagne » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| da934ca5b7 | UNTRIAGED | HUB | Analytics · `en` | unknown en word in « Cloudflare Web Analytics » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 436eb09a19 | UNTRIAGED | HUB | anti-spam · `fr` | unknown fr word in « L’envoi des formulaires. Les formulaires valident et confirment à l’écran, sans rien envoyer ; en production : enregistr » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 985de3f6f8 | UNTRIAGED | HUB | app · `en` | unknown en word in « Two-step login for staff, only for named work email addresses: either your work email account (Microsoft 365 or Google W » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| db270e774c | UNTRIAGED | HUB | Approx · `en` | unknown en word in « Approx. per month » (4×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 1280 |  |  |
| b977f7d5a1 | UNTRIAGED | HUB | ASSETNos · `fr` | unknown fr word in « OffresCongrèsContactNote pour ASSETNos questionsLes deux démosHaut de page ↑ » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 4f2709d3b6 | UNTRIAGED | HUB | Aujourd · `fr` | unknown fr word in « Aujourd’hui / concept » (48×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 4ca77c2e7d | UNTRIAGED | HUB | authorised · `en` | unknown en word in « Only if you lack authorised photos. Example: a stock-photo plan with 10 images a month » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 2b6719cebb | UNTRIAGED | HUB | avr · `fr` | unknown fr word in « avr. – juin 2027 » (24×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 405af55135 | UNTRIAGED | HUB | Brevo · `en` | unknown en word in « Brevo (French), backup Resend » (24×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| a077631d50 | UNTRIAGED | HUB | brief · `fr` | unknown fr word in « 01 Le brief » (88×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| aee985bdd9 | UNTRIAGED | HUB | clics · `fr` | unknown fr word in « Dans la maquette : toutes les offres et tous les formulaires accessibles sans quitter la page, en 1 à 2 clics depuis le  » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 990a5629af | UNTRIAGED | HUB | cliquable · `fr` | unknown fr word in « Une maquette cliquable de la refonte d’asset-voyagesdaffaires.com, construite à partir de votre consultation (version 0. » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| a9f0a4438b | UNTRIAGED | HUB | colours · `en` | unknown en word in « 10Do you have brand guidelines (logo files, colours, fonts)? Is the logo fixed, or is a light refresh welcome? » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d0677a7231 | UNTRIAGED | HUB | Commons · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 15f6ec277f | UNTRIAGED | HUB | CongrèsAgence · `fr` | unknown fr word in « Voyages d’affaires · MICE · CongrèsAgence Selectour Affaires · Issy-les-Moulineaux » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 1280 |  |  |
| 7c2d19da00 | UNTRIAGED | HUB | Connexion · `en` | unknown en word in « Client login. Your current client area says “Connexion Traveldoo”, while the brief mentions Wondermiles. Is Wondermiles  » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 1bb5eee6df | UNTRIAGED | HUB | Directus · `en` | unknown en word in « The alternative. A ready-made content editor such as Directus, installed on a rented server. It is a sound product and w » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 69bb595528 | UNTRIAGED | HUB | docx · `en` | unknown en word in « Word version (.docx) » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 9a9942af1f | UNTRIAGED | HUB | déc · `fr` | unknown fr word in « oct. – déc. 2027 » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| b8cc404940 | UNTRIAGED | HUB | Démo · `fr` | unknown fr word in « Démo de l’outil de réservation » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 12116dd180 | UNTRIAGED | HUB | démos · `fr` | unknown fr word in « Les autres pages : le concept · la Console · nos questions · les deux démos (en anglais). » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 0bdafe48d9 | UNTRIAGED | HUB | démosHaut · `fr` | unknown fr word in « OffresCongrèsContactNote pour ASSETNos questionsLes deux démosHaut de page ↑ » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 4e66cc8c11 | UNTRIAGED | HUB | E-mail · `fr` | unknown fr word in « E-mail professionnel » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 20bd825f00 | UNTRIAGED | HUB | Eiffel · `fr` | unknown fr word in « Panorama de Paris avec la tour Eiffel et le dôme des Invalides » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 96a3a6c500 | UNTRIAGED | HUB | Events · `fr` | unknown fr word in « Meetings & Events » (28×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 04ccf1fde6 | UNTRIAGED | HUB | export · `fr` | unknown fr word in « L’envoi des formulaires. Les formulaires valident et confirment à l’écran, sans rien envoyer ; en production : enregistr » (24×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 0129ae2dc7 | UNTRIAGED | HUB | fillable · `en` | unknown en word in « Download the answer sheet (fillable PDF) » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 2ad01bb712 | UNTRIAGED | HUB | filtrable · `fr` | unknown fr word in « Catalogue filtrable, fiche par congrès, devis vol pré-rempli ; les statuts internes ne sont jamais affichés » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 6205640fb5 | UNTRIAGED | HUB | févr · `fr` | unknown fr word in « 24–28 févr. 2027 » (16×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| f9fcd20efd | UNTRIAGED | HUB | Gandi · `en` | unknown en word in « Estimates, prices checked 28 October 2026, excluding VAT, paid to the providers, not to us. The domain name, hosting and » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d3eb0002ea | UNTRIAGED | HUB | Google · `fr` | unknown fr word in « Un concept publié à une adresse de test, non référencé : il n’apparaît pas sur Google et n’est lié depuis aucun site pub » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| ceaa94d7ac | UNTRIAGED | HUB | Géolocalisation · `fr` | unknown fr word in « Géolocalisation » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| b1a73ecca2 | UNTRIAGED | HUB | HubSpot · `en` | unknown en word in « Only if you choose one. Free plans exist (HubSpot: free for up to 2 users); paid plans start around $7–20 per user » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 4c17c972cd | UNTRIAGED | HUB | import · `fr` | unknown fr word in « L’administration réelle. La Console est une maquette : gestion des pages, rôles, import de tableur, versions et journal  » (16×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| a7d1734a0c | UNTRIAGED | HUB | incentive · `fr` | unknown fr word in « Séminaire, incentive, groupe » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 41ed136c8e | UNTRIAGED | HUB | incentives · `fr` | unknown fr word in « MICE · séminaires, incentives, groupes » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| b4e343d038 | UNTRIAGED | HUB | Issy-les-Moulineaux · `fr` | unknown fr word in « 58, rue Jean-Pierre Timbaud · 92130 Issy-les-Moulineaux · Photo : Wladyslaw Sojka, CC BY 3.0 via Wikimedia Commons » (24×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2c5df458c3 | UNTRIAGED | HUB | janv · `fr` | unknown fr word in « janv. – mars 2027 » (24×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 9f26cca240 | UNTRIAGED | HUB | juil · `fr` | unknown fr word in « juil. – sept. 2027 » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 1c3f7e679f | UNTRIAGED | HUB | Khatri · `fr` | unknown fr word in « ASSET Voyages — direction, et Mme Veena Khatri (coordination) » (72×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| 7c2d22d04e | UNTRIAGED | HUB | Khatri · `en` | unknown en word in « ASSET Voyages management, and Ms Veena Khatri (coordination) » (128×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| d4dbd57bdd | UNTRIAGED | HUB | LinkedIn · `en` | unknown en word in « 7Could you give us read-only access to Google Analytics and Search Console? Which trackers (LinkedIn, Meta) and ad campa » (16×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 78d066e22e | UNTRIAGED | HUB | Lisbonne · `fr` | unknown fr word in « Lisbonne, Portugal » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 075fc43d13 | UNTRIAGED | HUB | logins · `en` | unknown en word in « The console asks you to sign in with one of the logins below. » (16×) | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 320 |  |  |
| 63bbfd97df | UNTRIAGED | HUB | Lyon · `fr` | unknown fr word in « Lyon, France » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2d85aae16a | UNTRIAGED | HUB | Marseille · `fr` | unknown fr word in « Marseille, France » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| aabf7528dc | UNTRIAGED | HUB | Mme · `fr` | unknown fr word in « ASSET Voyages — direction, et Mme Veena Khatri (coordination) » (72×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |
| b444046a9b | UNTRIAGED | HUB | multi-segments · `fr` | unknown fr word in « « […] nous trouvons la meilleure combinaison tarifaire pour les billets complexes, comme les multi-segments ou les tours » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 9d03bce133 | UNTRIAGED | HUB | oct · `fr` | unknown fr word in « oct. – déc. 2027 » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 6c86b547e3 | UNTRIAGED | HUB | OffresCongrèsContactNote · `fr` | unknown fr word in « OffresCongrèsContactNote pour ASSETNos questionsLes deux démosHaut de page ↑ » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 0e512ef22d | UNTRIAGED | HUB | Oncologie · `fr` | unknown fr word in « Oncologie » (32×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2256cbea37 | UNTRIAGED | HUB | PME-PMI · `fr` | unknown fr word in « Nous proposons aux PME-PMI ainsi qu’aux TPE des solutions sur mesure pour gérer et optimiser vos déplacements profession » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 2e5af2964e | UNTRIAGED | HUB | PME-TPE · `fr` | unknown fr word in « Offre PME-TPE » (4×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| a8c062a2b3 | UNTRIAGED | HUB | Pneumologie · `fr` | unknown fr word in « Pneumologie » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| e3b73f2550 | UNTRIAGED | HUB | programme · `en` | unknown en word in « 18Answer first Does ASSET already work with Air France–KLM’s Global Meetings and Events programme? How do the event code » (8×) | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 320 |  |  |
| 18a7adae5f | UNTRIAGED | HUB | Qualifiéerappel · `fr` | unknown fr word in « Qualifiéerappel aujourd’hui » (8×) | https://asset-voyages-redesign.pages.dev/console/ · visiteur · 320 |  |  |
| 2a9294815b | UNTRIAGED | HUB | questionsLes · `fr` | unknown fr word in « OffresCongrèsContactNote pour ASSETNos questionsLes deux démosHaut de page ↑ » (8×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 8596de7d32 | UNTRIAGED | HUB | reporting · `fr` | unknown fr word in « « Un reporting complet et personnalisé des voyages d’affaires de vos collaborateurs. » » (16×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 18a9e03df8 | UNTRIAGED | HUB | revérifier · `fr` | unknown fr word in « « Avec plus de 122 agences et plateaux d’affaires en France, Selectour Affaires constitue le premier réseau dédié aux vo » (12×) | https://asset-voyages-redesign.pages.dev/ · visiteur · 320 |  |  |
| 5e07c50ae3 | UNTRIAGED | HUB | rhumatologie · `fr` | unknown fr word in « Journées de rhumatologie — exemple » (8×) | https://asset-voyages-redesign.pages.dev/console/ · visiteur · 320 |  |  |
| ebf90810a3 | UNTRIAGED | HUB | Réf · `fr` | unknown fr word in « Réf. » (16×) | https://asset-voyages-redesign.pages.dev/console/ · visiteur · 320 |  |  |
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
| c5177d9251 | UNTRIAGED | HUB | www · `fr` | unknown fr word in « Domaine actuel asset-voyagesdaffaires.com, alors que la consultation cite www.assetvoyages.com · l’espace client actuel  » (8×) | https://asset-voyages-redesign.pages.dev/pour-asset/ · visiteur · 320 |  |  |

### B6

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| d7a7c8a01f | UNTRIAGED | A | congress menu | none of « Congrès » seen in the A UI | glossary · visiteur ·  |  |  |
| 11b67150f0 | UNTRIAGED | A | add a congress | none of « Ajouter un congrès / Nouveau congrès / Ajouter » seen in the A UI | glossary · visiteur ·  |  |  |
| c9e407a20a | UNTRIAGED | A | list of congresses | none of « Tous les congrès / Congrès » seen in the A UI | glossary · visiteur ·  |  |  |
| 2982539102 | UNTRIAGED | A | enquiries | none of « Demandes / Toutes les demandes » seen in the A UI | glossary · visiteur ·  |  |  |
| 75760b38c0 | UNTRIAGED | A | status new | none of « Nouvelle » seen in the A UI | glossary · visiteur ·  |  |  |
| 36cc850fae | UNTRIAGED | A | status qualified | none of « Qualifiée » seen in the A UI | glossary · visiteur ·  |  |  |
| f4f6d69c00 | UNTRIAGED | A | notification log | none of « Journal des notifications / Notifications » seen in the A UI | glossary · visiteur ·  |  |  |
| 0807871384 | UNTRIAGED | A | quote form title | none of « Demander un devis vol / Demande de devis vol / Demander un devis » seen in the A UI | glossary · visiteur ·  |  |  |
| 10bf197512 | UNTRIAGED | A | send the enquiry | none of « Envoyer ma demande / Envoyer la demande » seen in the A UI | glossary · visiteur ·  |  |  |
| be7753f8bb | UNTRIAGED | A | team area link | none of « Espace équipe » seen in the A UI | glossary · visiteur ·  |  |  |
| 3e52fc691c | UNTRIAGED | A | GM&E codes screen | none of « Accès GM&E / Codes GM&E / Codes » seen in the A UI | glossary · visiteur ·  |  |  |
| e18336fe3d | UNTRIAGED | A | ask for access | none of « Demander l’accès / Demander l'accès » seen in the A UI | glossary · visiteur ·  |  |  |
| f6b9cd6fe1 | UNTRIAGED | A | approve | none of « Approuver (24 h) / Approuver pour 24 h / Approuver » seen in the A UI | glossary · visiteur ·  |  |  |
| afa414ffc1 | UNTRIAGED | A | show the code | none of « Révéler le code / Afficher le code » seen in the A UI | glossary · visiteur ·  |  |  |
| 12b3732ae8 | UNTRIAGED | A | access log | none of « Journal GM&E / Journal / Journal d’accès » seen in the A UI | glossary · visiteur ·  |  |  |
| f842c5f98e | UNTRIAGED | A | access requests | none of « Demandes d’accès » seen in the A UI | glossary · visiteur ·  |  |  |
| ff605f8b3f | UNTRIAGED | A | CSV export | none of « Exporter en CSV / Exporter (tableur CSV) / Exporter » seen in the A UI | glossary · visiteur ·  |  |  |
| de4f377ae3 | UNTRIAGED | A | sign out | none of « Se déconnecter » seen in the A UI | glossary · visiteur ·  |  |  |
| 073fca929b | UNTRIAGED | A | sign in | none of « Se connecter » seen in the A UI | glossary · visiteur ·  |  |  |
| 905ca055c2 | UNTRIAGED | A | dashboard | none of « Tableau de bord » seen in the A UI | glossary · visiteur ·  |  |  |
| 8f431cea8b | UNTRIAGED | A | public catalogue | none of « Catalogue des congrès » seen in the A UI | glossary · visiteur ·  |  |  |
| 20e5109167 | UNTRIAGED | A | « Congrès » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 3a7af20af3 | UNTRIAGED | A | « Ajouter un congrès » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| d0de5386c8 | UNTRIAGED | A | « Tous les congrès » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 53906737dc | UNTRIAGED | A | « Demander un devis vol » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 3dbeb7c223 | UNTRIAGED | A | « Espace équipe » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| b0e5b90212 | UNTRIAGED | A | « Demandes » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| c3319b4925 | UNTRIAGED | A | « Nouvelle » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| b47f9df1e5 | UNTRIAGED | A | « Qualifiée » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| c6e9febf80 | UNTRIAGED | A | « Journal des notifications » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| e433b68fa3 | UNTRIAGED | A | « Accès GM&E » | quoted on the hub for Option A but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 6027f8df43 | UNTRIAGED | B | congress menu | none of « Congrès » seen in the B UI | glossary · visiteur ·  |  |  |
| 39a22759f6 | UNTRIAGED | B | add a congress | none of « Ajouter un congrès / Nouveau congrès / Ajouter » seen in the B UI | glossary · visiteur ·  |  |  |
| 6e23758adb | UNTRIAGED | B | list of congresses | none of « Tous les congrès / Congrès » seen in the B UI | glossary · visiteur ·  |  |  |
| d170887729 | UNTRIAGED | B | enquiries | none of « Demandes / Toutes les demandes » seen in the B UI | glossary · visiteur ·  |  |  |
| 0c0abbc77a | UNTRIAGED | B | status new | none of « Nouvelle » seen in the B UI | glossary · visiteur ·  |  |  |
| de40143d82 | UNTRIAGED | B | status qualified | none of « Qualifiée » seen in the B UI | glossary · visiteur ·  |  |  |
| 6ddec3761d | UNTRIAGED | B | notification log | none of « Journal des notifications / Notifications » seen in the B UI | glossary · visiteur ·  |  |  |
| 2e71fbd06f | UNTRIAGED | B | quote form title | none of « Demander un devis vol / Demande de devis vol / Demander un devis » seen in the B UI | glossary · visiteur ·  |  |  |
| f478ea2841 | UNTRIAGED | B | send the enquiry | none of « Envoyer ma demande / Envoyer la demande » seen in the B UI | glossary · visiteur ·  |  |  |
| 6fcc4c6599 | UNTRIAGED | B | team area link | none of « Espace équipe » seen in the B UI | glossary · visiteur ·  |  |  |
| 4f23975f7e | UNTRIAGED | B | GM&E codes screen | none of « Accès GM&E / Codes GM&E / Codes » seen in the B UI | glossary · visiteur ·  |  |  |
| 14f60fb05f | UNTRIAGED | B | ask for access | none of « Demander l’accès / Demander l'accès » seen in the B UI | glossary · visiteur ·  |  |  |
| 4726616861 | UNTRIAGED | B | approve | none of « Approuver (24 h) / Approuver pour 24 h / Approuver » seen in the B UI | glossary · visiteur ·  |  |  |
| 9635e26009 | UNTRIAGED | B | show the code | none of « Révéler le code / Afficher le code » seen in the B UI | glossary · visiteur ·  |  |  |
| 791f5c3260 | UNTRIAGED | B | access log | none of « Journal GM&E / Journal / Journal d’accès » seen in the B UI | glossary · visiteur ·  |  |  |
| fd5d699400 | UNTRIAGED | B | access requests | none of « Demandes d’accès » seen in the B UI | glossary · visiteur ·  |  |  |
| 4b3caf7e52 | UNTRIAGED | B | CSV export | none of « Exporter en CSV / Exporter (tableur CSV) / Exporter » seen in the B UI | glossary · visiteur ·  |  |  |
| 7408259538 | UNTRIAGED | B | sign out | none of « Se déconnecter » seen in the B UI | glossary · visiteur ·  |  |  |
| 2c930d591f | UNTRIAGED | B | sign in | none of « Se connecter » seen in the B UI | glossary · visiteur ·  |  |  |
| 757deffe94 | UNTRIAGED | B | dashboard | none of « Tableau de bord » seen in the B UI | glossary · visiteur ·  |  |  |
| eb1cf007c5 | UNTRIAGED | B | public catalogue | none of « Catalogue des congrès » seen in the B UI | glossary · visiteur ·  |  |  |
| b8f3189524 | UNTRIAGED | B | group tab | none of « Groupe » seen in the B UI | glossary · visiteur ·  |  |  |
| 0eb7f061bb | UNTRIAGED | B | group link card | none of « Lien de groupe » seen in the B UI | glossary · visiteur ·  |  |  |
| 2fecfe772f | UNTRIAGED | B | group export | none of « Exporter pour cotation (CSV) » seen in the B UI | glossary · visiteur ·  |  |  |
| 10af161061 | UNTRIAGED | B | « Codes GM&E » | quoted on the hub for Option B but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 4ffc59ca93 | UNTRIAGED | B | « répondus / attendus » | quoted on the hub for Option B but not seen as a label in that UI | hub · visiteur ·  |  |  |
| 64a122faa9 | UNTRIAGED | B | « Exporter pour cotation (CSV) » | quoted on the hub for Option B but not seen as a label in that UI | hub · visiteur ·  |  |  |
| fb16684fe6 | UNTRIAGED | B | « Groupe » | quoted on the hub for Option B but not seen as a label in that UI | hub · visiteur ·  |  |  |
| c739e2ab32 | UNTRIAGED | B | « Lien de groupe » | quoted on the hub for Option B but not seen as a label in that UI | hub · visiteur ·  |  |  |

### B7

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 60d9fc14cf | UNTRIAGED | HUB | On a congress details page, find « Demander un devis vol ». · `li#task-3 > div.task__opt.task__opt--a > ol.steps > li` | « congress » should be « Congrèss » | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 390/1440 (4×) | out/shots/0006-HUB-visiteur-390-hub-demo.png |  |
| 4399ec9991 | UNTRIAGED | HUB | Signed in as equipe, open « Accès GM&E »: the codes are hidden. Ask for access and give a reason. · `li#task-5 > div.task__opt.task__opt--a > ol.steps > li` | « access » should be « Accèss » | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 390/1440 (4×) | out/shots/0006-HUB-visiteur-390-hub-demo.png |  |
| ad9e6d8db3 | UNTRIAGED | HUB | In the team console, sign in as equipe and open « Codes GM&E »: the codes are hidden. Ask for access and give a reason. · `li#task-5 > div.task__opt.task__opt--b > ol.steps > li` | « access » should be « Accèss » | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 1440 (2×) | out/shots/0021-HUB-visiteur-1440-hub-demo.png |  |

### C2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 46b8794844 | UNTRIAGED | HUB | Réinitialiser · `button` | not clickable: locator.click: Timeout 3000ms exceeded. | https://asset-voyages-redesign.pages.dev/ · visiteur · 390 |  |  |
| e0fe1091b4 | UNTRIAGED | HUB | Voir la fiche · `button` | not clickable: locator.click: Timeout 3000ms exceeded. | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (11×) |  |  |
| 86fb4de08e | UNTRIAGED | HUB | ‹ · `button` | not clickable: locator.click: Timeout 3000ms exceeded. | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (2×) |  |  |
| 4649fa6aad | UNTRIAGED | HUB | 1 · `button` | not clickable: locator.click: Timeout 3000ms exceeded. | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (2×) |  |  |
| fedbdde1a0 | UNTRIAGED | HUB | 2 · `button` | not clickable: locator.click: Timeout 3000ms exceeded. | https://asset-voyages-redesign.pages.dev/ · visiteur · 1440 |  |  |

### C5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 157184c163 | UNTRIAGED | hub | Inter (hub/demo/); ui-monospace (hub/) | 2 body font families | hub · visiteur ·  |  |  |
| dd39488a29 | UNTRIAGED | hub | EB Garamond (hub/demo/); Inter (hub/questions/) | 2 display font families | hub · visiteur ·  |  |  |
| af434992f4 | UNTRIAGED | hub | Inter \| radius 4px (hub/demo/ « Open the demos »); ui-monospace \| radius 4px (hub/ « ESPACE CLIENT »); Inter \| radius 2px (hub/ « Parler à u | 4 button style families | hub · visiteur ·  |  |  |

### C7

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 4005f28b67 | UNTRIAGED | B | SELECT id FROM sandboxes WHERE created_at < ?1 ORDER BY created_at LIMIT ${PURGE_SANDBOXES} · `source` | the 03:00 UTC purge selects sandboxes CREATED more than 24 h ago, not sandboxes IDLE for more than 24 h: a trial in use at 03:00 is wiped if it started the day before | custom_demo/src/data.js:298 · visiteur ·  |  |  |
| ffdd3e5a8b | UNTRIAGED | HUB |   Same requirements, fictional data and codes, sandboxes that reset themselves. | the hub does not say the trial is reset after 24 h | demo/ · visiteur ·  |  |  |

### D1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 5fc012f744 | UNTRIAGED | A | Editing all the site’s pages: Works in the demo The standard WordPress page editor; your current pages are mov · `table.cmp` | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP undefined · no earlier test ID in wp_demo/README.md | demo/#compare · visiteur ·  |  |  |
| 9266a5db64 | UNTRIAGED | B | Works in the Option B demo | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») | demo/#group · visiteur ·  |  |  |

### D2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 4c31617d02 | UNTRIAGED | HUB | Founder, ProdCraftdebanjan@prodcraft.fyi · `footer.foot > div.container.foot__in > div.foot__sig > p` | real-looking e-mail « ProdCraftdebanjan@prodcraft.fyi » | https://asset-voyages-redesign.pages.dev/demo/ · visiteur · 390/1440 (4×) | out/shots/0006-HUB-visiteur-390-hub-demo.png |  |
| 760a3afa82 | UNTRIAGED | HUB | Congrès européen de radiologie — exemple · `ul.rows > li.row > div > p.row__t` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (8×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| 4fd467697d | UNTRIAGED | HUB | 01 55 57 29 00 · `section#contact > div.contact__grid > div.contact__side` | phone « 01 55 57 29 00 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (4×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| db25742a2c | UNTRIAGED | HUB | 58, rue Jean-Pierre Timbaud92130 Issy-les-Moulineaux01 55 57 29 00 · `footer.ftr > div > p` | phone « 01 55 57 29 00 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | https://asset-voyages-redesign.pages.dev/ · visiteur · 390/1440 (4×) | out/shots/0007-HUB-visiteur-390-hub.png |  |
| 56eec219c6 | UNTRIAGED | HUB | If we don’t hear back, we’ll assume: every enquiry goes to one shared mailbox (direction@assetvoyages.com until you name another), and the c · `li#q15 > span > span.qa` | real-looking e-mail « direction@assetvoyages.com » | https://asset-voyages-redesign.pages.dev/questions/ · visiteur · 390/1440 (4×) | out/shots/0010-HUB-visiteur-390-hub-questions.png |  |

### D3

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 297483d3c4 | UNTRIAGED | HUB | two · `d by ProdCraft ⏎  ⏎ Back to the concept ⏎ The ⟨two⟩ demos ⏎ Try it ⏎ Recordings ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (2×) |  |  |
| 1d7c6396a3 | UNTRIAGED | HUB | Two · `E codes ⏎ Milestones ⏎ Book a demonstration ⏎ ⟨Two⟩ working demos. Try both, cho` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (4×) |  |  |
| f5941be923 | UNTRIAGED | HUB | one · `ion ⏎ Two working demos. Try both, choose ⟨one⟩. ⏎  ⏎ Same requirements, fiction` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (13×) |  |  |
| 8342d57cde | UNTRIAGED | HUB | 20 to 30 · `t themselves. ⏎  ⏎ Open the demos ⏎ or book a ⟨20 to 30⟩ minute demonstration ⏎ ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (2×) |  |  |
| 9adfc2d3b6 | UNTRIAGED | HUB | 1 · `r book a 20 to 30 minute demonstration ⏎  ⏎ ⟨1⟩ Two options, both working ⏎  ⏎ Y` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (3×) |  |  |
| 71ff5cb971 | UNTRIAGED | HUB | twice · `s. Rather than describe it, we built it ⟨twice⟩, so you can try it yourselves an` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 9e825e84b8 | UNTRIAGED | HUB | five · `SSET. ⏎  ⏎ Both demos are built to the same ⟨five⟩ requirements from your consul` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (5×) |  |  |
| 3720ce61b8 | UNTRIAGED | HUB | 20 to 40 · `o install. ⏎  ⏎ The first start takes about ⟨20 to 40⟩ seconds while it loads. L` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| f12355073f | UNTRIAGED | HUB | 2 · ` congresses, which then wait for review ⏎ ⟨2⟩ Try it in five minutes ⏎  ⏎ Your f` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (4×) |  |  |
| 3d3b390c7c | UNTRIAGED | HUB | 4 · `n Option A and in Option B. Tasks 3 and ⟨4⟩ follow on from each other: send an e` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (4×) |  |  |
| 7bd7b4fa2a | UNTRIAGED | HUB | 24 · `giving a reason. Direction approves for ⟨24⟩ hours, or refuses. Each time a code` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (5×) |  |  |
| e999c45a75 | UNTRIAGED | HUB | 3 · `m: the five tasks from start to finish. ⏎ ⟨3⟩ What works today, and what we woul` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (3×) |  |  |
| 4e9c564547 | UNTRIAGED | HUB | 5 · `changes, export to a spreadsheet (CSV). ⏎ ⟨5⟩. GM&E codes protected	 ⏎ Works in ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  (3×) |  |  |
| 8e6c3b6dd9 | UNTRIAGED | HUB | 300 · `nstead of sending them. ⏎ Importing about ⟨300⟩ congresses from a spreadsheet	 ⏎` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 25fd4bda4c | UNTRIAGED | HUB | One · `s in the Option B demo ⏎ Suggestion only ⏎  ⏎ ⟨One⟩ more idea: a link for group ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 1ed36a958f | UNTRIAGED | HUB | Three · ` demo-asset. ⏎ Choose the « Groupe » tab. ⟨Three⟩ fictional travellers have alre` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 5b3fae2155 | UNTRIAGED | HUB | 6 · `pt in a record that Direction can read. ⏎ ⟨6⟩ Milestones ⏎  ⏎ Counted from your ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 5d53bdeca1 | UNTRIAGED | HUB | four · `2 ⏎  ⏎ For your team, with a second session ⟨four⟩ weeks after launch. ⏎  ⏎ Laun` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 9da6419756 | UNTRIAGED | HUB | Four · `ected to the new pages. ⏎  ⏎ Stabilisation ⏎  ⏎ ⟨Four⟩ weeks after launch ⏎  ⏎ W` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |
| 5e8e2d52e5 | UNTRIAGED | HUB | 7 · `d. The launch date is agreed together. ⏎  ⏎ ⟨7⟩ A 20 to 30 minute demonstration ` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |

### E1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 0a4659202b | UNTRIAGED | A-hosted | hosted ad48baa5759e ≠ local build f2db344e4d84 | the hub's Playground links install an older plugin than the current wp_demo/ code | demo-wordpress/asset-congres-demo.zip · visiteur ·  |  |  |

## C10 instruction replay

| Option | Task.step | OK | Clicks | Role | Why | Hub text |
|---|---|---|---|---|---|---|

## D1 claims

| Function | Option | Cell | OK | Evidence |
|---|---|---|---|---|
| 1. Create and edit congresses | A | Works in the demo In the standard WordPress editor, with review before | yes | this run: C10 T1 functional PASS · wp_demo/README.md: S1-F1, S1-F2, S1-F3, S1-E1, S1-E2, S1-H1, S1-H2 |
| 1. Create and edit congresses | B | Works in the demo In the team console, with review before publishing. | yes | this run: C10 T1 functional PASS · custom_demo/README.md: `s1_congress.spec.mjs` 5/5 pass |
| 2. Public catalogue with search, filters and details page | A | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · wp_demo/README.md: S2-F1, S2-F2, S2-F3, S2-F4, S2-F5, S2-F6, S2-E1, S2-E2, S2-H1 |
| 2. Public catalogue with search, filters and details page | B | Works in the demo Search, filters by discipline, country and month, a  | yes | this run: C10 T2 functional PASS · custom_demo/README.md: `s2_catalogue.spec.mjs` 9/9 pass |
| 3. Flight enquiry form | A | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · wp_demo/README.md: S3-F1, S3-F2, S3-F3, S3-F4, S3-E1, S3-H1, S3-H2, S3-H3 |
| 3. Flight enquiry form | B | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · custom_demo/README.md: `s3_enquiry.spec.mjs` 7/7 pass |
| 4. Receive, view, track and update enquiries | A | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · wp_demo/README.md: S4-F1, S4-F2, S4-F3, S4-F4, S4-F5, S4-F6, S4-E1, S4-H1 |
| 4. Receive, view, track and update enquiries | B | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · custom_demo/README.md: `s4_team.spec.mjs` 7/7 pass |
| 5. GM&E codes protected | A | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | yes | this run: C10 T5 functional PASS · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 |
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
| Editing all the site’s pages | A | Works in the demo The standard WordPress page editor; your current pag | NO | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP undefined · no earlier test ID in wp_demo/README.md |
| Editing all the site’s pages | B | Built during the project A page editor added to the team console. | yes | no UI label pretends it works |
| Group link (#group) | B | Works in the Option B demo | NO | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») |

## A2 hosted boots


## B6 glossary

| Term | A | B | Hub quotes |
|---|---|---|---|
| congress menu |  |  | Congrès |
| add a congress |  |  | Ajouter un congrès |
| list of congresses |  |  | Tous les congrès / Congrès |
| enquiries |  |  | Demandes |
| status new |  |  | Nouvelle |
| status qualified |  |  | Qualifiée |
| notification log |  |  | Journal des notifications |
| quote form title |  |  | Demander un devis vol |
| send the enquiry |  |  |  |
| team area link |  |  | Espace équipe |
| GM&E codes screen |  |  | Accès GM&E / Codes GM&E |
| ask for access |  |  |  |
| approve |  |  |  |
| show the code |  |  |  |
| access log |  |  |  |
| access requests |  |  |  |
| CSV export |  |  |  |
| sign out |  |  |  |
| sign in |  |  |  |
| dashboard |  |  |  |
| public catalogue |  |  |  |
| group tab |  |  | Groupe |
| group link card |  |  | Lien de groupe |
| group export |  |  | Exporter pour cotation (CSV) |

## Notes

