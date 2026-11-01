# Lemo-Opuscar Film — Directive

## Goal

Make one 20–60 s hero film entirely in code (canvas or WebGL), with an original score, Kokoro narration and subtitles, using the third-party **lemo-opuscar** toolkit pinned at `bebbbe1`. It is for a single high-craft piece where the look carries the message: a case-study cold open, a launch teaser, an explainer. It is not for series work. Background reading: the audit `projects/alumnforce_case/film/LEMO_TEARDOWN.md`, the first build `projects/alumnforce_case/film/BUILD_LOG.md`, and the panel in `projects/alumnforce_case/film/panel/` (lenses 2, 3, 6, 10, 11).

**Automation boundary.** An agent drafts and renders. A human owns the facts, watches the film and ships it. Agents never post, send or schedule a film (`.claude/rules/automation-boundaries.md`).

## When to invoke

- "Make a film / cold open / teaser / explainer about …" where the look is the point and the length is 90 s or less.
- A client needs a house film, or a variant of an approved house film (see "Campaign rungs").
- Use something else when:
  - the same template is needed many times, or brand control must be exact: use Remotion (`directives/video/remotion_authoring.md`, `remotion_render.md`);
  - the source is real footage: use prodcraft (`directives/video/prodcraft_video_edit_pipeline.md`, `prodcraft_shorts_pipeline.md`);
  - the job is editing, trimming or converting an existing video: lemo cannot do it.

## Inputs

- **`FACTS.md` (required, human-owned).** It is the only source of numbers and quotes allowed on screen, in narration or in subtitles. Use the format of `projects/alumnforce_case/film/FACTS.md`:
  - a table `| id | Fact | Value | Source |` with ids `F01`, `F02` …, each with a source;
  - a `## Hard rules for the film` section (personal data, logos, no rounding, which ids may appear);
  - a sign-off line: `Signed off: <name>, <YYYY-MM-DD>`.

  An agent never adds a fact. If a number is missing, the film does without it.
- **Brief:** audience, purpose, language, length (default 40 s; 30–60 s; up to 90 s only with a stated reason; the first film ran 76 s), and an optional brand colour and fonts. Logos only with written rights.
- **Style:** a slug, or "pick one" (Step 3).
- **Aspect ratio:** `1920x1080` (default), `1080x1920` (9:16 social) or `1080x1350` (4:5 feed), passed to the toolkit as `--size`.

## Outputs (contract)

Project folder `projects/<project>/film/` (the source goes in `src/`):
- `<name>.mp4`: H.264 High yuv420p BT.709 + AAC 48 kHz; −14 LUFS ±1 integrated; true peak ≤ −1 dBTP; 24 fps unless STYLE.md says otherwise; ≤ 25 MB when it is going out by e-mail.
- `poster.jpg`.
- `captions/<name>.srt` (spoken films). Keep it in a subfolder when subtitles are burned in; see "Edge cases".
- `SCRIPT.md`: narration, subtitles and on-screen text with time codes and fact ids.
- `CREDITS`, `FACTS.md`, `BUILD_LOG.md`, and `src/` containing `build.sh`, `TREATMENT.md` and the page.
- The eval report: `film_eval.json` and `film_eval.md`.
- `film_ledger.jsonl`: one line per build with `style`, `jev_confidence`, `stage_minutes`, `fix_rounds`, `first_run_verdict` and `operator_watch`.

Upload the MP4, the poster and CREDITS to the project's Drive folder; local files are for processing only. **No machine notes in the film, the poster or the captions.**

## Exit Criteria (declarative)

- `python3 execution/video/lemo_bootstrap.py check` exits 0 against the clone that built the film.
- `film_eval.md` reads `OVERALL: PASS`.
- `readcheck.mjs` exits 0 and `asr_check.py` exits 0 on the voice lines.
- The visual reviewer has returned PASS on the final contact sheet.
- Every narrated and on-screen number appears in `FACTS.md`, tagged with its id in `SCRIPT.md`.
- The end card carries the AI disclosure, plus the CC BY credit if `piano` or `drum_kit` was used.
- `BUILD_LOG.md` has the line `Operator watch: <date> <PASS|notes>` before any external use. Without it, the film is a draft.

