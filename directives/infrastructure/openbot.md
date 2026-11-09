# Directive: OpenBot (self-hosted AI-agent workspace server)

Workspace-local SOP for standing up [OpenBot](https://github.com/nightly-labs/openbot), a local-first Electron workspace for persistent AI agents (Claude Code, Codex, Gemini, Grok, OpenCode, Cursor, Copilot and others) with queues, agent-to-agent messaging, an embedded browser and an optional Computer Use. This directive covers the **headless Docker server**. The desktop app is a Releases download (see Windows notes). Companion to `directives/infrastructure/freellmapi.md`, which uses the same script pattern.

- **Vetted upstream sha:** `9f69821b597eb231d4c3a026f24cc5f0a5cd333e` (2026-11-09, package version 0.66.0).
- **License: PolyForm Noncommercial 1.0.0.** Only noncommercial use is free. ProdCraft client work counts as commercial and needs a paid licence (Settings → Billing, or licenses@openbot.run). Versions up to 0.1.11 are Apache-2.0.

## Goal

One reproducible command that clones or updates the upstream repo, which is used only for its `docker/compose.yaml` and `docker/seccomp.json`, pins the image tag, and starts the `ghcr.io/nightly-labs/openbot` container. It is idempotent: a re-run fast-forwards the clone, keeps an operator-edited override, and leaves the `openbot-data` volume alone.

## Inputs

- **No secrets are needed to start.** Sign-in is interactive with `openbot login` and an emailed one-time code. Provider sign-ins (Claude, Codex and the rest) are done from the app and stored in the `openbot-data` volume, never in this repo.
- Optional provider key env vars, set in the compose `environment:` only if wanted: `XAI_API_KEY` (names only, never commit values).
- Optional env overrides: `OPENBOT_DIR` (default `$HOME/dev/openbot`), `OPENBOT_REF` (git ref, pin to the vetted sha above), `OPENBOT_IMAGE_TAG` (default `latest`, e.g. `0.66.0`).
- Upstream instance tuning vars (used only by `docker/instances/`, not by this script): `OPENBOT_CPUS`, `OPENBOT_MEM`, `OPENBOT_DISK`, `OPENBOT_BACKUP_*`, `OPENBOT_AUTH_API_URL`.

## Tools / scripts

- `execution/infrastructure/setup_openbot.sh`
  - `bash execution/infrastructure/setup_openbot.sh`: clone/update, write the image override, `docker compose pull` + `up -d`
  - `--dry-run`: print the plan and change nothing
  - `--down`: `docker compose stop` (container and volume kept)
  - `--uninstall`: `openbot logout` then `docker compose down` (the volume is kept; the script prints the `docker volume rm` command)
- Upstream reference clone (untrusted, read-only): `/tmp/ext/nightly-labs_openbot`. Canonical docs: README "Install", `docs/docker.md`, `docs/self-hosted-server.md`.

## How it runs

- **Docker only.** It uses upstream's compose file: image `ghcr.io/nightly-labs/openbot:<tag>`, a custom `seccomp.json` (the Docker default seccomp profile plus user namespaces for the Electron sandbox), `no-new-privileges`, `shm_size: 1g`, `stop_grace_period: 60s`, and volume `openbot-data:/data`.
- **The container publishes no port.** It only connects out, to the OpenBot account API (Cloudflare), the providers, and Signal/TURN for remote clients. Its Team API listens on `127.0.0.1` inside the container. Leave `network_mode: host` commented out: it exposes the token-accepting listeners and the X displays to the host.
- The image tag is pinned through `docker/compose.override.yaml`, which upstream does not track, so ff-only pulls do not conflict. Delete its `# managed-by` line to stop the script rewriting it.
- The script never runs `scripts/install-server.sh` (upstream's `curl | sudo bash` path) and never runs `bun install`. Upstream's `postinstall`/`prepare` download Electron and install git hooks.

## Steps

1. `bash execution/infrastructure/setup_openbot.sh --dry-run`
2. `OPENBOT_REF=9f69821b597eb231d4c3a026f24cc5f0a5cd333e OPENBOT_IMAGE_TAG=0.66.0 bash execution/infrastructure/setup_openbot.sh`
3. `(cd ~/dev/openbot/docker && docker compose exec openbot openbot login)`: enter the email and the code.
4. Open the desktop app, the iPhone app or `https://openbot.run/app` with the same account, select the server, and connect a provider.
5. Optional: turn off product analytics in Settings → General (it is on by default and goes to the vendor's self-hosted OpenPanel).
6. Stop: `--down`. Remove: `--uninstall`.

## Outputs

- A running container `openbot` that appears in the account's server list. The machine itself gets no local URL or port.
- `$OPENBOT_DIR/docker/compose.override.yaml`, which holds only the image tag and no secrets.
- Docker volume `openbot-data`, which holds the account session, provider sign-ins, conversations, an encrypted DB and its keyring. Back it up as you would a home folder.

## Edge cases / learnings

- **Trust model:** agents run with `danger-full-access` and `approvalPolicy: never`. Inside the container that is limited to `/data`. The desktop app gets full access to the host. Run only trusted agents and tasks.
- **Phones home:** an OpenBot account is required for the server, analytics are on by default, and the app checks GitHub Releases for updates. Every provider talks to its own vendor.
- **Commercial use is not covered by the free licence.** Get a licence before any client-facing use.
- The container fails to start under Docker's default seccomp profile. Always keep `seccomp=./seccomp.json` from the same ref.
- A package installed outside `/data` (for example with `apt-get`) is lost when the container is updated. Install tools into `~/.local` as the `openbot` user.
- Upgrade: bump `OPENBOT_IMAGE_TAG` and re-run. OpenBot never downgrades its DB.
- **Windows:** the Docker path works from Git Bash or WSL with Docker Desktop. For a local desktop app, download the signed `OpenBot-*-x64.exe` from GitHub Releases and verify the checksum or build attestation first, because SmartScreen may warn. On Linux desktops on Ubuntu 23.10+ or Debian 13, the AppImage needs upstream's AppArmor profile. Never run it with `--no-sandbox`.
- skillspector was not run: OpenBot is not a Claude skill, and the CLI is not installed in the cloud container. The repo's `.agents/skills/` folder holds contributor dev skills only and is not installed.
