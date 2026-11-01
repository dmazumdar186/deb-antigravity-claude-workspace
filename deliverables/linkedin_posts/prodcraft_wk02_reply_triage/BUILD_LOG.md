# Build log: ProdCraft weekly notes wk 02 film ("32 inboxes, 800 sends. Who replied?")

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

- **F21 / F07 line numbers**: FACTS cites line 97 for the comment and 98–107 for the snippet; the file has the comment at line 98 and the OOO block at 99–107. Please update F21 to "lines 99–107" (what the card and the film show).
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
