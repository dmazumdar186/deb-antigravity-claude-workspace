# Lens 10 (Brockman): 30 days unattended?

**Verdict: NOT CLEAR.** It reproduces only by hand in this container. Nothing pinned, mirrored or cached survives a fresh one.

## Fetches

- Git clone, 219 MB: SHA-pinned, no mirror.
- pip, 0.5 GB: unpinned, no hashes (`requirements*.txt`); it has broken before (the `av<19` comment).
- npm: lockfile, but `npm install`, not `npm ci`.
- Chromium, 261 MB: comes with the container image.
- Voice model + 3 sample packs, 1.28 GB: sha256 pinned, but the release tag can change, and a changed file stops the build.
- Whisper `small.en`, 462 MB: no revision pinned.

## Findings

**High**
- **H1. No bootstrap, lock or cache.** Versions exist only as prose (`BUILD_LOG.md:23-27`). The recommended wrapper (`LEMO_TEARDOWN.md:182`) was never built. Fix: build the spec below.
- **H2. The final encode overwrites the delivered film** (`src/build.sh:30-31`, `-y`). A timeout leaves a truncated file. Fix: write to a temp file, check it, then `mv`.
- **H3. The checksum error tells the agent to `git pull`** (`fetch.sh:99-100`). Under no-HITL, an agent would follow that and unpin. Fix: verify against our own lock and fetch from our mirror first.

**Medium**
- **M1. No resume or stage skips.** A rerun takes about 8 minutes, and an interrupted render restarts at frame 0 (`video.mjs:34`). Fix: skip stages by input hash, and give each stage a timeout.
- **M2. `film_eval.py:51` hardcodes `/tmp/ext/venv`.** Without that venv, ASR is SKIPPED and the eval can still pass. Fix: read the path from `lemo.env`, and FAIL if `--asr` cannot run.
- **M3. ffmpeg 6.1 vs the required 7+** (`TECHNIQUE.md:17`). It did not bite us (`BUILD_LOG.md:25`), but `apad` (`mux.sh:74`) could hide the length bug. Fix: require 7.x.
- **M4. Re-renders won't be byte-identical,** so `--expect-sha256` can't be the gate. Fix: compare with SSIM.

**Low**
- No dead-man alarm and no per-stage run log.
- Python is unpinned (the venv ran 3.13, not 3.11).

## Spec: `execution/video/lemo_bootstrap.py`

- **Inputs:** `--lock`, `--home`, `--cache`, `--packs`, `--check-only`. The lock holds:
  - the toolkit SHA
  - each pack's sha256 and mirror URL
  - the Whisper revision
  - hashed `requirements.lock`
- **Steps:**
  1. Fetch the SHA and assert `HEAD` equals it.
  2. Run `uv pip sync --require-hashes`.
  3. Run `npm ci`.
  4. Fetch each pack mirror-first, with 3 retries.
  5. Mark each step done with the lock hash, so reruns skip it.
- **Outputs:** `lemo.env` and `manifest.json`. Exit codes: 0 = ready, 1 = a check failed, 2 = a fetch failed.

## Runbook

1. Run the bootstrap.
2. Source `lemo.env`.
3. Run `build.sh`.
4. Run `film_eval --asr`.
5. Swap the new file in atomically, then upload.
6. Keep a symptom-to-fix table.

## Honest gaps

I did not:
- run a rebuild in a fresh container
- check that bebbbe1 survives a force-push
- check which Chromium build Playwright 1.63 expects
