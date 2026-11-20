"""pytest: per-job apply mode on the static job page (build_site.py + templates/job.html).

description: link mode renders an external Apply button (rel="noopener nofollow", ATS host in the label, no
  on-site form); email mode keeps the on-site form posting to /api/apply; a scraped row with no apply_mode keeps
  the legacy link. Unsafe URLs (http, javascript:, data:) never reach an href.
Run: python3 -m pytest -q tests/greenjobs_redesign/test_apply_mode_site.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
TEMPLATE = (
    REPO
    / "deliverables"
    / "greenjobs_redesign_2026-09-22"
    / "src"
    / "templates"
    / "job.html"
)
MAIN_JS = (
    REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src" / "js" / "main.js"
)
sys.path.insert(0, str(CODE))
import build_site as bs  # noqa: E402

JOB = {"id": "ie:strat:7001", "url": "https://www.greenjobs.ie/job.asp?id=7001"}


def page(j: dict) -> str:
    ctx = {
        k: "" for k in re.findall(r"{{(\w+)}}", TEMPLATE.read_text(encoding="utf-8"))
    }
    ctx.update(
        id=bs.esc(j["id"]),
        domain="greenjobs.ie",
        **bs.apply_ctx({**j, **bs.apply_of(j)}, "greenjobs.ie"),
    )
    return bs.render(TEMPLATE.read_text(encoding="utf-8"), ctx)


def apply_links(html: str) -> list[str]:
    return re.findall(r"<a [^>]*data-apply[^>]*>[^<]*", html)


def test_apply_of_modes_and_unsafe_urls():
    assert bs.apply_of(
        {"apply_mode": "link", "apply_url": "https://ats.example.com/7"}
    ) == {"apply_mode": "link", "apply_url": "https://ats.example.com/7"}
    assert bs.apply_of({"apply_mode": "email", "apply_url": None}) == {
        "apply_mode": "email",
        "apply_url": "",
    }
    assert bs.apply_of({}) == {"apply_mode": "legacy", "apply_url": ""}
    for bad in (
        "http://ats.example.com/7",
        "javascript:alert(1)",
        "data:text/html,x",
        "https://",
        "https://a b.com",
        "",
        None,
        'https://x.example.com/"onmouseover=alert(1)',
    ):
        assert bs.apply_of({"apply_mode": "link", "apply_url": bad}) == {
            "apply_mode": "email",
            "apply_url": "",
        }, bad


def test_link_mode_external_button_no_form():
    html = page(
        {
            **JOB,
            "apply_mode": "link",
            "apply_url": "https://ats.example.com/jobs/7?a=1&b=2",
        }
    )
    links = apply_links(html)
    assert len(links) == 2
    for a in links:
        assert 'href="https://ats.example.com/jobs/7?a=1&amp;b=2"' in a
        assert 'rel="noopener nofollow"' in a
        assert a.endswith("Apply on ats.example.com")
    assert "data-apply-form" not in html and "/api/apply" not in html


def test_email_mode_keeps_on_site_form():
    html = page({**JOB, "apply_mode": "email", "apply_email": "secret@client.ie"})
    links = apply_links(html)
    assert len(links) == 2 and all(
        'href="#apply-form"' in a and 'rel="noopener"' in a for a in links
    )
    form = re.search(r'<form [^>]*id="apply-form"[^>]*>.*?</form>', html, re.S).group(0)
    assert (
        'action="/api/apply"' in form
        and 'enctype="multipart/form-data"' in form
        and 'method="post"' in form
    )
    for name in (
        "job_id",
        "ts",
        "website",
        "name",
        "email",
        "phone",
        "cover_note",
        "cv",
        "consent",
    ):
        assert f'name="{name}"' in form, name
    assert 'name="job_id" value="ie:strat:7001"' in form
    assert "secret@client.ie" not in html  # the routing address never reaches the page
    js = MAIN_JS.read_text(encoding="utf-8")
    assert "data-apply-ts" in js and "form[data-apply-form]" in js


def test_legacy_row_unchanged():
    html = page(JOB)
    links = apply_links(html)
    assert len(links) == 2
    for a in links:
        assert (
            'href="https://www.greenjobs.ie/job.asp?id=7001" rel="noopener"' in a
            and a.endswith("Apply on greenjobs.ie")
        )
    assert "data-apply-form" not in html
    assert "{{" not in html


def test_jsonld_direct_apply_only_for_email_mode():
    src = (CODE / "build_site.py").read_text(encoding="utf-8")
    assert '"directApply": j.get("apply_mode") == "email"' in src
