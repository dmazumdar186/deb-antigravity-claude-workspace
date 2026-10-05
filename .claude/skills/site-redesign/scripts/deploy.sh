#!/usr/bin/env bash
# deploy.sh <site-dir> <project-name> [pitch-path]  — Cloudflare Pages deploy + live verification.
set -u
SITE="${1:?site dir}"; PROJ="${2:?project name}"; PITCH="${3:-}"
: "${CLOUDFLARE_API_TOKEN:?missing}"; : "${CLOUDFLARE_ACCOUNT_ID:?missing}"
if ! npx -y wrangler@4 pages project list 2>/dev/null | grep -q "^│ $PROJ "; then
  npx -y wrangler@4 pages project create "$PROJ" --production-branch main --force 2>&1 | tail -1
fi
npx -y wrangler@4 pages deploy "$SITE" --project-name "$PROJ" --branch main --commit-dirty=true 2>&1 | tail -1
URL="https://$PROJ.pages.dev"
for i in 1 2 3 4 5 6; do
  live=$(curl -s "$URL/css/styles.css?v=$RANDOM" | md5sum | cut -c1-8); loc=$(md5sum < "$SITE/css/styles.css" | cut -c1-8)
  [ "$live" = "$loc" ] && break; sleep 15
done
echo "css live=$live local=$loc $([ "$live" = "$loc" ] && echo MATCH || echo 'STALE — CDN lag, re-check in a minute')"
echo "/ -> $(curl -s -o /dev/null -w '%{http_code}' "$URL/")"
[ -n "$PITCH" ] && echo "$PITCH -> $(curl -s -o /dev/null -w '%{http_code}' "$URL/$PITCH")"
echo "LIVE: $URL/"
