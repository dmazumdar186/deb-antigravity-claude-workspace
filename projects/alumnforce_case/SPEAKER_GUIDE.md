# Speaker guide — AlumnForce case, 20-minute presentation + 30-minute Q&A

Deck is 15 slides plus three annexes: A is AI usage, B is selection logic, C is the technical and compliance sheet. In the deck the feature is called **Trusted Segments**. The natural-language input is "the sentence box". Reliability words are **Current / To confirm / To reactivate**, nothing else. And in the room, never say "chat", "grade" or "stale".

Audience is the CPO and a Lead Developer. Frédéric (founder) pitched the role as senior AI PM — someone who can clean the database, run AI evals, and think about LangChain-style orchestration. They're bootstrapping, so every slide should sound cheap and prove something.

## Timing (20 minutes)

| Min | Slides | What to say |
|---|---|---|
| 0–2 | 1 | Open with the data line: "Same sentence on your file: 2, 26 or 49 people, and 6 you can safely email." Then the thesis: you asked for speed, your users asked for trust, so the platform returns how far to trust the list. |
| 2–4 | 2–3 | How you read the material. The 8-of-12 verbatims point. |
| 4–7 | 4 | The data slide. Land the 525-vs-500 and the "tenure = staleness" insight. Then the 2 / 26 / 49 / 6 line. This is the memorable moment. |
| 7–11 | 5–7 | The increment, sized in dev-weeks with a 26 dev-week core and a pre-named cut, then the exclusions. The panel grades the "no". |
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
Three reasons. It needs member data in the prompt, so DPO vetoes it. Its output can't be checked against a golden set. And it sets an expectation we can't meet with 3 developers. A translator with a fixed vocabulary we can actually evaluate and explain.

**"What about LangChain / LangGraph? Would you use it?"**
Not for this increment. One model call with a JSON schema and a deterministic validator is a function, not a graph. Pulling a framework into a PHP shop adds a dependency and gives us nothing back. I'd look at it again in Q2 if we start chaining calls (question → aggregate query → narrative), and even then I'd rather have a thin internal orchestrator sitting behind the gateway so the provider stays swappable. What I actually keep from the LangChain world is the discipline: typed tool schemas, trace every call, evals in CI.

**"How do you run evals concretely?"**
A golden set of 60 to 100 sentences with expected filter JSON, written by two people independently so the labels are not one person's bias. Metric at the filter level: precision and recall per criterion, plus exact-match rate. Also a negative set of sentences that must return "cannot map" (discriminatory or impossible requests). Run in CI on every prompt, schema or model change; results versioned next to the prompt. Online: edit rate and rejection rate, plus a weekly manual sample of 20.

**"Which model and provider?"**
Open, and I want to keep it open. The contract is schema in, JSON out, so any EU-hosted mid-tier model works. I'd start with the cheapest one that clears the 85 percent eval gate. EU region is non-negotiable though, that's the DPO answer.

**"Why is the cost so low? Are you sure?"**
The prompt is the sentence plus a schema and value lists — roughly 2,000 tokens, with a cacheable prefix. I give an order of magnitude and confirm it on the gateway in week one. The expensive part is engineering, that's why the metering is there from day one.

**"How do you handle permissions?"**
The assistant runs in the admin's session. The model only sees the tenant's criteria names and operators, never data, so the cached prefix is shared per tenant. Then the validator strips any criterion the role isn't allowed to use — that part is unit-tested. The query itself goes through the existing segmenter engine, which already scopes to the instance. What's actually new to secure is the gateway credential and the per-call log. Both are covered in Annex C.

**"What if the model hallucinates a criterion?"**
It can't. The validator rejects any criterion that isn't in the schema and any value that isn't in the reference tables. Whatever doesn't map, the admin just sees as text. So the model can't invent a filter that actually reaches the database.

**"Isn't data cleaning a different project?"**
No, same project. Without normalisation the assistant gives you 2 or 49 people for the same sentence. The current / to confirm / to reactivate split is what turns dirt into something the admin can actually act on. And the deterministic layer ships to tenants who refuse AI entirely, so it's the commercial hedge too.

