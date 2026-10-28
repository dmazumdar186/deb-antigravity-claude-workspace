# Audit round 2: fix log (2026-10-28)

Operator decisions applied as given (no client names, genuine two-step login, deemed approval for design/content only, "signed proposal", one rounds rule, plan-bound support, mailto format, Précisions box, T09 default, instant #q jumps). Still 30 questions, no new question. Defaults identical across `site/questions/`, `01b_Questions_source.md` and `07_Question_Coverage_Matrix.md` (synced programmatically from the page).

## 11 — 11 lenses (21)

| # | Status | How |
|---|---|---|
| 1 | Done | §04 row + Q26: work email account (Microsoft 365 / Google Workspace, own two-step check on) or email one-time code + authenticator app or security key. Verified 28 Oct: Cloudflare Access "Independent MFA" doc (TOTP app, security keys, biometrics; enrolment after IdP or OTP login); MFA-from-IdP doc lists Entra ID, not Google, so Google is worded as "its own two-step check switched on". Source link "second login step" added in §04 |
| 2 | Done | Pitch steps: 1 answers, 2 proposal (sent separately), 3 « Après signature de la proposition, l’audit… (J1) » |
| 3 | Done | Q30 "With the optional maintenance plan…"; defaults backups line "With the maintenance plan, we aim…"; §05 report "With the optional maintenance plan"; J6 "After these 4 weeks, support and fixes are covered by the optional maintenance plan or quoted per request"; Q30 adds the same after J6 |
| 4 | Done | §02 goal 3: addresses from our scan and Search Console mapped to closest new page |
| 5 | Done | Q3: silence = approved for design and content stages only; "Launch always needs management’s written go-ahead (section 07)" |
| 6 | Done | Q9 "ASSET writes the French text for new pages"; J3 "French texts for new pages" |
| 7 | Done | One rule in §07: two rounds per design stage and two per content stage (page wording included, see Q9); Q9 refers to it; matrix U107 |
| 8 | Done | §01 "The proposal, once signed, is our contract."; "signed proposal" in email, §01, §03 exit terms, §05, §08, Q1; 01b + 07 mirrored |
| 9 | Done | Q1: signed proposal; access due at kickoff |
| 10 | Done | Defaults list: Search Console "if you give access (question 7)"; U112 |
| 11 | Done | §09 "(by Friday 6 November 2026)"; pitch « avant le vendredi 6 novembre 2026 » |
| 12 | Done | §09 cost split per brief incl. audit, each option, running and maintenance, three-year core total, excl./incl. VAT; pitch step 2 likewise |
| 13 | Done | Pitch « envoi à l’adresse choisie pour chaque activité » |
| 14 | Done | §06 "Statistics without cookies." |
| 15 | Done | §03 "your site, code, data and accounts go with you, under the exit terms" |
| 16 | Done | Q22 "one departure city or airport of the traveller’s choice" |
| 17 | Done (operator wording) | §09 "Examples of our work come with the proposal, described without naming our clients; we can put you in touch with a client only with that client’s permission." "Verifiable references" removed |
| 18 | Done | §05 split: short lead + "What this means" bullet box (target, report with plan, exclusions/firm terms, nobody promises 100%) |
| 19 | Done | Pitch « Points relevés, à confirmer avec vous » |
| 20 | Done | §03 "If the audit changes the approach, the change is agreed in writing with its effect on price and dates." |
| 21 | Done | `git mv` to `01b_Questions_source.md`; references fixed in 10, 11, 07 and `.tmp/asset_cov/gen_md.py` |

## 12 — project experts (13)

| # | Status | How |
|---|---|---|
| 1 | Done | Q9 "corrections made within the two rounds of changes of the content stage (section 07)" (same as 11 #7) |
| 2 | Done | Email: "(the questions start here: …/questions/#s8)"; hero link "Go straight to the 30 questions ↓" |
| 3 | Done | Pitch « …dans le périmètre fixé par la proposition signée (rôles : voir la question 28) »; console Rôles note « Exemple de répartition ; les rôles retenus sont fixés à la question 28. » |
| 4 | Done | Quote dialog: « Précisions (autres villes de départ, hôtel, transferts) » textarea; toast notes « précisions notées » when filled. Voyageurs default kept at 1 (optional item; prefill tests rely on it) |
| 5 | Done | Defaults list: cookie banner default (T09); matrix U114 |
| 6 | Done | Both mailtos: subject « ASSET – réponses aux questions », body first line "Write OK to accept our assumption, or your answer." then "1. Dates — " … "30. Support hours — " (1,267 chars); §08 intro "Write OK to accept our assumption as it is, or your answer."; email mentions it |
| 7 | Done | Same as 11 #12 |
| 8 | Done | Q3 "To keep the dates on track…"; Q5 "If an account is held by someone else, ASSET asks them to transfer it; we can tell you exactly what to ask for."; §08 box "After signature, changes are agreed in writing with their effect on price and dates." (box now a "What this means" bullet list) |
| 9 | Done | « Double authentification obligatoire » added to Éditrice and Approbateur cards; Rôles note « Connexion en deux étapes pour tous les comptes » |
| 10 | Done | Defaults list + §04 row: database to any minute of last 30 days; photos and documents to the previous day |
| 11 | Done | Same as 11 #3 |
| 12 | Done | `questions.css` <600 wide: `.qs li{display:block}`, number inline before the badge |
| 13 | Done | `questions.js`: #q jumps instant (scroll-behavior auto during jump, click + hashchange handlers); CSS `html:has(.qs li:target){scroll-behavior:auto}`. Test: #q18 fresh load lands at 96 after 250 ms |

**Gates:** functional 61/61 (5 new r2 tests; r1 expectations updated: mailto format, signed-proposal rule, two-step wording, "authenticator app" no longer banned); site_check PASSED 4 pages × 4 contexts; `screens/r2-{desk,iph}-*.png` (20) shot and reviewed (one fix: double colon in pitch step 3); redeployed, CSS hash match, 4 live URLs 200, live /questions/ contains "Go straight to the 30 questions". Not committed.
