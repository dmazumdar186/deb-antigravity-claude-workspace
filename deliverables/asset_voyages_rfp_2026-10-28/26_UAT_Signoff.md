# Internal UAT sign-off: ASSET demonstration

This is internal UAT, run by ProdCraft. The client's own UAT is part of the project (T01–T15). There is one scenario per story, covering the visitor side and the team side. The steps are written so that Veena, or anyone at ASSET, can follow them without help. Screen labels are quoted exactly as they appear, in French.

## Option B: custom platform

**Where:** https://asset-voyages-demo.debanjan186.workers.dev. The team console is at `/console`.

**Logins** (the password is `demo-asset` for all three):
- `direction`: Hélène Martin
- `equipe`: Karim Benali
- `contributeur`: Julie Roux

**Before you start:**
- Each browser gets its own private sandbox, so your tests are seen only by you.
- To start clean, log in as `direction` and click « Réinitialiser la démo » on « Tableau de bord ».
- All data is fictional. Codes look like `DEMO-GME-…`.

**Run:** 5 Nov 2026 (first run), re-run 6 Nov 2026 on live Worker version `29d23da1-4707-436e-8b91-dbdb96fd844c`, by an internal reviewer acting as a first-time office assistant. Each step was run twice: in a desktop browser (1440 px) and a phone-size browser (390 px), in French. Evidence for each step is a screenshot `qa/B/ux/evidence/uat-<1440|390>-<step>.png` plus the log lines in `qa/B/ux/uat1440.log` and `qa/B/ux/uat390.log`. Reference numbers below come from the 1440 run.

### Scenario 1: create and edit a congress (S1)

| # | Step | Expected | 1440 | 390 | Evidence (1440 log) |
|---|---|---|---|---|---|
| 1.1 | Open `/console`. Type `direction` in « Identifiant » and `demo-asset` in « Mot de passe », then click « Se connecter ». | « Tableau de bord » opens. | PASS | PASS | « Tableau de bord » |
| 1.2 | In the menu, click « Congrès », then « Nouveau congrès ». | An empty form opens with French labels, and every required field has a *. | PASS | PASS | 9 labels marked * |
| 1.3 | Fill in « Titre » (e.g. `Congrès test — exemple`), « Discipline », « Lieu », « Ville », « Pays », « Date de début », « Date de fin », « Site officiel » (starting `https://`) and « Vérifié le ». Click « Publier ». | « Congrès créé. » | PASS | PASS | « Congrès créé. » |
| 1.4 | **Visitor side:** open the home page and type the title in « Recherche », then click « Rechercher ». | The new congress is listed. | PASS | PASS | title found |
| 1.5 | Back in the console, click « Congrès », then click the congress title. Change « Ville » to `Marseille` and click « Enregistrer ». | « Modifications enregistrées. » | PASS | PASS | « Modifications enregistrées. » |
| 1.6 | Click « Voir la fiche publique ». | The public page shows « Marseille (France) ». | PASS | PASS | « Marseille (France) » |
| 1.7 | Click « Nouveau congrès » again. Fill in the form with « Date de fin » before « Date de début », then click « Publier ». | Nothing is saved, and a message explains the problem. | PASS | PASS | « Date de fin : La date de fin doit être le jour du début ou après. » |
| 1.8 | Click « Se déconnecter » and log in as `contributeur`. Click « Nouveau congrès », fill in the form, then click « Soumettre à relecture ». | There is no « Publier » button. The status reads « À relire ». | PASS | PASS | 0 « Publier » buttons; badge « À relire »; message « Congrès créé. Soumis à relecture. » |
| 1.9 | **Visitor side:** search the catalogue for that title. | « Aucun congrès trouvé ». The draft is not public. | PASS | PASS | « Aucun congrès trouvé » |
| 1.10 | Log in as `direction`. Click « Congrès », then « À relire ». Open the congress and click « Publier ». Then search the catalogue for it again. | It is now listed. | PASS | PASS | title found |

