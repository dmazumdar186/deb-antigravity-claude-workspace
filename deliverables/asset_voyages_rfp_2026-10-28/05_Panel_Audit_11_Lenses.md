# Panel audit, 11 lenses: ASSET Voyages RFP reply (2026-10-28)

Scope: the cover email `01_Questions_for_Veena.md` and the four pages in `site/`: `/`, `/pour-asset/`, `/console/` and `/questions/`. The live copies match the local files byte for byte; all four returned 200 on 2026-10-28. Checked against the RFP (`/tmp/rfp/brief.txt`), `HANDOFF.md` and `research/infra_costs_2026.md`. This is an audit only. Nothing has been fixed.

## 1. Karpathy: measurement
- Most cost figures match their source: translation 10,000 words × €0.10–0.15 = €1,000–1,500; CRM $7–20 ≈ €6–17; Brevo €7–9; Time Travel 30 days; Turnstile and UptimeRobot €0.
- **Two mismatches with the source:**
  - The Cloudflare paid plan is shown as ≈ €4.50. The source gives $5 ≈ €4.30.
  - The line "With paid alerts by text message, up to ≈ €30" is attributed wrongly. In the source, ~€30 is UptimeRobot Solo (~€10) plus AI (€1–5) on top of €5–15. Text-message credits cost about €3 for 10.
- The AI helper is shown at €5–20 a month. The research file says €1–5. The page does label it as its own estimate, but the two files disagree.
- Domain "≈ €10–32": the low end is $10.44 ≈ €9.
- The pitch table's screen counts (24 and 18 screens) do follow from the measured heights.

**Honest gaps:**
- Several figures were not re-fetched in this audit: the Gandi, Adobe Stock and HubSpot prices, and the Verisign +7%.
- The Access free limit and the Brevo paid price are UNVERIFIED in the source. The page says so.

## 2. Cherny: tooling craft
- **The screenshots are stale.** They were taken at 16:11, and `questions/index.html` was changed at 16:12. `questions-*.png` still shows "Our 20 questions" and "Timing and budget", while the live page says 25. The eye review therefore does not cover what is being sent.
- Links between pages are one-way. Only `/questions/` links to all four pages. `/`, `/pour-asset/` and `/console/` never link to `/questions/`.

**Honest gaps:**
- Nothing is committed (HANDOFF "Not done").
- The live phone check of `*.pages.dev` was never run.

## 3. Dario Amodei: honesty and legal exposure
- **The email says "All four pages are private: they aren't linked from anywhere."** That is false. The pages link to each other, and anyone who has a URL can open them. They are *unlisted* (noindex, robots), not private. `/questions/` §1 ("private") and its footer say the same thing.
- The RFP is marked "Confidential, restricted to invited suppliers". The RFP's own rule (§5) is that a test copy must be access-restricted. A public page that restates its contents does not meet that rule.
- **`/questions/` §5 says "an enquiry is never lost if one part is down".** That is an absolute promise. During a full Cloudflare outage (18 Nov 2025) the form cannot even load. The table row "so no enquiry is lost" has the same problem.
- `/pour-asset/` says "Les textes sont repris mot pour mot de votre site actuel". That is not true: every headline was newly written (HANDOFF, v2 "Not done"). Only the passages in quotation marks are verbatim.
- The concept uses ASSET's real logo, phone number and address, plus the Selectour logo. The footer does say "non officiel", and the forms send nothing.

**Honest gaps:** no lawyer has reviewed the reuse of the Selectour trademark.

## 4. Anthropic research: rigor
- **Milestone labels clash.** `/questions/` uses J0–J6. `/pour-asset/` uses "lots L0–L2, options L3 et L4" and "audit L0". Both systems come from the brief, but nothing on the pages explains how they relate.
- **Dead cross-reference.** `/pour-asset/` mentions "les questions de la section 8". That page has no section 8, and it does not link to `/questions/#s8`.
- "Database kept in the EU": the data is stored in the EU, but the computing can run anywhere (source §2). Question 22 covers this only in part.

