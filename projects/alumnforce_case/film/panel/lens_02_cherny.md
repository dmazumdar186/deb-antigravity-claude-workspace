# Lens 2 — Cherny (tooling craft)

**Verdict: NOT CLEAR.** The film can be shown. Rebuild isn't one command, determinism is unproven, and the harness's FAIL is false positives. Syntax checks and 26/26 tests pass.

## High

1. **A readcheck failure doesn't stop the build.** At `build.sh:24`, `readcheck && echo` is an AND-list, so `set -e` ignores a failure. Fix: own line.
2. **No one-command rebuild.**
   - Setup is narrated (`BUILD_LOG.md:130-132`); paths are absolute or placeholders (`:135-136`).
   - Pip and Whisper are unpinned; the npm lock is reverted; `build.sh:10` never checks the SHA.

   Fix: `bootstrap.sh` (checkout SHA, `pip --require-hashes`, `npm ci`, fetch). `build.sh` dies unless `git rev-parse HEAD` is bebbbe1aa92….
3. **Determinism is unproven.** `voice/out/` isn't shipped; Whisper word times drive the trim (`trim_voice.py:16`) and every landing, cue and foley hit (`export.mjs:16-18`). "Absorbed" (`BUILD_LOG.md:144`) means the frames move. No hashes are recorded. x264 output varies with thread count. Fix: freeze the voice stage with sha256s, pin `-threads`, write `out/MANIFEST.sha256` (timeline, mix.wav, framemd5, MP4), add `verify.sh`.

## Medium

4. **Harness false positives (reproduced). Rule changes** (film_eval.py line refs):
   - R1: `_STRUCT_COL_RE` (:346) — add `cue|line|sub|row`. Fixes S02.
   - R2: `_ID` (:145) — check an id only if its prefix occurs in FACTS (`M`); otherwise treat it as structure.
   - R3: add `\d{2,5}\s*[x×]\s*\d{2,5}` and `bpm`. Add `speed|crf` to :208. The test at `test_film_eval.py:46` covers ASCII `x` only.
   - R4: extract quotes per cell, and pair `“”` before `norm_quotes`. Removes the `"|"` and `"and label"` junk.
   - R5: in `core()` (:947), turn ` / ` into a space. F17's 97% "misquote" is a line break.
   - R6: a quote counts as a quotation only in narration or subtitles, with an attribution cue (`verbatim|said|put it`), or on a line tagged to a quoted fact. Anything else is a label: numbers checked, wording INFO.
   - R7: index FACTS number words, so "3 yrs" matches F22 "Three years".

   Data fix: add FACTS row F24 "schematic ids M0001–M0525" (covers M0475). Add a golden test on these files.
5. **No findable directive.** The draft is only an appendix (`LEMO_TEARDOWN.md:230`). It cites missing scripts. It says ffmpeg < 7 fails, but 6.1 worked (`BUILD_LOG.md:25`). It caps films at 60 s; this one is 76 s. It omits `film_eval.py` and this build's learnings: the Kokoro tail, CRF 26, no count-ups. Fix: promote it to `directives/video/lemo_opuscar.md`.
6. **Real issues the harness found.**
   - `.srt` has 40 ms gaps (`export.mjs:21`: set `t1=nx.t0`).
   - No 42-character wrap.
   - The "500" line should be tagged F02.

## Low

7. Stems transcode unscripted; `film_eval.md:20` hard-codes `/tmp/ext/venv`.

## Integration

Option C (pinned clone plus wrapper skill) is right. Add a lock file, the HEAD assertion, hashed pip, `npm ci`, mirrored models and a description of 250 characters or less. No marketplace plugin: it auto-updates code under bypassPermissions.

## Honest gaps

Nothing was re-rendered; determinism risks are inferred. Not checked:
- whether a build in place, outside `$LIB`, serves;
- whether readcheck exits non-zero on failure;
- whether Whisper's temperature fallback is random.
