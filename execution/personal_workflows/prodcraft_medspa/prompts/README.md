# Prompts

| File | Used by | Model tier | Output type |
|---|---|---|---|
| `vision_audit.md` | `audit/vision.py` | `claude-fable-5-1` | JSON (`dated_score`, `rationale`, `signals`) |
| `extract_services.md` | `preview/extract_services.py` | `claude-sonnet-5` | JSON (`services[]`, `tagline`) |
| `fuzzy_variables.md` | `outreach/draft_email.py` | `claude-sonnet-5` | JSON (two fuzzy-variable strings) |
| `classify_reply.md` | `outreach/scan_replies.py` | `claude-sonnet-5` | JSON (`sentiment`, `wants_call`, `remove_request`, `summary`, `suggested_next_step`) |
| `email_touch_1_a.md` | `outreach/draft_email.py` | n/a (human-written template; fuzzy slots only) | markdown email (front-matter + subject + body) |
| `email_touch_1_b.md` | `outreach/draft_email.py` | n/a | markdown email |
| `email_touch_1_c.md` | `outreach/draft_email.py` | n/a | markdown email |
| `email_touch_2.md` | `outreach/draft_email.py` | n/a | markdown email |
| `email_touch_3.md` | `outreach/draft_email.py` | n/a | markdown email |
| `email_touch_4.md` | `outreach/draft_email.py` | n/a | markdown email |
| `can_spam_checklist.md` | `outreach/lint_draft.py` | n/a (reference, not a prompt) | lint rule table |

Prompts are versioned; changing a prompt changes its sha256 recorded on every row (`common/llm.py` computes
`prompt_sha256` and stores it in `audits.raw` / `outreach` per call, per `CONTRACTS.md`). Never edit a prompt
file in place for a subtle wording tweak without expecting every downstream `prompt_sha256` to change —
that's intended: it lets `scripts/fit_weights.py` and reply-rate analysis separate results by prompt version.

Fixture responses for `--mock` runs live in `fixtures/llm/{prompt_name}.txt` (prompt_name = filename minus
`.md`), keyed by prompt name per `CONTRACTS.md`'s `common/llm.py` mock contract. The email templates and
`can_spam_checklist.md` are not LLM prompts (no fixture needed) — the email templates are human-written pools
with fuzzy slots filled by `fuzzy_variables.md`'s output.
