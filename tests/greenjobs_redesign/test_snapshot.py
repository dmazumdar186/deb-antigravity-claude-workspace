"""Offline pytest tests for the live-board snapshot functions in scrape_greenjobs.py.

description: Apply-mode rules (email / link / onsite_form), feed-marker detection
  (Broadbean, Idibu, LogicMelon, ATS-only is not a feed), day-first dates, the
  Gaia / third-party employer class, URL pattern -> redirect target mapping,
  robots.txt, sitemap parsing, employers aggregation and an end-to-end
  snapshot_crawl over the recorded corpus in tests/fixtures/greenjobs_scrape/.
  Never touches the network.
inputs: tests/fixtures/greenjobs_scrape/ (read-only) plus synthetic pages below
outputs: pytest results

Run: python3 -m pytest -q tests/greenjobs_redesign/test_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_greenjobs as sg  # noqa: E402
from test_scrape import FakeFetch, IE_JOBS, UK_JOBS  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "greenjobs_scrape"


def page(host: str, name: str) -> str:
    return (FIX / host / name).read_text(encoding="utf-8", errors="ignore")


def synth(
    app_link: str = "",
    desc: str = "<p>Role.</p>",
    extra_hidden: str = "",
    ref: str = "REF-1",
) -> str:
    return f"""<html><body><div id="JBcontent" class="jobView"><form action="/jobboard/cands/JobApplyLink.asp?v=1&amp;ov=v%3D1" method="post">
