# Lens 11 — Hassabis: does the loop compound?

**Verdict: NOT CLEAR.** The film is good one-off craft. Nothing yet makes the next film cheaper, and the one feedback signal we have would mislead.

## High

1. **The eval fails a shippable film, so a ledger of its results would be noise.** Most of the FAIL comes from false positives: scene IDs `S02`–`S16`, `M0475`, the `1920×1080 … 72 BPM` metadata line, and on-screen labels counted as quotes (43/61 numbers, 10/30 quotes). *Fix:* check only the narration and on-screen columns, whitelist `S\d\d` and `M\d{4}`, and add an on-screen-labels block to FACTS. Then log each run to `film_ledger.jsonl` (style, minutes per stage, fix rounds, verdict on the first run).
2. **Facts are hardcoded, so nothing is reusable.** `film.js` contains `Array(525)`, `.slice(0, 49)` and `SLOT_VAL = ['2','26','49','6']`. Authoring took about 1,000 s of the 49 min, and every new film pays it again. *Fix:* generate `content.json` from FACTS (lemo supports `--q content=`). Move the light table, loupe, counter and plates into an in-repo component library.
3. **The house style would disappear.** MY-STYLES saves to `~/lemo-my-styles/`, which cloud sessions lose. Its flow is also about 10 questions plus "show it to the user and wait", which breaks No-HITL. *Fix:* save "Trusted Data" in the repo (the guide allows "or the folder they want"), answer in "you decide" mode, and pin `library_version: bebbbe1`.

## Med

4. **"Jev learns from replies" is not a mechanism.** Jev is a fixed model, there is no hosted player to measure watch-through, and a few films in 90 days give no signal. *Fix:* for 90 days, improve on process metrics (authoring minutes, fix rounds, first-run pass rate). Log each Jev style pick with its confidence. Judge outcomes only after 30+ sends per style.
5. **Learnings are stuck in BUILD_LOG.** Examples: Kokoro's "Segments" vowel tail, "two" heard as "too", the sibilant cut, count-ups showing numbers not in FACTS, CRF 26 to fit the size limit. *Fix:* a pronunciation lexicon, plus Learnings in `directives/video/lemo_opuscar.md`, which is still only a draft in the teardown.
6. **Two engines mean two looks.** One variant takes about 5 min to render and encode, so 100 prospects take about 8 h. *Fix:* lemo `--q` for variants per segment. Remotion only for campaigns personalised per recipient, and port components only once one is approved.

## Low

7. **The Jev score flags the wrong lines.** It gives 0.19 to the call to action and 0.32 to the title. *Fix:* score only lines tagged `fact`.

## 90 days, with decision points
- **Day 14:** Does Trusted Segments rebuild from `content.json` and pass eval on the first run? If not, stop the library work.
- **Day 45:** Does film 3 in the house style need ≤5 min of authoring and ≤1 fix round? If not, lemo stays a tool for one-off hero films.
- **Day 90:** Is there a hosted player with analytics and 30+ views per variant? Only then let outcomes steer which style gets picked.

## AlumnForce: an auto-made alumni film per school
**Moat:** the trust layer (dedup, normalisation, the current / to confirm / to reactivate split) running on data only AlumnForce holds. The visuals are MIT-licensed, so they are no moat. **Trap:** the film's own thesis. With 68 % of profiles stale, a polished auto-made film would broadcast stale numbers. Other risks are school brand rights, GDPR, and agent-written films that cannot be reproduced. *Fix:* a fixed, deterministic template that shows only "current" counts and ends on "Confirm / Correct". The film then refreshes the data, and that is the loop that compounds.

## Honest gaps
- I did not run the eval or the build.
- I did not check that `--q` covers camera paths.
- Render times come from one container.
- No reply data exists to test finding 4.
