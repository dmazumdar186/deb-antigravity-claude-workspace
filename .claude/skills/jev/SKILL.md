---
name: jev
description: Use Jev (TypeSafe System One decision model via OpenRouter) for any classify / pick / score / gate step — bulk tagging, routing, triage, confidence gates. Triggers on "use jev", "classify with jev", "jev this", /jev, or any high-volume yes-no, menu or scale decision.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Jev — typed decisions, not text

Jev answers only three ways: **noul** (probability a statement is true), **choice** (one option from a
menu you supply, with per-option probabilities + confidence), **score** (position on an ordered scale).
It cannot write a word, so it cannot invent a category. ~100-700 ms per call, input-only billing
($0.042 / MTok, output free), 32k context. One call = many questions over one `state`.

Pair it with a System 2 model: Jev decides, Claude generates. Any step that is "look at N things and
tag / pick / gate each one" is a Jev step, never an LLM loop.

## Client (always use this; never call the API by hand)

```python
from execution.modules import jev_client as jev
r = jev.decide({"ticket": text}, {
    "team": jev.choice("Which team owns this?", {"billing": "...", "bug": "...", "none": "no clear owner"}),
    "urgent": jev.noul("Is this blocking revenue?", "true when ...", "false when ..."),
    "severity": jev.score("How severe?", ["cosmetic", "degraded", "outage"]),
})
r.choice("team"), r.confidence("team"), r.noul("urgent"), r.score("severity"), r.cost_usd
rs = jev.decide_many(list_of_states, questions, workers=8)   # same questions, many items, parallel
```
Fails open: `r.error` set and `r.answers == {}` on any failure. Threshold in code: below
`confidence` (choice) or a chosen `noul` cut, route to a person or to Claude. Add a `none` option so
Jev can abstain. Env key: `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN` also read).

## Question-writing rules (TypeSafe guidance)
1. State as named JSON fields; include the facts the decision needs, nothing else.
2. One judgement per question; split independent dimensions into separate questions in the same call.
3. Every option gets a one-line description; include a no-match option.
4. Batch: never one question per call. Ask speculative questions too; they cost ~nothing.
5. Validate on a labelled set first (`--validate` in the triage script); tune descriptions, then thresholds.

## Installed workspace uses
| Use | Entry point |
|---|---|
| Model tier + skill routing per prompt (Level 1) | `/jev on|off|status|test`, hook `.claude/hooks/jev-router.sh` |
| Categorize a sheet/CSV column | `execution/google/jev_sheet_categorize.py` |
| Triage customer inquiries with a confidence gate | `execution/crm_and_pm/jev_inquiry_triage.py` |
| Tag competitor ads (Meta Ad Library) into a swipe file | `execution/custom_scrapers/jev_ad_library_tagger.py` |
| Find the best short clips in a long transcript | `execution/video/jev_clip_finder.py` |
| Score a SaaS customer base for churn / expansion | `execution/gtm_icp_filters/jev_customer_health.py` |
| Backlinks across a site or the notes second brain | `execution/rag/jev_backlinks.py` |
| Find buyers in social comments (TikTok / IG / YouTube) | `execution/lead_sourcing/jev_comment_buyers.py` |
| Validate any question set on a labelled CSV, pick a threshold | `execution/infrastructure/jev_validate.py` (`modules/jev_eval.py`) |
| Pick / benchmark the right skill for a prompt | `execution/infrastructure/jev_skill_pick.py` |
| Gate an inbox before an agent reads it | `execution/google/jev_email_gate.py` |
| Chrome extension: fold feed slop, hide ads/banners | `execution/infrastructure/jev_feed_filter_extension/` |
| Find a passage by meaning in a file, URL or folder | `execution/rag/jev_find.py` |

Remaining use cases 14-19 (image search, live meeting meter, zero-LLM chatbot, icon picking, self-assembling pages, meta use-case finder) are tracked in `directives/infrastructure/jev.md`.

Cost ledger: `.tmp/jev_ledger.jsonl` (every script appends one row). Directive: `directives/infrastructure/jev.md`.
