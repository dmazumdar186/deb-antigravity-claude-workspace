#!/usr/bin/env bash
# Export EVERYTHING belonging to the Yoga Avec Jitendra contract into one
# standalone repo for end-of-contract handover: the site (dashboard, API
# functions, tests, docs included), the cron Worker, the ad creatives, the
# directive, the Pages CMS editor config, and (optionally) a dump of his data
# from Cloudflare KV. Only secrets and the old owner's account IDs are removed.
#
# Usage: bash HANDOVER/export_standalone_repo.sh <EMPTY_output_dir> [kv_dump_dir]
#   kv_dump_dir = output of `python3 HANDOVER/dump_kv.py <dir>` (all keys).
#   If it contains review.json, approved reviews replace reviews-seed.json so
#   the site shows the full current review list without any API.
set -euo pipefail
SITE="$(cd "$(dirname "$0")/.." && pwd)"
WS="$(cd "$SITE/../../.." && pwd)"
OUT="${1:-$SITE/.tmp/yogaavecjitendra-standalone-$(date +%Y%m%d%H%M%S)}"
KV="${2:-}"
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  echo "refusing to export into non-empty dir: $OUT" >&2; exit 1
fi
mkdir -p "$OUT"

python3 - "$SITE" "$WS" "$OUT" "$KV" <<'PY'
import fnmatch, json, os, shutil, sys
site, ws, out, kv = sys.argv[1:5]
SKIP_DIRS = {"node_modules", "dist", ".astro", ".tmp", ".git", "HANDOVER", "__pycache__", ".playwright"}
SKIP_GLOBS = [".env*", "*.log", "*.pyc"]

def copy_tree(src, dst_rel):
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(root, src)
        for f in files:
            if any(fnmatch.fnmatch(f, g) for g in SKIP_GLOBS):
                continue
            dst = os.path.join(out, dst_rel, "" if rel == "." else rel, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, f), dst)
            n += 1
    return n

print("site files:", copy_tree(site, "."))
print("cron worker files:", copy_tree(os.path.join(ws, "execution/infrastructure/yoga_jitendra_cron"), "cron"))
print("ad creative files:", copy_tree(os.path.join(ws, "deliverables/ad_creative/yoga_jitendra"), "deliverables/ads"))
shutil.copy2(os.path.join(ws, "directives/personal_workflows/yoga_jitendra_site.md"), os.path.join(out, "docs", "PROJECT_HISTORY.md"))
# Move loose dev docs into docs/ (they are his now; keep them findable).
for f in sorted(os.listdir(out)):
    if f.endswith(".md") and f != "README.md":
        os.replace(os.path.join(out, f), os.path.join(out, "docs", f))

# Data dump → data/kv/ ; approved reviews → reviews-seed.json
if kv and os.path.isdir(kv):
    print("kv dump files:", copy_tree(kv, "data/kv"))
    rp = os.path.join(kv, "review.json")
    if os.path.exists(rp):
        recs = [v for k, v in json.load(open(rp, encoding="utf-8")).items() if k.startswith("review:approved:")]
        seed_path = os.path.join(out, "src/content/reviews-seed.json")
        seed = json.load(open(seed_path, encoding="utf-8"))
        have = {r["id"] for r in recs}
        seed["reviews"] = recs + [r for r in seed["reviews"] if r["id"] not in have]
        seed["_comment"] = "All approved reviews as of handover. Edit freely; this file is the only review source now."
        json.dump(seed, open(seed_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("reviews in seed:", len(seed["reviews"]))

# package.json: no call to the old owner's API at build time.
pp = os.path.join(out, "package.json")
d = json.load(open(pp, encoding="utf-8"))
d["name"] = "yogaavecjitendra"
d["scripts"]["prebuild"] = "SYNC_REVIEWS_SKIP=1 node scripts/sync_reviews.mjs"
json.dump(d, open(pp, "w", encoding="utf-8"), indent=2); open(pp, "a").write("\n")

# Default dashboard login name.
for rel in ("functions/_middleware.ts", "functions/api/subscribers.ts"):
    p = os.path.join(out, rel)
    s = open(p, encoding="utf-8").read().replace("'debanjan'", "'jitendra'")
    open(p, "w", encoding="utf-8").write(s)
PY

# Site Cloudflare config: no KV namespace id from the old account.
cat > "$OUT/wrangler.toml" <<'TOML'
# Cloudflare Pages config. The dashboard, review form and newsletter need a KV
# namespace: in the Cloudflare dashboard create one (Workers & Pages → KV),
# then bind it to this Pages project as DASHBOARD_KV (Settings → Bindings),
# and set the secret DASHBOARD_PASS (Settings → Variables and Secrets).
# The public website itself works without any of this.
name = "yogaavecjitendra"
compatibility_date = "2024-11-01"
pages_build_output_dir = "./dist"
TOML
# Cron worker: strip the old account's KV id, keep everything else.
sed -i.bak -E 's/^(id *= *")[0-9a-f]{32}(")/\1REPLACE_WITH_YOUR_KV_NAMESPACE_ID\2/' "$OUT/cron/wrangler.toml" && rm -f "$OUT/cron/wrangler.toml.bak"
cp "$SITE/HANDOVER/README_JITENDRA.md" "$OUT/README.md"
cp "$SITE/HANDOVER/dump_kv.py" "$OUT/cron/dump_kv.py"
printf 'node_modules\ndist\n.astro\n.env\n.env.*\n*.log\nsrc/content/reviews.json\n' > "$OUT/.gitignore"
echo "exported to $OUT"; (cd "$OUT" && find . -type f | wc -l)
