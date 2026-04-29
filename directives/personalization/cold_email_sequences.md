# Cold Email Sequences — AI Opener Generation

## Goal
Generate a personalized first-line opener for each verified lead using the Claude API. The opener references something specific about the prospect's business, maintaining Aleksandar's blunt, direct tone.

## When to Use
After enrichment + verification. This is the third stage in the pipeline, running on verified leads only.

## Inputs
- `--input`: Path to verified leads JSON (default: `.tmp/verified_leads.json`)
- `--output`: Output path (default: `.tmp/personalized_leads.json`)
- `--tone-config`: Path to tone config (default: `config/tone.json`)
- `--batch-size`: Leads per batch (default: 50)
- `--mock`: Use template-based mock openers instead of real API
- Env var: `ANTHROPIC_API_KEY` (already in `.env`)

## Tools/Scripts
- `execution/personalization/ai_opener_generator.py` — AI opener generator
- `execution/modules/pipeline_utils.py` — shared utilities
- `config/tone.json` — tone configuration (voice, examples, never-say list)

## Outputs
- `.tmp/personalized_leads.json` — leads with `personalized_opener`, `opener_model`, `personalized_at` fields added

## Steps
1. Read verified leads from input JSON
2. Load tone config from `config/tone.json`
3. Build system prompt from tone config (voice, tone description, never-say, examples)
4. For each lead, construct a user prompt with: business name, industry, city, rating, reviews, website
5. Call Claude API (Haiku for cost efficiency) with system + user prompt
6. Extract opener text from response
7. Validate opener: 5-25 words, no exclamation marks, no banned phrases from never-say list
8. If validation fails, re-generate once; if still fails, use a safe fallback
9. Store `personalized_opener`, `opener_model`, `personalized_at`
10. Mark `status="personalized"`
11. Save to output JSON
12. Log: total processed, average opener length, validation failures, estimated cost

## Edge Cases
- **Cost optimization**: Haiku at ~$0.25/M input tokens. 800 leads/day = ~400K tokens/day = ~$0.10/day. Very cheap. No need for a more expensive model.
- **Rate limits**: Claude API rate limits depend on tier. Use `@retry_with_backoff`.
- **Off-tone response**: Validate that opener meets constraints (word count, no exclamation marks, no banned phrases). Re-generate once if invalid.
- **Missing lead data**: If a lead has no rating or reviews, the prompt adapts — reference industry + location instead.
- **Client tone not finalized**: Default to examples in `tone.json`. Update when client provides differentiator and never-say list.
- **Batch failures**: If a batch partially fails, save successful openers and retry failed ones. Never lose completed work.

## Changelog
| Date | Change |
|------|--------|
| 2026-04-29 | Created — initial directive for Accessory Masters pipeline |
