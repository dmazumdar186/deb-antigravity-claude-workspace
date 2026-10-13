# Speaker guide — AlumnForce case, 20-minute presentation + 30-minute Q&A

Deck: 15 slides + Annex A (AI usage), Annex B (selection logic), Annex C (technical and compliance sheet). Feature name in the deck: **Trusted Segments**; the natural-language input is "the sentence box"; reliability words: **Current / To confirm / To reactivate**. Never say "chat", "grade" or "stale" in the room.

Audience: the CPO and a Lead Developer. Frédéric (founder) framed the role as senior AI PM who can clean the database, run AI evals, and think about LangChain-style orchestration. Bootstrap phase: every slide should sound like it costs little and proves something.

## Timing (20 minutes)

| Min | Slides | What to say |
|---|---|---|
| 0–2 | 1 | Open with the data line: "Same sentence on your file: 2, 26 or 49 people, and 6 you can safely email." Then the thesis: you asked for speed, your users asked for trust, so the platform returns how far to trust the list. |
| 2–4 | 2–3 | How you read the material. The 8-of-12 verbatims point. |
| 4–7 | 4 | The data slide. Land the 525-vs-500 and the "tenure = staleness" insight. Then the 2 / 26 / 49 / 6 line. This is the memorable moment. |
| 7–11 | 5–7 | The increment, sized in dev-weeks with a 36 dev-week core and a pre-named cut, then the exclusions. The panel grades the "no". |
| 11–14 | 8–9 | Orchestration diagram. Say the DPO sentence out loud, slowly. |
| 14–17 | 10–11 | One stop criterion per layer, two dates (week 12, week 17), then the three risks. |
| 17–19 | 12–13 | Execution (two-step pilot, waves) and money (levers, payback formulas, packaging hypothesis), quickly. |
| 19–20 | 14–15 | Decision ask, then the two closing sentences: the thesis and the DPO sentence. |

Rehearse 17 minutes; you will run over.

## The five lines to memorise

1. "The administrator's problem is not building the list, it is believing it."
2. "In this file, three years in post and three years without a profile update are the same signal: the people you want are the ones to reactivate first."
3. "Same sentence: 2, 26 or 49 people, and 6 you can safely email."
4. "Only the administrator's question and the list of filter names leave the platform. Never a member."
5. "If under 30 percent of segments use it after three pilot weeks, or admins rewrite more than half of what it produces, I stop the sentence box at week 12 and keep the reliability layer."

## Likely questions and answers

**"Why not just a chatbot like Antoine asked?"**
Three reasons: it needs member data in the prompt (DPO veto), its output cannot be evaluated against a golden set, and it sets an expectation we cannot meet with 3 developers. A translator with a fixed vocabulary is evaluable and explainable.

**"What about LangChain / LangGraph? Would you use it?"**
For this increment, no. One model call with a JSON schema and a deterministic validator is a function, not a graph. A framework adds a dependency in a PHP shop for no gain. I would reconsider in Q2 if we chain calls (question to aggregate query to narrative), and even then I would prefer a thin internal orchestrator behind the gateway so the provider stays swappable. What I keep from the LangChain world is the discipline: typed tool schemas, tracing of every call, evals in CI.

**"How do you run evals concretely?"**
A golden set of 60 to 100 sentences with expected filter JSON, written by two people independently so the labels are not one person's bias. Metric at the filter level: precision and recall per criterion, plus exact-match rate. Also a negative set of sentences that must return "cannot map" (discriminatory or impossible requests). Run in CI on every prompt, schema or model change; results versioned next to the prompt. Online: edit rate and rejection rate, plus a weekly manual sample of 20.

**"Which model and provider?"**
Open, and I keep it open: the contract is schema in, JSON out, so any EU-hosted mid-tier model works. I would start with the cheapest model that passes the 85 percent eval gate. Region in the EU is non-negotiable for the DPO answer.

**"Why is the cost so low? Are you sure?"**
The prompt is the sentence plus a schema and value lists, roughly two thousand tokens with a cacheable prefix. I give an order of magnitude and confirm it on the gateway in week one. The expensive part is engineering, which is why the metering exists from day one.

