# Lens 2: Boris Cherny (tooling craft)

**Verdict: NOT CLEAR** for the series. The wk 02 film can be rebuilt by one pinned command. Wk 03 cannot be made from the directive alone.

## Findings (most severe first)

1. **HIGH: there is no content file, so wk 03 means forking and rewriting the code.** Week-specific values are hard-coded in 9 files: `timeline.js` (TXT, K), the `film.js` scenes (`f05`, `ledger`, `panel`, `reframe`), `code.py` (`raw[98:107]`, the `ooo_hits` assert), `script_md.mjs` (`99 + k`, tags), `master.sh` (title metadata), `contact_sheet.py` (SHOTS), `mix.py` (GLOCK), and `build.sh` (NAME, SRC_PY). *Fix:* move chrome, drawText, line, panel and the palette into a library in the house style. Each week supplies a `content.json` that `build.sh` reads.
2. **HIGH: the house style is tokens plus prose.** `style.json` holds only the palette and font names. The grid, chrome coordinates, safe areas and type scale exist only in the prose of STYLE.md §2 and §4. The directive's Repo locations section requires `content.schema.json` and demo source; neither exists. `reference_build` points at this deliverable. *Fix:* add `layout`, `safe`, `type_scale` and `chrome` keys, the schema, and a template `src/`.
3. **HIGH: the build does not produce the delivered folder.** `build.sh` writes the MP4, poster, SCRIPT.md and contact sheet to `$HERE` (`src/`). The delivered copies sit one level up and none are in `src/`, so someone moved them by hand. *Fix:* add `OUTDIR=${OUTDIR:-$HERE/..}`.
4. **MED: the rebuild was not proven identical.** BUILD_LOG reports "same MP4 size, SSIM 1.000". SSIM rounded to three decimals does not prove identity. Audio was not compared. "Identical poster/SCRIPT/drawn_text" has no recorded hashes or command, and the SHA of the MP4 is truncated. *Fix:* for both runs, log `ffmpeg -f framemd5` (video and audio) plus a sha256 of every artifact, and diff them in a script.
5. **MED: the environment comes from manual steps.** The LIB fallback is `/tmp/ext/lemo/lemo-opuscar`, but the directive says `.tmp/lemo-opuscar`. The venv was symlinked by hand and the bootstrap check warned that hashes are not enforced and the manifest is missing. Packs came from `fetch.sh`, the Chrome path is `/opt`, ffmpeg is 6.1 where TECHNIQUE asks for 7+, and `fonts.py` pulls from Google Fonts `main` without hashes. A fresh session starts with an empty `/tmp`. *Fix:* run `lemo_bootstrap.py install` → `check` → `build.sh`, and add a font hash list.
6. **MED: the directive does not cover series work.** It says the toolkit "is not for series work" and has no series section. It lacks a template folder, a naming rule (`prodcraft_wkNN_<slug>/`, `prodcraft-wkNN-<slug>.mp4`) and a weekly checklist (card ref, code range, FACTS sign-off, readcheck, eval, watch). Contract items are also missing: `film_ledger.jsonl`, `TREATMENT.md`, and a top-level `CREDITS` (it exists only in `src/`).
7. **LOW: `film_eval` fails every no-voice film** (`captions_parsed`, `speech_rate`). That makes OVERALL FAIL a weekly routine. *Fix:* add a `--no-narration` mode.

## Honest gaps

I ran only `sh -n` and `node --check` (both pass). I did not rebuild, decode-compare frames, check that the `/tmp` clone is at the pin, or read `film_eval.md` in full.