## Tools / Scripts (Layer 3)

- `execution/video/lemo_bootstrap.py`: the only supported way to get the toolkit. Exit codes: 0 ready, 1 a check failed, 2 a fetch or install failed.
  - `doctor`: ffmpeg (7+ recommended, 6.x is a WARN), Node 20+, Python 3.11–3.13, the Chromium path, disk space.
  - `install [--dry-run] [--cache DIR] [--mirror URL] [--packs …]` does the following:
    - clones at `PIN_SHA`, or verifies an existing clone, and refuses if `HEAD` differs from the pin;
    - makes the clone sparse: no demos and no nested `CLAUDE.md`;
    - builds `<target>/.venv` with `pip --require-hashes --no-deps --only-binary :all:` from `execution/video/lemo_requirements.lock`;
    - runs `npm ci --ignore-scripts`;
    - fetches the packs and the Whisper models, sha256-pinned in the script, into `--cache` (env `LEMO_CACHE`; point it at durable storage so fresh containers skip the 1.3 GB);
    - writes `bootstrap_manifest.json` and `lemo.env`.

    It never runs upstream `setup.sh` or `tools/fetch.sh`.
  - `check`: verifies everything offline: pin, tracked files, `lemo.managed` unset, venv against the lock, npm versions, pack hashes, Whisper revision, the espeak path under 160 bytes.
  - `lock --from-venv DIR`: regenerates the hashed lock (needs PyPI). Re-pinning the toolkit, a pack or the lock is a reviewed commit.
- `execution/video/film_eval.py`: the deterministic QA gate (`directives/video/film_eval.md`).
- `execution/modules/jev_client.py`: the style pick (Step 3).
- Toolkit tools, run from `$LEMO_OPUSCAR_HOME` after `. lemo.env`:
  - `core/render/{still,video,events,readcheck}.mjs`, `core/render/mux.sh`, `core/render/{sheet,srt}.py`;
  - `core/tts/{tts,asr_check}.py`, `core/audio/{sampler,sfx}.py`.

## Steps

1. **Bootstrap (background).** Run `python3 execution/video/lemo_bootstrap.py doctor`, then `install --cache <durable dir>`, then `. .tmp/lemo-opuscar/lemo.env`. Any exit other than 0 stops the build; see "Edge cases" before retrying.
2. **Fact gate (human).** `FACTS.md` must exist and carry the sign-off line. Without it, build only an internal draft and never mark it shippable.
3. **Style pick: a Jev `choice` in two steps** (66 styles is too wide a menu for one call):
   1. **Family.** One `jev.decide({"brief": brief}, {...})` with:
      - `family`: a `choice` over the 11 `category_en` families from `$LEMO_OPUSCAR_HOME/styles/*/style.json`, plus `none`. Each option is described by its member styles' `line` and `uses`.
      - Speculative `noul` questions in the same call: `needs_footage`, `needs_gpu`, `has_map`, `needs_real_person`.
   2. **Style.** A `choice` over that family's 2–8 styles, with descriptions built from `en`, `line` and `uses`.
   - **Fallback.** If confidence is below 0.6, or the answer is `none`, or Jev fails open (`answers == {}`), Claude picks from the top 3 and writes down why.
   - **Rejections.** Reject Edit & Documentary styles unless the footage is cleared. If `needs_gpu` is above 0.5 in a GPU-less container, expect about 6× the render time, or pick a 2D style.
   - Log the pick and its confidence in `film_ledger.jsonl`.
   - If an approved house style exists for the client (see "Repo locations"), use it and skip this step.
4. **Brief the worker once** (Opus tier, one worker per film). It gets:
   - `$LEMO_OPUSCAR_HOME/{AGENTS,DIRECTOR,TECHNIQUE}.md`, the chosen `STYLE.md`, `FACTS.md`, the brief;
   - **this directive's Overrides, which win over the guides.**

   The worker follows AGENTS.md Workflow 2–6 in "you decide" mode: treatment first, no questions.
