# 23. The "iPhone moment" for ASSET Voyages: research, candidates, debate, winner, demo spec

Internal, for Debanjan only · research done 5 Nov 2026 · delivery alongside the five-story demos on Fri 6 Nov 2026.
Nothing here was built or committed. Every sector claim carries a source line in §1; where a page could not be fetched, that is said.

**Winner in one line:** « Le lien de groupe » — one shareable link per congress enquiry that lets each delegate enter their own travel details once, filling a live manifest in ASSET's back-office (with the Air France-KLM GM&E group threshold and the quote-ready CSV), so Veena stops chasing fourteen doctors by email for the same spreadsheet.
**Runner-up:** CO2e per route on every congress page and flight quote, computed offline from ADEME factors (a legal information duty for travel agencies that nobody in ASSET's peer group displays).

---

## 1. Sources (all accessed 2026-11-05)

| # | What it establishes | URL |
|---|---|---|
| S1 | French medical-congress travel agencies: Agence Buzz (compliance declarations to CNOM, ticket booking, hotels, expense collection; **no portal, app or online tool described**); Beaux Regards (a contact form only; a stray "some-randome-random" placeholder on the page); Medicom International; Europa Booking & Services (congress hotel booking site built with H24 Travel) | https://www.agencebuzz.com/evenementiel/congres-medicaux/ · https://beauxregards.eu/ · https://www.medicom-international.fr/ · https://www.cardio-online.fr/congres-sfc/jesfc-2027/hebergement-transport-des-journees-europeennes-de-la-societe-francaise-de-cardiologie |
| S2 | Selectour Affaires PCO page: lists mobile app, "Réservations centralisées", "Suivi budgétaire", "Communication avec les participants", "Reporting personnalisé"; **no delegate self-registration, no CO2** | https://www.selectour-affaires.com/agence-pco-congres |
| S3 | Selectour member peers (Wagram Voyages, Corpotravel, Verdié Business, Travelil) present "tarifs négociés, assistance 24h/24"; brochure sites | https://www.wagram-voyages.com/agence-de-voyage-selectour/ · https://www.selectour-affaires.com/agences/TOULOUSE · https://www.selectour-affaires.com/agences/LILLE |
| S4 | ASSET's live site menu: Services incl. "Statistiques" ("Un reporting complet et personnalisé"), "Géolocalisation", "Développement durable" (no detail), tools IRES, Smart app, OPTIM R; **no congress page, no CO2 figure** | https://www.asset-voyagesdaffaires.com/ |
| S5 | Air France-KLM GM&E rules (from search snippets of klm.fr / Atout France PDF; the pages returned HTTP 503 to direct fetch): organiser gets a kit with a unique event ID; agency enters Corporate OIN + event ID per booking; "Minimum of 10 participants with a return flight"; "max. 9 passengers in 1 booking"; discounts "jusqu'à 15%"; valid "7 days before and after the event"; registration "up to 1 month before the event date" | https://www.klm.fr/information/business-travel/meetings-events · https://www.atout-france.fr/sites/default/files/2025-03/Air%20France-KLM%20Meeting%20%20Events%20presentation%20ORGANIZER_0.pdf · https://congres.bordeaux-tourisme.com/bons-plans/reductions-attractives-air-france-klm-global-meetings-events |
| S6 | Group-travel pain: traveller data arrives piecemeal (leader's spreadsheet, email replies, phone notes) and is re-keyed into airline name lists, rooming lists, manifests; "version chaos" with 3+ list versions per group; fix = collect once, generate lists from one record | https://www.gurutechnolabs.com/blog/group-traveller-data-collection · https://www.gurutechnolabs.com/blog/group-rooming-list-management |
| S7 | Boutique agencies (<50 groups) face "spreadsheet chaos, lost emails, manual tracking" | https://monday.com/blog/crm-and-sales/travel-agent-crm/ |
| S8 | Large congresses run group/third-party registration platforms: IDF 2025 group booking from 10 members with a group contact profile; EULAR group-registration platform for partners; Pharma Congress requires all group names at registration | https://idf2025.org/registration/ · https://congress.eular.org/congress-registration · https://www.pharmacongress.com/registration-onsite/ |
| S9 | HCP congress logistics specialists (PR Medical Events) sell "conference group registration process handling", delegate logistics and TOV reporting to pharma | https://pr-medicalevents.com/ |
| S10 | French PCO workflow: online registration form, "prise en charge" of invited HCPs, hotel page + booking form, rooming list; DMOS declarations of advantages (registration, hotel, transport, meals); MedTech code: no direct payment of HCP travel since 2018, educational grants via the society | https://www.perspectivesetorganisation.com/nos-metiers/ · https://www.bandyy.fr/organiser-congres-medical-2026-conformite-rgpd-hds/ · https://www.sforl.org/wp-content/uploads/2020/02/20SFORL_DESIGN_Dossiercommercial_V1.5.pdf |
| S11 | Transparence Santé / loi Bertrand / anti-gift: advantages ≥ €10 declared by the industry company; declaration/authorisation regimes; the declarant is the health-products company, not the agency | https://www.fimetfrance.fr/wa_files/guide_loi_bertrand.pdf · https://www.ethicalmedtech.eu/wp-content/uploads/2017/05/20190320_webinar_code_hco_france_final.pdf · https://www.cegedim-business-services.com/flux-sante/encadrement-des-avantages-transparence-anticorruption-ce-que-dit-la-reglementation-sur-les-interactions-avec-les-professionnels-et-organismes-de-sante/ |
| S12 | EFPIA e4ethics + MedTech Europe CVS: binding vetting of international congresses for member-company sponsorship; approved events carry an EMT reference | https://www.ethicalmedtech.eu/conference-vetting-system/ · https://www.efpia.eu/news-events/the-efpia-view/statements-press-releases/efpia-e4ethics-merge-with-the-medtech-europe-conference-vetting-system/ |
| S13 | TMC digital features 2025–26: FCM "Sam" AI assistant; Amex GBT/Egencia agentic AI, Claude connector (27 Jul 2026); BCD MCP on TripSource; Navan MCP layer; BCD "industry-leading sustainability and emissions reporting"; duty-of-care alerting standard | https://navan.com/blog/best-corporate-travel-agencies · https://travel-code.com/news/best-corporate-travel-management-companies-2026-tmcs-compared · https://rajeevgoswami.me/2026/09/07/every-major-tmc-ai-router/ |
| S14 | Havas Voyages Business Travel: "élaboration de bilans carbone", "définition de quotas carbone", "tableaux de bord dynamiques", Ecovadis Silver | https://business.havas-voyages.fr/ |
| S15 | Kuoni Tumlare Congress: "Sustainable Congress Services" aimed at medical societies with ESG/compliance objectives | https://congress.kuonitumlare.com/our-solutions/sustainable-congress-services |
| S16 | CSRD after Omnibus I (Feb 2026): direct duty only > 1,000 employees and €450 M; SMEs out of direct scope, but clients ask them for Scope 3 data; VSME voluntary standard; business travel = GHG Protocol Scope 3 cat. 6 / Bilan Carbone item 3.5; ADEME ×1.6 radiative-forcing factor for flights | https://www.clairegerardin.com/blog/csrd-pme-normes-esrs-2026/ · https://www.wecount.io/ressources-articles/vsme · https://ctabusinesstravel.com/blog/bilan-carbone-deplacements-scope-3 · https://blog.supertripper.com/rse/empreinte-carbone-deplacements-professionnels/ |
| S17 | "Information GES des prestations de transport": since 1 Oct 2013 anyone who markets or organises a passenger transport service must inform the beneficiary of the GHG quantity; the ministry/ADEME guide names travel agencies as covered; cascade principle to the intermediary facing the end customer | https://www.ecologie.gouv.fr/sites/default/files/publications/Guide_Information_CO2-2.pdf · https://www.enviroveille.com/public/fiches_pratiques/fiches-pratiques.html?cat_id=4&dossier_id=140699&fiche_id=998059 · https://www.franceinfo.fr/economie/transports/empreinte-carbone-l-affichage-obligatoire-pour-les-transports_1669377.html |
| S18 | ADEME Impact CO2 API: free, base `https://impactco2.fr/api/v1`, `/transport` by distance and mode (PLANE etc., `ignoreRadiativeForcing`), **API key required, requested by email to impactco2@ademe.fr**; data from Base Carbone; Swagger at /doc/api (page body not retrievable here) | https://www.data.gouv.fr/dataservices/api-impact-co2 · https://impactco2.fr/outils/transport · https://github.com/Jokod/impactco2-php · https://github.com/incubateur-ademe/monimpacttransport/blob/main/README.md |
| S19 | Open-source emission code: `dupontcyborg/flightyco2` (MIT, TypeScript port of Google's Travel Impact Model + DEFRA 2024 fallback, offline reference data); `jamiebull1/transport-carbon` (Python, pre-alpha, DEFRA 2013); `branliu0/flight-calculator` (no licence, last push 2020-05) | https://github.com/dupontcyborg/flightyco2 · https://github.com/jamiebull1/transport-carbon · https://github.com/branliu0/flight-calculator |
| S20 | ICS generation: `adamgibbons/ics` 788★, ISC licence, pushed 2026-10-01 (GitHub search API, 2026-11-05) | https://github.com/adamgibbons/ics |
| S21 | Airport coordinates for great-circle distance: OurAirports open data (public domain) via `davidmegginson/ourairports-data` (repo metadata call refused by this session's GitHub policy; licence to be confirmed at build time) | https://github.com/davidmegginson/ourairports-data |

Not verified (do not quote to the client): the klm.fr and airfrance.fr pages themselves (503); the Impact CO2 Swagger body; exact ADEME emission-factor values; GitHub star/licence metadata for S18/S19/S21 beyond what the search endpoint returned.

---

## 2. What the research says about the pain

1. **Data collection is the group-travel pain, and it is universal.** Names arrive by email, phone and a leader's spreadsheet, get re-keyed three times, and three list versions circulate (S6, S7). For ASSET this is exactly the congress use case: a lab, a society or a hospital service sends "about 12 doctors" to one congress; ASSET's offer starts at 10 people (live site, HANDOFF.md) and the GM&E fare needs 10 participants with return flights, bookable only in blocks of 9 (S5).
2. **Peers show nothing digital for this.** Agence Buzz, Beaux Regards, Medicom, Selectour's own PCO page and ASSET's live site are brochure sites with a contact form (S1, S2, S4). Only the big-congress platforms (IDF, EULAR) and pharma HCP specialists (PR Medical Events) have group registration flows (S8, S9).
3. **Carbon is where the big players differentiate** (BCD, Havas Voyages, Kuoni Tumlare: S13–S15), and the French legal floor is already there: an agency marketing a transport service owes the customer the GHG quantity (S17). Corporate clients of SMEs are asking for Scope 3 data even though SMEs are out of CSRD scope (S16).
4. **Pharma compliance is real but belongs to the lab, not the agency.** The declarant on Transparence Santé is the health-products company; the CVS/e4ethics vetting is an industry mechanism (S11, S12). Agence Buzz offers CNOM declarations as a service (S1), which shows demand, but a web agency building compliance tooling without a lawyer is a liability.
5. **AI assistants are the 2026 headline at Amex GBT/FCM/BCD/Navan** (S13), but for a 2-editor agency an AI chat is a cost centre and overlaps the RFP's own L4 option.

---

## 3. Candidates (8)

| # | Idea | Pain served | Sector signal | €0 to demo? | ≤ 1 day? |
|---|---|---|---|---|---|
| A | **Le lien de groupe**: per-enquiry shareable link, each delegate self-enters travel details, live manifest + GM&E threshold counter + CSV | S6, S7, S5 | S8, S9 | Yes (D1 + 2 pages on the existing custom demo) | Yes |
| B | **CO2e sur chaque devis et fiche congrès** from ADEME factors, offline | S16, S17 | S13–S15 | Yes (static factors, great-circle) | Yes (half day) |
| C | Hospitality ledger for Transparence Santé (per-delegate advantages ≥ €10, export) | S10, S11 | S9 (TOV reporting) | Yes | Yes, but legally exposed |
| D | Official-source watch: re-fetch the congress's official page, diff dates/venue, alert | last-minute date changes | overlaps RFP L4 | Yes | Yes |
| E | AI-drafted reply to each flight enquiry (Jev) | quote turnaround | S13 | Needs API spend | Yes |
| F | Live "dossier voyageur" page per congress group (programme, hotel, transfers, ICS) | on-site logistics | Selectour app, Smart app already do a "carnet de voyage" (S2, S4) | Yes | No (content-heavy) |
| G | GM&E eligibility hints in the back-office (dates inside ±7 days, ≥ 10 pax, ≥ 1 month lead) | missed fare windows | S5 | Yes | Yes (tiny) |
| H | Add-to-calendar + deadline reminders for congresses (ICS, S20) | small | common | Yes | Yes (tiny) |

Early cuts: **C** dropped (client perception: a web studio pretending to know the anti-gift regime; the lab is the declarant). **D** and **E** dropped (they are L4 by another name; E spends money and puts AI words in front of doctors). **F** dropped (competitors have it; a day is not enough). **G** and **H** are too small to be a moment on their own; G folds into A, H into B or A as a one-liner.

---

## 4. Debate log (Claim → Objection → Resolution)

### Winner: A, « Le lien de groupe »

1. **Correctness.** Claim: ASSET collects delegate data today by email. Objection: maybe the lab's CRO or the PCO collects it and sends ASSET a finished list. Resolution: **keep**; the RFP itself makes F03 a per-person flight enquiry and the live site sells groups from 10 people; even when a list arrives finished, the link replaces the "please send me your names as on the passport" round-trip, and the manifest is the same table ASSET needs for the 9-per-booking GM&E rule (S5). State it as a hypothesis in the email, not a fact about their process.
2. **GDPR / health sector.** Objection: a public link collecting travellers' personal data, some of whom are doctors on sponsored trips. Resolution: **amend**. Demo fields are name as on ID, email, departure city, outbound/return dates, one free-text line. No passport number, date of birth, dietary or health field. Token link, expiry date, single-purpose consent line pointing to the privacy notice, data lives with the enquiry in the EU database (Q27 commitment). Delegates are professionals, not patients: no HDS hosting question arises.
3. **Airline terms.** Objection: showing "GM&E" anywhere near the public could breach the RFP's code-protection rule or imply fares. Resolution: **amend**. The public delegate page never mentions GM&E or any fare. The counter ("8 / 10 pour un groupe") is back-office only, informational, and sourced to the public AF-KLM rule; no code, no price.
4. **Client perception: scope creep / "free work signals desperation".** Objection: an unrequested feature next to a low price reads as padding or as not understanding the brief. Resolution: **amend the framing**: it is one extra screen on S3/S4, shown last, after the five stories pass, introduced as "something the stories suggested"; not in the quotation; the operator decides whether it is a gift or an option line. One sentence in the email, not a paragraph.
5. **Competitor already does it.** Objection: Cvent, Swoogo, DigiFactory and big-congress platforms have group registration. Resolution: **keep**. Those are organiser-side tools priced for societies; none of ASSET's peers (S1–S4) offers it to an SME or a hospital service, and the point is to put it inside ASSET's own back-office.
6. **Operator time.** Objection: one day with five stories still to pass is not one day. Resolution: **amend scope to the minimum**: two tables, one public page, one admin tab, CSV export reused from S4, no email sending (notification log as in S3-F3). Build on the custom demo only; for the WordPress demo show the same screens as a static mock linked from /demo/. Estimate 6–8 h with AI help.
7. **Cost.** €0: Cloudflare Pages/Workers/D1 free tier already in use for the demo. Keep.
8. **Reversibility.** Feature flag per congress; dropping it is deleting two tables. Keep.
9. **Second round.** Objections 2 and 4 repeated in different words; stop.

### Runner-up: B, CO2e per route

1. Objection: the figure must be defensible. Resolution: factors from ADEME Base Empreinte with the methodology line and the ×1.6 radiative-forcing note shown; or the MIT `flightyco2` port with the DEFRA fallback (S19); the Impact CO2 API needs a key by email (S18), so the demo computes offline. Label every figure "estimation".
2. Objection: gimmick for a doctor booking one flight. Resolution: it is a legal information duty for the agency (S17) and what corporate clients ask SMEs for (S16); the "wow" is weaker than A for Veena's day, stronger for the manager pitching travel managers. Keep as runner-up; a single column in A's manifest ("CO2e estimé par délégué") can carry it later.

---

## 5. Why it makes them say "oh wow"

The moment: a lab assistant emails Veena "we are sending our 12 cardiologists to the congress in Vienna, can you quote the flights". Today Veena replies with a spreadsheet template, chases replies for two weeks, re-keys names, and finds out at the end that only 8 confirmed, below the 10-participant group threshold. With the link she pastes one URL into her reply; each doctor fills 60 seconds on their phone; her back-office tab shows "8 / 12 répondus, 8 / 10 pour un groupe", the departure-city mix (6 CDG, 2 LYS), and a "Télécharger pour cotation" button that gives her the exact table she sends to ticketing. Her manager sees one thing: ASSET's site is no longer a brochure, it is where the group gets organised.

---

## 6. Minimal demo spec (Fri 6 Nov 2026)

**Where it lives.** Option B custom demo (`custom_demo/`, Cloudflare Workers + D1), reached from the enquiry detail page in the back-office and listed on the hub page `/demo/` under "Et si… : le lien de groupe". For Option A (WordPress) a static two-screen mock in `site/demo/` with the same data, labelled "maquette".

**Fictional data.** Congress: « Congrès européen de cardiologie — exemple », Vienne, dates already in the seeded catalogue. Enquiry DV-2026-0007 from "Laboratoire Exemple SAS", contact "Mme Dupont (exemple)", 12 delegates expected. Seeded delegates: 8 fictional names (e.g. "Dr A. Martin", "Dr B. Leroy"), departure cities CDG×6, LYS×2, dates inside the congress window. No real doctors, labs, prices or codes.

**User journey (5 steps).**
1. Back-office › Demandes › DV-2026-0007 › bouton « Créer un lien de groupe » → link `/g/<token>` with an expiry date (default: congress start − 45 days) and a copy button.
2. Public page `/g/<token>` (mobile first): congress name and dates, 6 fields (nom comme sur la pièce d'identité, e-mail, ville de départ, aller, retour, remarque), consent checkbox, submit → confirmation "Merci, ASSET revient vers vous".
3. Back-office tab « Groupe » on the enquiry: live table of delegates, counters "répondus / attendus" and "seuil groupe : 8 / 10" (sourced hint, internal only), departure-city breakdown, status per row (reçu / à préciser / confirmé).
4. « Exporter pour cotation » → CSV (reuses S4 export), notification log row "manifeste mis à jour".
5. Hostile checks shown live: expired token → polite page; duplicate email → updates the row, no second row; HTML in a name → rendered as text; the token page never contains "GM&E" or a code (extend the S5 leak grep to `/g/*`).

**Real vs mocked.** Real: token creation, public form, D1 storage, counters, CSV, expiry, duplicate handling. Mocked: no email sent to delegates (notification log only), expected-delegate count typed by hand, threshold rule shown as text sourced to AF-KLM's public page (S5), no fare logic.

**Build estimate.** 6–8 h on the custom demo (2 D1 tables, 1 public route, 1 admin tab, 6 Playwright checks); 1–2 h for the static WordPress mock; 30 min to add it to `/demo/`. Total ≤ 1 day, €0.

**Gates before showing.** The five stories pass first (file 21). Then: leak grep on `/g/*`, 390 px pass, token expiry test, duplicate test, and the redteam pass on the email sentence.

---

## 7. The email sentence (operator chooses the frame)

Gift frame: « En préparant les histoires 3 et 4, nous avons ajouté un écran de plus, non demandé et non facturé : un lien de groupe par demande de congrès, que chaque participant remplit lui-même, et qui alimente directement votre manifeste et votre export de cotation ; c'est à voir en fin de démo, à garder ou non. »

Option frame: « Nous avons aussi prototypé, hors périmètre et hors devis, un lien de groupe par demande de congrès (chaque participant saisit ses données, votre équipe voit le manifeste se remplir) ; si cela vous est utile, nous le chiffrerons séparément. »

Guardrails: no number about ASSET's process ("vous perdez deux semaines") since we have no source for it; no "conforme GM&E"; no fare or discount figure; "manifeste" and "cotation" are their vocabulary from the RFP (F03, back-office export).

---

## 8. If the operator prefers the runner-up (B)

Half-day build: a `co2.ts` with ADEME-sourced factors per distance band, OurAirports coordinates for the 30 cities in the seeded catalogue, great-circle distance, output "≈ N kg CO2e par personne, aller-retour, méthode ADEME (forçage radiatif inclus)" on each congress page and in the enquiry acknowledgement; a "Export CO2 des demandes" CSV column in the back-office. Email sentence: « Chaque fiche congrès et chaque demande affichent une estimation CO2e du trajet, calculée hors ligne à partir des facteurs ADEME ; c'est l'information que la réglementation attend d'une agence de transport et que vos clients grands comptes demandent pour leur scope 3. » Both halves of that sentence carry a source (S17, S16).
