# Directive: FreeLLMAPI (self-hosted free-tier LLM router)

Workspace-local SOP for standing up [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) — an OpenAI-compatible router that stacks many providers' free tiers behind one local endpoint on `:3001`, with a web dashboard for keys, fallback chains and analytics. Companion to `directives/infrastructure/free_cc_proxy.md` (a different proxy) and `directives/infrastructure/pentagi.md` (consumes this as an LLM backend).

## Goal

One reproducible command that clones/updates FreeLLMAPI, brings it up (Docker Compose preferred, Node fallback), waits for health, and prints exactly what the operator must do next. Idempotent: re-running updates the code and preserves the existing `.env`/encryption key.

## Inputs

- **None required to start.** The encryption key is generated on first run.
- Provider API keys (Google, Groq, Cerebras, etc.) are added later **in the dashboard**, never on disk by us.
- Optional env overrides: `FREELLMAPI_DIR` (default `$HOME/dev/freellmapi`), `FREELLMAPI_REF`, `FREELLMAPI_MODE` (`docker`|`node`), `PORT` (default 3001), `HEALTH_TIMEOUT`.

## Tools / scripts

- `execution/infrastructure/setup_freellmapi.sh`
  - `bash execution/infrastructure/setup_freellmapi.sh` — install / update / start
  - `--dry-run` — print the plan, change nothing
  - `--down` — stop the stack (data volume kept)
- Upstream reference clone (untrusted, read-only): `/tmp/ext/tashfeenahmed_freellmapi`. Canonical docs: README "Quick start" and `docs/en/install/01-install.md`.

## How it runs

- **Docker mode (default when a daemon is reachable):** `docker compose up -d` from the clone; image `ghcr.io/tashfeenahmed/freellmapi:latest`, pull with local-build fallback. SQLite persists in the named volume `freellmapi-data`. Compose healthcheck + our wait both poll `GET /api/ping` (unauthenticated).
- **Node mode (fallback, needs Node 20+):** `npm install && npm run build`, then `node server/dist/index.js` backgrounded with a pidfile. Server + dashboard both serve on `:3001`.
- Bound to `127.0.0.1` by default. For LAN access set `HOST_BIND=0.0.0.0` (trusted networks only — single-user, guarded only by the unified key).

## Steps

1. Run `bash execution/infrastructure/setup_freellmapi.sh --dry-run` to preview the plan.
2. Run `bash execution/infrastructure/setup_freellmapi.sh` to clone/update, write `.env` (if absent), and start the stack.
3. Wait for the health check on `http://localhost:3001/api/ping` (the script does this).
4. Open the dashboard, add provider keys, reorder the Fallback Chain, copy the unified API key.
5. Wire a client: `npx freellmapi setup-claude --url http://localhost:3001 --api-key <key>` or `npx freellmapi launch`.
6. Stop when done: `bash execution/infrastructure/setup_freellmapi.sh --down`.

## Outputs

- Running router at `http://localhost:3001` (dashboard) / `http://localhost:3001/v1` (OpenAI base URL).
- `$FREELLMAPI_DIR/.env` with `ENCRYPTION_KEY` (mode 600) — **gitignored, never committed.**
- Printed next steps: add provider keys in the dashboard, grab the unified key, then `npx freellmapi setup-claude --url http://localhost:3001 --api-key <key>` or `npx freellmapi launch`.

## Edge cases / learnings

- **Secrets:** `ENCRYPTION_KEY` stays in the clone's `.env` only. Provider keys live in the dashboard's SQLite (AES-256-GCM at rest). Rotating `ENCRYPTION_KEY` requires `npm run rotate-encryption-key` first — a bare change breaks every stored key. See `docs/en/install/01-install.md#rotating-the-encryption-key`.
- **Re-run safety:** existing `.env` with a non-empty `ENCRYPTION_KEY` is preserved; a fast-forward-only pull avoids clobbering local edits.
- **Container can't reach providers but host can:** a host proxy on `127.0.0.1` is not the container's loopback — set `PROXY_URL=socks5h://host.docker.internal:7890`. IPv6-only hosts need IPv6 enabled in Docker.
- **Health path is `/api/ping`,** not `/health` (which is auth-gated).
- **Windows:** the Docker steps work in Git Bash / WSL; the native `.exe` desktop installer from Releases is the easiest non-Docker path.
