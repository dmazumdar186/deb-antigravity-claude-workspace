"""pytest: GA4 + consent + Search Console + sitemaps (build_site.py --analytics).

Staging build: no tag/meta/script. Production build: tag meta per edition, verification meta when a token is set,
robots.txt lists both sitemaps, no GA request before consent (static check of analytics.js), events carry no
personal fields, banner choice persists (static check of popups.js).
Run: python3 -m pytest -q tests/greenjobs_redesign/test_analytics.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
sys.path.insert(0, str(CODE))
import build_site as bs  # noqa: E402
import validate_site  # noqa: E402



def _build(tmp: Path, mode: str, token: str = "") -> Path:
    src = tmp / f"src_{mode}"
    shutil.copytree(SRC, src)
    cfg = json.loads((src / "analytics.json").read_text(encoding="utf-8"))
    cfg["editions"]["ie"]["gsc_token"] = token
    (src / "analytics.json").write_text(json.dumps(cfg), encoding="utf-8")
    out = REPO / ".tmp" / f"ga_test_{mode}"
    rc = bs.build(
        src,
        out,
        editions=["ie", "uk"],
        fixture=SRC / "data" / "_fixture.json",
        analytics=mode,
    )
    assert rc == 0
    return out


def test_staging_has_no_tag(tmp_path):
    out = _build(tmp_path, "off")
    for p in out.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        assert (
            "gj-ga4" not in t
            and "googletagmanager" not in t
            and "google-site-verification" not in t
            and "js/analytics.js" not in t
        )
    assert not (out / "js" / "analytics.js").exists()
    assert "Sitemap:" not in (out / "robots.txt").read_text(encoding="utf-8")
    assert (out / "sitemap.xml").exists() and (out / "sitemap-jobs.xml").exists()


def test_production_tag_and_verification(tmp_path):
    out = _build(tmp_path, "production", token="abc123_-X")
    ie = (out / "ie" / "index.html").read_text(encoding="utf-8")
    uk = (out / "uk" / "index.html").read_text(encoding="utf-8")
    assert 'name="gj-ga4" content="G-ZQPJGM484J"' in ie and "G-ZFW03XQE2N" not in ie
    assert 'name="gj-ga4" content="G-ZFW03XQE2N"' in uk and "G-ZQPJGM484J" not in uk
    assert 'name="google-site-verification" content="abc123_-X"' in ie
    assert "google-site-verification" not in uk  # empty token -> no meta
    assert (
        "data-cookie-ga" in ie
        and "data-cookie-reject" in ie
        and "js/analytics.js" in ie
    )
    r = (out / "robots.txt").read_text(encoding="utf-8")
    for h in ("greenjobs.ie", "greenjobs.co.uk"):
        assert (
            f"Sitemap: https://www.{h}/sitemap.xml" in r
            and f"Sitemap: https://www.{h}/sitemap-jobs.xml" in r
        )
    assert (out / "js" / "analytics.js").exists()


def test_no_ga_request_before_consent():
    js = (SRC / "js" / "analytics.js").read_text(encoding="utf-8")
    assert "analytics_storage: 'denied'" in js and "ad_user_data: 'denied'" in js
    assert js.count("googletagmanager.com/gtag/js") == 1  # only inside load()
    assert re.search(
        r"function load\(\) \{\s*if \(loaded \|\| !granted\(\)\) return;", js
    )
    assert "hosts.indexOf(location.hostname) < 0" in js  # production hosts only
    assert "googletagmanager" not in (SRC / "templates" / "_shell.html").read_text(
        encoding="utf-8"
    )


def test_events_carry_no_personal_fields():
    js = (SRC / "js" / "analytics.js").read_text(encoding="utf-8")
    allow = set(re.findall(r"(\w+): 1", re.search(r"ALLOW = \{(.*?)\}", js).group(1)))
    assert allow and not allow & {"email", "name", "phone", "cover_note", "employer"}
    html = (
        "".join(
            p.read_text(encoding="utf-8") for p in (SRC / "templates").glob("*.html")
        )
        + bs.APPLY_FORM
    )
    for attr in re.findall(r"data-ev-([a-z-]+)=", html):
        assert attr not in {"email", "name", "phone"}
    assert 'data-ev="apply_submit"' in bs.APPLY_FORM
    assert (
        bs.apply_ctx(
            {"id": "x", "url": "https://a.b/c", "apply_mode": "email"}, "greenjobs.ie"
        )["apply_ev"]
        == ""
    )
    assert (
        "apply_click"
        in bs.apply_ctx(
            {"id": "x", "apply_url": "https://a.b/c", "apply_mode": "link"},
            "greenjobs.ie",
        )["apply_ev"]
    )


def test_banner_choice_persists():
    js = (SRC / "js" / "popups.js").read_text(encoding="utf-8")
    assert (
        "store('gj-consent'" in js and "if (!consent ||" in js
    )  # saved choice suppresses the banner
    assert "data-cookie-reject" in js
    shell = (SRC / "templates" / "_shell.html").read_text(encoding="utf-8")
    assert (
        "<button" in shell.split("data-cookie")[1][:900]
    )  # real buttons: keyboard accessible
