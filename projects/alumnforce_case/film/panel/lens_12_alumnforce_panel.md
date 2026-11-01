# Lens 12 · The AlumnForce panel (CPO, CTO / Head of Data, CS lead)

**Verdict: NOT CLEAR as the opener. CLEAR as an on-request clip once the two high fixes are in.**

The film is substance, not style: every number traces to `FACTS.md` and the re-run SQL, and it uses no names or logo. But it is 76 s of a 20-minute slot (6 %), it tells the same story as slides 3–4, and it puts a synthetic British voice in front of a panel that is already wary of AI-made decks. Its one line that goes further than the deck is the line a CS lead will challenge.

## Findings

**HIGH 1. "6 can be e-mailed today" says more than the deck.** The deck says "Worth e-mailing today · recent enough to trust" (slide 3) and "send, confirm, reactivate" (slide 4), so only *Current* means send, and the 5 *To confirm* get a confirm prompt. Nothing shows opt-out or consent was checked, and the film quotes "Two unsubscribed." 15 s earlier. *Fix:* "6 worth contacting today: 1 to send, 5 to confirm." Change the S14 caption, the bracket label and the end slot ("6 e-mail today" becomes "6 worth contacting").

**HIGH 2. It is not in the plan.** `SPEAKER_GUIDE.md` never mentions the film. Minute 0–2 opens on the data line, so the film would delay the thesis and push slides 12–13 (already rushed). *Fix:* keep the opener as written. Add one line to the guide's "Likely questions": "Want to see it in 76 s? I had an agent render it from the verified numbers."

**MED 3. The brief's sentence is captioned with commas the brief doesn't have.** S01b reads "Graduates working in finance, in London, for more than three years." The brief and slide 3 have no commas. The search box is verbatim, so this reads as a misquote of *their* brief. *Fix:* put the exact text in quotation marks in the caption, and keep the commas only in the narration.

**MED 4. A real member ID sits next to a schematic city.** The loupe shows "M0475 · Londres (Royaume-Uni)". `src/FACTS.md` says cities on the cards are schematic. A Head of Data who opens the CSV may find M0475 somewhere else. *Fix:* check M0475 against the file, or use an ID that really has that spelling.

**MED 5. Our own eval says FAIL.** `EVAL_REPORT_v1.md` gives FAIL overall. Most of that is checker noise (cue IDs and resolution read as facts), but it also records a 4.29 s freeze at 55.7–60.0 s and 19.5 cps on the brief caption. If asked "did you check it?", "the report says FAIL" is a bad answer. *Fix:* produce a v2 report with the false positives whitelisted.

**LOW 6. No "exercise file" label.** "68 % of 500 members" could be taken for a claim about our live customers. *Fix:* add "exercise file" to the "Schematic" tag.

## Q&A, right after it plays

- **CPO: "How long did it take?"** About 49 minutes of agent time, measured in `BUILD_LOG.md`, all rendered locally with no paid API. The real work was the days of analysis it rests on. The film only packages it.
- **CPO: "Did you check every number?"** Every number on screen comes from a fact sheet traced to the re-run SQL (49, split 1/5/43). The build removed count-up animations that briefly showed numbers not in it. An automated speech check confirmed the narration matches the script.
- **CTO: "What did the AI get wrong?"** It flashed invented intermediate numbers ("13", "×2.5") and mispronounced the product name ("A trusted segment, see?"). Both were caught by checks and fixed, and that is why I verify rather than trust.
- **CS: "Could our product team make these for customers?"** Yes, as an annual "data health" recap per school: aggregates only, templated, rendered on our side. I'd build the static report first and add the film only if it lifts renewal conversations.
- **CTO on cost and safety:** The marginal cost is CPU minutes: about 2 min of frame render and local TTS. The risk is per-tenant aggregates leaking and asset licensing. It is a Q3 idea at the earliest, never part of the Q1 increment.

## Honest gaps

- I could not open the CSV (not in the folder), so M0475 and opt-out status are unverified.
- I have not checked the licences of the toolkit (lemo-opuscar), the Kokoro voice or the sample packs (`src/CREDITS` not read).
- I judged from the script, the captions and 6 frames, not from watching the film. I have not tested whether the audio works in the room.
- The guide talks about a 15-slide deck, but `presentation.html` has 8 slides. The opener plan needs to say which one is projected.
