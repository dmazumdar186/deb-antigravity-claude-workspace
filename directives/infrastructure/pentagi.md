# Directive: PentAGI (self-hosted security-testing agent)

Workspace-local SOP for standing up [PentAGI](https://github.com/vxcontrol/pentagi) — a self-hosted, Docker-based autonomous agent for authorized security testing. It runs a web UI on `https://localhost:8443` and drives its agents inside sandbox containers it manages via the Docker socket.

## Authorized use (read first)

- **AUTHORIZED TARGETS ONLY.** Point PentAGI only at systems the operator **owns or has explicit written permission to test**. Scope-of-work / rules-of-engagement must exist before any flow is run against a target that is not the operator's own lab.
- This directive and its script cover **install and start only** — they launch no test against anything. What PentAGI is pointed at afterward is the operator's responsibility and must stay inside the authorization above.
- **Runs on the operator's own local machine**, not in ephemeral cloud sessions (claude.ai/code). It needs a persistent Docker daemon, the Docker socket, named volumes, and published sandbox ports — none of which survive a throwaway cloud container. On Windows use Docker Desktop (WSL2 backend) with Git Bash or WSL.

## Goal

One idempotent command that clones/updates PentAGI, creates `.env` from `.env.example`, replaces insecure default secrets with generated random values, wires an LLM provider from the environment, starts the stack, waits for the web UI, and prints the URL + default login.

## Inputs

- A reachable **Docker daemon** + Docker Compose (checked first; clear error if missing).
- **At least one LLM provider** in the environment (the script picks in this order):
  - `OPENROUTER_API_KEY` / `OPENROUTER_API_TOEKN` → custom OpenAI-compatible provider at `https://openrouter.ai/api/v1` using the bundled `/opt/pentagi/conf/openrouter.provider.yml`.
  - `FREELLMAPI_KEY` (+ optional `FREELLMAPI_URL`, default `http://host.docker.internal:3001/v1`) → local FreeLLMAPI router (see `freellmapi.md`).
  - `OPEN_AI_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` → native provider.
- Optional overrides: `PENTAGI_DIR` (default `$HOME/dev/pentagi`), `PENTAGI_REF`, `HEALTH_TIMEOUT`.

## Tools / scripts

- `execution/infrastructure/setup_pentagi.sh`
  - `bash execution/infrastructure/setup_pentagi.sh` — install / update / start
  - `--dry-run` — print the plan, change nothing
  - `--down` — `docker compose down` (named volumes kept)
- Upstream reference clone (untrusted, read-only): `/tmp/ext/vxcontrol_pentagi`. Canonical docs: README "Quick Start" / "Manual Installation" and "Custom LLM Provider Configuration".

## Steps

1. Ensure Docker Desktop / the Docker daemon is running on the local machine.
2. Export an LLM key (e.g. `export OPENROUTER_API_KEY=...`).
3. `bash execution/infrastructure/setup_pentagi.sh --dry-run` to preview.
4. `bash execution/infrastructure/setup_pentagi.sh` to clone/update, write `.env`, generate secrets, wire the provider, and `docker compose up -d`.
5. Open `https://localhost:8443`, accept the self-signed cert, log in as `admin@pentagi.com` / `admin`, and **change the password immediately**.
6. Confirm the operator has authorization for any target before running a flow.
7. Stop with `bash execution/infrastructure/setup_pentagi.sh --down`.

## Outputs

- Running stack (pentagi, pgvector/Postgres, scraper) with the web UI at `https://localhost:8443` (self-signed TLS).
- `$PENTAGI_DIR/.env` (mode 600, **gitignored, never committed**) with generated `COOKIE_SIGNING_SALT`, `PENTAGI_POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, plus the wired `LLM_SERVER_*` / provider key.
- The three `example.*.provider.yml` files the compose file mounts (created so Docker does not mount directories in their place).
- Printed URL, default login, and the authorized-use + sandbox-port reminders.

## Resource minimums (from README System Requirements)

- Docker + Docker Compose, **2 vCPU minimum, 4 GB RAM minimum, 20 GB free disk**, internet access for image pulls. Graphiti/Neo4j and Langfuse add-ons want substantially more (Neo4j alone defaults to 4 CPU / 4 GB) and are off by default here.

## How to stop

- `bash execution/infrastructure/setup_pentagi.sh --down` (keeps named volumes / data).
- Full teardown including data: `cd $PENTAGI_DIR && docker compose down -v` (destructive — asks nothing; only run deliberately).

## Edge cases / learnings

- **Docker daemon required for a real run.** A real `up` hard-fails early if `docker info` or `docker compose version` fails — PentAGI needs the Docker socket to spawn sandboxes, so there is no non-Docker path. **`--dry-run` is exempt:** it only warns if the daemon is unreachable, so you can preview the plan on any machine (verified by `tests/test_infra_setup.sh`).
- **`--dry-run` is a pure offline preview.** It performs no clone, no network, no file writes, and needs neither Docker nor the LLM key — it just prints what a real run would do.
- **No cloud sessions.** Do not attempt this inside claude.ai/code — no persistent daemon, no socket, volumes vanish. Operator's machine only.
- **Sandbox ports are exposed.** Each flow publishes two TCP ports in the `DOCKER_PORTS_BASE` window (default `28000`–`29999`) on `DOCKER_PUBLIC_IP`, which the setup script pins to `127.0.0.1` (set `DOCKER_PUBLIC_IP=0.0.0.0` to expose; upstream's default `0.0.0.0` = every host interface), and Docker routes around `ufw`. Firewall the host (or the `DOCKER-USER` chain) if it is not already isolated. `DOCKER_NETWORK=host` exposes sandbox listeners with no mapping at all.
- **Secrets only in `.env`.** The script replaces `.env.example` defaults (`salt`, `postgres`, `devpassword`) only when they still hold the default, so re-runs do not churn a hardened `.env`. An existing `.env` is left untouched (no secret regen, no LLM rewrite).
- **`OPENROUTER_API_TOEKN`** is a known upstream typo; the script accepts both spellings.
- **Custom-provider tool-call errors** (`Failed to parse tool call arguments as JSON`, `failed to select primary docker image via llm call`) mean the backend emits malformed tool calls — validate with `docker exec -it pentagi /opt/pentagi/bin/ctester` before blaming PentAGI.
- **Change the default `admin@pentagi.com` / `admin` password on first login.** Password reset later is via the installer maintenance menu.
- **Self-signed TLS:** the health wait uses `curl -sk`; a browser will warn on first visit.
