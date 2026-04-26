---
paths:
  - "**/*"
---

# Security Rules (Always Active)

- Never commit `.env`, `credentials.json`, `token.json`, or any file containing API keys
- Never hardcode API keys, passwords, or tokens in any file — use environment variables
- Never expose API keys in print statements, logs, or error messages
- Always use `${ENV_VAR}` syntax in `.mcp.json` — never paste actual keys
- Never force-push to main/master branch without explicit user confirmation
- Never run `rm -rf` on directories without explicit user confirmation
- Never drop database tables or truncate data without explicit user confirmation
- Credentials go in `.env` (gitignored) — check `.gitignore` before adding any sensitive file
- When in doubt about a destructive operation, ask the user before proceeding