**Honest gaps:** the 99.5% target leaves out the exclusions that the source wording includes (announced maintenance, third-party host failure).

## 5. Hormozi: offer
- The dream outcome is clear: more qualified enquiries, and Veena publishing without a developer. Risk reversal is strong: ASSET owns everything, can leave at any time, and today's site stays live.
- **No proof.** ASSET's email asked for examples, and the RFP §8 asks for "verifiable references" and a named lead. No page says when or how references will come.
- The fee is deferred, which follows the operator rule. Even so, an RFP reply without a price risks being ranked behind priced bids. Question 2 (budget) helps.

**Honest gaps:** there is no date for the proposal.

## 6. Saraev: automation boundaries
- Human approval is kept where customers feel it: the AI helper never publishes, tickets are never issued automatically, and nothing goes live without written approval.
- The backup path for forms is described. An off-platform backup copy is recommended in the source (§4.5) but missing from the cost table.

**Honest gaps:** this is all design on paper. Nothing has been built.

## 7. Daniela Amodei: trust
- **The ask conflicts with itself.** The email asks for written answers by email. `/pour-asset/` "Prochaines étapes" proposes a 30-minute call with Veena to go through the questions. That breaks the operator's "written answers by email" rule.
- The email says "we" throughout, from a solo founder. This is common practice, but Q3 and the RFP's "effort by role" will bring it up.

**Honest gaps:** no line covers what happens if ASSET picks someone else, for example that the URLs will be taken down.

## 8. Sutskever: failure modes
- The AI option is bounded: there is a person in the loop, a monthly cap and a review queue. The worst output is a wrong congress waiting in the review queue, which is acceptable.
- The worst failure in the *send* is the "never lost" and "private" wording being quoted back later.

**Honest gaps:** there is no eval for the congress finder, because it is not built.

## 9. Murati: phone experience
- The `/questions/` mobile layout is clean (stale iPhone shots). The cost table becomes cards, and the 25 questions are numbered cards.
- `/console/` is dense with jargon for a manager: "MFA obligatoire", "moindre privilège", "côté serveur… navigateur", "Workflow interne", "CSV".
- **The email misdescribes `/pour-asset/`.** It says the page shows "how it turns visitors into enquiries for each of your three activities", which the page does not really do. It also does not say the page is in French.
- `/pour-asset/` opens on the film, not on "why". Its table shows the concept as longer than today's site (24 screens against 6 on a computer).
- "voyage d'affaire" is still uncorrected in the statement block of `/`.
- The 25 questions contain about 36 question marks. Q6, Q12, Q14, Q19, Q22 and Q25 are compound questions. Q12 (CRM) overlaps the CRM option.

**Honest gaps:** no screenshot of `/questions/` §5–§7 or §9 on a phone.

## 10. Brockman: reliability
- The 99.5% target and instant rollback match the source. The outage citations are real (source §3).
- The "€0 for a small team" Access limit is unverified, and Access failed completely on 12 Jun 2025. The source asks for a break-glass login path, and the page does not mention it.

**Honest gaps:** no response times are given. The RFP asks for them, and Q25 defers them.

## 11. Hassabis: system
- The four pages form a sensible funnel: concept → why → console → understanding and questions. But three of the four are dead ends toward the page that actually asks for something (`/questions/`).
- The answers will feed the proposal, and the J0–J6 milestones carry through.

**Honest gaps:** nothing yet says how answers to the 25 questions turn into the priced proposal, or by when.

## Verdict: FIX FIRST
There are two blockers. Both are text edits: the "private" claim, and the call that contradicts the written-answers rule.

## Round 2 verification (2026-10-28, 16:45 UTC, independent re-check)