**"How would you dedupe in production?"**
Blocking keys first — name prefix plus class year. Then inside each block, a scored candidate list: name similarity, same start date, same employer. Show it to the admin with the score. Never auto-merge. The one-off rule in Annex B requires the same start date because the looser "or same job" variant actually merged Martin into Martinez. Thresholds get tuned on the pilot tenants' confirmed and rejected merges.

**"What about OpenSearch and semantic search?"**
Q2 at the earliest, and only after normalisation. Embed eight spellings of London and you've just embedded the noise. It also means member text moves toward a model, that needs its own DPO conversation.

**"Pricing?"**
Included, with a fair-use quota. Metered past that. Catherine won't pay for AI, she pays for dues. If the nudge loop lifts dues in a measurable way, then that loop can actually be priced.

**"What would you do in week one?"**
Instrument the current segmenter first, so we actually have baselines. Then get the ticket data and build the golden set with CS. Decide freshness thresholds with the three expert tenants. And confirm gateway region and per-call logging.

**"You are the only PM with shared developers. What slips?"**
Deliverable 2 (the sentence box). Deliverable 1 ships regardless because it has value alone.

## Questions added after the six-lens review (be ready)

**"Your capacity math: our developers are shared."**
The brief says shared, so I plan on roughly half of 3–4 developers: 24–28 dev-weeks, confirmed in week 1. The core is 26: reliability tag, sentence box, the two actions, flags and metering. The duplicate report and the relative-date engine operator are Q2. Below 24 dev-weeks the box pre-fills from a saved-list import instead of live Vue state. The reliability tag and metering don't move.

**"Your pilot is three weeks and your stop criterion says eight."**
Two layers, two speeds. Week 12 decides the sentence box on leading indicators: eval gate, adoption and edit rate over three weeks. Week 17 decides the reactivation loop, thirty days after the first campaign. The quarter still ends with a decision.

**"You send the full criteria schema to the model and strip by role afterwards. Why?"**
The schema is just criteria names, not data. Sharing it per tenant keeps the cached prefix cheap. And role stripping is deterministic, it's unit-tested — that's more reliable than asking the model to respect permissions, right?

**"The gateway points to a US provider today."**
Right, so the sentence box doesn't launch until an EU-hosted endpoint is behind the gateway, with the provider's legal entity and transfer mechanism actually named. The reliability layer doesn't wait on that.

**"GDPR says stale data should be deleted, you say reactivate."**
Reactivation is actually the accuracy principle in practice: we ask the person to confirm or correct. Retention and deletion stay the tenant's policy. The status just makes the deletion candidates visible, which they weren't before.

**"Can the Vue segmenter be pre-filled, or is that a rewrite?"**
To confirm in week 1 with the Lead Developer. If live state pre-fill is expensive, the fallback is creating a saved list with the generated filters and opening it, which the current UI already supports.

**"Did you email us a question during the week?"**
Be honest here. If you didn't, say what you would have asked. For me it's two things: which tenants have already refused AI, and whether the gateway actually runs in the EU today.

**"Who maintains reference tables across 350 tenants?"**
One global service, product owns it. Each tenant gets overrides that admins can edit, but overrides never overwrite the source fields.

**"Dedup at 80,000 members is O(n²)."**
Blocking keys first — name prefix plus class year. Then score candidates within a block, admin reviews them. The Annex B rule is a one-off for a 525-row file, and it says so.

**"Why n8n and not Symfony Messenger?"**
The reactivation step reuses the existing Campagne de mise current module, so Q1 needs neither. n8n appears in Q3 for cross-module loops because it already exists in the stack and CS can read it.

**"Is 85 percent on 100 sentences meaningful?"**
It's a gate, nothing more — the confidence interval is roughly plus or minus 7 points. The number I actually trust is the online edit rate on real admins.

**"Which competitors?"**
Hivebrite, Graduway and similar all market AI search and assistants. As far as I know, none of them scores how reliable a segment is, or says in one sentence what actually leaves the platform. I'll check this against their current releases in week 1 rather than just assert it.

**"Which renewals are at risk in the next nine months, and do they get the score first?"**
Yes. The pilot cohort is every renewal already flagged at risk plus three top-decile ARR accounts, and the waves start with the at-risk renewals.

