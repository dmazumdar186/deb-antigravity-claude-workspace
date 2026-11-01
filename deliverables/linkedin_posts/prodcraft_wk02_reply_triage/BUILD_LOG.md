# Build log: ProdCraft weekly notes wk 02 film ("32 inboxes, 800 sends. Who replied?")

> **Current version: v2** (section at the end). The v1 sections below are history; v1 files are in `v1/`.

Short LinkedIn film that replaces the static wk 02 card. Built 2026-11-01, 13:38:44 → ~14:10 UTC, in a claude.ai cloud container. Status: **draft until the operator watch** (see the end).

## Provenance

| | |
|---|---|
| Generating model | standard tier (Jev-routed tier name; no model id recorded by policy) |
| Toolkit | lemo-opuscar **bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00**, clone at `/tmp/ext/lemo/lemo-opuscar`, never fetched, pulled or reset; `setup.sh` not run. `build.sh` refuses any other SHA. |
| `lemo_bootstrap.py check --target /tmp/ext/lemo/lemo-opuscar` | **check: OK** (exit 0). Two WARNs: venv not installed by the bootstrap (versions match the lock, hashes not enforced) and no `bootstrap_manifest.json` (the clone predates the bootstrap). |
| House style | **ProdCraft Notes**, new: `execution/video/lemo_house_styles/prodcraft-notes/` (`STYLE.md`, `style.json`, `CHANGES.md`, fonts + OFL, `styleframe.png`), indexed in `execution/video/lemo_house_styles/README.md`. Base swiss-motion, code grammar from living-screencast. The Jev style pick was skipped: the brief fixed the style. |
| Environment | Node 22.23.4 · Chrome headless shell 1243 (`PLAYWRIGHT_CHROME`), SwiftShader (2D canvas, irrelevant) · ffmpeg 6.1.1 · Python 3.13 venv `/tmp/ext/venv` · 4 vCPU |

## Result

| | |
|---|---|
| File | `prodcraft-wk02-replies.mp4`, 2,401,969 bytes (2.4 MB), sha256 `82338647cd8820c6…` |
| Video | 1080×1350 (4:5), 30 fps, 832 frames, H.264 **High**, yuv420p, BT.709 limited range, CRF 18 `-tune animation`, 671 kb/s |
| Audio | AAC-LC 48 kHz stereo 192 kb/s; **−16.0 LUFS** integrated, **true peak −1.6 dBTP**, LRA 3.6 LU |
| Duration | **27.733 s** (52 beats at 112.5 BPM = 13 bars; the last half beat dissolves into frame 0, so it loops on the bar line) |
| Poster | `poster.png`, frame 0 rendered losslessly from the page, 1080×1350 |
| Reading time | `readcheck.mjs`: **36/36 OK** (`src/out/readcheck.txt`); tightest: headline 3.60 s of 3.50 s, F05 5.04/4.77, code line 104 4.80/4.63, F15 4.28/3.97, F18 6.40/6.10 |
| Drawn text | `src/out/drawn_text.json`: 56 distinct strings over 832 frames. `grep -c fillText src/film.js` → **1** (line 47, inside `function drawText` at line 43): every canvas string goes through `drawText()`. Strings with digits: `02`, `wk 02`, `32 inboxes, 800`, `800 sends a day`, `30–60`, `: 0.99,`, `: 0.0,`, the three result lines, and `CC0` in the credit (structure, not a figure). |
| Verbatim code (F21) | `src/tools/code.py` reads `reply_classifier.py` lines 99–107 at build time, strips exactly 4 spaces, asserts that re-adding them reproduces the source bytes (sha256 of the 9 source lines `51b50c11…`) and that no `95`/`%` appears; the page asserts its syntax tokenizer re-joins to the same lines. |
| Contrast | measured on the encoded film (`src/out/contrast.txt`): every text ≥ 4.5:1; lowest code blue on the gold highlight 5.87:1 and the gold "02" 5.56:1; headline 15.8:1. |
| Black frames / freezes / silence | none (`blackdetect` in the build; eval: 0 s black, 0 s frozen, 0 s silence) |
| Eval | `EVAL_REPORT.md` / `.json`: 22 PASS, 2 WARN, 2 FAIL; both FAILs are harness false positives for a film with no narration and no captions (below). **No content FAIL.** |

