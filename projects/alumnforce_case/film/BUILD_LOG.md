# Trusted Segments — build log

Evidence film (cold open, 76.25 s) for the AlumnForce Senior PM case study. Built 2026-11-01, 10:25:56 → 11:15 UTC, in a claude.ai cloud container.
All timings below were measured with `date +%s.%N` around each command or with the tools' own timers. "Elapsed" timestamps are wall-clock UTC.

## Result

| | |
|---|---|
| File | `trusted-segments.mp4`, 23,178,599 bytes (22.1 MiB), 1920×1080, 24 fps, H.264 High yuv420p BT.709 limited range, AAC-LC 48 kHz stereo 256 kb/s |
| Duration | 76.25 s (1,830 frames) |
| Loudness | −14.0 LUFS integrated, true peak −1.2 dBTP, LRA 3.2 LU (`ffmpeg ebur128`) |
| Black frames | none (`blackdetect d=0.1 pix_th=0.05`) |
| Speech check, per line | `asr_check.py`, Whisper `small.en`: **16/16 lines pass, 0 mismatches** (one `asr` override, below) |
| Speech check, final mix | `tools/final_asr.py` on the delivered mp4 (music and foley included): 159 words expected, 160 heard, match ratio 0.9906. The two differences: "normalise" written "normalize" (spelling only), and an extra "as" heard in the foley between L09 and L10 (the develop-front whoosh). Every number is heard correctly. |
| Reading time | `readcheck.mjs`: 25/25 on-screen texts long enough |
| Cue grid | `tools/cuecheck.mjs`: 21 key actions + 16 voice starts on the 72 BPM half-beat grid, worst offset 0.03 ms (the hook start and the two silences are off-grid by design) |
| Style | Archive Light Table (kept; see "Style decision") |
| Voice | Kokoro `bf_emma` (British English, female), speed 0.9 (0.86 → 0.9 for the last line), offline. No edge-tts, no text sent off the machine |

## Versions

- Toolkit: `lemo-opuscar` at commit **bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00** ("Gallery and README: new films for eight styles"), pinned; never fetched, pulled or reset. `git status` in the clone shows only the `.venv` symlink (untracked) besides the ignored `films/` and `node_modules/`.
- Node v22.23.4 · npm 10.9.9 · playwright-core 1.63.0 (repo dependency) driving Chrome headless shell 153.0.8010.12 at `/opt/pw-browsers/chromium_headless_shell-1243/…` (via `PLAYWRIGHT_CHROME`), software GL (SwiftShader; the film is Canvas 2D, so it does not matter)
- ffmpeg 6.1.1-3ubuntu5 (the guide asks for 7+; 6.1 worked, `mux.sh` did not reject the audio)
- Python 3.13.18 venv at `/tmp/ext/venv`: numpy 2.5.4, scipy 1.18.1, soundfile 0.14.0, soxr, pillow, fonttools, kokoro-onnx 0.6.1, onnxruntime 1.31.1, edge-tts 7.3.1 (installed, unused), faster-whisper 1.2.1, ctranslate2 4.8.4, av 18.1.0
- Kokoro v1.0 ONNX model + voices (toolkit `voice` pack); Whisper `small.en` (Hugging Face, first use)
- Sample packs: salamander, vsco2ce, vcsl (toolkit release `assets`, sha256-checked by `fetch.sh`)
- Linux 6.18, 4 vCPU, 15 GB RAM

## Safety review of the toolkit's install scripts (before running anything)

- `plugin/skills/lemo-opuscar/scripts/setup.sh`: **not run.** It would (a) `git fetch` + `reset --hard` the clone to upstream `main` when `lemo.managed=true` (unset in this clone, but the coordinator asked to keep the clone pinned at bebbbe1 anyway), (b) clone into `~/lemo-opuscar` when not run inside a clone (outside the repo), (c) `npm install` (writes the npm cache in `~/.npm`), (d) `node playwright-core/cli.js install chromium-headless-shell`, which downloads a browser into `~/.cache/ms-playwright` (outside the repo; forbidden by the brief), (e) create `.venv` inside the repo and pip-install (pip cache in `~/.cache/pip`). No `curl | sh` anywhere. I reproduced its steps by hand (below) without (a), (b) and (d).
- `tools/fetch.sh`: downloads release tarballs from `github.com/lemomo-ai/lemo-opuscar/releases/download/assets/…` with `curl -L --fail` to a file (not piped to a shell), verifies sha256 against `tools/assets.json`, extracts with Python's `tarfile` `filter='data'` (rejects paths leaving the repo), writes only inside the repo (`.release/`, `core/tts/`, `core/audio/instruments/`). Ran as is.

