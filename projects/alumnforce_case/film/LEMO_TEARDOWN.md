# Lemo-Opuscar teardown: what it is worth, how to use it, what it cannot do

Audited 2026-11-01, read-only, against `github.com/lemomo-ai/lemo-opuscar` at commit `bebbbe1` (2026-11-01). The clone is shallow and the history visible here begins 2026-10-17 (31 commits). Paths below are relative to the repo root unless they start with `directives/` or `execution/`. I checked things statically only: I read files, and ran `py_compile` and `node --check` on core (all passed). I rendered nothing.

**Verdict in one paragraph.** This is not a video engine. It is roughly 1 MB of very good *prompting*: 66 style briefs (`styles/*/STYLE.md`, 937 KB in total) plus a directing method (`DIRECTOR.md`) and a build method (`TECHNIQUE.md`), all of which tell Claude Opus to hand-write a canvas or WebGL page for every film. Around that sits a small, well-engineered toolkit of about 2,900 lines (`core/`) that captures the page frame by frame, synthesises or samples a score, runs TTS with a speech-to-text check, and masters to -14 LUFS. What it gives you is taste and discipline, written down. What it costs you is 30–60 minutes of Opus per film and a film that is never the same twice. The main risk is the supply chain: the skill pulls the upstream `main` branch again on every run.

---

## 1. Architecture: how a film gets made

The pipeline is drawn at `TECHNIQUE.md:5-13`. The single source of truth is the timeline. Picture, voice, music, foley and subtitles are all derived from it.

| Step | Who does it | Files | Deterministic? |
|---|---|---|---|
| 0. Fetch library | `plugin/skills/lemo-opuscar/scripts/setup.sh` makes a sparse clone into `~/lemo-opuscar`, or **resets it to upstream main** if it already exists (`setup.sh:29-41`) | setup.sh | Script yes, content no (whatever is on main today) |
| 1. Brief | Model asks the user **once**, then fills every gap with defaults and asks nothing more (`AGENTS.md:67-74`, `DIRECTOR.md:11`) | AGENTS.md, DIRECTOR §1 | Model |
| 2. Benchmark and treatment | Model picks reference works and writes `TREATMENT.md` with three candidate structures **before** it opens the demo (`AGENTS.md:34`, DIRECTOR §2–4). Edit & Documentary styles gather their footage first | DIRECTOR.md | Model |
| 3. Look | Model writes `index.html` exposing `window.render(t)`, `DUR`, `READY`, optional `EV` cue events and `TEXTS` on-screen text (`TECHNIQUE.md:35-43`); renders style frames with `core/render/still.mjs` | STYLE.md, core/lib.js | The page is model-written; once written, `render(t)` must be pure (`TECHNIQUE.md:65`) |
| 4. Storyboard | Only if the user asked for one; it is the only stop for approval (`AGENTS.md:77`) | – | Model |
| 5a. Voice | `core/tts/tts.py` (Kokoro, offline) or `tts_zh.py` (edge-tts, online); `asr_check.py` transcribes every line with faster-whisper and loops until exit 0 (`TECHNIQUE.md:98-101`) | core/tts/ | Kokoro is deterministic given the text; the script text is model-written |
| 5b. Score | Model writes event lists for `core/audio/sampler.py` (seeded RNG, `sampler.py:24`), `pluck.py` (Karplus–Strong) or numpy synthesis | core/audio/ | Yes, given the score code |
| 5c. Foley and mix | `sfx.py`, driven by `window.EV` exported by `core/render/events.mjs`; the mix is a model-written `mix.py` | core/audio/sfx.py | Yes |
| 6. Capture | `core/render/video.mjs`: N headless-Chromium workers, JPEG screenshots piped to ffmpeg, segments joined losslessly (`video.mjs:44-69`) | core/render/ | Yes |
| 7. Master | `core/render/mux.sh`: two-pass loudnorm to -14 LUFS with a true-peak ceiling of -1.2 dB, grain added in ffmpeg, refuses truncated or damaged audio (`mux.sh:41-99`) | mux.sh | Yes |
| 8. QA | `readcheck.mjs` (every text on screen long enough to read), contact sheets (`sheet.py`), ebur128, blackdetect, Whisper on the final mix; **one fix round** (`DIRECTOR.md:116`); "not the demo again": at least 4 of 6 structural traits must differ from the demo (`DIRECTOR.md:117`) | core/render/, DIRECTOR §11 | Checks yes; judging the frames is the model |
| 9. Deliver | `<name>.mp4`, `poster.jpg`, `.srt`, `TREATMENT.md`, `CREDITS`, source + one-command `build.sh` (`DIRECTOR.md:124-130`) | – | – |