## Stage timings (measured)

| Stage | Wall clock |
|---|---|
| Reading (directive, FACTS, BUILD_LOG of the previous film, AGENTS/DIRECTOR/TECHNIQUE, swiss-motion + living-screencast STYLE, film_eval) and card sampling | 13:38:44 → ~13:46 (≈ 7 min) |
| Fonts (`tools/fonts.py`: 9 subsets + 3 OFL texts from Google Fonts) | ≈ 2 s |
| Page authoring (timeline, film.js, look stills, headline fit against the card) | ~13:46 → ~13:53 |
| Readcheck | 2.0 s |
| Score + mix (`mix.py`) | 5.8 s |
| Frame render (`video.mjs`, 4 workers, 832 frames) | 22.7 s first, 20 s in the full build |
| Master + encode (`master.sh`, two-pass loudnorm) | 13.8 s |
| **Full `build.sh`** (code, events, readcheck, render, mix, master, stems, poster, drawn-text manifest, SCRIPT.md, contact sheet) | **50.9 s** (reproduction run from a copy of `src/` in `/tmp/repro2`: exit 0 in 50.9 s; same MP4 size, SSIM 1.000, identical `poster.png`, `SCRIPT.md` and `drawn_text.json`) |
| Review: 0.25 s frame sheets across every transition (3 + 1 sheets), fixes, re-render | ~13:55 → ~14:02 |
| film_eval.py | 2.4 s per run (4 runs) |
| **Total** | 13:38:44 → ~14:10 UTC (≈ 31 min) |

## Defaults chosen (nobody to ask)