### Scenario 2: public catalogue, search, filters, details (S2)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| 2.1 | Open the home page without logging in. | « 12 congrès » | PASS | PASS | « 12 congrès » |
| 2.2 | Type `vienne` in « Recherche » and click « Rechercher ». | « 2 congrès trouvés », both in « Vienne, Autriche ». | PASS | PASS | « 2 congrès trouvés » |
| 2.3 | Search for `diabetologie`, typed without the accent. | « Journées françaises de diabétologie » is found. | PASS | PASS | found |
| 2.4 | Click « Réinitialiser », then click the « Cardiologie » button. | « 2 congrès trouvés » | PASS | PASS | « 2 congrès trouvés » |
| 2.5 | Choose `Espagne` in « Pays » and click « Rechercher ». | « 1 congrès trouvé ». The discipline filter is kept. | PASS | PASS | « 1 congrès trouvé » |
| 2.6 | Search for `rhumatologie`. | « Aucun congrès ne correspond. » appears, with the buttons « Réinitialiser la recherche » and « Nous écrire ». | PASS | PASS | no-result state |
| 2.7 | Start again from the home page and click « Page suivante ». | Page 2 shows the remaining 3 congresses. | PASS | PASS | 3 rows |
| 2.8 | Click « Cardiologie », then « Voir la fiche » on « Congrès européen de cardiologie ». | The page shows « Dates », « Ville », « Pays », « Discipline », « Lieu », « Site officiel » and « Vérifié le ». The form « Demander un devis de vol » has the congress already filled in. | PASS | PASS | all fields, prefilled |
| 2.9 | **Team side:** log in as `equipe`. Click « Congrès », then « Publié ». | 12 published congresses are listed. | PASS | PASS | 12 rows |

### Scenario 3: flight enquiry (S3)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| 3.1 | **Visitor side:** open « Journées d’oncologie digestive — exemple » from the catalogue. | The form has these fields: « Nom et prénom », « E-mail », « Téléphone », « Société (facultatif) », « Ville de départ », « Date aller », « Date retour », « Passagers », « Message (facultatif) », and the consent box « J’accepte… ». The congress is already filled in. | PASS | PASS | 10/10 fields |
| 3.2 | Fill in the form with the e-mail `veena@`, « Passagers » set to `0`, and the consent box left unticked. Click « Envoyer la demande ». | « 3 champs à corriger ; rien n’a été enregistré. » A message in French appears next to each wrong field. What you typed is kept. | PASS | PASS | « 3 champs à corriger… »; name kept |
| 3.3 | Correct the e-mail, set « Passagers » to `2`, tick the box, and click « Envoyer la demande » once. | « Merci, votre demande est enregistrée. » and a reference « DV-2026-NNNN ». | PASS | PASS | DV-2026-0007 |
| 3.4 | Reload the page (F5). | The same reference is shown and no second enquiry is created. | PASS | PASS | still DV-2026-0007 |
| 3.5 | **Team side:** in the same browser, log in as `equipe` and click « Notifications ». | « Nouvelle demande DV-2026-0007 : … » appears. | PASS | PASS | found |
| 3.6 | Click « Demandes » and search for the visitor's name. | Exactly one enquiry is found. | PASS | PASS | 1 row |

### Scenario 4: team receives, views, tracks, updates (S4)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| 4.1 | As `equipe`, open « Tableau de bord » and note the number on « Nouvelles ». | The new reference is first in « Dernières demandes ». | PASS | PASS | DV-2026-0007 first; « Nouvelles » = 3 |
| 4.2 | Click the reference. | You see the congress, contact, e-mail, « Ville de départ », « Aller », « Retour », « Passagers », and the status « Nouvelle ». | PASS | PASS | all shown |
| 4.3 | Under « Changer le statut », click « Qualifiée ». | « Statut mis à jour : Qualifiée. » appears and the badge reads « Qualifiée ». | PASS | PASS | « Statut mis à jour : Qualifiée. » |
| 4.4 | Click « Me l’attribuer ». | « Responsable » shows Karim Benali. | PASS | PASS | « Karim Benali, Équipe » |
| 4.5 | Type a note under « Note interne » and click « Ajouter la note ». | The note appears in « Historique ». | PASS | PASS | note shown |
| 4.6 | Click « Devis envoyé », then « Gagnée ». | « Historique » shows each change with who made it, when, and the old and new status. | PASS | PASS | « Nouvelle vers Qualifiée », « Qualifiée vers Devis envoyé », « Devis envoyé vers Gagnée » |
| 4.7 | Look at « Historique ». | There is no edit or delete button. | PASS | PASS | 0 buttons |
| 4.8 | Go back to « Tableau de bord ». | « Nouvelles » has gone down by one. | PASS | PASS | 3 → 2 |
| 4.9 | Click « Demandes », then the « Gagnée » filter. Then search for the reference with « Rechercher ». | The enquiry appears in both. | PASS | PASS | found / 1 row |
| 4.10 | Click « Exporter (tableur CSV) ». | A spreadsheet file downloads, with the enquiry in it. | PASS | PASS | `demandes-2026-11-06.csv`. The export follows the active search. |
| 4.11 | **Visitor side:** log out and search the public catalogue for the visitor's name. | Nothing is found, so enquiries are never public. | PASS | PASS | « Aucun congrès trouvé » |
| 4.12 | Log in as `contributeur` and open `/console/demandes`. | Access refused. | PASS | PASS | HTTP 403 |

