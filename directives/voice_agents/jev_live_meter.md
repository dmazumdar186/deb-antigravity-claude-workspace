# Directive — Jev Live Meeting Meter

**Category:** voice_agents
**Script:** `execution/voice_agents/jev_live_meter.py`
**Tests:** `tests/test_jev_live_meter.py` (offline)

## Goal

Sort every sentence of a meeting, sales call, interview or podcast *as it is said* into decisions,
action items, risks/blockers, questions, commitments, factual claims, objections or small talk, and
keep a rolling recap. Vague factual claims get a `[check]` marker (the "BS meter").

## Operator prompts

- "Run the Jev meeting meter on <transcript>" →
  `python3 execution/voice_agents/jev_live_meter.py --transcript <path> [--replay --speed 10]`
- "Watch <captions file> live" →
  `python3 execution/voice_agents/jev_live_meter.py --watch <path>`

## Inputs

- One source: `--stdin`, `--transcript path` (.srt/.vtt/.json/plain `[mm:ss] Speaker: text`, timestamp and speaker optional) or `--watch path`.
- `--replay` (sleep per timestamps), `--speed N`, `--all` (show small talk), `--no-color`, `--recap-every 60`, `--recap path` (default `.tmp/meeting_recap.md`), `--workers 4`, `--idle-exit N` (stop watching after N idle s), `--dry-run` (no calls, just the sentence stream).
- Env `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## How to feed it live (three options)

1. **`--watch` a captions file** — any tool that appends lines to a text file: a Google Meet captions browser extension saving to disk, an Otter live export, `whisper-live` writing transcripts. Polls every 0.5 s; partial last lines wait until the newline.
2. **`--stdin` from a captioner** — pipe one utterance per line: `whisper-stream ... | python3 execution/voice_agents/jev_live_meter.py --stdin`.
3. **`--replay` a recording** — `--transcript call.srt --replay --speed 10` makes a recorded call behave like a live one (demo, regression test).

## How it works

- Long utterances are split into sentences (punctuation, then 40-word chunks for run-on captions).
- ONE Jev call per sentence (`kind` choice, `owner_mentioned` + `needs_followup` noul, `claim_confidence` 4-level score); the previous 2 sentences ride along as context.
- Calls run in a small thread pool, so a slow call never blocks the feed; results print strictly in spoken order. Shared state is lock-guarded.
- `[check]` = `kind == factual_claim` and `claim_confidence <= 1`.
- Recap buckets: decision → Decisions; action_item + commitment_or_promise → Action items (owner flagged); risk_or_blocker + objection → Risks; question → Open questions; `[check]` claims → Claims to verify.

## Outputs

- Live lines `[mm:ss] KIND(conf) Speaker: text` (ANSI colour), small talk hidden unless `--all`.
- Recap markdown every `--recap-every` seconds and at the end.
- Ledger row in `.tmp/jev_ledger.jsonl`: `caller=jev_live_meter`, sentences, cost_usd, p50_ms, errors.

## Edge cases / learnings

- Fails open: a failed Jev call becomes `small_talk` (hidden) and counts in `errors`.
- Short acknowledgements ("Will do.", "Done.", "That could work.") inherit their meaning from context and land in Decisions/Action items; treat the recap as a draft.
- Lines without timestamps (stdin/watch) use seconds since start.
- 2026-10-07 live run (40-utterance sales call, 58 sentences): $0.0017 total, p50 476 ms, 0 errors; all 3 decisions, 4 owned action items, 2 risks and both vague claims caught.

## Changelog

- 2026-10-07 — Created (RoboNuggets use case 15): CLI, stdin/transcript/replay/watch sources, ordered worker pool, `[check]` rule, rolling recap, offline tests.
