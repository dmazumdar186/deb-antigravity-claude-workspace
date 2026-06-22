# Free-Claude-Code Proxy Integration

Workspace-local source-of-truth for the local FastAPI proxy that intercepts Claude Code's Anthropic-protocol calls and routes them to OpenRouter / Gemini / Z.AI direct / Ollama / etc. The mechanism that powers **personal mode** for Claude Code sessions.

Companion to `directives/infrastructure/model_chooser.md` (workspace-wide chooser) and `directives/infrastructure/glm_5_2_integration.md` (GLM specifics).

---

## Prior-art pass (per `~/.claude/rules/prior-art-first.md`)

Adopted upstream project: [github.com/Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code) — 36,320 stars, MIT license, active maintenance (last push 2026-06-20), Windows installer fix landed 2026-06-19 (commit `acf5885`).

**Pinned commit SHA**: `d281d52` ("Refactor messaging around explicit ports", 2026-06-20). Specific commit chosen rather than `main` to lock the trust boundary — upstream malicious updates cannot reach this workspace without an explicit `git pull && git checkout` on the operator's machine.

**Alternatives considered**:
- Build a minimal proxy ourselves (~100 LOC FastAPI + protocol translation): rejected; 17-provider routing + auto-compaction + Admin UI for $0 maintenance is better than reinventing.
- Skip the proxy, route only Python scripts (4 lines in `_call_openrouter`): rejected because the operator wants Claude Code sessions cost-tiered too (Q0=Both).
- Use other proxy projects (`1rgs/claude-code-proxy`, `raine/claude-code-proxy`, `fuergaosi233/claude-code-proxy`): rejected; Ali Sharer's project is the most general (17 providers vs 1-2).

---

## Architecture

```
Claude Code (claude.exe)
   │
   │ POST /v1/messages   (Anthropic protocol)
   │ ANTHROPIC_BASE_URL=http://localhost:8082
   │ ANTHROPIC_AUTH_TOKEN=freecc
   ▼
free-claude-code proxy (fcc-server, FastAPI on localhost:8082)
   │
   │ tier translation: claude-sonnet-4-6 → MODEL_SONNET → open_router/z-ai/glm-5.2
   │
   ▼
OpenRouter (https://openrouter.ai/api/v1)
   │
   ▼
Z.AI GLM-5.2 inference
```

Proxy intercepts the Anthropic protocol, rewrites the model name per the `.env` tier mapping, forwards to the chosen provider via the provider's native protocol. Response is streamed back in Anthropic-protocol shape so Claude Code is unaware of the substitution.

---

## Install location + pinned SHA

| Item | Value |
|---|---|
| Local clone | `C:\Users\deban\dev\free-claude-code\` |
| Pinned commit | `d281d52` |
| Install method | `py -m uv tool install --force C:\Users\deban\dev\free-claude-code` (from local clone, NOT from main) |
| Executables | `fcc-server.exe`, `fcc-claude.exe`, `fcc-codex.exe` (in `C:\Users\deban\.local\bin\`) |
| Proxy port | `8082` (default; persisted in `C:\Users\deban\dev\free-claude-code\.fcc-port`) |
| Server log | `C:\Users\deban\dev\free-claude-code\.fcc-server.log` |
| Admin UI | `http://127.0.0.1:8082/admin` (loopback-only) |

**Why outside the OneDrive workspace**: OneDrive sync on Python venv files churns aggressively. Putting the proxy at `~/dev/` matches the workspace convention (anneal is also there).

---

## .env config schema (proxy's, not workspace's)

Located at `C:\Users\deban\dev\free-claude-code\.env`. Generated 2026-06-22.

| Key | Value | Notes |
|---|---|---|
| `ANTHROPIC_AUTH_TOKEN` | `"freecc"` | Upstream default; the local auth value Claude Code passes |
| `FCC_OPEN_BROWSER` | `false` | Don't auto-open the admin UI |
| `OPENROUTER_API_KEY` | (mirrored from workspace `.env`) | The only currently-active backend |
| `GEMINI_API_KEY` | (mirrored from workspace `.env`) | Backup free path |
| `MODEL_OPUS` | `open_router/z-ai/glm-5.2` | All Claude tiers → GLM 5.2 in personal mode |
| `MODEL_SONNET` | `open_router/z-ai/glm-5.2` | (same) |
| `MODEL_HAIKU` | `open_router/z-ai/glm-5.2` | (same) |
| `MODEL` | `open_router/z-ai/glm-5.2` | Fallback for unmapped requests |
| `ENABLE_MODEL_THINKING` | `true` | Pass through reasoning blocks |
| `MESSAGING_PLATFORM` | `none` | No Discord/Telegram bridge |