Observation for 4.2 and 4.9 (re-run 6 Nov): the « Demandes » table now fits a desktop screen; « Statut » is the second column and « Voyage » groups departure, dates and passengers. USAB-B-011 is closed.

### Scenario 5: GM&E codes, access by authorisation (S5)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| 5.1 | **Visitor side:** open « Journées d’oncologie digestive — exemple ». | It says « Tarif congrès négocié disponible ». No code appears on the page, including in its source. | PASS | PASS | no `DEMO-GME-` in HTML |
| 5.2 | Log in as `equipe` and click « Codes ». | Every code is masked (•••• •••• ••••). | PASS | PASS | masked |
| 5.3 | Leave « Motif de la demande » empty and click « Demander l’accès ». | The request is refused with a message. | PASS | PASS | « Indiquez le motif de la demande (au moins 5 caractères). » |
| 5.4 | Type a reason and click « Demander l’accès ». | « Demande envoyée à la Direction. » | PASS | PASS | shown |
| 5.5 | Log out and log in as `direction`. On « Tableau de bord », click « … demande(s) d’accès GM&E à décider », then click « Approuver pour 24 h » on that request. | « Accès accordé pour 24 heures. » | PASS | PASS | shown |
| 5.6 | Log in as `equipe`. Click « Codes », then « Afficher le code ». | The code appears, with « Affichage enregistré dans le journal d’accès. » | PASS | PASS | DEMO-GME-4821 |
| 5.7 | Click « Masquer le code ». | The code is hidden again. | PASS | PASS | hidden |
| 5.8 | As `equipe`, open `/console/gme/journal`. | Access refused, because the journal is for Direction only. | PASS | PASS | HTTP 403 |
| 5.9 | Log in as `direction` and click « Journal ». | A row shows Karim Benali, Équipe, the congress, and « Code affiché ». | PASS | PASS | row found |
| 5.10 | Click « Demandes d’accès », then « Révoquer maintenant ». | « Accès révoqué immédiatement. » | PASS | PASS | shown |
| 5.11 | Log in as `equipe` and click « Codes ». | « Afficher le code » is gone. A new request is needed. | PASS | PASS | 0 buttons |

**Result, Option B (re-run 6 Nov 2026, live version `29d23da1-4707-436e-8b91-dbdb96fd844c`):** all 48 steps PASS at 1440 px and at 390 px. USAB-B-011 is fixed. Step 4.3 now expects the new message « Statut mis à jour : Qualifiée. ».

## Sign-off

| Option | Scenario | Tester | Date | Result | Open items | Signature |
|---|---|---|---|---|---|---|
| B | 1. Create and edit a congress | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (10/10) | USAB-B-013 (cosmetic) | |
| B | 2. Catalogue, search, filters, details | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (9/9) | USAB-B-012 (minor, phone) | |
| B | 3. Flight enquiry | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (6/6) | none | |
| B | 4. Team receives, tracks, updates | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (12/12) | USAB-B-011 (major, desktop table) | |
| B | 5. GM&E codes and authorisation | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (11/11) | none | |
| A | 1–5 | « Internal UAT (ProdCraft) » | | to be run | | |

