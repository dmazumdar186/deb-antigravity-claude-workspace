#!/usr/bin/env bash
# Starts a fresh local Playground (port 9400) with the admin blueprint, the plugin zip served on 9401,
# and the SQLite database mounted on the host (.tmp/db-current) so the leak test can inspect it.
set -euo pipefail
cd "$(dirname "$0")/.."
# ZIP_PORT (default 9401): the zip server. Give each checkout its own port so two worktrees never
# serve each other's plugin zip.
ZIP_PORT="${ZIP_PORT:-9401}"
export PLUGIN_ZIP_URL="${PLUGIN_ZIP_URL:-http://127.0.0.1:${ZIP_PORT}/asset-congres-demo.zip}"
./build_zip.sh --local >/dev/null
# Fresh, empty database directory for every run; .tmp/db-current points at it.
DBDIR="$PWD/.tmp/db-runs/${WP_PORT:-9400}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DBDIR"
ln -sfn "$DBDIR" ".tmp/db-current-${WP_PORT:-9400}"
if ! curl -sf -o /dev/null "http://127.0.0.1:${ZIP_PORT}/asset-congres-demo.zip"; then
	nohup python3 -m http.server "$ZIP_PORT" --bind 127.0.0.1 --directory "$PWD" > ".tmp/zip-server-${ZIP_PORT}.log" 2>&1 &
	sleep 1
fi
exec npx -y @wp-playground/cli@3.1.62 server \
	--blueprint=.tmp/blueprint-visitor.local.json \
	--port="${WP_PORT:-9400}" \
	--mount-before-install="$DBDIR:/wordpress/wp-content/database"
