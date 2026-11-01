# Lens 7: Daniela Amodei (people, trust, reputation)

**Verdict: NOT CLEAR.** One fix before posting; the rest are optional.

## Findings (most severe first)

1. **HIGH: the unsubscribe is scored, but never shown being honoured.** At 13.3 s, "Please unsubscribe me." gets `negative · 0.99 · €0.00`. Anyone who has typed "remove me" sees their request turned into a sales label, and the film never shows the request being respected. Wk 01 even asked "Should the sequence stop?" without answering it. *Fix:* add a second tag to that card, `sequence stopped`, or `suppressed`. Do this only if the operator confirms that is what the client system does, and add it to FACTS.md as an operator row. Then the classifier reads as courtesy, not triage.

2. **MEDIUM: the hook leads with volume.** The poster says "32 inboxes, 800 sends." Founders who know outbound will read 32 inboxes as inbox rotation, which is a spam-at-scale move. The reframe at 18 s ("never 800 sends a day for its own sake") helps, but many viewers will stop scrolling or leave before then. *Fix (operator's call, and it changes the deliverable):* keep the poster as it is, and put the reframe or "Who replied?" first in the opening line of the post.

3. **MEDIUM: a polite "no" is sent to a person.** "Not interested, thanks." falls under "The rest: to the right person, with context." and then gets "CRM updated". To the person who wrote it, that reads like "we'll try to change your mind" and "we keep a record of you". *Fix:* replace that card with a second neutral question, or a reply that is easy to misread. "No" is still in F04 through the post copy.

4. **LOW: the client is not named, but the two posts describe them differently.** Wk 01 calls them "an SMB Acquisition firm" sending 15–20 a day. Wk 02 calls them "a US outbound consultancy". Readers following the series will notice, and that hurts credibility. *Fix:* the operator settles on one description.

5. **LOW: the tone is calm and editorial, not cold.** The "illustrative replies" label and the "Made in code" credit are enough disclosure. The CTA ("feel free to send me a DM") invites without pushing. The "itnerest" typo is in the operator's verbatim copy, so this lens flags it but does not change it.

## Honest gaps

- The folder has no record that the client agreed to be described in the post.
- Nothing in this repo shows whether the client system suppresses contacts after an unsubscribe.
- Judged from 8 contact-sheet frames, not the full motion or the audio.
