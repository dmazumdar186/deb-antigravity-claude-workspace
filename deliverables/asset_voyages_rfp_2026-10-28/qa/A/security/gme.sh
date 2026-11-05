#!/usr/bin/env bash
# GM&E grant lifecycle attacks: no-grant reveal, self-approve, nonce cross-use, IDOR, revoke replay.
. "$(dirname "$0")/lib.sh"
forms(){ as $1 "$B/wp-admin/admin.php?page=asset-gme" | python3 -c '
import re,sys
h=sys.stdin.read()
for f in re.findall(r"<form.*?</form>",h,re.S):
  a=dict(re.findall(r"name=\"(\w+)\" value=\"([^\"]*)\"",f)); print(a.get("action") or a.get("asset_gme_action"), a.get("congres_id"), a.get("request_id"), a.get("decision"), a.get("asset_nonce"))'; }
echo "## equipe forms"; forms equipe | tee /tmp/ef
read _ CID _ _ RN < <(grep '^asset_gme_request' /tmp/ef | head -1)
echo "## 1 equipe reveal w/o grant cid=$CID using request nonce"
as equipe -d "asset_gme_action=reveal&congres_id=$CID&asset_nonce=$RN" "$B/wp-admin/admin.php?page=asset-gme" | grep -oE 'asset-notice-[a-z_]+|asset-revealed[^/]*' | sort -u
echo "## 2 equipe request (reason empty, then hostile)"
as equipe -o /dev/null -w "%{http_code} %{redirect_url}\n" -d "action=asset_gme_request&congres_id=$CID&asset_nonce=$RN&reason=" "$B/wp-admin/admin-post.php"
as equipe -o /dev/null -w "%{http_code} %{redirect_url}\n" --data-urlencode "reason=<img src=x onerror=alert('R')>=HYPERLINK(\"http://x\")" -d "action=asset_gme_request&congres_id=$CID&asset_nonce=$RN" "$B/wp-admin/admin-post.php"
echo "## direction forms"; forms direction | tee /tmp/df
read _ _ RID _ AN < <(grep "^asset_gme_decide" /tmp/df | grep " approve " | head -1)
echo "## 3 equipe self-approve rid=$RID with its request nonce / with direction nonce"
as equipe -o /dev/null -w "%{http_code}\n" -d "action=asset_gme_decide&request_id=$RID&decision=approve&asset_nonce=$RN" "$B/wp-admin/admin-post.php"
as equipe -o /dev/null -w "%{http_code}\n" -d "action=asset_gme_decide&request_id=$RID&decision=approve&asset_nonce=$AN" "$B/wp-admin/admin-post.php"
echo "## 4 nonce cross-decision: direction uses approve nonce to refuse? (same action string)"
grep "^asset_gme_decide.* $RID " /tmp/df
echo "## 5 direction approves"
as direction -o /dev/null -w "%{http_code} %{redirect_url}\n" -d "action=asset_gme_decide&request_id=$RID&decision=approve&asset_nonce=$AN&back=asset-gme-acces" "$B/wp-admin/admin-post.php"
forms equipe | tee /tmp/ef2
read _ _ _ _ VN < <(grep "^reveal $CID " /tmp/ef2)
echo "## 6 equipe reveal granted cid=$CID"
as equipe -d "asset_gme_action=reveal&congres_id=$CID&asset_nonce=$VN" "$B/wp-admin/admin.php?page=asset-gme" | grep -oE '<code class="asset-revealed">[^<]*' 
echo "## 7 IDOR: reveal nonce of $CID reused for other congresses"
for o in $(grep -oE '^asset_gme_request [0-9]+' /tmp/ef2 | awk '{print $2}'); do as equipe -d "asset_gme_action=reveal&congres_id=$o&asset_nonce=$VN" "$B/wp-admin/admin.php?page=asset-gme" | grep -oE 'asset-notice-[a-z_]+|asset-revealed">[^<]*' | sort -u | sed "s/^/$o: /"; done
echo "## 8 direction revokes; equipe replays reveal"
read _ _ RID2 _ KN < <(forms direction | grep "^asset_gme_decide.* revoke " | head -1)
echo "revoke rid=$RID2"; as direction -o /dev/null -w "%{http_code}\n" -d "action=asset_gme_decide&request_id=$RID2&decision=revoke&asset_nonce=$KN" "$B/wp-admin/admin-post.php"
as equipe -d "asset_gme_action=reveal&congres_id=$CID&asset_nonce=$VN" "$B/wp-admin/admin.php?page=asset-gme" | grep -oE 'asset-notice-[a-z_]+|asset-revealed">[^<]*' | sort -u
echo "## 9 replay approve on revoked (state machine)"
as direction -o /dev/null -w "%{http_code} %{redirect_url}\n" -d "action=asset_gme_decide&request_id=$RID&decision=approve&asset_nonce=$AN" "$B/wp-admin/admin-post.php"
echo "## 10 contributeur reveal / request with equipe nonce"
as contributeur -o /dev/null -w "%{http_code}\n" -d "asset_gme_action=reveal&congres_id=$CID&asset_nonce=$VN" "$B/wp-admin/admin.php?page=asset-gme"
as contributeur -o /dev/null -w "%{http_code}\n" -d "action=asset_gme_request&congres_id=$CID&asset_nonce=$RN&reason=x" "$B/wp-admin/admin-post.php"
