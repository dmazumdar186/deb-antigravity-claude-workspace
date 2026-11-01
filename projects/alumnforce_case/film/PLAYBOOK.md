# Trusted Segments film: presenter's sheet

For v2 (about 55–62 s). v1 (`trusted-segments.mp4`, 76 s) is superseded: do not play it.

## 1. Placement

**Recommendation: no film in the 20-minute talk. Play it once in Q&A, as your answer to the AI-usage question (Annex A).**

Both lenses want 2 / 26 / 49 / 6 to come from you. Lens 7's 4:00 slot then repeats your slide; lens 12's AI-question slot shows your method (fact sheet, checks, review) instead.

| Minute | What happens |
|---|---|
| 0:00–20:00 | Talk as in SPEAKER_GUIDE. You say the data line live. |
| 20:00–38:00 | On the first question about AI, evals or "how did you build this": honest line, film, follow-ups (2:30). It replaces your spoken Annex A answer: net cost about 1 minute. |
| 38:00 | Not asked yet? Offer it: "Annex A covers how I used AI. I have a one-minute example: now, or shall I send it?" |
| 40:00–48:00 | Your own questions, cut from 10 to 8 minutes. |

**Fallback:** if the sound check fails, the panel says "send it", or fewer than 4 minutes remain, don't play it. Say the honest line and send an unlisted link to the clean master, plus FACTS.md, the same day.

**If you overrule this** (lens 7): play it at 4:00 in place of the slide-4 walkthrough, cut that row from 3:00 to 1:30 (film, then 30 s live: "Six. That's the product."), and drop the data line from slide 1.

**SPEAKER_GUIDE lines to change** (you make the edits):

| Where | Now | Change to |
|---|---|---|
| Timing, row 0–2 | "and 6 you can safely email." | "and 6 worth contacting today." |
| Five lines, no. 3 | "Same sentence: 2, 26 or 49 people, and 6 you can safely email." | "Same sentence: 2, 26 or 49 people, and 6 worth contacting today: 1 to send, 5 to confirm." |
| Your questions | "Your 10 minutes of questions" | "Your 8 minutes of questions" (hold the team question in reserve) |

"Safely email" claims consent that was never checked (lenses 3, 7, 12).

## 2. The honest line (before pressing play)

"An AI agent built this film in code from the same verified numbers as the deck. The voice is synthetic, every number traces to the fact sheet, and I watched it and checked each one."

Only true once you have watched v2 with sound and ticked every number against FACTS.md.

## 3. Playback checklist

| Step | In the room | Zoom / Teams |
|---|---|---|
| File | v2 captioned master, local copy | v2 clean master (no captions), local copy. Captions are unreadable in a call tile, and you may need to talk over it. |
| Player | Local player, full screen, 100 %; not a browser tab | Same; share that window |
| Sound | Room or own speaker, volume about 70 % | Zoom: tick **Share sound** and **Optimize for video clip**. Teams: turn on **Include sound** |
| Day before | Test on the room's kit if possible | Test call to a second device: sound, slow pans not smeared |
| 10 min before | Do Not Disturb on, file paused at 0:00 | Same, plus 5 s inside a test share |

**If sound fails:** restart once. If it fails again, play it silent and narrate these beats live:

1. The brief's sentence. One sentence, four answers.
2. 525 records for 500 members. London spelled 8 ways (real record M0271 under the loupe). 25 people appear twice.
3. As delivered: 2. Normalised: 26. Full logic: 49.
4. 68 % of profiles untouched for 2+ years. Three years in post = three years without an update.
5. "340 London expats. Twenty had moved back years ago. Two unsubscribed."
6. 1 current, 5 to confirm, 43 to reactivate. 6 worth contacting today: 1 to send, 5 to confirm.
7. "The administrator's problem is not building the list. It is believing it." Trusted Segments.

Re-check these against the v2 SCRIPT.md when it lands.

## 4. The six questions after it plays

| Question | Answer |
|---|---|
| "How long did it take?" | v1 took 49 minutes of measured agent time, with voice and music rendered offline. v2 is still being measured, and token cost was never logged. |
| "Did you check every number?" | Every number comes from a fact sheet traced to the Annex B SQL, and I checked each one on screen. "6" says "worth contacting", not "can email": consent sits in the campaign module. |
| "What did the AI get wrong?" | A label sat over the previous step's value for half a second, and a real member ID appeared next to an invented city. Review caught both; v2 fixes both and shows the real record M0271. |
| "Your one current member, M0502, is a duplicate?" | It is the kept record of a duplicate pair: dedup keeps the most recently updated record, and M0502 was updated in June 2026. |
| "Could our team make these for customers?" | Yes: a yearly data-health recap per school, aggregates only, rendered on your side, each watched before it ships. A static report comes first. |
| "Cost and safety?" | A re-render is about 5 minutes of machine time; the cost is writing and checking it. No member data is in it; for customers the risks are per-tenant leaks and licences, so Q3 at the earliest. |

## 5. Recommended Annex A addition (your call)

"Evidence film (one minute, shown on request): written and rendered in code by an AI agent with lemo-opuscar from the fact sheet behind Annex B, with a synthetic voice (Kokoro); I watched it and checked every number."
