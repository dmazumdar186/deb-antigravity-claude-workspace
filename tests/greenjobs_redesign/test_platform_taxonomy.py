"""The frozen taxonomy (platform_worker/src/taxonomy.json) is the one vocabulary source.

description: Asserts build_site.py's sector classifier, type canon, contract, workplace, level and agency
  vocabularies are loaded from taxonomy.json (not a second copy), that each site's region list equals the
  map region table the static build resolves against, that edition settings agree, and that the Worker's
  frozen copy of the templates/shell (site_assets.gen.js) is current (export_site_assets.py --check).
inputs: none (reads the repo read-only)
outputs: pytest results
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GJ = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
sys.path.insert(0, str(GJ))
import build_site  # noqa: E402

TAX = json.loads(
    (GJ / "platform_worker" / "src" / "taxonomy.json").read_text(encoding="utf-8")
)


def test_taxonomy_is_versioned_and_well_formed() -> None:
    assert isinstance(TAX["version"], int) and TAX["version"] >= 1
    names = [s["name"] for s in TAX["sectors"]]
    slugs = [s["slug"] for s in TAX["sectors"]]
    assert len(names) == len(set(names)) == len(slugs) == len(set(slugs)) >= 10
    assert all(re.fullmatch(r"#[0-9a-f]{6}", s["color"]) for s in TAX["sectors"])
    assert all(s["slug"] == build_site.slugify(s["name"]) for s in TAX["sectors"])
    assert TAX["default_sector"] in names
    assert set(TAX["job_types"]["console"]) <= set(TAX["job_types"]["canon"].values())


def test_build_site_reads_the_frozen_file() -> None:
    assert build_site.TAXONOMY == [
        (s["name"], s["color"], s["dark"], s["keywords"]) for s in TAX["sectors"]
    ]
    assert build_site.TYPE_CANON == TAX["job_types"]["canon"]
    assert build_site.CONTRACT_LABEL == TAX["contract"]
    assert build_site.WORKPLACE_LABEL == TAX["workplace"]
    assert build_site.LEVEL_ORDER == TAX["levels"]
    assert build_site.LOC_LABEL == TAX["loc_classes"]
    assert build_site.AGENCY_NAMES == set(TAX["agency"]["names"])
    assert build_site.AGENCY_WORDS == TAX["agency"]["words"]
    assert {lv for lv, _ in build_site.LEVELS} == set(TAX["levels"]) - {"Mid-level"}
    # The classifier only ever emits taxonomy names.
    assert build_site.assign_sectors({"title": "Solar PV designer"}) == ["Solar energy"]
    assert build_site.assign_sectors({"title": "Office manager"}) == [
        TAX["default_sector"]
    ]


def test_site_regions_match_the_map_tables_and_editions() -> None:
    for ed, site in TAX["sites"].items():
        table = json.loads(
            (SRC / "data" / f"regions_{ed}.json").read_text(encoding="utf-8")
        )
        assert site["regions"] == list(table["regions"].keys()), ed
        e = build_site.EDITIONS[ed]
        for k in (
            "domain",
            "currency",
            "sym",
            "unit",
            "name",
            "short",
            "lang",
            "none",
            "elsewhere",
        ):
            assert site[k] == e[k], (ed, k)
        assert set(site["edition_includes"]) == build_site.EDITION_INCLUDES[ed]
        assert site["home"] == build_site.EDITION_HOME[ed]


def test_worker_template_copy_is_current() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(GJ / "platform_worker" / "tools" / "export_site_assets.py"),
            "--check",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
