#!/usr/bin/env bash
# Deploy the Jeevana site to Cloudflare Pages (project jeevana-yoga). Run from the repo root.
# Functions only deploy when wrangler runs from inside site/ (fix brief A1).
set -euo pipefail
ROOT="deliverables/jeevana_site_2026-10-26"
node "$ROOT/research/stamp.mjs"
( cd "$ROOT/site" && npx wrangler@4 pages deploy . --project-name jeevana-yoga --branch main --commit-dirty=true )
URL="https://jeevana-yoga.pages.dev"
sleep 45
echo "register (expect 400 JSON):"; curl -s -o /dev/stdout -w " %{http_code}\n" -X POST "$URL/api/register" -H 'content-type: application/json' -d '{}'
for p in /wrangler.toml /functions/api/_lib.ts /research/brief.md; do echo "$p (expect 404): $(curl -s -o /dev/null -w '%{http_code}' "$URL$p")"; done
echo "secrets:"; ( cd "$ROOT/site" && npx wrangler@4 pages secret list --project-name jeevana-yoga ) || true
