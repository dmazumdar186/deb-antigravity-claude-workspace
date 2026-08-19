"""
Orchestrator and link-liveness tests.

Written after a coverage pass showed `run.py` at 11% -- 548 of 615 statements
untested -- in a session where three separate bugs had lived in exactly that
file. The 105 tests that existed were all pointed at the layers; the thing that
sequences them had none.

Everything here runs with zero network.
"""

from __future__ import annotations

import json

import pytest

from gtm_client_workflows.gaia_sourcing.layers import linkcheck


# ---------------------------------------------------------------------------
# L12 -- "could not check" is not "broken"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [999, 403, 429, 401])
def test_bot_blocked_is_unverifiable_not_dead(monkeypatch, status):
    """A host that refuses robots has told us nothing about the page.

    LinkedIn answers every non-browser client with 999. Read as "dead", it put
    "1 source link(s) did not return 200" on eight of eleven delivered cards --
    including the only Tier A candidate -- when each link was that person's
    live LinkedIn profile. A reader who clicks one and finds it works has been
    handed a reason to distrust every other check on the page.
    """
    monkeypatch.setattr(linkcheck, "head_ok", lambda url, timeout=20: (False, status))

    check = linkcheck.check_url("https://www.linkedin.com/in/someone")

    assert check.alive is None, "bot-block must not be recorded as dead"
    assert check.unverifiable is True
    assert "not evidence the page is missing" in check.note


@pytest.mark.parametrize("status", [404, 410, 500, 0])
def test_genuine_failures_are_still_dead(monkeypatch, status):
    monkeypatch.setattr(linkcheck, "head_ok", lambda url, timeout=20: (False, status))

    check = linkcheck.check_url("https://example.ie/gone")

    assert check.alive is False
    assert check.unverifiable is False


def test_report_separates_dead_from_unverifiable():
    report = linkcheck.LinkReport(person_id="p1", checks=[
        linkcheck.LinkCheck(url="https://a.ie", alive=True, http_status=200),
        linkcheck.LinkCheck(url="https://linkedin.com/in/x", alive=None, http_status=999),
        linkcheck.LinkCheck(url="https://b.ie/gone", alive=False, http_status=404),
    ])

    assert [c.http_status for c in report.dead] == [404]
    assert [c.http_status for c in report.unverifiable] == [999]
    # One link is genuinely gone, so this cannot claim everything is live.
    assert report.all_alive is False


def test_all_alive_is_false_when_a_link_is_merely_unchecked():
    """"All links live and checked" is a claim about links we reached."""
    report = linkcheck.LinkReport(person_id="p1", checks=[
        linkcheck.LinkCheck(url="https://a.ie", alive=True, http_status=200),
        linkcheck.LinkCheck(url="https://linkedin.com/in/x", alive=None, http_status=999),
    ])

    assert report.all_alive is False
    assert report.dead == []


# ---------------------------------------------------------------------------
# L0 -- stage persistence and failure containment
# ---------------------------------------------------------------------------


@pytest.fixture
def run_module(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing import run as R

    monkeypatch.setattr(R, "RUN_DIR", tmp_path)
    monkeypatch.setattr(R, "DOCS", tmp_path / "docs.jsonl")
    return R


def test_save_and_load_round_trip(run_module):
    run_module.save("demo", {"a": 1, "b": ["x"]})
    assert run_module.done("demo") is True
    assert run_module.load("demo") == {"a": 1, "b": ["x"]}


def test_load_of_an_unrun_stage_is_an_explicit_failure(run_module):
    assert run_module.done("never_ran") is False
    with pytest.raises(SystemExit) as exc:
        run_module.load("never_ran")
    assert "has not run yet" in str(exc.value)


def test_run_all_survives_a_failing_item(run_module):
    """One bad item degrades coverage by one item, never by the batch.

    ThreadPoolExecutor.map re-raises the first exception when its results are
    consumed, which killed a whole stage and cost ~190 already-extracted people
    -- stages save only at the end, so everything in memory went with it.
    """
    done_items: list[int] = []

    def work(n: int) -> None:
        if n == 3:
            raise ValueError("this item is broken")
        done_items.append(n)

    failures = run_module.run_all(work, [1, 2, 3, 4, 5], workers=2, label="t")

    assert failures == 1
    assert sorted(done_items) == [1, 2, 4, 5]


def test_run_all_reports_every_failure(run_module):
    failures = run_module.run_all(
        lambda n: (_ for _ in ()).throw(RuntimeError("no")), [1, 2, 3], workers=2
    )
    assert failures == 3


def test_docs_store_deduplicates_by_doc_id(run_module):
    from datetime import date

    from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument

    def doc(doc_id: str, text: str) -> RawDocument:
        return RawDocument(
            doc_id=doc_id, url="https://example.ie/d", source_type="other",
            fetched_at=date(2026, 8, 19), content_text=text, http_status=200,
        )

    run_module.save_docs([doc("d1", "one"), doc("d2", "two")])
    run_module.save_docs([doc("d1", "one"), doc("d3", "three")])

    loaded = run_module.load_docs()
    assert set(loaded) == {"d1", "d2", "d3"}


def test_docs_store_skips_a_torn_line(run_module):
    """A partially written line must lose one document, not the store."""
    run_module.DOCS.write_text(
        json.dumps({
            "doc_id": "d1", "url": "https://example.ie/a", "source_type": "other",
            "fetched_at": "2026-08-19", "content_text": "ok", "http_status": 200,
        }) + "\n{\"doc_id\": \"trunca\n",
        encoding="utf-8",
    )
    assert set(run_module.load_docs()) == {"d1"}


# ---------------------------------------------------------------------------
# L0 -- employer attribution, which reached delivered cards twice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "assertion,expected",
    [
        ("Susie Coyle is an Associate Director at Jacobs.", "Jacobs"),
        # The LAST preposition wins. A lazy prefix took the first "of" and the
        # character class swallowed the rest, yielding "Highways in Jacobs".
        ("Senior Associate Director of Highways in Jacobs", "Jacobs"),
        ("She is a Director of Roughan & O Donovan.", "Roughan & O Donovan"),
        (
            "Programme Manager in the Capital Investments division of "
            "Iarnrod Eireann",
            "Iarnrod Eireann",
        ),
        # Not employers. "Dublin office" overwrote "Barrett Mahony Consulting
        # Engineers" on a delivered card.
        ("Rouslan Taskov is a Director based in the Dublin office", None),
        ("He leads the Structures team", None),
        ("He holds a degree in civil engineering.", None),
    ],
)
def test_employer_extraction(run_module, assertion, expected):
    assert run_module._employer_from_claim(assertion) == expected


def test_duplicate_quote_key_is_whitespace_and_case_insensitive(run_module):
    """The same quote re-rendered with different spacing is one claim.

    The same staff page fetched as ocsc.ie/people and www.ocsc.ie/people gets
    two doc_ids, so claim_id -- a hash of (person, doc, quote) -- does not
    collapse them. Left alone it printed every bullet twice AND inflated the
    primary-signal count that decides the tier.
    """
    a = run_module._norm_quote("Chartered Engineer  (CEng MIEI)")
    b = run_module._norm_quote("chartered engineer (ceng miei)")
    assert a == b
