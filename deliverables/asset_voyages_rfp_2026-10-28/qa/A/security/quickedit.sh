#!/usr/bin/env bash
# Contributeur: quick edit / post.php / REST future to force publish on own pending post ($1).
. "$(dirname "$0")/lib.sh"; P=${1:-40}
QN=$(as contributeur "$B/wp-admin/edit.php?post_type=asset_congres&post_status=pending" | grep -oE 'name="_inline_edit" value="[a-f0-9]+' | grep -oE '[a-f0-9]+$' | head -1)
echo "inline nonce: ${QN:+found}"
as contributeur -d "action=inline-save&post_ID=$P&post_type=asset_congres&_inline_edit=$QN&post_title=QE+—+exemple&_status=publish&screen=edit-asset_congres" "$B/wp-admin/admin-ajax.php" | head -c 200; echo
N=$(as contributeur "$B/wp-admin/admin-ajax.php?action=rest-nonce")
as contributeur -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"status":"future","date":"2030-01-01T00:00:00"}' "$B/wp-json/wp/v2/asset_congres/$P" | head -c 160; echo
as contributeur -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"status":"private"}' "$B/wp-json/wp/v2/asset_congres/$P" | head -c 160; echo
as contributeur -H "X-WP-Nonce: $N" -X DELETE "$B/wp-json/wp/v2/asset_congres/16" | head -c 160; echo
as contributeur -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"title":"hijack"}' "$B/wp-json/wp/v2/asset_congres/16" | head -c 160; echo
as admin "$B/wp-json/wp/v2/asset_congres/$P?context=edit&_wpnonce=$(as admin "$B/wp-admin/admin-ajax.php?action=rest-nonce")" | python3 -c "import json,sys;d=json.load(sys.stdin);print('final status',d['status'])"