## Stage timings (measured)

| Stage | Command(s) | Wall clock |
|---|---|---|
| Setup: venv + pip (core + voice tiers) | `python3 -m venv /tmp/ext/venv && pip install -r requirements.txt -r requirements-voice.txt` | 29.2 s |
| Setup: npm | `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install` (then `git checkout -- package.json package-lock.json`) | 2.1 s |
| Setup: Kokoro model | `sh tools/fetch.sh voice` (354 MB) | 4.9 s |
| Setup: sample packs | `fetch.sh instruments salamander` / `vcsl` / `vsco2ce` | 3.0 s / 3.8 s / 5.7 s |
| Setup: fonts | `python -I tools/fonts.py <film>` (IBM Plex Mono/Sans/Serif from Google Fonts + OFL texts) | 2.8 s |
| **Setup total** | | **51.5 s** (+ Whisper `small.en` download inside the first speech check) |
| Reading guides + treatment | AGENTS → DIRECTOR → TECHNIQUE → STYLE.md, `TREATMENT.md` written before opening DEMO.md | 10:25:56 → 10:29:05 (189 s) |
| TTS, first pass | `tts.py voice/lines.json voice/out` (16 lines, 155 words) | 20.2 s |
| Speech check, first pass | `asr_check.py … --lang en` (`small.en`, incl. model download) | 40.6 s → 6 mismatches (fixes below) |
| TTS, final | `tts.py` + `tools/trim_voice.py` + `asr_check.py` | 54.3 s (earlier iteration 61.0 s) |
| Page authoring, first pass | `timeline.js`, `tools/export.mjs`, `index.html`, `film.js` (≈ 430 lines, Canvas 2D) until the first full render | 10:36:41 → 10:47:46 (665 s) |
| Page authoring, fix round | review of two contact sheets + strips, fixes, re-checks | 10:50:00 → 10:55:26 (≈ 326 s), plus one late fix 11:04–11:05 |
| Frame render | `node core/render/video.mjs <film> --fps 24 --workers 4` | 127.1 s (14.4 fps) · 116.2 s (15.8 fps) · final 123.6 s (14.8 fps) for 1,830 frames |
| Music (score) | sampler render + room reverb inside `mix.py` | 3.3–3.7 s |
| Foley, voice, beds | inside `mix.py` | 3.0 s |
| Mix / master stems | inside `mix.py` | 2.1 s (whole `mix.py` 8.9–11.3 s) |
| Mux + loudness | `LEMO_COLOR=bt709 sh core/render/mux.sh video.mp4 mix.wav master.mp4 24 1` (two-pass loudnorm, grain 1, x264 CRF 19 slow) | 99.0 s · 127.1 s · final 107.2 s |
| Encode to size | `ffmpeg … -crf 26 -tune grain …` | CRF 24: 69.0 s → 28.4 MB (too big); CRF 26: 62.4 / 76.6 / final 70.2 s → 23.2 MB |
| Checks | `readcheck.mjs` 62.8 s · `final_asr.py` 15.1 s · `ebur128` + `blackdetect` ≈ 10 s | |
| **Total wall clock** | first command → deliverables copied | **10:25:56 → 11:15:07 = 2,951 s (49 min 11 s)** |

## Commands that mattered (in order)

