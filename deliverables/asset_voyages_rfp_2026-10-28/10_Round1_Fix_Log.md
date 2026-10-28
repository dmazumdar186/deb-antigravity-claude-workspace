# Audit round 1: fix log (2026-10-28)

Where the two audits differed, the more protective wording that is still plain was used. Defaults are identical in `site/questions/`, `01b_Questions_source.md` and `07_Question_Coverage_Matrix.md`. Still 30 questions; no new question (new topics folded into defaults or page sections).

## 08 — 11 lenses (29)

| # | Status | How |
|---|---|---|
| 1 | Done | Deadline Fri 6 Nov 2026 in email, §08 box, §09, pitch; late changes by email until contract signature, may alter price/dates |
| 2 | Done | Scope rule: email, `/questions/` §01 box, pitch « Ce que c'est », console banner, home footer |
| 3 | Done | Header « option »; toast « Version anglaise : option chiffrée séparément » |
| 4 | Done | Q1: start within 5 working days of signed order + access, 16 Nov earliest; launch ~12 weeks after start; late input shifts dates |
| 5 | Done | §03 "About €5–15 a month in provider fees"; §04 note: our maintenance plan separate, priced in proposal |
| 6 | Done | "At handover… once the delivered work is paid… under the exit terms in the contract" |
| 7 | Done | §05 "designed to… put back within minutes"; target, exclusions, monthly report |
| 8 | Done | Q30 and defaults list: "on our side; outages at the hosting providers are outside this target" |
| 9 | Done | Q27: database in the EU; US providers under data-processing agreements (neutral wording; transfer mechanism not asserted); list in proposal |
| 10 | Done | Q26 + §04 row: one-time code to work email (verified: Cloudflare Access One-time PIN doc) |
| 11 | Done | Q7 + new §04 row "Built into the site" (verified: Web Analytics FAQ says custom events "Not yet") |
| 12 | Done | Pitch « de nombreuses pages internes »; Q9 up to 20 pages, wording only, one round, legal wording by ASSET, no legal advice |
| 13 | Done | §07: two rounds of changes per design/content stage; matrix U107 |
| 14 | Done | Q17: ASSET provides spreadsheet in our template; no finding/cleaning |
| 15 | Done | Q28: management reads enquiries and gives final congress approval |
| 16 | Done | Q13: 24/7 wording as today; number only once confirmed in writing |
| 17 | Done | Q3: "directly, or through Veena on its behalf" |
| 18 | Done | Q29: optional plan, unused hours don't carry over |
| 19 | Done | Q27: "quoted separately" |
| 20 | Done | §03 "Also outside…" line |
| 21 | Done | J1 workshop up to 2 h by video; training two recorded video sessions |
| 22 | Done | Console: Nouvelle / Qualifiée (+ rappel flag) / Devis envoyé / Gagnée; defaults list adds reminder flag |
| 23 | Done | Pitch « routées vers l'adresse que vous choisissez pour chaque activité » |
| 24 | Done | Pitch « Dans la maquette : toutes les offres… » |
| 25 | Done | "in a monthly report"; backups row "any minute of the last 30 days" (database) |
| 26 | Done | Q6 "(web address only; your email is not touched)" |
| 27 | Done | Email "we've already put together a first look" |
| 28 | Done | Q30 "from us for the website" |
| 29 | Done | HANDOFF: WordPress 6.9.11 generator meta + wp-content paths (curl 28 Oct); count 30 |

## 09 — project experts (25)

| # | Status | How |
|---|---|---|
| 1 | Done | Same as 08 #1 |
| 2 | Done | Q3: silence after 3 working days = approved unless blocking problems listed; acceptance testing 5 working days vs T01–T15 only |
| 3 | Done | Q2 "as set out in our proposal, which lists the pages, listings, rounds of changes and exclusions" |
| 4 | Done | §02 goal 3 "Keep the value Google already gives you… (No supplier can guarantee rankings.)" |
| 5 | Done | Same as 08 #2 |
| 6 | Done | Q1 late-input clause (Q3 "later approvals" sentence removed) |
| 7 | Done, adapted | 08 #12 wording kept ("29" is unsourced, so not repeated); light editing defined; rounds in §07 |
| 8 | Done | Q17: one import, error rows returned, no research or rewriting |
| 9 | Done | Defaults list: redirect scope = our scan + Search Console last 12 months |
| 10 | Done | Q29 optional plan; §03 "maintenance is an optional monthly plan"; "once the delivered work is paid" |
| 11 | Done | Defaults list + J6: 4 weeks, defects vs accepted tests only |
| 12 | Done | Defaults list: WCAG 2.2 AA design target, report, no certification; lab speed tests |
| 13 | Done | §04 row + Q7 |
| 14 | Done | §05 "target, not a guarantee… any firm service commitment is set out in the maintenance contract" |
| 15 | Not done (superseded) | Authenticator app in Access is not documented; used 08 #10's email code, which official docs confirm |
| 16 | Done | Backups row: photos and documents copied daily; §05 "within minutes" |
| 17 | Done | UptimeRobot business-use added to the re-check sentence |
| 18 | Done | Q18 "holds the code, its evidence and its validity period for each congress" |
| 19 | Done | Q22 one group, one departure city, free text for the rest |
| 20 | Done | Q21 "Veena can add a link"; Q16 "export that opens in Excel" ("CSV" dropped as jargon) |
| 21 | Done | Pitch « Le film. … sa reprise éventuelle est chiffrée à part » |
| 22 | Done | Console CG-0107/0108/0109 « Publié »; one draft CG-0113 not in catalogue; tile « 1 congrès en brouillon, hors du site » |
| 23 | Done | Label « option » (« en option » rendered "EN EN OPTION" in caps, so shortened); tooltip text = same span |
| 24 | Done | Mailto button in §08 and §09 (subject « ASSET – réponses aux questions », per brief); 8 badges; `#q1`–`#q30` + `js/questions.js` re-align |
| 25 | Done | Contents row `position:static` below 600 px wide |

**Gates:** functional 56/56; site_check PASSED 4 pages × 4 contexts; screens re-shot and reviewed; redeployed. Not committed.
