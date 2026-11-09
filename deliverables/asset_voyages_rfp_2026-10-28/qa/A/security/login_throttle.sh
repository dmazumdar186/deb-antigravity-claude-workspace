#!/usr/bin/env bash
# 15 wrong passwords then the right one: is there any throttle/lockout? Plus error-page leakage.
. "$(dirname "$0")/lib.sh"
for i in $(seq 1 15); do curl -s -o /dev/null -w "%{http_code} " -b "wordpress_test_cookie=WP%20Cookie%20check" -d "log=direction&pwd=wrong$i&testcookie=1" "$B/wp-login.php"; done; echo
curl -s -o /dev/null -w "correct after 15 fails: %{http_code} %{redirect_url}\n" -b "wordpress_test_cookie=WP%20Cookie%20check" -d "log=direction&pwd=demo-asset&testcookie=1" "$B/wp-login.php"
curl -s -b "wordpress_test_cookie=WP%20Cookie%20check" -d "log=direction&pwd=bad&testcookie=1" "$B/wp-login.php" | grep -oE 'id="login_error".{0,200}' | sed 's/<[^>]*>//g' | head -2
for u in "nope-404" "wp-content/plugins/asset-congres-demo/includes/class-gme.php" "wp-content/plugins/asset-congres-demo/asset-congres-demo.php" "wp-content/debug.log" "?p=99999" "wp-json/wp/v2/asset_congres/99999"; do curl -s -o /tmp/e.out -w "%-70s %{http_code} " "$B/$u"; grep -ciE "fatal|warning:|stack trace|/wordpress/" /tmp/e.out; done
