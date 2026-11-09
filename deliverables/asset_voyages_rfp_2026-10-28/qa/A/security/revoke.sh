#!/usr/bin/env bash
# Revocation: direction revokes from the access screen, equipe replays the old reveal nonce.
. "$(dirname "$0")/lib.sh"; CID=${1:-5}
H=$(as direction "$B/wp-admin/admin.php?page=asset-gme-acces")
echo "$H" | grep -oE 'onerror[^<]{0,40}|&lt;img[^<]{0,40}' | head -3
read RID KN < <(echo "$H" | python3 -c '
import re,sys
for f in re.findall(r"<form.*?</form>",sys.stdin.read(),re.S):
  a=dict(re.findall(r"name=\"(\w+)\" value=\"([^\"]*)\"",f))
  if a.get("decision")=="revoke": print(a["request_id"],a["asset_nonce"]); break')
echo "revoke rid=$RID"
as direction -o /dev/null -w "%{http_code} %{redirect_url}\n" -d "action=asset_gme_decide&request_id=$RID&decision=revoke&asset_nonce=$KN&back=asset-gme-acces" "$B/wp-admin/admin-post.php"
VN=$(as equipe "$B/wp-admin/admin.php?page=asset-gme" | grep -oE 'asset_gme_reveal_[0-9]+' | head -1)
echo "equipe still has reveal form: ${VN:-none}"
