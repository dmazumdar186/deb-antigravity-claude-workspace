"""data-stat figure slots: build_site.py marks every live figure on the home page and the KPI dashboard with
its /api/stats path, --stats-json writes the deployed Worker's values into them, and the release smoke compares
each marked figure with /api/stats (deploy/smoke.py compare_figures).

Run: python3 -m pytest tests/greenjobs_redesign/smoke -q   (offline; one real two-edition build)
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "execution/gtm_client_workflows/greenjobs_redesign"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "deploy"))
import build_site  # noqa: E402
import smoke  # noqa: E402

SRC = ROOT / "deliverables/greenjobs_redesign_2026-09-22/src"
MARK = re.compile(r'data-stat="([a-z0-9_.]+)"[^>]*>([^<]*)<')


def fake_stats(site: str) -> dict:
    return {
        "site": site,
        "live_jobs": 4321,
        "asof": "2026-11-20",
        "salary": {
            "n_jobs": 4321,
            "n_disc": 1234,
            "disc_pct": 29,
            "median": "€12.3k" if site == "ie" else "£45.6k",
        },
        "kpis": {
            "asof": "2026-11-20",
            "live": 4321,
            "new7": 17,
            "closing7": 3,
            "sal_pct": 29,
            "days_to_close": None,
            "remote_pct": 11,
            "top_share": 7,
            "agency_pct": 40,
            "sal_n": 1234,
        },
    }


def test_fill_stat_markers_writes_values_and_counts():
    html = (
        '<b class="kpi__v num" data-stat="kpis.sal_pct">31%</b><span data-count="5" data-live="n_disc" '
        'data-stat="salary.n_disc">5</span><b data-stat="kpis.days_to_close">44</b><i data-stat="kpis.nope">1</i>'
    )
    out, n, unknown = build_site.fill_stat_markers(html, fake_stats("ie"))
    assert n == 3 and unknown == ["kpis.nope"]
    assert 'data-stat="kpis.sal_pct">29%</b>' in out
    assert (
        'data-count="1234" data-live="n_disc" data-stat="salary.n_disc">1234</span>'
        in out
    )
    assert 'data-stat="kpis.days_to_close">n/a</b>' in out
    assert build_site.stat_text(None) == "n/a" and build_site.stat_text(7, True) == "7%"


@pytest.fixture(scope="module")
def built():
    """One plain build and one --stats-json build of the real two-edition site (under .tmp/: build_site's guard)."""
    (ROOT / ".tmp").mkdir(exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="greenjobs_statmarks_", dir=str(ROOT / ".tmp")))
    plain, filled = base / "plain", base / "filled"
    assert build_site.build(SRC, plain, editions=["ie", "uk"]) == 0
    stats = {s: fake_stats(s) for s in ("ie", "uk")}
    assert build_site.build(SRC, filled, editions=["ie", "uk"], stats=stats) == 0
    yield plain, filled, stats
    shutil.rmtree(base, ignore_errors=True)


def test_every_home_and_dashboard_figure_is_marked(built):
    plain, _filled, _ = built
    for ed in ("ie", "uk"):
        dash = (plain / ed / "dashboard" / "index.html").read_text(encoding="utf-8")
        keys = [k for k, _ in MARK.findall(dash)]
        assert [k for k in keys if k.startswith("kpis.")] == [f"kpis.{k}" for k in build_site.DASH_TILE_KEYS], keys
        assert [k for k in keys if not k.startswith("kpis.")] == ["salary.n_jobs"], keys  # the shell footer count
        live = re.findall(r'<b class="kpi__v num"[^>]*>', dash.split("data-wired")[0])
        assert len(live) == 8 and all("data-stat=" in t for t in live)
        home = (plain / ed / "index.html").read_text(encoding="utf-8")
        hk = {k for k, _ in MARK.findall(home)}
        assert hk == {
            "salary.n_jobs",
            "salary.n_disc",
            "salary.disc_pct",
            "salary.median",
        }, hk
        # every data-live slot on the home page carries its stats path too
        assert (
            len(re.findall(r'data-live="[a-z_]+"', home))
            == len(MARK.findall(home))
            == 10
        )
        # the jobs page: the intro "N green roles" and the quick-match "N live roles are indexed" (+ the footer)
        jobs = (plain / ed / "jobs" / "index.html").read_text(encoding="utf-8")
        assert [k for k, _ in MARK.findall(jobs)] == ["salary.n_jobs"] * 3
        # every data-live figure on any page carries its stats path (one source: the overlay writes them all)
        for f in (plain / ed).rglob("*.html"):
            raw = f.read_text(encoding="utf-8")
            assert len(re.findall(r'data-live="[a-z_]+"', raw)) <= len(MARK.findall(raw)), f


