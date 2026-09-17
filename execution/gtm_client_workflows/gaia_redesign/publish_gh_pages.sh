#!/usr/bin/env bash
# Publish the rendered Gaia redesign into the gh-pages branch under a sub-path.
# Usage: bash execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh [site_dir] [subpath]
# Default: deliverables/gaia_redesign_2026-09-17/site -> gh-pages:/gaia/
# Never touches other paths on gh-pages (the existing POC pages at / stay byte-identical).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SITE="${1:-$ROOT/deliverables/gaia_redesign_2026-09-17/site}"
SUB="${2:-gaia}"
WT="$ROOT/.tmp/gh-pages-wt"
[ -f "$SITE/index.html" ] || { echo "no index.html in $SITE" >&2; exit 1; }
git -C "$ROOT" fetch origin gh-pages
if [ -d "$WT" ]; then git -C "$ROOT" worktree remove --force "$WT"; fi
git -C "$ROOT" worktree prune
git -C "$ROOT" worktree add -B gh-pages "$WT" origin/gh-pages
# Replace only the sub-path (git rm keeps the operation scoped and reviewable).
if [ -d "$WT/$SUB" ]; then git -C "$WT" rm -rq "$SUB"; fi
mkdir -p "$WT/$SUB"
cp -R "$SITE"/. "$WT/$SUB"/
touch "$WT/.nojekyll"
cd "$WT"
git add -A "$SUB" .nojekyll
if git diff --cached --quiet; then
  echo "gh-pages: nothing to publish"
else
  git commit -q -m "gaia redesign: publish $SUB/ ($(date -u +%Y-%m-%dT%H:%MZ))

Co-Authored-By: Claude <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012yGk6DQ9jVHhCS6neDKsrh"
  for i in 1 2 3 4 5; do
    if git push -u origin gh-pages; then break; fi
    [ "$i" -eq 5 ] && exit 1
    sleep $((2 ** i))
  done
fi
echo "published: https://dmazumdar186.github.io/deb-antigravity-claude-workspace/$SUB/"
cd "$ROOT"
git worktree remove --force "$WT"
