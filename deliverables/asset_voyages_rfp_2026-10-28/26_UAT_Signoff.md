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