## Option A: WordPress plugin (WordPress Playground)

**Where (round 2, 6 Nov 2026):** two places. (1) Locally: `wp_demo/` built with `./build_zip.sh --local` and served by `@wp-playground/cli@3.1.62` with the visitor blueprint on http://127.0.0.1:9405 (fresh seed, WordPress 7.1.4, PHP 8.3). (2) On the hosted links the client will click (`mode=seamless`, with `login=no` for the visitor link), run 3 times in fresh browsers. The hosted blueprints and zip are byte-identical to the local build (zip sha256 ad48baa5…).

**Logins** (the password is `demo-asset`): `direction` (Direction (démo)), `equipe` (Équipe (démo)), `contributeur`. The administrator is `admin` / `password`.

**Before you start:** reload the Playground page to start from the seed. All data is fictional. Codes look like `DEMO-GME-…`.

**Run:** round 1 on 5 Nov 2026, re-run on 6 Nov 2026 after the fix round, by an independent internal reviewer acting as a first-time office assistant who follows only the on-screen labels. The visitor steps (S2, S3) were run at 1440 px and 390 px; the team steps at 1440 px. Local steps were driven by `qa/A/ux/uat.mjs`, run from `qa/A/ux/r2/`, and keyboard-only steps by `qa/A/ux/kb.mjs`. The hosted walk was driven by `qa/A/ux/r2/hosted2.mjs`. Round-2 evidence: `qa/A/ux/r2/evidence/`, plus the logs `uat2-run.log`, `kb2-result.json` and `hosted2.log` (run 3; runs 1–2 in `hosted2-run1.log` and `hosted2-run2.log`). The results below are round 2.

### Scenario A1: create and edit a congress (S1)

| # | Step | Expected | Result | Evidence |
|---|---|---|---|---|
| A1.1 | Log in as `direction`. Look at the left menu on « Tableau de bord ». | The menu shows « Tableau de bord, Médias, Congrès, Demandes, Accès GM&E, Profil ». | PASS | uat-S1-01.png |
| A1.2 | Click « Congrès », then « Ajouter un congrès ». | The « Informations du congrès » box opens, and the required fields are marked « (obligatoire) ». | PASS | uat-S1-02.png (5 fields marked) |
| A1.3 | Type a title ending « — exemple ». Fill in « Date de début », « Date de fin », « Ville » (Lille), « Pays », « Discipline », « Lieu », « Site officiel » and « Date de vérification ». | Each field can be found by its French label. | PASS | uat-S1-03.png |
| A1.4 | Click « Publier ». | « Publication mise en ligne. » | PASS (hosted too: 1.0 s, no « Connexion perdue » in 3 runs) | r2/evidence/uat-S1-04.png, hosted2-s1-published-1440.png |
| A1.5 | **Visitor side:** open the congress page while logged out. | The title and « Lille » are shown. | PASS | uat-s1-run.log |
| A1.6 | From « Tableau de bord », click « Congrès », then the title. Change « Ville » to Roubaix and click « Mettre à jour ». | The change is saved, and the admin shows Roubaix. | PASS | uat-S1-06.png |
| A1.7 | **Visitor side:** reload the public page. | It shows « Roubaix ». | PASS | uat-s1-run.log |
| A1.8 | Set « Date de fin » earlier than « Date de début » and click « Mettre à jour ». | « La date de fin doit être postérieure ou égale à la date de début : dates non enregistrées. » | PASS | uat-S1-08.png |
| A1.9 | Log in as `contributeur`, then go to « Congrès » → « Ajouter un congrès ». | The button reads « Soumettre à la relecture », not « Publier ». After submitting, the status is « En attente de relecture ». | PASS | uat-S1-09.png |
| A1.10 | **Visitor side:** search for that congress in the catalogue. | « 0 congrès trouvés ». | PASS | uat-s1-run.log |
| A1.K | Keyboard only: steps A1.2 to A1.4. | The congress is published. | PASS | r2/kb2-result.json: 7 Tabs to « Congrès », 9 to « Ajouter un congrès », 38 from the title to « Date de début » (through « Description du congrès », no tab trap), 2/2/1/1 for the other fields, then 22 Shift+Tab to « Publier » and Enter. Result: « Publication mise en ligne. » The focus ring is visible throughout. A11Y-A-005 is fixed (A11Y-A-203). |

