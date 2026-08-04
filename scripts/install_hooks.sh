#!/usr/bin/env sh
# scripts/install_hooks.sh
#
# Phase-1 workspace hardening (2026-08-04). Points git at the tracked
# .githooks/ directory so pre-commit + pre-push run automatically.
#
# One-time setup after a fresh clone. Safe to re-run.
#
# What this does:
#   git config core.hooksPath .githooks
#
# What it does NOT do:
#   - Symlink or copy files into .git/hooks/ (unnecessary once core.hooksPath is set)
#   - Modify anything outside .git/config
#
# To undo:
#   git config --unset core.hooksPath

set -eu

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

if [ ! -d .githooks ]; then
    echo "[install_hooks] .githooks/ directory not found in $REPO_ROOT" >&2
    echo "[install_hooks] Expected .githooks/pre-commit and .githooks/pre-push." >&2
    exit 1
fi

# Make hook scripts executable (no-op on Windows NTFS, useful on Unix clones)
for h in .githooks/*; do
    [ -f "$h" ] || continue
    chmod +x "$h" 2>/dev/null || true
done

git config core.hooksPath .githooks
CURRENT=$(git config --get core.hooksPath || true)

if [ "$CURRENT" = ".githooks" ]; then
    echo "[install_hooks] OK: core.hooksPath = .githooks"
    echo "[install_hooks] Active hooks:"
    for h in .githooks/*; do
        [ -f "$h" ] || continue
        echo "  $h"
    done
else
    echo "[install_hooks] ERROR: git config core.hooksPath did not stick." >&2
    exit 1
fi