**In short:** everything after the page and the score are written is deterministic and can be rebuilt from source with `build.sh`. Everything creative (the story, every pixel's drawing code, the score) is written fresh by the model on each run. If you hand the same brief over twice, you get two different films.

## 2. Inventory

### Styles: 66, plus a template (`styles/_template`), in 11 families (from `style.json` `category_en`)

| Family | n | Styles |
|---|---|---|
| **Evidence Films** (real data, every number sourced; `FACTS.md` required, `TECHNIQUE.md:147`) | 8 | satellite-briefing, briefing-board, lidar-survey, white-model, data-physical, teardown, microscope, archive-lighttable |
| **Edit & Documentary** (cut from real archive footage and documents) | 8 | caption-news, newsreel, countdown, city-symphony, visual-investigation, kino-montage, telestrator, news-package |
| Information & Keynote | 8 | dataviz, iso-infographic, dark-keynote, living-screencast, hologram-hud, transit-map, isometric-picture-book, circuit-board |
| Hand-drawn & Painting | 8 | crayon-book, watercolor, ink-wash, impasto, one-line, whiteboard, urban-sketch, chalkboard |
| Graphic & Type | 7 | swiss-motion, spy-titles, art-deco, blueprint, stained-glass, pictogram-motion, ascii-crt |
| Materials & 3D | 7 | brick-toy, paper-popup, tilt-shift, lowpoly-island, glass-product, memphis-diorama, desktop-flythrough |
| Print & Printmaking | 6 | risograph, halftone-dossier, woodcut, engraving, silkscreen-poster, printed-long-take |
| East Asian Traditions | 4 | shadow-puppet, ukiyoe, papercut-red, paper-lantern |
| Cartoon & Anime | 4 | rubber-hose, cel-anime-80s, scifi-toon, midcentury-toon |
| Games | 4 | pixel-rpg, hd-2d, microgame, game-show |
| Cinema & Eras | 2 | silent-film, backrooms |

The README groups the seven newest styles under a "New · 2026-10-29" heading. Their `style.json` files put them in the families above. The Edit & Documentary demo tools reach archive.org, Wikimedia Commons, NASA, the Library of Congress and, in telestrator, YouTube via `yt-dlp` (`styles/telestrator/demo/tools/fetch_sources.sh:14`). Demo durations run from 30 s to 149 s; most are 40–60 s.

### Core tools (`core/README.md` is the command reference)

| Module | One line |
|---|---|
| `render/serve.mjs` | Static server on 127.0.0.1 only, with a host-header check and a path-traversal guard (`serve.mjs:22,30`) |
| `render/page.mjs`, `browser.mjs` | Opens the page in Playwright Chromium and waits up to 180 s for `READY`; any page error or missing script exits 1; warns when WebGL falls back to software |
| `render/still.mjs` | Review stills at given times or over a range |
| `render/video.mjs` | Parallel frame capture to H.264 (CRF 14), up to 6 workers, lock file per output |
| `render/events.mjs` | Exports `DUR` and `EV` to `events.json` for the mixer |
| `render/readcheck.mjs` | Every on-screen text must stay visible for at least CJK chars ÷ 4.5 + Latin chars ÷ 15 + 1.5 s |
| `render/sheet.py` | Contact sheet from stills |
| `render/srt.py` | `.srt` from `[{t0,t1,text}]` |
| `render/mux.sh` | Mux, two-pass loudnorm to -14 LUFS, grain, damaged-audio detection |
| `render/slot.mjs` | Optional machine-wide render throttle (`RENDER_SLOTS`) |
| `tts/tts.py` | Kokoro-82M offline. The downloaded voice pack has 54 voices: English 28, Chinese 8, Japanese 5, Hindi 4, Spanish 3, Portuguese 3, Italian 2, **French 1** (`ff_siwis`, female). I listed these from `voices-v1.0.bin`; the repo itself documents only English and Chinese |
| `tts/tts_zh.py` | edge-tts (Microsoft neural voices, online, any language); "check Microsoft's terms yourself before using the voices commercially" (`tts_zh.py:10`) |
| `tts/asr_check.py` | faster-whisper check of each line: word-exact for English, character similarity of at least 0.92 for zh/ja/ko, numbers compared by value; writes word timestamps |
| `audio/sampler.py` | Sampled instruments from five free libraries, round-robins, seeded; `credits()` writes the attribution lines |
| `audio/pluck.py` | Physically modelled plucked strings (numba) |
| `audio/sfx.py` | Procedural foley: click, whoosh, thump, ding, paper; compressor and limiter |
| `three/post.js` | three.js r170 post-processing: depth of field, GTAO, bloom, grade, 2× supersampling |
| `post/crt.js` | WebGL2 CRT/VHS pass |
| `lib.js` | Seeded `mulberry`, `hash`, noise, easing, interpolation |
| `fonts/` | Four OFL display families, subset; Chinese only about 200 glyphs |
| `assets/polyhaven/` | CC0 HDRIs and two models |

## 3. Requirements

| Item | Requirement | Evidence |
|---|---|---|
| Node | 20+ | `package.json` engines; `setup.sh:98-100` |
| ffmpeg | **7+** (6.x under-reports audio length, so `mux.sh` rejects the file). Ubuntu 24.04 ships 6.1; the README points to an unofficial static build at johnvansickle.com | `TECHNIQUE.md:17`, `README.md:147` |
| Python | 3.11+; voice tier needs **3.11–3.13** (kokoro-onnx). Our local 3.14 is not enough; `uv` fetches 3.12 | `setup.sh:51-57,75`; `requirements-voice.txt` |
| OS | Developed on macOS (Apple silicon); "Linux should work"; **Windows only through WSL** | `TECHNIQUE.md:17` |
| GPU | 3D and shader styles "want a GPU"; software WebGL (SwiftShader) is about 6× slower | `TECHNIQUE.md:17`, `styles/paper-lantern/STYLE.md:104` |
| Library path | espeak-ng data path under 160 bytes | `tts.py:28-39` |
| Not supported | claude.ai chat; it needs a local shell | `tools/directory/README.md:34` |

**Dependency tiers and downloads** (`TECHNIQUE.md:21-27`):

| Tier | What | Size | Pinned? |
|---|---|---|---|
| core | npm `playwright-core` ^1.63, `three` ^0.170 (lockfile with sha512 integrity, installed with `npm install`, not `npm ci`); Chromium headless shell from Playwright's CDN; pip numpy, scipy, soundfile, soxr, pillow, fonttools | ~350 MB | npm: lockfile. **pip: no versions, no hashes** (`requirements.txt`) |
| voice | kokoro-onnx, edge-tts, faster-whisper, `av<19`; Kokoro model `voice.tar` (354 MB) from **this repo's own GitHub release `assets`**; Whisper model from Hugging Face on first check (145 MB English, 480 MB Chinese) | ~0.55 GB + Whisper | Kokoro tar: sha256 in `tools/assets.json`. pip: unpinned. HF: no revision pin |
| music | numba | ~140 MB | unpinned |
| samples | `fetch.sh instruments <lib>`: freepats 416 MB, vsco2ce 414 MB, vcsl 285 MB, salamander 229 MB, karoryfer 78 MB (about 1.4 GB in total) | 70–420 MB each; needs 2.2× free space while it unpacks | sha256 pinned (`tools/assets.json`); tar extraction uses the `data` filter (`fetch.sh:75-86`) |
| hdri | Poly Haven HDRIs | 12 MB | sha256 pinned |
| per style | LiDAR readers, CAD importers, `yt-dlp`, Google Fonts at build time | varies | agent installs them into the project folder (`TECHNIQUE.md:29`) |

**Time.** About 30–60 minutes of agent time and "a fair amount of tokens" per film (`README.md:146`). The repo gives no dollar figure. A demo `build.sh` re-run (render, TTS, Whisper, mix) takes 2–7 minutes on Apple silicon, and picture capture alone 20–90 s with 3–4 workers (`styles/dataviz/DEMO.md:80`, `styles/data-physical/DEMO.md:80`, `styles/microscope/DEMO.md:84`).

## 4. Licensing

| Layer | Licence | Commercial use | Duty |
|---|---|---|---|
| Code and guides | MIT, © 2026 LemoLab (`LICENSE`, `README.md:386`) | Yes | Keep the notice if you redistribute the code |
| **Films you make** | "Yours, no credit needed" (`README.md:388`, `AGENTS.md:16`); the guides even strip LemoLab sign-offs (`DIRECTOR.md:122`) | Yes | Your own `CREDITS` for third-party assets |
| Demo films and stills | CC BY 4.0 (`README.md:387`) | Yes | Credit LemoLab with a link and say what you changed. Demos also carry third-party assets under their own licences (`README.md:389`), and some are "unofficial fan films of real events or characters" (`DIRECTOR.md:138`). **Don't reuse demo films in client work** |
| Excluded voice tracks | Game Show (macOS `say`), Paper-cut Lightbox (Edge TTS), News Package (Doubao) are not CC BY (`README.md:390`) | No | – |
| Fonts in `core/fonts` | OFL 1.1; Lilita One and IM Fell have Reserved Font Names (`core/fonts/OFL.md`) | Yes, embedding in video included | Rename the font if you modify it |
| Samples | VSCO 2 CE, VCSL, FreePats, Karoryfer: CC0. **Salamander piano: CC BY 3.0. MuldjordKit drums: CC BY 4.0** (`core/audio/INSTRUMENTS.md:107-125`) | Yes | Credit is required whenever `piano` or `drum_kit` is used |
| Kokoro voices | Apache-2.0 (`styles/cel-anime-80s/DEMO.md:62`) | Yes | None for the audio output |
| edge-tts voices | Microsoft online service; the repo itself says to check the terms (`tts_zh.py:10`) | **Unclear: treat as no for paid work** | – |
| Whisper | Used only to check lines, never shipped | n/a | – |
| Poly Haven | CC0 | Yes | – |
| Archive footage and data (Edit & Doc, Evidence) | Per item. CC0, CC BY, OFL or public domain only; "no known restrictions" does not count; ODbL or CC BY-SA only after the user agrees (`TECHNIQUE.md:145`) | Per item | `SOURCES.md` / `CREDITS` |
| Your brand and client marks | Not covered | Only with rights (`DIRECTOR.md:137`) | – |

**For our cases:**
- **Recruitment presentation:** fine.
- **Client marketing:** fine if `CREDITS` is honoured and you have the logo rights.
- **Paid ads:** fine if you stay on CC0 instruments and Kokoro, use no edge-tts, and use no archive footage you have not cleared. CC BY credit lines are awkward in a 15 s ad; the simple rule is "no `piano`, no `drum_kit`".
- **Inference I have not checked:** `kokoro-onnx` pulls in `espeakng_loader` (`tts.py:30`), which ships espeak-ng under GPL-3. That matters only if you redistribute the toolchain, not for the films.

## 5. Security review (severity-ranked)

| # | Severity | Finding | Evidence | Mitigation |
|---|---|---|---|---|
| 1 | **High** | **The code it runs changes upstream on every run.** The marketplace install tracks the repo, and `plugin.json` has no version. Every skill run does `git fetch --depth 1 origin main && git reset --hard FETCH_HEAD`, then the agent runs `node`/`python` from that tree. The guides (`AGENTS.md` etc.) are also prompts, so an upstream commit can steer the agent. In our workspace this runs under `bypassPermissions` (CLAUDE.md principle 5): any upstream change executes with the operator's rights and nothing prompts. The repo is about two weeks old, has one maintainer and moves fast | `setup.sh:29-33`; `.claude-plugin/marketplace.json`; `plugin/.claude-plugin/plugin.json` | Don't install the marketplace plugin. Clone yourself and pin a SHA. **Don't set `git config lemo.managed true`**: `setup.sh` then treats it as the user's clone and never fetches (`setup.sh:29,34`). Set `LEMO_OPUSCAR_HOME` |
| 2 | Medium | Python dependencies are unpinned and unhashed; Whisper is downloaded from HF with no revision pin. The Kokoro model is re-hosted on the maintainer's own release, not upstream. The sha256 values in `assets.json` live in the same repo that auto-updates, so they prove the download arrived intact, not who made it | `requirements*.txt`; `setup.sh:80-81`; `asr_check.py:16`; `tools/assets.json` | Generate a `uv pip compile --generate-hashes` lock in our wrapper; mirror the models once and verify them |
| 3 | Medium | Privacy: edge-tts sends narration text to Microsoft. The main-edition skill does not force a consent step (the directory edition does). The footage tools call public archives with a `lemo-opuscar` User-Agent; fonts come from Google | `tts_zh.py:10`; `tools/directory/SKILL.md` (Chinese narration row); `footage.py` UA | Ban `tts_zh.py` for client or member data; Kokoro only |
| 4 | Medium | Headless Chromium runs model-written pages with **no network interception** (`page.mjs` only logs responses) plus `--ignore-gpu-blocklist`. Edit & Doc styles feed downloaded third-party media (archive.org, Commons, YouTube) to ffmpeg and the browser | `page.mjs:100-110`; `browser.mjs:48` | Fine for the operator's own briefs; for untrusted footage, run it in the cloud container |
| 5 | Low | Writes outside the project folder: `~/lemo-opuscar`, `~/lemo-my-styles`, `/tmp/lemo-opuscar-render-slots-<uid>`; `reset --hard` wipes local edits in a managed library; `rm -rf "$LIB"` runs only after a failed fresh clone into an empty folder | `setup.sh:35-38`; `slot.mjs:11`; `MY-STYLES.md` | Point `LEMO_OPUSCAR_HOME` at a dedicated path |
| 6 | Low | `LEMO_OPUSCAR_REPO` env var can redirect the clone source | `setup.sh:11` | Don't set it |
| 7 | Info (good) | No hooks, no MCP servers, nothing auto-run in the plugin (only `plugin.json`, `SKILL.md`, `setup.sh`). No `curl \| sh`. fetch.sh checks sha256 and refuses unsafe tar entries. The server binds to loopback and blocks DNS rebinding. No telemetry found in code | `plugin/` tree; `fetch.sh:97-101`; `serve.mjs:30,39` | – |
| 8 | Info | CI only builds the gallery (no tests, no SAST); actions pinned by major tag, not by SHA | `.github/workflows/pages.yml` | – |
| 9 | Info (cost) | Skill description is **1,114 chars** (our budget is 250, `.claude/rules/token-economy.md` §1) and is re-sent on every call once installed. Each film reads about 55–75 KB of guides | `plugin/skills/lemo-opuscar/SKILL.md:3` | Our own wrapper skill with a short description |
| 10 | **Policy** | `DIRECTOR.md` §13 applies to "every frame that shows a map … in every style": when China is in frame, draw Taiwan, the South China Sea dashed line and so on per PRC standard maps, and never list Taiwan, Hong Kong or Macao as countries. For a French or European client an agent may silently apply this. That is reputational risk, not code risk | `DIRECTOR.md:140-150` | Override it in our directive: keep "no borders, frame out disputed areas" and drop the China-view rules unless the client asks for them |

## 6. What it cannot do, and what it does poorly

**Hard limits**
- **No live action, no photoreal people, no generated video.** "No video generation, no stock footage" (`README.md:54`). Characters are 2.5D code rigs (`TECHNIQUE.md` §10). Real people appear only as generic stand-ins (`styles/game-show/STYLE.md:98`) or as archive figures in Edit & Doc styles.
- **No real lip sync.** Mouths follow loudness and spectral centroid at 12 fps (`styles/scifi-toon/STYLE.md:48`). That reads as cartoon flapping, with no visemes.
- **No screenshots of the product.** Living Screencast redraws every UI element in HTML/SVG and forbids screenshots (`styles/living-screencast/STYLE.md:24,28`). You need a precise UI spec.
- **No editing of existing videos** (`SKILL.md:3`: "Not for plain editing, trimming or converting").
- **No editing UI.** There is no timeline GUI. Every change means re-prompting the agent and re-rendering.
- **Not in claude.ai chat, and Windows only through WSL.**
- **Brand assets are BYO.** Logo and fonts come from the user (`MY-STYLES.md:78`). It does not manage brand kits.

**Soft limits**
- **Model-bound.** Tuned for Opus 5.5 (`README.md:13`); our Opus tier matches, Fable and Sonnet are untested.
- **Short-form.** The default is 30–60 s; beyond 2–3 minutes "multiplies time and token cost" (`DIRECTOR.md:13`).
- **French is thin.** Kokoro has one French voice (`ff_siwis`); natural French means edge-tts (online, terms unclear). Bundled fonts are Latin display faces; body fonts come from Google Fonts at build time.
- **Determinism stops at the source.** The rebuild is reproducible, but the creative output is not. There is no seed for "the same film again".
- **One fix round, by design** (`DIRECTOR.md:116`). Polish beyond that is your notes, one round at a time.
- **The cost is opaque.** Tokens are undocumented. Expect an Opus session of an hour per film plus fix rounds.
- **Software WebGL is slow.** 3D, glass and paper styles in a GPU-less cloud container are about 6× slower.
- **Loudness targets social, not broadcast.** It masters to -14 LUFS; broadcast specs (-23/-24) need re-mastering.

**Strengths worth stealing.** The `readcheck` reading-time gate, ASR verification of every TTS line, two-pass loudnorm with truncation detection, the `FACTS.md` discipline, "not the demo again", and the "brief once, then no questions" protocol, which fits our No-HITL rule.

## 7. Compared with our Remotion and prodcraft pipelines

| | Lemo-Opuscar | Our Remotion (`directives/video/remotion_*.md`) | prodcraft (`execution/video/prodcraft_*`, shorts and v2v directives) |
|---|---|---|---|
| What it is | Style knowledge plus an agent that writes a canvas page per film | React compositions in a registered project, rendered through `remotion_render.py` | GLM plan → stills → Gemini critic → reroll → Remotion render; v2v through Higgsfield |
| Picture | Hand-coded, 66 distinct looks | Motion graphics, captions, overlays (alpha), `@remotion/three` | Remotion scenes; generative v2v on ≤10 s real clips |
| Audio | Scoring, foley, TTS, ASR check, mastering included | Bring your own | Bring your own (Whisper for captions) |
| Reuse | Low: every film is new code | High: components and templates | Medium: plan schema |
| Licence | MIT, free | Remotion company licence above 3 seats (`remotion_render.md:10-11`) | Per provider |
| Repeatability | Rebuild yes, re-create no | High | Medium (critic loop) |
| Best for | One-off hero films with a strong look: case-study cold opens, launch teasers, explainers | Templated series, brand-consistent captions, overlays for Resolve | Repurposing long-form, real-footage edits |

**Rule of thumb.** Use Lemo for a single high-craft 30–60 s piece where the look is the message. Use Remotion when you need the same template many times or exact brand control. Use prodcraft when the source is real footage. Lemo's audio and QA tools (`mux.sh`, `readcheck`, `asr_check`) are worth lifting into the Remotion pipeline in any case. They are MIT.

## 8. Integration options

| Option | How | Verdict |
|---|---|---|
| A. Install the marketplace plugin | `claude plugin marketplace add …` | **No.** Auto-updating code under bypassPermissions (finding 1) and a 1.1 KB description in every context |
| B. Vendor into the repo | Copy `core/` and the guides | No. 219 MB with demos; nested `CLAUDE.md` (`@AGENTS.md`) would load whenever files are read; we would own the merges |
| C. **Pinned clone plus a thin skill wrapper** (recommended) | `execution/video/lemo_opuscar_setup.py`: clone to `$LEMO_OPUSCAR_HOME` (default `~/lemo-opuscar`) at a pinned SHA, never set `lemo.managed`, hashed pip lock, run `setup.sh deps`. A workspace skill with a description of 250 chars or less points at the directive | Yes |

**Where Jev fits** (`.claude/skills/jev/SKILL.md`):
- **Style pick.** Two calls, because 66 options is too wide a menu for one `choice`:
  1. `choice` over the 11 families plus `none`, using the brief.
  2. `choice` over that family's 2–8 styles. Descriptions are built from each `style.json` `line` and `uses` fields.

  Add `noul` questions in the same call, for example "the brief needs real footage", "the brief needs 3D/GPU" and "the brief has a map". Below the confidence threshold, Claude proposes 2–3 styles itself, as `AGENTS.md:43` already does.
- **QA gate (text only).** Ask `noul` over `TREATMENT.md` plus `FACTS.md`: "every number in the treatment is in FACTS", "the treatment names a real logo or person", "the treatment contains a map". The deterministic gates (`readcheck` exit 0, `asr_check` exit 0, LUFS in [-15,-13], `blackdetect` empty) need no model. Visual QA stays with a vision worker that returns PASS or a defect list, per the token-economy images rule.

## 9. Use cases

### (a) AlumnForce hiring panel: the "Trusted Segments" case
- **What works:**
  - **Dark Tech Keynote** (SaaS launch grammar: one giant number, a single accent). Path: "340 London expats" → the 49 → "6 worth e-mailing today".
  - **Data Storytelling.** 525 rows → 500 members → 2 / 26 / 49 → split 1 / 5 / 43.
  - **Living Screencast.** The segment builder redrawn from our `presentation.html` mock, with a pixel mascot as the "reliability split".

  Our `film/FACTS.md` already matches Lemo's `FACTS.md` convention, and `readcheck` plus `asr_check` police every number.
- **What doesn't:**
  - No AlumnForce logo (our FACTS hard rule, and `DIRECTOR.md:137`).
  - No member faces or data.
  - Living Screencast's "real UI" rule assumes a shipped product. Ours is a concept, so frame the UI as a prototype.
  - Windows needs WSL or a cloud session.
  - French narration has one Kokoro voice.
- **Risk.** A single wrong number or a mis-said line in front of the panel. "Gimmick" perception if the film runs over 45 s or comes before the substance. Mitigation: 30–40 s cold open, numbers only from FACTS, gates as in the appendix.

### (b) AlumnForce's customers' campaigns
- **What works:**
  - Profile-update campaigns: **Mid-century Cartoon** (its listed uses include "Set-up guides, how-to").
  - Fundraising: **Data Physicalization** (annual reports) or **Archive Light Table** (school heritage, from the school's own archive scans).
  - Events: **Spy Titles** or **Countdown** openers.
  - Mentoring: **One-line Drawing** or **Watercolor** (life milestones).
  - "Make a style your own" turns a school's colours and logo into a reusable house style (`MY-STYLES.md:76-78`). `--q 'content=…json'` renders variants of a finished film (school name, figures) without re-authoring it (`TECHNIQUE.md:80`).
- **What doesn't:**
  - Per-recipient personalisation at scale. Each variant still renders for minutes.
  - French or other voices at quality, without edge-tts.
  - Real student or alumni photos are possible as "the user's own material", but that raises GDPR consent issues. No faces is the safe default.
- **Risk.** Brand rights per school; the §13 maps rule on alumni world maps; a variable look between films, so pin one house style per client.

### (c) The user's own outbound
- **Cold email (Instantly):** video does not embed. Use a poster image or GIF linking to a hosted MP4. Variants per segment are feasible through `--q`; per-prospect variants are not worth the render minutes.
- **LinkedIn:** **Caption News** "works with the sound off" and has a real 9:16 layout (`styles/caption-news/STYLE.md:29`). Swiss Motion or Pictogram Motion suit thought-leadership loops.
- **Paid ads:** 15–30 s motion pieces at 1080×1920 or 1080×1350 through `--size`. Rules: CC0 instruments only, Kokoro only, no archive footage, claims backed by `FACTS.md`. Our `ad-creative` skill remains the volume tool; Lemo is for one hero ad per angle.
- **Risk.** Undisclosed AI-made claims in ads; token cost per creative against the 5-hour cap; AI-made aesthetics may read as "AI" to marketers.

---

## Appendix: draft `directives/video/lemo_opuscar.md`

```markdown
# Lemo-Opuscar Film — Directive

## Goal
Produce one 20–60 s styled film made entirely in code (canvas/WebGL) with an original score, Kokoro
narration and burned-in subtitles, using the pinned Lemo-Opuscar library. One hero piece, not a series.

## Contract (output)
Project folder `projects/<project>/film/<name>/`: `<name>.mp4` (H.264/AAC, -14 LUFS ±1, 24 fps unless
STYLE.md says otherwise), `poster.jpg`, `<name>.srt` if spoken, `TREATMENT.md`, `CREDITS`, `FACTS.md`
(if any number appears), `build.sh`. Upload the MP4 and poster to the project's Drive folder; local files
are processing-only. No machine notes in the film or the poster.

## Inputs
- Brief: audience, purpose, length (default 40 s), aspect (`1920x1080` | `1080x1920` | `1080x1350`), language.
- `FACTS.md`: the only numbers and quotes allowed on screen or in narration.
- Optional: style slug; brand colours, fonts and logo **with written rights**; own voice recording.

## Tools
- `execution/video/lemo_opuscar_setup.py` (to build): clone to `$LEMO_OPUSCAR_HOME` at the SHA in
  `execution/video/lemo_opuscar.lock`; never set `git config lemo.managed`; install pip deps from a
  hashed lock; then `sh plugin/skills/lemo-opuscar/scripts/setup.sh deps [voice] [music]`.
- `execution/video/lemo_style_pick.py` (to build): Jev two-step `choice` (family → style) from
  `styles/*/style.json`, plus `noul`: needs_footage, needs_gpu, has_map, needs_real_person.
- Library tools, run from `$LIB`: `core/render/{still,video,events,readcheck}.mjs`, `core/render/mux.sh`,
  `core/tts/{tts,asr_check}.py`, `core/audio/{sampler,sfx}.py`.

## Steps
1. Setup (background). Fail if the library HEAD differs from the lock SHA.
2. Style: use the named slug, or run `lemo_style_pick.py`; below confidence 0.6, Claude picks from the
   top 3 and states why. Reject Edit & Documentary styles unless the footage is cleared.
3. Hand the worker (Opus 5.5 tier) a complete brief: `$LIB/AGENTS.md`, `DIRECTOR.md`, `TECHNIQUE.md`,
   the STYLE.md, our FACTS.md, and the **overrides** below. The worker follows AGENTS.md Workflow 2–6.
4. Gates, all must pass before delivery:
   - `readcheck.mjs` exit 0; `asr_check.py` exit 0 on the voice lines and on the final mix.
   - `mux.sh` measured I within [-15, -13] LUFS and true peak at or below -1 dB; `ffmpeg blackdetect` empty.
   - Jev `noul` on TREATMENT.md + narration vs FACTS.md: "every number appears in FACTS" ≥ 0.9.
   - Vision worker reads the contact sheet (`sheet.py`, one frame every 1.5 s) and returns PASS or defects;
     the main session never loads the images.
5. One fix round (DIRECTOR §11). Then upload and report the Drive links.

## Overrides of the library guides (these win)
- Voice: Kokoro only (`tts.py`). Never `tts_zh.py`/edge-tts for client, member or paid work.
- Music: CC0 instruments only for ads; `piano`/`drum_kit` only when CREDITS can be shown.
- Maps: no borders, frame out disputed areas. **Ignore DIRECTOR §13's China-view rules** unless the client asks.
- No logos, trademarks or real faces without written rights; no personal data on screen.
- Never install the marketplace plugin; never let setup.sh fetch upstream.

## Edge cases
- ffmpeg < 7: `mux.sh` rejects the audio; install a 7.x build first.
- Python 3.14: the voice tier fails; use `uv` (it creates a 3.12 venv).
- No GPU (cloud): avoid 3D/glass/paper styles or allow about 6× render time.
- Library path ≥ 160 bytes: Kokoro's espeak-ng fails; keep `LEMO_OPUSCAR_HOME` short.
- French narration: only `ff_siwis` (female); for a male or more natural voice use the operator's recording.
- Variants: render with `--q 'content=content_<v>.json' --out out/<v>.mp4`, never re-author.
- Over 90 s: warn about cost; split into chapters.

## Learnings
(append API limits, render timings and failures here)
```

---

## Honest gaps (not verified statically)

- **Output quality and failure rate.** I rendered nothing (another worker is doing that). I have not seen any film quality or measured how often the one-round fix converges.
- **Token cost per film.** Not documented. "30–60 min" is the author's claim (`README.md:146`).
- **Linux GPU path.** `browser.mjs` passes no ANGLE backend on Linux; whether 3D styles work at all headless in our cloud container is unknown.
- **Kokoro French quality.** `ff_siwis` exists in the voice pack, but whether Kokoro's phonemiser produces good French through `tts.py`, and how `asr_check` copes with French accents and numbers, is untested.
- **Playwright sandbox state.** I did not check whether Playwright 1.63 still launches Chromium without its sandbox by default.
- **Licences I took from the repo's own documents.** Kokoro Apache-2.0, sample libraries and the espeak-ng GPL inference were not checked against upstream licence files. Microsoft's edge-tts terms for commercial use were not checked.
- **The re-hosted Kokoro and sample tars.** I did not compare them with the upstream originals; I only confirmed that a sha256 is declared.
- **The plugin-directory edition.** Its publication state (`tools/directory/*`, which bundles the library and never fetches) is unknown. If it is published, it removes finding 1.
- **Demo footage rights.** Rights claims in demo `SOURCES.md` files were not audited (for example telestrator's beIN SPORTS clip, marked CC BY).
- **History.** The clone is shallow; I could not review the history before 2026-10-17 for removed or rewritten code.