5. **Optional storyboard gate.** Only if the brief asks for one: `TREATMENT.md` plus 6 stills go to the operator. It is the only mid-build stop.
6. **Build.** Use `src/build.sh` with `set -e`, and put every check on its own line (`readcheck … && echo` hides failures). Encode to `out/<name>.tmp.mp4`, check it, then `mv` it over the deliverable; never let `ffmpeg -y` overwrite the delivered film in place. Add the AI-marking metadata (see "AI disclosure").
7. **Deterministic gates.** All must pass:
   - `readcheck.mjs` exit 0;
   - `asr_check.py` exit 0 (`WHISPER_MODEL` from `lemo.env`, offline);
   - `mux.sh` measured I in [−15, −13] LUFS;
   - `blackdetect` empty;
   - then:
     ```
     python3 execution/video/film_eval.py --video <mp4> --srt <srt> --script SCRIPT.md --facts FACTS.md \
       --lufs-target -14 --asr --asr-python "$LEMO_PYTHON" --out film_eval.json --md film_eval.md
     ```
     `OVERALL` must be PASS. Never change a threshold to turn something green; fix the film or the script.
8. **Visual reviewer agent.** A vision worker reads the contact sheet (`sheet.py`, one frame every 1.5 s) and the stills, and returns PASS or a list of defects. The main session never loads the images. Its checklist:
   - contrast and legibility;
   - the label/value sync (each number lands on its narrated word);
   - text overflow and overlaps;
   - no faces, logos or personal data;
   - schematic tags on screen for as long as the schematic shows;
   - maps per the Overrides;
   - the end card is present.
9. **One fix round** (DIRECTOR §11), then re-run steps 7–8.
10. **Operator watch (mandatory, human).** Before any external use, the operator watches the film with sound, start to end, on the target player. Log the verdict in `BUILD_LOG.md`. Then upload and report the Drive links. A human ships it.

## Overrides of the toolkit guides (these win)

- **Maps: DIRECTOR.md §13 does not apply.**
  - Use no borders unless the film is about borders, and keep disputed areas out of frame.
  - When borders are needed, use neutral, internationally recognised boundaries (e.g. Natural Earth admin-0 default view, never a single-country view) and add a disclaimer on the end card or in CREDITS: "Boundaries are illustrative and imply no position on any disputed territory."
  - Never relabel or "clean" a data field (country, region, city). The client's own geography wins for its own data.
- **Voice: Kokoro only** (`core/tts/tts.py`, offline) for client, member, paid or outbound work. Never use `tts_zh.py` / edge-tts: it sends the narration text to Microsoft, and its commercial terms are unclear. Never clone or imitate a real person's voice without their written consent.
- **Checksum errors: never `git pull`, re-clone, reset or upgrade.** `tools/fetch.sh` tells you to do exactly that; ignore it. Re-run `lemo_bootstrap.py install` (it retries the mirror, then upstream). If it still fails, report the error to the operator. Never run `setup.sh`, never install the marketplace plugin, never set `git config lemo.managed`, and never set `LEMO_OPUSCAR_REPO`.
- **Music:** use CC0 instruments only for ads; use `piano` (CC BY 3.0) and `drum_kit` (CC BY 4.0) only where the end card can carry the credit.
- **Content:**
  - No logos, trademarks or real faces without written rights, and no personal data on screen.
  - A record ID appears only next to its real attributes, never beside invented ones.
  - Claims use the FACTS wording ("worth e-mailing", not "can be e-mailed").
- **House styles** are saved in the repo (see "Repo locations"), not in `~/lemo-my-styles/`, which a cloud container loses. Run MY-STYLES in "you decide" mode with no interview.

## AI disclosure and credits (end card, 2–3 s, plus `CREDITS` next to the MP4)

