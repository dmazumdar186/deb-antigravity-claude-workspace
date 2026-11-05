#!/usr/bin/env bash
# Crawl leak surface per role; flag GM&E codes, enquiry data, ciphertext.
. "$(dirname "$0")/lib.sh"
CID=$(curl -s "$B/wp-json/wp/v2/asset_congres?per_page=1&_fields=id" | grep -oE '[0-9]+' | head -1)
U=( "wp-json/" "wp-json/wp/v2/asset_congres?per_page=100&context=edit" "wp-json/wp/v2/asset_congres/$CID?context=edit" "wp-json/wp/v2/asset_congres/$CID/revisions" "wp-json/wp/v2/asset_demande" "wp-json/wp/v2/types?context=edit" "wp-json/wp/v2/users?context=edit" "wp-json/wp/v2/users" "wp-json/wp/v2/search?search=a&subtype=any&per_page=100" "wp-json/wp/v2/settings" "wp-json/wp/v2/media" "wp-json/wp/v2/posts?status=private,draft" "wp-json/wp/v2/asset_congres?status=draft,private,pending&context=edit" "?post_type=asset_demande" "?post_type=asset_demande&p=1" "?s=DEMO" "?s=example.com&post_type=any" "feed/" "congres/feed/" "?feed=rss2&post_type=asset_demande" "wp-sitemap.xml" "wp-sitemap-posts-asset_congres-1.xml" "wp-json/oembed/1.0/embed?url=$B/?p=$CID" "?p=$CID&preview=true" "wp-admin/admin-ajax.php?action=heartbeat" "wp-admin/admin-ajax.php?action=query-attachments" "?rest_route=/wp/v2/asset_congres/$CID&context=edit" "?author=1" "wp-json/wp/v2/comments" )
for r in anon contributeur equipe; do
 for u in "${U[@]}"; do
  code=$(as $r -o /tmp/l.out -w "%{http_code}" "$B/$u")
  hits=$(grep -oE "DEMO-GME-[A-Z0-9]+|_asset_(email|nom|telephone)|code_enc|@example\.com|asset_demande[^s]" /tmp/l.out | sort | uniq -c | tr '\n' ' ')
  printf "%-12s %-3s %-70s %s\n" $r $code "${u:0:70}" "$hits"
 done
done
