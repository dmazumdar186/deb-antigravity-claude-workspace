# Auto-Reply Engine — Positive-Reply Nurture

## Goal
Generate human-sounding replies to positive cold-email responses and schedule them with a randomized delay. Handle common objections from the broker playbook (Accessory Masters / Hedgestone), hand off hot leads to a human, and skip neutral/negative replies. Voice and tone come from a per-client reference markdown file injected into the LLM system prompt at runtime.

## When to Use
- Triggered after `reply_classifier.py` tags a reply as `positive` (non-hot)
- Called from `accessory_masters_pipeline.py --poll-replies`
- Skipped automatically for `hot_positive` (routed to Telegram for human takeover), `negative`, and `neutral`

## Inputs

### Function arguments
- `reply` (dict): `body`, `from_email`, `from_name`, `company`, `classification`
- `config` (dict): loaded from `config/{client}.json`
- `mock` (bool): use template responses instead of the LLM
- `send_fn` (callable): function that actually sends the reply (e.g. Instantly API wrapper)

### Config keys (`auto_reply` section)
| Key | Purpose |
|-----|---------|
| `enabled` | Master kill switch |
| `model` | LLM model id (OpenRouter slug, default `anthropic/claude-haiku-4.5`) |
| `delay_min_seconds` / `delay_max_seconds` | Randomized human-like delay before sending |
| `max_sentences` / `max_words` | Hard length caps applied post-generation |
| `sender_persona` | Single-line persona injected as "You are ..." |
| `voice_reference_file` | Path to a markdown voice/tone reference (cached, injected into system prompt) |
| `cta_variants` | List of CTA phrasings — LLM is told to pick one and never repeat |
| `objection_responses` | Dict of `key → {triggers: [...], response: "..."}` matched against the inbound body (lowercased substring) |
| `hot_lead_signals` | Phrases that trigger human handoff instead of auto-reply |
| `stop_on_hot_lead` | If true, never auto-reply when a hot signal is present |
| `guard_rails` | List of rules injected as "Rules:" bullets in the system prompt |

### Environment variables
- `OPENROUTER_API_KEY` — required for non-mock generation (via `modules/llm_client.chat_completion`)

## Tools/Scripts
- `execution/modules/outputs/auto_reply.py` — auto-reply engine
- `execution/modules/llm_client.py` — `chat_completion` wrapper
- `config/accessory_masters.json` — `auto_reply` config block
- `config/accessory_masters_voice.md` — voice/tone reference (Alex broker persona)
- `tests/test_flow_chains.py` — parametrized objection-trigger tests + system-prompt injection test

## Outputs
Action dict, one of:
- `{"action": "skip", "reason": "..."}` — disabled or not actionable
- `{"action": "handoff", "reason": "hot lead detected"}` — caller should route to Telegram
- `{"action": "auto_reply", "reply_text": "...", "delay_seconds": int}` — reply was generated (and sent if `send_fn` was passed)

Side effects:
- Logs to module logger (`auto_reply`)
- If `send_fn` is provided: sleeps `delay_seconds`, then calls `send_fn(reply_text)`
- Voice reference file is loaded once per process and cached in `_VOICE_REFERENCE_CACHE`

## Steps

1. Read the `auto_reply` config block. If `enabled` is false, return `skip`.
2. If `stop_on_hot_lead` is true and any `hot_lead_signals` substring matches the body (lowercased), return `handoff`.
3. If `classification` is `negative` or `neutral`, return `skip` ("not actionable").
4. Resolve the voice reference: load `voice_reference_file` (relative paths resolve from repo root), cache it, and inject as a "Voice and tone reference" block in the system prompt.
5. Match objections: lowercase the body and for each `objection_responses` entry, check if any `trigger` is a substring. First match wins. The matched example response is injected into the system prompt as a guide ("Use this as a guide but vary the wording naturally").
6. If `cta_variants` is set, inject them with the instruction "pick one and never repeat the same one across replies".
7. Build the system prompt by joining (in order, blank-line separated): persona line, `tone.auto_reply_instruction`, `Rules:` block from `guard_rails`, voice section, objection section, CTA section.
8. Generate the reply via `modules.llm_client.chat_completion` (or `_generate_reply_mock` in mock mode). On any exception, log and return `FALLBACK_REPLY`.
9. Post-processing (in order):
   - Truncate to `max_words`, prefer cutting at the last sentence boundary in the second half; otherwise strip trailing punctuation and add a period.
   - Strip dollar amounts (`$\s*[\d,]+[A-Za-z]*`) — broker rule, never quote money. Drop any sentence fragments under 3 words left behind.
   - Replace `!` with `.`.
   - Truncate to `max_sentences`.
10. Pick a random delay in `[delay_min_seconds, delay_max_seconds]`. If `send_fn` is provided, sleep and send (or just log in mock mode). Return the action dict.

## Edge Cases
- **Voice reference file missing**: `_load_voice_reference` logs a warning and returns `None`; the system prompt is still valid without that section.
- **No `objection_responses` configured**: Generation still works; the objection guide section is just omitted.
- **Trigger matching is naive substring**: Triggers are lowercased substring matches with first-match-wins semantics. Order entries from specific to generic in the config — e.g. `not_ready` (handles "too small") should appear before `not_interested`. Negation is not handled at the matcher level; rely on the classifier upstream to filter out clearly negative replies.
- **LLM provider failure**: `_generate_reply` catches all exceptions and returns `FALLBACK_REPLY` ("Thanks for getting back to me. Let me follow up with more details shortly."). The post-processing pipeline still runs.
- **Word-truncation produces a fragment**: If the last sentence boundary is in the first half of the truncated text, the engine appends a period instead of cutting mid-sentence to keep the reply readable.
- **Dollar amounts in LLM output**: Stripped regardless of context — guard rail requires brokers never to quote a valuation.
- **Hot-lead detection is independent of classifier**: Even if the classifier says `positive`, an explicit phone number or "ready to sell" signal in the body still forces handoff. This is defense-in-depth.
- **CTA repetition**: Enforced only at the prompt level (no state across replies). Variants must be set in config; the model is told to pick one and never repeat. Tracking actual repetition across sends would require persisting state per-recipient (not currently implemented).
- **Voice reference caching**: Cached per-process, keyed on the config path string. Edits to the voice file are not picked up until the process restarts.

## Changelog
| Date | Change |
|------|--------|
| 2026-05-12 | Created. Documents existing auto-reply engine, the expanded 11-entry objection playbook, voice-reference injection (`voice_reference_file`), CTA-variant rotation (`cta_variants`), and the new "vary the CTA" guard rail. Source script: `execution/modules/outputs/auto_reply.py`. Voice reference: `config/accessory_masters_voice.md`. Objection script source: `~/Downloads/Accessory Masters AI Bot Training.md`. |
