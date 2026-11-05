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

**Run:** 5 Nov 2026, on live, by an internal reviewer acting as a first-time office assistant. Each step was run twice: in a desktop browser (1440 px) and a phone-size browser (390 px), in French. Evidence for each step is a screenshot `qa/B/ux/evidence/uat-<1440|390>-<step>.png` plus the log lines in `qa/B/ux/uat1440.log` and `qa/B/ux/uat390.log`. Reference numbers below come from the 1440 run.

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
| 1.8 | Click « Se déconnecter » and log in as `contributeur`. Click « Nouveau congrès », fill in the form, then click « Soumettre à relecture ». | There is no « Publier » button. The status reads « À relire ». | PASS | PASS | 0 « Publier » buttons; badge « À relire » (the message says « Congrès créé. »; see USAB-B-013) |
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
| 4.3 | Under « Changer le statut », click « Qualifiée ». | « Enregistré. » appears and the badge reads « Qualifiée ». | PASS | PASS | « Enregistré. » |
| 4.4 | Click « Me l’attribuer ». | « Responsable » shows Karim Benali. | PASS | PASS | « Karim Benali, Équipe » |
| 4.5 | Type a note under « Note interne » and click « Ajouter la note ». | The note appears in « Historique ». | PASS | PASS | note shown |
| 4.6 | Click « Devis envoyé », then « Gagnée ». | « Historique » shows each change with who made it, when, and the old and new status. | PASS | PASS | « Nouvelle vers Qualifiée », « Qualifiée vers Devis envoyé », « Devis envoyé vers Gagnée » |
| 4.7 | Look at « Historique ». | There is no edit or delete button. | PASS | PASS | 0 buttons |
| 4.8 | Go back to « Tableau de bord ». | « Nouvelles » has gone down by one. | PASS | PASS | 3 → 2 |
| 4.9 | Click « Demandes », then the « Gagnée » filter. Then search for the reference with « Rechercher ». | The enquiry appears in both. | PASS | PASS | found / 1 row |
| 4.10 | Click « Exporter (tableur CSV) ». | A spreadsheet file downloads, with the enquiry in it. | PASS | PASS | `demandes-2026-11-05.csv`. The export follows the active search. |
| 4.11 | **Visitor side:** log out and search the public catalogue for the visitor's name. | Nothing is found, so enquiries are never public. | PASS | PASS | « Aucun congrès trouvé » |
| 4.12 | Log in as `contributeur` and open `/console/demandes`. | Access refused. | PASS | PASS | HTTP 403 |

Observation for 4.2 and 4.9: on a desktop screen, the « Demandes » table hides the columns « Passagers », « Statut » and « Responsable » past its right edge. They only show if you scroll sideways inside the table, and nothing on screen tells you to. The steps still pass, but a first-time user would not find the status in the list. This is logged as USAB-B-011 (major) and is to be fixed before sending.

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

**Result, Option B:** all 48 steps PASS at 1440 px and at 390 px. There is one observation, USAB-B-011, to fix before sending.

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

**Where:** locally, `wp_demo/` built with `./build_zip.sh --local` and served by `@wp-playground/cli@3.1.62` with the visitor blueprint on http://127.0.0.1:9402 (fresh seed). The hosted links were opened once for first impressions (step 2.0).

**Logins** (the password is `demo-asset`): `direction` (Direction (démo)), `equipe` (Équipe (démo)), `contributeur`. The administrator is `admin` / `password`.

**Before you start:** reload the Playground page to start from the seed. All data is fictional. Codes look like `DEMO-GME-…`.

**Run:** 5 Nov 2026, local, by an internal reviewer acting as a first-time office assistant who follows only the on-screen labels. The visitor steps (S2, S3) were run at 1440 px and 390 px. The team steps were run at 1440 px. Every step was driven by `qa/A/ux/uat.mjs`. Evidence: `qa/A/ux/evidence/uat-<story>-<step>.png` and the logs `qa/A/ux/uat-run.log` and `qa/A/ux/uat-s1-run.log`. The keyboard-only runs are in `qa/A/ux/kb-result-run*.json`.

### Scenario A1: create and edit a congress (S1)

