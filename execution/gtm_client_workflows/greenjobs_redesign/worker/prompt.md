# Ask GreenJobs — prompt contract (phase 2)

The page never sees a model or a key. It POSTs to the Worker and receives the
same shape the local matcher produces today, so the UI does not change.

## Request (browser → Worker)

```json
{ "edition": "ie", "query": "<free text or pasted CV, ≤ 4000 chars>", "limit": 5 }
```

## Response (Worker → browser)

```json
{ "matches": [ { "id": "12345", "why": "Phase 1 habitat survey experience matches the ecology brief", "terms": ["habitat", "survey", "EIA"] } ],
  "model": "z-ai/glm-5.3", "cached": true }
```

`id` must be one of the ids in the edition's `data/jobs.json`; anything else is
dropped by the Worker before it reaches the page. `why` is one sentence, plain,
no marketing.

## System prompt (sent to the model)

You match a candidate's text to live job listings. You receive the listings as
a JSON array (id, title, employer, location, sectors, salary, summary). Return
ONLY a JSON object `{"matches":[{"id","why","terms"}]}` with at most `limit`
entries, best first. Match on skills, sector vocabulary, seniority and
location. Never invent an id. If nothing fits, return an empty array.
Write `why` in one plain sentence a candidate would find useful.

## Cost control

- The dataset block is placed first in the prompt and marked for prompt
  caching; the candidate text follows, so repeat queries hit the cache.
- `max_tokens` 400; temperature 0; JSON mode on.
- Per-IP limit `RATE_PER_MINUTE`; query length capped at `MAX_QUERY_CHARS`.
