# INTERNE — ne pas joindre au dossier

## Sources des tarifs (section A)

| Tarif | Source |
|---|---|
| Site 2 500 à 3 000 €, 48 à 72 h | Grille fixée par le fondateur (10/11/2026) ; site principal à 2 500 € : `deliverables/asset_voyages_rfp_2026-10-28/proposal/ProdCraft_ASSET_Voyages_Proposal_v1.0_2026-10-28.md:228` |
| Maintenance PME 600 €/mois | `execution/gtm_client_workflows/proposal_system/proposals/greenjobs-official.official.json:96-97` ; proposition ASSET Voyages, l. 276 |
| Maintenance indépendants 99 €/mois | Prix fixé par le fondateur (10/11/2026) ; lettres d'intention Jitendra Kumar et Jeevana Gogula |
| Moteur de prospection 12 000 € | `execution/personal_workflows/self_outbound_system/config/tone.json:228` ; repère : Nick Saraev, « High-ticket services ($10k, $15k, $20k) », `deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md:282` |
| Prototype IA 4 000 € | `tone.json:297` |
| Pilote approche de candidats 1 500 à 2 500 € | `deliverables/gaia_2026-09-10/call_brief_2026-09-10.md:82` |
| Assistant téléphonique 199 €/mois | `docs/sales/vitry_dental_one_pager.md:42` |
| Module de veille 1 500 €, connecteur CRM 500 €, version anglaise 750 € | Proposition ASSET Voyages, l. 247, 243, 242 |

## Sources des charges (section B)

| Charge | Source |
|---|---|
| Claude 100 €/mois | Déclaration du fondateur (10/11/2026) |
| Instantly 89 €/mois | `directives/personal_workflows/self_outbound_system.md:5` (la page de facturation indique 97 $/mois : `docs/runbooks/lenore_reply_draft.md:15`) |
| Google Workspace 8,28 €/mois | `directives/personal_workflows/self_outbound_system.md:95` |
| OpenRouter 10 $/mois | Plafond recommandé : `docs/reference/openrouter_spend_audit_2026-11-03.md:41` |
| Cloudflare 5 $/mois | `greenjobs-official.official.json:98` |
| Domaine 10 €/an | `directives/personal_workflows/self_outbound_system.md:87,93` |

Calculs : `.tmp/titre_sejour_sources/calc.py`. Seuils officiels 2026 : plafond micro services 83 600 € (2026-2028, proratisé l'année de création) ; franchise TVA services 37 500 € / 41 250 € ([URSSAF](https://www.autoentrepreneur.urssaf.fr/portail/accueil/sinformer-sur-le-statut/toutes-les-actualites/2026--modification-des-seuils-de.html), [impots.gouv](https://www.impots.gouv.fr/professionnel/questions/en-tant-que-micro-entrepreneur-puis-je-etre-redevable-de-la-tva)).

## Points à vérifier avant dépôt

1. **Lettres d'intention.** Dire à Jitendra et Jeevana, avant signature, qu'elles indiquent 99 €/mois pendant 12 mois après l'autorisation, et qu'ils ne signent que s'ils comptent vraiment le payer. Joindre les deux lettres signées.
2. **GreenJobs.** Ne rien joindre et ne pas citer GreenJobs dans le dossier. Aucune facturation avant l'autorisation d'exercer.
3. **TVA.** L'année 1 dépasse 41 250 € : TVA facturée dès le dépassement. Vérifier le régime de TVA des clients hors de France.
4. **Plafond micro.** Années 2 et 3 (78 676 € et 79 576 €) sous 83 600 €. Le plafond est proratisé l'année de création : vérifier selon la date d'immatriculation.
5. **Instantly.** 89 € ou 97 $ par mois : vérifier sur la dernière facture.
6. **OpenRouter.** Fixer le plafond de 10 $/mois sur la clé.
7. **Renouvellement de prodcraft.fyi.** Montant à ajouter.
8. **Délai de 48 à 72 heures.** Joindre des liens vers des sites livrés.
