---
id: 2026-09-22-wrangler-pages-create-force
triggers: wrangler, cloudflare pages, pages project, deploy, new site
scope: infra
strength: 1
status: active
created: 2026-09-22
confirmed: 2026-09-22
source: .claude/notes/general.md
supersedes:
---
With wrangler 4.136+, create a classic Pages project with `pages project create --force`, or it fails with 'Missing entry-point'.

Why: 2026-09-22: project creation was delegated to Workers and failed.
