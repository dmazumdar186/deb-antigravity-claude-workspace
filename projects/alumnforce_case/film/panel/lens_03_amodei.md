# Lens 3 (Amodei): safety, honesty, legal exposure

**Verdict: NOT CLEAR.** Three fixes are needed before the talk, and none takes more than an hour.

## High

1. **Real ID paired with an invented record, in an "evidence" film.** `film.js:29-34` assigns cities at random, and `film.js:58` picks the loupe card. The result is "M0475 · Londres (Royaume-Uni)", lit as one of the 49 (`SCRIPT.md:61`). M0475 is not in `annexB_result.csv`. AlumnForce owns this CSV, so anyone on the panel can look it up and find a different record. The "Schematic" tag leaves the screen at 12.47 s (`SCRIPT.md:59`), before the loupe shot. **Fix:** show a real member of the 49 with their true city. `annexB_result.csv` has ten "Londres (Royaume-Uni)" rows, for example M0271. Or use IDs that are not in the file ("#475"), and keep the tag on screen through 16.7 s.
2. **CC BY 3.0 credit is missing from the film.** The Salamander credit exists only in `src/CREDITS:5`. The film ends on the title with no credits (`SCRIPT.md:79`), and the deliverables are just the mp4 and srt (`BUILD_LOG.md:121`). **Fix:** add a 2 s end card or a line on the deck's last slide: "Piano: Salamander Grand Piano V3, Alexander Holm, CC BY 3.0" plus the source URL, which CREDITS also lacks. Ship CREDITS next to the mp4.

## Medium

3. **"6 can be e-mailed today" overclaims** (`film.js:350`, `SCRIPT.md:23,75`). F12 says "Worth e-mailing today" (`FACTS.md:18`). Five of the six are "to confirm", and the brief's own quote is about unsubscribes. "Can" reads as consent or lawfulness, and no consent field was checked. `SPEAKER_GUIDE.md:11,26` goes further ("safely email"). **Fix:** change the film and the guide to "6 worth e-mailing today" and re-run TTS for L14.
4. **Annex A does not mention the film** (`deck.html:320-331`). The role is an AI PM, and the film was made in 49 minutes by an agent with "nobody to ask" (`BUILD_LOG.md:115`). If the panel finds this out afterwards, it undercuts the deck's honesty framing. **Fix:** add one line to Annex A: "Opening film: scripted, drawn, scored and voiced by an AI agent from FACTS.md; synthetic voice (Kokoro); I checked every number." Also put "Synthetic voice" on the end card. And a human must watch the film before the talk: `EVAL_REPORT_v1.md:3` is still FAIL.
5. **Campaign use.** Art. 50(4) of the AI Act (in force since 2 Aug 2026) covers deep fakes. This schematic film is not one, but AI disclosure in ads is cheap insurance. The voice is the real risk. Under the SREN law, French Penal Code art. 226-8 makes it an offence to publish a synthetic voice of a real person without their consent unless it is labelled. **Fix (directive):** a "Made with AI · synthetic voice" label on every outbound or ad film. Never clone a real person's voice without written consent. Apply platform AI-content labels where they exist. Use CC0 instruments only (`LEMO_TEARDOWN.md:121`).
6. **The PRC map rule** (`DIRECTOR.md:145-147`) goes beyond drawing borders. It says to rewrite country fields so that Taiwan, Hong Kong and Macao never appear as countries. For a French school, that alters member data and takes a political side. The override exists only in a draft (`LEMO_TEARDOWN.md:276`). **Fix:** promote it to a live directive: "DIRECTOR §13 does not apply. Never relabel any data field. Maps show no borders and keep disputed areas out of frame. The client's own geography wins."

## Low

7. **GDPR.** A pseudonymous ID is personal data for anyone who holds the key (here AlumnForce). Since the cities are random, the film shows no real attributes, only false ones. That raises an accuracy problem, not a disclosure problem, and fix 1 removes it. Showing AlumnForce its own practice file inside a recruitment exercise is acceptable.
8. **Kokoro (Apache 2.0) and Plex fonts (OFL).** Neither licence places duties on the rendered output. The OFL texts already ship in `src/fonts`. The MIT notice matters only if the toolkit code is redistributed.

## Honest gaps

- I don't know if the practice CSV holds real people or synthetic ones. It is not in the workspace.
- I did not check the provenance of the Kokoro `bf_emma` voice, or whether the Digital Omnibus has moved any Art. 50 dates.
- I did not watch the mp4. All of this comes from the source, the script and the logs.
- No trademark search on "Trusted Segments".