**Sensitive content gate**: this proxy is for PERSONAL MODE only. PII / CV / leads / AM-scoped / client data MUST NOT touch this proxy. Use `claude-client.ps1` (Anthropic native) instead. The sensitivity guardrail in `~/.claude/rules/model-tier.md` and the `RuntimeError` raised by `call_model(sensitivity="sensitive")` are the runtime enforcement.

---

## Operator workflows

### Start the proxy (manual)

```powershell
nohup "$env:USERPROFILE\.local\bin\fcc-server.exe" > "$env:USERPROFILE\dev\free-claude-code\.fcc-server.log" 2>&1 &
```

Or simply run `claude-personal.ps1` — it auto-starts the proxy if down.

### Run Claude Code in personal mode

```powershell
.\execution\infrastructure\launchers\claude-personal.ps1
```

The launcher reads the port from `.fcc-port`, health-checks the proxy, auto-starts if needed, then launches Claude Code with the proxy as `ANTHROPIC_BASE_URL`.

### Switch back to client mode

```powershell
.\execution\infrastructure\launchers\claude-client.ps1
```

Or simply type `claude` directly — the workspace default is Opus 4.7 client mode.

### Interactive picker

```powershell
.\execution\infrastructure\launchers\claude-pick.ps1
```

Prompts client-vs-personal first.

---

## Trust boundary

The proxy is third-party Python code running locally with API keys in its `.env`. Same trust posture as any pip dependency. Specific mitigations:

1. **Pinned SHA**: upstream malicious updates cannot reach us without an explicit `git pull && git checkout` on the operator's machine.
2. **No `irm | iex` install**: install was done via `uv tool install --force <local_path>`, not via PowerShell remote-execution. (The original `scripts/install.ps1` would have pulled from `main`; we bypassed it.)
3. **Loopback-only Admin UI**: `127.0.0.1` only, no network exposure.
4. **MIT license + 36k stars + active maintenance**: standard signals.
5. **Sensitivity guardrail**: even if the proxy were compromised, the call site policy + the model-tier rule reject sensitive data from ever reaching it.

---

## Verify proxy is healthy

```powershell
curl http://localhost:8082/health
# Expected: {"status":"healthy"}
```

End-to-end smoke test (requires OR balance > $0):
```powershell
curl -X POST http://localhost:8082/v1/messages `
  -H "Authorization: Bearer freecc" `
  -H "anthropic-version: 2023-06-01" `
  -H "Content-Type: application/json" `
  -d '{"model":"claude-sonnet-4-6","max_tokens":30,"messages":[{"role":"user","content":"hi"}]}'
```

Without OR balance (current state 2026-06-22), the same call returns an Anthropic-protocol streaming response whose content is a 402 error from OR — that means **the routing chain is correct, only the balance is missing**.

---

## Upgrade path

To upgrade to a newer upstream version:

```bash
cd /c/Users/deban/dev/free-claude-code
git fetch origin
git log --oneline HEAD..origin/main | head -20   # review changes
git checkout <new_sha>                            # pick a specific SHA, not main
py -m uv tool install --force .
# Restart: kill fcc-server.exe and re-launch via claude-personal.ps1
```

Update the pinned SHA in this directive when upgrading.

---

## Revert procedure (full backout)

1. **Stop the proxy**: kill `fcc-server.exe` (Task Manager or `taskkill /IM fcc-server.exe`).
2. **Uninstall the tool**: `py -m uv tool uninstall free-claude-code`.
3. **Delete the local clone**: `rm -rf C:/Users/deban/dev/free-claude-code`.
4. **Delete the launchers**: `claude-personal.ps1`, `claude-client.ps1` (`.ps1` + `.sh`), and revert `claude-pick.ps1` to the pre-mode-prompt version.
5. **Revert the global rule**: `mv ~/.claude/rules/model-tier.md.bak-2026-06-22-2 ~/.claude/rules/model-tier.md`.
6. **Revert the chooser code**: drop the `mode` and `sensitivity` parameters from `call_model()` in `execution/modules/model_router.py`; drop the GLM tier branch in `execution/modules/model_registry.py`.

Each step is independent — partial revert is valid.

---

## Owed work

- **SAST grep** for `call_model(... mode="personal" ...)` × PII keyword in same function. Filed in `HARDENING_BACKLOG.md`.
- **Empirical test**: ship one ProdCraft video using personal mode (proxy → GLM-5.2) end-to-end. Validates GLM-5.2 quality on the operator's actual creative workload (per `~/.claude/rules/panel-pass.md` Karpathy lens). Gated on $5 OR top-up.
- **Z.AI direct backend**: `.env.example` has `ZAI_API_KEY` slot. If/when the operator signs up for Z.AI direct, add the key + `MODEL_SONNET=zai/glm-5.2` for one-fewer-hop routing.
