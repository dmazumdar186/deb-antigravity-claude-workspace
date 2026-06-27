# Notice de transparence — Assistante vocale IA « Lisa »

*Document publié au titre de l'article 13 du règlement européen (UE) 2024/1689 sur l'intelligence artificielle (EU AI Act). Applicable à partir du 2 août 2026.*

---

## Système IA

**Nom** : Lisa — assistante vocale francophone pour cabinet dentaire.
**Fournisseur** : Debanjan Mazumdar (prodcraft.fyi), 6 rue des Malassis, 94400 Vitry-sur-Seine, France.
**Déployeur** : {{NOM_DU_CABINET}}, {{ADRESSE}}.
**Date de mise en service** : {{DATE_DEPLOIEMENT}}.
**Version** : 1.0.

## Classification

Système classé **à haut risque** au titre de l'annexe III, point 5.b du règlement (système IA utilisé pour évaluer ou déterminer l'accès et le bénéfice des services de soins de santé).

## Finalité

L'assistante vocale Lisa décroche les appels téléphoniques entrants du Cabinet, identifie le motif de l'appel, propose des créneaux de rendez-vous disponibles et confirme la réservation dans l'agenda du Cabinet. Elle transfère l'appel vers un membre du personnel humain dans les cas suivants :
- l'appelant demande explicitement un humain (mot-clé « opérateur ») ;
- l'IA détecte des signes d'urgence médicale (douleur forte, abcès, saignement, traumatisme) ;
- l'appelant ne s'exprime pas en français ;
- l'IA rencontre une situation qu'elle n'a pas la compétence de traiter (tarifs, conseils médicaux, modification d'un dossier patient).

**Ce que Lisa ne fait pas** : aucun diagnostic, aucune information tarifaire, aucune modification de dossier patient, aucun conseil médical.

## Modèles d'IA utilisés

| Composant | Fournisseur | Description |
|---|---|---|
| Reconnaissance vocale + génération vocale + raisonnement | Google — Gemini 2.5 Flash (API « Live ») | Modèle de fondation multimodal traitant l'audio en français de bout en bout |
| Détection des mots-clés d'urgence | Règle déterministe en Python | Liste fermée de motifs (regex) ; pas d'IA |
| Lecture de l'agenda | API Google Calendar | Pas d'IA |

## Données d'entrée

- Voix de l'appelant pendant la durée de l'appel (audio PCM 16 kHz).
- Numéro d'appel entrant (CLI) lorsque disponible.

## Données de sortie

- Réponses vocales en français.
- Appels à des outils logiciels : `list_slots(motif)` → liste de 3 créneaux ; `book_slot(slot_id, nom, téléphone, motif)` → identifiant de rendez-vous.
- Transcription textuelle de l'appel (à des fins d'audit, conservée 30 jours).

## Performance attendue

| Indicateur | Cible |
|---|---|
| Taux de classification correcte du motif (consultation / détartrage / contrôle / urgence) | ≥ 92 % sur le corpus d'évaluation |
| Latence entre la fin de la parole de l'appelant et le début de la réponse vocale | < 800 ms (audio web) ; < 1500 ms (téléphone) |
| Taux de transferts humains sur situations d'urgence ambiguës | 100 % (politique de surrédondance volontaire) |
| Taux d'erreur sur la rétention du numéro de rappel | < 2 % (vérification par répétition obligatoire) |

Ces indicateurs sont mesurés mensuellement et publiés au Cabinet sur demande.

## Limites connues

- **Accent non métropolitain (subsaharien, maghrébin, antillais)** : le taux d'erreur sur l'intention peut être supérieur. Mitigation : fallback automatique vers un humain en cas d'incertitude.
- **Voix d'enfant** : non testé. Mitigation : transfert humain par défaut.
- **Environnement bruyant côté appelant** : le taux d'erreur augmente. Mitigation : Lisa demande de répéter une fois, puis transfert si l'incompréhension persiste.
- **Plages horaires** : Lisa ne propose que les créneaux conformes aux heures d'ouverture configurées. Une mise à jour des horaires est une opération manuelle du Cabinet.

## Droit de contestation et intervention humaine

À tout moment de l'appel, l'appelant peut demander à parler à un humain en disant « opérateur ». Le transfert est inconditionnel.

Le Cabinet peut désactiver Lisa à tout moment via le tableau de bord administrateur. La désactivation est immédiate.

## Sécurité et hébergement

- Toutes les données de santé (motif, transcription, enregistrement) sont hébergées sur une infrastructure certifiée **Hébergeur de Données de Santé (HDS)** localisée en France.
- Chiffrement TLS 1.3 en transit, AES-256 au repos.
- Suppression automatique des enregistrements après 30 jours.

## Évaluation de conformité

Documentation technique tenue à disposition de l'autorité française de surveillance du marché (DGCCRF / ANSSI / CNIL selon répartition) à l'adresse postale ci-dessus. Délai de communication sur demande : 10 jours ouvrés.

## Mise à jour

Cette notice est mise à jour à chaque évolution significative du système (changement de modèle d'IA, modification du périmètre fonctionnel, nouvelle limite identifiée). La version actuelle est consultable à l'adresse {{URL_PUBLIQUE}}.

## Contact

Toute question relative à cette notice peut être adressée à : Debanjan Mazumdar — debolshop@gmail.com — 6 rue des Malassis, 94400 Vitry-sur-Seine.

---

Dernière mise à jour : {{DATE}}.
