#!/usr/bin/env bash
# Builds asset-congres-demo.zip reproducibly and renders the two Playground blueprints.
#
#   ./build_zip.sh                       -> blueprints point at the hosted zip (PLUGIN_ZIP_URL default)
#   PLUGIN_ZIP_URL=http://127.0.0.1:9401/asset-congres-demo.zip ./build_zip.sh --local
#                                        -> also writes .tmp/blueprint-*.local.json for local tests
set -euo pipefail
cd "$(dirname "$0")"

# Single place to swap the plugin URL.
HOSTED_ZIP_URL="https://asset-voyages-redesign.pages.dev/demo-wordpress/asset-congres-demo.zip"
LOCAL_ZIP_URL="${PLUGIN_ZIP_URL:-http://127.0.0.1:9401/asset-congres-demo.zip}"

STAGE=".tmp/build-$$"
rm -rf -- "$STAGE"
mkdir -p "$STAGE"
cp -R plugin/asset-congres-demo "$STAGE/"
# Fixed timestamps + sorted entries + no extra attributes = byte-identical zip on re-run.
find "$STAGE" -exec touch -h -d '2026-11-01 00:00:00 UTC' {} +
# Atomic replace: a server downloading the zip never sees a half-written file.
TMPZIP=".tmp/asset-congres-demo.zip.$$"
rm -f "$TMPZIP"
( cd "$STAGE" && find asset-congres-demo -type f | LC_ALL=C sort | TZ=UTC zip -X -D -q -@ "../../$TMPZIP" )
mv -f "$TMPZIP" asset-congres-demo.zip
rm -rf -- "$STAGE"

render() { # $1 template, $2 url, $3 output
	sed "s#__PLUGIN_ZIP_URL__#$2#g" "$1" > "$3"
	python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$3"
}
render blueprints/visitor.template.json "$HOSTED_ZIP_URL" blueprint-visitor.json
render blueprints/admin.template.json   "$HOSTED_ZIP_URL" blueprint-admin.json
if [[ "${1:-}" == "--local" ]]; then
	mkdir -p .tmp
	render blueprints/visitor.template.json "$LOCAL_ZIP_URL" .tmp/blueprint-visitor.local.json
	render blueprints/admin.template.json   "$LOCAL_ZIP_URL" .tmp/blueprint-admin.local.json
	render blueprints/test-nokey.template.json "$LOCAL_ZIP_URL" .tmp/blueprint-nokey.local.json
fi
sha256sum asset-congres-demo.zip