```sh
LIB=/tmp/ext/lemo/lemo-opuscar; F=$LIB/films/trusted-segments; cd $LIB
python3 -m venv /tmp/ext/venv && /tmp/ext/venv/bin/pip install -r requirements.txt -r requirements-voice.txt
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund && git checkout -q -- package.json package-lock.json
ln -sfn /tmp/ext/venv .venv                      # the tools call $LIB/.venv/bin/python
sh tools/fetch.sh voice; for l in salamander vcsl vsco2ce; do sh tools/fetch.sh instruments $l; done
export PLAYWRIGHT_CHROME=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
.venv/bin/python -I $F/tools/fonts.py $F
.venv/bin/python core/tts/tts.py $F/voice/lines.json $F/voice/out
WHISPER_MODEL=small.en .venv/bin/python -I $F/tools/trim_voice.py $F/voice/lines.json $F/voice/out
WHISPER_MODEL=small.en .venv/bin/python core/tts/asr_check.py $F/voice/lines.json $F/voice/out --lang en
node $F/tools/export.mjs $F && node $F/tools/cuecheck.mjs $F
node core/render/still.mjs $F 2 7 11 14 18 22 27 32.6 35 40 47 55 61 63.2 67 74 --out $F/stills   # look stills
node core/render/readcheck.mjs $F
node core/render/video.mjs $F --fps 24 --workers 4 --out $F/out/video.mp4
.venv/bin/python $F/mix.py
LEMO_COLOR=bt709 sh core/render/mux.sh $F/out/video.mp4 $F/out/mix.wav $F/out/master.mp4 24 1
ffmpeg -y -i $F/out/master.mp4 -c:v libx264 -preset slow -crf 26 -tune grain -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a copy -movflags +faststart $F/trusted-segments.mp4
.venv/bin/python core/render/srt.py $F/out/cues_srt.json $F/trusted-segments.srt
LIB=$LIB .venv/bin/python -I $F/tools/final_asr.py $F/trusted-segments.mp4 $F/voice/lines.json
node $F/tools/script_md.mjs $F > $F/SCRIPT.md
.venv/bin/python core/render/sheet.py $F/contact_sheet.jpg $F/out/cs/beat_{7.0,15.5,29.0,36.0,61.5,74.0}.jpg --cols 3 --w 640
```

## Style decision

Archive Light Table was kept. 525 cards render without trouble in Canvas 2D (≈ 15 fps capture with 4 workers) and read well at 1080p because the style's own grammar solves the density problem: at table scale the cards are texture (their text is drawn as bars), and anything that must be read is either magnified under the loupe (≥ 30 px glyphs) or lifted out onto a dark caption plate (28–110 px). No switch to dataviz or visual-investigation was needed.

## What failed and how it was fixed

1. **ASR, first pass: 6 mismatches.** "loupe" heard as "loop" (a true homophone: `asr` field set, accepted); "…as delivered: two" heard as "too" (line rewritten: "…two members."); "Normalise" (my wrong `asr` override, removed); "Sixty-eight percent" written "68%" (`asr` field with the expected transcription, as `asr_check.py` documents); "sort by trust" heard as "sought" (rewritten "split by trust"); "Trusted Segments." heard as "A trusted segment, see?".
2. **Kokoro adds a vowel tail after a sentence-final "Segments".** Five phrasings tested (all failed: "Segmenty", "Segmentie"…); "Trusted Segments, the product." passes. `tools/trim_voice.py` speaks that and cuts after "Segments". The first cut used Whisper's word end and clipped the final /ts/ (the final-mix check heard "Trusted segment"); fixed by finding the sibilant burst above 4 kHz and cutting after it (cut at 1.05 s instead of 0.94 s). Final-mix check now hears "Trusted segments".
3. **`timeline.js` overlap**: L03 placed before L02 ended; `export.mjs` caught it; beats shifted (L03 → beat 10.5 and onward).
4. **`readcheck.mjs` failures**: "the same signal" (1.40 s of 2.37 s) and "6 can be e-mailed today" (2.40 of 2.77 s): the quote and the switch-off moved one and a half / half a beat later. Later the "Schematic" tag failed (3.96 of 4.70 s) after I shortened its window; text shortened and window extended; 25/25 pass.
5. **Review round 1 (contact sheets at 2 s + spot stills)**: count-up animations put numbers on screen that are not in FACTS.md (e.g. "13" on the way to 26, "×2.5" under the loupe) → removed; every number now lands only as its fact value on the narrator's word. The loupe landed over the "525" plate → plate leaves earlier. The quote note bled through the index plates → faster fade. The six glowing cards overlapped the first product line → faster fade. Duplicate subtitle under the "6 can be e-mailed today" label → that cue (and the closing F19/F23 cues, which are on screen as type) is not burned in; all cues stay in the `.srt`. The dates on the loupe card overflowed the card → shorter wording. After the switch-off the stale cards and the aluminium frame stayed grey → they now dim with the light. A one-frame subtitle gap between back-to-back cues → cues bridge the 40 ms gap.
6. **mix.py**: `sfx.click` and `sfx.thump` have different lengths → summed through a padding helper.
7. **Size**: CRF 24 gave 28.4 MB → CRF 26 with `-tune grain` gives 23.2 MB.
8. **Toolkit stderr note** "WebGL runs on software rendering": harmless for a 2D-canvas film.

## Deviations from the guides (and why)

