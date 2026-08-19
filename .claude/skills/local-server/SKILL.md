---
name: local-server
description: Run Claude orchestrator locally with Cloudflare tunneling. Use when user asks to run locally, start local server, or test webhooks locally.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Local Server Execution

## Goal
Run the Claude orchestrator locally with Cloudflare tunnel for external webhook access.

## Start Server
```bash
python3 .claude/skills/local-server/local_server.py
```

Starts FastAPI server on port 8000.

## Cloudflare Tunnel
For external access (webhooks), use Cloudflare tunnel:
```bash
cloudflared tunnel --url http://localhost:8000
```

## Endpoints
Same as Modal deployment:
- `/directive?slug={slug}` - Execute directive
- `/list-webhooks` - List webhooks
- `/general-agent` - General agent tasks

## Development Use
- Faster iteration than Modal deploys
- Full access to local files and credentials
- Real-time debugging with print statements

## Environment
Uses local `.env` file directly (unlike Modal which uses secrets).
