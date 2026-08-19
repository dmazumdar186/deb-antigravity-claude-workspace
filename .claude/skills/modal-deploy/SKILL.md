---
name: modal-deploy
description: >
  Push any workflow or skill to Modal as an HTTP endpoint. User says "push X to modal" and it deploys as a persistent web_endpoint callable via HTTP POST. Triggers on "push to modal", "deploy to modal", "modal deploy", or /modal-deploy.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

> **AM LOCKDOWN — read this before running the skill.**
>
> This skill touches `INSTANTLY_API_KEY / GHL_API_KEY`. Accessory Masters has been handed off and those
> credentials are off-limits per `CLAUDE.local.md`: no calls, no credits, no
> requests to AM-scoped endpoints. Run it only against a non-AM workspace, and
> only with Debanjan's explicit go-ahead in the current session. Do not infer
> authorisation from a previous session or from the fact that this file exists.

> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Modal Deploy

Deploy any local workflow, skill, or script to Modal as a persistent HTTP endpoint.

## Prerequisites

- Modal CLI installed and authenticated (`modal` in PATH, `modal profile list` shows active workspace)
- Python dependencies available in `.venv/`
- API keys in `.env` for any secrets the workflow needs

## Execution

### 1. Identify the target

Parse the user's request to determine what to deploy:
- A skill name (e.g., "push stochastic consensus to modal") → read `.claude/skills/{name}/SKILL.md`
- A script path (e.g., "push active/execution/foo.py to modal") → read the script
- A description (e.g., "push a Claude API summarizer to modal") → generate from scratch

### 2. Read and understand the target

Read the target skill/script completely. Identify:
- **Core logic**: What it actually does (strip away Claude Code orchestration — Agent tool calls, file I/O, etc.)
- **Dependencies**: Python packages needed (anthropic, requests, etc.)
- **Secrets**: Environment variables required (ANTHROPIC_API_KEY, etc.)
- **Input/output**: What goes in (user prompt, config), what comes out (report, data)

### 3. Generate the Modal app

Create `active/modal/{app-name}/app.py` with this structure:

```python
import modal

app = modal.App("{app-name}")

# Image with dependencies
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "anthropic", "fastapi[standard]",  # add whatever's needed
)

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-key")],  # map to Modal secrets
    timeout=600,
)
@modal.fastapi_endpoint(method="POST")
def run(request: dict):
    # Core logic here — pure Python, no Claude Code dependencies
    ...
    return {"result": ...}
```

**Key rules:**
- **No Claude Code dependencies** — no Agent tool, no Task tool, no MCP. Pure Python + SDKs.
- **Translate orchestration to code** — if the skill spawns subagents, replace with direct API calls (e.g., `anthropic.Anthropic().messages.create()`)
- **Use asyncio for parallelism** — if the skill runs N things in parallel, use `asyncio.gather()`
- **Return JSON** — web_endpoint returns dict, which becomes JSON response
- **Secrets via Modal** — never hardcode keys. Use `modal.Secret.from_name()`

### 4. Set up Modal secrets

Check if required secrets exist:
```bash
modal secret list 2>/dev/null | grep {secret-name}
```

If missing, create them from `.env`:
```bash
# Read the key from .env
source /path/to/your/workspace/.env
modal secret create anthropic-key ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
```

Common secret mappings:
- `anthropic-key` → ANTHROPIC_API_KEY
- `instantly-key` → INSTANTLY_API_KEY
- `apify-key` → APIFY_API_TOKEN

### 5. Deploy

```bash
cd /path/to/your/workspace/active/modal/{app-name}
modal deploy app.py
```

This outputs a persistent URL like `https://{{MODAL_WORKSPACE}}--{app-name}-run.modal.run`

### 6. Test the endpoint

```bash
curl -X POST https://{{MODAL_WORKSPACE}}--{app-name}-run.modal.run \
  -H "Content-Type: application/json" \
  -d '{"test": "payload"}'
```

### 7. Report to user

Provide:
- The endpoint URL
- Example curl command
- Expected input/output schema
- Cost estimate per invocation

## Output files

| File | Description |
|------|-------------|
| `active/modal/{app-name}/app.py` | The Modal app source |

## Edge cases

- **Large dependencies**: Use `modal.Image.debian_slim().pip_install()` — Modal caches images, so first deploy is slow but subsequent ones are fast
- **Long-running tasks**: Set `timeout=` appropriately (default 600s = 10 min)
- **GPU workloads**: Add `gpu="T4"` or `gpu="A10G"` to `@app.function()` if needed
- **Existing deployment**: `modal deploy` overwrites the existing endpoint — safe to re-deploy
- **Auth**: Modal web_endpoints are public by default. For sensitive endpoints, add a bearer token check in the function body

## Cost

- Modal charges per compute-second. A 10-agent Claude consensus call takes ~30-60s of compute (mostly waiting on API) = ~$0.001 Modal cost + Claude API cost
- Persistent endpoints have no idle cost — they scale to zero
