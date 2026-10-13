# Briefing — the AlumnForce case, explained to its presenter

You contracted the work; this is the handover. It explains the problem, what was built and why, what was rejected and why, how the answer moves if an assumption moves, and the questions the panel (a CPO and a Lead Developer) can ask, with answers. Read it once end to end, then rehearse with SPEAKER_GUIDE.md.

---

## 1. The problem, as AlumnForce stated it

AlumnForce is a B2B2C SaaS: about 350 schools, universities and alumni associations each run their own isolated instance to manage their alumni community. Instances range from 400 to 80,000 members. Each is run by one to three administrators.

Their admin tool includes a **segmenter**: build an audience from about sixty criteria (class year, degree, location, employer, job function, dues status, event participation), then use it for a newsletter, an SMS campaign, a dues call or an export.

The observed problem: administrators can describe their target in one sentence, but translating it into filters is slow and reserved for experts. Many fall back to exporting to Excel.

Product leadership wants a **campaign targeting assistant**: the admin types "find me the graduates working in finance in London for more than three years" and gets a usable segment. Your mission: frame this product and propose the first increment to ship within one quarter, with one PM (you) and three to four developers who are shared with other projects.

Constraints they imposed:
- Multi-tenant: 350 isolated instances; features activate per instance or in bulk via feature flags.
- Stack: Symfony/PHP, Vue.js, MariaDB, OpenSearch, n8n; an internal AI gateway to an LLM provider, with provider and region an open choice.
- Personal data: clients are mostly European higher-education institutions. Any member data sent to a model must be justified, minimised and traceable. Some clients will refuse any transfer.
- Cost: every model call costs money; they must know what a use costs and which client generated it. Business model (included, option, pay-per-use) is open.
- The existing segmenter must keep working identically for instances where the feature is off.

Deliverable: 15 slides maximum answering five questions (problem reformulated; first increment with explicit exclusions; orchestration; measurement with a stop criterion; three risks) plus Annex A (how you used AI) and Annex B (SQL for the London finance query on the 500-member CSV, with assumptions and the count). One hour: 20 minutes you, 30 minutes their questions, 10 minutes yours.

## 2. The problem, as the material actually reveals it

The brief says "speed". The twelve verbatims and the data say "trust". This reframing is the spine of the whole deck.

**The verbatims, coded by underlying need** (my coding, one coder):
- Speed (3): Sophie spends an hour per list; Antoine wants ChatGPT; Yessica says the segmenter is abandoned six months after onboarding.
- Truth (3): Nathalie sent a "London expats" dues call to 340 people and twenty replied they had moved back years ago, two unsubscribed; Julie says people do not update profiles ("Analyst at Lehman Brothers"); Inès says nine list tickets in ten are a wrong profile, not a wrong filter.
- Proof (3): Karim needs "1,200 in finance, 180 in London, 40 percent paying" for his board; Isabelle needs placement numbers to defend her budget; Catherine needs each euro justified by time saved or dues collected.
- Data (2): Thomas needs a one-sentence answer to "where does my data go"; Philippe, a university CIO, says a US model gets a "no" from his DPO unless told precisely what leaves.
- Not for me (1): Marc runs a 400-member association and wants the Excel export columns in the right order.

Eight of twelve are about truth, proof or data. A pure natural-language-to-filters chatbot satisfies Antoine and makes the wrong list faster for everyone else.

**The data confirms it.** The CSV is announced as 500 members and holds 525 rows. Twenty-five rows (M0501 to M0525) are duplicate persons: surname in capitals or compound, truncated first name, gmail address, same job and start date. After deduplication, 500 members, which matches the brief. On those 500:
- London is spelled eight ways; the UK three ways plus 41 missing countries.
- Declared sector is missing on 174 members; 70 of 127 people at banks declare "Services", "Other" or nothing.
- Only 19 of 47 Master in Finance holders work in finance: the degree is not the sector.
- 68 percent of profiles untouched for two or more years; 77 percent no login in twelve months (89 percent if the 60 future-dated logins are treated as unknown).
- 60 last-login dates are in the future, up to October 2027: an export or integrity defect.

**The insight that makes the solution specific to this company:** profile updates cluster just after a job start (median 112 days, interquartile 50 to 165) and then stop. In this data, "in post for three or more years" and "profile untouched for three or more years" are the same signal. A naive assistant answering the brief's own example sentence returns exactly the people most likely to have moved. Nathalie's disaster is reproduced on their own file: the same sentence gives 2 members (naive filter), 26 (normalised), 49 (full logic), of whom only 6 are current or to-confirm, and only 1 strictly current.

