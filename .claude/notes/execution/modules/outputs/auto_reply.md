# Notes — execution/modules/outputs/auto_reply.py

- [pattern] Objection matching: lowercased-body substring scan, first-match wins. Order in `objection_responses` matters — put specific keys (e.g. `not_ready`, which also catches "too small" / "not big enough") before generic ones (`not_interested`).
- [technical] Voice reference is process-cached in `_VOICE_REFERENCE_CACHE` keyed on the config path. Editing `config/accessory_masters_voice.md` requires a process restart to take effect.
- [technical] Relative `voice_reference_file` paths resolve from repo root (`Path(__file__).resolve().parents[3]`). Keep config paths repo-relative, not absolute, so they work across machines.
- [pattern] System prompt is assembled by joining non-empty sections with blank lines: persona, `tone.auto_reply_instruction`, `Rules:` guard rails, voice section, objection section, CTA section. Order matters for LLM attention — voice + objection + CTA come last so they're freshest.
- [constraint] CTA rotation is prompt-only — no per-recipient state. The model is told "pick one and never repeat", but actual cross-send tracking would need persistence (not built).
- [learned] Hot-lead handoff runs *before* classification check. Even a `positive`-classified reply with "call me at 555-..." bypasses auto-reply. Defense-in-depth against the classifier missing a hot signal.
- [constraint] Post-processing pipeline order is load-bearing: word-cap → strip dollar amounts → strip exclamations → sentence-cap. Strip-dollars also drops sub-3-word fragments left behind so we don't ship orphaned phrases.
- [pattern] Word-cap fallback: if last sentence boundary is in the second half of the truncated string, cut there; otherwise strip trailing punctuation and append a period. Keeps replies readable when the LLM runs long.
- [learned] LLM provider failures return `FALLBACK_REPLY` ("Thanks for getting back to me. Let me follow up with more details shortly.") — generic but safe. Post-processing still runs on the fallback.
- [technical] Source of truth for objection script: `~/Downloads/Accessory Masters AI Bot Training.md` (human-authored). 11 objections currently encoded; if the broker playbook expands, mirror it into `config/accessory_masters.json` and `config/accessory_masters_voice.md`.
