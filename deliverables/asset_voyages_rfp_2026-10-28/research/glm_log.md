# GLM / Kimi log — Asset cover backdrop

Payload: public visual brief only (brand name, colours, motif, API spec). No PII, no client data.

| when | model | round | prompt tok | completion tok | cost | output | wall | generation id |
|---|---|---|---|---|---|---|---|---|
| 2026-10-28 14:25 | z-ai/glm-5.3 | initial | 705 | 5533 | $0.0253322 | 6466 B | 22s | gen-1793197508-irYX8J2sk4yqPvAQLaDc |

## v2 — concept paper + film module (2026-10-28)

Payload: the public facts only (what ASSET sells, Selectour network, Issy-les-Moulineaux, the reference scroll-film mechanic described generically). No PII, no client data, no RFP-confidential content. Prompts and raw outputs: `research/v2_models/`.

| when | model | round | prompt tok | completion tok | cost | output | wall | generation id |
|---|---|---|---|---|---|---|---|---|
| 2026-10-28 15:03 | openai/gpt-6.1-sol | 3 signature concepts (`concept_prompt.txt`) | 680 | 2122 | $0.0225800 | 7.9 KB | 51s | gen-1793199437-mvMgDmamxOED9mf3aszh |
| 2026-10-28 15:03 | z-ai/glm-5.3 | 3 signature concepts, try 1: empty (6k tokens spent on reasoning) | 691 | 6000 | $0.0167204 | 0 B | 59s | gen-1793199437-thc9AJrVXlToDg61F05m |
| 2026-10-28 15:04 | z-ai/glm-5.3 | 3 signature concepts, try 2 (reasoning effort low) | 691 | 2470 | $0.0072247 | 10.0 KB | 28s | gen-1793199510-h9q3Hh1UbWLOATIlPaxS |
| 2026-10-28 15:06 | z-ai/glm-5.3 | film canvas module (`film_prompt.txt`), truncated at 24k tokens | 1777 | 24000 | $0.0488885 | 21.4 KB | 361s | gen-1793199618-fOUPJMlfuykXTqAKkV0D |
| 2026-10-28 15:12 | z-ai/glm-5.3 | film module continuation | 10352 | 3645 | $0.0120359 | 9.3 KB | 30s | gen-1793200006-qYBT2dDZXplsDPZJnb2r |
| | | **v2 total** | | | **$0.1074495** | | | |

Review of the GLM film draft (`v2_models/film_draft_glm-5.3.js`): it was syntactically valid after the continuation, but the composition did not work.
- Objects were tiny.
- The checkbox labels sat outside the sheet.
- The map was a strip of noise at the bottom.
- The split-flap board showed random letters at the keyframe.

Kept from the draft: the API shape, the seeded PRNG, the storyboard timing and the split-flap idea. `site/js/film.js` was re-choreographed by hand on that skeleton.

GLM 5.3 lesson: with default reasoning it can spend the whole `max_tokens` thinking and return an empty message. Pass `reasoning: {effort: "low"}` and ≥ 14k `max_tokens` for code.
