# AIPD — Assistante vocale IA en cabinet dentaire

**Analyse d'impact relative à la protection des données** — Modèle conforme à l'art. 35 RGPD + au guide CNIL+HAS « IA en santé » de février 2026.

> Modèle. À compléter avec les spécificités du Cabinet avant déploiement avec des patients réels (Phase 5). Ne dispense pas d'une revue par un DPO ou un conseil juridique.

---

## 1. Description du traitement

**Finalité.** Prise de rendez-vous par téléphone à l'aide d'un agent vocal automatisé en français. L'agent décroche, identifie le motif, propose 3 créneaux disponibles, confirme la réservation dans l'agenda du Cabinet, ou transfère vers un humain en cas d'urgence ou à la demande de l'appelant.

**Périmètre.** Patients (existants ou nouveaux) qui appellent le numéro principal du Cabinet en dehors des horaires de présence du secrétariat, ou pendant les pics où le standard est saturé.

**Acteurs.**
- Responsable de traitement : le Cabinet {{NOM}}.
- Sous-traitant : Debanjan Mazumdar (prodcraft.fyi).
- Sous-traitants ultérieurs : Google (modèle Gemini), hébergeur HDS, Modal Labs (phase démo uniquement).

## 2. Catégories de données

| Catégorie | Exemples | Sensible |
|---|---|---|
| Identité | Prénom, nom de l'appelant | Non |
| Coordonnées | Numéro de téléphone | Non |
| Santé | Motif d'appel (« douleur », « détartrage », « urgence ») | **Oui (art. 9 RGPD)** |
| Voix | Enregistrement audio de l'appel | **Oui (donnée biométrique)** |
| Métadonnées | Date, durée, transcription | Non en soi, mais **Oui dans ce contexte** car associées à des données de santé |

## 3. Base légale

Triple base juridique :
- **Exécution du contrat de soins (art. 6.1.b)** pour les données d'identification et de contact.
- **Consentement explicite recueilli au début de l'appel (art. 9.2.a)** pour les données de santé, l'enregistrement vocal et la transcription. La phrase de consentement est lue en première position et le patient peut refuser en disant « opérateur » à tout moment.
- **Intérêt légitime** du Cabinet pour conserver la preuve contractuelle de la prise de rendez-vous (30 jours).

## 4. Risques pour les personnes

| Risque | Probabilité | Gravité | Niveau global |
|---|---|---|---|
| Mauvaise compréhension du motif → triage incorrect (urgence non détectée) | Moyenne | **Critique** | **Élevé** |
| Fuite des enregistrements vocaux | Faible | Élevée | Moyen |
| Réutilisation des données par le sous-traitant LLM (Google) | Faible | Élevée | Moyen |
| Discrimination algorithmique (accent, langue, âge) | Moyenne | Moyenne | Moyen |
| Atteinte à la confidentialité par accès non autorisé au tableau de bord | Faible | Élevée | Moyen |
| Patient qui croit parler à un humain | Faible (mitigé par la phrase de consentement) | Moyenne | Faible |

## 5. Mesures de mitigation

**Pour le triage d'urgence (risque le plus élevé).**
- Liste de mots-clés d'urgence prédéfinie : « très mal », « abcès », « cassé », « saigne », « infection », « fièvre », « ne tiens plus », « j'ai mal depuis ».
- Sur détection : pas de prise de RDV par l'IA, transfert immédiat vers un humain, message clair *« Je vous transfère immédiatement au cabinet »*.
- Hors heures ouvrées : message *« Pour une urgence vitale, composez le 15 »* et redirection vers le service de garde local.
- Audit hebdomadaire (Phase 5) : revue d'un échantillon de 10 % des appels classés non-urgents pour détecter les urgences manquées.

**Pour la fuite d'enregistrements.**
- Hébergement HDS, chiffrement TLS 1.3 en transit, chiffrement AES-256 au repos.
- Rétention 30 jours puis suppression automatique.
- Accès sur authentification forte (2FA) uniquement, journalisé.

**Pour la réutilisation par Google.**
- Utilisation de Gemini API en région européenne (europe-west) avec opt-out explicite de l'entraînement modèle (option « data not used for training »).
- À défaut, bascule vers une alternative auto-hébergée (Whisper + Llama) avant Phase 5.

**Pour la discrimination algorithmique.**
- Corpus d'acceptance qui inclut au moins un échantillon d'accent non-métropolitain (cas `accented_fr_maghrebi` du corpus actuel).
- En cas d'échec d'intent : fallback systématique sur « opérateur », jamais de tentative de devinette.

**Pour l'accès au tableau de bord.**
- Authentification par secret partagé (`X-Voice-Agent-Secret`) — Phase 1.
- Bascule vers OAuth Cabinet avec rôles fins — Phase 5.

**Pour la confusion humain/IA.**
- Phrase de consentement obligatoire en première position de l'appel : *« Cet appel est traité par une intelligence artificielle. »*
- Bandeau « démo — données simulées » sur la page web tant que `DEMO_MODE=true`.
- Information sur le site du Cabinet (mention légale + en-tête de la page contact).

## 6. Avis du DPO / consultation des personnes concernées

- DPO du Cabinet consulté : {{NOM_DPO}}, le {{DATE}}.
- Avis : à compléter.
- Consultation des patients : information collective via affichage en salle d'attente + sur le site web. Consultation individuelle au cas par cas si demandé.

## 7. Conformité EU AI Act

L'assistante vocale est classée **système à haut risque** au sens du règlement européen sur l'IA (annexe III, point 5.b « accès et bénéfice des services de santé »). Obligations applicables à partir du 2 août 2026 :
- Notice de transparence en français accessible publiquement.
- Journal d'audit des décisions (créneaux proposés, transferts humains).
- Évaluation de conformité tenue à disposition de l'autorité de surveillance.
- Possibilité pour l'utilisateur de contester une décision (= demander un humain).

> Toutes ces obligations sont prises en compte dans la conception. Le journal d'audit est implémenté dans `app.py` (Phase 5 — table KV/D1 dédiée).

## 8. Décision

| Critère | Verdict |
|---|---|
| Le traitement est-il nécessaire pour la finalité ? | Oui — comble une lacune réelle (appels manqués). |
| Les risques résiduels sont-ils acceptables ? | Oui, sous réserve de l'audit hebdomadaire d'urgences (Phase 5). |
| Les mesures de mitigation sont-elles documentées et techniquement effectives ? | Oui, voir corpus d'acceptance + tests. |
| Les patients sont-ils informés ? | Oui (consentement explicite + bandeau + site). |

**Décision : déploiement autorisé après signature de l'accord de sous-traitance et bascule HDS.**

Signé : {{REPRESENTANT_CABINET}}, le {{DATE}}.
