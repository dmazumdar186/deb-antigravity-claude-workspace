# INTERNE — ne pas joindre au dossier

## Sources des tarifs (section A)

| Tarif | Source |
|---|---|
| Site 2 500 à 3 000 €, 48 à 72 h | Grille fixée par le fondateur (10/11/2026) ; site principal à 2 500 € : `deliverables/asset_voyages_rfp_2026-10-28/proposal/ProdCraft_ASSET_Voyages_Proposal_v1.0_2026-10-28.md:228` |
| Maintenance PME 600 €/mois | `execution/gtm_client_workflows/proposal_system/proposals/greenjobs-official.official.json:96-97` ; proposition ASSET Voyages, l. 276 |
| Formation en ligne 20 €/participant | Déclaration du fondateur (10/11/2026) |
| Missions plateformes 487 €/jour | Malt Research, TJM médian freelance tech : `deliverables/asset_voyages_rfp_2026-10-28/research/market_pricing_paris_2026.md:69` |
| Moteur de prospection 12 000 € | `execution/personal_workflows/self_outbound_system/config/tone.json:228` ; repère : Nick Saraev, « High-ticket services ($10k, $15k, $20k) », `deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md:282` |
| Prototype IA 4 000 € | `tone.json:297` |
| Système complet 5 000 à 15 000 € | `tone.json:150` |
| Vidéo IA 50 à 200 €/plan + 150 € | `directives/gtm_client_workflows/video_edit_client_pipeline.md:17-21,42` |
| Pilote approche de candidats 1 500 à 2 500 € | `deliverables/gaia_2026-09-10/call_brief_2026-09-10.md:82` |
| Assistant téléphonique 199 €/mois | `docs/sales/vitry_dental_one_pager.md:42` |
| Module de veille 1 500 €, connecteur CRM 500 €, version anglaise 750 € | Proposition ASSET Voyages, l. 247, 243, 242 |

## Sources des charges (section B)

| Charge | Source |
|---|---|
| Claude 100 €/mois | Déclaration du fondateur (10/11/2026) |
| Instantly 97 $/mois | Page de facturation : `docs/runbooks/lenore_reply_draft.md:15` (la directive indique 89 €/mois) |
| Google Workspace 8,28 €/mois | `directives/personal_workflows/self_outbound_system.md:95` |
| OpenRouter 10 $/mois | Plafond recommandé : `docs/reference/openrouter_spend_audit_2026-11-03.md:41` |
| Cloudflare 5 $/mois | `greenjobs-official.official.json:98` |
| Domaine 10 €/an | `directives/personal_workflows/self_outbound_system.md:87,93` |
| Meetup Standard 174,99 $/an | Relevé web 10/11/2026 (pages d'aide Meetup, prix « à partir de », variable selon le pays) : [whos-in.app](https://whos-in.app/blog/meetup-pricing-guide-2026) |
| Commissions 10 % | Malt 10 % HT première mission, 5 % après 6 mois : [take-me.fr](https://take-me.fr/en/guides/commissions-plateformes-freelance) ; Upwork 0 à 15 % variable : [upwork.com](https://www.upwork.com/resources/is-upwork-free) ; Free-Work sans commission (source unique, concurrent) |

Calculs : `.tmp/titre_sejour_sources/calc.py`. Seuils officiels 2026 : plafond micro services 83 600 € (2026-2028, proratisé l'année de création) ; franchise TVA services 37 500 € / 41 250 € ([URSSAF](https://www.autoentrepreneur.urssaf.fr/portail/accueil/sinformer-sur-le-statut/toutes-les-actualites/2026--modification-des-seuils-de.html), [impots.gouv](https://www.impots.gouv.fr/professionnel/questions/en-tant-que-micro-entrepreneur-puis-je-etre-redevable-de-la-tva)).

## Points à vérifier avant dépôt

1. **Lettres.** Aucune lettre d'intention ni de recommandation jointe (optionnelles, retirées).
2. **GreenJobs.** Ne rien joindre et ne pas citer GreenJobs dans le dossier. Aucune facturation avant l'autorisation d'exercer.
3. **TVA.** Les années 1 à 3 dépassent 37 500 € et, en année 2 et 3, 41 250 € : TVA facturée dès le dépassement. Vérifier le régime de TVA des clients hors de France.
4. **Plafond micro.** Années 1 à 3 (39 705 €, 51 205 €, 62 770 €) sous 83 600 €. Le plafond est proratisé l'année de création : vérifier selon la date d'immatriculation.
5. **Instantly.** 97 $/mois retenu (page de facturation) : vérifier sur la dernière facture.
6. **OpenRouter.** Fixer le plafond de 10 $/mois sur la clé.
7. **Renouvellement de prodcraft.fyi.** Montant à ajouter.
8. **Délai de 48 à 72 heures.** Joindre des liens vers des sites livrés.
9. **Meetup.** Vérifier le prix de l'abonnement organisateur en France et les frais sur les événements payants.
10. **Formations.** Vérifier si une déclaration d'activité de prestataire de formation est requise (non nécessaire sans financement public ou OPCO).
11. **Calendrier.** Carte actuelle valable jusqu'au 5 mars 2027 : déposer la demande sur l'ANEF avant cette date (vérifier le délai de dépôt recommandé, en général dans les 2 mois précédant l'expiration).

## Repères de marché utilisés (section E et D)

- 157 jours facturables par an : Malt 2024, via blogdumoderateur.com.
- 975 000 micro-entrepreneurs sur 3,03 millions sans chiffre d'affaires déclaré en 2025 : Urssaf Stat'ur 423, via tpeactu.fr (09/2026). À vérifier sur urssaf.fr avant dépôt.
- Site vitrine freelance expérimenté 2 500 à 5 000 € : seedweb.fr, ipaoo.fr (2026).
- Projets d'automatisation PME 2 000 à 6 000 € : workflowpro.fr, czmultimedia.com (2026), grilles de prestataires.
- Repères complémentaires non cités : INSEE, revenu moyen micro-entrepreneurs information-communication 1 050 €/mois (données 2023) ; Malt développeurs 576 € ; Freeland développeur web 400 €. Maker School (Nick Saraev) : premiers projets rapportés 1 400 à 6 350 $, auto-déclarés, aucune donnée France vérifiée ; non cité dans le dossier.
