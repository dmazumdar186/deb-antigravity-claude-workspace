#!/usr/bin/env bash
# Publish the rendered GreenJobs redesign into the gh-pages branch under a sub-path.
# Usage: bash execution/gtm_client_workflows/greenjobs_redesign/publish_gh_pages.sh [site_dir] [subpath]
# Default: deliverables/greenjobs_redesign_2026-09-22/site -> gh-pages:/greenjobs/
# Never touches other paths on gh-pages (the existing POC pages at / stay byte-identical).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SITE="${1:-$ROOT/deliverables/greenjobs_redesign_2026-09-22/site}"
SUB="${2:-greenjobs}"
[[ "$SUB" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "invalid subpath: $SUB" >&2; exit 1; }
WT="$ROOT/.tmp/gh-pages-wt"
REMOTE_URL="$(git -C "$ROOT" remote get-url origin | sed -E 's#(\.git)?$##')"
OWNER="$(basename "$(dirname "$REMOTE_URL")")"
REPO="$(basename "$REMOTE_URL")"
cleanup() { git -C "$ROOT" worktree remove --force "$WT" 2>/dev/null || true; }
trap cleanup EXIT
[ -f "$SITE/index.html" ] || { echo "no index.html in $SITE" >&2; exit 1; }
git -C "$ROOT" fetch origin gh-pages
if [ -d "$WT" ]; then git -C "$ROOT" worktree remove --force "$WT"; fi
git -C "$ROOT" worktree prune
if git -C "$ROOT" rev-parse --verify -q gh-pages >/dev/null; then
  if [ -n "$(git -C "$ROOT" log --oneline origin/gh-pages..gh-pages)" ]; then
    echo "local gh-pages has unpushed commits; refusing to reset it" >&2; exit 1
  fi
fi
git -C "$ROOT" worktree add -B gh-pages "$WT" origin/gh-pages
# Replace only the sub-path (git rm keeps the operation scoped and reviewable).
if [ -d "$WT/$SUB" ]; then git -C "$WT" rm -rq "$SUB"; fi
mkdir -p "$WT/$SUB"
# Exclude build/scratch artifacts that must never ship: the build marker and
# any leftover screenshot-scratch token file.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude='.greenjobs-build' --exclude='_shot-*' "$SITE"/ "$WT/$SUB"/
else
  cp -R "$SITE"/. "$WT/$SUB"/
  find "$WT/$SUB" \( -name '.greenjobs-build' -o -name '_shot-*' \) -print0 | xargs -0 -r rm -f
fi
touch "$WT/.nojekyll"
cd "$WT"
git add -A "$SUB" .nojekyll
if git diff --cached --quiet; then
  echo "gh-pages: nothing to publish"
else
  git commit -q -m "greenjobs redesign: publish $SUB/ ($(date -u +%Y-%m-%dT%H:%MZ))

Co-Authored-By: Claude <noreply@anthropic.com>"
  for i in 1 2 3 4 5; do
    if git push -u origin gh-pages; then break; fi
    [ "$i" -eq 5 ] && exit 1
    sleep $((2 ** i))
    # Re-base onto whatever landed on the remote meanwhile (non-fast-forward case).
    git fetch origin gh-pages && git rebase origin/gh-pages
  done
fi
echo "published: https://$OWNER.github.io/$REPO/$SUB/"
cd "$ROOT"
