# ai_opener_generator.py — Notes

- [technical] OR-empty-credits fallback: when `OPENROUTER_API_KEY` is present but the account
  has $0 credits, OR returns HTTP 402 silently on the first call. The script has no OR balance
  check at startup. Symptom: every opener returns an empty string or the script exits on the
  first lead. Fix: check OR credits at https://openrouter.ai/account before running large
  batches, or set `DEFAULT_MODEL` to an Anthropic-direct model (e.g.
  `anthropic/claude-haiku-4-5`) and ensure `ANTHROPIC_API_KEY` is set instead.

- [technical] Anthropic-direct fallback path: when OR is unavailable, set `OPENROUTER_BASE_URL`
  to `https://api.anthropic.com/v1` and use `ANTHROPIC_API_KEY`. The script uses the
  OpenAI-compatible client interface, which works with Anthropic's /v1/messages endpoint via
  the openai SDK's `base_url` override. No code change needed — env var only.

- [technical] cache_control opportunity: the system prompt is static per batch (same
  voice/persona instructions for all leads). Adding `cache_control: {"type": "ephemeral"}`
  to the system prompt message would enable prompt caching on Anthropic's side, cutting
  effective input token cost to 0.1× for all leads after the first. The static system prompt
  is currently NOT cache-marked — this is the highest-ROI single-line change in this script.
  Implementation: pass `{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}`
  as the system content item instead of a plain string.

- [technical] Cache-aware pricing gap: the cost log line uses flat `input + output` pricing.
  Under caching, this over-estimates 5–10×. The correct formula requires 4 token counts:
  `input_tokens`, `cache_read_input_tokens` (0.1× input rate), `cache_creation_input_tokens`
  (1.25× input rate), `output_tokens`. All 4 are available in `response.usage` when using
  the Anthropic SDK directly.

- [constraint] No --mode flag: `DEFAULT_MODEL` is hardcoded to `anthropic/claude-haiku-4-5`.
  There is no `--mode cheap/balanced/premium` flag per the `_TEMPLATE.py` pattern. When
  adding a `--mode` flag, map: cheap=haiku, balanced=sonnet-4-5, premium=opus-4-5.

- [pattern] Batch sizing: the script processes leads sequentially with no parallelism.
  For batches >50 leads, wall-clock time grows linearly. ThreadPoolExecutor(max_workers=3)
  with Anthropic rate-limit awareness (3 req/s sustained) is the safe parallelism ceiling.

## See also

- execution/personalization/variant_generator.py (same pricing gap applies)
- .claude/upgrades/other_categories.md (audit findings, personalization section)
- C:\Users\deban\dev\anneal\src\anneal\cost.py (reference cache-aware pricing implementation)