| # | Step | Expected | Result | Evidence |
|---|---|---|---|---|
| A1.1 | Log in as `direction`. Look at the left menu on « Tableau de bord ». | The menu shows « Tableau de bord, Médias, Congrès, Demandes, Accès GM&E, Profil ». | PASS | uat-S1-01.png |
| A1.2 | Click « Congrès », then « Ajouter un congrès ». | The « Informations du congrès » box opens, and the required fields are marked « (obligatoire) ». | PASS | uat-S1-02.png (5 fields marked) |
| A1.3 | Type a title ending « — exemple ». Fill in « Date de début », « Date de fin », « Ville » (Lille), « Pays », « Discipline », « Lieu », « Site officiel » and « Date de vérification ». | Each field can be found by its French label. | PASS | uat-S1-03.png |
| A1.4 | Click « Publier ». | « Publication mise en ligne. » | PASS (see note) | uat-S1-04.png |
| A1.5 | **Visitor side:** open the congress page while logged out. | The title and « Lille » are shown. | PASS | uat-s1-run.log |
| A1.6 | From « Tableau de bord », click « Congrès », then the title. Change « Ville » to Roubaix and click « Mettre à jour ». | The change is saved, and the admin shows Roubaix. | PASS | uat-S1-06.png |
| A1.7 | **Visitor side:** reload the public page. | It shows « Roubaix ». | PASS | uat-s1-run.log |
| A1.8 | Set « Date de fin » earlier than « Date de début » and click « Mettre à jour ». | « La date de fin doit être postérieure ou égale à la date de début : dates non enregistrées. » | PASS | uat-S1-08.png |
| A1.9 | Log in as `contributeur`, then go to « Congrès » → « Ajouter un congrès ». | The button reads « Soumettre à la relecture », not « Publier ». After submitting, the status is « En attente de relecture ». | PASS | uat-S1-09.png |
| A1.10 | **Visitor side:** search for that congress in the catalogue. | « 0 congrès trouvés ». | PASS | uat-s1-run.log |
| A1.K | Keyboard only: steps A1.2 to A1.4. | The congress is published. | **FAIL** | kb-result-run4/5/6/7.json: every field and « Publier » can be reached with a visible focus ring (7 + 9 + 22 + 55 Tabs), but the form was never posted in 5 runs. A control run, using a mouse click after typing with the keyboard, also failed. A mouse run with filled fields passed. See A11Y-A-005. |

Note A1.4: in the first mouse run, « Publier » did nothing, and WordPress showed « Connexion perdue. L’enregistrement a été désactivé… ». It passed on the re-run. See USAB-A-008.

### Scenario A2: public catalogue, search, filters, details (S2)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| A2.0 | Open the hosted **visitor** link. | The catalogue opens, logged out. | **FAIL** | n/a | hosted-visitor-1440.png: catalogue after 18.8 s, but the page shows the admin bar with « Bonjour, admin », « Modifier le site » and « Modifier la page ». The Playground toolbar (« New, Playgrounds, Site Settings, Export, Dev Tools ») covers the bottom of the page. See USAB-A-001. |
| A2.1 | Open the catalogue while logged out. | « Catalogue des congrès » and « 12 congrès trouvés ». | PASS | PASS | uat-S2-01.png, uat-S2@390-01.png |
| A2.2 | Click the « Cardiologie » chip. | Only cardiology congresses are listed (« 2 congrès trouvés »). | PASS | PASS | uat-S2-02.png |
| A2.3 | Click the first card. | The details page shows « Dates, Ville, Pays, Discipline, Lieu, Site officiel » and « Demander un devis vol ». | PASS | PASS | uat-S2-03.png |
| A2.4 | Check for sideways scrolling. | There is none. | PASS | PASS | scrollWidth 1440/1440 and 390/390 |
| A2.5 | Type `vienne` in « Recherche » and click « Rechercher ». | The Vienne congresses are listed. | PASS | n/a | uat-S2-05.png (2 found) |
| A2.6 | Search for `diabetologie`, typed without an accent. | « Diabétologie » is found. | PASS | n/a | uat-S2-06.png |
| A2.7 | Search for `zzzz`, then click « Voir tous les congrès ». | « Aucun congrès ne correspond à votre recherche ». The reset brings back 12. | PASS | n/a | uat-S2-07.png |
| A2.8 | Choose « Pays » = France and click « Rechercher ». | The filter is applied. Pagination was not exercised, because there were fewer than 10 results. | PASS | n/a | uat-S2-08.png |
| A2.K | Keyboard only: Tab to the « Cardiologie » chip, press Enter, then Tab to the first card and press Enter. | The details page opens, with a visible focus ring. | PASS | n/a | kb-result-run4.json (12 + 24 Tabs) |

### Scenario A3: flight enquiry (S3)

