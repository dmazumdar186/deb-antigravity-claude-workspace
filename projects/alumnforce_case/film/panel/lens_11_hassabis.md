# Lens 11 — Hassabis: does the loop compound?

**Verdict: NOT CLEAR.** The film is good one-off craft. Nothing yet makes the next film cheaper.

## High

1. **The eval fails a shippable film, so a ledger of its results would be noise.** Most failures are false positives: scene IDs, `M0475`, a metadata line, on-screen labels counted as quotes (43/61, 10/30). *Fix:* check only narration and on-screen columns and whitelist ID patterns. Then log each run to `film_ledger.jsonl` (style, stage minutes, fix rounds, first-run verdict).
2. **Facts are hardcoded, so nothing is reusable.** `film.js` contains `Array(525)`, `.slice(0, 49)` and `SLOT_VAL = ['2','26','49','6']`. Every new film pays the ~1,000 s of authoring again. *Fix:* generate `content.json` from FACTS (lemo supports `--q content=`). Move the light table, loupe and counter into an in-repo library.
3. **The house style would disappear.** MY-STYLES saves to `~/lemo-my-styles/`, which cloud sessions lose. Its interview-and-wait flow breaks No-HITL. *Fix:* save "Trusted Data" in the repo, answer in "you decide" mode, and pin `bebbbe1`.

## Med

4. **"Jev learns from replies" is not a mechanism.** Jev is a fixed model, nothing measures watch-through, and a few films give no signal. *Fix:* use process metrics for 90 days and log each Jev style pick with its confidence. Judge outcomes after 30+ sends per style.
5. **Learnings are stuck in BUILD_LOG.** Examples: Kokoro's "Segments" tail, "two" heard as "too", count-ups showing numbers not in FACTS. *Fix:* a pronunciation lexicon and a real `directives/video/lemo_opuscar.md`.
6. **Two engines mean two looks.** One variant takes about 5 min to render and encode, so 100 prospects take about 8 h. *Fix:* lemo `--q` for variants per segment. Remotion only once a per-recipient campaign is approved.

## Low

7. **The Jev score flags the wrong lines.** It scores the call to action and the title. *Fix:* score only lines tagged `fact`.

## 90 days, with decision points
- **Day 14:** Rebuilds from `content.json` and passes eval first run? If not, stop.
- **Day 45:** Film 3 needs ≤5 min of authoring and ≤1 fix round? If not, lemo stays for hero films only.
- **Day 90:** Analytics player live and 30+ views per variant? Only then let outcomes steer style.

## AlumnForce: an auto-made alumni film per school
**Moat:** the trust layer: dedup, normalisation and the reliability split, on data only AlumnForce holds. MIT visuals are no moat. **Trap:** the film's own thesis. With 68 % of profiles stale, a polished auto-made film would broadcast stale numbers. Also brand rights, GDPR, irreproducible films. *Fix:* a deterministic template showing only "current" counts, ending on "Confirm / Correct". The film then refreshes the data: that loop compounds.

## Honest gaps
- I did not run the eval or the build.
- I did not check that `--q` covers camera paths.
- Render times come from one container.
- No reply data exists to test finding 4.