Note A1.4: round 1 saw one « Connexion perdue » on a loaded machine (USAB-A-008). In round 2 autosave is off on the congress editor, and « Publier » worked in every local and hosted run, so USAB-A-008 is closed. New in round 2: « Description du congrès » shows raw block markup (`<!-- wp:paragraph -->`) on the seeded congresses (EYE-A-201, Medium). It does not block any step.

### Scenario A2: public catalogue, search, filters, details (S2)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| A2.0 | Open the hosted **visitor** link. | The catalogue opens, logged out. | PASS | PASS | hosted2.log: logged out in 3 of 3 runs (no « Bonjour », no admin bar), no Playground toolbar, catalogue in 13.1–16.5 s at 1440 and 13.1–15.8 s at 390. The hosted chip → card → enquiry also passed (DV-2026-0007). USAB-A-201. |
| A2.1 | Open the catalogue while logged out. | « Catalogue des congrès » and « 12 congrès trouvés ». | PASS | PASS | r2/evidence/uat-S2-01.png. The run showed 13, because A1 had just published one more congress; the fresh seed shows 12 (visitor-01-catalogue-1440.png). |
| A2.2 | Click the « Cardiologie » chip. | Only cardiology congresses are listed (« 2 congrès trouvés »). | PASS | PASS | uat-S2-02.png |
| A2.3 | Click the first card. | The details page shows « Dates, Ville, Pays, Discipline, Lieu, Site officiel » and « Demander un devis vol ». | PASS | PASS | uat-S2-03.png |
| A2.4 | Check for sideways scrolling. | There is none. | PASS | PASS | scrollWidth 1440/1440 and 390/390 |
| A2.5 | Type `vienne` in « Recherche » and click « Rechercher ». | The Vienne congresses are listed. | PASS | n/a | uat-S2-05.png (2 found) |
| A2.6 | Search for `diabetologie`, typed without an accent. | « Diabétologie » is found. | PASS | n/a | uat-S2-06.png |
| A2.7 | Search for `zzzz`, then click « Voir tous les congrès ». | « Aucun congrès ne correspond à votre recherche ». The reset brings back 12. | PASS | n/a | uat-S2-07.png |
| A2.8 | Choose « Pays » = France and click « Rechercher ». | The filter is applied. Pagination was not exercised, because there were fewer than 10 results. | PASS | n/a | uat-S2-08.png |
| A2.K | Keyboard only: Tab to the « Cardiologie » chip, press Enter, then Tab to the first card and press Enter. | The details page opens, with a visible focus ring. | PASS | n/a | r2/kb2-result.json (12 + 24 Tabs) |

### Scenario A3: flight enquiry (S3)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| A3.1 | On the congress page, look at « Demander un devis vol ». | « Congrès : … » is prefilled. All labels are present, from « Nom et prénom » to the « J’accepte… » consent. | PASS | PASS | uat-S3-01.png |
| A3.2 | Click « Envoyer ma demande » with the form empty. | « Merci de corriger les points suivants », with « Indiquez votre nom. » and the other messages next to each field. | PASS | PASS | uat-S3-02.png |
| A3.3 | Enter 0 passengers and a return date before the outbound date. | « La date retour doit être postérieure ou égale à la date aller. » and « Le nombre de passagers doit être un nombre entier entre 1 et 50. » The name already typed is kept. | PASS | PASS | uat-S3-03.png |
| A3.4 | Correct the form (2 passengers, return 30/08/2027) and click « Envoyer ma demande » once. | « Merci, votre demande a bien été envoyée. » and « Votre référence : DV-2026-NNNN ». | PASS | PASS | DV-2026-0007 (1440), DV-2026-0008 (390); hosted DV-2026-0007 |
| A3.5 | Reload the confirmation page. | The same reference is shown, and no second enquiry is created. | PASS | PASS | uat-S3-05.png |
| A3.K | Keyboard only: fill and send the form. | A reference is shown. | PASS | n/a | r2/kb2-result.json |

