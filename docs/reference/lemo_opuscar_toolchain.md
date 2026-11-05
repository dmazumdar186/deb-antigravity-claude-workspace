# lemo-opuscar toolchain (cloud container, verified 2026-11-05)

Status: WORKS. Library at /home/user/tools/lemo-opuscar (full clone, MIT). Proof film (5 s, 1080x1350, 30 fps, score + foley, metadata) rendered end to end: /home/user/tools/films/proof/proof_meta.mp4 (render 4.9 s, mux 2 s).

## Style choice
1. `dataviz` (Data Storytelling): cream paper, ink, Newsreader serif + IBM Plex Mono labels, handwritten notes, line-draw, pinned notes. Path: styles/dataviz/STYLE.md, demo source styles/dataviz/demo/ (engine.js has paper, type, leader, line-draw helpers). Closest on materials/type. It is chart-centred, so reuse its paper/type/line-draw grammar, not the pencil.
2. `swiss-motion` (styles/swiss-motion/STYLE.md; demo/film.js has clip-reveal text, knife cuts, snap easing, caption rows): closest on kinetic typography, grid, one signal colour (use ochre).
3. `halftone-dossier` (cream archive paper, stamps): only if a print/dossier feel is wanted.
No library style is "editorial notes" exactly. Best path: own composition in swiss-motion kinetic-type grammar on dataviz paper palette (the README "make a style your own" flow does the same; MY-STYLES.md). Demos ship WITHOUT fonts/data/voices/music, so they cannot be rendered as-is (stills fail on missing Newsreader TTFs, data/jja.json). The SKILL says demo source is reference only. Not verified which one produced the earlier video.

## One-time setup (done; repeat in a fresh container)
```
git clone https://github.com/lemomo-ai/lemo-opuscar /home/user/tools/lemo-opuscar && cd /home/user/tools/lemo-opuscar
npm install --no-audit --no-fund            # playwright-core + three. Do NOT run setup.sh deps (it runs playwright install)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sh tools/fetch.sh instruments vsco2ce       # 396 MB, CC0, Versilian Studios Chamber Orchestra (strings/brass/keys/perc)
sh tools/fetch.sh instruments vcsl          # 271 MB, Versilian Community Sample Library, CC0
# ffmpeg 7+ REQUIRED (system is 6.1: mux.sh rejects audio "only 2.1 s of 5 s could be decoded")
python3 -m venv /home/user/tools/ffmpeg7/v && /home/user/tools/ffmpeg7/v/bin/pip install imageio-ffmpeg
mkdir -p /home/user/tools/ffmpeg7/bin && ln -sf $(/home/user/tools/ffmpeg7/v/bin/python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())") /home/user/tools/ffmpeg7/bin/ffmpeg   # gives ffmpeg 9.0.2
```
Every session:
```
export PATH=/home/user/tools/ffmpeg7/bin:$PATH
export PLAYWRIGHT_CHROME=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
```
Network: github.com release assets, raw/HF, pypi, npm, fonts.googleapis.com all reachable. Versilian samples come from the lemomo-ai GitHub release (tools/assets.json), not versilian.com directly.

## Film project layout (outside the library, e.g. /home/user/tools/films/<name>/)
```
index.html   canvas page, loads fonts/fonts.css + main.js (module)
main.js      sets window.DUR, window.EV, window.render(t), window.READY=true (page contract: core/README.md)
fonts/       woff2 + fonts.css (Newsreader 400/700 + italics, IBM Plex Mono 400/600 from npm @fontsource/*, OFL)
mix.py       score + foley -> out/mix.wav
out/         video.mp4, mix.wav, stills
```
Proof film at /home/user/tools/films/proof is a working template (headline clip-reveal, line-draw underline, italic quote, staggered code card with typewriter, footer "ProdCraft · weekly notes" + "02").
Rules: render(t) must be deterministic (no Date.now, no unseeded Math.random); lay out from innerWidth/innerHeight (size comes from --size); load fonts with document.fonts.load before READY; library helpers via absolute URL `import {clamp,seg,eo,eio,back} from '/core/lib.js'`. Text goes in main.js draw calls (or a content.json fetched relative to the page). Put every on-screen text in window.TEXTS(t) to use readcheck.

## Render a ~30 s 1080x1350 film
```
cd /home/user/tools/lemo-opuscar; F=/home/user/tools/films/<name>; mkdir -p $F/out
node core/render/still.mjs $F 1.5 8 15 --size 1080x1350 --out $F/out --prefix s_   # review frames (JPEG; read via a worker, not main context)
node core/render/events.mjs $F                                                    # DUR + EV -> $F/events.json
node core/render/readcheck.mjs $F --size 1080x1350                                # text dwell check (needs window.TEXTS)
node core/render/video.mjs $F --size 1080x1350 --fps 30 --workers 3 --out $F/out/video.mp4
.venv/bin/python $F/mix.py /home/user/tools/lemo-opuscar $F                        # -> $F/out/mix.wav
sh core/render/mux.sh $F/out/video.mp4 $F/out/mix.wav $F/film.mp4 30 0             # loudnorm -14 LUFS, grain 0 (paper style)
ffmpeg -y -i $F/film.mp4 -c copy -metadata title="..." -metadata comment="Made in code with lemo-opuscar (MIT) | music: original, CC0 samples (Versilian Studios)" $F/film_final.mp4
```
Speed: ~30 fps capture of a simple 2D canvas ~ 1 s per 30 frames/worker; 30 s film est. 30-60 s.

## Score
Write events (t, inst, pitch, dur, vel, pan) and call `core/audio/sampler.py` `S.render([...])` (returns stereo float32 48 kHz; write with soundfile). Instruments e.g. violins, violins_pizz, cellos, harp, piano (piano needs Salamander CC BY: `sh tools/fetch.sh instruments salamander` and credit it). Verified: violins_pizz + cellos render in ~1 s. Credits line: `S.credits(['violins_pizz','cellos'])` -> "Samples (CC0): VS Chamber Orchestra: Community Edition (Versilian Studios)". Foley (click, whoosh, ding, paper) from `core/audio/sfx.py`, driven by window.EV so sound lands on the frame. Mix: score, foley, `sfx.limit`, 48 kHz wav; no voice. Proof mix.py shows the drone+foley fallback needing no samples.

## Metadata
mux.sh sets none. Add with the ffmpeg `-c copy -metadata title= -metadata comment=` step above (verified; encoder tag Lavf is added too).

## Gotchas
- ffmpeg 6.1 breaks mux.sh (see above); use the ffmpeg 9 shim on PATH. video.mjs also uses PATH ffmpeg.
- Setup is scripted: `bash execution/video/linkedin_weekly_video_setup.sh && source /home/user/tools/lemo_env.sh`.
- Use PLAYWRIGHT_CHROME; never `setup.sh deps` / playwright install. Headless shell reports WebGL on SwiftShader (software): fine for 2D canvas, slow for three.js styles.
- video.mjs has no start/end trim; make a short DUR (or `--q` param) for tests.
- Demos lack fonts, data, voices, music (stripped); stills show "optional file missing" then pageerror.
- Tools take --size WxH (even numbers), events.mjs run without --size is fine if layout uses innerWidth only at draw time.
- Default output is 24 fps 1920x1080; pass --fps 30 to video.mjs AND to mux.sh (4th arg).
- library hooks: don't edit core/ or styles/ for a film; keep film dirs outside the library. Lock file out/video.mp4.lock if a render crashes: delete it.
- Credit text in the film must say "Made in code with lemo-opuscar (MIT)"; samples CC0 (Versilian), Newsreader/Plex Mono OFL.
