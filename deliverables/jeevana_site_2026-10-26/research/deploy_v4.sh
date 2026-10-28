#!/usr/bin/env bash
# Preview deploy of the v4 site to Cloudflare Pages branch "v4" (never production). Run from the deliverable dir.
set -euo pipefail
cd "$(dirname "$0")/../site"
npx --yes wrangler@4 pages deploy . --project-name jeevana-yoga --branch v4 --commit-dirty=true 2>&1 | tail -5
URL="https://v4.jeevana-yoga.pages.dev"
sleep 20
echo "home: $(curl -s -o /dev/null -w '%{http_code}' "$URL/")  privacy: $(curl -s -o /dev/null -w '%{http_code}' "$URL/privacy/")"
echo "register empty POST (expect 400): $(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL/api/register" -H 'content-type: application/json' -d '{}')"
for p in /wrangler.toml /functions/api/_lib.ts; do echo "$p (expect 404): $(curl -s -o /dev/null -w '%{http_code}' "$URL$p")"; done
echo "no Jitendra on page: $(curl -s "$URL/" | grep -c -i jitendra)"