**"The sentence box is a copyable feature."**
Yes, agreed. The sentence box is the illustration, not the asset. The asset is the normalised, reliability-scored, consented base per tenant — that takes quarters to build, and that is what the renewal pack actually sells.

**"If employer names become placeholders, how does 'chez Goldman Sachs' ever map?"**
The model only sees the placeholder. The validator swaps the original text back in locally, before employer and city resolution. That round trip is actually in the eval set, it's the most common sentence shape we get.

**"Relative dates: evaluated when?"**
At query time, on the tenant's clock. Campaign modules resolve the member set at send time. Exports are snapshots, they carry the resolution date with them.

**"Custom criteria labels like 'Donors > €10k' go to the model. Is a label never confidential?"**
Standard criteria names are AlumnForce's vocabulary. Tenant-defined labels are different, they go out as typed ids unless the tenant opts its labels in. That's a per-instance call, the tenant makes it in the same place it switches the flag.

**"You compute the status for all 350 tenants before any DPIA is written?"**
No. Normalisation columns get backfilled for everyone, they don't derive anything new. Reliability status is different — it's computed per tenant, and only after that tenant has recorded its decision and switched the flag.

**"Are you asking for an engine change in Q1?"**
No. Q1 adds two date fields and a status keyword to the OpenSearch mapping and exposes them through the date filter the engine already has, plus a nightly tag. The relative-date operator is Q2 with its own rehearsal. If capacity still falls short, the live Vue pre-fill goes first and becomes a saved-list import. The reliability tag and metering never move.

## Developer split (removed from slide 12 for space)

Backend 1: status column, criteria, reindex, reference tables. Backend 2: gateway, validator, metering, evals. Front: segmenter pre-fill and split (Vue). Shared: backfill, actions (duplicate report is Q2).

## Your 10 minutes of questions

Questions to ask: which tenants have already said no to AI, and why. How criteria and permissions are modelled in the segmenter. What the gateway logs today and where it actually runs. How the three expert tenants differ from the rest.

Add one business question: which tenants refuse AI today and what share of ARR that is. And one on the team: who owns data quality right now, if anyone does.

## What you saw on the demo (say it as your own observation)

- Users → Lists: roughly 45 criteria across 9 groups, picker with search. Values inside a property are OR'd, properties stack with AND. No nesting, no relative dates.
- City (workplace) has a geocoded radius operator; Experience (date) has before/after; Sector and the NAF industry code exist on the current job.
- No criterion and no profile field for last login or last profile update. That is the gap the reliability status fills.
- 31 saved lists, most auto-named "List - date". Actions on a list: Export only; campaigns pick lists from their own module.
- A "Campagne de mise current" module exists already (your nudge loop). A support chat widget exists; no AI in the segmenter.
- The brief says about 60 criteria; the demo shows about 45. Say "the demo shows around 43; I assume production instances expose more".

## The verification checklist behind Annex A

Annex A says these were run by an agent on your instruction and reviewed by you. VERIFICATION.md is the record. If you want to redo any step yourself before sending, here they are.

1. Run `bash tools/build.sh`? Not needed. Run the Annex B snippet in README.md on the CSV and confirm 49 rows.
2. Open the CSV in a spreadsheet: check 525 rows, the eight spellings of London, the 25 rows M0501 to M0525.
3. Read the twelve verbatims and decide whether you agree with the coding on slide 3.
4. Log into the demo instance yourself, open Users → Lists → Create a list → Add a filter, and confirm there is no last-login criterion and that Communication → Campagne de mise current exists.
5. Read every slide once as yourself; change any position you would not defend.

If anyone asks, say it: two automated browser sessions went through the demo using your account. The first created one empty test list and deleted it; the second was read-only. The five Annex A checks were run by an agent on your instruction and are recorded in VERIFICATION.md. Also, you shared the demo password — I'd change it.

## Honesty notes

- Token prices in the deck are deliberately an order of magnitude. If asked for a number, say you will take it from the gateway logs, not from memory.
- The demo-instance findings are from one admin session on the demo. Say what you saw, not more.
- The 25 duplicates were found by a matching rule you tuned by hand; say so if asked how.


## Production labels are French

The deck is English. In the product the status words will be French UI strings; decide them with CS in week 1 and keep the same rule: an action word for the third status, never a verdict, and nothing admin-side shown to members.