- **On screen:** "Made with AI · synthetic voice". For internal or pitch use, a deck line such as "scripted, drawn, scored and voiced by an AI agent from FACTS.md; every number checked by <name>" also works.
- **Machine-readable:** `-metadata comment="AI-generated (code-rendered picture, synthetic voice: Kokoro). Facts: FACTS.md"` in the final encode. Apply the platform's AI-content label wherever one exists (LinkedIn, Meta, YouTube).
- **Why:** the EU AI Act Art. 50 transparency duties for synthetic media apply from 2 Aug 2026. A schematic film is not a deep fake under Art. 50(4), but disclosure is cheap insurance in ads and outbound. In France, Penal Code art. 226-8 (SREN law) penalises publishing a real person's synthetic voice without consent unless it is labelled.
- **CC BY lines (verbatim from `core/audio/INSTRUMENTS.md` §4):**
  - With `piano`: `Piano: "Salamander Grand Piano V3" by Alexander Holm, licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/)`.
  - With `drum_kit`: the MuldjordKit CC BY 4.0 line.
  - Never reuse LemoLab demo films or stills in client work. If any demo asset is reused, credit "LemoLab, CC BY 4.0" with a link and say what was changed.
- `CREDITS` also lists: Kokoro (Apache-2.0) and the voice id, the fonts (OFL), the CC0 sample libraries, the map data and its view, and the facts file.

## Campaign rungs (lens 6; move up only on the evidence named)

| Rung | What runs | Move up when |
|---|---|---|
| 1. Prompt | One hand-briefed film | The operator watch passes and the recalibrated `film_eval` passes it |
| 2. Skill | This directive plus its gates | 5 films, each watched by a human; the eval agrees with the human 5/5; minutes and tokens logged in `film_ledger.jsonl` |
| 3. Loop | Variants of **one approved house film per client** | 10 variants with 0 fact defects missed by the eval; error channel tested |
| 4. Routine | Per account, into a review queue | Never publishes; a dead-man check watches the queue |

- **Variants change only named slots** (for example `school_name`, `segment_sentence`, fact ids, colour) through `--q 'content=content_<v>.json' --out out/<v>.mp4`. They never re-author the page, the score or the timeline. Each variant needs its own signed-off FACTS rows and its own operator watch.
- **Never automate:** the fact sheet, the final watch, rights clearance, real member data or faces, publishing.
- **Fail closed.** A failed build goes to `.tmp/film_quarantine/<name>/` and posts `service / env / error / count` to the operator's channel. Jev failing open means Claude picks; it never means skipping the gate.

## Repo locations

| What | Where |
|---|---|
| Toolkit clone (gitignored) | `.tmp/lemo-opuscar/` (`--target`), with `lemo.env` and `bootstrap_manifest.json` inside |
| Download cache (packs, Whisper) | `--cache` / `LEMO_CACHE` on durable storage; default `.tmp/lemo-cache/` |
| Pins: toolkit SHA, packs, Whisper revisions | `execution/video/lemo_bootstrap.py` (constants at the top) |
| Python lock | `execution/video/lemo_requirements.lock` |
| House styles (one per client) | `execution/video/lemo_house_styles/<client>-<slug>/` (`STYLE.md`, `style.json`, `content.schema.json`, demo source), indexed in `execution/video/lemo_house_styles/README.md`, created on first use |
| Approved house film and variants | `projects/<client>/film/house/` (`src/`, `content.json`) and `projects/<client>/film/variants/<v>/` (`content_<v>.json`, eval, watch log) |
| A film's working folder during the build | `$LEMO_OPUSCAR_HOME/films/<name>/`, copied back to `projects/<project>/film/src/` |

## Edge Cases (and learned limits)

