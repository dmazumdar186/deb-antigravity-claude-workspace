# ASSET Voyages, concept v2: « Du brief au retour »

*Concept paper, written before any design work. 28 October 2026. Model inputs and costs: `research/glm_log.md`.*

## 1. The idea in one line
ASSET does for a business trip what a good exhibit builder does for a stand: it **packs** the request (brief, travel policy, itinerary, bookings) into one travel wallet, **ships** it (the departure, the route), and **unpacks** it on site (badge, programme, the congress hall coming together). Then it brings back the report. The homepage hero is a 30-second scroll-scrubbed film covering that whole job in seven stages.

**Brief → Politique voyage → Itinéraire → Réservation → Départ → Sur place → Retour & reporting**

## 2. How we chose it
We gave the same public-facts brief to two models, each asked for three concepts.

| Source | Concepts | What we kept |
|---|---|---|
| `openai/gpt-6.1-sol` | « Le Dossier qui voyage », « Le Fil sans rupture », « La Date prend place » (it would ship the Dossier) | The tabbed dossier carrying real categories (policy, assistance, expense notes, statistics). The rule "no decorative passport stamps, only real content". The drum *Écouter → Cadrer → Organiser → Accompagner → Analyser* |
| `z-ai/glm-5.3` | « Le Passeport », « De la Demande au Tarmac », « La Carte se déplie » (it would ship Tarmac) | The split-flap departure board. The line "vous partez léger, nous portons le reste", i.e. documents packed into a case. The receipts dropping into the report at the end |

**Verdict.** We shipped the starting candidate « Du brief au retour », enriched with GPT's dossier and GLM's departure board and packing gesture.
- It is the only option with a true **pack → ship → unpack** arc.
- It covers all three trades in one story: the trip, the group in the hall, and the congress badge.
- Each keyframe shows an object a travel manager already handles: the request, the policy, the boarding pass, the expense report.
- GPT's « Dossier » is strong but static, with no departure. GLM's « Tarmac » is legible but sells the airline moment, and it invented figures ("délai de devis < 4 h", "%"), which we rejected.
- « La Carte se déplie » would repeat the v1 fold-out leaflet, which the operator rejected.

## 3. Positioning
**« Optimisez vos voyages d'affaires »** (their slogan, kept). ASSET is *« une agence de voyages d'Affaires à taille humaine, membre du réseau Selectour Affaires »*:
- the closeness of a dedicated advisor (*« interlocuteur dédié »*);
- the scale of the leading network (*« plus de 122 agences et plateaux d'affaires en France »*).

The site should prove ASSET runs the *whole* job, not just the ticket.

## 4. Three buyers, three journeys (RFP §2)
| Buyer | Lands on | Needs to see | Converts by |
|---|---|---|---|
| SME owner / office manager, and the travel or procurement manager | Film → Voyages d'affaires card | Dedicated advisor, policy applied « quel que soit le canal de réservation », 24h/24 7j/7, reporting | Account or travel-audit request (F01) |
| HR / communication manager | MICE card | « dès 10 personnes », « un chef de projet dédié : présent dès la prise de brief », Analyse → Cahier des charges → Réussite | Progressive MICE brief (F02) |
| Congress participant | Congrès card → catalogue | Search, dates, city, official source and verification date | Flight quote prefilled from the listing, from any airport (F03) |

The **existing client** goes to the header link « Espace client », which points to the authorised external tool; no password lives in the CMS.

## 5. What a site like ASSET's must have (from the RFP)
- **Three service doors** on the home page.
- **Approved evidence only.** No invented figures, clients, testimonials or fare claims.
- **A filterable congress catalogue:**
  - search and filters;
  - ascending date sort, pagination and a no-results state;
  - source plus verification date on each listing;
  - GM&E codes never sent to the browser.
- **Forms reachable in 2–3 clicks**, with no account required.
- **French at launch**, with English ready behind the switch.
- **An editor console** for Veena and a backup editor, with 5 roles.
- **Mobile parity.**
- **Premium, understated design.**

## 6. Section map, and how each section carries the concept
| # | Section | Register | Concept role |
|---|---|---|---|
| 0 | Floating pill header + progress bar, logo, « Espace client », FR/EN (EN « bientôt ») | ink | The page itself is the trip; the progress bar is the route |
| 1 | **Film** (hero, 8 viewports, step rail of 7) | paper | Pack → ship → unpack, scrubbed by scroll |
| 2 | Statement band: « Votre voyage n'est plus un coût, mais un avantage. » (from their line « afin que votre voyage ne soit plus un coût mais un avantage pour votre entreprise ») | paper | The promise the film just proved |
| 3 | **Pinned card stack: the contents of the wallet.** Three documents dealt one by one: Voyages d'affaires (a boarding pass), MICE (a seminar programme), Congrès internationaux (a congress badge). Each carries verbatim offer text and a CTA | ink | What comes out of the pochette |
| 4 | **Congress catalogue** (working demo, « — exemple » data) with a prefilled flight quote | paper | The unpack, made functional |
| 5 | **Drum: la méthode ASSET**, 5 steps: Analyse → Cahier des charges → Politique & réservation → Accompagnement 24h/24 → Reporting | navy | The film's stages, as a method |
| 6 | Capabilities hover list: the 12 services actually listed on their site | ink | Everything inside the wallet |
| 7 | L'agence: Issy-les-Moulineaux, Selectour Affaires, the relationship line | paper | The people behind the film |
| 8 | Contact: three journeys (Entreprise / Événement / Congrès) plus the phone number | ink | Departure gate |
| 9 | Footer | ink | |

## 7. Rules for the build
- **Facts:** verbatim from `HANDOFF.md` and the live pages, sources listed there. Congress data is clearly marked as an example.
- **Film:** self-rendered in vector (paper, ink, orange route), served as an mp4 or webm blob for scrubbing, with a live-canvas fallback. With reduced motion it shows a poster and a static list of the stages.
- **Look:** paper `#F2EEE5`, ink `#0A1F30`, ASSET navy `#0D3048`, accent orange `#EF760D` taken from the logo.
- **Fonts:** EB Garamond for display (precomposed French accents), Inter for text, the system monospace for labels.
- **Mobile:** below 800 px every pinned section flattens, and nothing fixed overlaps content.
