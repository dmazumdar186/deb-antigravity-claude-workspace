# Client Call Follow-up Generator (skeleton stub)

> **Status: stub directive.** Skeleton not implemented yet. Captured 2026-06-25 as part of the 12-AI-tools backlog (see `docs/ideas/12_ai_tools_money_makers_2026-06-25.md` shortlist #1). Pick up when the operator's call cadence justifies the ~half-day build.

## Goal

Take a recorded client / discovery / sales call → output a branded, voice-matched follow-up email ready to send via Instantly. Combines three already-shipped workspace pieces; the missing piece is ~30 lines of orchestration.

## The three already-shipped components

| Component | File | Role |
|-----------|------|------|
| Transcription + word-timing | `execution/personal_workflows/prodcraft_transcribe.py` | Whisper on the audio file -> sentence-level transcript |
| Voice-matched summarization | `execution/content/humanizer.py` | Rewrite the LLM-drafted summary in Debanjan's voice |
| Send | `execution/modules/outputs/instantly.py` | Push the email through Instantly (or Gmail MCP for non-Instantly clients) |

## Steps when implementing

1. Read directive.
2. Build `execution/personal_workflows/client_call_followup.py`:
   - Accept `--audio <path>` and `--client <slug>`.
   - Call `prodcraft_transcribe` for transcript.
   - LLM summarize (Gemini free) into structured: {recap, next_steps[], owner_per_step}.
   - Format as an email draft (subject + body).
   - Run draft through `humanizer.py --voice debanjan --platform email`.
   - Either print to stdout for review OR push to Instantly when `--send` is passed.
3. Write directive sections: Goal / Inputs / Tools-Scripts / Outputs / Steps / Edge Cases / Exit Criteria.
4. Add `tests/front_door_client_call_followup.sh` with a fixture .wav (or pre-transcribed .txt to skip Whisper in CI) + assert the resulting email mentions fixture-known names + a next-step.

## Why this is a stub today

Operator has not reported a current pain (call cadence is low). High latent value but no triggering use case. Cost to build when needed: ~3-4 hours.

## Honest gaps

- No fixture audio file captured yet.
- No Gmail-MCP alternative path written (Instantly is AM-coupled; for non-AM clients we'd send via Gmail MCP).
- No client-side "review before send" UX — `--send` would be all-or-nothing in v1.