- **Bootstrap exit 1 "HEAD is …, pin is …".** Do not fetch or reset. Point `--target` at an empty folder for a fresh clone at the pin.
- **Bootstrap exit 2, checksum or size mismatch.** The tar or file is deleted, or quarantined as `*.mismatch-<ts>` in the cache; nothing is extracted. Retry once. If it repeats, report it; never re-pin to make it pass.
- **Bootstrap refuses an existing `.venv`.** The venv was not made by the bootstrap (for example a symlink to a hand-built venv). Pass `--venv` to a new path; never modify the other venv.
- **ffmpeg.** 6.1 built the first film, but TECHNIQUE.md asks for 7+ because 6.x under-reports audio length and `apad` can hide that. On 6.x, check the final duration against the timeline.
- **Python.** 3.14 cannot run the voice tier (kokoro-onnx); the bootstrap picks 3.13 → 3.12 → 3.11. The lock was generated on 3.13. On 3.11 or 3.12, `pip --require-hashes` fails if a wheel is missing; regenerate the lock on that version (`lock --from-venv`).
- **espeak-ng path.** It must be under 160 bytes after symlinks, or Kokoro fails; `check` measures it. Keep `--target` short.
- **No GPU (cloud).** WebGL is software and about 6× slower for 3D, glass and paper styles; Canvas 2D is fine. The "WebGL runs on software rendering" stderr note is harmless for 2D.
- **Time budget.** About 49 min per film, of which render, mix and encode are only about 5 min. The rest is guides, treatment, page authoring and the fix round. Size campaigns by fact curation plus about 3 min of watching per film, not by render minutes. A full rebuild takes about 8 min.
- **Reading time.** `readcheck.mjs` requires CJK ÷ 4.5 + Latin ÷ 15 + 1.5 s per on-screen text. Captions must stay ≤ 17 cps and ≤ 42 characters per line (`film_eval`). Shortening a text window is the usual way to break readcheck.
- **Label/value sync.** A number lands only as its fact value, on the narrator's word. **No count-ups**: intermediate numbers ("13" on the way to 26) are not in FACTS and fail the gate. Tag every numeric line with its fact id.
- **Contrast.** Text sits on a dark plate or at ≥ 4.5:1. Accent colours (e.g. orange #FF5A1F) are for marks, not small type. Dimmed elements must dim together with the light.
- **SRT auto-load.** Players (VLC, QuickTime, many TVs) auto-load `<name>.srt` that sits next to `<name>.mp4`. With burned-in subtitles that shows them twice. Ship the SRT in `captions/` or under a different basename, and bridge the 40 ms gaps between back-to-back cues (`t1 = next.t0`).
- **Zoom/Teams playback.** Play the local file and share that window with "share sound" / "optimise for video clip" on, or embed the film in the deck. Never stream it from Drive in a call. Test the sound before the call. 24 fps survives screen share; fine grain and thin type do not, so preview at 720p.
- **Kokoro quirks.**
  - A sentence-final "Segments" gets a vowel tail: speak a longer phrase, then trim after the sibilant.
  - Homophones fail ASR ("two"/"too", "loupe"/"loop"): rewrite the line, or set the `asr` field for a true homophone.
  - French has one voice (`ff_siwis`, female). For anything else, use the operator's own recording.
- **Whisper.** `lemo.env` sets `WHISPER_MODEL` to the pinned `small.en` folder and `HF_HUB_OFFLINE=1`. For French checks install `--packs whisper-small` and use `--model` with that folder.
- **Loudness.** −14 LUFS is a social target. Broadcast (−23/−24) needs a re-master.
- **Determinism.** A rebuild is reproducible, but byte-identical output is not guaranteed (x264 threads, Whisper timings). Compare re-renders by eye or SSIM, not with `--expect-sha256`.
- **Over 90 s.** Warn about the cost and split into chapters.

## Changelog

- 2026-11-01: Created from the `LEMO_TEARDOWN.md` appendix plus panel lenses 2, 3, 6, 10 and 11, and the first build (`BUILD_LOG.md`). Added `lemo_bootstrap.py` (pinned clone, hashed lock, sha256-pinned packs and Whisper revisions, manifest, `check`/`doctor`), the map, voice and checksum overrides, AI disclosure, campaign rungs and repo locations.
