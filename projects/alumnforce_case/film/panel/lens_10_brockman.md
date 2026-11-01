# Lens 10 (Brockman): can it run unattended for 30 days?

**Verdict: NOT CLEAR.** Today it can be reproduced by hand in this container. A fresh container next month would depend on unpinned or unmirrored fetches. No bootstrap, lock or durable cache exists.

## External fetches (what is pinned, and what happens on failure)

- **Git clone of the toolkit, ~219 MB.** Pinned to a SHA, with no mirror. If upstream force-pushes, the SHA can disappear.
- **pip, ~0.5 GB.** No versions, no hashes (`requirements*.txt`). It drifts silently; the `av<19` comment shows drift has broken it once already.
- **npm.** Lockfile with sha512, but installed with `npm install`, not `npm ci`.
- **Chromium, 261 MB.** Supplied by the container image (build 1243). If it is missing or a different build, the run fails or the frames differ.
- **Voice model and three sample packs, 1.28 GB.** sha256 is pinned, but the `assets` release tag is mutable. A changed file is a hard stop.
- **Whisper `small.en`, 462 MB.** No revision pinned. If it cannot be fetched, the speech check exits 2.

## Findings

**High**
- **H1. Nothing survives a new container.** Versions are recorded only as prose (`BUILD_LOG.md:23-27`). The wrapper and lock recommended in `LEMO_TEARDOWN.md:182,251` were never built. Fix: build the bootstrap below.
- **H2. The final encode overwrites the delivered film in place.** `src/build.sh:30-31` writes `ffmpeg -y` straight to `trusted-segments.mp4`. A timeout mid-encode truncates the good file. Fix: render to a temp file, check it with ffprobe and `film_eval`, then `mv`.
- **H3. The checksum error tells the agent to unpin.** `fetch.sh:99-100` says to refresh with setup.sh or git pull. Under the no-HITL rule an agent will follow that onto upstream main. Fix: verify against our own lock and fetch from our mirror first.

**Medium**
- **M1. A rerun redoes every stage, with no resume.** It takes about 8 minutes. `video.mjs:34` deletes its segments when interrupted, so the next render starts at frame 0. The other ~41 of the 49 minutes were agent authoring, which cannot be replayed. Fix: skip stages whose input hashes have not changed, and put a timeout on each stage.
- **M2. `film_eval.py:51` points the speech check at `/tmp/ext/venv`.** In a fresh container the check is skipped and the report can still pass. Fix: read the path from `lemo.env`, and fail when `--asr` cannot run.
- **M3. ffmpeg 6.1 vs the 7+ the toolkit asks for (`TECHNIQUE.md:17`).** It did not bite us: the length check in `mux.sh:51-56` passed (`BUILD_LOG.md:25`). The risk is still there, because `apad` (`mux.sh:74`) could hide an under-reported length. Fix: require 7.x, or a pinned static build with a hash check.
- **M4. Re-renders will not be byte-identical.** Chromium, Kokoro and libx264 builds all vary, so `--expect-sha256` cannot work as a gate. Fix: compare against a reference with SSIM.

**Low**
- **L1. No dead-man alarm or run log.** Fix: write one JSONL line per stage to `.tmp/lemo_runs/`.
- **L2. Python version is not pinned.** The build ran on 3.13.18, not the 3.11 the cloud default suggests. Fix: pin it in the lock.

## Spec: `execution/video/lemo_bootstrap.py`

**Inputs**
- `--lock lemo_opuscar.lock`, containing: the toolkit SHA and tarball sha256; each pack's size, sha256 and mirror URL; Whisper's revision and sha256; a hashed `requirements.lock` (`uv pip compile --generate-hashes`); minimum ffmpeg version (7).
- `--home` (path under 160 bytes), `--cache` (durable bucket), `--packs`, `--check-only`.

**Steps** (each is skipped when a marker for the same lock hash exists, so reruns are safe)
1. Fetch the SHA (`git fetch --depth 1`), or fall back to the mirror tarball. Assert HEAD equals the SHA and `lemo.managed` is unset.
2. Install Python packages with `uv pip sync --require-hashes`, and Node packages with `npm ci`.
3. Fetch the packs from the mirror first, with 3 retries and backoff, and verify them against our lock.
4. Fetch Whisper at the pinned revision.

**Outputs**
- `lemo.env` (LIB, PLAYWRIGHT_CHROME, WHISPER_MODEL, HF_HUB_OFFLINE=1) and `manifest.json`.
- Exit codes: 0 ready, 1 a check failed, 2 a fetch failed.

## Runbook outline

1. Run the bootstrap.
2. `source lemo.env`.
3. Run `build.sh`.
4. Run `film_eval --asr`.
5. Swap the new file in atomically and upload it.
6. Use the symptom-to-fix table for each stage.

## Honest gaps

- I did not try a rebuild in a fresh container.
- I did not check whether GitHub still serves bebbbe1 after a force-push.
- I did not check which Chromium build Playwright 1.63 expects.
