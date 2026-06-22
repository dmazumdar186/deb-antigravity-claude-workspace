# Universal Model Chooser

Click-of-a-button switching between GLM 5.2, Opus, Sonnet, GPT-4o, and Gemini for any project in this workspace. Two surfaces:

- **Python dispatcher** (`execution/modules/model_router.py`) — one function `call_model(alias, ...)` that routes per-call. Use from any script.
- **Claude Code session launchers** (`execution/infrastructure/launchers/claude-*.ps1` and `.sh`) — flip the entire Claude Code session to a different model via `ANTHROPIC_BASE_URL` swap, the pattern from Nick Saraev's video (KAnDbJhNJ4E @ 7:18).

---

## Available aliases

| Alias | Model ID | Native provider | Sensitivity | Per-token cost |
|---|---|---|---|---|
| `opus` | `claude-opus-4-7` | Anthropic | sensitive_ok | $$$$ (premium) |
| `sonnet` | `claude-sonnet-4-6` | Anthropic | sensitive_ok | $$ (default) |
| `gpt`, `gpt4o` | `gpt-4o` | OpenAI | sensitive_ok | $$$ |
| `o1` | `o1` | OpenAI | sensitive_ok | $$$$$ |
| `gemini` | `gemini-2.5-flash` | Google (FREE tier 250 RPD) | sensitive_ok | $0 |
| `gemini-pro` | `gemini-2.5-pro` | Google | sensitive_ok | $$ |
| `glm`, `glm-5.2` | `z-ai/glm-5.2` | Z.AI (OR only) | **public-only** | $ (~1/30th of Opus) |
| `glm-4.7` | `z-ai/glm-4.7` | Z.AI (OR only) | **public-only** | $ (cheapest) |

Sensitivity rule: anything tagged `public` (the GLM family) must NOT receive PII / CV / leads / AM / client data. Z.AI is China-jurisdiction. See `~/.claude/rules/model-tier.md` Exhibit C.

---

## Python dispatcher

### CLI one-shot

```bash
# List aliases:
py execution/modules/model_router.py --list

# One-shot prompt:
py execution/modules/model_router.py gemini "How rainbows form"
py execution/modules/model_router.py glm "Build a 3D nebula scene in three.js" --max-tokens 4000
py execution/modules/model_router.py opus "Refactor this Python function for clarity" --max-tokens 2000

# Force OR route even when a native key exists:
py execution/modules/model_router.py sonnet "..." --via-openrouter
```

### Importable from any workspace script

```python
from execution.modules.model_router import call_model

result = call_model(
    "glm",
    system="You are a creative coder. Output a single self-contained HTML file.",
    user="Interactive explainer: how DNS resolution works.",
    max_tokens=4000,
)
print(result["text"])
print(f"routed via {result['provider']} ({result['model']})")
```

Returns `{"text": str, "model": str, "provider": str, "usage": dict | None}`.

### Routing logic (per alias)

The dispatcher picks the cheapest available route:

1. If the alias has a `native_provider` and that provider's key is set in `.env` → use that direct SDK (fastest, no OR markup).
2. Else fall back to OpenRouter using the `or_model` mapping.
3. GLM is OR-only by design (no Z.AI key in `.env` yet; the workspace has not provisioned one).

Pass `via_openrouter=True` (or `--via-openrouter`) to force OR for cost-accounting consistency across all providers.

---

## Claude Code session launchers

These launchers spawn a NEW Claude Code session whose underlying LLM is the named model. The pattern is `ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1` + `ANTHROPIC_AUTH_TOKEN=<OR key>` + `claude --model <slug>`.

### PowerShell (Windows native)

```powershell
.\execution\infrastructure\launchers\claude-glm.ps1      # GLM 5.2 (via OR)
.\execution\infrastructure\launchers\claude-gpt.ps1      # GPT-4o (via OR)
.\execution\infrastructure\launchers\claude-gemini.ps1   # Gemini 2.5 Pro (via OR)
.\execution\infrastructure\launchers\claude-sonnet.ps1   # Sonnet 4.6 (Anthropic native)
.\execution\infrastructure\launchers\claude-opus.ps1     # Opus 4.7 (Anthropic native)
```

### Bash (Git Bash on Windows)

```bash
./execution/infrastructure/launchers/claude-glm.sh
./execution/infrastructure/launchers/claude-gpt.sh
./execution/infrastructure/launchers/claude-gemini.sh
./execution/infrastructure/launchers/claude-sonnet.sh
./execution/infrastructure/launchers/claude-opus.sh
```

### True click-of-a-button (put launchers on PATH)

Add `<workspace_root>\execution\infrastructure\launchers` to your PowerShell PATH so you can just type `claude-glm` anywhere:

