# Humanizer

## Goal

Strip AI-tells from generated text and rewrite it in a personal voice profile so it reads as natural human writing before pasting into LinkedIn, Slack, email, or Twitter. The tool is voice-profile-first: each profile captures real writing samples, lexicon preferences, and formatting habits so the LLM can match cadence rather than just removing banned words.

## Inputs

### CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--text <str>` | (none) | Direct text to humanize. Mutually exclusive with `--file`. If neither is provided, reads from stdin. |
| `--file <path>` | (none) | Path to a text file to humanize. |
| `--voice <name>` | `debanjan` | Voice profile name. Must match a file in `execution/content/voices/{name}.json`. |
| `--platform <name>` | `generic` | Target platform: `linkedin`, `email`, `slack`, `tweet`, `generic`. |
| `--max-length <n>` | (platform default) | Hard character cap. Tweet default is 280. |
| `--show-diff` | off | Print before/after side-by-side to stderr. |
| `--keep-em-dashes` | off | Skip em-dash replacement for intentional dashes. |
| `--tier <name>` | `default` | Model tier: `default` (Sonnet-class), `premium` (Opus-class), `gemini` (free Gemini). |
| `--dry-run` | off | Skip LLM call; show pre-pass output and estimated cost. |

### Environment variables

| Var | Required? | Purpose |
|-----|-----------|---------|
| `OPENROUTER_API_KEY` | Preferred | One key reaches Claude/Gemini/GPT via OR (default and premium tiers) |
| `ANTHROPIC_API_KEY` | Fallback | Direct Anthropic path if OR key is absent |
| `GEMINI_API_KEY` | For `--tier gemini` free path | If absent, `gemini` tier routes via OR (paid) |

### Voice profile format

Voice profiles live in `execution/content/voices/{name}.json`. Copy `_template.json` to create a new one. Required fields:

```json
{
  "name": "...",
  "display_name": "...",
  "description": "...",
  "traits": {
    "sentence_length": "...",
    "register": "...",
    "punctuation": "...",
    "formatting": "..."
  },
  "lexicon": {
    "uses": ["..."],
    "avoids": ["..."]
  },
  "examples": ["Real sentence 1", "Real sentence 2", "..."]
}
```

The `examples` field is the most important: it should contain 5-10 verbatim sentences written by the real person. The more natural the samples, the better the LLM matches cadence.

## Tools / Scripts

| File | Purpose |
|------|---------|
| `execution/content/humanizer.py` | Main CLI — four-stage pipeline |
| `execution/content/voices/debanjan.json` | Default voice profile |
| `execution/content/voices/_template.json` | Template for new voice profiles |
| `execution/modules/model_registry.py` | Runtime model resolution (resolve_model) |

### Dependencies

```
pip install python-dotenv openai anthropic google-genai
```

(OpenRouter uses the `openai` SDK pointed at the OR base URL.)

## Outputs

- **stdout**: humanized text only (pipe-safe)
- **stderr**: log lines (INFO level), estimated cost (on `--dry-run`), before/after diff (on `--show-diff`)

## Steps

The humanizer runs a four-stage pipeline:

1. **Read input** — from `--text`, `--file`, or stdin. Input > 5000 chars is truncated to 5000 chars with a WARNING log; text beyond the limit is dropped before any further processing.

2. **Deterministic pre-pass** (`_rules_pre_pass`)
   - Strip opening fluff: "Certainly!", "I'd be happy to...", "Great question!", etc.
   - Strip closing fluff: "I hope this helps!", "Let me know if you have questions", etc.
   - Replace em-dashes (`—`) with ` - ` (unless `--keep-em-dashes`)
   - Flag (do NOT auto-replace) banned vocab from voice profile + default list
   - Flag triple-parallel structures ("not just X, but Y, and even Z")
   - Flag excessive hedges ("it's worth noting", "perhaps", "broadly speaking")
   - Output: pre-cleaned text + list of flags for the LLM

3. **LLM rewrite** (`_call_llm_humanize`)
   - Provider auto-detected from env vars and tier
   - `--tier gemini` with `GEMINI_API_KEY` -> Gemini direct (free)
   - `--tier gemini` without `GEMINI_API_KEY` -> OpenRouter (paid)
   - `--tier default/premium` with `OPENROUTER_API_KEY` -> OpenRouter (preferred)
   - `--tier default/premium` without OR key -> Anthropic direct
   - Tool-use with forced `submit_humanized` call ensures clean JSON extraction
   - System prompt embeds all rules; user prompt includes voice profile + flags

4. **Platform post-process** (`_platform_post_process`)
   - `linkedin`: strip `**bold**`, `*italic*`, `#` headings; keep bullets as prose
   - `slack`: strip markdown except `*italic*` and `` `code` ``
   - `tweet`: hard cap at 280 chars (or `--max-length`)
   - `email`: preserve paragraph/list structure
   - `generic`: minimal changes

5. **Output** — print humanized text to stdout. If `--show-diff`, print before/after to stderr first.

## Edge Cases

| Case | Behavior |
|------|---------|
| Empty input | Returns empty string, exits 0, logs a warning |
| Input > 5000 chars | Truncated to 5000 chars with a WARNING log; text beyond the limit is dropped before any further processing. |
| Voice profile missing | Exits with clear error listing available voices and template path |
| Voice JSON invalid | Exits with JSON parse error |
| No API keys set | Exits with clear message listing which env vars are needed for the chosen tier |
| `--tier gemini` without `GEMINI_API_KEY` | Logs a warning, routes via OpenRouter (paid) |
| Mixed languages | English only in v1; voice profile lexicon won't match non-English banned vocab |
| Intentional em-dashes | Use `--keep-em-dashes` to preserve them |
| LLM returns no tool call | Falls back to raw content or text block; logs a warning |
| Very short input (< 10 chars) | Pre-pass runs normally; LLM rewrites may be odd for single words |

## Exit Criteria

- `py execution/content/humanizer.py --text "Certainly! I'd be happy to help you with that!" --dry-run` exits with code `0`, prints pre-pass output to stdout, and prints estimated cost to stderr — no errors.
- `py execution/content/humanizer.py --text "Certainly! I'd be happy to help!" --voice debanjan` (real call) exits `0` and stdout contains no em-dashes (`—`), no opening fluff ("Certainly", "I'd be happy to"), and no exclamation marks in the humanized output.
- Stdout contains only the humanized text (pipe-safe); all logs and cost lines appear on stderr only.
- `py execution/content/humanizer.py --voice nonexistent` exits non-zero and stderr lists the available voice names and template path.
- `execution/content/voices/debanjan.json` exists, is valid JSON, and has a non-empty `examples` array of at least 5 strings.

## Adding a new voice

1. Copy `execution/content/voices/_template.json` to `voices/{name}.json`
2. Fill in `display_name`, `description`, `traits`, `lexicon`
3. Collect 5-10 real sentences written by the person — exact quotes from their messages, posts, or emails. Paste as `examples` strings verbatim. Autocorrect and paraphrasing defeat the purpose.
4. Save, then test: `py execution/content/humanizer.py --text "Certainly! I'd be happy to..." --voice {name} --dry-run`
5. Run a real call and check that the output sounds like the person: `py execution/content/humanizer.py --text "..." --voice {name} --show-diff`
