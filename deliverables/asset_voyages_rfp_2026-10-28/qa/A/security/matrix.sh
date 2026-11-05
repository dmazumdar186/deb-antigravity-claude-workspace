#!/usr/bin/env bash
# Authorisation matrix: role x plugin screen / core screen / handler (GET, no nonce).
. "$(dirname "$0")/lib.sh"
U=( "wp-admin/admin.php?page=asset-demandes" "wp-admin/admin.php?page=asset-gme" "wp-admin/admin.php?page=asset-gme-acces" "wp-admin/admin.php?page=asset-gme-journal" "wp-admin/admin.php?page=asset-notifications" "wp-admin/admin.php?page=asset-congres-demo" "wp-admin/edit.php?post_type=asset_congres" "wp-admin/post-new.php?post_type=asset_congres" "wp-admin/edit.php?post_type=asset_demande" "wp-admin/users.php" "wp-admin/user-new.php" "wp-admin/export.php" "wp-admin/admin-post.php?action=asset_demandes_export" "wp-admin/admin-post.php?action=asset_gme_save" "wp-admin/admin-post.php?action=asset_gme_decide" "wp-admin/admin-post.php?action=asset_gme_request" "wp-admin/admin-post.php?action=asset_demande_update" "wp-admin/admin-post.php?action=asset_cd_reseed" )
printf "%-62s %s\n" URL "anon contributeur equipe direction"
for u in "${U[@]}"; do
  line=""
  for r in anon contributeur equipe direction; do
    out=$(as $r -o /tmp/m.html -w "%{http_code}" "$B/$u"); 
    if grep -qiE "pas autoris|not allowed|Accès refusé|Lien expiré|Sorry, you" /tmp/m.html; then out="$out:deny"; fi
    line="$line $out"; done
  printf "%-62s %s\n" "$u" "$line"
done
