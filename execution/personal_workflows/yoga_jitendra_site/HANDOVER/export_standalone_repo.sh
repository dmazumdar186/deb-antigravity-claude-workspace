#!/usr/bin/env bash
# Export the yoga_jitendra_site folder as a clean standalone repo for handover.
# Drops the operator-only dashboard, tests, dev docs and the Cloudflare KV
# binding so the copy builds in ANY Cloudflare Pages account with zero secrets.
#
# Usage: bash HANDOVER/export_standalone_repo.sh [/path/to/EMPTY_or_new_output_dir]
# Default output: <site>/.tmp/yogaavecjitendra-standalone-<timestamp>
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$SRC/.tmp/yogaavecjitendra-standalone-$(date +%Y%m%d%H%M%S)}"
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  echo "refusing to export into non-empty dir: $OUT" >&2; exit 1
fi
mkdir -p "$OUT"
# Portable copy (no rsync on Windows / minimal containers).
python3 - "$SRC" "$OUT" <<'PY'
import fnmatch, os, shutil, sys
src, out = sys.argv[1], sys.argv[2]
SKIP_DIRS = {"node_modules", "dist", ".astro", ".tmp", ".git", "HANDOVER", "tests", "docs",
             "src/pages/dashboard", "src/components/dashboard"}
SKIP_FILES = {"generate.py", "src/pages/dashboard.astro", "src/content/dashboard-data.json",
              "functions/api/dashboard-data.ts", "functions/api/self-report.ts",
              "scripts/pull_gbp_reviews.mjs", "scripts/get_google_refresh_token.py",
              "scripts/backfill_review_dates_from_maps.mjs", "scripts/generate_ambient_loop.py",
              "scripts/seed_reviews.mjs",
              "src/content/reviews.json"}
SKIP_GLOBS = [".env*", "*.log", "*.md"]
n = 0
for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src).replace(os.sep, "/")
    rel = "" if rel == "." else rel
    dirs[:] = [d for d in dirs if (f"{rel}/{d}" if rel else d) not in SKIP_DIRS]
    for f in files:
        r = f"{rel}/{f}" if rel else f
        if r in SKIP_FILES or any(fnmatch.fnmatch(f, g) for g in SKIP_GLOBS):
            continue
        dst = os.path.join(out, r)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(root, f), dst)
        n += 1
print(f"copied {n} files")
PY
# Reviews: build from the checked-in list; never call the old owner's API.
python3 - "$OUT/package.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["name"] = "yogaavecjitendra"
d["scripts"]["prebuild"] = "SYNC_REVIEWS_SKIP=1 node scripts/sync_reviews.mjs"
d["scripts"].pop("seed-reviews", None)
with open(p, "w") as f:
    json.dump(d, f, indent=2); f.write("\n")
PY
# Cloudflare config without the old account's KV namespace.
cat > "$OUT/wrangler.toml" <<'TOML'
name = "yogaavecjitendra"
compatibility_date = "2024-11-01"
pages_build_output_dir = "./dist"
TOML
cp "$SRC/HANDOVER/README_JITENDRA.md" "$OUT/README.md"
echo "exported to $OUT"
(cd "$OUT" && find . -type f | wc -l)
