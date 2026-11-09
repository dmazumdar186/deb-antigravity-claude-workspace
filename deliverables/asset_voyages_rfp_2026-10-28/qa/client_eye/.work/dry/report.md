# Client-eye gate report

Generated 2026-11-06T08:30:38.718Z. Commit 8a0aeeb4afdd49ef3716350888f39a0c87b103c5. Spec: `28_PreMortem_Client_Eye_Gate.md`. Machine-readable: `report.json`. Triage verdicts: `triage.json`. Register: `../register/CLIENT_EYE.md`.

## Targets and versions

- Hub: 5 tasks parsed, group section present; demo/index.html deployed = source, index.html deployed = source, js/demo.js deployed = source, css/demo.css deployed = source
- Option B Worker: 9fdd6cb6-04fa-4d3a-a7ea-b2b7617bca32 deployed 2026-11-06T07:50:09.302386Z; custom_demo/src last commit d1c1942 2026-11-06T07:32:28+00:00
- Option A: local Playground  built from the current wp_demo/ (zip f2db344e4d84); hosted zip f2db344e4d84
- Uncommitted source changes at run time: none
- States captured: 151; widths 320, 390, 768, 1280, 1440, 1920; roles B:visiteur, B:contributeur, B:direction, B:equipe, B:voyageur
- Part b: run 2026-11-06T08:30:27.302Z, logins 9, writing contexts 2, own sandboxes 2

## Per check

