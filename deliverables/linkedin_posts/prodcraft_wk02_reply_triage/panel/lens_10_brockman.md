# Lens 10: Greg Brockman (reliability, execution)

**Verdict: NOT CLEAR.** The film is fine, but next Sunday's fresh container can't rebuild it, and nothing falls back to the static card if the build fails.

## Findings (severity-ranked)

1. **BLOCKER: the logo isn't in git.** `film.js:9` awaits `logo-prodcraft.png`, but `.gitignore:27 *.png` drops it, and drops `ref/wk02_card.png` and `styleframe.png` too (`git check-ignore`). A fresh clone hangs or fails at render. *Fix:* add `!deliverables/linkedin_posts/**/src/*.png` and `!…/ref/*.png` (the repo already does this for other deliverables), then commit.
2. **HIGH: the toolkit lives only in `/tmp/ext` (2.7 GB).** It is hand-built: no manifest, and the venv hashes aren't enforced. `build.sh` reads `LIB` (default `/tmp/ext/…`), but the bootstrap's `lemo.env` exports `LEMO_OPUSCAR_HOME`, so a bootstrapped container stops with "set LIB". The bootstrap path has never built this film. *Fix:* `LIB=${LIB:-$LEMO_OPUSCAR_HOME}`, `install --packs instruments-vcsl,instruments-vsco2ce` (≈700 MB), and `LEMO_CACHE` on durable storage. Prove it once in a clean container before wk 03.
3. **HIGH: no deadline fallback.** No step says "if the film isn't ready, post the static card", and that card isn't in git anyway (finding 1). *Fix:* make the static card first, every week; it is the default deliverable, and the film replaces it only after it passes the gates.
4. **MED: the build isn't atomic as a set.** `master.sh` moves the MP4 into place before `blackdetect` runs. Stems are written in place. Failures after the master leave a new MP4 next to the old poster and SCRIPT. *Fix:* stage everything in `out/stage/`, run `blackdetect` and `film_eval` there, then promote all the files together.
5. **MED: MP4s are in git.** The 2.4 MB film plus 0.6 MB of stems are committed. That's about 160 MB a year of history that can't be removed, and the directive (line 41) says Drive. *Fix:* put the MP4, poster and CREDITS in Drive, and keep only the sha256 and the Drive link in `BUILD_LOG`.
6. **LOW:** `master.sh` hard-codes the "wk 02" title metadata. There's no `film_ledger.jsonl` (the directive requires one). The FACTS sign-off is missing.

## Time budget (BUILD_LOG)

About 31 min of agent time: 7 reading, 7 authoring, 7 review and fixes. `build.sh` itself takes 50.9 s. Add the bootstrap time (not measured) and about 3 min for the operator watch.

## Runbook: wk 03 by Sunday 18:00

- **Thu (agent):** bootstrap, check, static card. Gate: card done.
- **Fri (operator):** FACTS signed off.
- **Sat 12:00 (agent):** build plus `film_eval`. Gate: no content FAIL.
- **Sat 18:00 (operator):** watch. Gate: verdict logged.
- **Sun 12:00:** no PASS means post the card.
- **Sun 18:00:** post.

## Honest gaps

I didn't run the bootstrap install or a clean-container build, and I didn't time the pack download. How the wk 03 static card gets made isn't known.