- `setup.sh` not run; its steps done by hand with the venv at `/tmp/ext/venv` (symlinked as `$LIB/.venv`) and the preinstalled Chromium (no `playwright install`). Python 3.13 (allowed: kokoro-onnx needs 3.11–3.13).
- **No real archive scans.** STYLE.md wants real archive objects; here the "archive" is the client's member file, which may not be shown. The cards are schematic stand-ins (IDs + city field + redaction bars), labelled on screen "Schematic · IDs and city only · no member data". The eight London spellings are the real list from VERIFICATION.md §2.
- **Loupe in Canvas 2D, not WebGL**: the lens re-draws the world at 2.5× inside a circular clip, with rim, bevel, acrylic skirt, shadow and the 1.35× landing; it has no pincushion distortion or RGB fringe.
- **Signal colour** kept at the style's example orange #FF5A1F.
- **Burned-in subtitles omitted** for S14–S16 because the identical words are on screen as type at that moment; the `.srt` has all 21 cues.
- Delivered at 24 fps, −14 LUFS, as DIRECTOR.md asks; final encode at CRF 26 (the toolkit's master is CRF 19) to meet the 25 MB limit.
- Two silences open a quarter beat before their downbeat (like the demo's breaths); `cuecheck.mjs` exempts them by name.
- Not-the-demo check (DIRECTOR.md §11): structure, opening, signature shot, camera path and score shape differ from *Two Seconds Short*; the index pull-back exists in both, but here it is the split, not the ending.
- Music-to-voice gap is 15.9 dB while speaking (≈ 11 dB before a 5 dB duck), matching the guide's "about 10 dB under, ducked". The low band (20–120 Hz) sits at −19.8 dB vs the rest: light, by design (felt piano, no drums).

## Defaults chosen (nobody to ask)

Voice Kokoro `bf_emma` at 0.9; 72 BPM, D minor → F major; felt piano (Salamander, soft velocities, 7 kHz low-pass), VSCO 2 CE string sections, VCSL bowed vibraphone + glockenspiel; signal orange; IBM Plex Mono/Sans/Serif; subtitles burned in (IBM Plex Sans 40 px, dark plate, 3 px signal edge); grain 1; poster = the loupe on the London card (`src/poster.jpg`).

## Deliverables

- `trusted-segments.mp4`, `trusted-segments.srt` (21 cues), `SCRIPT.md` (narration, subtitles and on-screen text with time codes and fact ids), `contact_sheet.jpg` (one frame per beat: 7.0 s cold open, 15.5 s loupe, 29.0 s climb, 36.0 s turn, 61.5 s split, 74.0 s close), this log.
- `src/`: `index.html`, `film.js`, `timeline.js`, `mix.py`, `build.sh`, `tools/` (fonts, export, cuecheck, trim_voice, final_asr, script_md), `voice/lines.json`, `out/timeline.json` + `out/cues_srt.json` (the page reads them), `out/readcheck.txt`, `fonts/` (OFL), `stems/` (voice, music, foley, beds as 96 kb/s AAC, 2.9 MB), `TREATMENT.md`, `CREDITS`, `FACTS.md` (what is schematic), `poster.jpg`. No node_modules, venv or sample libraries.

## Reproduce

```sh
# 1. toolkit at the pinned commit
git clone https://github.com/lemomo-ai/lemo-opuscar /tmp/ext/lemo/lemo-opuscar && cd /tmp/ext/lemo/lemo-opuscar && git checkout bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00
# 2. dependencies (no setup.sh)
python3.13 -m venv /tmp/ext/venv && /tmp/ext/venv/bin/pip install -r requirements.txt -r requirements-voice.txt
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund && git checkout -q -- package.json package-lock.json
ln -sfn /tmp/ext/venv .venv
sh tools/fetch.sh voice && for l in salamander vsco2ce vcsl; do sh tools/fetch.sh instruments $l; done
# 3. the film source
mkdir -p films/trusted-segments && cp -r <workspace>/projects/alumnforce_case/film/src/. films/trusted-segments/
export PLAYWRIGHT_CHROME=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
# 4. one command: voice, checks, picture, score + mix, master, size pass, subtitles (CRF=26 by default)
sh films/trusted-segments/build.sh
# 5. optional checks and documents
LIB=$PWD .venv/bin/python -I films/trusted-segments/tools/final_asr.py films/trusted-segments/trusted-segments.mp4 films/trusted-segments/voice/lines.json
node films/trusted-segments/tools/script_md.mjs films/trusted-segments > films/trusted-segments/SCRIPT.md
```

Kokoro and the sampler are deterministic on the same machine; a different CPU may shift a voice line by a few milliseconds, which `export.mjs` absorbs (it re-reads the durations and word times).
