# Likeness Release Template (v2v editing)

> **Not legal advice.** This template is a starting point drafted 2026-07-07 for use with the workspace's video-to-video editing pipeline. Have it reviewed by counsel before use with paying clients in France or the EU. Adapted to satisfy French *droit à l'image* + GDPR principles for biometric-adjacent personal data.

Two copies below: **English (short-form)** and **French (short-form)**. Both should be executed for FR-market clients; either alone is acceptable for single-jurisdiction jobs.

---

## English — Likeness release for AI-modified video

**Between:**
- **Subject** (the person appearing in the source footage): _________________
- **Client** (the entity commissioning the AI-modified video): _________________
- **Provider** (the entity performing the AI modification): _________________

**Effective date:** _________________
**Expiry date:** _________________  (leave blank for open-ended; recommended max 5 years)

### 1. Grant

The Subject grants the Client and the Provider a non-exclusive, revocable, limited license to:

- Capture, record, and store video footage in which the Subject appears (the "Source Footage");
- Modify the Source Footage using AI video-to-video editing tools (including but not limited to Higgsfield, Gemini Omni, Runway, Sora, Veo) to produce derivative works (the "Modified Footage");
- Use the Modified Footage in the Client's marketing, advertising, social media, and organic content channels described in Schedule A.

### 2. Permitted uses (Schedule A — check all that apply)

- [ ] Client's paid advertising campaigns
- [ ] Client's organic social media (specify platforms: __________)
- [ ] Client's owned websites and landing pages
- [ ] Client's owned newsletters and email marketing
- [ ] Other (specify): __________

### 3. Prohibited uses

The Subject explicitly does NOT consent to use of the Modified Footage for:

- Political messaging or endorsement of political figures, parties, or causes
- Non-consensual imagery of any kind (including intimate, harassing, or degrading content)
- Impersonation of the Subject in interviews, statements, or endorsements the Subject did not personally make
- Misleading news framing or fabricated journalism
- Sale or sublicense to third parties without a new signed release

### 4. Retention and deletion

- The Provider will retain Source Footage on its infrastructure for the duration of production and delete or archive within thirty (30) days of Modified Footage delivery.
- The Provider will retain this signed release for five (5) years for legal audit purposes.
- The Subject may request deletion of all Modified Footage from Client-controlled channels with thirty (30) days notice; use in third-party redistributed contexts (e.g. viewers who saved local copies) is out of the Client's control.

### 5. Revocation

The Subject may revoke this release with written notice to the Client and Provider. Revocation takes effect for future uses only; the Subject waives claims against uses already made in good-faith reliance on this release prior to the notice date.

### 6. Compensation

- [ ] Included in Subject's fee for the underlying production (default)
- [ ] Separate fee: __________ EUR
- [ ] Other consideration: __________

### 7. Signatures

Subject: _________________________  Date: _________________

Client representative: _________________________  Date: _________________

Provider representative: _________________________  Date: _________________

---

## Français — Autorisation de droit à l'image (montage vidéo par IA)

**Entre:**
- **Le Sujet** (la personne apparaissant dans la vidéo source): _________________
- **Le Client** (l'entité commanditant la vidéo modifiée par IA): _________________
- **Le Prestataire** (l'entité effectuant la modification par IA): _________________

**Date d'effet:** _________________
**Date d'expiration:** _________________  (laisser vide pour une durée indéterminée; recommandation: 5 ans max)

### 1. Concession de droits

Le Sujet accorde au Client et au Prestataire un droit non-exclusif, révocable, et limité de:

- Capturer, enregistrer et stocker les séquences vidéo dans lesquelles le Sujet apparaît (les "Séquences Sources");
- Modifier les Séquences Sources à l'aide d'outils d'édition vidéo par intelligence artificielle (incluant sans s'y limiter Higgsfield, Gemini Omni, Runway, Sora, Veo) pour produire des œuvres dérivées (les "Séquences Modifiées");
- Utiliser les Séquences Modifiées dans les canaux marketing, publicitaires et de communication du Client décrits à l'Annexe A.

### 2. Usages autorisés (Annexe A — cocher les cases applicables)

- [ ] Campagnes publicitaires payantes du Client
- [ ] Réseaux sociaux organiques du Client (préciser plateformes: __________)
- [ ] Sites web et pages de destination du Client
- [ ] Newsletters et emailings du Client
- [ ] Autre (préciser): __________

### 3. Usages prohibés

Le Sujet ne consent explicitement PAS à l'usage des Séquences Modifiées pour:

- Messages politiques ou soutien à des personnalités, partis, ou causes politiques
- Imagerie non-consensuelle de toute nature (contenu intime, harcelant, ou dégradant)
- Usurpation de l'identité du Sujet dans des interviews, déclarations, ou recommandations que le Sujet n'a pas personnellement effectuées
- Cadrage journalistique trompeur ou journalisme fabriqué
- Vente ou sous-licence à des tiers sans nouvelle autorisation signée

### 4. Conservation et suppression

- Le Prestataire conservera les Séquences Sources sur son infrastructure pendant la durée de la production et les supprimera ou archivera dans les trente (30) jours suivant la livraison des Séquences Modifiées.
- Le Prestataire conservera la présente autorisation signée pendant cinq (5) ans à des fins d'audit légal.
- Le Sujet peut demander la suppression de toute Séquence Modifiée des canaux contrôlés par le Client moyennant un préavis de trente (30) jours; l'usage dans des contextes redistribués par des tiers (par exemple, spectateurs ayant sauvegardé des copies locales) échappe au contrôle du Client.

### 5. Révocation

Le Sujet peut révoquer la présente autorisation par notification écrite au Client et au Prestataire. La révocation prend effet pour les usages futurs uniquement; le Sujet renonce aux recours contre les usages déjà effectués de bonne foi antérieurement à la date de notification.

### 6. Contrepartie

- [ ] Incluse dans les honoraires du Sujet pour la production sous-jacente (par défaut)
- [ ] Honoraires séparés: __________ EUR
- [ ] Autre contrepartie: __________

### 7. Signatures

Le Sujet: _________________________  Date: _________________

Représentant du Client: _________________________  Date: _________________

Représentant du Prestataire: _________________________  Date: _________________

---

## Operator instructions

1. Send the release to the Client's producer/coordinator BEFORE the shoot day.
2. Every human subject appearing in source footage supplied for `--sensitivity sensitive` pipeline runs must sign a copy.
3. Store signed PDFs at `.tmp/video/<project-slug>/consent/<subject-slug>.pdf` per project.
4. Reference the file path in the pipeline invocation: `--consent-verified .tmp/video/<slug>/consent/<subject>.pdf`.
5. The pipeline hashes the file (SHA-256) and logs `path + sha256 + mtime` to `<out>/run.log`. This is the audit trail — do not rely on it as content-validation.
6. Retain signed originals for 5 years minimum. Store scans in the Google Drive folder `Client Contracts / Video Releases / <client-slug>/`.
