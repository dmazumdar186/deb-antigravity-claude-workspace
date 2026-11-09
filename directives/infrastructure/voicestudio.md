# Directive: VoiceStudio (self-hosted local voice studio)

Workspace-local SOP for standing up [VoiceStudio](https://github.com/debpalash/VoiceStudio) (formerly OmniVoice Studio). It is a local TTS / voice-cloning / voice-design / transcription / dubbing app. It serves a web UI, an OpenAI-compatible audio API (`/v1/audio/speech`, `/v1/audio/transcriptions`) and an MCP endpoint (`/mcp`) on `:3900`. Inference runs locally; model weights download from Hugging Face only when you install a model. Companion pattern: `directives/infrastructure/freellmapi.md`.

- **License:** AGPL-3.0-only (`LICENSE`, `LICENSE-NOTICE.md`). Free for internal and commercial use. A modified version served to others over a network must offer its source. Closed-source embedding needs a paid commercial license. Model weights carry their own licenses.
- **Last vetted upstream commit:** `5aaadd51d3172fccae665bc68cf9304aa2946f98` (2026-11-09). Container image `ghcr.io/debpalash/voicestudio:stable`.

## Goal

One reproducible command that clones/updates VoiceStudio, starts its Docker Compose stack on loopback, waits for health and prints what the operator does next. Idempotent: re-runs fast-forward the code, keep the existing `.env`/API key and recreate only changed containers.

## Inputs

- **Nothing is required to start.** `OMNIVOICE_API_KEY` (the admin key the web UI asks for) is generated on the first run into the clone's `.env`.
- Optional: `HF_TOKEN` (exported in your shell, only for gated Hugging Face models).
- Env overrides: `VOICESTUDIO_DIR` (default `$HOME/dev/voicestudio`), `VOICESTUDIO_REF` (pin a branch/tag/SHA), `VOICESTUDIO_PROFILE` (`cpu`|`gpu`|`rocm`, default `cpu`), `VOICESTUDIO_IMAGE` (e.g. `ghcr.io/debpalash/voicestudio:0.5.6` to pin the image), `HEALTH_TIMEOUT` (default 600 s).

## Tools / scripts

- `execution/infrastructure/setup_voicestudio.sh`
  - no flag: install / update / start
  - `--dry-run`: print the plan and change nothing
  - `--down`: stop the stack (the data volume is kept)
  - `--uninstall`: stop the stack and print the `rm -rf` / `docker volume rm` commands, which you run yourself. Nothing is deleted automatically (security rule).
  - `--with-skill`: also copy upstream's `skills/voicestudio/SKILL.md` into `.claude/skills/voicestudio/`. This runs only after `skillspector scan --no-llm -f json` passes. The copy aborts if the scan finds HIGH/CRITICAL issues or if the CLI is missing.
- Untrusted reference clone (read-only): `/tmp/ext/debpalash_VoiceStudio/src`. Canonical docs: README "Docker" section and `docs/install/docker.md`.

## How it runs

- **Docker only.** The script uses upstream's `deploy/docker-compose.yml` with project name `voicestudio`, `--env-file $DIR/.env` and the chosen profile's service (`omnivoice` / `omnivoice-gpu` / `omnivoice-rocm`). Data and models persist in the volume `voicestudio_omnivoice-data`.
- **Loopback only.** Upstream publishes the port as `127.0.0.1:3900:3900`. Do not change this to `0.0.0.0` without HTTPS and a trusted network.
- **Analytics hard-off.** Upstream analytics are opt-in (Supermetry, consent prompt, default off). The script also writes an untracked `$DIR/.voicestudio.override.yml` that sets `OMNIVOICE_ANALYTICS_DISABLED=1`, the upstream kill switch.
- Health: `GET /health` (unauthenticated, in upstream's startup-exempt list).
- GPU profile needs the NVIDIA Container Toolkit. The ROCm profile needs `/dev/kfd` and `/dev/dri` (amdgpu driver).

## Steps

1. `bash execution/infrastructure/setup_voicestudio.sh --dry-run` to preview.
2. `bash execution/infrastructure/setup_voicestudio.sh` (optionally `VOICESTUDIO_PROFILE=gpu`).
3. Wait for `http://127.0.0.1:3900/health`. The script waits for you. The first image pull is several GB.
4. Open `http://127.0.0.1:3900`, paste the key from `$VOICESTUDIO_DIR/.env` and install a model when the app asks.
5. Use it from agents: add the MCP server at `http://127.0.0.1:3900/mcp` (HTTP transport), or call the OpenAI-compatible endpoints.
6. Stop with `--down`.

## Outputs

- A running service at `http://127.0.0.1:3900` (UI) with `/v1/audio/*` and `/mcp`.
- `$VOICESTUDIO_DIR/.env` holding `OMNIVOICE_API_KEY` (mode 600). It is outside this repo, and upstream's `.gitignore` covers it.
- `$VOICESTUDIO_DIR/.voicestudio.override.yml` (regenerated on every run).

## Edge cases / learnings

- **Vetting (2026-11-09):**
  - Upstream's `curl -fsSL https://voicestudio.sh/install | sh` and `irm .../install.ps1 | iex` installers are deliberately **not** used. Docker images and Releases installers are the reviewed paths.
  - The Dockerfile only apt-installs ffmpeg/libsndfile/curl/build-essential, and it does not pipe a remote script into a shell.
  - `.gitmodules` pulls one gallery submodule. The script never runs `--recurse-submodules`, and the submodule is not needed for Docker.
  - The repo also ships maintainer agent material (`CLAUDE.md`, `.claude/`, `.agents/`, `skills/`). This only matters if you open the clone in Claude Code, so do not open it as a working directory.
  - `skillspector` was not installed in the vetting container, so the skill is **not** installed in this repo. Use `--with-skill` after installing the CLI.
- **Compose needs the key even for `down`.** `${OMNIVOICE_API_KEY:?}` is interpolated for every command. If `.env` is missing, `--down` writes a placeholder, and the next `up` replaces it.
- **The image tag is independent of `VOICESTUDIO_REF`.** The compose file pins `:stable`. For a fully reproducible deploy, set both `VOICESTUDIO_REF` and `VOICESTUDIO_IMAGE=...:X.Y.Z`.
- **Upgrading from an old `omnivoice` container:** follow upstream `docs/install/docker-data-recovery.md` before recreating it.
- **ARM64:** use `VOICESTUDIO_IMAGE=ghcr.io/debpalash/voicestudio:stable-cuda-arm64` (NVIDIA only). On Apple Silicon, use the native macOS app.
- **Windows:** Docker Desktop + Git Bash or WSL runs this script unchanged. For a no-Docker setup, use the `.exe` installer from GitHub Releases rather than `irm | iex`. Experimental ROCm instructions are in upstream's `docs/install/windows-rocm.md`.
- **Cloud containers:** no Docker daemon, so only `--dry-run` works there.