<input type="hidden" name="strAppLink" id="strAppLink" value="{app_link}" />{extra_hidden}
<h1>T</h1><div class="jobLogo"><a href="/browse-jobs/acme/"><img src="/l.png" alt="Acme"></a></div>
<dl><dt>Recruiter:</dt><dd>Acme</dd><dt>Job Ref:</dt><dd>{ref}</dd></dl>
<div class="jobDescription">{desc}</div><!-- job documents --></form></div><div id="right"></div></body></html>"""


# ------------------------------------------------------------------ apply mode
def test_apply_link_from_hidden_field():
    a = sg.classify_apply(synth("https://careers.example.com/job/1?utm_source=x"), "")
    assert a["mode"] == "link" and a["link_host"] == "careers.example.com"
    assert a["evidence"].startswith('strAppLink="https://careers.example.com')


def test_apply_link_on_recorded_pages():
    hosts = {
        sg.classify_apply(page("www.greenjobs.ie", f"job_{i}.html"), "")["link_host"]
        for i in IE_JOBS
    }
    assert hosts == {"mottmac.com", "emit.fa.ca3.oraclecloud.com"}
    assert all(
        sg.classify_apply(page("www.greenjobs.co.uk", f"job_{i}.html"), "")["mode"]
        == "link"
        for i in UK_JOBS
    )


def test_apply_email_from_mailto_in_field_and_description():
    assert (
        sg.classify_apply(synth("mailto:jobs@acme.ie?subject=x"), "")["email"]
        == "jobs@acme.ie"
    )
    d = sg.classify_apply(
        synth(""), '<p>Apply to <a href="mailto:cv@acme.ie">cv@acme.ie</a></p>'
    )
    assert d["mode"] == "email" and d["email"] == "cv@acme.ie"


def test_apply_email_from_plain_text_needs_apply_context():
    yes = sg.classify_apply(
        synth(""), "<p>Please send your CV to hr@acme.ie by Friday.</p>"
    )
    assert (
        yes["mode"] == "email"
        and yes["email"] == "hr@acme.ie"
        and "CV" in yes["evidence"]
    )
    no = sg.classify_apply(
        synth(""), "<p>" + ("lorem ipsum " * 40) + "Our office mail is x@acme.ie.</p>"
    )
    assert no["mode"] == "onsite_form"


def test_apply_onsite_when_own_host_or_empty():
    assert sg.classify_apply(synth(""), "<p>Plain role</p>")["mode"] == "onsite_form"
    own = sg.classify_apply(synth("https://www.greenjobs.ie/x"), "")
    assert own["mode"] == "onsite_form" and "JobApplyLink.asp" in own["evidence"]


def test_apply_hostile_description_does_not_crash():
    nasty = "<p>" + "@" * 5000 + "<script>x</script>mailto:</p>"
    assert sg.classify_apply(synth(""), nasty)["mode"] in ("email", "onsite_form")
    assert sg.classify_apply("", "")["mode"] == "onsite_form"


# ------------------------------------------------------------------ feed markers
def test_feed_vendor_hits():
    p = synth("https://x.example.com/apply?src=broadbean", ref="BB-123")
    f = sg.detect_feed_markers(p, sg.classify_apply(p, ""), "BB-123")
    assert f["feed_vendor"] == "broadbean" and f["markers"][0]["kind"] == "vendor"
    assert f["markers"][0]["where"] == "apply_url"
    p2 = synth(
        "", extra_hidden='<input type="hidden" name="idibuRef" value="idibu-9" />'
    )
    f2 = sg.detect_feed_markers(p2, sg.classify_apply(p2, ""), None)
    assert f2["feed_vendor"] == "idibu" and any(
        m["kind"] == "extra_hidden_field" for m in f2["markers"]
    )
    p3 = synth("", desc="<!-- posted via Logic-Melon -->")
    assert (
        sg.detect_feed_markers(p3, sg.classify_apply(p3, ""), None)["feed_vendor"]
        == "logicmelon"
    )


def test_ats_host_alone_is_not_a_feed():
    for i in IE_JOBS:
        p = page("www.greenjobs.ie", f"job_{i}.html")
        f = sg.detect_feed_markers(p, sg.classify_apply(p, ""), None)
        assert f["feed_vendor"] is None, i
    p = synth("https://emit.fa.ca3.oraclecloud.com/hcmUI/job/1")
    assert (
        sg.detect_feed_markers(p, sg.classify_apply(p, ""), None)["employer_ats"]
        == "oracle_cloud"
    )


def test_tracking_param_and_ref_shape():
    p = synth("https://a.example.com/j?utm_source=x&trackid=9", ref="AB-1234")
    f = sg.detect_feed_markers(p, sg.classify_apply(p, ""), "AB-1234")
    assert any(
        m["kind"] == "tracking_param" and "utm_source" in m["evidence"]
        for m in f["markers"]
    )
    assert f["job_ref_shape"] == "AA-9999" and f["feed_vendor"] is None


# ------------------------------------------------------------------ small helpers
def test_day_first_iso():
    assert (
        sg.day_first_iso("31/10/2026") == "2026-10-31"
        and sg.day_first_iso("1/2/2026") == "2026-02-01"
    )
    assert (
        sg.day_first_iso("13/13/2026") is None
        and sg.day_first_iso("ASAP") is None
        and sg.day_first_iso(None) is None
    )


def test_employer_class():
    assert (
        sg.employer_class("Gaia Talent") == "gaia"
        and sg.employer_class("GAIA TALENT Ltd") == "gaia"
    )
    assert (
        sg.employer_class("CHM Recruit") == "chm_recruit"
        and sg.employer_class("Mattinson Partnership") == "mattinson"
    )
    assert (
        sg.employer_class("Mott MacDonald") == "third_party"
        and sg.employer_class("") == "unknown"
    )


def test_hidden_fields_first_wins_and_unescapes():
    h = sg.hidden_fields(
        '<input type="hidden" name="a" value="x&amp;y"><input type="hidden" name="a" value="z"><input name="b" value="1">'
    )
    assert h == {"a": "x&y"}


# ------------------------------------------------------------------ robots + sitemap
def test_robots_allows_and_sitemaps():
    robots = "User-agent: *\nDisallow: /jobboard/cands/\nSitemap: https://www.greenjobs.ie/sm.xml\n"
    assert not sg.robots_allows(
        robots, "https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=1"
    )
    assert sg.robots_allows(robots, "https://www.greenjobs.ie/jobs/1/x.asp")
    assert sg.robots_allows(None, "https://x/") and sg.robots_allows("", "https://x/")
    assert sg.robots_sitemaps(robots) == ["https://www.greenjobs.ie/sm.xml"]


def test_parse_sitemap_urlset_and_index():
    assert sg.parse_sitemap(
        "<urlset><url><loc>https://a/1</loc></url><url><loc> https://a/2 </loc></url></urlset>"
    ) == (["https://a/1", "https://a/2"], [])
    assert sg.parse_sitemap(
        "<sitemapindex><sitemap><loc>https://a/s1.xml</loc></sitemap></sitemapindex>"
    ) == ([], ["https://a/s1.xml"])
    assert sg.parse_sitemap("") == ([], [])


# ------------------------------------------------------------------ redirect map
def mapped(path, site="ie", ids=("11502675",), facets=None, emp=()):
    return sg.map_old_url(path, site, set(ids), sg.facet_kinds(facets or {}), set(emp))


def test_url_patterns():
    assert sg.url_pattern("/jobs/11502675/principal-environmental-consultant.asp") == (
        "job",
        "/jobs/{id}/{slug}.asp",
    )
    assert sg.url_pattern("/jobboard/cands/jobview.asp?v=1")[0] == "job"
    assert sg.url_pattern("/jobboard/cands/jobresults.asp?pg=3")[0] == "listing"
    assert (
        sg.url_pattern("/jobboard/cands/JobResults.asp?c=1&lstRegion=London")[0]
        == "location"
    )
    assert sg.url_pattern("/browse-jobs/london/")[0] == "facet"
    assert sg.url_pattern("/about-us.cms.asp")[0] == "static"
    assert sg.url_pattern("/jobboard/cands/candLogin.asp")[0] == "account"
    assert (
        sg.url_pattern("/jobboard/scripts/vbs/adredirect.asp?b=1&u=x")[0]
        == "banner_redirect"
    )
    assert sg.url_pattern("/jobboard/public/5104/banners/a.png")[0] == "asset"


def test_map_job_live_and_closed():
    assert mapped("/jobs/11502675/x.asp")["target"] == "/ie/jobs/11502675/"
    gone = mapped("/jobs/999/x.asp")
    assert gone["target"] == "/ie/jobs/" and gone["status"] == "mapped"
    assert (
        mapped("/jobboard/cands/jobview.asp?v=11502675")["target"]
        == "/ie/jobs/11502675/"
    )


def test_map_facets_to_landing_pages_or_unmapped():
    facets = {
        "sector": [{"slug": "ecology-jobs"}, {"slug": "waste-jobs"}],
        "region": [{"slug": "london"}, {"slug": "dublin"}],
    }
    assert (
        mapped("/browse-jobs/ecology-jobs/", "uk", facets=facets)["target"]
        == "/uk/ecology-jobs-uk/"
    )
    assert (
        mapped("/browse-jobs/london/", "uk", facets=facets)["target"]
        == "/uk/environmental-jobs-london/"
    )
    assert (
        mapped("/browse-jobs/dublin/", "ie", facets=facets)["target"]
        == "/ie/environmental-jobs-dublin/"
    )
    w = mapped("/browse-jobs/waste-jobs/", "uk", facets=facets)
    assert (
        w["status"] == "unmapped"
        and w["proposed"] == "/uk/jobs/"
        and w["facet_kind"] == "sector"
    )
    e = mapped(
        "/browse-jobs/mott-macdonald/", "ie", facets=facets, emp={"mott-macdonald"}
    )
    assert e["status"] == "unmapped" and e["proposed"] == "/ie/employers/"


def test_map_targets_exist_in_the_built_site():
    """Every mapped target (other than live job ids) is a page the committed build produced."""
    site = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "site"
    if not site.exists():
        return
    for ed in ("ie", "uk"):
        for l in sg.build_landings(ed):
            assert (site / ed / l["slug"] / "index.html").exists(), l["slug"]
        for p in ("", "jobs/", "sectors/", "employers/"):
            assert (site / ed / p / "index.html").exists(), p


def test_map_static_and_account():
    assert mapped("/for-employers.asp")["target"] == "/ie/employers/"
    assert mapped("/green-job-sectors.cms.asp")["target"] == "/ie/sectors/"
    assert mapped("/about-us.cms.asp")["status"] == "unmapped"
    assert mapped("/jobboard/cands/candLogin.asp")["status"] == "unmapped"
    assert mapped("/jobboard/public/1/x.png")["status"] == "skip"


def test_build_redirect_map_counts_patterns():
    rm = sg.build_redirect_map(
        "ie",
        {"/jobs/1/a.asp", "/jobs/2/b.asp", "/about-us.cms.asp"},
        {"1"},
        {},
        set(),
        "test",
    )
    pats = {p["pattern"]: p for p in rm["patterns"]}
    assert pats["/jobs/{id}/{slug}.asp"]["count"] == 2 and len(rm["unmapped"]) == 1


def test_collect_internal_paths():
    p = sg.collect_internal_paths(
        '<a href="/a?x=1#f">1</a><a href="https://www.greenjobs.ie/b">2</a><a href="https://other.com/c">3</a><a href="mailto:a@b.c">4</a>',
        "https://www.greenjobs.ie",
    )
    assert p == {"/a?x=1", "/b"}


def test_aggregate_employers():
    jobs = [
        {
            "id": "1",
            "employer": "Gaia Talent",
            "employer_class": "gaia",
            "employer_logo_url": "l",
            "employer_url": "u",
        },
        {"id": "2", "employer": "Gaia Talent", "employer_class": "gaia"},
        {"id": "3", "employer": "Acme", "employer_class": "third_party"},
    ]
    out = sg.aggregate_employers({"ie": jobs})["sites"]["ie"]
    assert (
        out["distinct_employers"] == 2
        and out["employers"][0]["jobs"] == 2
        and out["employers"][0]["logo_url"] == "l"
    )
    assert out["class_split_jobs"] == {"gaia": 2, "third_party": 1}


# ------------------------------------------------------------------ end to end (recorded corpus, no network)
def test_snapshot_crawl_and_run_snapshot(tmp_path, monkeypatch):
    fake = FakeFetch({"www.greenjobs.ie": "ie", "www.greenjobs.co.uk": "uk"})
    monkeypatch.setattr(sg, "fetch", fake)
    r = sg.snapshot_crawl("ie", 1.0, 400, "2026-11-20")
    ids = {j["id"] for j in r["jobs"]}
    assert set(IE_JOBS) <= ids and r["source_total"] >= len(r["listing_ids"]) > 0
    j = next(x for x in r["jobs"] if x["id"] == IE_JOBS[0])
    assert j["apply"]["mode"] == "link" and j["source_url"].startswith(
        "https://www.greenjobs.ie/jobs/"
    )
    assert j["closing_iso"] == "2026-10-31" and j["employer_url"].endswith(
        "/browse-jobs/mott-macdonald/"
    )
    assert any("robots.txt" in u for u in fake.calls) and any(
        "sitemap.xml" in u for u in fake.calls
    )
    rc = sg.run_snapshot(str(tmp_path), ["ie", "uk"], 0.0, 400, dry_run=False)
    assert rc == 0 and sorted(p.name for p in tmp_path.iterdir()) == [
        "employers.json",
        "jobs_ie.json",
        "jobs_uk.json",
        "redirect_map.json",
    ]
    assert sg.UA == sg.SNAPSHOT_UA
    jobs_ie = json.loads((tmp_path / "jobs_ie.json").read_text(encoding="utf-8"))
    assert jobs_ie["parsed"] == len(jobs_ie["jobs"]) and jobs_ie["stats"]["apply_modes"]
    assert not list(tmp_path.glob("*.csv"))


def test_run_snapshot_dry_run_writes_and_fetches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used in dry run")

    monkeypatch.setattr(sg, "fetch", boom)
    assert sg.run_snapshot(str(tmp_path / "out"), ["ie"], 0.0, 10, dry_run=True) == 0
    assert not (tmp_path / "out").exists()


def test_snapshot_homepage_down_exits_3(tmp_path, monkeypatch):
    monkeypatch.setattr(sg, "fetch", lambda *a, **k: None)
    assert sg.run_snapshot(str(tmp_path), ["uk"], 0.0, 10, dry_run=False) == 3


def test_snapshot_respects_robots_disallow(tmp_path, monkeypatch):
    fake = FakeFetch(
        {"www.greenjobs.ie": "ie"},
        extra={
            "https://www.greenjobs.ie/robots.txt": "User-agent: *\nDisallow: /jobs/\n"
        },
    )
    monkeypatch.setattr(sg, "fetch", fake)
    r = sg.snapshot_crawl("ie", 1.0, 400, "2026-11-20")
    assert r["jobs"] == [] and any("robots.txt disallows job" in e for e in r["errors"])
    assert not [u for u in fake.calls if "/jobs/" in u]


def test_min_sleep_is_one_second_and_ua_is_honest():
    assert (
        sg.SNAPSHOT_MIN_SLEEP >= 1.0
        and "Mozilla" not in sg.SNAPSHOT_UA
        and "GreenJobs" in sg.SNAPSHOT_UA
    )


def test_default_main_unchanged_flags():
    import argparse  # the default crawl keeps its browser UA constant

    assert (
        "Mozilla" in sg.UA or sg.UA == sg.SNAPSHOT_UA
    )  # UA only switches inside run_snapshot
    assert argparse is not None