```powershell
# Permanent — add to your $PROFILE:
$env:PATH = "C:\Users\deban\OneDrive\Documents\AntiGravity Project Space\execution\infrastructure\launchers;$env:PATH"
```

Or create Windows Start-menu shortcuts pointing to each `.ps1` for actual click-of-a-button launch.

---

## Provider availability today (2026-06-22)

Live-tested during chooser build:

| Route | Status | Note |
|---|---|---|
| Gemini direct (free tier) | ✅ WORKS | 250 RPD / 10 RPM. The only route usable without spend today. |
| Anthropic direct (Opus / Sonnet) | ❌ BLOCKED | Credit balance = 0; needs top-up. Same constraint as memory's `project_cv_optimizer`. |
| OpenAI direct (GPT / o1) | ❌ BLOCKED | OPENAI_API_KEY is restricted; missing `model.request` scope. Update scope to "All" (see memory `feedback_openai_audio_scope`). |
| OpenRouter (GLM / any via OR) | ❌ BLOCKED | OR balance = 0; needs $5+ top-up. |

So today, **`gemini` is the only alias that succeeds end-to-end without operator action.** All other aliases will error with a clear credit/scope message — the dispatcher and launchers are correct and ready, the *budget* is what's missing.

---

## To unblock the other aliases

| Want | Action | Cost |
|---|---|---|
| Use GLM, GPT, Sonnet, Opus via OR | Top up OpenRouter ($5 min) | ~$5 buys ~5M GLM tokens (a lot) |
| Use GLM at flat rate | Sign up for Z.AI Lite plan, add `Z_AI_API_KEY` to `.env`, route via `base_url="https://api.z.ai/api/anthropic"` | $3/mo |
| Use Opus / Sonnet direct | Top up Anthropic Console ($20 min) | $20+ |
| Use GPT / o1 direct | Edit OPENAI_API_KEY scopes to include `model.request` (or use unrestricted key) | $0 (admin-only fix) |
| Use Gemini Pro (paid) | Add billing to Google Cloud / AI Studio | depends on use |

---

## What Nick's video covered that this workspace already provides

Nick's setup pattern (video timestamps in his terms):

- **7:18** ANTHROPIC_BASE_URL swap → `claude-glm.ps1` and `.sh` implement exactly this.
- **8:33** "set up exa.ai for web search" → workspace already has Firecrawl / Tavily / Serper / Perplexity MCP servers registered. GLM-driven Claude Code sessions can use any of them; no new Exa signup needed.
- **9:04** Open Code / Crush install (`brew install opencode`, `brew install crush`) → Mac-only via brew. Skipped on Windows; Claude Code remains the primary harness. (If wanted: scoop / chocolatey / direct release-binary install.)
- **12:08** Provider hosting options (Open Router, Z.AI, Fireworks, Deep Infra, GMI, self-host) → documented in `glm_5_2_integration.md`. Today: OR is the wired route. Z.AI direct one-line away (key needed).
- **13:14** Self-host quantized GLM (2-bit, 256GB Mac) → infeasible on Windows + RAM constraints. Documented, not implemented.

---

## Files involved

| File | Role |
|---|---|
| `execution/modules/model_router.py` | Python dispatcher (lib + CLI) |
| `execution/modules/model_registry.py` | Tier resolver — GLM tier added in Phase 1 |
| `execution/modules/llm_client.py` | OR client with base_url-keyed cache (Z.AI direct ready) |
| `execution/infrastructure/launchers/_load_env.ps1` | Shared `.env` loader for PowerShell launchers |
| `execution/infrastructure/launchers/claude-{glm,gpt,gemini,sonnet,opus}.ps1` | PowerShell session launchers |
| `execution/infrastructure/launchers/claude-{glm,gpt,gemini,sonnet,opus}.sh` | Bash session launchers |
| `~/.claude/rules/model-tier.md` | Global rule — Exhibit C adds GLM 5.2 + sensitivity guardrail |
| `directives/infrastructure/glm_5_2_integration.md` | GLM-specific integration doc |

---

## Sensitivity guardrail (repeated for emphasis)

GLM 5.2 (and any `z-ai/*` route) is **public-content only**. The dispatcher does NOT enforce this — it's a policy guardrail until the SAST grep lands (owed item in `HARDENING_BACKLOG.md`).

Forbidden uses of GLM:
- Cold-email leads / recipient data
- CV / recruiter / candidate content
- AM-scoped data (Accessory Masters / Elite Broker / Hedgestone)
- Client / customer data
- Anything that contains PII the operator hasn't pre-classified as public

When in doubt: use `sonnet` or `gemini` instead.
