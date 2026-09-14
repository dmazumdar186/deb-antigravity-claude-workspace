"""Unit tests for job_search_v2.normalizer.posting_verifier.

No network: fetch is always injected. parse_posting_page() is pure and tested
directly; verify_job()/verify_jobs() are tested via a fake `fetch` callable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution.personal_workflows.job_search_v2.contracts import (
    ContractType,
    JobSource,
    NormalizedJob,
    RemoteMode,
    compute_content_hash,
)
from execution.personal_workflows.job_search_v2.normalizer import posting_verifier as pv

NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def make_job(
    *,
    title="Product Manager",
    company="Acme",
    url="https://example.com/jobs/123",
    posted_at=None,
    source=JobSource.FIXTURE,
) -> NormalizedJob:
    canonical = url
    return NormalizedJob(
        source=source,
        source_id="123",
        url=url,
        canonical_url=canonical,
        title=title,
        company=company,
        location="Paris",
        description_snippet="A great job.",
        posted_at=posted_at,
        contract_type=ContractType.CDI,
        contract_type_raw="CDI",
        remote_mode=RemoteMode.REMOTE,
        fetched_at=NOW,
        content_hash=compute_content_hash(title, company, canonical),
    )


def fetch_returning(status, html, final_url=None):
    def _fetch(url):
        return status, html, final_url or url

    return _fetch


# ---------------------------------------------------------------------------
# parse_posting_page — JSON-LD
# ---------------------------------------------------------------------------


def _html_with_jsonld(payload: str) -> str:
    return f"""<html><head>
    <script type="application/ld+json">{payload}</script>
    </head><body>Apply now for this great job.</body></html>"""


def test_jsonld_object_top_level_date_posted():
    html = _html_with_jsonld('{"@type": "JobPosting", "datePosted": "2026-09-08"}')
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 8, tzinfo=timezone.utc)
    assert "jsonld:datePosted" in v.evidence
    assert v.status == "open"


def test_jsonld_at_graph():
    html = _html_with_jsonld(
        '{"@graph": [{"@type": "Organization"}, {"@type": "JobPosting", "datePosted": "2026-09-05T10:00:00Z"}]}'
    )
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
    assert v.status == "open"


def test_jsonld_array_of_objects():
    html = _html_with_jsonld('[{"@type": "JobPosting", "datePosted": "2026-09-01"}]')
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_jsonld_main_entity_nesting():
    html = _html_with_jsonld(
        '{"@type": "WebPage", "mainEntity": {"@type": "JobPosting", "datePosted": "2026-09-02"}}'
    )
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 2, tzinfo=timezone.utc)


def test_jsonld_date_only_is_midnight_utc():
    html = _html_with_jsonld('{"@type": "JobPosting", "datePosted": "2026-09-08"}')
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at.hour == 0 and v.posted_at.minute == 0


def test_jsonld_malformed_json_never_raises():
    html = _html_with_jsonld("{not valid json!!!")
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)  # must not raise
    assert v.status in ("unknown", "open")


def test_jsonld_valid_through_past_is_closed():
    html = _html_with_jsonld(
        '{"@type": "JobPosting", "datePosted": "2026-08-01", "validThrough": "2026-09-01T00:00:00Z"}'
    )
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.status == "closed"
    assert "validThrough" in v.evidence


# ---------------------------------------------------------------------------
# parse_posting_page — closed text detection
# ---------------------------------------------------------------------------

CLOSED_PHRASES_EN = [
    "No longer accepting applications",
    "This job is no longer available",
    "Job has expired",
    "This job has expired",
    "This position has been filled",
    "Applications for this job are closed",
    "Job posting has closed",
    "This job posting is no longer active",
    "The job you are looking for is no longer available",
    "Job not found",
    "This job has expired on Indeed",
]

CLOSED_PHRASES_FR = [
    "n'est plus disponible",
    "n'accepte plus de candidatures",
    "offre expirée",
    "cette offre a expiré",
    "offre d'emploi a expiré",
    "n'est plus en ligne",
    "offre pourvue",
    "poste pourvu",
    "cette annonce n'est plus d'actualité",
    "offre introuvable",
    "cette offre d'emploi n'existe plus",
    "les candidatures sont closes",
    "Cette offre n'accepte plus de candidatures",
    "Cette offre n'est plus disponible",
    "Cette offre d'emploi a expiré",
    "L'offre n'est plus disponible",
]


@pytest.mark.parametrize("phrase", CLOSED_PHRASES_EN + CLOSED_PHRASES_FR)
def test_closed_phrase_detected(phrase):
    html = f"<html><body>Some header. {phrase}. Footer text.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.status == "closed", f"expected closed for phrase: {phrase!r}"


def test_open_page_negative_case_no_false_positive():
    html = """<html><body>
    <h1>Senior Product Manager</h1>
    <p>Apply now for this exciting role.</p>
    <div>Voir toutes les offres similaires</div>
    <a href="/jobs">offres similaires</a>
    </body></html>"""
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.status != "closed"


# ---------------------------------------------------------------------------
# parse_posting_page — meta / time tags
# ---------------------------------------------------------------------------


def test_meta_article_published_time():
    html = '<html><head><meta property="article:published_time" content="2026-09-07T08:00:00Z"></head><body>Apply now</body></html>'
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 7, 8, 0, 0, tzinfo=timezone.utc)


def test_time_datetime_attr():
    html = '<html><body>Apply now <time datetime="2026-09-06">Sept 6</time></body></html>'
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == datetime(2026, 9, 6, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# parse_posting_page — relative / absolute text dates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_days_ago",
    [
        ("Posted 3 days ago", 3),
        ("Reposted 2 weeks ago", 14),
        ("Posted 1 month ago", 30),
        ("30+ days ago", 31),
        ("Posted today", 0),
        ("Posted yesterday", 1),
    ],
)
def test_relative_date_en(text, expected_days_ago):
    html = f"<html><body>Apply now. {text}.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at is not None
    delta_days = (NOW - v.posted_at).total_seconds() / 86400.0
    assert abs(delta_days - expected_days_ago) < 1.0


def test_relative_date_en_hours_ago():
    html = "<html><body>Apply now. 5 hours ago.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at is not None
    assert (NOW - v.posted_at) < timedelta(days=1)


def test_relative_date_en_just_now():
    html = "<html><body>Apply now. Just now.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == NOW


@pytest.mark.parametrize(
    "text,expected_days_ago",
    [
        ("il y a 5 jours", 5),
        ("il y a 3 semaines", 21),
        ("il y a 1 mois", 30),
        ("il y a 2 heures", 0),
        ("aujourd'hui", 0),
        ("hier", 1),
    ],
)
def test_relative_date_fr(text, expected_days_ago):
    html = f"<html><body>Postuler maintenant. {text}.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at is not None
    delta_days = (NOW - v.posted_at).total_seconds() / 86400.0
    assert abs(delta_days - expected_days_ago) < 1.0


@pytest.mark.parametrize(
    "text,expected_date",
    [
        ("publiée le 03/09/2026", datetime(2026, 9, 3, tzinfo=timezone.utc)),
        ("publié le 3 septembre 2026", datetime(2026, 9, 3, tzinfo=timezone.utc)),
        ("date de publication : 02/09/2026", datetime(2026, 9, 2, tzinfo=timezone.utc)),
        ("actualisé le 05/09/2026", datetime(2026, 9, 5, tzinfo=timezone.utc)),
    ],
)
def test_absolute_date_fr(text, expected_date):
    html = f"<html><body>Postuler maintenant. {text}.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    assert v.posted_at == expected_date


def test_first_match_in_document_order_wins():
    html = "<html><body>Apply now. Posted 3 days ago. Posted 10 days ago.</body></html>"
    v = pv.parse_posting_page(html, "https://x.com/j", NOW)
    delta_days = (NOW - v.posted_at).total_seconds() / 86400.0
    assert abs(delta_days - 3) < 1.0


# ---------------------------------------------------------------------------
# verify_job — HTTP status mapping
# ---------------------------------------------------------------------------


def test_verify_job_404_is_closed():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(404, ""))
    assert rec.status == "closed"
    assert rec.decision == "drop"
    assert rec.reason == "closed"


def test_verify_job_410_is_closed():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(410, ""))
    assert rec.status == "closed"


def test_verify_job_403_strict_default_drops_blocked():
    # strict=True is now the default: a blocked host is no longer trusted on
    # source date alone, even when the source date is fresh.
    job = make_job(posted_at=NOW - timedelta(days=2))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(403, ""))
    assert rec.status == "unverifiable"
    assert rec.decision == "drop"
    assert rec.reason == "unverifiable_blocked"
    assert rec.date_source == "source"


def test_verify_job_403_lenient_mode_keeps_fresh_source_date():
    # Was: test_verify_job_403_with_fresh_source_date_kept (lenient-by-default
    # expectation). Now requires strict=False explicitly.
    job = make_job(posted_at=NOW - timedelta(days=2))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(403, ""), strict=False)
    assert rec.status == "unverifiable"
    assert rec.decision == "keep"
    assert rec.reason == "ok_unverified_fresh"
    assert rec.date_source == "source"


def test_verify_job_403_no_source_date_dropped():
    job = make_job(posted_at=None)
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(403, ""))
    assert rec.decision == "drop"
    assert rec.reason == "unverifiable_no_date"


def test_verify_job_429_treated_as_unverifiable():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(429, ""))
    assert rec.status == "unverifiable"


def test_verify_job_999_treated_as_unverifiable():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(999, ""))
    assert rec.status == "unverifiable"


def test_verify_job_5xx_treated_as_unverifiable():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(503, ""))
    assert rec.status == "unverifiable"


def test_verify_job_none_status_fetch_failure_unverifiable():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(None, ""))
    assert rec.status == "unverifiable"


def test_verify_job_redirect_to_search_page_closed():
    job = make_job(posted_at=NOW - timedelta(days=1))
    html = "<html><body>Apply now</body></html>"
    rec = pv.verify_job(
        job, NOW, fetch=fetch_returning(200, html, final_url="https://example.com/jobs/search?q=pm")
    )
    assert rec.status == "closed"


def test_verify_job_redirect_to_host_root_closed():
    job = make_job(posted_at=NOW - timedelta(days=1))
    html = "<html><body>Apply now</body></html>"
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html, final_url="https://example.com/"))
    assert rec.status == "closed"


# ---------------------------------------------------------------------------
# verify_job — age / decision logic
# ---------------------------------------------------------------------------


def test_verify_job_stale_10_days_dropped():
    html = '<html><head><script type="application/ld+json">{"@type": "JobPosting", "datePosted": "%s"}</script></head><body>Apply now</body></html>' % (
        (NOW - timedelta(days=10)).date().isoformat()
    )
    job = make_job(posted_at=NOW - timedelta(days=10))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.decision == "drop"
    assert rec.reason == "stale"


def test_verify_job_fresh_2_days_kept():
    html = '<html><head><script type="application/ld+json">{"@type": "JobPosting", "datePosted": "%s"}</script></head><body>Apply now</body></html>' % (
        (NOW - timedelta(days=2)).date().isoformat()
    )
    job = make_job(posted_at=NOW - timedelta(days=2))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.decision == "keep"
    assert rec.reason == "ok"


def test_verify_job_no_date_at_all_dropped_age_unknown():
    html = "<html><body>Apply now for this role. No dates anywhere.</body></html>"
    job = make_job(posted_at=None)
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.decision == "drop"
    assert rec.reason == "age_unknown"


def test_page_date_overrides_stale_source_date():
    # source says 30 days old, but page JSON-LD says 2 days old -> keep.
    html = '<html><head><script type="application/ld+json">{"@type": "JobPosting", "datePosted": "%s"}</script></head><body>Apply now</body></html>' % (
        (NOW - timedelta(days=2)).date().isoformat()
    )
    job = make_job(posted_at=NOW - timedelta(days=30))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.date_source == "page"
    assert rec.decision == "keep"


def test_page_date_overrides_fresh_source_date_to_stale():
    # source says 2 days old, but page JSON-LD says 30 days old -> drop.
    html = '<html><head><script type="application/ld+json">{"@type": "JobPosting", "datePosted": "%s"}</script></head><body>Apply now</body></html>' % (
        (NOW - timedelta(days=30)).date().isoformat()
    )
    job = make_job(posted_at=NOW - timedelta(days=2))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.date_source == "page"
    assert rec.decision == "drop"
    assert rec.reason == "stale"


def test_france_travail_trusts_source_date_when_page_has_none():
    html = "<html><body>Apply now, no date on this page at all.</body></html>"
    job = make_job(posted_at=NOW - timedelta(days=2), source=JobSource.FRANCE_TRAVAIL)
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, html))
    assert rec.date_source == "source"
    assert rec.decision == "keep"


# ---------------------------------------------------------------------------
# verify_jobs — batch
# ---------------------------------------------------------------------------


def test_verify_jobs_concurrency_20_jobs():
    jobs = [make_job(url=f"https://example.com/jobs/{i}", posted_at=NOW - timedelta(days=1), title=f"PM {i}") for i in range(20)]
    html = '<html><head><script type="application/ld+json">{"@type": "JobPosting", "datePosted": "%s"}</script></head><body>Apply now</body></html>' % (
        (NOW - timedelta(days=1)).date().isoformat()
    )
    kept, stats, records = pv.verify_jobs(jobs, now=NOW, fetch=fetch_returning(200, html), concurrency=8)
    assert stats["total_in"] == 20
    assert stats["kept"] == 20
    assert len(records) == 20


def test_verify_jobs_disabled_passthrough():
    jobs = [make_job()]
    kept, stats, records = pv.verify_jobs(jobs, enabled=False)
    assert kept == jobs
    assert stats == {"disabled": True}
    assert records[jobs[0].content_hash].reason == "disabled"


def test_verify_jobs_warns_on_blocked_host():
    jobs = [make_job(url=f"https://blocked.example.com/jobs/{i}", posted_at=None) for i in range(6)]
    kept, stats, records = pv.verify_jobs(jobs, now=NOW, fetch=fetch_returning(403, ""), concurrency=4)
    assert len(stats["warnings"]) == 1
    assert "blocked.example.com" in stats["warnings"][0]
    assert stats["kept"] == 0


def test_verify_jobs_mixed_stats_shape():
    jobs = [
        make_job(url="https://example.com/1", posted_at=NOW - timedelta(days=1)),
        make_job(url="https://example.com/2", posted_at=NOW - timedelta(days=20)),
    ]
    kept, stats, records = pv.verify_jobs(jobs, now=NOW, fetch=fetch_returning(404, ""), concurrency=2)
    assert stats["rejected"] == 2
    assert "closed" in stats["by_reason"]
    assert len(stats["rejected_sample"]) == 2


# ---------------------------------------------------------------------------
# records_to_jsonl
# ---------------------------------------------------------------------------


def test_records_to_jsonl_roundtrip():
    jobs = [make_job(posted_at=NOW - timedelta(days=1))]
    _, _, records = pv.verify_jobs(jobs, now=NOW, fetch=fetch_returning(404, ""), concurrency=1)
    text = pv.records_to_jsonl(records)
    import json

    lines = [json.loads(l) for l in text.splitlines()]
    assert len(lines) == 1
    assert lines[0]["reason"] == "closed"


# ---------------------------------------------------------------------------
# Live-observed edge cases (2026-09-10 smoke test against real boards).
# ---------------------------------------------------------------------------
from datetime import datetime as _dt, timezone as _tz, timedelta as _td  # noqa: E402

from execution.personal_workflows.job_search_v2.normalizer import posting_verifier as _pv  # noqa: E402


def _mk_job_for_edge(url: str, posted_at):
    from execution.personal_workflows.job_search_v2.contracts import (
        JobSource, NormalizedJob, ContractType, RemoteMode, canonicalize_url, compute_content_hash,
    )
    canon = canonicalize_url(url)
    return NormalizedJob(
        source=JobSource.LINKEDIN_GUEST_API if hasattr(JobSource, "LINKEDIN_GUEST_API") else list(JobSource)[0],
        source_id="edge-1", url=url, canonical_url=canon, title="Product Manager", company="Acme",
        location="Paris", description_snippet="", posted_at=posted_at,
        contract_type=ContractType.UNKNOWN, remote_mode=RemoteMode.UNKNOWN,
        fetched_at=_dt.now(_tz.utc), content_hash=compute_content_hash("Product Manager", "Acme", canon),
    )


def test_linkedin_expired_redirect_is_closed():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    job = _mk_job_for_edge("https://fr.linkedin.com/jobs/view/3900000000", now - _td(days=1))
    fetch = lambda u: (200, "<html><body>" + "x" * 1000 + "</body></html>",  # noqa: E731
                       "https://www.linkedin.com/jobs/executive-medical-director-jobs?trk=expired_jd_redirect")
    rec = _pv.verify_job(job, now, fetch=fetch)
    assert rec.decision == "drop" and rec.reason == "closed" and "redirect" in rec.evidence


def test_wttj_soft_404_body_is_closed():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    job = _mk_job_for_edge("https://www.welcometothejungle.com/en/companies/x/jobs/pm_paris", now - _td(days=1))
    html = "<html><head><title>Welcome to the jungle</title><script>var notfound='page not found';</script></head>" \
           "<body><nav>Find your next job</nav><h1>Error 404</h1><p>Page not found</p>" + "<p>filler</p>" * 100 + "</body></html>"
    rec = _pv.verify_job(job, now, fetch=lambda u: (200, html, u))
    assert rec.decision == "drop" and rec.reason == "closed"


def test_script_only_404_string_does_not_close_live_page():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    html = ('<html><head><script>window.err="page not found";</script></head><body>'
            '<script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-09-09"}</script>'
            '<h1>Product Manager</h1><button>Postuler</button>' + "<p>filler</p>" * 100 + "</body></html>")
    v = _pv.parse_posting_page(html, "https://example.com/j/1", now)
    assert v.status == "open"


def test_empty_2xx_body_is_unverifiable_not_no_signal():
    # Was: expected "keep"/"ok_unverified_fresh" by default. strict=True is
    # now the default, so a blocked/empty-body page with a fresh source date
    # drops (unverifiable_blocked); the lenient path is covered separately.
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    fresh = _mk_job_for_edge("https://www.welcometothejungle.com/en/companies/x/jobs/pm_paris", now - _td(days=1))
    rec = _pv.verify_job(fresh, now, fetch=lambda u: (202, "", u))
    assert rec.status == "unverifiable" and rec.decision == "drop" and rec.reason == "unverifiable_blocked"
    undated = _mk_job_for_edge("https://www.welcometothejungle.com/en/companies/x/jobs/pm2_paris", None)
    rec2 = _pv.verify_job(undated, now, fetch=lambda u: (202, "", u))
    assert rec2.decision == "drop" and rec2.reason == "unverifiable_no_date"


def test_empty_2xx_body_lenient_mode_keeps_fresh_source_date():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    fresh = _mk_job_for_edge("https://www.welcometothejungle.com/en/companies/x/jobs/pm_paris", now - _td(days=1))
    rec = _pv.verify_job(fresh, now, fetch=lambda u: (202, "", u), strict=False)
    assert rec.status == "unverifiable" and rec.decision == "keep" and rec.reason == "ok_unverified_fresh"


def test_fetch_page_retries_soft_block_once(monkeypatch):
    calls = []

    class _Resp:
        def __init__(self, status, text, url):
            self.status_code, self.text, self.url = status, text, url

    class _Client:
        def __init__(self, *a, **k):
            pass

        def get(self, url, headers=None, timeout=None):
            calls.append(url)
            if len(calls) == 1:
                return _Resp(202, "", url)
            return _Resp(200, "<html>" + "y" * 1000 + "</html>", url)

        def close(self):
            pass

    import types, sys as _sys
    fake_httpx = types.SimpleNamespace(Client=_Client)
    monkeypatch.setitem(_sys.modules, "httpx", fake_httpx)
    monkeypatch.setattr(_pv, "_RETRY_DELAY_SECONDS", 0.0)
    status, html, final = _pv.fetch_page("https://example.com/job")
    assert status == 200 and len(html) > 500 and len(calls) == 2


def test_verify_jobs_survives_exception_in_fetch():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    fresh = _mk_job_for_edge("https://example.com/a", now - _td(days=1))
    old = _mk_job_for_edge("https://example.com/b", now - _td(days=20))

    def boom(u):
        raise RuntimeError("boom")

    kept, stats, recs = _pv.verify_jobs([fresh, old], now=now, fetch=boom, concurrency=2)
    assert [j.content_hash for j in kept] == [fresh.content_hash]
    assert recs[fresh.content_hash].reason == "ok_unverified_fresh"
    assert recs[old.content_hash].reason == "stale"
    assert all(r.evidence.startswith("error:") for r in recs.values())


# ---------------------------------------------------------------------------
# Strict mode / browser-fallback / verify_url (new in this change)
# ---------------------------------------------------------------------------


def _jsonld_open_html(date_iso: str) -> str:
    return (
        '<html><head><script type="application/ld+json">'
        f'{{"@type": "JobPosting", "datePosted": "{date_iso}"}}'
        "</script></head><body>Apply now for this great job."
        + "x" * 600 + "</body></html>"
    )


def test_verify_url_usable_without_a_job_content_hash_empty():
    rec = pv.verify_url(
        "https://example.com/jobs/999",
        source_posted_at=NOW - timedelta(days=1),
        source=JobSource.FIXTURE,
        now=NOW,
        fetch=fetch_returning(404, ""),
    )
    assert rec.content_hash == ""
    assert rec.status == "closed"


def test_browser_fallback_recovers_403_into_open():
    job = make_job(posted_at=NOW - timedelta(days=1))
    html = _jsonld_open_html((NOW - timedelta(days=1)).date().isoformat())
    rec = pv.verify_job(
        job, NOW,
        fetch=fetch_returning(403, ""),
        browser_fetch=fetch_returning(200, html),
    )
    assert rec.status == "open"
    assert rec.decision == "keep"
    assert rec.evidence.startswith("browser:")


def test_browser_fallback_recovers_403_into_closed_via_404():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(
        job, NOW,
        fetch=fetch_returning(403, ""),
        browser_fetch=fetch_returning(404, ""),
    )
    assert rec.status == "closed"
    assert rec.decision == "drop"
    assert rec.reason == "closed"
    assert "browser:" in rec.evidence


def test_browser_fallback_recovers_403_into_closed_via_text():
    job = make_job(posted_at=NOW - timedelta(days=1))
    html = "<html><body>" + "filler " * 100 + "This job has expired</body></html>"
    rec = pv.verify_job(
        job, NOW,
        fetch=fetch_returning(403, ""),
        browser_fetch=fetch_returning(200, html),
    )
    assert rec.status == "closed"
    assert rec.decision == "drop"
    assert rec.reason == "closed"


def test_browser_fallback_still_blocked_strict_drops_unverifiable_blocked():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(
        job, NOW,
        fetch=fetch_returning(403, ""),
        browser_fetch=fetch_returning(403, ""),
    )
    assert rec.status == "unverifiable"
    assert rec.decision == "drop"
    assert rec.reason == "unverifiable_blocked"
    assert rec.evidence.startswith("browser:")


def _linkedin_unknown_html() -> str:
    # Has a <time datetime> but no JSON-LD JobPosting and no apply text —
    # the "unknown" LinkedIn variant observed live.
    return (
        '<html><body><time datetime="2026-09-09">Sept 9</time>'
        "<p>Some job description content here.</p>" + "x" * 600 + "</body></html>"
    )


def test_unknown_status_refetch_returns_full_page_open_kept_strict():
    job = make_job(posted_at=NOW - timedelta(days=1))
    calls = {"n": 0}

    def fetch(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return 200, _linkedin_unknown_html(), url
        return 200, _jsonld_open_html((NOW - timedelta(days=1)).date().isoformat()), url

    rec = pv.verify_job(job, NOW, fetch=fetch)
    assert calls["n"] == 2
    assert rec.status == "open"
    assert rec.decision == "keep"


def test_unknown_status_twice_strict_drops_unconfirmed_open():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, _linkedin_unknown_html()))
    assert rec.status == "unknown"
    assert rec.decision == "drop"
    assert rec.reason == "unconfirmed_open"


def test_unknown_status_twice_lenient_keeps():
    job = make_job(posted_at=NOW - timedelta(days=1))
    rec = pv.verify_job(job, NOW, fetch=fetch_returning(200, _linkedin_unknown_html()), strict=False)
    assert rec.status == "unknown"
    assert rec.decision == "keep"
    assert rec.reason == "ok"


def test_linkedin_class_name_open_signal():
    html = (
        '<html><body><div class="top-card-layout__entity-info">'
        "<h1>Product Manager</h1></div>"
        '<button class="jobs-apply-button">Submit</button>'
        + "x" * 600 + "</body></html>"
    )
    v = pv.parse_posting_page(html, "https://linkedin.com/jobs/view/1", NOW)
    assert v.status == "open"
    assert v.evidence == "class:apply_signal"


# ---------------------------------------------------------------------------
# verify_jobs — pass 2
# ---------------------------------------------------------------------------


def test_verify_jobs_pass2_uses_browser_for_unverifiable_and_fetch_for_unknown():
    fresh = NOW - timedelta(days=1)
    blocked_job = make_job(url="https://blocked.example.com/jobs/1", posted_at=fresh, title="Blocked")
    unknown_job = make_job(url="https://linkedin.example.com/jobs/2", posted_at=fresh, title="Unknown")

    fetch_calls = {"blocked.example.com": 0, "linkedin.example.com": 0}

    def fetch(url):
        host = "blocked.example.com" if "blocked" in url else "linkedin.example.com"
        fetch_calls[host] += 1
        if host == "blocked.example.com":
            return 403, "", url
        # First fetch (pass 1) and the internal strict re-fetch inside
        # verify_url both see the "unknown" variant; only pass 2's dedicated
        # re-fetch (the 3rd normal-fetch call for this URL) resolves it.
        if fetch_calls[host] <= 2:
            return 200, _linkedin_unknown_html(), url
        return 200, _jsonld_open_html(fresh.date().isoformat()), url

    browser_calls = {"n": 0}

    def browser_fetch(url):
        browser_calls["n"] += 1
        return 200, _jsonld_open_html(fresh.date().isoformat()), url

    kept, stats, records = pv.verify_jobs(
        [blocked_job, unknown_job], now=NOW, fetch=fetch, concurrency=2,
        browser_fetch=browser_fetch,
    )

    assert browser_calls["n"] == 1  # only the unverifiable record used the browser
    assert fetch_calls["blocked.example.com"] == 1  # never fell back to plain fetch
    assert fetch_calls["linkedin.example.com"] == 3  # pass1 fetch + 1 internal retry + pass2 refetch

    assert records[blocked_job.content_hash].status == "open"
    assert records[unknown_job.content_hash].status == "open"
    assert stats["pass2_attempted"] == 2
    assert stats["pass2_recovered"] == 2
    assert stats["browser_used"] is True
    assert stats["strict"] is True
    assert kept and len(kept) == 2


def test_verify_jobs_browser_fallback_false_skips_pass2():
    job = make_job(url="https://blocked.example.com/jobs/1", posted_at=NOW - timedelta(days=1))
    kept, stats, records = pv.verify_jobs(
        [job], now=NOW, fetch=fetch_returning(403, ""), concurrency=1,
        browser_fallback=False,
    )
    assert stats["pass2_attempted"] == 0
    assert stats["browser_used"] is False
    assert records[job.content_hash].status == "unverifiable"
    assert records[job.content_hash].decision == "drop"
    assert records[job.content_hash].reason == "unverifiable_blocked"
    assert kept == []


def test_future_page_date_is_ignored():
    now = _dt(2026, 9, 10, tzinfo=_tz.utc)
    html = ('<html><body><script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-12-01"}</script>'
            '<button>Apply</button>' + "x" * 600 + "</body></html>")
    with_source = _mk_job_for_edge("https://example.com/c", now - _td(days=2))
    rec = _pv.verify_job(with_source, now, fetch=lambda u: (200, html, u))
    assert rec.decision == "keep" and rec.date_source == "source" and "future_date_ignored" in rec.evidence
    no_source = _mk_job_for_edge("https://example.com/d", None)
    rec2 = _pv.verify_job(no_source, now, fetch=lambda u: (200, html, u))
    assert rec2.decision == "drop" and rec2.reason == "age_unknown"
