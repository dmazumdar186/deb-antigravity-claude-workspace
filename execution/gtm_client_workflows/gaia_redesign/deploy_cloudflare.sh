#!/usr/bin/env bash
# Deploy the rendered Gaia redesign to Cloudflare Pages (free tier).
# Usage: bash execution/gtm_client_workflows/gaia_redesign/deploy_cloudflare.sh [site_dir] [project_name]
# Needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in the environment or in the
# workspace .env (gitignored). Token permissions: Account > Cloudflare Pages > Edit.
# Result URL: https://<project_name>.pages.dev/
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SITE="${1:-$ROOT/deliverables/gaia_redesign_2026-09-17/site}"
PROJECT="${2:-gaia-talent-redesign}"
[[ "$PROJECT" =~ ^[a-z0-9][a-z0-9-]{0,57}$ ]] || { echo "invalid project name: $PROJECT" >&2; exit 1; }
[ -f "$SITE/index.html" ] || { echo "no index.html in $SITE" >&2; exit 1; }

# Load .env without exporting anything else and without echoing values.
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] && [ -f "$ROOT/.env" ]; then
  CLOUDFLARE_API_TOKEN="$(grep -E '^CLOUDFLARE_API_TOKEN=' "$ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi
if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ] && [ -f "$ROOT/.env" ]; then
  CLOUDFLARE_ACCOUNT_ID="$(grep -E '^CLOUDFLARE_ACCOUNT_ID=' "$ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || { echo "CLOUDFLARE_API_TOKEN is not set (env or .env)" >&2; exit 1; }
[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ] || { echo "CLOUDFLARE_ACCOUNT_ID is not set (env or .env)" >&2; exit 1; }
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID

WRANGLER="npx -y wrangler@4"
$WRANGLER whoami >/dev/null 2>&1 || { echo "wrangler could not authenticate with the token" >&2; exit 1; }

# Create the project on first run; ignore "already exists".
if ! $WRANGLER pages project list 2>/dev/null | grep -qE "(^|[[:space:]])$PROJECT([[:space:]]|$)"; then
  $WRANGLER pages project create "$PROJECT" --production-branch main
fi

$WRANGLER pages deploy "$SITE" --project-name "$PROJECT" --branch main --commit-dirty=true
echo "deployed: https://$PROJECT.pages.dev/"
