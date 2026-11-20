"""Redirects: every target is a path the new site serves; sector forwards; idempotent; guards fail loud."""

from __future__ import annotations

import json
import urllib.parse

import pytest

import common as C
import redirects as R


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    cov = R.build(C.REDIRECT_MAP, None, None, out)
    return out, cov


def _routes():
    rmap = C.read_json(C.REDIRECT_MAP)
    live, _ = R.load_live_ids(None, rmap)
    return {ed: C.Routes(ed, live[ed]) for ed in C.BOARDS}, live


def test_every_redirect_target_is_served_by_the_site(built):
    out, cov = built
    routes, _ = _routes()
    host_ed = {urllib.parse.urlsplit(u).hostname: ed for ed, u in C.CANONICAL.items()}
    bulk = C.read_json(out / "bulk_redirects.json")
    assert bulk["items"], "empty list"
    for it in bulk["items"]:
        tgt = it["redirect"]["target_url"]
        ed = host_ed[urllib.parse.urlsplit(tgt).hostname]
        assert routes[ed].serves(tgt), tgt
    assert cov["unserved"] == [] and cov["served_pct"] == 100.0


def test_route_set_rejects_paths_the_site_does_not_serve():
    routes, _ = _routes()
    uk = routes["uk"]
    assert (
        uk.serves("/jobs/")
        and uk.serves("/sectors/wind-energy/")
        and uk.serves("/jobs/?sector=wind-energy&region=london")
    )
    for bad in (
        "/jobs/?sector=not-a-sector",
        "/jobs/?colour=green",
        "/uk/jobs/",
        "/browse-jobs/x/",
        "/jobs/99999999/",
        "https://evil.example/jobs/",
        "/sectors/made-up/",
        "/jobs/?sector=wind-energy&sector=solar-energy",
    ):
        assert not uk.serves(bad), bad


def test_unserved_target_aborts_the_build(tmp_path):
    routes = tmp_path / "routes.json"
    routes.write_text(
        json.dumps({"ie": ["/"], "uk": ["/"]})
    )  # a site that serves only its home page
    with pytest.raises(SystemExit, match="not served"):
        R.build(C.REDIRECT_MAP, None, routes, tmp_path / "out")
    assert not (tmp_path / "out" / "bulk_redirects.json").exists()


def test_sector_domains_forward_to_sector_pages(built):
    out, _ = built
    items = {
        i["redirect"]["source_url"]: i["redirect"]
        for i in C.read_json(out / "bulk_redirects.json")["items"]
    }
    for dom in C.SECTOR_DOMAINS:
        r = items[dom + "/"]
        assert (
            r["status_code"] == 301
            and r["include_subdomains"]
            and r["subpath_matching"]
        )
        assert r["target_url"].startswith("https://www.greenjobs.co.uk/sectors/") and r[
            "target_url"
        ].endswith("/")
    assert "renewableenergyjobsuk.com/" in items and not any(
        k.startswith("renewablejobsuk.com") for k in items
    )
    assert (
        items["windjobsuk.com/"]["target_url"]
        == "https://www.greenjobs.co.uk/sectors/wind-energy/"
    )


def test_bulk_list_has_no_query_strings_and_worker_takes_them(built):
    out, _ = built
    bulk = C.read_json(out / "bulk_redirects.json")
    assert all("?" not in i["redirect"]["source_url"] for i in bulk["items"])
    p = R.plan(C.read_json(C.REDIRECT_MAP), {"ie": set(), "uk": set()})
    assert {r["via"] for r in p["rows"] if "?" in r["old"]} == {"worker"}
    assert len(bulk["items"]) <= R.FREE_TIER_MAX_ITEMS


def test_facets_map_with_build_site_vocabulary():
    emp = C.employer_slugs("uk")
    assert (
        R.facet_target("offshore-wind-jobs", "sector", "uk", emp)[0]
        == "/jobs/?sector=wind-energy"
    )
    assert (
        R.facet_target("south-east", "region", "uk", emp)[0]
        == "/jobs/?region=south-east"
    )
    assert (
        R.facet_target("Cork", "location", "ie", C.employer_slugs("ie"))[0]
        == "/jobs/?region=cork"
    )
    assert (
        R.facet_target("permanent", "job_type", "uk", emp)[0] == "/jobs/?type=permanent"
    )
    assert R.facet_target("bid-manager", "category", "uk", emp) == (
        "/jobs/",
        "fallback:board",
    )
    assert R.facet_target("no-such-employer-xyz", "employer", "uk", emp) == (
        "/employers/",
        "fallback:employers",
    )


def test_coverage_report_counts_and_lists_leftovers(built):
    _, cov = built
    assert cov["old_urls"] == 1206
    assert 0 < cov["specific_match_pct"] <= 100
    assert all(l["target"] in ("/jobs/", "/", "/employers/") for l in cov["leftovers"])
    assert "ASSUMED" in cov["live_ids_source"]


def test_build_is_idempotent(tmp_path):
    out = tmp_path / "g"
    R.build(C.REDIRECT_MAP, None, None, out)
    first = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()}
    R.build(C.REDIRECT_MAP, None, None, out)
    second = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in out.iterdir()}
    assert first == second


def test_committed_generated_files_are_current(tmp_path):
    R.build(C.REDIRECT_MAP, None, None, tmp_path)
    for name in (
        "bulk_redirects.json",
        "worker_redirects.json",
        "redirect_coverage.json",
    ):
        assert C.read_json(tmp_path / name) == C.read_json(
            C.GENERATED / name
        ), f"re-run: python3 ops/redirects.py build ({name})"


def test_live_ids_from_d1_export_drop_expired_jobs(tmp_path):
    exp = tmp_path / "d1.json"
    exp.write_text(
        json.dumps(
            {
                "tables": {
                    "jobs": [
                        {
                            "id": "a",
                            "site": "uk",
                            "status": "live",
                            "source_id": "11488772",
                        },
                        {"id": "b", "site": "uk", "status": "closed", "source_id": "2"},
                    ]
                }
            }
        )
    )
    live, src = R.load_live_ids(exp, C.read_json(C.REDIRECT_MAP))
    assert live["uk"] == {"11488772"} and "D1" in src
    rows = R.plan(C.read_json(C.REDIRECT_MAP), live)["rows"]
    jobs = [r for r in rows if r["kind"] == "job"]
    assert all(r["served"] for r in jobs)
    assert sum(r["class"] == "exact:job" for r in jobs) <= 1


def test_free_tier_ceiling_fails_loud(monkeypatch):
    monkeypatch.setattr(R, "FREE_TIER_MAX_ITEMS", 5)
    with pytest.raises(SystemExit, match="free-tier"):
        R.bulk_list(
            R.plan(C.read_json(C.REDIRECT_MAP), {"ie": set(), "uk": set()})["rows"]
        )


def test_crawl_counts_two_hop_200s_only():
    rows = [
        {"site": "uk", "old": "/a"},
        {"site": "uk", "old": "/b"},
        {"site": "uk", "old": "/c"},
        {"site": "uk", "old": "/d"},
    ]
    graph = {
        "/a": (301, "/x"),
        "/x": (200, None),
        "/b": (301, "/y"),
        "/y": (301, "/z"),
        "/z": (301, "/w"),
        "/w": (200, None),
        "/c": (404, None),
    }

    def head(url):
        p = urllib.parse.urlsplit(url).path
        if p == "/d":
            raise TimeoutError
        return graph[p]

    res = R.crawl(rows, head)
    assert res["checked"] == 4 and res["ok_le_2_hops"] == 1
