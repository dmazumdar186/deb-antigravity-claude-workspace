# Lens 11 — Hassabis: does the loop compound?

**Verdict: NOT CLEAR.** The film is good one-off craft. Nothing about it makes the next film cheaper yet, and the one feedback signal we have would mislead us.

## High

1. **The eval cries wolf, so a ledger of its results would be noise.** It returns Overall FAIL on a film that is fine to ship. Most of the failures are the harness's own false positives: scene IDs `S02`–`S16`, `M0475`, the `1920×1080 … 72 BPM` metadata line, and on-screen labels flagged as quotes (43/61 numbers, 10/30 quotes). If the gate fails good films, people learn to ignore it, and then it cannot drive any decision. *Fix:* check only the narration and on-screen columns, whitelist `S\d\d` and `M\d{4}`, and add an "on-screen labels" block to FACTS. Then append each run to a `film_ledger.jsonl` with: style, minutes per stage, fix rounds, verdict on the first run.
2. **The facts are hardcoded, so nothing can be reused.** `film.js` (473 lines) has `Array(525)`, `.slice(0, 49)` and `SLOT_VAL = ['2','26','49','6']` written into the code. Authoring took 665 + 326 s, about a third of the 49 min wall clock, and the next film pays that again. *Fix:* generate `content.json` from FACTS.md (lemo already has `--q content=`). Lift the light table, loupe, climb counter, reading plate and subtitles into an in-repo component library with a props contract.
3. **A house style saved the MY-STYLES way would disappear.** It saves to `~/lemo-my-styles/`, which cloud sessions lose. Its flow is also about 10 AskUserQuestion prompts plus "show it to the user and wait" (§2, §4), which breaks No-HITL. *Fix:* use the "or the folder they want" option to save "Trusted Data" in the repo, answer the interview in "you decide" mode, and pin `library_version: bebbbe1`.

## Med

4. **"Jev learns from replies" is not a mechanism.** Jev is a fixed model, so "learning" means a person edits option descriptions. One talk and a handful of films in 90 days carry no statistical signal. There is also no hosted player to measure watch-through. *Fix:* for 90 days, improve the process using authoring minutes, fix rounds and first-run pass rate. Log each Jev style pick with its confidence. Draw conclusions about outcomes only after 30 or more sends per style.
5. **Craft learnings are stuck in BUILD_LOG.** Examples: Kokoro's vowel tail on "Segments", "two" heard as "too", the >4 kHz sibilant cut, count-ups showing numbers not in FACTS, CRF 26 to stay under 25 MB. *Fix:* turn them into a pronunciation lexicon and the Learnings section of `directives/video/lemo_opuscar.md`, which so far exists only as a draft in the teardown appendix.
6. **Two engines mean two looks.** Each variant needs about 2 min of frame rendering plus about 3 min of mux and encode, so 100 prospect variants take about 8 h. *Fix:* use lemo `--q` for variants per segment. Use Remotion only for campaigns personalised per recipient, and port components into it only once such a campaign is approved.

## Low

7. **The Jev score flags the wrong lines.** It gives "supported" 0.19 to the call to action and 0.32 to the title. *Fix:* score only lines tagged `fact`.

## 90 days, with decision points
- **Day 14:** Rebuild Trusted Segments from `content.json` and it passes eval on the first run? If not, stop the library work.
- **Day 45:** Three films in the house style: a 9:16 LinkedIn film, a per-segment outbound film, one more. Film 3 needs 5 min of authoring or less and at most one fix round? If not, lemo stays a tool for one-off hero films.
- **Day 90:** A hosted player with analytics is in place, and each variant has 30 or more views or sends? Only then let outcomes change which style gets picked.

## AlumnForce: annual alumni film per school
The **moat** is the trust layer: dedup, normalisation and the current / to confirm / to reactivate split, run on data only AlumnForce holds. The visuals are not a moat: they are MIT-licensed, so anyone can copy them. The **trap** is the film's own thesis. 68 % of profiles are untouched for 2+ years and 77 % have no login in 12 months, so a polished auto-made film would broadcast stale numbers. Other risks: rights to each school's brand, GDPR, and films written by an agent are not reproducible. *Fix:* use a fixed, deterministic template that shows only "current" counts and ends with "Confirm / Correct". Then the film refreshes the data, and that is the loop that compounds.

## Honest gaps
- I did not run film_eval or the build. Its false-positive rate comes from one report.
- I did not check whether `--q content=` covers the camera paths and set slicing.
- The render-time figures are from one 4-vCPU container.
- No reply or watch data exists to test anything in finding 4.
