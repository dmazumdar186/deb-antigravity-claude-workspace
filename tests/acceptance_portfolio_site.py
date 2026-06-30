"""Output-acceptance gate for the freelance portfolio site.

Enforces the contract from ~/.claude/rules/output-acceptance-gate.md:
hard-fails if any user-facing artifact is structurally broken or if any
operator-stretched metric still carries the `approve_before_publish` status
at deploy time.

Run from workspace root:
    py tests/acceptance_portfolio_site.py
Exit code 0 = gate green; non-zero = block the deploy.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
CONTENT_DIR = WORKSPACE / "execution" / "personal_workflows" / "portfolio_site" / "src" / "content"

UNAPPROVED = "approve_before_publish"
PLACEHOLDER_TOKEN = "placeholder"


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _load(name: str) -> dict:
    path = CONTENT_DIR / name
    if not path.exists():
        raise SystemExit(f"FATAL: missing content file {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_hero(f: Findings, allow_placeholders: bool) -> None:
    data = _load("hero.en.json")
    for key in ("brand", "operator_name", "operator_role", "headline", "subhead", "primary_cta", "secondary_cta"):
        if not data.get(key):
            f.fail(f"hero.en.json: missing required field `{key}`")
    for cta_key in ("primary_cta", "secondary_cta"):
        cta = data.get(cta_key, {})
        if not (cta.get("label") and cta.get("href")):
            f.fail(f"hero.en.json: {cta_key} missing label or href")
    PLACEHOLDER_CAL = "https://cal.com/debanjan-mazumdar/30min"
    if data.get("primary_cta", {}).get("href", "") == PLACEHOLDER_CAL:
        if not allow_placeholders:
            f.fail("hero.en.json: primary_cta.href is the placeholder Cal.com slug; set the real booking URL before deploy")
        else:
            f.warn("hero.en.json: primary_cta.href is the placeholder Cal.com slug")


def check_proof_bar(f: Findings, allow_placeholders: bool) -> None:
    data = _load("proof_bar.en.json")
    tiles = data.get("tiles", [])
    if len(tiles) != 3:
        f.fail(f"proof_bar.en.json: expected exactly 3 tiles, got {len(tiles)}")
    for i, t in enumerate(tiles):
        for k in ("value", "unit", "label"):
            if not t.get(k):
                f.fail(f"proof_bar.en.json[{i}]: missing `{k}`")
        if t.get("_status") == UNAPPROVED and not allow_placeholders:
            f.fail(
                f"proof_bar.en.json[{i}] ({t.get('value')} {t.get('unit')}): "
                f"_status='{UNAPPROVED}' — operator must approve before publish"
            )


def check_services(f: Findings) -> None:
    data = _load("services.en.json")
    tiles = data.get("tiles", [])
    if len(tiles) < 3:
        f.fail(f"services.en.json: expected >=3 service tiles, got {len(tiles)}")
    for i, t in enumerate(tiles):
        for k in ("title", "blurb", "features", "cta_label"):
            if not t.get(k):
                f.fail(f"services.en.json[{i}]: missing `{k}`")
        if len(t.get("features", [])) < 3:
            f.fail(f"services.en.json[{i}] ({t.get('title')}): expected >=3 features, got {len(t.get('features', []))}")


def check_systems(f: Findings, allow_placeholders: bool) -> None:
    data = _load("systems.en.json")
    cards = data.get("cards", [])
    if len(cards) < 6:
        f.fail(f"systems.en.json: expected >=6 system cards, got {len(cards)}")
    for i, c in enumerate(cards):
        for k in ("id", "category", "title", "description", "brief", "metrics"):
            if not c.get(k):
                f.fail(f"systems.en.json[{i}]: missing `{k}`")
        if len(c.get("metrics", [])) < 2:
            f.fail(f"systems.en.json[{i}] ({c.get('title')}): expected >=2 metrics, got {len(c.get('metrics', []))}")
        for j, m in enumerate(c.get("metrics", [])):
            for k in ("value", "label"):
                if not m.get(k):
                    f.fail(f"systems.en.json[{i}].metrics[{j}]: missing `{k}`")
            if m.get("_status") == UNAPPROVED and not allow_placeholders:
                f.fail(
                    f"systems.en.json[{i}] ({c.get('title')}).metrics[{j}] "
                    f"({m.get('value')} {m.get('label')}): _status='{UNAPPROVED}' — approve before publish"
                )


def check_stack(f: Findings) -> None:
    data = _load("stack.en.json")
    if len(data.get("groups", [])) < 2:
        f.fail("stack.en.json: expected >=2 groups")


def check_how_i_work(f: Findings) -> None:
    data = _load("how_i_work.en.json")
    tiles = data.get("tiles", [])
    if len(tiles) != 3:
        f.fail(f"how_i_work.en.json: expected exactly 3 tiles, got {len(tiles)}")
    for i, t in enumerate(tiles):
        for k in ("objection", "answer", "detail"):
            if not t.get(k):
                f.fail(f"how_i_work.en.json[{i}]: missing `{k}`")


def check_recommendations(f: Findings, allow_placeholders: bool) -> None:
    data = _load("recommendations.en.json")
    quotes = data.get("quotes", [])
    if len(quotes) < 3:
        f.fail(f"recommendations.en.json: expected >=3 quotes, got {len(quotes)}")
    for i, q in enumerate(quotes):
        if q.get("_status") == PLACEHOLDER_TOKEN:
            if not allow_placeholders:
                f.fail(f"recommendations.en.json[{i}]: still a placeholder — populate from LinkedIn Data Export before publish")
            else:
                f.warn(f"recommendations.en.json[{i}]: placeholder (will be filled from LinkedIn Data Export)")
            continue
        for k in ("quote", "name", "role", "linkedin_url"):
            if not q.get(k) or q.get(k) == "—":
                f.fail(f"recommendations.en.json[{i}]: missing or sentinel `{k}`")


def check_contact(f: Findings, _allow_placeholders: bool) -> None:
    data = _load("contact.en.json")
    if not data.get("primary_cta", {}).get("href"):
        f.fail("contact.en.json: primary_cta.href missing")
    links = data.get("links", [])
    if len(links) < 3:
        f.fail(f"contact.en.json: expected >=3 contact links, got {len(links)}")
    for i, link in enumerate(links):
        if not (link.get("label") and link.get("href")):
            f.fail(f"contact.en.json.links[{i}]: missing label or href")


def main() -> int:
    # --staging allows placeholders (Cal.com slug, LinkedIn rec stubs, stretched metrics
    # still pending approval). For local-dev sanity checking. CI / production deploy uses
    # the default strict mode.
    allow_placeholders = "--staging" in sys.argv

    f = Findings()
    check_hero(f, allow_placeholders)
    check_proof_bar(f, allow_placeholders)
    check_services(f)
    check_systems(f, allow_placeholders)
    check_stack(f)
    check_how_i_work(f)
    check_recommendations(f, allow_placeholders)
    check_contact(f, allow_placeholders)

    if f.warnings:
        print("WARNINGS:")
        for w in f.warnings:
            print(f"  - {w}")
        print()

    if f.errors:
        print(f"FAIL: {len(f.errors)} blocking issue(s):")
        for e in f.errors:
            print(f"  - {e}")
        return 1

    mode = "staging (placeholders permitted)" if allow_placeholders else "strict (publish-ready)"
    print(f"PASS: portfolio_site acceptance gate green [{mode}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