Method: file reads, greps on `site/` and the email, Playwright on a local static server (desktop 1440×900 and iPhone 13), axe-core (WCAG 2.2 AA) on all 4 pages, `site_check.mjs` re-run on 4 pages × 4 contexts after the console tab-row change, and curl on the live URLs. Live HTML, CSS and JS are byte-identical to `site/`.

| Lens item | Status | Evidence |
|---|---|---|
| 1. Cloudflare ≈ €4.50 | PASS | `/questions/` §4 now ≈ €4.30 |
| 1. "≈ €30 with SMS alerts" | PASS | now "With a paid monitoring plan (≈ €10): up to ≈ €25" (5–15 + 10) |
| 1. AI €5–20 vs research €1–5 | PASS | page states method ("about 200 pages read a month"); `research/infra_costs_2026.md` line 28 now €5–20 |
| 1. Domain low end | PASS | ≈ €9–32 |
| 2. Stale screenshots | PASS | `screens/` re-shot by this round's site_check (all 4 pages) |
| 2. One-way links | PASS | every page links to the other three (home footer, pitch top bar + footer note, console sidebar, questions top bar + footer); 0 broken internal links, 0 missing anchors |
| 3. "Private" claim | PASS | email, `/questions/` §1 and footer say "unlisted… anyone with the link can open it"; grep "private" only hits "private event codes" |
| 3. "Never lost" promise | PASS | now "designed so an enquiry is saved through a backup path" (§4 and §5) |
| 3. "mot pour mot" claim | PASS | now "Les passages entre guillemets sont repris mot pour mot… les titres sont des propositions" |
| 4. J0–J6 vs L0–L4 | PASS | no L codes left on any page; pitch uses "étape J1" |
| 4. Dead "section 8" | PASS | pitch links `../questions/#s8`; `id="s8"` exists |
| 5. No proof / references | PASS | §9: "Verifiable references and the name of the project lead come with the proposal" |
| 7. 30-minute call vs written answers | PASS | grep for call/échange/30 minutes/rendez-vous: 0 offers; step 1 is "Vos réponses écrites, par e-mail" |
| 9. Email misdescribes `/pour-asset/` | PASS | pitch now has the per-activity table (visitor → page → form → what ASSET receives); email says "(in French)" |
| 9. Console jargon | PASS | "Double authentification", "tableur"; GM&E note folded in a closed `<details>` |
| 9. "voyage d'affaire" | PASS | grep 0 hits; hero reads "voyages d'affaires" |
| 9. Compound questions | PASS (partly) | Q6/12/14/19/22/25 tightened; 32 "?" on the page vs 36; count still 25 everywhere (email, pitch, questions) |
| 9. No phone shots of §5–§7, §9 | PASS | shot on iPhone 13 this round; layout clean, no horizontal scroll |

Global checks: no ProdCraft fee (every € is a provider, translator, stock or CRM cost, labelled "paid to the providers, not to us"); 0 other-client names; 0 "px" in visible copy; no call offers; no analytics or tracking script (CSP `script-src 'self'`; only own JS files; "Cloudflare Web Analytics" appears only as a recommendation in a table); site_check PASSED, 104 ok / 0 FAIL; axe 0 violations on all 4 pages; 0 JS errors; live `/`, `/pour-asset/`, `/console/`, `/questions/` all 200.

**New defect (FAIL, minor, text):** `site/pour-asset/index.html` line 27, « il est invisible sur Google et lié d'aucun site public » is incorrect French. Fix: « il n'apparaît pas sur Google et n'est lié depuis aucun site public ».

**Still open, not on the fix list (accepted for this send):** RFP confidentiality vs an unlisted public URL; 99.5% exclusions; break-glass admin login; off-platform backup not costed; no proposal date; no "what happens to the URLs if not selected"; `research/infra_costs_2026.md` line 28 still says "about EUR 4.5" (internal only); home catalogue note still says "(CSV)".

**Round 2 verdict: FIX FIRST (one line of French, about 1 minute), then SEND.**