def test_stats_json_build_prints_the_api_figures_and_smoke_agrees(built):
    _plain, filled, stats = built
    for ed in ("ie", "uk"):
        for page in ("index.html", "dashboard/index.html"):
            raw = (filled / ed / page).read_text(encoding="utf-8")
            marks = MARK.findall(raw)
            assert marks
            for key, text in marks:
                ok, v = build_site.stat_lookup(stats[ed], key)
                assert ok and text == build_site.stat_text(v, text.endswith("%")), (
                    ed,
                    page,
                    key,
                    text,
                )
        dash = (filled / ed / "dashboard" / "index.html").read_text(encoding="utf-8")
        payload = json.loads(dash.split('id="gj-dash">')[1].split("</script>")[0])
        assert (
            payload["live"] == 4321 and payload["sectors"]
        ), "gj-dash takes the API KPIs, keeps the chart payload"
    # the smoke's comparison of the same pages finds every figure equal
    pages = {
        f"/{ed}/{p}": (filled / ed / (p + "index.html")).read_text(encoding="utf-8")
        for ed in ("ie", "uk")
        for p in ("", "dashboard/", "jobs/")
    }

    def transport(method, url, headers, body):
        path = re.sub(r"^https://[^/]+", "", url)
        return (
            smoke.Resp(200, {}, pages[path].encode())
            if path in pages
            else smoke.Resp(404, {})
        )

    cfg = json.loads((PKG / "deploy/environments.json").read_text(encoding="utf-8"))
    s = smoke.Smoke(cfg, "staging", "full", "0" * 40, transport=transport)
    for ed in ("ie", "uk"):
        n, bad = s.compare_figures("https://board.example", ed, stats[ed])
        assert n == (8 + 1) + 10 + 3 and bad == [], (ed, n, bad)
        n, bad = s.compare_figures(
            "https://board.example",
            ed,
            {**stats[ed], "kpis": {**stats[ed]["kpis"], "new7": 18}},
        )
        assert bad == ["dashboard kpis.new7=17 vs stats 18"]


def test_stats_json_with_an_unknown_marker_fails_the_build():
    bad = {s: {**fake_stats(s), "kpis": {"live": 1}} for s in ("ie", "uk")}
    (ROOT / ".tmp").mkdir(exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="greenjobs_statmarks_bad_", dir=str(ROOT / ".tmp")))
    try:
        assert build_site.build(SRC, base / "site", editions=["ie", "uk"], stats=bad) == 1
        assert not (base / "site" / build_site.OK_MARKER).exists()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_deploy_gate_accepts_the_overlaid_build_and_rejects_tampering(built):
    """deploy_cloudflare.sh re-runs validate_site.py: an overlaid build validates against the KPIs it recorded
    (.greenjobs-stats.json, inside the hashed tree); editing a figure afterwards still fails the gate."""
    import validate_site

    plain, filled, _ = built
    assert (filled / build_site.STATS_OVERLAY).is_file() and not (plain / build_site.STATS_OVERLAY).exists()
    assert validate_site.main([str(filled)]) == 0
    dash = filled / "uk" / "dashboard" / "index.html"
    raw = dash.read_text(encoding="utf-8")
    dash.write_text(raw.replace('data-stat="kpis.live">4321<', 'data-stat="kpis.live">9999<'), encoding="utf-8")
    try:
        assert validate_site.main([str(filled)]) == 1
    finally:
        dash.write_text(raw, encoding="utf-8")