## 3. What we built, decision by decision, and why

### 3.1 The product principle: a reliability split, not a chatbot
Every segment returns three counts: **Current** (profile updated within two years or login within one year), **To confirm** (updated two to four years ago), **To reactivate** (older, or no date). The admin acts on each: send, confirm, reactivate.

Why: the admin's problem is believing the list, not building it. A number with its reliability attached answers Nathalie, Julie, Inès (truth), Karim and Isabelle (proof), and gives Catherine a dues lever. No competitor we know of does this; it is the part that is hard to copy because it requires a normalised, reliability-scored base per tenant.

Why the words: "grade" and "stale" read as a verdict on the client's data stewardship; "to reactivate" is an action. Admin vocabulary never reaches members: they see "Profile last updated 4 years ago · Confirm / Correct".

### 3.2 Deterministic first, model second
Normalisation (city geocode, country, employer to sector), duplicate detection and the reliability status run in MariaDB and PHP with no model call. The model does exactly one thing: translate the admin's sentence into a structured filter set constrained to the segmenter's existing criteria.

Why: three reasons that each stand alone. The dirt is the product problem, so it must be fixed first or the assistant returns 2 or 49 people for the same sentence. Tenants who refuse any transfer (Philippe) still get the full deterministic layer. And a one-call translator with no member data in the prompt is evaluable, explainable and cheap.

### 3.3 Human in the existing segmenter
Generated filters pre-fill the existing segmenter UI next to the admin's own sentence (a diff view). The unmapped part is shown inline ("Add this criterion by hand"), never a blank page. The admin edits, saves, sends or reactivates. The model never sends, merges or edits anything.

Why: the segmenter already exists and is known; replacing it would widen scope and break the "identical when flag off" constraint. A visible filter set is the bound on the model's worst output: a valid but wrong filter set is caught by a human reading the filters and the count before any send.

### 3.4 Scope: four deliverables, a 36 dev-week core, a pre-named cut
- D1 Reliability layer (16 dev-weeks): status column computed nightly, OpenSearch field and per-tenant reindex, two new segmenter criteria (last profile update, last login), a relative-date operator in the engine, reference tables with per-tenant overrides written to separate normalised columns, idempotent chunked backfill, status shown on the member's own profile.
- D2 Sentence to filters (11): gateway integration, filter contract, validator, prompt cache, Vue pre-fill.
- D3a Actions (2, core): send to current plus to-confirm; "Reactivate N members" opens the existing Profile Update Campaign module pre-filled.
- D3b Hygiene (3, stretch): duplicate detection report, stable export column order.
- D4 Flags, metering, evals (7): two flags, per-call log, kill switch, record/replay eval harness plus nightly live replay, campaign outcomes stored by segment and status, per-tenant config table.

Why D1 is the heaviest and first: the two reliability criteria do not exist in the engine today (verified on the demo instance), so this is an engine change plus a reindex, not a UI tweak. Why D3a is in the core: the reactivation loop is the only priced lever and the subject of the week-17 decision; it cannot live in the stretch cut. Why 3 effective FTE: developers are shared; the plan states the assumption and names what drops below it (D3b, then live Vue pre-fill replaced by a saved-list import).

### 3.5 Two flags, both off by default
`reliability` (status, criteria, counts) and `nl_targeting` (the sentence box). Why: the brief requires the segmenter to be identical where the feature is off, and the status is derived personal data that each tenant must decide on before it is computed for them. Tenants that refuse AI can still turn on reliability.

### 3.6 Orchestration and data protection
Only the admin's sentence, scrubbed of e-mails, phones and exact full-name matches from the tenant's member table, plus the tenant's criteria names and operators and closed taxonomies (sector list, country list, diploma types) go to the model. Never a member row, never an employer list. Placeholders replace other capitalised two-token sequences and are re-substituted locally so "those who work at Goldman Sachs" still maps. The validator strips criteria outside the admin's role (unit-tested), geocodes place text with the segmenter's existing geocoder, resolves relative durations, applies sanity bounds (radius cap, type table, result-count versus tenant-size alert), retries once on invalid JSON, then falls back to "cannot map". Cache key includes tenant, taxonomy hash, schema hash, prompt version, model id and role.

The DPO sentence: "Only the administrator's question, scrubbed of identifiers and full names, and the names of the filters leave the platform, to a model hosted in the EU under a no-retention, no-training contract. No member profile is ever sent; residual hits in the question are logged and reviewed."