### Scenario A4: team receives, views, tracks, updates (S4)

| # | Step | Expected | Result | Evidence |
|---|---|---|---|---|
| A4.1 | Log in as `equipe`. Look at « Demandes de devis par statut » on « Tableau de bord ». | The status counts are shown, and « Dernière demande » is the new reference. | PASS | uat-S4-01.png (Nouvelle = 6) |
| A4.2 | Click the « Dernière demande » link. | The detail page shows « Ville de départ », « Date aller », « Date retour », « Passagers » and the contact. | PASS | uat-S4-02.png |
| A4.3 | Choose « Qualifiée » in « Statut », choose « Équipe (démo) » in « Responsable », add an internal note and click « Enregistrer ». | « Demande mise à jour. » | PASS | uat-S4-03.png |
| A4.4 | Look at « Historique ». | It shows who, when and « Nouvelle → Qualifiée », with no edit or delete control. | PASS | uat-S4-04.png |
| A4.5 | Go back to « Tableau de bord ». | « Nouvelle » has gone down by 1. | PASS | r2/evidence/uat-S4-05.png (4 → 3) |
| A4.6 | Click « Demandes ». | The row shows the reference, date, congress, contact, Lyon, dates, 2 passengers and « Qualifiée ». | PASS | uat-S4-06.png |
| A4.7 | Click the « Qualifiée » view, search for « Claire » and click « Rechercher ». | The enquiry is found. | PASS | uat-S4-07.png |
| A4.8 | Open « Demandes » → « Journal des notifications ». | There is an entry for the reference, marked « Non distribué (pas de SMTP) ». | PASS | uat-S4-08.png |
| A4.K | Keyboard only: steps A4.2 to A4.3. | The status is saved. | PASS | r2/kb2-result.json (31 + 24 + 3 Tabs). Hosted, mouse: equipe changed DV-2026-0006 to « Qualifiée » (hosted2-s4-1440.png). |

### Scenario A5: GM&E codes, access by authorisation (S5)

| # | Step | Expected | Result | Evidence |
|---|---|---|---|---|
| A5.1 | As `equipe`, click « Accès GM&E ». | Every code is shown as dots, and no `DEMO-GME` code is in the HTML. | PASS | uat-S5-01.png |
| A5.2 | Click « Demander l’accès » with the reason empty. | The request is refused: « Raison de la demande (obligatoire) ». | PASS | uat-S5-02.png |
| A5.3 | Type a reason and click « Demander l’accès ». | « Demande d’accès envoyée à la Direction. » | PASS | uat-S5-03.png |
| A5.4 | As `direction`, click « Approuver (24 h) » in « Accès GM&E en attente » on « Tableau de bord ». | « Accès approuvé pour 24 heures. » | PASS | uat-S5-04.png |
| A5.5 | As `equipe`, click « Accès GM&E », then « Révéler le code ». | The code is shown once. | PASS | uat-S5-05.png |
| A5.6 | Reload « Accès GM&E ». | The code is masked again. | PASS | uat-S5-06.png |
| A5.7 | As `direction`, open « Journal GM&E ». | « Code révélé » by Équipe (démo), with no code text. | PASS | uat-S5-07.png |
| A5.8 | As `direction`, open « Demandes d’accès » and click « Révoquer ». | « Accès révoqué immédiatement. » | PASS | uat-S5-08.png |
| A5.9 | As `equipe`, reload « Accès GM&E ». | « Révéler le code » is gone, and « Dernière demande : Révoquée » is shown. | PASS | uat-S5-09.png |
| A5.10 | Log in as `contributeur`. | The menu shows neither « Accès GM&E » nor « Demandes ». | PASS | uat-run.log |
| A5.11 | **Visitor side:** open the neurology congress page. | « Tarif congrès négocié disponible » is shown, with 0 codes in the HTML. | PASS | uat-run.log |
| A5.K | Keyboard only: request, approve and reveal. | All three succeed. | PASS | r2/kb2-result.json (15/23/1, 44, 15/23 Tabs). Hosted, mouse: request, approve, reveal, and masked again after reload (hosted2-s5-reveal-1440.png). |