- **Duration 27.733 s** instead of a round number: the reading floor (chars ÷ 15 + 1.5 s per text) of the brief's texts sums to ≈ 27.5 s even with overlaps, and the loop needs a whole number of bars. 112.5 BPM makes every beat 16 frames at 30 fps.
- **Poster**: the wk 02 card's header, footer and headline at the card's measured size and place (Newsreader display 500, 93 px, tracking −2.86 px; ink-pixel count within 2 % of the card), plus an 8×4 grid of 32 envelope tiles (F01) where the card has its code panel. The ProdCraft mark is tinted to ink, as on the card.
- **Replies (illustrative, labelled once)**: "Tell me more." · "I'm out of the office until Monday." · "Please unsubscribe me." · "What does pricing look like?" · "Automatic reply: on vacation." · "Can we jump on a call next week?" · "Not interested, thanks." (7 cards; OOO and stop wording uses F11/F12 pattern examples, the hot card uses the F13 wording).
- **Stop and hot rules**: F21's snippet contains only the OOO rule, so no on-screen line can light for them. Their cards get the gold bar on the card and the pattern-list name (`_STOP_PATTERNS`, `_HOT_PATTERNS`, F12/F13) next to the result. No extra code was shown (the hot block contains a phone-number-shaped comment).
- **Judgement**: the three uncaught cards get an ink bar and "✓ CRM updated" (F16) under the heading "The rest: to the right person, with context." (F15). No class, model name or confidence for them.
- **F19 wording**: the full FACTS phrase "The target was never 800 sends a day for its own sake." (the brief's shorter "…800 sends a day." drops "for its own sake", which changes the claim). F18: "It was 30–60 positive conversations a month, with booked calls tracked in the CRM."
- **Music**: original score, CC0 only (VCSL, VSCO 2 CE): marimba ostinato, vibraphone, glockenspiel on each rule, contrabass pizzicato, woodblock/claves ticks, shaker. No piano or drum kit, so **no CC BY line is required**; the end card says "music: original, CC0 samples (Versilian Studios)". Two silences: a half-beat break before the panel lands (beat 15) and a near-silence before the reframe (beats 31–32.5). Low band −4.5 dB vs the rest.
- **End card**: header, footer, the two credit lines (`Made in code with lemo-opuscar (MIT)` / `music: original, CC0 samples (Versilian Studios)`) and the 32 empty tiles re-built on the grid; 47 → 52 beats = 2.67 s, the last 0.27 s dissolving into frame 0 (seamless loop).
- **AI marking**: no voice, so the directive's "synthetic voice" line does not apply; the MP4 carries `comment="Code-rendered picture and score made with an AI coding agent (lemo-opuscar toolkit); no synthetic voice, no generated footage. Facts: FACTS.md"`. Applying LinkedIn's AI-content label at posting is the operator's call.
- **Stems** shipped as 96 kb/s AAC (`src/stems/`, 588 KB total).

## Deviations (and why)

- **F21 line range.** FACTS says lines 98–107, but in the current file line 98 is the comment `# Deterministic layer FIRST — catches ~95% …`, which the hard rules forbid on screen. The wk 02 card itself shows lines 99–107; the film shows the same 9 lines. Listed under "facts requested".
- **Swiss-motion's "never dissolves"** is broken once, for the requested loop dissolve.
- **Readcheck for the code** counts each code line as its own text (≤ 4.63 s each, panel on screen 4.80 s); the whole 9-line snippet as one block would need 18 s. The card's highlighted line and the results are what the viewer must read; the rest is recognisable code.
- **Small chrome** (14–15 px mono header/footer/labels, 18–25 px code and cards) follows the card's own scale → `drawn_text_size` WARN, accepted for series fidelity.
- **ffmpeg 6.1** (TECHNIQUE asks for 7+): final duration checked against the timeline (27.733 s video, 27.714 s audio).
- **Colour pipeline**: the toolkit's intermediate is limited-range BT.601; the master now converts with ffmpeg's `colorspace` filter. The first master used `scale=in_range=pc`, which darkened the paper to #DADAD3 in the file; caught by pixel sampling, fixed, re-mastered (paper now #EEECE7 vs the card's #EFEDE8).

## Fix round (from my own 0.25 s review and the checks)

1. Headline was 112 px and lighter than the card → fitted to the card by bounding box and ink count (93 px, weight 500, −2.86 px tracking, baselines 231/327); wordmark 26.4 px; logo tinted to ink.
2. 3.5 s near-static stretch under the F05 quote → the quote's gold rule now draws itself (linear) while it holds, and the ribbon lights step on sixteenths.
3. Re-flow: rows moving up were drawn under rows moving down → caught cards are drawn on top.
4. End card was an empty page for 2.3 s → the 32 tiles wipe back in, so the loop dissolve only brings the headline back.
5. D-layout ledger sat too high, leaving the lower half empty → re-spaced (row pitch 86).
6. Low band +0.8 dB vs rest → −4.5 dB (bass gain, thump pitch).
7. Paper colour shift in the master (see Deviations).
8. SCRIPT.md title began with "SCRIPT", which film_eval reads as a narration section (every on-screen line became "narration": speech_rate 411 wpm, quote FAILs on code keys) → retitled; quote_fidelity now PASS.
9. `poster.mjs` / `drawn_text.mjs` imported the toolkit by a relative path and failed outside the clone (caught by the reproduction run) → they import `$LIB/core/render/page.mjs`.

## Eval (film_eval.py 2.0.0)

Command (from the workspace root):
```
python3 execution/video/film_eval.py --video deliverables/linkedin_posts/prodcraft_wk02_reply_triage/prodcraft-wk02-replies.mp4 \
  --srt deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/out/no_captions.srt \
  --script deliverables/linkedin_posts/prodcraft_wk02_reply_triage/SCRIPT.md --facts deliverables/linkedin_posts/prodcraft_wk02_reply_triage/FACTS.md \
  --drawn deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/out/drawn_text.json \
  --out deliverables/linkedin_posts/prodcraft_wk02_reply_triage/EVAL_REPORT.json --md deliverables/linkedin_posts/prodcraft_wk02_reply_triage/EVAL_REPORT.md
```
`--srt` is required by the parser (`Path(args.srt)`), so an **empty** `src/out/no_captions.srt` was passed, as the brief allows.

Harness report: OVERALL FAIL (exit 1) from these two, both **harness false positives** (film_eval.py not edited):
- `captions_parsed` FAIL ("no cues parsed from SRT"): the film has no voice and no captions by design (FACTS hard rule: no AI voice; brief: silent-safe on-screen type). The SRT is empty on purpose.
- `speech_rate` FAIL (2.6 wpm): the only "narration" is the required placeholder line "(none)", counted as 1 word over 22.7 s.

WARNs, accepted: `resolution` 1080×1350 (the harness wants ≥ 1280×720 landscape; 4:5 at 1080 wide is the brief's format) and `drawn_text_size` 14 px (the card's chrome scale, see Deviations).

Everything else PASS: size, duration, fps, codec, audio, bitrate, loudness −16.0, TP −1.6, LRA 3.6, black/frozen/silence 0 s, number fidelity (on-screen 13/13 in SCRIPT, drawn 13/13), tag coverage 10/10, tag validity, tag consistency, quote fidelity (F05 exact; code keys INFO), PII 0 hits.

## Facts requested

- ~~**F21 / F07 line numbers**~~: resolved in FACTS.md before v2 (F07 → line 98, F21 → lines 99–107).
- **Sign-off line**: FACTS.md has no `Signed off: <name>, <date>` line; per the directive the film stays a draft until it is added.

## Deliverables

- `prodcraft-wk02-replies.mp4`, `poster.png`, `SCRIPT.md` (header block; "## On-screen text" with 36 time-coded rows and fact ids; "## Narration" = "(none)"; staging notes), `contact_sheet.jpg` (8 frames, one per beat), `EVAL_REPORT.json` / `.md`, this log.
- `src/`: `index.html`, `film.js`, `timeline.js`, `mix.py`, `build.sh`, `events.json`, `logo-prodcraft.png`, `CREDITS`, `fonts/` (9 woff2 + 3 OFL texts), `stems/` (music, ticks, foley; AAC), `tools/` (fonts, code, master, drawn_text, poster, script_md, contact_sheet), `out/drawn_text.json`, `out/code.json`, `out/readcheck.txt`, `out/contrast.txt`, `out/no_captions.srt` (empty, eval only).
- House style: `execution/video/lemo_house_styles/prodcraft-notes/` + `execution/video/lemo_house_styles/README.md`.
- Not committed (as instructed).

## Reproduce

```sh
# toolkit at the pin (never setup.sh, never git pull); deps as in projects/alumnforce_case/film/BUILD_LOG.md:
#   venv /tmp/ext/venv symlinked as $LIB/.venv, npm ci, packs vcsl + vsco2ce (sh tools/fetch.sh instruments <lib>)
export LIB=/tmp/ext/lemo/lemo-opuscar
export PLAYWRIGHT_CHROME=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
export WS=/home/user/deb-antigravity-claude-workspace          # for reply_classifier.py (F21)
mkdir -p /tmp/wk02 && cp -r "$WS/deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src" /tmp/wk02/src
sh /tmp/wk02/src/build.sh       # → /tmp/wk02/src/{prodcraft-wk02-replies.mp4, poster.png, SCRIPT.md, contact_sheet.jpg, out/drawn_text.json}
# then the eval command above, pointed at the rebuilt files
```
Re-renders are reproducible but not guaranteed byte-identical (x264 threads); the reproduction run matched the delivered film at SSIM 1.000 with the same byte size.

Operator watch: _pending_ (watch with sound and muted, start to end, on LinkedIn mobile and desktop before posting).

---

# v2 (round 2), 2026-11-01, 14:13:14 → ~14:38 UTC

Brief: the coordinator's round-2 list (fixes 1–10), then VISUAL_QA.md items A–F. Inputs: panel lenses 2, 3, 4, 8, 9, 10, 11 and 12, VISUAL_QA.md, and the updated FACTS.md (F07 → line 98, F21 → lines 99–107; not edited). Generating model: standard tier. Toolkit: lemo-opuscar bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00 (pinned; never pulled, setup.sh never run). v1 was moved to `v1/` first: `prodcraft-wk02-replies_v1.mp4`, `v1_poster.png`, `v1_contact_sheet.jpg`, `v1_SCRIPT.md`, `v1_EVAL_REPORT.*`, and the v1 source in `v1/src/`.

## Result (v2)

| | |
|---|---|
| File | `prodcraft-wk02-replies.mp4`, 3,161,627 bytes (3.2 MB) |
| Video | 1080×1350, 30 fps, 832 frames, H.264 **High**, yuv420p, BT.709 limited, CRF 14 with `-maxrate 8M -bufsize 16M`, `-tune animation`, `+faststart`; 706 kb/s video (flat graphics compress well at CRF 14) |
| Audio | AAC-LC 48 kHz 192 kb/s; **−16.0 LUFS**, **TP −1.7 dBTP**, LRA 3.7 LU |
| Duration | 27.733 s (52 beats); seamless loop |
| Poster | `poster.png` = frame 0 rendered losslessly from the page (re-exported) |
| film_eval 2.1.0 `--profile linkedin_4x5` (no `--srt`) | **OVERALL WARN, 0 FAIL**: 21 PASS, 8 SKIPPED (no narration, no captions), 2 WARN (below) |
| Readcheck | 36/36 OK (`src/out/readcheck.txt`) |
| Contrast | every text ≥ 4.5:1 on the encoded film (`src/out/contrast.txt`); lowest is the blue code string on the gold highlight at 5.36:1 |
| Motion onset | frame 0 is the poster. Pixels changed by more than 40 levels vs frame 0, frames 0–11: `0, 406, 333, 422, 292, 594, 4693, 7029, 7215, …`. Frames 1–5 are encoder ringing around type; the first envelope fill is visible from **frame 6 (0.20 s)**, full at frame 8 (0.27 s). |
| `drawText()` | `grep -c fillText src/film.js` = **1** (line 56, inside `function drawText` at line 49). It now logs a run only when part of its box lies inside the current clip and alpha > 0, with a `vis` fraction. The manifest has 53 strings; `_STOP_PATTERNS` and `_HOT_PATTERNS` are logged because they are now on screen. |

### sha256 (from `src/out/hashes.txt`, written by build.sh)

| Artifact | sha256 |
|---|---|
| `prodcraft-wk02-replies.mp4` | `ecf6d307aff0039957ec70cdd8a32424c13971196a640bcba6f8beb507a01524` |
| frame @ 0 s (rgb24, BT.709 limited → full) | `ace51356970ea197ec87507296b35723f803474b1736c00edc3a0301eb7296e6` |
| frame @ 9.6 s | `72dcad2f40f1a8232dc957cface18c67e8ec9d708822157c85e1ff81394980a4` |
| frame @ 21.0 s | `0c74b2efeac0c9334f14bd6dc63549e2ccc2e6dc660d7e4edbc6deb90f549aed` |
| audio (decoded s16le) | `7d00a5d395d78d8ac1732fe9be0d8dbefff95975811fa971f34f05ec60f44915` |
| `poster.png` | `7730a4c09f35d28e22fc8b159af4fbe183e7c543947ac641ef4eaa9d8e7e06b4` |

Two consecutive builds of the same source produced identical hashes for the three frames, the decoded audio and the poster. The MP4 container hash differs (x264 threading), as the directive expects.

## Fix list → what changed

| # | Required | Done |
|---|---|---|
| 1 | Motion by 0.3 s | Eight poster envelopes fill gold one after another, every half beat from 0.13 s (first fill complete at 0.27 s), each with a soft woodblock tick. Frame 0 is unchanged and remains the poster and the loop seam. |
| 2 | Provenance | The code tab reads **"from my own build · same rules-first pattern · verbatim"** (31 px). CREDITS says the code is the operator's own build, not the client system. |
| 3 | Confidence wording | OOO: `auto_reply_or_OOO · 0.99 (set by the rule)` / `€0.00 · no model called`. Unsubscribe: `negative · stop rule · 0.99 · €0.00`, with no "sequence stopped". Hot: `hot · meeting request · to a person`; 0.90 is gone. |
| 4 | Rules are not infallible | Before routing, the heading flips to **"Rules catch the obvious. Anything else goes to a person."** (F15/F17 wording, no numbers). |
| 5 | One CRM tick | One group row, "to the right person, with context", carries one shared "✓ CRM updated". "Not interested, thanks." sits in that group (it matches no stop pattern). |
| 6 | Mobile size | Card text 32 px, results and pattern tags 31 px, label and tab 31 px, code 30 px (see the pt table). Header and footer stay at card size. |
| 7 / F | Sort overlap | Cards never overlap. A caught card collapses where it is (a quarter beat), the column closes, and it re-opens at the top of the column (half a beat); only then do its tag and result stamp in. Checked at 0.1 s through every sort: 0 frames with card-on-card. |
| 8 | Export | `tools/master.sh`: libx264 High, CRF 14, `-maxrate 8M -bufsize 16M`, 30 fps, yuv420p, `+faststart`, ≤ 30 MB enforced. `poster.png` re-exported at frame 0. |
| 9 | Reproducibility | Logo copied to `src/assets/logo-prodcraft.png`. Toolkit path comes from `LEMO_OPUSCAR_HOME`, with `LIB` as fallback (`build.sh`, `tools/page.mjs`, `mix.py`). `build.sh` stages everything in `src/out/stage.*`, runs the black-frame check and `film_eval` there (any FAIL stops it), writes `src/out/hashes.txt`, then moves the set into the deliverable folder. Nothing in `src/` outside `src/out/` is written; build scratch (`out/video.mp4`, `out/mix.wav`, WAV stems) is deleted at the end, and the AAC stems (620 KB) stay in `src/out/stems/`. |
| 10 | Series template | Every week-specific string and number is in `src/content.json`. Tokens are in `src/house.js` (also in `execution/video/lemo_house_styles/prodcraft-notes/house.js`). `film.js`, `mix.py`, `script_md.mjs`, `contact_sheet.py`, `code.py` and `master.sh` read them. The house STYLE.md has token tables (frame/grid/safe areas, type scale in px and pt, colour, chrome) and a §11 "Making the next week (wk 03)". |
| A | Phone legibility, fewer cards | 5 cards (the five reply kinds of F04), larger, one sort at a time. Code is 30 px with a 1-space-per-level re-indent so the longest verbatim line fits; `tools/code.py` proves the re-indent is reversible and that the tokens are unchanged. |
| B | Clip bug + honest manifest | Tags draw in their own wipe outside the result clip. `drawText()` tracks the clip stack (`pushClip`/`popClip`) and skips invisible runs. |
| C | Highlight matches the rule | The gold bar marks OOO lines 99 and 102 only while the OOO rule fires. It is removed when the stop rule fires. Each caught card shows its own pattern list in gold: `_OOO_PATTERNS`, `_STOP_PATTERNS`, `_HOT_PATTERNS`. |
| D | Logo | The mark is tone-mapped by darkness (v = min(rgb) × (1 − 2·saturation), levels 0.3–0.6, alpha kept), not flooded through alpha. Mean absolute difference vs the card's logo region: v1 31.6 → **v2 15.9**. |
| E | Headline clipped the header | Every clip-reveal slot is clamped at y ≥ 145 (the header's safe line). Exits no longer touch the header. |
| (QA D7) | Quote vs cards | F05 is fully on screen at 2.53 s; the cards start at 3.2 s. |
| (QA D9) | Third typeface | Geist dropped; cards are set in Newsreader text. |
| (QA D10) | 1 px sliver | Stamp clips start at width 0. |

Other changes found in my own 0.1 s review:
- The two headings no longer share the slot during the flip: the old one leaves in a quarter beat, then the new one rises.
- The code panel draws above the column it slides over.
- The routed-group hold got a gold reading rule, so no static hold exceeds 3 s.
- The routed-group layout was moved down for balance.
- Label and tab went to 31 px; the tab's tracking was tightened so "verbatim" clears the panel edge.

## Effective size on a phone (px × 390 / 1080), from `src/out/drawn_text.json`

| Text class | px | ≈ pt | Floor (≈ 11 pt) |
|---|---|---|---|
| poster headline | 93 | 33.6 | ✓ |
| reframe statement | 84 | 30.3 | ✓ |
| 30–60 | 250 | 90.3 | ✓ |
| heading "Rules first." | 64 | 23.1 | ✓ |
| quote (F05) | 46 | 16.6 | ✓ |
| F18 lines / "It was" | 44 / 40 | 15.9 / 14.4 | ✓ |
| limits heading | 34 | 12.3 | ✓ |
| reply cards, group label | 32 | 11.6 | ✓ |
| results, pattern tags, CRM | 31 | 11.2 | ✓ |
| "illustrative replies", code tab | 31 | 11.2 | ✓ |
| code lines | 30 | 10.8 | 0.2 pt under the harness's 11 pt proxy; at 30 px the longest verbatim line (53 chars) fills the 992 px panel |
| wordmark "ProdCraft" | 26.4 | 9.5 | card scale (accepted) |
| "wk 02", footer, "02" | 14 | 5.1 | card scale (accepted) |
| end credits | 18 | 6.5 | small by design (directive: subtle) |

The two eval WARNs come only from this table's last four rows: `drawn_text_size` (14 px chrome, 18 px credits) and `drawn_text_mobile` (chrome, credits, and the 30 px code lines at 10.8 pt).

## Frame review (mine)

At 0.1 s steps:
- 0–0.6 s
- 3.3–4.6 s (headline exit, pour)
- 7.8–14.6 s (panel entry, all three sorts, the heading flip, panel exit, routing)
- 13.6–17.1 s (hold, reading rule, knife)
- 24.9–25.5 s (exit, end-card grid)
- 27.3–27.73 s (loop)

Results: no card overlap, no text through the header, no ghosting. Exits leave 1–2-frame slices of glyphs, by design (clip wipes). The tab no longer clips.

## Stage timings (v2, measured)

| Stage | Wall clock |
|---|---|
| Reading panel lenses 9, 3, 4, 8, 10, 2, 11, 12 and FACTS; moving v1 | 14:13:14 → ~14:16 |
| VISUAL_QA.md + logo study (three tone-map fits against the card) | ~14:16 → ~14:20 |
| content.json, house.js, film.js rewrite, tools, build.sh | ~14:20 → ~14:26 |
| Build 1 (full `build.sh`, incl. eval and hashes) | 55.1 s |
| 0.1 s review → fixes → build 2 | 55.9 s |
| Contrast, motion onset, pt table, logo diff | ~2 min |
| House style STYLE.md / style.json / house.js / README | ~14:28 → ~14:30 |
| Builds 3 and 4 (label and tab 31 px, tab tracking) | 54.7 s, 53.2 s |
| Build 5 (final `build.sh` with scratch cleanup, end to end) | 58.8 s (render 21 s of it) |
| film_eval alone | 2.2 s |
| **Total v2** | **14:13:14 → ~14:38 ≈ 25 min** |

## Facts requested (v2)

- **F10**: the hot result (0.90) is returned only in dry-run (reply_classifier.py line 124); F10 doesn't say so. The film no longer shows 0.90.
- **Sign-off line**: FACTS.md still has no `Signed off:` line, so the film remains a draft until one is added and the operator has watched it.

## Git notes

`*.png` is ignored repo-wide (`.gitignore:27`). Force-add these PNGs (or add `!` rules):
- `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/assets/logo-prodcraft.png` (needed to build);
- `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/poster.png`;
- `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/ref/wk02_card.png`;
- `execution/video/lemo_house_styles/prodcraft-notes/styleframe.png`.

Not committed (as instructed).

## Reproduce (v2)

```sh
export LEMO_OPUSCAR_HOME=/tmp/ext/lemo/lemo-opuscar        # or: . .tmp/lemo-opuscar/lemo.env after lemo_bootstrap.py install
export PLAYWRIGHT_CHROME=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
cd /home/user/deb-antigravity-claude-workspace
sh deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/build.sh
# → mp4, poster.png, SCRIPT.md, contact_sheet.jpg, EVAL_REPORT.* in the deliverable folder; src/out/{drawn_text.json, hashes.txt, readcheck.txt, stems/}
```
It needs the vcsl and vsco2ce sample packs in the clone, and the fonts in `src/fonts/` (fetch once with `python3 -I src/tools/fonts.py src` if they are missing; the build never fetches).

Operator watch: _pending_.