| Check | Type | What | REAL | FALSE-POSITIVE | UNTRIAGED | Status |
|---|---|---|---|---|---|---|
| A1 | auto | E-mail draft: one short https link, 200, no Playground URL | 0 | 0 | 0 | PASS |
| A2 | auto | Boot time shown next to each Option A button; boot screen never blank (hosted boot measured) | 0 | 0 | 0 | PASS |
| A3 | auto | Text blacklist (will appear here, REPLACE, TODO, lorem, undefined, NaN, null, [object Object], {{, %s, XXX) in text and attributes | 0 | 0 | 0 | PASS |
| A4 | auto | Every anchor, src, href, poster, video source answers 200 (or 30x to 200) with the right content type; no mixed content | 0 | 0 | 8 | FAIL |
| A5 | auto | Videos: poster, controls, playsinline, preload=metadata, < 25 MB, faststart, decoded frames > 0 | 0 | 0 | 0 | PASS |
| A6 | auto | Meaningful <title> and a favicon that answers 200 | 0 | 0 | 0 | PASS |
| A7 | decision | Address bar shows « debanjan186 »: operator decision | 0 | 0 | 0 | OPERATOR DECISION |
| B1 | auto | No English in French screens (fr-FR and en-GB browsers); hub French only inside « » | 0 | 0 | 0 | PASS |
| B2 | auto | No ISO/US dates; jj/mm/aaaa valid; Paris time; 00:05 Paris clock probe | 0 | 0 | 16 | FAIL |
| B3 | auto | Plural agreement after 0, 1, 2 and many | 0 | 0 | 0 | PASS |
| B4 | auto | No mid-word breaks, no line starting with » ; : ! ? or ending with «, no orphan « — exemple » (320/390/768/1280/1440/1920) | 0 | 0 | 2 | FAIL |
| B5 | auto | Spell check fr + en (pyspellchecker) with a reasoned allowlist | 0 | 0 | 60 | FAIL |
| B6 | auto | Glossary of key labels: same names in the hub and both UIs | 0 | 0 | 31 | FAIL |
| B7 | auto | Missing accents / capitals on known words | 0 | 0 | 0 | PASS |
| C1 | auto | No 4xx/5xx, console or page errors in normal use; styled French error pages reached only on purpose | 0 | 0 | 8 | FAIL |
| C2 | auto | Every visible non-submit button changes something within 2 s; submit buttons exercised by the journeys | 0 | 0 | 1 | FAIL |
| C3 | auto | No empty box: every 0-item list shows a sentence | 0 | 0 | 0 | PASS |
| C4 | auto | CLS ≤ 0.02 per page | 0 | 0 | 0 | PASS |
| C5 | auto | One body family, one display family, one button style family, one accent colour per surface | 0 | 0 | 1 | FAIL |
| C6 | auto | No horizontal overflow (six widths); anchors not under the sticky header | 0 | 0 | 0 | PASS |
| C7 | auto | Expired session shows « Session expirée » + login link; purge only idle > 24 h; hub says private + 24 h reset | 0 | 0 | 5 | FAIL |
| C8 | auto | No technical residue (errors, stack, JSON braces, wp: markup, hex runs ≥ 16) in visible text | 0 | 0 | 0 | PASS |
| C9 | auto | No test residue in the sample data (fresh browsers) | 0 | 0 | 0 | PASS |
| C10 | auto | Instruction replay: each hub step followed literally by visible labels | 0 | 0 | 2 | FAIL |
| D1 | auto | Every « Works in the demo » cell backed by evidence; « Built during the project » not faked by UI | 0 | 0 | 4 | FAIL |
| D2 | auto | Fictional people: @example.com, fiction phone ranges, no real congress names | 0 | 0 | 19 | FAIL |
| D3 | auto | Every number on the hub is a week, a date, our demo data, or traced to a source line | 0 | 0 | 1 | FAIL |
| D4 | auto | No GM&E code in DOM, attributes or inputs outside an approved reveal | 0 | 0 | 0 | PASS |
| E1 | auto | Report names the commit and deployed versions; hub links checked against live versions | 0 | 0 | 0 | PASS |
| E2 | process | Full suites twice green after every change; this gate runs last | 0 | 0 | 0 | HUMAN/PROCESS |
| E3 | auto | Screenshots taken by this run from fresh contexts on the deployed sites | 0 | 0 | 0 | PASS |
| E4 | n/a | WebKit and Firefox | 0 | 0 | 0 | N/A |
| E5 | auto | Every check at 390 and 1440; B4/C6 at six widths | 0 | 0 | 0 | PASS |

## Check notes

- **E4** N/A: Only Chromium is installed (.links, chromium, chromium-1243, chromium_headless_shell-1243, ffmpeg-1011); Firefox and WebKit are not, and the brief forbids installing them. Recorded N/A, never PASS.
- **A7** OPERATOR DECISION: Option B's address is http://localhost:8799 (contains « debanjan186 »). Accepted unless the operator asks for a custom domain.
- **E2** HUMAN/PROCESS: The suites (wp_demo/tests/run_all.sh, custom_demo playwright) must run twice green after the last change; this gate does not run them. It runs last, on the deployed versions named above.
- **E3** PASS: 115 screenshots, all written by this gate from fresh browser contexts on the deployed hub and Option B and the local Option A build.
- **E5** PASS: B: 320/390/768/1280/1440/1920. The hosted Option A boot is one boot per link at 1440 by design (brief).

## Findings

### A4

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 71a41e6fe7 | UNTRIAGED | B | https://www.example.org/congres/cg-0112 · `a « www.example.org/congres/cg-0112 »` | HTTP 404 | http://localhost:8799/congres/journees-d-oncologie-digestive-cg-0112 · visiteur ·  |  |  |
| 372069b58f | UNTRIAGED | B | http://localhost:8799/cette-page-n-existe-pas · `a « Aller au contenu »` | HTTP 404 | http://localhost:8799/cette-page-n-existe-pas · visiteur ·  |  |  |
| 93f245eca3 | UNTRIAGED | B | http://localhost:8799/congres/congres-inexistant-cg-9999 · `a « Aller au contenu »` | HTTP 404 | http://localhost:8799/congres/congres-inexistant-cg-9999 · visiteur ·  |  |  |
| 90e44763d3 | UNTRIAGED | B | http://localhost:8799/g/lien-invalide · `a « Aller au contenu »` | HTTP 404 | http://localhost:8799/g/lien-invalide · visiteur ·  |  |  |
| 13fdb4305d | UNTRIAGED | B | http://localhost:8799/congres/congres-de-relecture-om3i-cg-0114 · `a « Voir la fiche publique »` | HTTP 404 | http://localhost:8799/console/congres/114?ok=publish · visiteur ·  |  |  |
| 12317546a0 | UNTRIAGED | B | https://www.example.org/relecture · `a « www.example.org/relecture »` | HTTP 404 | http://localhost:8799/congres/congres-de-relecture-om3i-cg-0114 · visiteur ·  |  |  |
| 52da26a502 | UNTRIAGED | B | https://www.example.org/congres/cg-0108 · `a « www.example.org/congres/cg-0108 »` | HTTP 404 | http://localhost:8799/demande · visiteur ·  |  |  |
| 8961c524f3 | UNTRIAGED | B | http://localhost:8799/demande · `a « Aller au contenu »` | HTTP 404 | http://localhost:8799/demande · visiteur ·  |  |  |

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
| cd266b3a95 | UNTRIAGED | B | voyer aux 6 participants : chacun r · `section#lien-groupe > p.quiet` | line-starts-with-: | http://localhost:8799/console/demandes/1 · equipe · 390 (2×) |  |  |
| 59381427af | UNTRIAGED | B | voyer aux 4 participants : chacun r · `section#lien-groupe > p.quiet` | line-starts-with-: | http://localhost:8799/console/demandes/6 · equipe · 390 | .work/dry/shots/0133-B-equipe-390-equipe-console-demandes-6-390.png |  |

### B5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 4f9af3e470 | UNTRIAGED | B | Alice · `fr` | unknown fr word in « Alice Martin (exemple) » (14×) | http://localhost:8799/console/demandes/1/groupe · equipe · 1440 |  |  |
| c5fbcb1066 | UNTRIAGED | B | Allemagne · `fr` | unknown fr word in « Allemagne » (28×) | http://localhost:8799/ · visiteur · 320 |  |  |
| b4bbd91c8e | UNTRIAGED | B | Amsterdam · `fr` | unknown fr word in « Amsterdam, Pays-Bas » (14×) | http://localhost:8799/ · visiteur · 320 |  |  |
| d1fe5839a3 | UNTRIAGED | B | Ariane · `fr` | unknown fr word in « Fil d’Ariane » (42×) | http://localhost:8799/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |
| 8c9f11447a | UNTRIAGED | B | avr · `fr` | unknown fr word in « 13 au 14 avr. 2027 » (9×) | http://localhost:8799/ · visiteur · 320 |  |  |
| 676b67d08b | UNTRIAGED | B | Benali · `fr` | unknown fr word in « Karim Benali, Équipe ASSET : congrès et demandes ; codes GM&E masqués, accès sur demande. » (114×) | http://localhost:8799/console/connexion · visiteur · 390 |  |  |
| ea4a22bcba | UNTRIAGED | B | Berlin · `fr` | unknown fr word in « Berlin » (6×) | http://localhost:8799/console/congres · contributeur · 1440 |  |  |
| 81b221b5ec | UNTRIAGED | B | Bruno · `fr` | unknown fr word in « Bruno Leroy (exemple) » (14×) | http://localhost:8799/console/demandes/1/groupe · equipe · 1440 |  |  |
| 9111bed219 | UNTRIAGED | B | Camille · `fr` | unknown fr word in « Camille Laurent (exemple) Laboratoire A (exemple) » (19×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| 7a5273a7f9 | UNTRIAGED | B | Chicago · `fr` | unknown fr word in « Chicago, États-Unis » (13×) | http://localhost:8799/?q=cardiologie · visiteur · 390 |  |  |
| f94b13e9aa | UNTRIAGED | B | chloe · `fr` | unknown fr word in « chloe.petit @example .com » (3×) | http://localhost:8799/console/demandes/1/groupe · equipe · 320 |  |  |
| b1f11ffd8d | UNTRIAGED | B | Chloé · `fr` | unknown fr word in « Chloé Petit (exemple) » (11×) | http://localhost:8799/console/demandes/1/groupe · equipe · 1440 |  |  |
| 3754c42eb1 | UNTRIAGED | B | com · `fr` | unknown fr word in « alice.martin @example .com » (7×) | http://localhost:8799/console/demandes/1/groupe · equipe · 320 |  |  |
| 3e41910553 | UNTRIAGED | B | Dubois · `fr` | unknown fr word in « Claire Dubois (exemple) claire.dubois @example.com » (23×) | http://localhost:8799/console/demandes · equipe · 1440 |  |  |
| 352238db56 | UNTRIAGED | B | Durand · `fr` | unknown fr word in « Sophie Durand (exemple) » (11×) | http://localhost:8799/g/YFp_InKpTZuk_ZeF3efZlyfHZ3fGOKrOtagMmZKbXF0/merci?d=bGEJZYvoFdmM.1793957326.wpmPuB_OVwep71izOxblVHxN9sqmmWWnLC-dDvlsuoI · voyageur · 1440 |  |  |
| 8d346542cd | UNTRIAGED | B | démo · `fr` | unknown fr word in « Réinitialiser la démo » (2×) | http://localhost:8799/console · direction · 1440 |  |  |
| 777d1351eb | UNTRIAGED | B | E-mail · `fr` | unknown fr word in « E-mail * » (146×) | http://localhost:8799/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |
| c8dcc2d3d5 | UNTRIAGED | B | Events · `fr` | unknown fr word in « Codes tarifaires Air France-KLM Global Meetings & Events, chiffrés en base. Chaque affichage est enregistré. Pour ajoute » (2×) | http://localhost:8799/console/gme · direction · 1440 |  |  |
| a873cfd378 | UNTRIAGED | B | example · `fr` | unknown fr word in « alice.martin @example .com » (7×) | http://localhost:8799/console/demandes/1/groupe · equipe · 320 |  |  |
| 56a1ddcd00 | UNTRIAGED | B | févr · `fr` | unknown fr word in « 24 au 28 févr. 2027 » (12×) | http://localhost:8799/ · visiteur · 320 |  |  |
| c671e7ed82 | UNTRIAGED | B | Garnier · `fr` | unknown fr word in « Léa Garnier (exemple) » (28×) | http://localhost:8799/console · direction · 1440 |  |  |
| b4de9f91a3 | UNTRIAGED | B | Gastro-entérologie · `fr` | unknown fr word in « Gastro-entérologie » (8×) | http://localhost:8799/console/congres/nouveau · contributeur · 1440 |  |  |
| c721805a9c | UNTRIAGED | B | Hugo · `fr` | unknown fr word in « Hugo Martin (exemple) » (18×) | http://localhost:8799/console · direction · 1440 |  |  |
| cf854b5338 | UNTRIAGED | B | Hélène · `fr` | unknown fr word in « Hélène Martin, Direction ASSET : tout, y compris les codes GM&E et les autorisations. » (119×) | http://localhost:8799/console/connexion · visiteur · 390 |  |  |
| b4dfb8e4ce | UNTRIAGED | B | interventionnelle · `fr` | unknown fr word in « Imagerie diagnostique et interventionnelle, intelligence artificielle en radiologie. Fiche d’exemple pour la démonstrati » (2×) | http://localhost:8799/console/congres/108 · direction · 1440 |  |  |
| 038f7abc36 | UNTRIAGED | B | Inès · `fr` | unknown fr word in « Inès Moreau (exemple) » (23×) | http://localhost:8799/console · direction · 1440 |  |  |
| 29a4ed7ed9 | UNTRIAGED | B | janv · `fr` | unknown fr word in « 28 au 30 janv. 2027 » (48×) | http://localhost:8799/ · visiteur · 320 |  |  |
| c62a54efe1 | UNTRIAGED | B | juil · `fr` | unknown fr word in « 5 au 7 juil. 2027 » (5×) | http://localhost:8799/console/congres · direction · 1440 |  |  |
| 6b4c8ad66f | UNTRIAGED | B | Julie · `fr` | unknown fr word in « Julie Roux, contributrice : prépare des brouillons et les soumet à relecture, sans publier. » (23×) | http://localhost:8799/console/connexion · visiteur · 390 |  |  |
| 8b0a78d656 | UNTRIAGED | B | Karim · `fr` | unknown fr word in « Karim Benali, Équipe ASSET : congrès et demandes ; codes GM&E masqués, accès sur demande. » (114×) | http://localhost:8799/console/connexion · visiteur · 390 |  |  |
| a71a8d61b7 | UNTRIAGED | B | Laurent · `fr` | unknown fr word in « Camille Laurent (exemple) Laboratoire A (exemple) » (19×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| 1d6234cba4 | UNTRIAGED | B | lea · `fr` | unknown fr word in « Léa Garnier (exemple) lea.garnier @example.com » (6×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| 5d91297f68 | UNTRIAGED | B | Lefebvre · `fr` | unknown fr word in « Paul Lefebvre (exemple) » (22×) | http://localhost:8799/console · direction · 1440 |  |  |
| 2f7bff35e4 | UNTRIAGED | B | Leroy · `fr` | unknown fr word in « Bruno Leroy (exemple) » (14×) | http://localhost:8799/console/demandes/1/groupe · equipe · 1440 |  |  |
| 1e1e084cc4 | UNTRIAGED | B | Lille · `fr` | unknown fr word in « Départ de Lille 27/01/2027 au 31/01/2027 6 passagers » (52×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| f72adf1d2c | UNTRIAGED | B | Lisbonne · `fr` | unknown fr word in « Lisbonne, Portugal » (15×) | http://localhost:8799/ · visiteur · 320 |  |  |
| 33453f9c36 | UNTRIAGED | B | Londres · `fr` | unknown fr word in « Londres » (6×) | http://localhost:8799/console/congres · contributeur · 1440 |  |  |
| b8328bafd8 | UNTRIAGED | B | Lyon · `fr` | unknown fr word in « Lyon, France » (29×) | http://localhost:8799/ · visiteur · 320 |  |  |
| 8eaf16068c | UNTRIAGED | B | Léa · `fr` | unknown fr word in « Léa Garnier (exemple) » (22×) | http://localhost:8799/console · direction · 1440 |  |  |
| d37fcb95aa | UNTRIAGED | B | Madrid · `fr` | unknown fr word in « Madrid, Espagne » (20×) | http://localhost:8799/ · visiteur · 320 |  |  |
| 5be7d460ee | UNTRIAGED | B | Marseille · `fr` | unknown fr word in « Marseille, France » (46×) | http://localhost:8799/ · visiteur · 320 |  |  |
| b8fe7e411b | UNTRIAGED | B | Martin · `fr` | unknown fr word in « Hélène Martin, Direction ASSET : tout, y compris les codes GM&E et les autorisations. » (154×) | http://localhost:8799/console/connexion · visiteur · 390 |  |  |
| 55f8d4486b | UNTRIAGED | B | Moreau · `fr` | unknown fr word in « Inès Moreau (exemple) » (23×) | http://localhost:8799/console · direction · 1440 |  |  |
| 35b57299c7 | UNTRIAGED | B | Nantes · `fr` | unknown fr word in « Départ de Nantes 26/08/2027 au 31/08/2027 12 passagers » (14×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| 7a37a81450 | UNTRIAGED | B | Nathan · `fr` | unknown fr word in « Nathan Roux (exemple) » (23×) | http://localhost:8799/console · direction · 1440 |  |  |
| b08cb87340 | UNTRIAGED | B | Nice · `fr` | unknown fr word in « Nice » (6×) | http://localhost:8799/console/congres · direction · 1440 |  |  |
| 63cbe47411 | UNTRIAGED | B | nov · `fr` | unknown fr word in « 13 au 16 nov. 2027 » (15×) | http://localhost:8799/?q=cardiologie · visiteur · 390 |  |  |
| c86bbe1f7b | UNTRIAGED | B | oct · `fr` | unknown fr word in « 29 sept. au 2 oct. 2027 » (20×) | http://localhost:8799/ · visiteur · 320 |  |  |
| d8a4545a74 | UNTRIAGED | B | Oncologie · `fr` | unknown fr word in « Oncologie » (194×) | http://localhost:8799/ · visiteur · 320 |  |  |
| a10a2b6d7b | UNTRIAGED | B | Paul · `fr` | unknown fr word in « Paul Lefebvre (exemple) » (22×) | http://localhost:8799/console · direction · 1440 |  |  |
| 5cf3422791 | UNTRIAGED | B | Pharo · `fr` | unknown fr word in « Palais du Pharo — exemple » (10×) | http://localhost:8799/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |
| 2fc8a08858 | UNTRIAGED | B | Pneumologie · `fr` | unknown fr word in « Pneumologie » (52×) | http://localhost:8799/ · visiteur · 320 |  |  |
| 35a173046c | UNTRIAGED | B | PubliéVoir · `fr` | unknown fr word in « PubliéVoir la fiche publique » (4×) | http://localhost:8799/console/congres/114?ok=publish · direction · 1440 |  |  |
| 12c3353a90 | UNTRIAGED | B | recontacte · `fr` | unknown fr word in « Demande de devis vol pour Journées d’oncologie digestive — exemple. Un conseiller ASSET vous recontacte avec une proposi » (2×) | http://localhost:8799/demande/confirmation?ref=DV-2026-0007&k=D8xkkBs2448DQxpEaR7nN1 · direction · 1440 |  |  |
| f1a47ae77c | UNTRIAGED | B | rhumatologie · `fr` | unknown fr word in « Journées de rhumatologie — exemple » (15×) | http://localhost:8799/console/congres · contributeur · 1440 |  |  |
| 68ce94366c | UNTRIAGED | B | Réf · `fr` | unknown fr word in « Réf. » (8×) | http://localhost:8799/console/congres · contributeur · 1440 |  |  |
| 4a3acb083f | UNTRIAGED | B | Sophie · `fr` | unknown fr word in « Sophie Durand (exemple) » (11×) | http://localhost:8799/g/YFp_InKpTZuk_ZeF3efZlyfHZ3fGOKrOtagMmZKbXF0/merci?d=bGEJZYvoFdmM.1793957326.wpmPuB_OVwep71izOxblVHxN9sqmmWWnLC-dDvlsuoI · voyageur · 1440 |  |  |
| c8e77a808d | UNTRIAGED | B | Toulouse · `fr` | unknown fr word in « Départ de Toulouse 22/03/2027 au 26/03/2027 2 passagers » (11×) | http://localhost:8799/console/demandes · direction · 1440 |  |  |
| b9074fd554 | UNTRIAGED | B | Urologie · `fr` | unknown fr word in « Urologie » (8×) | http://localhost:8799/console/congres/nouveau · contributeur · 1440 |  |  |
| edc783bab3 | UNTRIAGED | B | www · `fr` | unknown fr word in « www.example.org/congres/cg-0112 » (12×) | http://localhost:8799/congres/journees-d-oncologie-digestive-cg-0112 · visiteur · 320 |  |  |

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

### C1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| ff9eed1328 | UNTRIAGED | B | Failed to load resource: the server responded with a status of 404 (Not Found) · `console` | during error 404 public | http://localhost:8799/cette-page-n-existe-pas · visiteur · 390/1440 (4×) |  |  |
| c5fb19b5da | UNTRIAGED | B | Failed to load resource: the server responded with a status of 404 (Not Found) · `console` | during error 404 congress | http://localhost:8799/congres/congres-inexistant-cg-9999 · visiteur · 390/1440 (4×) |  |  |
| eecf8299c2 | UNTRIAGED | B | Failed to load resource: the server responded with a status of 404 (Not Found) · `console` | during error group link unknown | http://localhost:8799/g/lien-invalide · visiteur · 390/1440 (4×) |  |  |
| a2b34c4cfc | UNTRIAGED | B | 404 document http://localhost:8799/console/listes · `http` | during /console/listes | http://localhost:8799/console/listes · direction · 1440 |  |  |
| 514a2896c4 | UNTRIAGED | B | Failed to load resource: the server responded with a status of 404 (Not Found) · `console` | during /console/listes | http://localhost:8799/console/listes · direction · 1440 |  |  |
| ef1277fb52 | UNTRIAGED | B | Failed to load resource: the server responded with a status of 401 (Unauthorized) · `console` | during expired | http://localhost:8799/console/demandes/6 · equipe · 390 |  |  |
| c568345bfb | UNTRIAGED | B | 404 document http://localhost:8799/console/listes · `http` | during reset 390 | http://localhost:8799/console/listes · direction · 390 |  |  |
| 2ff0aaaaab | UNTRIAGED | B | Failed to load resource: the server responded with a status of 404 (Not Found) · `console` | during reset 390 | http://localhost:8799/console/listes · direction · 390 |  |  |

### C2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 7d15d29c7d | UNTRIAGED | B | Copier le lien · `button` | no navigation, no DOM change within 2 s | http://localhost:8799/console/demandes/1 · equipe · 390 (2×) |  |  |

### C5

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 41b4bf5573 | UNTRIAGED | B-console | EB Garamond (login page); Inter (direction /console/notifications) | 2 display font families | B-console · visiteur ·  |  |  |

### C7

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| ec6902d336 | UNTRIAGED | B | Aller au contenu \| ASSET \| Voyages \| Démonstration avec des données fictives | after the session ends, a form sent from an open tab shows no « Session expirée » message | http://localhost:8799/console/demandes/6 · equipe · 390 | .work/dry/shots/0134-B-equipe-390-C7-expired-session-stale-form-submitted.png |  |
| aa7b325632 | UNTRIAGED | B | Aller au contenu \| ASSET \| Voyages | session cookie __Host-av_session gone: the reader is sent to the login page with no « Session expirée » message | http://localhost:8799/console/connexion?next=%2Fconsole%2Fdemandes · equipe · 390 | .work/dry/shots/0135-B-equipe-390-C7-expired-session-next-navigation.png |  |
| 4005f28b67 | UNTRIAGED | B | SELECT id FROM sandboxes WHERE created_at < ?1 ORDER BY created_at LIMIT ${PURGE_SANDBOXES} · `source` | the 03:00 UTC purge selects sandboxes CREATED more than 24 h ago, not sandboxes IDLE for more than 24 h: a trial in use at 03:00 is wiped if it started the day before | custom_demo/src/data.js:298 · visiteur ·  |  |  |
| 751798daf3 | UNTRIAGED | HUB |   Same requirements, fictional data and codes, sandboxes that reset themselves. | the hub does not say that each trial is private | demo/ · visiteur ·  |  |  |
| ffdd3e5a8b | UNTRIAGED | HUB |   Same requirements, fictional data and codes, sandboxes that reset themselves. | the hub does not say the trial is reset after 24 h | demo/ · visiteur ·  |  |  |

### C10

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 9be18199d7 | UNTRIAGED | B | T2 step 2: Type a word in the search box, or narrow the list by discipline, country or month. · `instruction replay` | filters not visible by label: Discipline (hub says discipline, country, month) | http://localhost:8799/?q=cardiologie&pays=&mois=#resultats · direction · 1440 | .work/dry/shots/0065-B-direction-1440-C10-T2-2.png |  |
| 2f88445db5 | UNTRIAGED | B | T5 step 3: Sign in as equipe again: the code is shown, and the access record lists it. · `instruction replay` | label « Codes » not visible | http://localhost:8799/console · equipe · 1440 | .work/dry/shots/0080-B-equipe-1440-C10-T5-3.png |  |

### D1

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 5fc012f744 | UNTRIAGED | A | Editing all the site’s pages: Works in the demo The standard WordPress page editor; your current pages are mov · `table.cmp` | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP undefined · no earlier test ID in wp_demo/README.md | demo/#compare · visiteur ·  |  |  |
| 296513c7ed | UNTRIAGED | B | 2. Public catalogue with search, filters and details page: Works in the demo Search, filters by discipline, country and month, a page per c · `table.cmp` | this run: C10 T2 FAIL · custom_demo/README.md: `s2_catalogue.spec.mjs` 9/9 pass | demo/#compare · visiteur ·  |  |  |
| a2cd02abc4 | UNTRIAGED | B | 5. GM&E codes protected: Works in the demo Codes hidden, access asked with a reason, 24-hour approval, a  · `table.cmp` | this run: C10 T5 FAIL · custom_demo/README.md: `s5_gme.spec.mjs` 11/11 pass | demo/#compare · visiteur ·  |  |  |
| 9266a5db64 | UNTRIAGED | B | Works in the Option B demo | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») | demo/#group · visiteur ·  |  |  |

### D2

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| ed34769f19 | UNTRIAGED | B | Congrès européen de radiologie — exemple · `li.row > a.row__a > span.row__main > span.row__t` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/ · visiteur · 390/1440 (32×) | .work/dry/shots/0003-B-visiteur-390-catalogue.png |  |
| c3cf241814 | UNTRIAGED | B | Congrès mondial de neurologie — exemple · `li.row > a.row__a > span.row__main > span.row__t` | matches a real congress name « congres mondial de neurologie » (marked as an example in the same text) | http://localhost:8799/ · visiteur · 390/1440 (11×) | .work/dry/shots/0003-B-visiteur-390-catalogue.png |  |
| 366f3a475a | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0006 Congrès : Congrès international d’oncologie — exemple (C · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 06 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| 758a709e2b | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0005 Congrès : Rencontres d’ophtalmologie — exemple (CG-0107) · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 05 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| 25aa23b767 | UNTRIAGED | B | Nouvelle demande DV-2026-0004 : Congrès européen de radiologie — exemple · `main#main > ol.mails > li.card.mail > h2.h4` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| 9d67d05a8a | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0004 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 04 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| d729e5e7e8 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0004 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| 4128df0104 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0003 Congrès : Congrès européen de cardiologie — exemple (CG- · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 03 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| add580994c | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0002 Congrès : Journées françaises de diabétologie — exemple  · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 02 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| dcd5757ebb | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0001 Congrès : Journées d’oncologie digestive — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | phone « 01 23 45 67 01 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/notifications · direction · 1440/390 (5×) | .work/dry/shots/0056-B-direction-1440-direction-console-notifications.png |  |
| 40ad4ededf | UNTRIAGED | B | 01 23 45 67 03 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 03 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/demandes/3 · direction · 1440 | .work/dry/shots/0063-B-direction-1440-direction-console-demandes-3.png |  |
| d9c61236fd | UNTRIAGED | B | 01 23 45 67 01 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 01 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/demandes/1 · equipe · 1440/390 (2×) | .work/dry/shots/0081-B-equipe-1440-C10-G-1.png |  |
| b2d6ade1c6 | UNTRIAGED | B | E-mail : Cette adresse e-mail n’est pas valide (exemple : prenom.nom@societe.fr). · `div#form-errors > ul > li` | real-looking e-mail « prenom.nom@societe.fr » | http://localhost:8799/demande · visiteur · 390 | .work/dry/shots/0119-B-visiteur-390-enquiry-errors-390.png |  |
| 0f9810b903 | UNTRIAGED | B | Congrès européen de radiologie — exemple, 24 au 28 févr. 2027 · `aside#demande > form.form > div.field.field--full > p.form__cg-v` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/demande · visiteur · 390 | .work/dry/shots/0119-B-visiteur-390-enquiry-errors-390.png |  |
| d8d07bb291 | UNTRIAGED | B | Cette adresse e-mail n’est pas valide (exemple : prenom.nom@societe.fr). · `p#f-email-e` | real-looking e-mail « prenom.nom@societe.fr » | http://localhost:8799/demande · visiteur · 390 | .work/dry/shots/0119-B-visiteur-390-enquiry-errors-390.png |  |
| d4567b5cf3 | UNTRIAGED | B | Demande de devis vol pour Congrès européen de radiologie — exemple. Un conseiller ASSET vous recontacte avec une proposition ; gardez cette  · `main#main > section.thanks > p` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/demande/confirmation?ref=DV-2026-0007&k=D8xkkBs2448DQxpEaR7nN1 · visiteur · 390 | .work/dry/shots/0120-B-visiteur-390-enquiry-confirmation-390.png |  |
| f5a5a12b6f | UNTRIAGED | B | Nouvelle demande DV-2026-0007 : Congrès européen de radiologie — exemple · `main#main > ol.mails > li.card.mail > h2.h4` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/console/notifications · equipe · 390 (2×) | .work/dry/shots/0129-B-equipe-390-equipe-390-console-notifications.png |  |
| 127fb4fb39 | UNTRIAGED | B | Une nouvelle demande de devis vol est arrivée sur le site. Référence : DV-2026-0007 Congrès : Congrès européen de radiologie — exemple (CG-0 · `main#main > ol.mails > li.card.mail > pre` | matches a real congress name « congres europeen de radiologie » (marked as an example in the same text) | http://localhost:8799/console/notifications · equipe · 390 (2×) | .work/dry/shots/0129-B-equipe-390-equipe-390-console-notifications.png |  |
| abee61f38a | UNTRIAGED | B | 01 23 45 67 06 · `section.card > dl.facts.facts--tight > div > dd` | phone « 01 23 45 67 06 » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked | http://localhost:8799/console/demandes/6 · equipe · 390 | .work/dry/shots/0133-B-equipe-390-equipe-console-demandes-6-390.png |  |

### D3

| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |
|---|---|---|---|---|---|---|---|
| 9e825e84b8 | UNTRIAGED | HUB | five · ` which then wait for review ⏎ 2 Try it in ⟨five⟩ minutes ⏎  ⏎ Your five requirem` | number not classified (week, date, our demo data) and not traced to a source line | demo/ · visiteur ·  |  |  |

## C10 instruction replay

| Option | Task.step | OK | Clicks | Role | Why | Hub text |
|---|---|---|---|---|---|---|
| B | T1.1 | yes | 1 | contributeur |  | Open the team console and sign in as contributeur. |
| B | T1.2 | yes | 2 | contributeur |  | Open the list of congresses and add a new one, or open an existing one to change it. |
| B | T1.3 | yes | 6 | direction |  | Send it for review. Sign in as direction to check it and publish it. |
| B | T2.1 | yes | 1 | direction |  | Open the visitor site and go to the congress catalogue. |
| B | T2.2 | NO | 1 | direction | filters not visible by label: Discipline (hub says discipline, country, month) | Type a word in the search box, or narrow the list by discipline, country or month. |
| B | T2.3 | yes | 1 | direction |  | Open a congress to see its details page: dates, city, venue and discipline. |
| B | T3.1 | yes | 0 | direction | form already open on the page (0 clicks) | On a congress details page, open the flight enquiry form. |
| B | T3.2 | yes | 0 | direction |  | Enter your contact details, departure city, travel dates and number of passengers. |
| B | T3.3 | yes | 1 | direction |  | Send it. You receive a reference number on screen. |
| B | T4.1 | yes | 2 | equipe |  | Open the team console, sign in as equipe and open the enquiries. |
| B | T4.2 | yes | 2 | equipe |  | Open your enquiry from task 3 and change its status. Each change is kept in its history. |
| B | T4.3 | yes | 3 | equipe | CSV demandes-2026-11-06.csv | Export the list as a spreadsheet file (CSV), and see the log of notifications your team would have received. |
| B | T5.1 | yes | 2 | equipe |  | In the team console, sign in as equipe and open « Codes GM&E »: the codes are hidden. Ask for access and give a reason. |
| B | T5.2 | yes | 4 | direction |  | Sign out, sign in as direction, and approve for 24 hours or refuse. |
| B | T5.3 | NO | 2 | equipe | label « Codes » not visible | Sign in as equipe again: the code is shown, and the access record lists it. |
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
| 2. Public catalogue with search, filters and details page | B | Works in the demo Search, filters by discipline, country and month, a  | NO | this run: C10 T2 FAIL · custom_demo/README.md: `s2_catalogue.spec.mjs` 9/9 pass |
| 3. Flight enquiry form | A | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · wp_demo/README.md: S3-F1, S3-F2, S3-F3, S3-F4, S3-E1, S3-H1, S3-H2, S3-H3 |
| 3. Flight enquiry form | B | Works in the demo Every field is checked before sending; you get a ref | yes | this run: C10 T3 functional PASS · custom_demo/README.md: `s3_enquiry.spec.mjs` 7/7 pass |
| 4. Receive, view, track and update enquiries | A | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · wp_demo/README.md: S4-F1, S4-F2, S4-F3, S4-F4, S4-F5, S4-F6, S4-E1, S4-H1 |
| 4. Receive, view, track and update enquiries | B | Works in the demo Statuses, history of changes, export to a spreadshee | yes | this run: C10 T4 functional PASS · custom_demo/README.md: `s4_team.spec.mjs` 7/7 pass |
| 5. GM&E codes protected | A | Works in the demo Codes hidden, access asked with a reason, 24-hour ap | yes | this run: C10 T5 functional PASS · wp_demo/README.md: S5-F1, S5-F2, S5-F3, S5-F4, S5-F5, S5-E1, S5-H1, S5-L1, S5-L2 |
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
| Editing all the site’s pages | A | Works in the demo The standard WordPress page editor; your current pag | NO | this run (gate test CE-D1-PAGES): direction opens « Pages » (edit.php?post_type=page) HTTP undefined · no earlier test ID in wp_demo/README.md |
| Editing all the site’s pages | B | Built during the project A page editor added to the team console. | yes | no UI label pretends it works |
| Group link (#group) | B | Works in the Option B demo | NO | this run: G steps PASS · custom_demo/README.md extra_group.spec.mjs G-F1..G-X3 (README says « not deployed ») |

## A2 hosted boots


## B6 glossary

| Term | A | B | Hub quotes |
|---|---|---|---|
| congress menu |  | Congrès | Congrès |
| add a congress |  | Nouveau congrès / Ajouter | Ajouter un congrès |
| list of congresses |  | Congrès | Tous les congrès / Congrès |
| enquiries |  | Demandes / Toutes les demandes | Demandes |
| status new |  | Nouvelle | Nouvelle |
| status qualified |  | Qualifiée | Qualifiée |
| notification log |  | Notifications | Journal des notifications |
| quote form title |  | Demande de devis vol | Demander un devis vol |
| send the enquiry |  | Envoyer la demande |  |
| team area link |  | Espace équipe | Espace équipe |
| GM&E codes screen |  | Codes GM&E / Codes | Accès GM&E / Codes GM&E |
| ask for access |  | Demander l’accès |  |
| approve |  | Approuver pour 24 h |  |
| show the code |  | Afficher le code |  |
| access log |  | Journal / Journal d’accès |  |
| access requests |  | Demandes d’accès |  |
| CSV export |  | Exporter (tableur CSV) / Exporter |  |
| sign out |  | Se déconnecter |  |
| sign in |  | Se connecter |  |
| dashboard |  | Tableau de bord |  |
| public catalogue |  | Catalogue des congrès |  |
| group tab |  | Groupe | Groupe |
| group link card |  | Lien de groupe | Lien de groupe |
| group export |  | Exporter pour cotation (CSV) | Exporter pour cotation (CSV) |

## Notes

- traveller phone sandbox cookie: TQAtcuGkLcZYWMTHqmunvzy_
