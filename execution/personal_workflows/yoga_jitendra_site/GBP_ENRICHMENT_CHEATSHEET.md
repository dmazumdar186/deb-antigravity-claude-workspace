# GBP enrichment cheat-sheet — for Debanjan @ debolshop@gmail.com

Copy-paste-ready values for the Google Business Profile at CID `0xc39304b7fc72d34b` (Yoga avec Jitendra, 22 rue Eugène Manuel 75016 Paris). Go through this once, top-to-bottom, in the GBP dashboard: [business.google.com](https://business.google.com).

Audit assumptions before writing anything:
- Address = Option A (public, exact). Address stays as-is on the profile.
- No paid ads, no promotions section, no "sur devis" prices in any field (Jitendra's existing rule).
- Every FR field also gets an EN counterpart — GBP supports per-language fields via profile duplication or the "add language" flow in some regions; if the FR field is the only one available, prioritize FR (French audience is the primary market).

---

## 1. Business name

**Yoga avec Jitendra**

Don't add descriptors like "· Hatha Yoga · Paris" — Google penalizes keyword-stuffing in the name field. Descriptive terms belong in the categories + description.

## 2. Categories

- **Primary category:** `Yoga instructor` (`Instructeur de yoga`)
- **Secondary category 1:** `Yoga studio` (`Studio de yoga`)
- **Secondary category 2:** `Meditation instructor` (`Instructeur de méditation`) — optional; useful if the meditation-portrait hero is central to positioning.

Do not add more — GBP limits to 10 but Google favors 2-3 well-matched over 10 diluted.

## 3. Contact

- **Phone:** `+33 7 58 25 55 83`
- **Website:** `https://yogaavecjitendra.fr`  (**IMPORTANT:** if it currently points at the Google Sites URL, change it now — the new site is canonical.)
- **Appointment link:** `https://calendly.com/yogaavecjitendra/15min`
- **Menu/services link:** leave empty (not applicable).

## 4. Service area (delivery / at-home / corporate radius)

GBP settings → Location and areas → Service areas. Add:
- Paris 1er, 2e, 3e, 4e, 5e, 6e, 7e, 8e, 9e, 10e, 11e, 12e, 13e, 14e, 15e, 16e, 17e, 18e, 19e, 20e
- Boulogne-Billancourt (92100)
- Neuilly-sur-Seine (92200)
- Levallois-Perret (92300)
- Issy-les-Moulineaux (92130)
- Saint-Cloud (92210)
- Puteaux (92800) — La Défense corporate

## 5. Hours

From `schedule.fr.json` the schedule is "sur rendez-vous, cadre chaque semaine." GBP requires concrete hours. Two options:

- **Option A (recommended):** open Mon–Sat 07:00–20:00, closed Sunday. Broad enough to cover all class types.
- **Option B:** enable "By appointment only" if that flag is available in your GBP UI. Some categories support it.

Special hours: leave empty until real closures appear.

## 6. Business description

FR (750-char max, no phone/URL/promotion — Google strips those):

> Cours de Hatha Yoga traditionnel indien à Paris avec Jitendra Kumar. Enseignement structuré dans la lignée indienne : respiration, mouvement, alignement, relaxation. Séances au studio à Passy (Paris 16), à domicile dans tout Paris et proche banlieue, en entreprise, et en plein air au Champ-de-Mars ou au Bois de Boulogne. Certifié 500 h au Centre Tapovan Paris. Enseigne également au Tapovan Open University en Normandie et à L'école châlonnaise « Au pied du cerisier ». Cours particuliers, petits groupes, ateliers bilingues français/anglais.

EN (if GBP language slot allows):

> Traditional Indian Hatha Yoga in Paris with Jitendra Kumar. Structured practice in the Indian lineage: breath, movement, alignment, relaxation. Sessions at the Passy studio (Paris 16), at-home across Paris and inner suburbs, in-company, and outdoor at Champ-de-Mars or Bois de Boulogne. 500-hour certification at Centre Tapovan Paris. Also teaches at Tapovan Open University in Normandy and at L'école châlonnaise «Au pied du cerisier». Private lessons, small groups, bilingual FR/EN workshops.

## 7. Services (individual service entries under Products/Services)

Add each as a separate service (no price — Jitendra's rule):

1. **Cours particulier au studio (Passy)** — Séance individuelle de Hatha Yoga au studio de Passy, Paris 16. Adapté à tous les niveaux. Sur rendez-vous.
2. **Cours à domicile** — Cours particulier chez vous, Paris et proche banlieue. Idéal pour les débutants, les emplois du temps chargés, ou pour pratiquer en duo/famille.
3. **Yoga en entreprise** — Ateliers de bien-être au bureau : Hatha Yoga, respiration, méditation. Formules ponctuelles ou récurrentes. Bilingue FR/EN pour équipes internationales.
4. **Yoga en plein air** — Séances de groupe au Champ-de-Mars ou au Bois de Boulogne, annoncées sur MeetUp « Paris Hatha yoga ». Ouvertes à tous.
5. **Ateliers & retraites** — Ateliers thématiques (respiration, méditation, textes traditionnels) au studio, en Normandie, ou en résidentiel.

Repeat in EN if the language slot exists — same names, translate the descriptions.

## 8. Photos (upload from `/public/assets/images/`)

Recommended order (Google shows the first ~3 prominently):
1. `meditation-portrait.jpg` — the current hero. Set as **Cover photo**.
2. `portrait-namaste.jpg` — Jitendra's face. Set as **Logo / profile photo**.
3. `champ-de-mars-eiffel.jpg` — outdoor practice with Eiffel Tower.
4. `teaching-backbend.jpg` — Jitendra guiding a student.
5. Any additional interior studio shot if available.

Alt/caption: use the same alt text already in the JSON files.

## 9. Attributes

Tick the ones that apply:
- Wheelchair-accessible? — leave OFF unless verified.
- Online classes — ON if he does virtual sessions.
- LGBTQ+ friendly — ON (safe default for wellness).
- Onsite services — ON (studio).
- Language — French, English (both).

## 10. `sameAs` / Linked profiles (in the profile's URL fields where available)

- Instagram: https://www.instagram.com/jitendrakuma/
- MeetUp: https://www.meetup.com/paris-hatha-yoga/
- Superprof: https://www.superprof.fr/hatha-yoga-paris-experience-personnalisee-studio-prive-passy-domicile.html
- LinkedIn / YouTube / Facebook — pull from the Google Sites page https://sites.google.com/view/yogaavecjitendra/home
- L'Hebdo du Vendredi press article — add under "News/mentions" if that field exists

## 11. GBP Posts cadence (Phase 4 ongoing)

2 posts / month, ~5 min each. Rotate:
- Weekly outdoor session at Champ-de-Mars → "What's new" post with a photo.
- Seasonal offering (retreats, workshops) → "Offer" post (without price — description only).
- Student milestone / class recap → "What's new" post.
- Q&A ("What's the difference between Hatha and Vinyasa?") → answer format.

## 12. Q&A seeding

Add these Q&A pairs (owner-asks-owner-answers is allowed and helpful for local SEO):

1. Q: `Est-ce que Jitendra propose des cours à domicile ?` A: `Oui — cours particuliers à domicile dans tout Paris et proche banlieue (Boulogne, Neuilly, Levallois, Issy, Saint-Cloud, Puteaux). Écrivez-lui pour caler un créneau.`
2. Q: `Do you offer classes in English?` A: `Yes — Jitendra teaches bilingual French/English private lessons and corporate workshops. Message him directly to arrange a session.`
3. Q: `Quelle différence entre Hatha Yoga et Vinyasa ?` A: `Le Hatha Yoga traditionnel indien est plus lent et structuré : chaque posture est tenue, alignée, et reliée à la respiration. Le Vinyasa est un enchaînement plus dynamique. La méthode de Jitendra est ancrée dans la lignée indienne — travail sur la stabilité, l'alignement, et la circulation de l'énergie.`
4. Q: `Faut-il de l'expérience pour venir à un cours ?` A: `Non — Jitendra adapte chaque séance au niveau et à la disponibilité corporelle de l'élève. Débutants bienvenus.`

## 13. Review response templates (for when reviews come in)

**5-star FR:**
> Merci [Prénom] 🙏 Votre confiance et votre pratique nourrissent ce chemin partagé. À très bientôt sur le tapis. — Jitendra

**5-star EN:**
> Thank you [Name] 🙏 Your trust and your practice nourish this shared path. See you on the mat. — Jitendra

**Constructive (3-4 star) FR:**
> Merci [Prénom] pour votre retour honnête — c'est précieux. Je serais ravi d'en discuter avec vous si vous voulez qu'on ajuste la pratique. N'hésitez pas à m'écrire directement au +33 7 58 25 55 83. — Jitendra

**1-2 star FR (rare):**
> Bonjour [Prénom], je suis désolé que la séance n'ait pas répondu à vos attentes. Merci de me contacter directement (+33 7 58 25 55 83) — j'aimerais comprendre ce qui a manqué et voir comment corriger.

---

## Execution order (do sections in this order for max value / min time)

1. Section 3 (Contact — change website URL to yogaavecjitendra.fr) — **highest priority, ~1 min**. This alone starts sending GBP → site authority signals.
2. Section 2 (Categories) — **~2 min**. Google's ranking algorithm keys off this.
3. Section 6 (Description) — **~3 min**. Paste FR + EN.
4. Section 4 (Service areas) — **~5 min**. Longest but critical for map-pack coverage across Paris + banlieue.
5. Section 8 (Photos) — **~5 min**. Upload the 5 photos.
6. Section 7 (Services) — **~5 min**. 5 services × ~1 min each.
7. Section 10 (`sameAs` links) — **~3 min**.
8. Section 12 (Q&A seeding) — **~5 min**.
9. Sections 5, 9, 11, 13 — ongoing / lower priority.

**Total: ~30 min** for a complete initial enrichment. Nothing here needs Jitendra's involvement.