**Result, Option A (round 2, 6 Nov 2026):** 51 of 51 local mouse steps pass (A1 10, A2 12, A3 10, A4 8, A5 11). All five keyboard-only stories pass, including A1.K publish. The hosted walk passes 11 of 11 steps, and A2.0 passes. Round 1's two failures (A2.0, A1.K) are fixed. One item is still open outside the WordPress demo itself: the demo hub (`site/demo/index.html`) says in Task 4, « Your enquiry from task 3 is at the top ». On the hosted links it is not there, because the visitor link and the admin link are separate in-browser sites (USAB-A-207, Major, hub copy). Also open: EYE-A-201 (raw block markup in the description field, Medium), USAB-A-208 (hub copy, Minor) and EYE-A-202 (revealed code wraps, Minor). Details are in `qa/register/A_ux.md`.

### Sign-off: Option A

| Option | Scenario | Tester | Date | Result | Open items | Signature |
|---|---|---|---|---|---|---|
| A | 1. Create and edit a congress | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (10/10 + keyboard + hosted) | EYE-A-201 (medium, raw markup in description) | |
| A | 2. Catalogue, search, filters, details | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (12/12 + A2.0 hosted + keyboard) | none | |
| A | 3. Flight enquiry | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (10/10 + keyboard + hosted) | none | |
| A | 4. Team receives, tracks, updates | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (8/8 + keyboard + hosted) | USAB-A-207 (major, demo hub Task 4 copy), USAB-A-208 (minor) | |
| A | 5. GM&E codes and authorisation | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS (11/11 + keyboard + hosted) | EYE-A-202 (minor), USAB-A-208 (hub Task 5 path) | |

## Extra — Le lien de groupe

