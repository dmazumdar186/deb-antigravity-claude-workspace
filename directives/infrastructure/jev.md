# Jev — System One decision model in the workspace

## Purpose

Jev (TypeSafe) is a decision model, not a language model: it answers noul / choice / score questions
in ~100-700 ms with input-only billing ($0.042 / MTok, output free). Installed 2026-10-06 from the
RoboNuggets lessons "Jev will 10x your Claude Code" and "19 Jev-Claude use cases". It makes the
workspace cheaper (Level 1: per-prompt model routing + skill picking), faster (Level 2: bulk
classification automations) and able to ship things that were not cost-effective before (Level 3:
search-by-meaning, live meters, zero-LLM chatbots).

## Access

- Via OpenRouter Decisions API: `POST https://openrouter.ai/api/alpha/decisions`, model
  `typesafe/jev-1.13` (alias `~typesafe/jev-latest`). No TypeSafe account needed.
- Key: `OPENROUTER_API_KEY` (the cloud environment currently exposes it as `OPENROUTER_API_TOEKN`;
  `jev_client.api_key()` reads both). Verify: `python3 execution/modules/jev_client.py`.
- Jev does not appear in `/api/v1/models` unless `?output_modalities=decisions`.
- Shared client: `execution/modules/jev_client.py` (`decide`, `decide_many`, builders, ledger). Skill:
  `.claude/skills/jev/SKILL.md`.

## Level 1 — the router (`/jev on|off|status|test|pick`)

- Hook: `UserPromptSubmit` → `.claude/hooks/jev-router.sh` → `execution/infrastructure/jev_router.py hook`.
- One Jev call per prompt with two questions: **tier** (tiny / bulk / standard / hard) and **skill**
  (menu = every `.claude/skills/*/SKILL.md` name + description, plus `none`).
- Injected context (only when confidence ≥ `min_confidence`):
  - tiny, hard → inline on `claude-fable-5-1` (the session model).
  - bulk → one sub-agent on `claude-sonnet-5-5`.
  - standard → one sub-agent on `claude-opus-5-5`.
  - skill match ≥ `skill_min_confidence` → "load `<skill>` first".
  Haiku is banned; the Haiku slot from the video is Sonnet here (operator order 2026-10-06).
- Config `.claude/jev/config.json` (routes, thresholds, timeout 2.5 s). State `.claude/jev/state.json`.
- Fail-open: missing key, timeout, HTTP error, bad JSON → no output, prompt untouched. Slash commands,
  `!` shell lines and prompts under 12 chars are never routed.
- Privacy: when ON, prompt text (≤ 6000 chars) is sent to OpenRouter → TypeSafe. `/jev off` for
  confidential work.
- Cost: ~$0.0001 per prompt (33-skill menu ≈ 2.3k input tokens), ~600 ms. Measured 2026-10-06:
  10 prompts, 6.8 s, $0.00099, all tiers correct, skill picks gmail-label / youtube-outliers /
  gmaps-leads at 0.99.

## Level 2 / 3 — use cases (RoboNuggets order; ✅ built)

| # | Use case | Status / entry |
|---|---|---|
| 1 | Jev in Google Sheets — fill a category column from a fixed list | ✅ `execution/google/jev_sheet_categorize.py` (`directives/google/jev_sheet_categorize.md`) |
| 2 | Triage customer inquiries, confidence gate to a human | ✅ `execution/crm_and_pm/jev_inquiry_triage.py` (`directives/crm_and_pm/jev_inquiry_triage.md`) |
| 3 | Analyze competitor ads (Meta Ad Library → swipe file) | ✅ `execution/custom_scrapers/jev_ad_library_tagger.py` (`directives/custom_scrapers/jev_ad_library_tagger.md`) |
| 4 | Clip finder — score candidate moments in long video | ✅ `execution/video/jev_clip_finder.py` (`directives/video/jev_clip_finder.md`) |
| 5 | Score & profile the customer base (healthy / attention / churn risk) | ✅ `execution/gtm_icp_filters/jev_customer_health.py` (`directives/gtm_icp_filters/jev_customer_health.md`) |
| 6 | Backlinks inside a site or second brain (`.claude/notes/`) | ✅ `execution/rag/jev_backlinks.py` (`directives/rag/jev_backlinks.md`) |
| 7 | Find buyers in social comments (Apify → tag ready/question/complaint) | ✅ `execution/lead_sourcing/jev_comment_buyers.py` (`directives/lead_sourcing/jev_comment_buyers.md`) |
| 8 | Verification with a validation set | ✅ `execution/infrastructure/jev_validate.py` + `execution/modules/jev_eval.py` (`directives/infrastructure/jev_validate.md`) |
| 9 | Let Jev pick the skill | ✅ router + `execution/infrastructure/jev_skill_pick.py` bench (`directives/infrastructure/jev_skill_pick.md`) |
| 10 | Let Jev pick the model (`/jev`) | ✅ router |
| 11 | Jev in front of AI agents (email gate: reply / brand deal / spam) | planned (`google/`, extend gmail-label) |
| 12 | Chrome extensions (feed slop filter, unclutter) | planned (`infrastructure/`) |
| 13 | Search by meaning (paragraph picker) | planned |
| 14 | Image search by content (needs captions; prompt log is the metadata) | planned (`image_generation/`) |
| 15 | Live checker for speech (meeting action-item / risk meter) | planned (`voice_agents/`) |
| 16 | Chatbot with zero LLM calls over transcripts/docs | planned (`rag/`) |
| 17 | Smarter app UI (icon picking from text) | planned (`mobile_apps/`) |
| 18 | Self-assembling pages from a component library | planned |
| 19 | Find your own use cases (shipwithjev.com + past sessions) | planned |

Build order: three per session, in this order, each with script + directive + offline test + one live run.

## Exit criteria

- `python3 execution/infrastructure/jev_router.py test` returns 10 rows, 0 errors, < 15 s.
- `/jev status` shows `key: present`, routes Sonnet/Opus/Fable, no Haiku anywhere.
- Every Jev script appends to `.tmp/jev_ledger.jsonl` and prints cost + wall time.
- Offline tests pass: `python3 -m pytest tests/test_jev_*.py -q`.

## Edge cases

- 32k context: `jev_client` truncates string state at 100k chars; dict state is the caller's job.
- Choice confidence < threshold means competing options, not failure: route to a person, do not retry.
- OpenRouter 402 = out of credits; 429 = rate limit (back off; `decide_many` workers default 8).
- Windows: hooks use `py`; cloud uses `python3` (wrapper detects).

## Changelog

- 2026-10-06: installed (client, router, /jev, skill, use cases 1-3). Haiku slot replaced by Sonnet 5.5.
- 2026-10-06 (session 2): use cases 4-6 (clip finder, customer health, backlinks).
- 2026-10-07: use cases 7-9 (comment buyers, validation harness, skill-pick bench).