**"How do you handle permissions?"**
The assistant runs in the admin's session. The model receives the tenant's criteria names and operators, never data, so the cached prefix is shared per tenant; the validator then strips any criterion the role may not use, unit-tested; the query runs through the existing segmenter engine, which already scopes to the instance. What is new to secure is the gateway credential and the per-call log, both covered in Annex C.

**"What if the model hallucinates a criterion?"**
The validator rejects any criterion not in the schema and any value not in the reference tables. The admin sees the unmapped part as text. The model cannot invent a filter that reaches the database.

**"Isn't data cleaning a different project?"**
It is the same project. Without normalisation the assistant returns 2 or 49 people for the same sentence. The current / to confirm / to reactivate split turns dirt into something the admin can act on. And the deterministic layer ships to tenants who refuse AI entirely, so it is also the commercial hedge.

**"How would you dedupe in production?"**
Blocking keys first (name prefix plus class year), then a scored candidate list inside each block (name similarity, same start date, same employer), proposed to the admin with the score. Never auto-merge. Annex B's one-off rule requires the same start date because a looser "or same job" variant merged Martin into Martinez. Tune thresholds on the pilot tenants' confirmed and rejected merges.

**"What about OpenSearch and semantic search?"**
Q2 at the earliest, after normalisation. Embedding eight spellings of London just embeds the noise. And it moves member text toward a model, which needs its own DPO conversation.

**"Pricing?"**
Included with a fair-use quota, metered beyond. Catherine will not pay for AI, she pays for dues. If the nudge loop lifts dues measurably, that loop can be priced.

**"What would you do in week one?"**
Instrument the current segmenter for baselines, get the ticket data, build the golden set with CS, decide freshness thresholds with the three expert tenants, confirm gateway region and per-call logging.

**"You are the only PM with shared developers. What slips?"**
Deliverable 2 (the sentence box). Deliverable 1 ships regardless because it has value alone.

## Questions added after the six-lens review (be ready)

**"Your capacity math: our developers are shared."**
I plan on three effective FTE, 36 dev-weeks, and confirm it in week 1. The core is 36: reliability layer, sentence box, the two actions, flags and metering. Deliverable 3b (duplicate report, export order) is the stretch. Below three FTE, the box pre-fills through a saved-list import instead of live Vue state. The reliability criteria and metering never move.

**"Your pilot is three weeks and your stop criterion says eight."**
Two layers, two speeds. Week 12 decides the sentence box on leading indicators: eval gate, adoption and edit rate over three weeks. Week 17 decides the reactivation loop, thirty days after the first campaign. The quarter still ends with a decision.

**"You send the full criteria schema to the model and strip by role afterwards. Why?"**
Because the schema is criteria names, not data, and sharing it per tenant keeps the cached prefix cheap. Role stripping is deterministic and unit-tested, which is more reliable than asking the model to respect permissions.

**"The gateway points to a US provider today."**
Then the sentence box launches only once an EU-hosted endpoint is behind the gateway, with the provider's legal entity and transfer mechanism named. The reliability layer does not wait for that.

**"GDPR says stale data should be deleted, you say reactivate."**
Reactivation is the accuracy principle in action: we ask the person to confirm or correct. Retention and deletion stay the tenant's policy, and the status makes the candidates for deletion visible for the first time.

**"Can the Vue segmenter be pre-filled, or is that a rewrite?"**
To confirm in week 1 with the Lead Developer. If live state pre-fill is expensive, the fallback is creating a saved list with the generated filters and opening it, which the current UI already supports.

**"Did you email us a question during the week?"**
Answer honestly. If you did not, say which question you would have asked: which tenants have already refused AI, and whether the gateway runs in the EU today.

**"Who maintains reference tables across 350 tenants?"**
A global service owned by product, with per-tenant overrides that admins can edit; overrides never overwrite source fields.

**"Dedup at 80,000 members is O(n²)."**
Blocking keys first (name prefix plus class year), scored candidates within a block, reviewed by the admin. The Annex B rule is a one-off for a 525-row file and says so.

**"Why n8n and not Symfony Messenger?"**
The reactivation step reuses the existing Campagne de mise current module, so Q1 needs neither. n8n appears in Q3 for cross-module loops because it already exists in the stack and CS can read it.

**"Is 85 percent on 100 sentences meaningful?"**
It is a gate with a confidence interval of roughly plus or minus seven points. The online edit rate on real admins is the number I trust more.

