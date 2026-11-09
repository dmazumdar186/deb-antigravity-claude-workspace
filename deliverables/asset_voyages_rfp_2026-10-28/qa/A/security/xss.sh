#!/usr/bin/env bash
# Look for unescaped payloads in every admin surface that shows enquiry / GM&E data, plus a hostile note.
. "$(dirname "$0")/lib.sh"
RAW='<script>alert|<img src=x onerror|<svg onload|"><script'
L=$(as equipe "$B/wp-admin/admin.php?page=asset-demandes"); ID=$(echo "$L" | grep -oE 'action=view&(amp;|#038;)?id=[0-9]+' | grep -oE '[0-9]+$' | sort -n | tail -1)
echo "newest id=$ID"
D=$(as equipe "$B/wp-admin/admin.php?page=asset-demandes&action=view&id=$ID"); UN=$(echo "$D" | grep -oE 'name="asset_nonce" value="[a-f0-9]+' | grep -oE '[a-f0-9]+$' | head -1)
as equipe -o /dev/null -w "note %{http_code}\n" -d "action=asset_demande_update&id=$ID&asset_nonce=$UN&statut=en_cours&owner=999999" --data-urlencode 'note=</textarea><script>alert(9)</script><img src=x onerror=alert(9)>' "$B/wp-admin/admin-post.php"
as equipe -o /dev/null -w "update other id w/ nonce of $ID: %{http_code}\n" -d "action=asset_demande_update&id=$((ID-1))&asset_nonce=$UN&statut=perdue" "$B/wp-admin/admin-post.php"
EN=$(echo "$L" | grep -oE 'asset_demandes_export[^"]*_wpnonce=[a-f0-9]+' | grep -oE '[a-f0-9]+$' | head -1)
for p in "page=asset-demandes" "page=asset-demandes&action=view&id=$ID" "page=asset-notifications" "index.php" ; do
  printf "%-45s raw:%s esc:%s\n" "$p" "$(as equipe "$B/wp-admin/admin.php?$p" | grep -cE "$RAW")" "$(as equipe "$B/wp-admin/admin.php?$p" | grep -cE '&lt;script|&lt;img')"; done
for p in "page=asset-gme-acces" "page=asset-gme-journal" "index.php"; do printf "direction %-35s raw:%s esc:%s\n" "$p" "$(as direction "$B/wp-admin/$( [ $p = index.php ] && echo index.php || echo "admin.php?$p")" | grep -cE "$RAW|<img src=x")" "$(as direction "$B/wp-admin/admin.php?$p" | grep -cE '&lt;img')"; done
as equipe "$B/wp-admin/admin-post.php?action=asset_demandes_export&_wpnonce=$EN" > out/export.csv; echo "csv rows: $(wc -l < out/export.csv)"; grep -oE "^[^;]*;[^;]*;[^;]*" out/export.csv | head -0; grep -oE ";'?[=@+-][^;]{0,25}" out/export.csv | head -6
echo "owner stored:"; as equipe "$B/wp-admin/admin.php?page=asset-demandes&action=view&id=$ID" | grep -oE 'name="owner".{0,300}' | grep -oE 'selected[^>]*>[^<]*' | head -2