The legal file: tenant is controller, AlumnForce processor, provider a sub-processor listed with 30-day notice; DPIA screening memo and balancing-test template supplied by AlumnForce, decision recorded by each tenant; reliability status treated as derived personal data, visible and contestable by the member (contest answered within 10 business days and freezes the status as confirmed for 12 months); logs pseudonymised, 12-month retention, tenant-scoped export; one reactivation per member per quarter; suppression after a "not me" reply or opt-out. Annex C holds the security-questionnaire rows.

### 3.7 Cost and business model
One request is roughly 1,500 to 2,500 input tokens (schema and taxonomies in a cached prefix) and 150 to 300 output tokens: a fraction of a euro cent on a mid-tier model, under a euro a month for a heavy tenant. The cost that matters is engineering (36 to 39 dev-weeks). Position: reliability layer included for all (retention tool at renewal); sentence box included with fair use (300 requests a month, soft block and CS alert); the reactivation loop is the only priced add-on, tested on the three expert tenants as a flat monthly fee per member tier, reverting to included if reactivation stays under 10 percent. Primary lever is retention across 350 installed tenants; "do you do AI?" is the new-logo answer; reactivation is the only upsell because it is the only thing tied to dues.

### 3.8 Measurement and the stop criteria
Offline: 100 labelled sentences from tickets and verbatims, two annotators, Cohen's kappa at least 0.8, plus 30 negative sentences that must return "cannot map" (impossible, discriminatory, injection, widening attacks). Gate: canonicalised exact match at least 85 percent with its roughly plus or minus 7 point interval stated, negative-set recall at least 95 percent. Replayed nightly against the live endpoint with an alert on a 5-point drop, because providers update silently. Online: edit rate per segment, rejection rate and cannot-map share per sentence, all aggregate and pseudonymised, disclosed to admins at flag-on. Value: time to list, "not me" replies, share of current profiles, dues response of current plus to-confirm sends versus historical.

Two stop criteria, two dates. Week 12, sentence box: stop if under 30 percent of new segments on the seven non-expert pilot tenants use it, or edit rate stays above 50 percent, or the eval gate fails; keep the reliability layer. Week 17, reactivation loop: stop if under 10 percent of to-reactivate profiles move to current within 30 days of the first campaign; keep the status and criteria. Expert tenants reported separately so three power users cannot carry the number. Every threshold is labelled an initial guess reset on the week-4 baseline.

### 3.9 Three risks and positions
1. The data is too dirty for any assistant to look good. Position: the reliability layer is the increment; the split makes the dirt visible and reactivation starts cleaning it; accept shipping the sentence box later than a pure-AI roadmap.
2. Personal data and the DPO veto. Position: design so the answer is short and true; no member data in prompts, EU endpoint, status visible and contestable; refusing tenants get everything but the sentence box; never trade this for a richer prompt.
3. Expectation gap: Antoine expects ChatGPT. Position: never call it a chat, always show the filters and the unmapped part, make the first win the split, end every demo on "6 you can safely e-mail", onboard the three expert tenants first.

### 3.10 Timeline
Weeks 1 to 2: baselines, golden set, thresholds validated by CS hand-grading 100 members on two tenants (must agree at least 80 percent), DPIA screening memo, gateway region and FTE confirmed. Weeks 3 to 7: D1 and D4. Weeks 6 to 9: D2 and D3a, eval gate before week 10. Weeks 8 to 12: two-step pilot on ten tenants (reliability from week 8, sentence box from week 10): three expert, five mid, two small, one refusing transfer, including three top-decile ARR accounts and every renewal at risk in the next nine months. Week 12 go or no-go on leading indicators; week 17 reactivation outcome. Then waves of about 50 tenants a month, backfill plus flag only, at-risk renewals first.

## 4. Alternatives considered and why they were rejected