Target: the **preview** Worker, https://asset-voyages-demo-preview.debanjan186.workers.dev (never production). Run on 06/11/2026 with Playwright Chromium, `fr-FR`, `Europe/Paris`, at 1440×900 and 390×844 (touch). Every browser is a fresh context and so a private sandbox; staff = `equipe`, delegates = separate logged-out browsers. Script and raw output: `qa/EXTRA/ux/uat.mjs` → `uat-1440.json`, `uat-390.json`; screenshots `qa/EXTRA/ux/evidence/`, `qa/EXTRA/ux/eye/`. Every sandbox used was reset with « Réinitialiser la démo » at the end of the run. Register: `qa/register/EXTRA_ux.md`.

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| X.1 | As `equipe`, open « Demandes » and click the reference of an enquiry with 2 or more passengers and no link (DV-2026-0002). | The « Lien de groupe » card shows « Créer le lien ». | PASS | PASS (card 2.3 screens down, USAB-X-006) | evidence/*-X1-detail.png |
| X.2 | Click « Créer le lien ». | « Lien créé : copiez-le et envoyez-le aux participants. », a `/g/<token>` link of 43 characters and « Valable jusqu’au 06/12/2026 » (30 days). | PASS | PASS | evidence/*-X2-created.png |
| X.3 | Click « Copier le lien ». | The clipboard holds the link; « Lien copié » is shown. | PASS | PASS | uat-*.json |
| X.4 | As delegate A (another browser, logged out), open the link. | The congress name and dates only; no reference, contact, passenger count, threshold, fare, airline or code. | PASS | PASS | evidence/*-X4-public.png |
| X.5 | Clear the dates and click « Envoyer mes informations » with every field empty. | « 6 champs à corriger ; rien n’a été enregistré. », focused, each field explained. | PASS | PASS | evidence/*-X5-errors.png |
| X.6 | Fill « Nom et prénom », « E-mail », « Ville de départ », set « Date retour » before « Date aller », tick the consent box, send. | « La date retour doit être le jour de l’aller ou après. »; typed values kept. | PASS | PASS | uat-*.json |
| X.7 | Fix the date and tap « Envoyer mes informations » (1 click). | « Votre réponse a bien été reçue. » showing only what A sent. | PASS | PASS | evidence/*-X7-confirm.png |
| X.8 | Same browser, same e-mail, « Ville de départ » = Marseille, send. | The entry is updated in place; no « Modifications à vérifier ». | PASS | PASS | uat-*.json |
| X.9 | Delegate B (a different browser) sends A’s e-mail with « Ville de départ » = Nantes. | The same « Votre réponse a bien été reçue. » page. | PASS | PASS | uat-*.json |
| X.10 | As `equipe`: « Demandes » › the reference › « Groupe (1/2) » (2 clicks from the list). | « 1 répondu / 2 attendus »; « Modification à vérifier » with « Actuel : … Marseille » and « Proposé : … Nantes ». | PASS | PASS | evidence/*-X10-pending.png |
| X.11 | Click « Refuser ». | « Modification refusée : l’inscription d’origine est conservée. »; Marseille kept. | PASS | PASS | uat-*.json |
| X.12 | Delegate B resends; `equipe` reloads and clicks « Accepter ». | « Modification acceptée : la liste est à jour. »; Nantes shown; still 1 entry. | PASS | PASS | uat-*.json |
| X.13 | Keep « Groupe » open; delegate C sends from a third browser; wait up to 25 s without reloading. | The counter changes to « 2 répondus / 2 attendus » by itself. | PASS | PASS | uat-*.json |
| X.14 | Set « Seuil groupe (à confirmer) » to 3 and click « Enregistrer »; then try 0. | « Seuil groupe enregistré. » and the hint « Proche du seuil groupe : 2 réponses sur 3 (à confirmer). … Indication interne, jamais montrée aux participants. »; 0 is refused (browser check, min 2). | PASS | PASS | evidence/*-X14-hint.png |
| X.15 | Click « Exporter pour cotation (CSV) ». | `groupe-DV-2026-0002-<date>.csv`, UTF-8 BOM, header « Nom (pièce d’identité) » …, one row per delegate. | PASS | PASS | evidence/*-X15.csv |
| X.16 | Click « Révoquer le lien », confirm; delegate A reloads the link. | « Lien révoqué : il ne fonctionne plus. … »; the public page answers 410 « Ce lien n’est plus actif »; the list is kept. | PASS | PASS | evidence/*-X16-revoked.png |
| X.17 | Click « Créer un nouveau lien »; open the new link, then the old one. | New link works; old link says « Ce lien n’est plus actif ». | **FAIL** (old link shows 404 « Lien introuvable », USAB-X-001) | **FAIL** (same) | uat-*.json |
| X.18 | Open DV-2026-0001 › « Groupe (3/6) »; open its link logged out. | « 3 répondus / 6 attendus »; the public page shows none of the three seeded delegates. | PASS | PASS | uat-*.json |
| X.19 | Log in as `contributeur`; open `/console/demandes/1/groupe`. | Refused (403 « Accès refusé »). | PASS | PASS | uat-*.json |
| X.20 | Open DV-2026-0005 (1 passenger). | No « Lien de groupe » card; `/groupe` answers 404. | PASS | PASS | uat-*.json |
| X.21 | Open `/g/` with a made-up token. | 404 « Lien introuvable ». | PASS | PASS | evidence/*-X21-unknown.png |
| X.K | Keyboard only: create and copy the link; fill and send the delegate form; « Refuser » and « Accepter ». | All succeed; focus moves to the message after each action. | PASS | PASS | qa/EXTRA/ux/kb-1440.json, kb-390.json |

Note on X.13 and X.15: a second 1440 run made right after three other runs failed these two steps because the per-IP guard (20 accepted answers per 10 minutes) refused delegate C, as designed. A run made after the window closed passed (the result above); the first run is kept as `uat1440_run2_ratelimited.log`.

**Result, Extra:** 20 of 21 steps pass at both widths, plus the keyboard run. X.17 fails on wording only: a replaced link tells the delegate « Lien introuvable … Vérifiez l’adresse reçue » instead of « Ce lien n’est plus actif ».

| Option | Scenario | Tester | Date | Result | Open items | Signature |
|---|---|---|---|---|---|---|
| B | Extra. Le lien de groupe | « Internal UAT (ProdCraft) » | 06/11/2026 | PASS with 1 minor FAIL (20/21 at 1440 and 390; keyboard PASS) | USAB-X-001, EYE-X-001 | |
