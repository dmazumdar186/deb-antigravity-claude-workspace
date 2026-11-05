#!/usr/bin/env bash
# set_demo_urls.sh <custom_url> [site_dir] — point the demos hub at the deployed Option B worker.
# Rewrites CUSTOM_URL in site/js/demo.js and every Option B href fallback in site/demo/index.html
# (CUSTOM_CONSOLE_URL follows as <custom_url>console). Idempotent: re-running with the same URL is a no-op.
# Optional second argument: another site folder (the tests use a scratch copy).
set -euo pipefail
new="${1:-}"
if [[ ! "$new" =~ ^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~/-]*)?$ ]]; then
  echo "usage: $0 https://<worker-host>/   (https only; letters, digits, . - _ ~ / allowed)" >&2; exit 2
fi
[[ "${new: -1}" == "/" ]] || new="${new}/"
site="${2:-$(cd "$(dirname "$0")/../site" && pwd)}"
js="$site/js/demo.js"; html="$site/demo/index.html"
[[ -f "$js" && -f "$html" ]] || { echo "missing $js or $html" >&2; exit 2; }
python3 -I - "$js" "$html" "$new" <<'PY'
import re, sys
js, html, new = sys.argv[1:4]
src = open(js, encoding='utf-8').read()
m = re.search(r"const CUSTOM_URL = '([^']+)';", src)
if not m:
    sys.exit('CUSTOM_URL constant not found in demo.js')
old = m.group(1)
if old == new:
    print('already set:', new)
    sys.exit(0)
open(js, 'w', encoding='utf-8').write(src.replace(f"const CUSTOM_URL = '{old}';", f"const CUSTOM_URL = '{new}';"))
h = open(html, encoding='utf-8').read()
pat = re.compile(r'(data-demo="CUSTOM(?:_CONSOLE)?_URL" href=")' + re.escape(old) + r'((?:console)?")')
h2, n = pat.subn(lambda mo: mo.group(1) + new + mo.group(2), h)
open(html, 'w', encoding='utf-8').write(h2)
print(f'CUSTOM_URL: {old} -> {new}; {n} href fallback(s) updated')
PY