| Alternative | Why rejected |
|---|---|
| Free-text multi-turn chat over the member base (what Antoine asked for) | Needs member data in the prompt (DPO veto); output not evaluable against a golden set; sets an expectation three developers cannot meet; no reliability information. |
| Retrieval or semantic search over profiles in OpenSearch | Embedding eight spellings of London embeds the noise; only useful after normalisation; moves member text toward a model. Q2 at earliest. |
| Sentence box first, data quality later | Returns 2 or 49 people for the same sentence; brand damage lands on AlumnForce; abandons the eight verbatims about trust. |
| Automatic profile correction | Silent edits destroy the trust being built; the platform asks, the member confirms. |
| Enrichment from LinkedIn or company registries | Legal basis unclear for most tenants; per-profile cost; not needed to prove the increment. |
| Duplicate merge UI in Q1 | Multi-module, irreversible; needs candidate table, reviewer, undo window; detection report carries the pilot. |
| "Three questions for the board" analytics first (Isabelle's ask) | Highest value, but on dirty data it yields confident wrong numbers; it is the Q2 headline on the reliability-scored base. |
| Role-pruned schema sent to the model | Breaks the shared cached prefix per tenant; stripping by role in a unit-tested validator is more reliable than asking a model to respect permissions. |
| Blocking the request when the scrub finds a name | Surnames like Paris, Martin, Finance would block constantly; log, placeholder and show to the admin instead. |
| LangChain or an orchestration framework | One call with a JSON schema and a deterministic validator is a function, not a graph; a dependency in a PHP shop for no gain; reconsider if calls are chained in Q2. |
| Fine-tuning or self-hosting a model | No evidence it is needed; prompt plus schema plus evals suffices and keeps the provider swappable. |
| Pricing the sentence box | Catherine will not pay for a text box; kills adoption before value is measured. |
| Making the reactivation loop free forever | It is the only lever tied to dues; test a price on three expert tenants, revert if uplift is not measurable. |
| One stop criterion at week 12 for everything | The reactivation outcome needs 30 days after a campaign that cannot start before week 10; two dates match the two speeds. |
| Deleting stale profiles instead of reactivating | Accuracy principle favours asking the person; retention and deletion remain the tenant's policy; the status makes deletion candidates visible for the first time. |

## 5. Sensitivities: if one thing changes, what moves

- **Developers are 2.5 FTE, not 3.** D3b drops; live Vue pre-fill becomes a saved-list import; reliability criteria and metering never move. If the engine has no criterion-type extension point and the relative-date operator costs six weeks, that operator drops first (saved segments carry an "as of" date and re-resolve on open), then the Vue pre-fill.
- **The gateway points to a US provider today.** The sentence box launches only once an EU-hosted endpoint is behind the gateway, with the legal entity and transfer mechanism named. The reliability layer does not wait.
- **A tenant refuses all transfer.** It keeps the reliability layer, the duplicate report and the score; loses only the sentence box. The pilot deliberately includes one such tenant.
- **Hand-grading in weeks 1 to 2 disagrees with the 2-year / 4-year thresholds.** Thresholds move before the nightly job ships; the rule is a config value per tenant, not code.
- **Exact match stays below 85 percent.** The box does not go to pilot tenants; prompt and schema iterate on record/replay fixtures; if the ceiling is structural, the candidate pre-fills only the mapped criteria and marks the rest.
- **Edit rate is above 50 percent at week 12.** Sentence box stops; the quarter still delivered the reliability layer, which pays back in tickets and renewals.
- **Reactivation moves under 10 percent at week 17.** The priced add-on idea is dropped; status and criteria stay because they cost nothing to run.
- **A provider silently updates its model.** Nightly replay catches a 5-point drop; release blocked; provider version logged per call; prompt and model id pinned.
- **The brief's "sixty criteria" are really 45.** The schema is smaller, prompts are cheaper, and the "cannot map" path matters more; nothing else changes.
- **An 80,000-member reindex takes longer than a night.** Alias-swap reindex with canary tenants; waves slow down; nothing is user-visible because the alias flips only when the new index is verified.
- **Admins type names in the sentence.** Scrubbed if an exact full-name match exists; otherwise placeholder, logged, shown back. Residual risk is stated in the DPO sentence, not hidden.

## 6. The panel's questions, with answers

### Generic
- *Why this and not the chatbot we asked for?* See 3.1 and the first row of section 4. Say it in one breath: not evaluable, needs member data, sets an expectation we cannot meet, gives no reliability.
- *What is the one thing you would protect if everything else slipped?* The two reliability criteria and the metering. Everything else is a layer on top.
- *What did you learn from the data that changed your plan?* The 525 rows, and that tenure and staleness are the same signal in this file. The plan became data-first because of it.
- *How did you use AI?* Annex A, truthfully: drafting, data runs, a browser session on the demo, eleven review lenses. What you verify yourself is listed, and you must actually do it (checklist in SPEAKER_GUIDE.md).

### Specific
- *Walk me through the 2, 26, 49, 6.* City value "Londres" and sector "Finance" with the 3-year clause on the file as delivered: 2 (3 without tenure). Normalise the eight London spellings and three sector labels, no dedup: 26. Dedup to 500, three finance sources, country gate, tenure: 49. Of those, 1 current, 5 to confirm, 43 to reactivate: 6 worth e-mailing.
- *Why same start date in the dedup rule?* A looser "or same job" rule merged Raphaël Martin into Raphaël Martinez and dropped 26, not 25. The start date is the discriminating field in this file. In production the rule becomes a scored candidate list with blocking keys, reviewed by the admin.
- *Why 2 years and 4 years?* Initial guesses anchored on the 112-day median update lag; validated by CS hand-grading 100 members on two tenants before the nightly job ships; per-tenant config, not code.
- *What exactly leaves the platform?* The scrubbed sentence, criteria names and operators, closed taxonomy values. Not members, not employer lists. Tenant-defined labels go as typed ids unless the tenant opts in.
- *How do you know the model is not getting worse?* Nightly replay of the 130 fixtures against the live endpoint, alert on a 5-point drop, provider version per call, record/replay in CI.
- *Where does the status live technically?* Nightly batch into a MariaDB column and an OpenSearch field, per-tenant alias-swap reindex, exposed as two criteria in the existing engine.

### Why this decision and not another
- *Why send the full tenant schema and strip by role afterwards?* Names only, no data, so the cached prefix is shared per tenant; deterministic stripping beats asking the model to respect permissions.
- *Why two flags?* The brief demands an identical segmenter when off, and the status is derived personal data that each controller decides on separately from the AI question.
- *Why include the sentence box in the subscription?* Catherine will not pay for AI; she pays for dues. Pricing a text box kills adoption before value is measured. The only thing priced is the thing tied to dues.
- *Why reuse the Profile Update Campaign module?* It exists (seen on the demo), it is tenant-editable, and it keeps model-written copy out of member-facing mail.
- *Why two decision dates?* The reactivation outcome needs 30 days after a campaign that cannot start before week 10.

### Alternatives and why not
Use section 4. If pressed on LangChain: it is a dependency in a PHP shop for one function call; keep the disciplines (typed schemas, tracing, evals in CI), not the framework. If pressed on RAG: embed normalised data, not noise, and that is a Q2 conversation with its own DPO question.

### What-ifs
Use section 5. The two they will most likely raise: shared developers (answer: 3 effective FTE assumed, confirmed week 1, pre-named cut) and a US provider today (answer: reliability layer does not wait; sentence box waits for an EU endpoint).

### Decision points
- *Why is the duplicate report stretch but reactivation core?* Reactivation is the priced lever and the week-17 criterion; the report is a renewal nicety.
- *Why no euro figure anywhere?* You have not seen their cost base. Payback is formulas with baselines measured in weeks 1 to 4; breakeven you would accept: engineering recovered within four quarters from ticket savings and retained ARR across pilot and first 50-tenant wave, before any upsell.
- *Why hedge the competitor claim?* Because it is unverified. "To my knowledge none scores a segment's reliability; I will verify in week 1" is the honest form.

### Questions deliberately outside the deliverable (they said some will be)
- *How would you run discovery with tenants you have never met?* Ten tenants, weekly 30-minute call, a pilot agreement, ticket data tagged from week 1.
- *What would you do in your first week?* Instrument the segmenter, get ticket data, build the golden set with CS, decide thresholds with three expert tenants, confirm gateway region, FTE and the engine's extension point.
- *Did you e-mail us a question during the week?* Answer truthfully. If not, name the question you would have asked: which tenants have refused AI and why, and whether the gateway runs in the EU today.
- *What would make you turn this down?* A gateway that cannot be moved to the EU and a leadership that wants the chatbot anyway.

## 7. Weak points to own, not hide

- Dev-weeks, token costs, backfill timing and the demo counts are one person's estimates from one session; the Lead Developer's numbers win.
- Competitor claims are hedged, not verified.
- The thresholds are lopsided on this synthetic file (43 of 49 to reactivate); hand-grading is the test.
- The eval set is a gate, not a drift detector on its own; the nightly replay covers drift but 130 items have about plus or minus 7 points of noise.
- Annex A commits you to five verifications; do them before sending or the annex is false.
- The demo exploration was an automated browser session under your account that created and deleted one empty list; disclose if asked and change the password.

## 8. The 20 minutes, in one paragraph

Open with the data line (2, 26, 49, 6), then the thesis: they asked for speed, their users asked for trust, so the platform returns how far to trust the list. Show the segmenter as it is and what it cannot see. Show the verbatims coded and the data table. State the principle and the demo ending on "6 you can safely e-mail". Size the quarter, name the cut, list the exclusions with reasons. Walk the orchestration diagram and say the DPO sentence slowly. Measurement with two dates, three risks with positions. Execution, money, 2027 in three minutes. Close with the decision ask and the two sentences on slide 15.
