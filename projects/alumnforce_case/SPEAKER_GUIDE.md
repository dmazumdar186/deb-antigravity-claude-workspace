# Speaker guide — AlumnForce case, 20-minute presentation + 30-minute Q&A

Audience: the CPO and a Lead Developer. Frédéric (founder) framed the role as senior AI PM who can clean the database, run AI evals, and think about LangChain-style orchestration. Bootstrap phase: every slide should sound like it costs little and proves something.

## Timing (20 minutes)

| Min | Slides | What to say |
|---|---|---|
| 0–2 | 1 | The proposition first. "You asked for speed; your users asked for trust. The first thing the assistant returns is a grade." |
| 2–4 | 2–3 | How you read the material. The 8-of-12 verbatims point. |
| 4–7 | 4 | The data slide. Land the 525-vs-500 and the "tenure = staleness" insight. Then the 2 / 26 / 49 / 6 line. This is the memorable moment. |
| 7–11 | 5–7 | The increment and the exclusions. Spend time on exclusions; the panel grades the "no". |
| 11–14 | 8–9 | Orchestration diagram. Say the DPO sentence out loud, slowly. |
| 14–17 | 10–11 | Measure and stop criterion, then the three risks. |
| 17–19 | 12–13 | Quarter plan and 2027 link, quickly. |
| 19–20 | 14–15 | Decision ask, closing sentence. |

Rehearse 17 minutes; you will run over.

## The five lines to memorise

1. "The administrator's problem is not building the list, it is believing it."
2. "In this file, three years in post and three years without a profile update are the same signal."
3. "Same sentence: 2, 26 or 49 people, and 6 you can safely email."
4. "Only the administrator's question and the list of filter names leave the platform. Never a member."
5. "If under 30 percent of segments use it after eight weeks, I stop the model layer and keep the data layer."

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
The assistant runs in the admin's session. The schema sent to the model only contains the criteria that admin can see, and the query runs through the existing segmenter engine, which already scopes to the instance. We add nothing new to secure.

**"What if the model hallucinates a criterion?"**
The validator rejects any criterion not in the schema and any value not in the reference tables. The admin sees the unmapped part as text. The model cannot invent a filter that reaches the database.

**"Isn't data cleaning a different project?"**
It is the same project. Without normalisation the assistant returns 2 or 49 people for the same sentence. Grades turn dirt into something the admin can act on. And the deterministic layer ships to tenants who refuse AI entirely, so it is also the commercial hedge.

**"How would you dedupe in production?"**
Same rules as Annex B as a scoring function (name similarity, same employer or start date, same email domain pattern), proposing merges to the admin with a confidence score. Never auto-merge. Tune thresholds on the pilot tenants' confirmed and rejected merges.

**"What about OpenSearch and semantic search?"**
Q2 at the earliest, after normalisation. Embedding eight spellings of London just embeds the noise. And it moves member text toward a model, which needs its own DPO conversation.

**"Pricing?"**
Included with a fair-use quota, metered beyond. Catherine will not pay for AI, she pays for dues. If the nudge loop lifts dues measurably, that loop can be priced.

**"What would you do in week one?"**
Instrument the current segmenter for baselines, get the ticket data, build the golden set with CS, decide freshness thresholds with the three expert tenants, confirm gateway region and per-call logging.

**"You are the only PM with shared developers. What slips?"**
Deliverable 2 (the sentence box). Deliverable 1 ships regardless because it has value alone.

## Your 10 minutes of questions

Use the list on slide 14. Add one on the business: which tenants refuse AI today and what share of ARR they represent. And one on the team: who owns data quality today, if anyone.

## What you saw on the demo (say it as your own observation)

- Utilisateurs → Listes: about 43 criteria in 10 groups, picker with search, values joined by OU inside a property, properties stacked with ET, no nesting, no relative dates.
- Ville (Lieu de travail) has a geocoded radius operator; Expériences (Date) has before/after; Secteur and Code NAF exist on the current job.
- No criterion and no profile field for last login or last profile update. That is the gap the grade fills.
- 31 saved lists, most auto-named "Liste - date". Actions on a list: Exporter only; campaigns pick lists from their own module.
- A "Campagne de mise à jour" module exists already (your nudge loop). A support chat widget exists; no AI in the segmenter.
- The brief says about 60 criteria; the demo shows about 43. Say "the demo shows around 43; I assume production instances expose more".

## Honesty notes

- Token prices in the deck are deliberately an order of magnitude. If asked for a number, say you will take it from the gateway logs, not from memory.
- The demo-instance findings are from one admin session on the demo. Say what you saw, not more. A test list (id 783, 'Liste - 12/10/2026 - 16:58') was created during exploration; delete it or mention it.
- The 25 duplicates were found by a matching rule you tuned by hand; say so if asked how.
