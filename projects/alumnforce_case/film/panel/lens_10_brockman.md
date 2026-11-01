# Lens 10 (Brockman): can it run unattended for 30 days?

**Verdict: NOT CLEAR.** The film is reproducible today, in this container, by hand. Next month, in a fresh container, it depends on six unpinned or unmirrored fetches, and no bootstrap, lock or cache exists.

## External fetches

| Fetch | Size | Pinned? | On failure |
|---|---|---|---|
| git clone lemo-opuscar @bebbbe1 | ~219 MB | SHA, no mirror | SHA disappears if upstream force-pushes; history is shallow from 10-17 |
| pip, 3 tiers | ~0.5 GB | **no versions, no hashes** (`requirements*.txt`) | silent drift (the `av<19` comment shows drift has already broken it once) |
| npm | ~50 MB | lockfile with sha512, but `npm install`, not `ci` | low risk |
| Chromium headless shell | 261 MB | image-provided `/opt/pw-browsers/...-1243` | wrong path: `build.sh` fails, or a different build renders different frames |
| `voice.tar` + 3 sample packs | 1.28 GB | sha256 in `tools/assets.json` | release tag `assets` can change; a mismatch is a hard stop |
| Whisper `small.en` (and `small` for eval) | 462 MB each | no revision (HF `refs/main` = d1d751a5) | ASR stage dies (exit 2) |
| ffmpeg | apt | 6.1.1, not 7+ | see M3 |

## Findings

**High**
- **H1. No bootstrap, lock or durable cache.** `/tmp` and `~/.cache` go when the container goes. Evidence: `BUILD_LOG.md:23-27` (versions written in prose only). `execution/video/lemo_opuscar_setup.py` and `lemo_opuscar.lock` are recommended in `LEMO_TEARDOWN.md:182,251` but were never built. **Fix:** the bootstrap spec below.
- **H2. The final encode overwrites the committed deliverable in place.** `src/build.sh:30-31` runs `ffmpeg -y` straight to `trusted-segments.mp4`. A timeout mid-encode leaves a truncated file where the good one was. **Fix:** write to `out/final.tmp.mp4`, check it with ffprobe and `film_eval`, then `mv` it into place.
- **H3. The fetch error tells the agent to unpin.** `fetch.sh:99-100` says "Refresh the library (setup.sh or git pull)". An agent running under no-HITL will follow it and land on upstream `main`. **Fix:** verify against our own lock and fetch from our mirror first.

**Medium**
- **M1. A rerun redoes every stage and has no resume.** `build.sh` regenerates TTS and ASR, and a full render takes 124 s. `video.mjs:34` deletes its segments when interrupted, so the next run starts again from frame 0. A rerun takes about 8 minutes. The other ~41 of the 49 minutes were agent authoring, which cannot be replayed. **Fix:** skip a stage when its inputs' hash matches, and give each stage a `timeout`.
- **M2. `film_eval` ASR is hardwired to the ephemeral venv.** `film_eval.py:51` points at `/tmp/ext/venv`. In a new container ASR is SKIPPED, and the report can still say PASS. **Fix:** read the path from the bootstrap's `lemo.env`, and FAIL when `--asr` is requested but cannot run.
- **M3. ffmpeg 6.1 against the required 7+ (`TECHNIQUE.md:17`).** It did not bite us: the length check in `mux.sh:51-56` passed (`BUILD_LOG.md:25`). It is still a latent risk, because `mux.sh:74` pads short audio with `apad`, which could hide an under-reported length. **Fix:** in the bootstrap, require ffmpeg 7.x or fetch a pinned static build with a sha256 check.
- **M4. Byte-identical re-renders are unlikely.** Chromium, Kokoro on a different CPU and the libx264 build all shift the output. `--expect-sha256` would FAIL. **Fix:** gate on SSIM against the reference instead.

**Low**
- **L1. No dead-man alarm and no run log.** **Fix:** write one JSONL line per stage (`stage, sec, exit, sha`) to `.tmp/lemo_runs/`.
- **L2.** Python is 3.13.18 (`BUILD_LOG.md:26`), not 3.11. The cloud image's default 3.11 is in range, but the version is not pinned.

## Spec: `execution/video/lemo_bootstrap.py`

- **Inputs:** `--lock execution/video/lemo_opuscar.lock` (JSON with: repo, SHA, tree-tarball sha256, packs {file, size, sha256, mirror_url}, whisper {repo, revision, model.bin sha256}, `requirements.lock` from `uv pip compile --generate-hashes`, node≥20, ffmpeg≥7, chromium build), `--home` (path under 160 bytes), `--cache gs://…|drive`, `--packs`, `--check-only`, `--offline`.
- **Steps:**
  - Fetch the SHA with `git fetch --depth 1`. If that fails, fall back to the mirror tarball. Assert that HEAD equals the SHA and that `lemo.managed` is unset.
  - Install Python with `uv pip sync --require-hashes`, and Node with `npm ci`.
  - Fetch each pack mirror-first, with 3 retries and backoff, and verify it against **our** lock.
  - Download Whisper with `snapshot_download(revision=…)`.
  - Find Chromium or install it.
  - Write markers keyed by the lock hash, so a rerun does nothing.
- **Outputs:** `lemo.env` (LIB, PLAYWRIGHT_CHROME, WHISPER_MODEL=dir, HF_HUB_OFFLINE=1) and `manifest.json` (versions and hashes). Exit 0 = ready, 1 = a check failed, 2 = a fetch failed.

## Runbook outline

1. Bootstrap from cache, about 2 minutes.
2. `source lemo.env`.
3. Copy `src/` into the library, or set LIB.
4. Run `build.sh` with stage skips.
5. Run `film_eval --asr --expect-ssim ref`.
6. Swap the output in atomically and upload to Drive.
7. When a stage fails, look up its row in a symptom→fix table.

## Honest gaps

- I did not try a fresh-container rebuild, or whether a re-render matches pixel for pixel.
- I did not check that GitHub still serves bebbbe1 after a force-push.
- I did not check Playwright 1.63's expected Chromium build number.
- I did not measure the mirror cost, about 2.5 GB in total.
