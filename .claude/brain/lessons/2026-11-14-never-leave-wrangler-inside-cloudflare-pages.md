---
id: 2026-11-14-never-leave-wrangler-inside-cloudflare-pages
triggers: wrangler, pages dev, .dev.vars, deploy, cloudflare pages, jeevana
scope: all
strength: 2
status: active
created: 2026-11-14
confirmed: 2026-11-14
source:
supersedes:
---
Never leave .dev.vars or .wrangler/ inside a Cloudflare Pages output dir (pages_build_output_dir='.'): Pages publishes every file there; pass dev secrets as --binding flags and move .wrangler out before deploy.

Why: Jeevana reviews build 2026-11-14: .dev.vars with test admin creds was written into the site dir, which is not gitignored and would have been served publicly; caught by check-ignore before deploy.
