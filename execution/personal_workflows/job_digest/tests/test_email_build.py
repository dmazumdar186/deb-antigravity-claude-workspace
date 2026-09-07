"""
description: Offline unit tests for notifier/email.py's build_digest().
inputs: synthetic NormalizedJob/RankedJob pairs and a minimal Profile — no network.
outputs: pytest assertions on subject format, HTML-escaping of untrusted job
    text, and tier grouping/ordering.
"""
from __future__ import annotations

from execution.personal_workflows.job_digest.contracts import (
    ContractType,
    JobSource,
    JobTier,
    NormalizedJob,
    RankedJob,
    RemoteMode,
    compute_content_hash,
)
from execution.personal_workflows.job_digest.notifier.email import build_digest
from execution.personal_workflows.job_digest.profile_schema import Profile


def _profile(**overrides) -> Profile:
    raw = {
        "version": 1,
        "candidate": {"name": "Jordan Example", "email": "jordan.example@example.com"},
        "roles": [{"title": "Sales Manager", "synonyms": [], "seniority": "any"}],
        "locations": {"countries": ["FR", "IN"], "cities": [], "remote_ok": True},
        "screening": {
            "summary": "A" * 50,
            "skills": [],
        },
    }
    raw.update(overrides)
    return Profile.model_validate(raw)


def _job(title: str, company: str = "Acme", url: str = "https://example.com/job/1") -> NormalizedJob:
    canonical = url
    return NormalizedJob(
        source=JobSource.FIXTURE,
        source_id="1",
        url=url,
        canonical_url=canonical,
        title=title,
        company=company,
        location="Paris",
        description_snippet="",
        posted_at=None,
        contract_type=ContractType.CDI,
        remote_mode=RemoteMode.REMOTE,
        fetched_at="2026-09-06T00:00:00Z",
        content_hash=compute_content_hash(title, company, canonical),
    )


def _ranked(job: NormalizedJob, score: float, tier: JobTier, reasoning: str = "good fit") -> RankedJob:
    return RankedJob(
        content_hash=job.content_hash,
        score=score,
        tier=tier,
        reasoning=reasoning,
        rubric_version="v1",
        ranker_model="heuristic",
    )


def test_subject_format():
    profile = _profile()
    job = _job("Sales Manager", "Acme")
    ranked = _ranked(job, 0.9, JobTier.A)
    subject, _, _ = build_digest([(job, ranked)], profile, {}, None)

    assert subject.startswith("Job digest · 1 new · Sales Manager · FR, IN · ")
    # date suffix is today's date in ISO form
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2}$", subject)


def test_subject_count_matches_pairs():
    profile = _profile()
    jobs = [_job(f"Sales Manager {i}", "Acme", f"https://example.com/job/{i}") for i in range(3)]
    pairs = [(j, _ranked(j, 0.6, JobTier.B)) for j in jobs]
    subject, _, _ = build_digest(pairs, profile, {}, None)
    assert subject.startswith("Job digest · 3 new ·")


def test_html_escapes_untrusted_job_title():
    profile = _profile()
    malicious_title = "<script>alert('xss')</script>Sales Manager"
    job = _job(malicious_title, "<b>EvilCo</b>")
    ranked = _ranked(job, 0.8, JobTier.A, reasoning="<img src=x onerror=alert(1)>")
    _, plain_text, html = build_digest([(job, ranked)], profile, {}, None)

    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>EvilCo</b>" not in html
    assert "&lt;b&gt;EvilCo&lt;/b&gt;" in html
    assert "<img src=x onerror=alert(1)>" not in html
    # Plain text is not escaped — it's not rendered as markup.
    assert malicious_title in plain_text


def test_tier_grouping_and_order():
    profile = _profile()
    job_a = _job("Sales Manager A", "CoA", "https://example.com/a")
    job_b = _job("Sales Manager B", "CoB", "https://example.com/b")
    job_c = _job("Sales Manager C", "CoC", "https://example.com/c")
    pairs = [
        (job_c, _ranked(job_c, 0.3, JobTier.C)),
        (job_a, _ranked(job_a, 0.9, JobTier.A)),
        (job_b, _ranked(job_b, 0.6, JobTier.B)),
    ]
    _, plain_text, html = build_digest(pairs, profile, {}, None)

    # Tier A section must appear before Tier B, which appears before Tier C.
    idx_a = html.index("Tier A")
    idx_b = html.index("Tier B")
    idx_c = html.index("Tier C")
    assert idx_a < idx_b < idx_c

    idx_a_t = plain_text.index("Tier A")
    idx_b_t = plain_text.index("Tier B")
    idx_c_t = plain_text.index("Tier C")
    assert idx_a_t < idx_b_t < idx_c_t


def test_skip_tier_excluded_from_output():
    profile = _profile()
    job = _job("Sales Manager", "Acme")
    ranked = _ranked(job, 0.1, JobTier.SKIP)
    subject, plain_text, html = build_digest([(job, ranked)], profile, {}, None)
    # SKIP-tier pairs should never reach build_digest in practice, but if one
    # slips through it must not be counted or rendered as a row.
    assert subject.startswith("Job digest · 1 new ·")  # count reflects input length
    assert "Acme" not in plain_text
    assert "No jobs matched your profile" in plain_text
    assert "Acme" not in html


def test_sheet_url_rendered_when_present():
    profile = _profile()
    job = _job("Sales Manager", "Acme")
    ranked = _ranked(job, 0.9, JobTier.A)
    _, plain_text, html = build_digest([(job, ranked)], profile, {}, "https://sheet.example.com/x")
    assert "https://sheet.example.com/x" in plain_text
    assert "https://sheet.example.com/x" in html


def test_no_sheet_url():
    profile = _profile()
    job = _job("Sales Manager", "Acme")
    ranked = _ranked(job, 0.9, JobTier.A)
    _, plain_text, _ = build_digest([(job, ranked)], profile, {}, None)
    assert "not configured" in plain_text
