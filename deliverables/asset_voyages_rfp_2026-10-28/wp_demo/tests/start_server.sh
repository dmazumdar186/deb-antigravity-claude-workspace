#!/usr/bin/env bash
# Starts a fresh local Playground (port 9400) with the admin blueprint, the plugin zip served on 9401,
# and the SQLite database mounted on the host (.tmp/db) so the leak test can inspect it.
set -euo pipefail
cd "$(dirname "$0")/.."
./build_zip.sh --local >/dev/null
mkdir -p .tmp/db
rm -f .tmp/db/.ht.sqlite .tmp/db/.ht.sqlite-wal .tmp/db/.ht.sqlite-shm .tmp/db/.htaccess .tmp/db/index.php
if ! curl -sf -o /dev/null http://127.0.0.1:9401/asset-congres-demo.zip; then
	nohup python3 -m http.server 9401 --bind 127.0.0.1 --directory "$PWD" > .tmp/zip-server.log 2>&1 &
	sleep 1
fi
exec npx -y @wp-playground/cli@3.1.62 server \
	--blueprint=.tmp/blueprint-visitor.local.json \
	--port=9400 \
	--mount-before-install="$PWD/.tmp/db:/wordpress/wp-content/database"
