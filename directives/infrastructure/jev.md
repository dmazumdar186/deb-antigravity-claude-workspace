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

- Hook: `UserPromptSubmit` → `.claude/mods/jev-router-mod` locally; in cloud sessions (where the mod does not load) `.claude/hooks/jev-router-cloud.sh` (settings.json, no-op unless `CLAUDE_CODE_REMOTE=true`, so it never double-routes) → `execution/infrastructure/jev_router.py hook` (the old always-on shell hook is archived in `docs/reference/hooks-archive/2026-10-22/`).
- One Jev call per prompt with up to three questions: **tier** (tiny / bulk / standard / hard), **skill**
  (menu = every `.claude/skills/*/SKILL.md` name + description, plus `none`) and **advise** (plugin
  advisor, below).
- Injected context (only when confidence ≥ `min_confidence`):
  - tiny, hard → inline on `claude-fable-5-1` (the session model).
  - bulk → one sub-agent on `claude-sonnet-5-5`.
  - standard → one sub-agent on `claude-opus-5-5`.
  - skill match ≥ `skill_min_confidence` → "load `<skill>` first".
  Haiku is banned; the Haiku slot from the video is Sonnet here (operator order 2026-10-06).
- Config `.claude/jev/config.json` (routes, thresholds, timeout 2.5 s; toggles `skill_pick` and `advise`
  default true; `advisor_min_confidence` 0.6). State `.claude/jev/state.json` (`enabled`,
  `changed`); advisor dedupe in gitignored `.tmp/jev_suggested.json` (`{session_id: [caps]}` — key `_` when the hook payload has no session_id), so routing never dirties tracked files.
- Fail-open: missing key, timeout, HTTP error, bad JSON → no output, prompt untouched. Slash commands,
  `!` shell lines and prompts under 12 chars are never routed.
- Privacy: when ON, prompt text (≤ 6000 chars) is sent to OpenRouter → TypeSafe. `/jev off` for
  confidential work.

### Plugin advisor (so the operator never has to remember which tool to use)

Hybrid surfacing (operator decision): NORMAL suggestions are NON-BLOCKING; ONE risky event blocks.

- **Capability map**: `.claude/jev/advisor.json` — per capability `{kind, when, value_add}`. `kind`
  `skill`/`service` are suggestable; `always-on` (`ponytail`, `safety-guard`) are documented only,
  never suggested. `when` is the trigger Jev matches; `value_add` is a ≤90-char operator one-liner.
  Services (`freellmapi`, `pentagi`) say "Set up …" (not per-prompt installs).
- **Non-blocking note**: the router's `classify()` carries a third `choice` ("which ONE capability,
  if any, materially helps THIS prompt? include 'none'") in the SAME Jev call as tier + skill — one
  request, ~no extra latency. On a hit ≥ `advisor_min_confidence` (config, default 0.6) the hook
  prepends a single `💡 <capability>: <value_add>` line to `additionalContext`, which the
  jev-router-mod band surfaces. **Per-session dedupe**: suggested caps are stored in
  `.tmp/jev_suggested.json` (`{session_id: [...]}`); the same capability is never repeated in a session.
- **Blocking gate (the one risky event)**: `execution/infrastructure/skillspector_gate.py`, a
  `PreToolUse(Bash)` hook (`.claude/hooks/skillspector-gate.sh`, settings.json). It detects an
  unvetted skill/plugin install (git clone into/near `.claude/skills`, `cp`/`mv` into
  `.claude/skills|plugins`, `agent-reach add`, plugin enable), runs `skillspector scan <target>
  --no-llm -f json`, and on max severity HIGH/CRITICAL emits `permissionDecision=ask` so the
  operator confirms (the finding is surfaced). Below HIGH → one-line note; unscannable or scan
  error/timeout/missing binary → fail-open note, never blocks. Tightly scoped: ordinary bash
  (`ls`, `git commit`, a normal `git clone`) never trips it.
- **CLI**: `python3 execution/infrastructure/jev_router.py advise "<prompt>"` prints what it would
  suggest; `python3 execution/infrastructure/skillspector_gate.py check "<cmd>"` prints the gate verdict.
