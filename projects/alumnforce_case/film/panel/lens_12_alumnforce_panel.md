# Lens 12 · AlumnForce panel (CPO, CTO / Head of Data, CS lead)

**Verdict: NOT CLEAR as the opener. CLEAR as an on-request clip once the two high fixes are in.**

Substance, not style: the numbers trace to the re-run SQL, with no names and no logo. But it spends 76 s of 20 minutes repeating slides 3–4 in a synthetic voice, in front of a panel wary of AI decks.

## Findings

**HIGH 1. "6 can be e-mailed today" overclaims.** The deck says "Worth e-mailing today · recent enough to trust" (slide 3) and "send, confirm, reactivate" (slide 4), so only *Current* means send. Opt-out was never checked, and the film says "Two unsubscribed." 15 s earlier. *Fix:* "6 worth contacting today: 1 to send, 5 to confirm." Apply it to S14, the bracket and the end slot.

**HIGH 2. The guide never mentions the film.** In `SPEAKER_GUIDE.md`, minute 0–2 opens on the data line. The film delays the thesis. *Fix:* keep that opener and add the film as a prepared Q&A answer.

**MED 3. The caption adds commas to the brief's sentence.** S01b reads "Graduates working in finance, in London, for more than three years". The original has no commas. *Fix:* use the exact text in quotation marks in the caption, and keep the commas only in the narration.

**MED 4. A real ID is shown next to a schematic city.** The loupe shows "M0475 · Londres (Royaume-Uni)", but `src/FACTS.md` says the cities are schematic. *Fix:* check M0475 in the CSV, or switch to an ID that really has that spelling.

**MED 5. `EVAL_REPORT_v1.md` says FAIL.** Mostly checker noise, plus a real 4.29 s freeze at 55.7 s. *Fix:* re-run as v2 with the noise whitelisted.

**LOW 6. "68 % of 500 members" could be read as our live data.** *Fix:* add "exercise file" to the "Schematic" tag.

## Q&A after it plays

- **CPO: "How long did it take?"** Forty-nine minutes of measured agent time, rendered locally with no paid API. The analysis underneath was the real work.
- **CPO: "Did you check every number?"** Every number on screen comes from a fact sheet traced to the re-run SQL (49; 1/5/43).
- **CTO: "What did the AI get wrong?"** It flashed invented in-between numbers ("13", "×2.5") and said the product name as "A trusted segment, see?". The checks caught both.
- **CS: "Could our team make these for customers?"** Yes: an annual data-health recap per school, aggregates only, rendered on our side. A static report comes first.
- **CTO, on cost and safety:** It costs about 2 CPU minutes per film plus local TTS. The risks are per-tenant leaks and licensing, so Q3 at the earliest.

## Recommendation

Don't open with it. Keep it cued after the Annex A (AI usage) answer, or offer it as a leave-behind link, and play it with sound only after a room check.

## Honest gaps

- The CSV is not in the folder, so I could not verify M0475 or opt-out status.
- I have not reviewed the toolkit, voice or sample-pack licences (`src/CREDITS` not read).
- I judged from the script, the captions and 6 frames; I did not watch the film.
- The guide describes 15 slides; `presentation.html` has 8.
