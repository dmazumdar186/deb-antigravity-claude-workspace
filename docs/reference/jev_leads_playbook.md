# Jev Leads Playbook

Distilled outcome of a working session between a senior GTM engineer at Instantly and a senior AI researcher/engineer (formerly OpenAI, now Anthropic), 2026-10-16. Tooling: `execution/gtm_icp_filters/jev_leads.py`, skill `/jev-leads`, directive `directives/gtm_icp_filters/jev_leads.md`.

Source labels: **sourced** = public docs, release notes or reproducible community tests; **vendor claim** = stated by TypeSafe or the video presenter, not independently verified.

## (a) What the video says vs what it leaves out

The presenter runs a GTM agency and uses TypeSafe's Jev as an if/then gate. Jev returns typed decisions only (noul yes/no with probability, choice, score), never text.

What he says:

- An ICP "should I reach out?" gate in front of every send.
- Signals worth acting on: recent funding (seed to Series B at B2B companies), job posts for outbound roles where the hire contacts prospects directly, and job changes or promotions inside the buying function.
- Export your LinkedIn connections, score every row for ICP ("best 10 cents you ever spend"), save the snapshot, re-run monthly to catch people who moved to a company worth contacting.
- Data hygiene before send (all-caps first names, junk company names) flagged without an LLM.
- Suppression of customers, competitors and bad actors.
- Reply sentiment plus unsubscribe / do-not-contact detection; inbound form spam and competitor filtering.
- Benchmark: 1,000 businesses scored in 6.8 s for about 4.5 cents (**vendor claim**, consistent with our token math below).
- Works in Cursor; any harness works: tell the agent about Jev, let it read the docs, build a cookbook.

What he leaves out:

| Gap | Why it matters |
|---|---|
| No accuracy numbers | Jev is "RL-trained for calibrated decisions" (**vendor claim**) but no calibration is published. Thresholds must be validated locally. |
| Context quality | Jev fails on thin context (**sourced**: 78 GitHub issues, ~10 labels matched). A bare title is not enough. |
| Where the signal data comes from | Jev judges facts; it does not find funding rounds or job posts. Something upstream must fetch them. |
| What happens to uncertain rows | Unstated. Our answer: hold, never skip silently, never send. |
| Privacy | Every prompt goes to OpenRouter then TypeSafe. |
| Model versioning | jev-1.14 shipped 2026-10-14 (**sourced**); behaviour may shift between versions. |

## (b) Feasibility verdict per use case

Cost basis (**sourced**): $0.042 per million input tokens, output free. Per row: lead state 300-600 tokens plus ICP context and questions ~300-400, so ~600-1,000 tokens per row, i.e. **0.6-1.0M tokens per 1k rows = $0.025-0.042 per 1k rows**. Replies/inbound run longer (body text ~800-1,800 tokens per row: **$0.034-0.076 per 1k**).

| Use case | Jev question shape | State fields | Data source here | Cost / 1k rows | Risk / failure mode | Verdict |
|---|---|---|---|---|---|---|
| ICP qualify | score fit 0-3, noul reach_out, choice persona, noul timing, noul enough_context | name, title, company, industry, size, location, company description | scrape-leads (Apify leads-finder), gmaps-leads, prospeo_leads.py, serper_maps_scraper.py | ~$0.03-0.04 | Thin rows, vague ICP prose | Build now |
| Hygiene | 5 nouls (clean first name, clean company, person title, work email, usable) | first name, company, title, email | any source JSON / CSV | ~$0.02 | Over-flagging non-English names | Build now (pairs with casualize_and_city_split.py) |
| Suppression | choice relation, noul do_not_contact | company, domain, title + customer list and competitor prose | ICP profile `customers` / `competitors` | ~$0.03 | Long customer lists bloat context; exact matches belong in code | Build now |
| Signals | 4 nouls + score strength | funding round/date, job post title/text, role history | must be supplied in the row (Apify / Prospeo fields, manual export) | ~$0.03-0.05 | Jev cannot discover signals; date math is weak, compute "months since" in code | Build now (judging only) |
| LinkedIn monthly diff | choice change_type, noul now_worth_contacting | old vs new title/company | LinkedIn connections export + snapshot | ~$0.01 (changed rows only) | Fingerprint noise from title rewording | Build now |
| Reply triage | choice intent (11), score sentiment, noul needs_human, noul unsubscribe | subject, body, from | `modules/outputs/instantly.py` fetch_replies | ~$0.04-0.08 | Sarcasm, multi-intent replies; unsubscribe misses are costly | Build now, unsubscribe always reviewed under threshold |
| Inbound form filter | nouls real_buyer/spam/competitor/budget, score urgency, choice route | form fields | webhook (not built) | ~$0.04 | Low volume, so cost is irrelevant; latency matters | Build later (Modal webhook) |
| Enrichment waterfall gate | noul "worth paying to enrich" | qualify output | anymailfinder / million_verifier (AM-locked) | ~$0.03 | Saves paid credits only if qualify is validated | Build later |
| Writing the email, extracting free text, finding emails | none (generative) | n/a | Claude, Anymailfinder | n/a | Jev cannot generate | Not Jev |

