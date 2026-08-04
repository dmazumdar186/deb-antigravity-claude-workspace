#!/usr/bin/env python3
"""
Offline output-acceptance gate for AgentUp.

Runs against the built `dist/` directory (produced by `npm run build`) and
hard-fails (exit 1) on any structural regression. Per workspace rule
`output-acceptance-gate.md`, this asserts on the OUTPUT a user reads, not
just that the build succeeded.

Usage:
    npm run build && py tests/acceptance_agentup.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def expect_file(p: Path, min_bytes: int = 100) -> None:
    if not p.exists():
        fail(f"missing: {p.relative_to(ROOT)}")
        return
    size = p.stat().st_size
    if size < min_bytes:
        fail(f"too small ({size} < {min_bytes}): {p.relative_to(ROOT)}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def check_dist_structure() -> None:
    """All 3 pages present, plus favicon and function chunks."""
    expect_file(DIST / "index.html", 1_500)
    expect_file(DIST / "cases" / "index.html", 1_500)
    expect_file(DIST / "dashboard" / "index.html", 1_500)
    expect_file(DIST / "favicon.svg", 50)
    # At least one Astro JS chunk (React island bundles).
    astro_js = list((DIST / "_astro").glob("*.js")) if (DIST / "_astro").exists() else []
    if not astro_js:
        fail("no _astro/*.js chunks found — client islands did not build")


def check_no_banned_models() -> None:
    """No banned Claude Haiku 4.5 model IDs anywhere in built output."""
    banned = ["claude-haiku-4-5", "claude-3-haiku"]
    for f in DIST.rglob("*"):
        if not f.is_file() or f.suffix not in {".html", ".js", ".css"}:
            continue
        body = read(f)
        for b in banned:
            if b in body:
                fail(f"banned model {b!r} leaked into {f.relative_to(ROOT)}")


def check_no_hardcoded_keys() -> None:
    """No hardcoded API key patterns anywhere in built output."""
    patterns = [
        (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic API key"),
        (re.compile(r"sk-[A-Za-z0-9]{40,}"),        "OpenAI-style API key"),
    ]
    for f in DIST.rglob("*"):
        if not f.is_file() or f.suffix not in {".html", ".js", ".css", ".json"}:
            continue
        body = read(f)
        for rx, label in patterns:
            m = rx.search(body)
            if m:
                fail(f"{label} leaked into {f.relative_to(ROOT)}: {m.group()[:20]}...")


def check_nav_and_headings() -> None:
    """Every page has the persistent nav bar and the correct H1."""
    expectations = [
        ("index.html", "Daily Training"),
        ("cases/index.html", "My Cases"),
        ("dashboard/index.html", "My Dashboard"),
    ]
    for rel, h1 in expectations:
        p = DIST / rel
        if not p.exists():
            continue
        body = read(p)
        if f"<h1" not in body or h1 not in body:
            fail(f"h1 {h1!r} missing from /{rel}")
        # All 3 nav links present.
        for link_text in ("Daily Training", "My Cases", "My Dashboard"):
            if link_text not in body:
                fail(f"nav link {link_text!r} missing from /{rel}")


def check_bundle_size() -> None:
    """Client bundle stays under budget. Dashboard route (recharts) is
    allowed a larger cap because Recharts is heavy.
    """
    per_file_cap = 450_000       # single file
    total_cap    = 900_000       # sum of all _astro/*.js
    astro_dir = DIST / "_astro"
    if not astro_dir.exists():
        return
    total = 0
    for f in astro_dir.glob("*.js"):
        size = f.stat().st_size
        if size > per_file_cap:
            fail(f"bundle too large ({size} > {per_file_cap}): _astro/{f.name}")
        total += size
    if total > total_cap:
        fail(f"total _astro bundle too large ({total} > {total_cap})")


def check_default_cases_shape() -> None:
    """The 5 mandatory default cases (per PRD) are present and well-formed."""
    p = ROOT / "src" / "data" / "default-cases.json"
    if not p.exists():
        fail("default-cases.json missing")
        return
    try:
        data = json.loads(read(p))
    except json.JSONDecodeError as e:
        fail(f"default-cases.json malformed: {e}")
        return
    if not isinstance(data, list) or len(data) < 5:
        fail(f"default-cases.json must contain >= 5 cases, got {len(data) if isinstance(data, list) else 'non-list'}")
        return
    required_keys = {"id", "title", "scenario", "opening", "channel", "topic", "difficulty"}
    channels = {"Chat", "Call", "Both"}
    diffs = {"Beginner", "Intermediate", "Advanced"}
    for i, c in enumerate(data):
        if not isinstance(c, dict):
            fail(f"case[{i}] not an object")
            continue
        missing = required_keys - set(c.keys())
        if missing:
            fail(f"case[{i}] missing keys: {missing}")
        if c.get("channel") not in channels:
            fail(f"case[{i}] channel {c.get('channel')!r} not in {channels}")
        if c.get("difficulty") not in diffs:
            fail(f"case[{i}] difficulty {c.get('difficulty')!r} not in {diffs}")
        if len(str(c.get("scenario", ""))) < 50:
            fail(f"case[{i}] scenario too short (< 50 chars)")


def check_wrangler_config() -> None:
    """wrangler.toml is present and does not leak secrets."""
    p = ROOT / "wrangler.toml"
    if not p.exists():
        fail("wrangler.toml missing")
        return
    body = read(p)
    if "ANTHROPIC_API_KEY" in body and "=" in body.split("ANTHROPIC_API_KEY", 1)[1].split("\n", 1)[0]:
        fail("wrangler.toml appears to define ANTHROPIC_API_KEY — must use `wrangler pages secret put` instead")
    if "pages_build_output_dir" not in body:
        fail("wrangler.toml missing pages_build_output_dir")


def main() -> int:
    if not DIST.exists():
        print(f"FAIL: {DIST} does not exist. Run `npm run build` first.")
        return 2

    check_dist_structure()
    check_no_banned_models()
    check_no_hardcoded_keys()
    check_nav_and_headings()
    check_bundle_size()
    check_default_cases_shape()
    check_wrangler_config()

    if failures:
        print(f"\nFAIL: {len(failures)} acceptance issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: all acceptance checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