| # | Step | Expected | 1440 | 390 | Evidence |
|---|---|---|---|---|---|
| A3.1 | On the congress page, look at « Demander un devis vol ». | « Congrès : … » is prefilled. All labels are present, from « Nom et prénom » to the « J’accepte… » consent. | PASS | PASS | uat-S3-01.png |
| A3.2 | Click « Envoyer ma demande » with the form empty. | « Merci de corriger les points suivants », with « Indiquez votre nom. » and the other messages next to each field. | PASS | PASS | uat-S3-02.png |
| A3.3 | Enter 0 passengers and a return date before the outbound date. | « La date retour doit être postérieure ou égale à la date aller. » and « Le nombre de passagers doit être un nombre entier entre 1 et 50. » The name already typed is kept. | PASS | PASS | uat-S3-03.png |
| A3.4 | Correct the form (2 passengers, return 30/08/2027) and click « Envoyer ma demande » once. | « Merci, votre demande a bien été envoyée. » and « Votre référence : DV-2026-NNNN ». | PASS | PASS | DV-2026-0009 (1440), DV-2026-0010 (390) |
| A3.5 | Reload the confirmation page. | The same reference is shown, and no second enquiry is created. | PASS | PASS | uat-S3-05.png |
| A3.K | Keyboard only: fill and send the form. | A reference is shown. | PASS | n/a | kb-result-run4.json |

### Scenario A4: team receives, views, tracks, updates (S4)

| # | Step | Expected | Result | Evidence |
|---|---|---|---|---|
| A4.1 | Log in as `equipe`. Look at « Demandes de devis par statut » on « Tableau de bord ». | The status counts are shown, and « Dernière demande » is the new reference. | PASS | uat-S4-01.png (Nouvelle = 6) |
| A4.2 | Click the « Dernière demande » link. | The detail page shows « Ville de départ », « Date aller », « Date retour », « Passagers » and the contact. | PASS | uat-S4-02.png |
| A4.3 | Choose « Qualifiée » in « Statut », choose « Équipe (démo) » in « Responsable », add an internal note and click « Enregistrer ». | « Demande mise à jour. » | PASS | uat-S4-03.png |
| A4.4 | Look at « Historique ». | It shows who, when and « Nouvelle → Qualifiée », with no edit or delete control. | PASS | uat-S4-04.png |
| A4.5 | Go back to « Tableau de bord ». | « Nouvelle » has gone down by 1 (6 → 5). | PASS | uat-S4-05.png |
| A4.6 | Click « Demandes ». | The row shows the reference, date, congress, contact, Lyon, dates, 2 passengers and « Qualifiée ». | PASS | uat-S4-06.png |
| A4.7 | Click the « Qualifiée » view, search for « Claire » and click « Rechercher ». | The enquiry is found. | PASS | uat-S4-07.png |
| A4.8 | Open « Demandes » → « Journal des notifications ». | There is an entry for the reference, marked « Non distribué (pas de SMTP) ». | PASS | uat-S4-08.png |
| A4.K | Keyboard only: steps A4.2 to A4.3. | The status is saved. | PASS | kb-result.json (31 + 24 + 3 Tabs) |

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
| A5.K | Keyboard only: request, approve and reveal. | All three succeed. | PASS | kb-result-run2.json (15/23/1, 44, 15/23 Tabs) |

**Result, Option A:** every local mouse step passes at 1440 px, and at 390 px where it was run. Two steps fail. A2.0: the hosted visitor link opens logged in as admin. A1.K: a congress cannot be published by keyboard alone. The eye review (EYE-A-001/002/005/006) blocks sending the current screenshots. Details are in `qa/register/A_ux.md`.

### Sign-off: Option A

| Option | Scenario | Tester | Date | Result | Open items | Signature |
|---|---|---|---|---|---|---|
| A | 1. Create and edit a congress | « Internal UAT (ProdCraft) » | 05/11/2026 | FAIL (10/10 mouse; keyboard FAIL) | A11Y-A-005, USAB-A-008 | |
| A | 2. Catalogue, search, filters, details | « Internal UAT (ProdCraft) » | 05/11/2026 | FAIL (12/12 local; hosted A2.0 FAIL) | USAB-A-001, EYE-A-001/002 | |
| A | 3. Flight enquiry | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (10/10) | EYE-A-003/008/009 (cosmetic) | |
| A | 4. Team receives, tracks, updates | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (8/8) | EYE-A-004 (UTC/ISO dates) | |
| A | 5. GM&E codes and authorisation | « Internal UAT (ProdCraft) » | 05/11/2026 | PASS (11/11) | USAB-A-006 | |
