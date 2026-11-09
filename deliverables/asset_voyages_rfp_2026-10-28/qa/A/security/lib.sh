#!/usr/bin/env bash
# Security probe helpers for Option A (Playground on :9400). Read-only against source.
B=${B:-http://127.0.0.1:9400}
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
J="$D/out"
login(){ # role pass
  rm -f "$J/$1.cj"
  curl -s -c "$J/$1.cj" -b "$J/$1.cj" "$B/wp-login.php" -o /dev/null
  curl -s -c "$J/$1.cj" -b "$J/$1.cj" -o /dev/null -w "login $1 %{http_code} %{redirect_url}\n" \
   --data-urlencode "log=$1" --data-urlencode "pwd=$2" -d "wp-submit=1&testcookie=1" "$B/wp-login.php"
}
as(){ local r=$1; shift; if [ "$r" = anon ]; then curl -s "$@"; else curl -s -b "$J/$r.cj" -c "$J/$r.cj" "$@"; fi; }
