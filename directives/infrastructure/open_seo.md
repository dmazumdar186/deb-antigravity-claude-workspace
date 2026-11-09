# Directive: OpenSEO (self-hosted SEO suite + MCP)

Workspace-local SOP for standing up [OpenSEO](https://github.com/every-app/open-seo) — an MIT-licensed, open-source Semrush/Ahrefs alternative (keyword research, rank tracking, competitor insights, backlinks, site audits, AI visibility) with a built-in MCP server at `/mcp`. Pay-as-you-go: you bring your own DataForSEO key. Companion to `directives/infrastructure/freellmapi.md` (same install pattern; OpenSEO can use FreeLLMAPI as its OpenAI-compatible backend via `OPENROUTER_BASE_URL`).

Vetted at upstream commit `46b815be34723e46ceeefe9b2b907bb62b62fd76` (2026-11-09). License: MIT (Ben Senescu).

## Goal

One reproducible command that clones/updates OpenSEO, brings up upstream's Docker "standalone" stack (`deploy/standalone/compose.yaml`), waits for health, and prints exactly what the operator must do next. Idempotent: re-running fast-forwards the code and preserves the existing `.env` and data volumes.

## Inputs

- **None required to start.** `STORAGE_SECRET_KEY` is generated on first run; the stack's `init` service generates the rest of its secrets into the `config` volume.
- **Needed for data (operator fills in `deploy/standalone/.env`, never in this repo):** `DATAFORSEO_API_KEY` (base64 of `login:password`; paid per request at DataForSEO).
- **Optional:** `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` (SAM agent), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (Search Console/Analytics), `CONTEXT_API_KEY` (JS rendering in audits), `GOOGLE_MAPS_API_KEY` (Local SEO map), `CRAWLER_ACCESS_SECRET`. Stack-level: `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `AUTH_MODE` (`password` default | `local_noauth`), `BETTER_AUTH_URL`, `PORT`.
- Script env overrides: `OPEN_SEO_DIR` (default `$HOME/dev/open-seo`), `OPEN_SEO_REF` (pin, e.g. the sha above), `OPEN_SEO_IMAGE` (default `ghcr.io/every-app/open-seo-standalone:latest`), `OPEN_SEO_PORT` (default **3011**, chosen so it does not collide with FreeLLMAPI on 3001), `HEALTH_TIMEOUT` (default 240).

## Tools / scripts

- `execution/infrastructure/setup_open_seo.sh`
  - `bash execution/infrastructure/setup_open_seo.sh` — install / update / start
  - `--dry-run` — print the plan, change nothing
  - `--down` — stop the stack (volumes kept)
  - `--uninstall --yes` — `docker compose down -v` + delete the clone (destroys data and generated secrets; back up first)
- Upstream reference clone (untrusted, read-only): `/tmp/ext/every-app_open-seo`. Canonical docs: `docs/SELF_HOSTING_DOCKER.md`, `docs/DATAFORSEO_API_KEY.md`.

## How it runs

- **Docker only** (upstream's other self-host path is a Cloudflare Workers deploy, `docs/SELF_HOSTING_CLOUDFLARE.md`, not scripted here). Services: `storage` (RustFS, digest-pinned), `runtime` (celld Workers runtime, 2 GiB mem limit), `init` (one-shot: secrets, migrations), `crawl-gateway` (blocks private-address crawls), `web` (Nginx, digest-pinned).
- Only Nginx is published, on `127.0.0.1:${PORT}`; everything else stays on the Compose network.
- The script always calls `docker compose -f deploy/standalone/compose.yaml --env-file deploy/standalone/.env` so it never depends on a shell-exported `COMPOSE_FILE`.
- Health: `GET /api/health` (succeeds once auth is configured and the DB answers).

## Steps

1. `bash execution/infrastructure/setup_open_seo.sh --dry-run` to preview.
2. `bash execution/infrastructure/setup_open_seo.sh` to clone/update, write `.env` (if absent) and start.
3. Open `http://localhost:3011` **immediately** and create the admin account — registration closes after the first account.
4. Put `DATAFORSEO_API_KEY` (and optionally `OPENROUTER_API_KEY`) into `$OPEN_SEO_DIR/deploy/standalone/.env`, then `docker compose -f … --env-file … up -d --force-recreate init web crawl-gateway`.
5. Wire Claude Code: add an HTTP MCP server at `http://localhost:3011/mcp` (OAuth sign-in or an API key from Settings). Do not commit the key or add it to `.mcp.json`.
6. Stop when done: `--down`.

## Outputs

- Running app at `http://localhost:3011`, MCP at `/mcp`.
- `$OPEN_SEO_DIR/deploy/standalone/.env` (mode 600, outside this repo) with `STORAGE_SECRET_KEY`.
- Docker volumes `openseo-standalone_{storage,runtime,config,web-config}` (config holds generated secrets — include it in backups).

## Edge cases / learnings

- **Spend:** every keyword/backlink/SERP/audit call bills the operator's DataForSEO account (and OpenRouter if set). No spend happens until a key is added and a feature is used; treat MCP calls from agents as paid calls (budget guard + ledger per CLAUDE.md).
- **Phone-home:** the standalone stack hard-codes `OPENSEO_TELEMETRY_DISABLED=true` / `DO_NOT_TRACK=1` (`scripts/celld/runtime/configure.mjs`). The *legacy* root `compose.yaml` image sends an anonymous PostHog heartbeat unless `OPENSEO_TELEMETRY_DISABLED=1` — we do not use it. Outbound traffic otherwise goes only to the providers you configure and to sites you crawl.
- **Images:** `open-seo-standalone:latest` floats; pin with `OPEN_SEO_IMAGE=ghcr.io/every-app/open-seo-standalone:<tag>` for reproducibility. RustFS and Nginx are digest-pinned upstream.
- **Updates:** back up first (`node scripts/celld/backup.mjs backup ./backups/<date>` from the clone), then re-run the script. Migrations run in `init` and are not reversible by downgrading the image.
- **Re-run safety:** existing `.env` with a real `STORAGE_SECRET_KEY` is preserved (changing it after first start breaks storage access); a placeholder `replace-with…` value is regenerated. Pull is fast-forward only.
- **No sign-in mode:** `AUTH_MODE=local_noauth` only on a private network/Tailscale; default `password` mode is correct for this workspace.
- **Repo also ships agent assets:** `.claude-plugin/marketplace.json` → plugin `openseo` (12 SEO workflow skills wired to the **hosted** openseo.so MCP) and contributor skills in `.claude/skills/`. Not installed here: they target the hosted paid service; SkillSpector CLI was unavailable at vetting time. Scan before any install.
- **Resources:** Docker needs ≥ 4 GiB RAM; runtime needs 4 KiB memory pages (`getconf PAGESIZE` = 4096).
- **Windows:** run the script from Git Bash or WSL with Docker Desktop running (WSL2 backend, ≥ 4 GiB assigned). `openssl` ships with Git Bash; the script falls back to `/dev/urandom` otherwise. `node` is only needed for the optional backup script.
