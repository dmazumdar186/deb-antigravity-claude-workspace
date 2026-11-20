"""Offline tests for the Gaia feed sync (gaia_feed_sync.py) and its eval fixtures.

Run: python3 -m pytest tests/greenjobs_redesign/test_gaia_feed_sync.py -q
No network, no keys: Jev is either disabled or replaced by a fake.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(ROOT / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
)
import gaia_feed_sync as gfs  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "gaia_eval"
SNAP = FIX / "gaia_snapshot_2026-11-20.json"
BOARD = FIX / "board_snapshot_2026-11-20.json"

TAX = {
    "job_location": [
        {"id": 1, "name": "Dublin", "slug": "dublin", "parent": 0},
        {"id": 2, "name": "Naas", "slug": "naas", "parent": 0},
        {"id": 3, "name": "Meath", "slug": "meath", "parent": 0},
    ],
    "job_category": [
        {"id": 10, "name": "Ecologist", "slug": "ecologist", "parent": 0},
        {"id": 11, "name": "Engineering", "slug": "engineering", "parent": 0},
    ],
    "job_type": [
        {"id": 20, "name": "Permanent", "slug": "permanent", "parent": 0},
        {"id": 21, "name": "Contract", "slug": "contract", "parent": 0},
    ],
    "job_sector": [
        {"id": 30, "name": "Ecology", "slug": "ecology", "parent": 0},
        {"id": 31, "name": "Engineering", "slug": "engineering", "parent": 0},
        {"id": 32, "name": "Civil Engineering", "slug": "civil", "parent": 0},
    ],
}


def job(
    i: int,
    title: str,
    content: str,
    loc: int = 1,
    sec: int = 30,
    cat: int = 10,
    typ: int = 20,
    modified: str = "2026-11-01T10:00:00",
) -> dict:
    return {
        "id": i,
        "date_gmt": "2026-11-01T09:00:00",
        "modified_gmt": modified,
        "slug": f"j{i}",
        "status": "publish",
        "link": f"https://gaiatalent.com/jobs/j{i}/",
        "title": title,
        "content": content,
        "job_location": [loc],
        "job_category": [cat],
        "job_type": [typ],
        "job_sector": [sec],
        "acf": {"overview_salary": "", "overview_closing_date": None},
    }


ECO_TEXT = "<p>Location: Dublin. Our client seeks an Ecologist to deliver habitat surveys across Leinster, prepare ecological impact reports and mentor junior staff on bat and bird surveys.</p>"


def snap(jobs: list[dict]) -> dict:
    return {"source": "test", "total": len(jobs), "jobs": jobs, "taxonomies": TAX}


class FakeJev(gfs.Jev):
    """Answers every question with a fixed choice/noul and confidence; no network."""

    def __init__(
        self, choice: dict[str, str], conf: float = 0.9, noul: float = 0.9
    ) -> None:
        self.cache, self.cache_path, self.enabled, self.reason = {}, None, True, ""
        self.calls = self.errors = 0
        self.cost = 0.0
        self.choice_by_q, self.conf, self.nv = choice, conf, noul

    def ask_many(self, items):
        out = []
        for _state, qs in items:
            q = next(iter(qs))
            self.calls += 1
            if qs[q]["type"] == "noul":
                out.append({q: {"noul": self.nv}})
            else:
                out.append(
                    {
                        q: {
                            "choice": self.choice_by_q.get(q, "none"),
                            "confidence": self.conf,
                        }
                    }
                )
        return out


def run_offline(tmp: Path, s: dict, board: list[dict] | None = None, **kw) -> dict:
    return gfs.run(s, board or [], tmp, use_jev=False, **kw)


# ---------------------------------------------------------------- fetch / pagination


def test_pagination_reads_every_page_and_checks_total():
    pages = {
        1: [{"id": i} for i in range(100)],
        2: [{"id": i} for i in range(100, 200)],
        3: [{"id": i} for i in range(200, 250)],
    }
    seen = []

    def get(url):
        page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["page"][0])
        seen.append(page)
        return pages[page], {"x-wp-total": "250", "x-wp-totalpages": "3"}

    rows = gfs.fetch_paged(get, "jobs", {}, sleep_s=0)
    assert len(rows) == 250 and seen == [1, 2, 3]


def test_pagination_count_mismatch_fails_loud():
    def get(url):
        return [{"id": 1}], {"x-wp-total": "2", "x-wp-totalpages": "1"}

    with pytest.raises(gfs.GateError):
        gfs.fetch_paged(get, "jobs", {}, sleep_s=0)


def test_http_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    class Resp(io.BytesIO):
        headers = {"X-WP-Total": "1"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        assert (
            "GreenJobsFeedSync" in req.get_header("User-agent")
            and timeout == gfs.TIMEOUT_S
        )
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, None)
        return Resp(b"[]")

    monkeypatch.setattr(gfs.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gfs.time, "sleep", lambda s: None)
    data, hdrs = gfs.http_get_json("https://example.invalid/x")
    assert data == [] and calls["n"] == 3 and hdrs["x-wp-total"] == "1"


def test_http_404_is_not_retried(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 404, "nope", {}, None)

    monkeypatch.setattr(gfs.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        gfs.http_get_json("https://example.invalid/x")
    assert calls["n"] == 1


# ---------------------------------------------------------------- sanitisation


def test_sanitiser_strips_scripts_handlers_and_bad_links():
    raw = (
        '<div style="x" onclick="evil()">Hi <script>alert(1)</script><style>p{}</style>'
        '<a href="javascript:alert(2)">bad</a> <a href="https://ok.example/a?b=1&c=2" onmouseover="x">ok</a>'
        '<iframe src="https://x"></iframe><img src=x onerror=alert(3)><ul><li>one</li></ul></div>'
    )
    out = gfs.sanitise_html(raw)
    low = out.lower()
    for bad in (
        "<script",
        "alert",
        "<style",
        "onclick",
        "onmouseover",
        "onerror",
        "javascript:",
        "<iframe",
        "<img",
        "style=",
    ):
        assert bad not in low, bad
    assert (
        '<a href="https://ok.example/a?b=1&amp;c=2" rel="nofollow noopener">ok</a>'
        in out
    )
    assert "<ul><li>one</li></ul>" in out and out.startswith("<p>")


def test_sanitiser_closes_unclosed_tags_and_escapes_text():
    out = gfs.sanitise_html("<p><strong>a < b & c")
    assert out == "<p><strong>a &lt; b &amp; c</strong></p>"


# ---------------------------------------------------------------- mapping


def test_dictionary_mapping_and_record_shape(tmp_path):
    rep = run_offline(tmp_path, snap([job(1, "Ecologist", ECO_TEXT)]))
    rec = json.loads((tmp_path / "feed.json").read_text())["jobs"][0]
    assert (
        rec["source_id"] == "gaia:1"
        and rec["sector"] == "Ecology, nature recovery & biodiversity"
    )
    assert (
        rec["region"] == "Dublin"
        and rec["job_type"] == "Permanent"
        and rec["boards"] == ["ie"]
    )
    assert rec["apply"] == {"method": "url", "url": "https://gaiatalent.com/jobs/j1/"}
    assert rec["posted_at"] == "2026-11-01T09:00:00Z" and rec["status"] == "ready"
    assert rep["mapped_deterministically"] == 3 and rep["queued"] == 0


def test_town_maps_to_county_and_mailto_is_email_apply(tmp_path):
    s = snap(
        [
            job(
                2,
                "Ecologist",
                ECO_TEXT.replace("Location: Dublin", "Location: Naas")
                + '<a href="mailto:jobs@example.com">apply</a>',
                loc=2,
            )
        ]
    )
    run_offline(tmp_path, s)
    rec = json.loads((tmp_path / "feed.json").read_text())["jobs"][0]
    assert rec["region"] == "Kildare"
    assert (
        rec["apply"]["method"] == "email"
        and rec["apply"]["email"] == "jobs@example.com"
    )


def test_conflicts_queue_without_jev_never_guess(tmp_path):
    # Gaia term says Meath + Permanent, but the advert's Location line says Westmeath and it is a
    # specified-purpose contract; the title names two sectors (road + water): all three go to review.
    text = "<p>Location: Mullingar, Co. Westmeath Job Type: Specified Purpose Contract</p><p>Road drainage and water works.</p>"
    rep = run_offline(
        tmp_path,
        snap([job(3, "Road Drainage Engineer – Water", text, loc=3, sec=31, cat=11)]),
    )
    rec = json.loads((tmp_path / "feed.json").read_text())["jobs"][0]
    assert rec["sector"] is None and rec["region"] is None and rec["job_type"] is None
    assert rec["status"] == "needs_review" and rep["queued"] == 3
    q = json.loads((tmp_path / "review_queue.json").read_text())
    assert {i["dimension"] for i in q["items"]} == {"sector", "region", "job_type"}
    assert all("Jev disabled" in i["reason"] for i in q["items"])


def test_jev_low_confidence_goes_to_queue_high_is_used():
    recs = gfs.normalise(
        snap(
            [
                job(
                    4,
                    "Engineer",
                    "<p>Location: Dublin. General engineering role.</p>",
                    sec=31,
                    cat=11,
                )
            ]
        ),
        gfs.load_mapping(),
    )
    regions, mapping = gfs.load_regions(), gfs.load_mapping()
    gfs.map_jobs(
        recs, mapping, regions, FakeJev({"sector": "water_flood"}, conf=0.3), cut=0.6
    )
    m = recs[0]["mapping"]["sector"]
    assert (
        m["method"] == "queue"
        and m["value"] is None
        and m["jev_value"] == "Water & flood"
    )
    recs = gfs.normalise(
        snap(
            [
                job(
                    4,
                    "Engineer",
                    "<p>Location: Dublin. General engineering role.</p>",
                    sec=31,
                    cat=11,
                )
            ]
        ),
        mapping,
    )
    gfs.map_jobs(
        recs, mapping, regions, FakeJev({"sector": "water_flood"}, conf=0.95), cut=0.6
    )
    assert recs[0]["mapping"]["sector"] == {
        "method": "jev",
        "confidence": 0.95,
        "reason": "Jev choice",
        "value": "Water & flood",
    }


def test_jev_abstain_or_unknown_option_is_queued():
    mapping, regions = gfs.load_mapping(), gfs.load_regions()
    recs = gfs.normalise(
        snap([job(5, "Engineer", "<p>x</p>", sec=31, cat=11)]), mapping
    )
    gfs.map_jobs(
        recs, mapping, regions, FakeJev({"sector": "none"}, conf=0.99), cut=0.6
    )
    assert recs[0]["mapping"]["sector"]["method"] == "queue"
    recs = gfs.normalise(
        snap([job(5, "Engineer", "<p>x</p>", sec=31, cat=11)]), mapping
    )
    gfs.map_jobs(
        recs,
        mapping,
        regions,
        FakeJev({"sector": "made_up_sector"}, conf=0.99),
        cut=0.6,
    )
    assert recs[0]["mapping"]["sector"]["method"] == "queue"


def test_jev_region_options_are_irish_only_for_gaia():
    q = gfs.region_question(gfs.load_regions(), ["ie"])["region"]["criteria"]
    assert "ie_dublin" in q and not any(k.startswith("uk_") for k in q) and "none" in q


def test_mapping_file_rejects_unknown_vocab(tmp_path):
    m = json.loads(gfs.MAPPING_PATH.read_text())
    m["sector_by_gaia_sector"]["ecology"] = "Not A Sector"
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        gfs.load_mapping(p)


# ---------------------------------------------------------------- dedupe


def board_job(
    i: str,
    title: str,
    text: str,
    employer: str = "Gaia Talent",
    site: str = "ie",
    location: str = "Dublin",
) -> dict:
    return {
        "id": i,
        "site": site,
        "title": title,
        "employer": employer,
        "location": location,
        "url": f"https://b/{i}",
        "text": text,
    }


def test_dedupe_both_directions(tmp_path):
    s = snap(
        [
            job(1, "Ecologist", ECO_TEXT),
            job(
                2,
                "Senior Planner",
                "<p>Location: Dublin. Lead planning applications for wind farms and grid connections nationally.</p>",
            ),
        ]
    )
    copy = board_job("100", "Ecologist", gfs.plain_text(ECO_TEXT))
    other_emp = board_job(
        "101", "Ecologist", gfs.plain_text(ECO_TEXT), employer="Mattinson Partnership"
    )
    orphan = board_job(
        "102",
        "Water Director",
        "Gaia Talent's client seeks a Water Director for a national utility.",
    )
    rep = run_offline(tmp_path, s, [copy, other_emp, orphan])
    feed = {
        r["source_id"]: r
        for r in json.loads((tmp_path / "feed.json").read_text())["jobs"]
    }
    assert feed["gaia:1"]["on_board"] == [
        {"site": "ie", "board_id": "100", "method": "rule"}
    ]  # feed -> board
    assert feed["gaia:2"]["on_board"] == []
    dd = json.loads((tmp_path / "dedupe.json").read_text())
    assert dd["board_only"] == [
        {"site": "ie", "board_id": "102", "title": "Water Director"}
    ]  # board -> feed
    assert all(
        p["board_id"] != "101" for p in dd["pairs"]
    )  # another employer's advert is never a Gaia duplicate
    assert (
        rep["duplicates_found"] == 1
        and rep["new_vs_board"] == 1
        and rep["board_gaia_jobs_not_in_feed"] == 1
    )


def test_same_title_rewrite_is_ambiguous_not_auto_merged(tmp_path):
    s = snap(
        [
            job(
                1,
                "Senior Planner",
                "<p>Location: Dublin. Lead planning applications for wind farms and grid connections nationally.</p>",
            )
        ]
    )
    rewrite = board_job(
        "200",
        "Senior Planner",
        "An established consultancy in Galway and Sligo seeks a Senior Planner to manage strategic housing applications.",
    )
    run_offline(tmp_path, s, [rewrite])
    dd = json.loads((tmp_path / "dedupe.json").read_text())
    assert [p["verdict"] for p in dd["pairs"]] == [
        "queue"
    ]  # no Jev -> review, never guessed
    regions = gfs.load_regions()
    recs = gfs.normalise(s, gfs.load_mapping())
    v = gfs.judge_pairs([(recs[0], rewrite)], regions, FakeJev({}, noul=0.95), 0.8, 0.2)
    assert v[0]["verdict"] == "dup" and v[0]["method"] == "jev"
    v = gfs.judge_pairs([(recs[0], rewrite)], regions, FakeJev({}, noul=0.5), 0.8, 0.2)
    assert v[0]["verdict"] == "queue"
    v = gfs.judge_pairs([(recs[0], rewrite)], regions, FakeJev({}, noul=0.05), 0.8, 0.2)
    assert v[0]["verdict"] == "not"


def test_board_advert_copied_from_one_job_is_not_dup_of_another():
    a = job(
        1,
        "Principal Ecologist",
        "<p>Location: Ireland. Lead and expand the ecology team of an established multidisciplinary consultancy, managing surveys and reports.</p>",
    )
    b = job(
        2,
        "Principal Ecologist",
        "<p>Position: Principal Ecologist. Location: Dublin, Cork or Galway. Our client is expanding its team across Ireland.</p>",
    )
    s = snap([a, b])
    recs = gfs.normalise(s, gfs.load_mapping())
    copy_of_a = board_job("300", "Principal Ecologist", recs[0]["description_text"])
    v = gfs.judge_pairs(
        [(recs[0], copy_of_a), (recs[1], copy_of_a)],
        gfs.load_regions(),
        FakeJev({}, noul=0.99),
        0.8,
        0.2,
    )
    assert v[0]["verdict"] == "dup" and v[0]["method"] == "rule"
    assert v[1]["verdict"] == "not" and "already a copy of gaia:1" in v[1]["reason"]


def test_rss_board_loader(tmp_path):
    p = tmp_path / "gj.xml"
    p.write_text(
        '<?xml version="1.0"?><rss><channel><item><title>Ecologist</title><link>https://www.greenjobs.ie/jobboard/cands/jobview.asp?v=123&amp;rcode=RSS</link>'
        "<description>Our client seeks</description></item></channel></rss>"
    )
    rows = gfs.load_board(p, "ie")
    assert (
        rows[0]["id"] == "123"
        and rows[0]["employer"] is None
        and rows[0]["site"] == "ie"
    )


# ---------------------------------------------------------------- outputs, idempotency, gates


def test_rerun_is_byte_identical_and_report_converges(tmp_path):
    s = snap(
        [
            job(1, "Ecologist", ECO_TEXT),
            job(2, "Engineer", "<p>Location: Dublin.</p>", sec=31, cat=11),
        ]
    )
    run_offline(tmp_path, s)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    rep2 = run_offline(tmp_path, s)
    second = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    rep3 = run_offline(tmp_path, s)
    third = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert (
        first["feed.json"] == second["feed.json"]
        and first["feed.xml"] == second["feed.xml"]
    )
    assert second == third  # every file, report included, once nothing changes
    assert rep2["new"] == rep2["updated"] == rep2["removed"] == 0 and rep3 == rep2
    assert not list(tmp_path.glob("*.tmp"))


def test_update_and_remove_are_counted(tmp_path):
    a, b = job(1, "Ecologist", ECO_TEXT), job(2, "Senior Ecologist", ECO_TEXT)
    run_offline(tmp_path, snap([a, b]))
    a2 = job(
        1, "Ecologist", ECO_TEXT + "<p>Now hybrid.</p>", modified="2026-11-02T10:00:00"
    )
    rep = run_offline(tmp_path, snap([a2, b]), max_removed_share=1.0)
    assert (rep["new"], rep["updated"], rep["removed"]) == (0, 1, 0)
    rep = run_offline(tmp_path, snap([a2]), max_removed_share=0.5)
    assert rep["removed"] == 1 and rep["removed_ids"] == ["gaia:2"]


def test_gates_empty_fetch_and_mass_removal(tmp_path):
    with pytest.raises(gfs.GateError):
        run_offline(tmp_path, snap([]))
    jobs = [job(i, f"Ecologist {i}", ECO_TEXT) for i in range(1, 5)]
    run_offline(tmp_path, snap(jobs))
    with pytest.raises(gfs.GateError):
        run_offline(tmp_path, snap(jobs[:1]))  # 3 of 4 removed > 50% ceiling
    bad = snap(jobs)
    bad["total"] = 99
    with pytest.raises(gfs.GateError):
        run_offline(tmp_path / "x", bad)


def test_xml_feed_is_valid_and_complete(tmp_path):
    s = snap(
        [
            job(1, "Ecologist & Botanist <Senior>", ECO_TEXT + "<p>bad\x0bchar</p>"),
            job(2, "Engineer", "<p>Location: Dublin.</p>", sec=31, cat=11),
        ]
    )
    run_offline(tmp_path, s)
    root = ET.parse(tmp_path / "feed.xml").getroot()
    assert root.tag == "jobs" and root.get("count") == "2" and len(root) == 2
    first = root[0]
    for f in (
        "id",
        "title",
        "description",
        "location",
        "region",
        "category",
        "type",
        "url",
        "apply",
        "date",
        "expiry",
        "boards",
    ):
        assert first.find(f) is not None, f
    assert (
        first.findtext("title") == "Ecologist & Botanist <Senior>"
        and first.find("apply").get("method") == "url"
    )
    assert "\x0b" not in (tmp_path / "feed.xml").read_text()


def test_cli_offline_dry_run(tmp_path, capsys):
    s = tmp_path / "s.json"
    s.write_text(json.dumps(snap([job(1, "Ecologist", ECO_TEXT)])))
    assert (
        gfs.main(["--offline", str(s), "--out", str(tmp_path / "o"), "--no-jev"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert (
        gfs.main(
            [
                "--offline",
                str(s),
                "--out",
                str(tmp_path / "o"),
                "--no-jev",
                "--jev-cut",
                "0",
            ]
        )
        == 2
    )


# ---------------------------------------------------------------- real snapshot + eval fixtures


def test_real_snapshot_runs_offline(tmp_path):
    s = json.loads(SNAP.read_text())
    board = gfs.load_board(BOARD)
    rep = gfs.run(s, board, tmp_path, use_jev=False)
    assert (
        rep["fetched"] == 83 == rep["jobs_in_feed"]
        and rep["board_jobs_compared"] == 230
    )
    assert (
        rep["mapped_deterministically"] >= 200
    )  # dictionary + title tier cover most decisions
    assert rep["duplicates_found"] >= 60  # copied adverts found without any AI
    feed = json.loads((tmp_path / "feed.json").read_text())["jobs"]
    assert all("<script" not in r["description_html"].lower() for r in feed)
    assert len({r["source_id"] for r in feed}) == 83


def test_eval_fixtures_are_consistent():
    s = json.loads(SNAP.read_text())
    ids = {f"gaia:{j['id']}" for j in s["jobs"]}
    e1 = json.loads((FIX / "e1_labels.json").read_text())
    assert {r["source_id"] for r in e1["labels"]} == ids and e1["n"] == len(ids)
    regions = gfs.load_regions()
    names = {n for t in regions.values() for n in t["regions"]} | {
        t["none"] for t in regions.values()
    }
    types = set(gfs.load_mapping()["greenjobs_types"])
    for r in e1["labels"]:
        assert (
            r["sector"] in gfs.SECTORS
            and r["region"] in names
            and r["job_type"] in types
        ), r
    e2 = json.loads((FIX / "e2_pairs.json").read_text())
    c = e2["counts"]
    assert (
        c["positive"] + c["negative"] + c["unsure_excluded"]
        == c["pairs"]
        == len(e2["pairs"])
    )
    assert all(p["source_id"] in ids for p in e2["pairs"])
    assert c["positive"] >= 100 and c["negative"] >= 900


def test_eval_runs_offline_deterministic_tier(tmp_path):
    import gaia_feed_eval as gfe

    report = tmp_path / "r.md"
    assert gfe.main(["--no-jev", "--report", str(report)]) == 0
    text = report.read_text()
    assert "NOT RUN" in text and "E1" in text and "E2" in text and "Wilson" in text
    res = json.loads(report.with_suffix(".json").read_text())
    assert res["e2"]["rule"]["fp"] == 0  # copied-advert rule: no false merges on the labelled set
