"""Static boards: _redirects, _headers and the indexing policy (integration gap e, 2026-11-20).

description: build_site.py writes Cloudflare Pages `_redirects` (one board's legacy URLs, from the ops Bulk
    Redirects list) and `_headers` (CSP with the inline-script hashes, HSTS, nosniff, Referrer-Policy,
    frame-ancestors, and X-Robots-Tag noindex unless the build is the indexed production one). Unit tests on
    the helpers plus one check that every rule the IE board would ship lands on a path the static tree or the
    platform Worker serves.
inputs: none (reads ops/generated/bulk_redirects.json read-only)
outputs: pytest result
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(
    0, str(REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
)
import build_site as b  # noqa: E402
import validate_site  # noqa: E402

BULK = json.loads(b.OPS_BULK_REDIRECTS.read_text(encoding="utf-8"))


def item(src: str, tgt: str, subpath: bool = False) -> dict:
    return {
        "redirect": {
            "source_url": src,
            "target_url": tgt,
            "status_code": 301,
            "subpath_matching": subpath,
        }
    }


def test_rules_prefix_the_edition_and_skip_what_pages_cannot_match() -> None:
    bulk = {
        "items": [
            item("greenjobs.ie/", "https://www.greenjobs.ie/"),
            item(
                "greenjobs.ie/browse-jobs/dublin/",
                "https://www.greenjobs.ie/jobs/?region=dublin",
            ),
            item("greenjobs.ie/x/", "https://www.greenjobs.ie/ie/already/"),
            item(
                "greenjobs.ie/jobview.asp?v=1", "https://www.greenjobs.ie/jobs/1/"
            ),  # query: Worker table
            item("greenjobs.co.uk/", "https://www.greenjobs.co.uk/"),  # other board
            item(
                "windjobsuk.com/", "https://www.greenjobs.co.uk/sectors/wind/", True
            ),  # sector domain
            item("greenjobs.ie/evil/", "javascript:alert(1)"),
        ]
    }
    assert b.pages_redirect_rules(bulk, "ie") == [
        ("/", "/ie/"),
        ("/browse-jobs/dublin/", "/ie/jobs/?region=dublin"),
        ("/x/", "/ie/already/"),
    ]
    assert b.pages_redirect_rules(bulk, "uk") == [("/", "/uk/")]


def test_job_rules_fall_back_to_the_list_when_the_board_does_not_serve_the_job() -> (
    None
):
    bulk = {
        "items": [
            item("greenjobs.ie/jobs/111/a.asp", "https://www.greenjobs.ie/jobs/111/"),
            item("greenjobs.ie/jobs/222/b.asp", "https://www.greenjobs.ie/jobs/222/"),
        ]
    }
    assert b.pages_redirect_rules(bulk, "ie", {"111"}) == [
        ("/jobs/111/a.asp", "/ie/jobs/111/"),
        ("/jobs/222/b.asp", "/ie/jobs/"),
    ]
    assert b.pages_redirect_rules(bulk, "ie") == [
        ("/jobs/111/a.asp", "/ie/jobs/111/"),
        ("/jobs/222/b.asp", "/ie/jobs/222/"),
    ]


def test_rules_have_a_floor_and_a_ceiling() -> None:
    with pytest.raises(ValueError):
        b.pages_redirect_rules({"items": []}, "ie")
    many = {
        "items": [
            item(f"greenjobs.ie/p{i}/", "https://www.greenjobs.ie/")
            for i in range(b.PAGES_MAX_REDIRECTS + 1)
        ]
    }
    with pytest.raises(ValueError):
        b.pages_redirect_rules(many, "ie")
    with pytest.raises(ValueError):
        b.pages_redirect_rules(BULK, "fr")


@pytest.mark.parametrize("site", ["ie", "uk"])
def test_real_ops_list_gives_well_formed_rules(site: str) -> None:
    rules = b.pages_redirect_rules(BULK, site)
    assert 50 <= len(rules) <= b.PAGES_MAX_REDIRECTS
    for old, new in rules:
        assert old.startswith("/") and " " not in old and "?" not in old
        assert new.startswith(f"/{site}/") or new == f"/{site}"
        assert old != new


def test_ie_rules_land_on_served_paths() -> None:
    """Every IE target is either a static page the build writes (validate_site + common.Routes' static set)
    or a Worker board path (/ie/jobs/, /ie/jobs/<id>/, /ie/sectors/<slug>/)."""
    sys.path.insert(
        0,
        str(REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign" / "ops"),
    )
    import common as C  # noqa: PLC0415

    static = {"/ie" + p for p in C.static_routes("ie")} | {"/ie/"}
    for _old, new in b.pages_redirect_rules(BULK, "ie"):
        path = new.split("?", 1)[0]
        assert path in static or re.fullmatch(
            r"/ie/(jobs/([0-9]+/)?|sectors/[a-z0-9-]+/)", path
        ), new


def test_headers_carry_every_security_header_and_hash_inline_scripts(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.html").write_text(
        '<html><head><script>var x=1;</script><script src="js/m.js"></script>'
        '<script type="application/ld+json">{"@type":"JobPosting"}</script></head></html>',
        encoding="utf-8",
    )
    h = b.pages_headers(tmp_path, robots_index=False)
    assert h.startswith("/*\n")
    for need in (
        "Content-Security-Policy:",
        "frame-ancestors 'none'",
        "Strict-Transport-Security: max-age=31536000",
        "X-Content-Type-Options: nosniff",
        "Referrer-Policy:",
        "X-Frame-Options: DENY",
        "X-Robots-Tag: noindex",
    ):
        assert need in h, need
    csp = re.search(r"Content-Security-Policy: (.*)", h).group(1)
    assert (
        csp.count("'sha256-") == 1
        and "'unsafe-inline'" not in csp.split("style-src")[0]
    )
    assert "X-Robots-Tag" not in b.pages_headers(tmp_path, robots_index=True)


def test_robots_policy_staging_noindex_production_index(tmp_path: Path) -> None:
    page = tmp_path / "ie" / "index.html"
    page.parent.mkdir()
    page.write_text('<meta name="robots" content="noindex,nofollow">', encoding="utf-8")
    (tmp_path / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    b.apply_robots_policy(tmp_path, False, "https://x.pages.dev/")
    assert "noindex" in page.read_text(encoding="utf-8") and "Disallow: /" in (
        tmp_path / "robots.txt"
    ).read_text(encoding="utf-8")
    b.apply_robots_policy(tmp_path, True, "https://www.greenjobs.ie/")
    assert 'content="index,follow"' in page.read_text(encoding="utf-8")
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert (
        "Allow: /" in robots
        and "Sitemap: https://www.greenjobs.ie/sitemap.xml" in robots
        and "Disallow" not in robots
    )


def test_shell_template_has_no_dead_strategies_signup_link() -> None:
    src = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src" / "templates"
    for name in ("_shell.html", "home.html"):
        assert "newsletter-signup.asp" not in (src / name).read_text(
            encoding="utf-8"
        ), name
    assert 'data-live-api="{{live_api}}"' in (src / "_shell.html").read_text(
        encoding="utf-8"
    )


def test_validator_knows_the_indexed_build() -> None:
    src = Path(validate_site.__file__).read_text(encoding="utf-8")
    assert (
        "indexed build (production) but no <meta name=robots content=index,follow>"
        in src
    )