Reference points (**sourced**, community): Salesforge email agent (ICP 0-3, persona choice, probability of enough info to personalise, contact/nurture/don't; low confidence becomes "unclear" and is never sent); Single Grain 60k-lead qualification (hold/route/recommend/uncertain, below 0.55 holds); an Apollo to Jev to draft repo (draft only when fit is good, an angle is picked, confidence clears and a company is present); title/company classification at ~350 tokens per call, ~$10 for ~680k title calls; 1,700 emails triaged for $0.18 with only reply-needed ones going to Claude.

## (c) The agreed architecture

**Jev gates, Claude generates, deterministic scripts move data.**

```
source (Apify / Maps / Prospeo) -> hygiene -> suppress -> qualify --only-pass
  -> enrich go rows (MX verify; paid finders only with go-ahead) -> signals
  -> Claude writes first lines -> Instantly / Sheet
standalone: replies (hourly) | inbound (per form) | diff (monthly)
```

Thresholds sit at three points: qualify (`go` needs reach_out and persona confidence at or above `--min-confidence`, fit at least good), suppress (suppress when do_not_contact or a hard relation clears the threshold) and replies/inbound (below threshold becomes `review`).

**Hold is not skip.** A `skip` row is a confident no. A `hold` row is "Jev is not sure", which usually means the row lacks facts. Holds go to enrichment, a person or Claude. Retrying Jev on the same state returns the same uncertainty and costs money for nothing. Holds are never sent and never silently discarded, because in a typical B2B list the hold bucket contains real buyers with sparse data.

## (d) Objections and answers

| GTM engineer's objection | Researcher's answer |
|---|---|
| "Calibrated" is unproven; why trust 0.6? | You don't. Label 30-100 rows per client (go/hold/skip), run `--validate labels.csv`, then sweep thresholds with `execution/infrastructure/jev_validate.py` and spec `jev_specs/lead_qualify.json`. Pick the threshold where false-go rate is acceptable, write it in the directive Run log. |
| It guesses on thin rows. | Known failure mode (**sourced**). Enrich before judging; never judge from a bare title. `enough_context` exposes thin rows so they hold instead of passing. |
| Cost at 100k rows? | Cost is all input tokens. Keep ICP context under ~400 tokens; send only fields the scenario needs; cache per unique company+title (same state, one call). At ~$0.04 per 1k rows, 100k rows is ~$4. |
| Rate limits will stall big lists. | Per-org limits (40-80 req/s reported, figures conflict). `--workers 8`, back off on 429 using retry-after, and batch many questions per call: 13 questions in one call was ~12x cheaper and 10x faster than separate calls (**sourced**). |
| The model changes under us. | Pin jev-1.13 (workspace default). Before moving to 1.14 or `~typesafe/jev-latest`, re-run the labelled set and compare accuracy and hold rate. |
| Client lists are confidential. | Prompt text leaves the workspace. Send name, title, company only. A confidential list gets company-level fields or does not run; that is the off-switch. |
| It can reason through "Series A 8 months ago, so not recent"? | Multistep and numeric reasoning are weak (**sourced**). Compute months-since and headcount bands in code, pass booleans or bands. |
| Long company descriptions help, right? | Irrelevant context hurts. Fields are capped at 1,200 chars; the 64k request / 32k per-question limits are ceilings, not targets. |

## (e) Using it permanently: weekly rhythm

| When | Run |
|---|---|
| New list (weekly) | scrape-leads or gmaps-leads to `.tmp/leads.json`, then the chain below |
| Monthly | LinkedIn connections export, `diff` against last month, save new export as snapshot |
| Hourly | Instantly fetch_replies to `.tmp/replies.json`, `replies` scenario; `interested`/`question` rows to instantly-autoreply drafts; `unsubscribe` to DNC |
| Per submission | inbound form JSON to `inbound` (manual until the webhook exists) |

```
S=execution/gtm_icp_filters/jev_leads.py; I="--icp execution/gtm_icp_filters/icp_profiles/<client>.json"
python3 $S hygiene  --input .tmp/leads.json --csv-out .tmp/clean.csv
python3 $S suppress --input .tmp/clean.csv $I --csv-out .tmp/allowed.csv
python3 $S qualify  --input .tmp/allowed.csv $I --only-pass --csv-out .tmp/go.csv --md .tmp/go.md
python3 execution/enrichment/email_mx_verify.py ...          # go rows only
python3 $S signals  --input .tmp/go.csv $I --csv-out .tmp/signals.csv
python3 $S diff     --input .tmp/connections_2026-11.csv --snapshot .tmp/connections_2026-10.csv $I
python3 $S replies  --input .tmp/replies.json --md .tmp/replies.md
python3 $S inbound  --input .tmp/form.json $I
```

Run `--dry-run` first on any new source format. Anymailfinder and Million Verifier stay AM-locked: explicit go-ahead per run.

## (f) What to measure

| Metric | Source | Healthy | Stop trusting the threshold when |
|---|---|---|---|
| Hold rate | summary decisions | 10-30% | moves >10 points week on week with no ICP change |
| Go rate | summary decisions | stable per source | doubles suddenly (ICP prose drifted or source changed) |
| Validated accuracy | `--validate` | at or above the level recorded at sign-off | drops >5 points on a fresh labelled sample |
| Cost per go lead | ledger cost / go count | cents | rising with flat go count (context bloat) |
| Reply-triage precision | spot-check 20 replies weekly | unsubscribe misses = 0 | any missed unsubscribe |

Re-label 30 rows after any model pin change, ICP edit or new source.

## (g) Next builds (not built)

| Build | Shape | Status |
|---|---|---|
| Modal webhook for inbound forms | `directives/add_webhook.md`, calls `inbound` per submission, routes to Sheet/Slack | Not built |
| Instantly reply poller | hourly fetch_replies to `replies`, writes DNC and autoreply queue | Not built |
| Enrichment waterfall gated by Jev | Clay-style: MX verify, then paid finders only for validated `go` rows | Not built (AM-lock applies) |
