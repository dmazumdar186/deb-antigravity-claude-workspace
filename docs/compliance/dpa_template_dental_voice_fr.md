# Accord de sous-traitance — Assistante vocale IA (RGPD art. 28)

**Modèle** — À adapter avant signature. Ce document fixe les obligations du sous-traitant (Debanjan Mazumdar, ci-après « le Prestataire ») envers le Responsable de traitement (le cabinet dentaire client, ci-après « le Cabinet ») pour l'utilisation de l'assistante vocale IA déployée sur l'infrastructure du Prestataire.

> Avertissement : ce modèle ne dispense pas d'une revue juridique. Le Prestataire et le Cabinet sont invités à le faire valider par leurs conseils respectifs avant signature, notamment au regard du **Guide CNIL+HAS « IA en santé » (février 2026)** et du **règlement européen sur l'IA (entrée en vigueur du volet haut-risque le 2 août 2026)**.

---

## 1. Parties

- **Responsable de traitement (le Cabinet)** : {{NOM_DU_CABINET}}, {{ADRESSE}}, SIRET {{SIRET}}, représenté par {{REPRESENTANT}}.
- **Sous-traitant (le Prestataire)** : Debanjan Mazumdar, micro-entrepreneur — 6 rue des Malassis, 94400 Vitry-sur-Seine, France, SIREN {{SIREN_PRESTATAIRE}}.

## 2. Objet

Le Prestataire exploite pour le compte du Cabinet une assistante vocale IA en français (« Lisa ») qui :
- décroche les appels téléphoniques entrants ;
- identifie le motif d'appel ;
- propose et confirme des créneaux de rendez-vous ;
- transfère vers un humain en cas d'urgence ou à la demande.

## 3. Données traitées

| Donnée | Nature | Base légale | Conservation |
|---|---|---|---|
| Nom + prénom de l'appelant | Donnée à caractère personnel | Exécution du contrat patient (art. 6.1.b) | Durée du dossier patient (10 ans réglementaires) côté Cabinet ; 30 jours côté Prestataire (pour audit). |
| Numéro de téléphone | Donnée à caractère personnel | Idem | Idem |
| Motif d'appel (« détartrage », « urgence »…) | Donnée de santé (art. 9.2.h) | Consentement explicite recueilli au début de l'appel | Idem |
| Enregistrement vocal | Donnée de santé | Consentement explicite + intérêt légitime (preuve contractuelle) | 30 jours sur stockage HDS, puis suppression automatique |
| Transcription textuelle | Donnée de santé | Idem | Idem |

## 4. Hébergement

Toutes les données de santé (motif, enregistrements, transcriptions) sont hébergées sur une infrastructure **certifiée HDS** (Hébergeur de Données de Santé) localisée en France. Le Prestataire fournit l'attestation HDS à la signature et à chaque renouvellement annuel.

> Phase 1 (démo) : pas de données patient. Hébergement Modal (États-Unis) acceptable car aucune donnée réelle ne transite.
> Phase 5 (production) : bascule HDS obligatoire avant tout appel d'un vrai patient. Hébergeurs candidats : OVH HDS, Outscale, Healthcare Cloud (Microsoft).

## 5. Mesures de sécurité

- Chiffrement TLS 1.3 sur tous les flux entrants/sortants.
- Authentification par secret partagé (`X-Voice-Agent-Secret`) pour toute API administrative.
- Aucune donnée patient stockée dans des journaux d'application (logs Modal).
- Compte de service Google dédié, restreint au seul agenda du Cabinet, révocable en un clic.
- Sauvegardes chiffrées au repos sur le stockage HDS.

## 6. Sous-traitance ultérieure

Le Prestataire s'appuie sur les sous-traitants suivants :

| Sous-traitant | Rôle | Pays | Certification |
|---|---|---|---|
| Google (Gemini API) | Modèle vocal IA | UE (région europe-west) | ISO 27001 / 27017 / 27018 |
| Hébergeur HDS (Phase 5) | Stockage transcripts + enregistrements | France | HDS certifié |
| Modal Labs | Hébergement applicatif (phase démo) | États-Unis | SOC 2 Type II |

Tout changement de sous-traitant fait l'objet d'une notification écrite au Cabinet **15 jours avant** la bascule. Le Cabinet dispose d'un droit d'opposition.

## 7. Droits des personnes

Le Cabinet reste l'interlocuteur unique des patients pour l'exercice de leurs droits (accès, rectification, effacement, opposition). Le Prestataire fournit dans un délai de **3 jours ouvrés** toute information ou export nécessaire pour répondre à une demande patient.

## 8. Violations de données

Le Prestataire notifie le Cabinet **dans les 24 heures** suivant la découverte d'une violation de données (intrusion, fuite, perte de disponibilité). Le Cabinet reste responsable de la notification CNIL si nécessaire (art. 33 RGPD).

## 9. Audit

Le Cabinet peut, sur préavis de 10 jours ouvrés, auditer les mesures techniques et organisationnelles du Prestataire (1 fois par an, ou ad hoc en cas d'incident). Le Prestataire fournit les logs d'accès, l'attestation HDS, et la documentation technique.

## 10. Fin du contrat

À la fin du contrat (résiliation, non-renouvellement) :
- Le Prestataire restitue toutes les données au Cabinet sous **15 jours** dans un format standard (CSV pour l'agenda, MP3 pour les enregistrements, JSON pour les transcriptions).
- Le Prestataire supprime toutes les copies sous **30 jours** après restitution et fournit une attestation de suppression signée.

## 11. Responsabilité

La responsabilité du Prestataire est limitée au montant des sommes versées par le Cabinet au titre des 12 derniers mois, sauf en cas de faute lourde ou intentionnelle.

## 12. Loi applicable

Droit français. Tribunal compétent : tribunal judiciaire de Créteil.

---

Fait à {{LIEU}}, le {{DATE}}, en deux exemplaires originaux.

**Pour le Cabinet :** {{REPRESENTANT}}, signature précédée de la mention « lu et approuvé »

**Pour le Prestataire :** Debanjan Mazumdar, signature précédée de la mention « lu et approuvé »