- **Validation**: labelled set `tests/fixtures/jev_advisor_set.csv` (18 prompts, every capability +
  clear negatives) + spec `tests/fixtures/jev_advisor_spec.json` (generated from advisor.json). Run
  with `jev_validate.py --spec … --data … --sweep`. Offline tests: `bash tests/test_jev_advisor.sh`.
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
| 11 | Jev in front of AI agents (email gate: reply / brand deal / spam) | ✅ `execution/google/jev_email_gate.py` (`directives/google/jev_email_gate.md`) |
| 12 | Chrome extensions (feed slop filter, unclutter) | ✅ `execution/infrastructure/jev_feed_filter_extension/` (`directives/infrastructure/jev_feed_filter_extension.md`) |
| 13 | Search by meaning (paragraph picker) | ✅ `execution/rag/jev_find.py` + `jev_find_demo.html` (`directives/rag/jev_find.md`) |
| 14 | Image search by content (needs captions; prompt log is the metadata) | ✅ `execution/image_generation/jev_image_search.py` (`directives/image_generation/jev_image_search.md`) |
| 15 | Live checker for speech (meeting action-item / risk meter) | ✅ `execution/voice_agents/jev_live_meter.py` (`directives/voice_agents/jev_live_meter.md`) |
| 16 | Chatbot with zero LLM calls over transcripts/docs | ✅ `execution/rag/jev_chatbot.py` + `jev_chatbot_ui.html` (`directives/rag/jev_chatbot.md`) |
| 17 | Smarter app UI (icon picking from text) | ✅ `execution/mobile_apps/jev_icon_pick.py` + demo + RN hook (`directives/mobile_apps/jev_icon_pick.md`) |
| 18 | Self-assembling pages from a component library | ✅ `execution/content/jev_page_assembler/` (`directives/content/jev_page_assembler.md`) |
| 19 | Find your own use cases (shipwithjev.com + past sessions) | ✅ `execution/infrastructure/jev_use_case_finder.py` (`directives/infrastructure/jev_use_case_finder.md`) |
| 20 | Confidence gate on the audit stack (escalate weak audit reports; Stop hook) | ✅ `execution/infrastructure/jev_audit_gate.py` (`directives/infrastructure/jev_audit_gate.md`) |
| 21 | Lead pipeline gates: ICP qualify, signals, hygiene, suppression, reply/inbound triage, LinkedIn diff | ✅ `execution/gtm_icp_filters/jev_leads.py` (`directives/gtm_icp_filters/jev_leads.md`, playbook `docs/reference/jev_leads_playbook.md`) |

All 21 built (1-19 on 2026-10-06/07, #20 2026-10-07, #21 jev-leads 2026-10-16), each with script + directive + offline test + one live run. New use cases: run `jev_use_case_finder.py rank` and add rows here.

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
- 2026-10-07 (session 2): use cases 11-13 (email gate, Chrome feed filter extension, search by meaning).
- 2026-10-07 (session 3): use cases 14-16 (image search, live meeting meter, zero-LLM chatbot).
- 2026-10-07 (session 4): use cases 17-19 (icon picking, self-assembling pages, use-case finder). All 19 done.
- 2026-10-07 (session 5): #20 from the use-case finder's quick-win list — Jev confidence gate on the audit stack, wired into the Stop hook.
- 2026-10-16: #21 jev-leads (skill `/jev-leads`, script, directive, playbook): Jev gates for the whole lead pipeline (qualify, signals, hygiene, suppress, replies, inbound, diff).
- 2026-11-03: plugin advisor added to the router — `.claude/jev/advisor.json` capability map, a third `advise` choice batched into the per-prompt Jev call (non-blocking `💡` note, per-session dedupe, gate `advisor_min_confidence` 0.6), and the SkillSpector `PreToolUse(Bash)` install gate (`skillspector_gate.py`, HIGH/CRITICAL → ask, else fail-open). Tests `tests/test_jev_advisor.sh` (20/20 offline); live accuracy pending OpenRouter credits (402 at build time).