**"Which competitors?"**
Hivebrite, Graduway and similar market AI search and assistants. To my knowledge none scores the reliability of a segment or states in one sentence what leaves the platform. I will verify against their current releases in week 1 rather than assert it.

**"Which renewals are at risk in the next nine months, and do they get the score first?"**
Yes. The pilot cohort includes every renewal already flagged at risk and three top-decile ARR accounts, and the waves start with at-risk renewals.

**"The sentence box is a copyable feature."**
Agreed. The sentence box is the illustration. The asset is the normalised, reliability-scored, consented base per tenant, which takes quarters to build and is what the renewal pack sells.

**"If employer names become placeholders, how does 'chez Goldman Sachs' ever map?"**
The placeholder goes to the model, the validator re-substitutes the original text locally before employer and city resolution. The round trip is in the eval set, because it is the most common sentence shape.

**"Relative dates: evaluated when?"**
At query time, on the tenant's clock. Campaign modules resolve the member set at send time. Exports are snapshots and carry the resolution date.

**"Custom criteria labels like 'Donors > €10k' go to the model. Is a label never confidential?"**
Standard criteria names are AlumnForce's vocabulary. Tenant-defined labels are sent as typed ids unless the tenant opts its labels in. The tenant decides, per instance, in the same place it switches the flag.

**"You compute the status for all 350 tenants before any DPIA is written?"**
No. Normalisation columns are backfilled for everyone because they derive nothing new. The reliability status is computed per tenant only after it has recorded its decision and switched the flag.

**"The engine has no criterion-type extension point and the relative-date operator costs six weeks. What do you cut?"**
The relative-date operator first: saved segments then carry an "as of" date and the box re-resolves on open. Then the live Vue pre-fill, replaced by the saved-list import. Never the status column, the two criteria or the metering.

## Developer split (removed from slide 12 for space)

Backend 1: status column, criteria, reindex, reference tables. Backend 2: gateway, validator, metering, evals. Front: segmenter pre-fill and split (Vue). Shared: backfill, actions, duplicate report.

## Your 10 minutes of questions

Ask: which tenants have already said no to AI and why; how criteria and permissions are modelled in the segmenter; what the gateway logs today and where it runs; how the three expert tenants differ from the rest. Add one on the business: which tenants refuse AI today and what share of ARR they represent. And one on the team: who owns data quality today, if anyone.

## What you saw on the demo (say it as your own observation)

- Users → Lists: about 45 criteria in 9 groups, picker with search, values joined by OR inside a property, properties stacked with AND, no nesting, no relative dates.
- City (workplace) has a geocoded radius operator; Experience (date) has before/after; Sector and the NAF industry code exist on the current job.
- No criterion and no profile field for last login or last profile update. That is the gap the reliability status fills.
- 31 saved lists, most auto-named "List - date". Actions on a list: Export only; campaigns pick lists from their own module.
- A "Campagne de mise current" module exists already (your nudge loop). A support chat widget exists; no AI in the segmenter.
- The brief says about 60 criteria; the demo shows about 45. Say "the demo shows around 43; I assume production instances expose more".

## Before you send: the verification checklist Annex A commits you to

Annex A says you verified these yourself. Do them, or edit Annex A to what you actually did.

1. Run `bash tools/build.sh`? Not needed. Run the Annex B snippet in README.md on the CSV and confirm 49 rows.
2. Open the CSV in a spreadsheet: check 525 rows, the eight spellings of London, the 25 rows M0501 to M0525.
3. Read the twelve verbatims and decide whether you agree with the coding on slide 3.
4. Log into the demo instance yourself, open Users → Lists → Create a list → Add a filter, and confirm there is no last-login criterion and that Communication → Campagne de mise current exists.
5. Read every slide once as yourself; change any position you would not defend.

Disclose if asked: an automated browser session explored the demo with your account and created then deleted one empty test list. Consider changing the demo password you shared.

## Honesty notes

- Token prices in the deck are deliberately an order of magnitude. If asked for a number, say you will take it from the gateway logs, not from memory.
- The demo-instance findings are from one admin session on the demo. Say what you saw, not more.
- The 25 duplicates were found by a matching rule you tuned by hand; say so if asked how.
