"""
test_audit.py
description: Tests for execution/personal_workflows/prodcraft_medspa/audit/ (scoring, signals, detectors,
             stats, and the end-to-end --mock audit_site/scoring CLIs).
inputs: pytest fixtures from conftest.py (local_store, fixtures_root).
outputs: N/A (pytest).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.audit import (
    booking_detect,
    html_signals,
    scoring,
    stats,
    tech_detect,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_ROOT = (
    REPO_ROOT / "execution" / "personal_workflows" / "prodcraft_medspa" / "audit"
)
AUDIT_FIXTURES = AUDIT_ROOT / "fixtures"

MOCK_HOST_TO_FIXTURE = {
    "example-medspa-01.test": "site_modern_booking",
    "example-medspa-02.test": "site_wix_nobooking",
    "example-medspa-03.test": "site_wordpress_old_theme",
    "example-medspa-04.test": "site_http_only",
    "example-medspa-05.test": "site_no_viewport",
    "example-medspa-06.test": "site_squarespace_calendly",
    "example-medspa-07.test": "site_godaddy_no_analytics",
    "example-medspa-08.test": "site_broken_404",
}

# Expected {total_score, bucket, gap signals} for the 8-business mock audit_site run, computed
# by hand against the fixture HTML/PSI content and re-verified against a live --mock run.
EXPECTED_MOCK_AUDITS = {
    "example-medspa-01.test": (15, "skip", {"dated_design"}),
    "example-medspa-02.test": (
        82,
        "qualified",
        {
            "no_booking_widget",
            "not_mobile_friendly",
            "poor_performance",
            "dated_design",
            "old_builder",
            "no_analytics",
            "stale_footer",
        },
    ),
    "example-medspa-03.test": (
        58,
        "qualified",
        {"no_booking_widget", "dated_design", "poor_performance", "old_builder", "stale_footer"},
    ),
    "example-medspa-04.test": (23, "skip", {"dated_design", "no_ssl"}),
    "example-medspa-05.test": (30, "borderline", {"not_mobile_friendly", "dated_design"}),
    "example-medspa-06.test": (25, "borderline", {"dated_design", "poor_performance"}),
    "example-medspa-07.test": (27, "borderline", {"dated_design", "old_builder", "no_analytics"}),
    "example-medspa-08.test": (100, "qualified", {"no_website"}),
}


# ---------------------------------------------------------------------------
# scoring.py — exhaustive per CONTRACTS.md scoring table
# ---------------------------------------------------------------------------


class TestScoringSignalsInIsolation:
    def test_no_signals_defaults_to_no_booking_widget(self):
        # An empty signals dict means booking_widget defaults to None (not detected), which
        # IS the no_booking_widget fail condition -- it is not a "perfect site" baseline.
        result = scoring.score({})
        assert result["total"] == 22
        assert result["bucket"] == "skip"
        assert [g["signal"] for g in result["gaps"]] == ["no_booking_widget"]
        assert result["score_version"] == scoring.SCORE_VERSION

    def test_no_booking_widget_alone(self):
        result = scoring.score({"booking_widget": None})
        assert result["total"] == 22
        assert result["gaps"] == [
            {
                "signal": "no_booking_widget",
                "points": 22,
                "human_phrase": "clients can't book online without calling",
            }
        ]

    def test_booking_widget_present_no_gap(self):
        result = scoring.score({"booking_widget": "vagaro"})
        assert result["total"] == 0
        assert result["gaps"] == []

    def test_not_mobile_friendly_alone(self):
        result = scoring.score({"is_mobile_friendly": False, "booking_widget": "vagaro"})
        assert result["total"] == 15
        assert result["gaps"][0]["signal"] == "not_mobile_friendly"
        assert result["gaps"][0]["human_phrase"] == (
            "the site is hard to use on a phone, where most people look you up"
        )

    def test_mobile_friendly_true_no_gap(self):
        result = scoring.score({"is_mobile_friendly": True, "booking_widget": "vagaro"})
        assert result["total"] == 0

    def test_mobile_friendly_none_no_gap(self):
        result = scoring.score({"is_mobile_friendly": None, "booking_widget": "vagaro"})
        assert result["total"] == 0

    @pytest.mark.parametrize(
        "psi_mobile,expected_points",
        [(0, 15), (49, 15), (50, 10), (69, 10), (70, 0), (100, 0)],
    )
    def test_poor_performance_boundaries(self, psi_mobile, expected_points):
        result = scoring.score({"psi_mobile": psi_mobile, "booking_widget": "vagaro"})
        assert result["total"] == expected_points
        if expected_points:
            assert result["gaps"][0]["signal"] == "poor_performance"
            assert result["gaps"][0]["points"] == expected_points
            assert result["gaps"][0]["human_phrase"] == "pages take several seconds to load on mobile"

    def test_poor_performance_none_no_gap(self):
        result = scoring.score({"psi_mobile": None, "booking_widget": "vagaro"})
        assert result["total"] == 0

    @pytest.mark.parametrize("dated_score,expected", [(0, 0), (6, 0), (7, 15), (10, 15)])
    def test_dated_design_boundary(self, dated_score, expected):
        result = scoring.score({"vision_dated_score": dated_score, "booking_widget": "vagaro"})
        assert result["total"] == expected
        if expected:
            assert result["gaps"][0]["human_phrase"] == "the layout hides the booking step"

    def test_no_cta_above_fold_alone(self):
        result = scoring.score({"has_cta_above_fold": False, "booking_widget": "vagaro"})
        assert result["total"] == 10
        assert result["gaps"][0]["human_phrase"] == "there's no way to book from the first screen"

    def test_cta_above_fold_none_no_gap(self):
        result = scoring.score({"has_cta_above_fold": None, "booking_widget": "vagaro"})
        assert result["total"] == 0

    def test_no_ssl_alone(self):
        result = scoring.score({"has_ssl": False, "booking_widget": "vagaro"})
        assert result["total"] == 8
        assert result["gaps"][0]["human_phrase"] == "browsers flag the site as not secure"

    @pytest.mark.parametrize(
        "signals",
        [
            {"builder": "wix", "booking_widget": "vagaro"},
            {"builder": "godaddy", "booking_widget": "vagaro"},
            {"builder": "wordpress", "theme_year": 2017, "booking_widget": "vagaro"},
            {"has_jquery_legacy": True, "booking_widget": "vagaro"},
        ],
    )
    def test_old_builder_variants(self, signals):
        result = scoring.score(signals)
        assert result["total"] == 8
        assert result["gaps"][0]["signal"] == "old_builder"
        assert result["gaps"][0]["human_phrase"] == "the site builder limits online booking options"

    @pytest.mark.parametrize(
        "signals",
        [
            {"builder": "wordpress", "theme_year": 2018, "booking_widget": "vagaro"},
            {"builder": "wordpress", "theme_year": None, "booking_widget": "vagaro"},
            {"builder": "squarespace", "booking_widget": "vagaro"},
            {"has_jquery_legacy": False, "booking_widget": "vagaro"},
            {"has_jquery_legacy": None, "booking_widget": "vagaro"},
        ],
    )
    def test_old_builder_not_triggered(self, signals):
        result = scoring.score(signals)
        assert result["total"] == 0

    def test_no_analytics_alone(self):
        result = scoring.score({"has_analytics": False, "booking_widget": "vagaro"})
        assert result["total"] == 4
        assert result["gaps"][0]["human_phrase"] == "there's no way to see where bookings are lost"

    def test_stale_footer_alone_fills_year(self):
        result = scoring.score({"footer_year": 2019, "current_year": 2026, "booking_widget": "vagaro"})
        assert result["total"] == 3
        assert result["gaps"][0]["human_phrase"] == "the footer still says 2019"

    @pytest.mark.parametrize(
        "footer_year,current_year,expected_points",
        [(2024, 2026, 3), (2025, 2026, 0), (2026, 2026, 0)],
    )
    def test_stale_footer_boundary(self, footer_year, current_year, expected_points):
        result = scoring.score({"footer_year": footer_year, "current_year": current_year, "booking_widget": "vagaro"})
        assert result["total"] == expected_points

    def test_no_website_short_circuits_everything(self):
        result = scoring.score(
            {
                "has_website": False,
                "booking_widget": "vagaro",  # would otherwise zero out no_booking_widget
                "is_mobile_friendly": True,
                "psi_mobile": 99,
            }
        )
        assert result["total"] == 100
        assert result["bucket"] == "qualified"
        assert result["gaps"] == [
            {
                "signal": "no_website",
                "points": 100,
                "human_phrase": "there's no website to book from",
            }
        ]


class TestScoringBuckets:
    @pytest.mark.parametrize(
        "signals,expected_total,expected_bucket",
        [
            ({"psi_mobile": 60, "has_cta_above_fold": False, "has_analytics": False, "booking_widget": "vagaro"}, 24, "skip"),
            ({"booking_widget": None, "footer_year": 2020, "current_year": 2026}, 25, "borderline"),
            (
                {
                    "booking_widget": None,
                    "is_mobile_friendly": False,
                    "has_analytics": False,
                    "footer_year": 2020,
                    "current_year": 2026,
                },
                44,
                "borderline",
            ),
            (
                {"booking_widget": None, "is_mobile_friendly": False, "has_ssl": False},
                45,
                "qualified",
            ),
        ],
    )
    def test_bucket_boundaries(self, signals, expected_total, expected_bucket):
        result = scoring.score(signals)
        assert result["total"] == expected_total
        assert result["bucket"] == expected_bucket


class TestScoringGapOrdering:
    def test_gaps_ordered_by_points_descending(self):
        result = scoring.score(
            {
                "footer_year": 2020,
                "current_year": 2026,
                "has_analytics": False,
                "has_ssl": False,
                "booking_widget": None,
            }
        )
        points_sequence = [g["points"] for g in result["gaps"]]
        assert points_sequence == sorted(points_sequence, reverse=True)
        assert [g["signal"] for g in result["gaps"]] == [
            "no_booking_widget",
            "no_ssl",
            "no_analytics",
            "stale_footer",
        ]

    def test_every_human_phrase_is_customer_safe(self):
        banned_words = {"bad", "ugly", "terrible", "awful", "unprofessional"}
        for phrase in scoring.HUMAN_PHRASES.values():
            lowered = phrase.lower()
            assert not any(word in lowered for word in banned_words)


# ---------------------------------------------------------------------------
# html_signals.py — against the committed fixtures
# ---------------------------------------------------------------------------


class TestHtmlSignals:
    def _html(self, name: str) -> str:
        return (AUDIT_FIXTURES / f"{name}.html").read_text(encoding="utf-8")

    def test_viewport_present(self):
        assert html_signals.has_viewport_meta(self._html("site_modern_booking")) is True

    def test_viewport_absent(self):
        assert html_signals.has_viewport_meta(self._html("site_no_viewport")) is False

    def test_footer_year_html_entity_copyright(self):
        assert html_signals.footer_year(self._html("site_modern_booking")) == 2026

    def test_footer_year_word_copyright(self):
        assert html_signals.footer_year(self._html("site_wix_nobooking")) == 2018

    def test_footer_year_absent(self):
        assert html_signals.footer_year(self._html("site_broken_404")) is None

    def test_has_analytics_gtag(self):
        assert html_signals.has_analytics(self._html("site_modern_booking")) is True

    def test_has_analytics_absent(self):
        assert html_signals.has_analytics(self._html("site_wix_nobooking")) is False

    def test_has_analytics_gtm(self):
        assert html_signals.has_analytics(self._html("site_wordpress_old_theme")) is True

    def test_site_text_strips_tags_and_scripts(self):
        text = html_signals.site_text(self._html("site_modern_booking"))
        assert "<" not in text
        assert "gtag" not in text
        assert "Botox" in text
        assert len(text) <= html_signals.MAX_SITE_TEXT_CHARS

    def test_title_extracted(self):
        assert html_signals.title(self._html("site_modern_booking")) == "Glow Aesthetics Med Spa"

    def test_title_absent_returns_none(self):
        assert html_signals.title("<html><body>no title here</body></html>") is None


# ---------------------------------------------------------------------------
# booking_detect.py — one case per vendor
# ---------------------------------------------------------------------------


class TestBookingDetect:
    @pytest.mark.parametrize(
        "vendor,src",
        [
            ("vagaro", "https://www.vagaro.com/biz/book"),
            ("mindbody", "https://widgets.mindbodyonline.com/widget"),
            ("boulevard", "https://widget.blvd.co/booking/x"),
            ("zenoti", "https://webstore.zenoti.com/x"),
            ("acuity", "https://x.acuityscheduling.com/schedule.php"),
            ("calendly", "https://calendly.com/x/consult"),
            ("square", "https://squareup.com/appointments/book/x"),
            ("aesthetic_record", "https://booking.aestheticrecord.com/x"),
            ("patientnow", "https://schedule.patientnow.com/x"),
            ("moxie", "https://joinmoxie.com/book/x"),
            ("glossgenius", "https://booking.glossgenius.com/x"),
            ("booker", "https://www.booker.com/x"),
            ("schedulicity", "https://www.schedulicity.com/x"),
            ("fresha", "https://www.fresha.com/x"),
            ("setmore", "https://booking.setmore.com/x"),
            ("jane.app", "https://x.jane.app/book"),
            ("nextech", "https://patientportal.nextech.com/x"),
            ("weave", "https://getweave.com/x"),
        ],
    )
    def test_vendor_detected_from_src(self, vendor, src):
        html = f'<iframe src="{src}"></iframe>'
        assert booking_detect.booking_widget(html) == vendor

    def test_vendor_detected_from_href(self):
        html = '<a href="https://calendly.com/glow-aesthetics">Book</a>'
        assert booking_detect.booking_widget(html) == "calendly"

    def test_no_vendor_returns_none(self):
        html = "<p>Call us to book an appointment.</p>"
        assert booking_detect.booking_widget(html) is None

    def test_booking_links_collected(self):
        html = (
            '<iframe src="https://widget.blvd.co/a"></iframe>'
            '<a href="https://widget.blvd.co/a">Book</a>'
            '<a href="https://example.com/about">About</a>'
        )
        detection = booking_detect.detect_booking(html)
        assert detection.vendor == "boulevard"
        assert detection.booking_links == ["https://widget.blvd.co/a"]

    def test_empty_html_returns_none(self):
        assert booking_detect.booking_widget("") is None


# ---------------------------------------------------------------------------
# tech_detect.py
# ---------------------------------------------------------------------------


class TestTechDetect:
    def test_wix_builder(self):
        html = '<link href="https://static.wixstatic.com/x.css">'
        assert tech_detect.detect_builder(html) == "wix"

    def test_squarespace_builder(self):
        html = '<script src="https://static1.squarespace.com/x.js"></script>'
        assert tech_detect.detect_builder(html) == "squarespace"

    def test_godaddy_builder(self):
        html = '<img src="https://img1.wsimg.com/x.jpg">'
        assert tech_detect.detect_builder(html) == "godaddy"

    def test_webflow_builder(self):
        html = '<script src="https://assets-global.website-files.com/x.js"></script>'
        assert tech_detect.detect_builder(html) == "webflow"

    def test_wordpress_builder(self):
        html = '<link href="/wp-content/themes/foo/style.css">'
        assert tech_detect.detect_builder(html) == "wordpress"

    def test_shopify_builder(self):
        html = '<script src="https://cdn.shopify.com/s/x.js"></script>'
        assert tech_detect.detect_builder(html) == "shopify"

    def test_duda_builder(self):
        html = '<img src="https://irp.cdn-website.com/x.jpg">'
        assert tech_detect.detect_builder(html) == "duda"

    def test_weebly_builder(self):
        html = '<script src="https://cdn2.editmysite.com/x.js"></script>'
        assert tech_detect.detect_builder(html) == "weebly"

    def test_no_builder_detected(self):
        assert tech_detect.detect_builder("<p>plain html</p>") is None

    def test_wordpress_theme_slug(self):
        html = '<link href="/wp-content/themes/med-spa-classic/style.css">'
        assert tech_detect.detect_wordpress_theme(html) == "med-spa-classic"

    def test_theme_slug_none_when_not_wordpress(self):
        assert tech_detect.detect_wordpress_theme("<p>no theme here</p>") is None

    @pytest.mark.parametrize(
        "src,expected",
        [
            ("https://code.jquery.com/jquery-1.12.4.min.js", True),
            ("https://code.jquery.com/jquery-2.2.4.min.js", True),
            ("https://code.jquery.com/jquery-3.6.0.min.js", False),
            ("https://code.jquery.com/jquery-3.7.1.js", False),
        ],
    )
    def test_jquery_legacy_versions(self, src, expected):
        html = f'<script src="{src}"></script>'
        assert tech_detect.detect_jquery_legacy(html) is expected

    def test_jquery_legacy_none_when_absent(self):
        assert tech_detect.detect_jquery_legacy("<p>no jquery</p>") is None

    def test_detect_tech_wordpress_full(self):
        html = (
            '<link href="/wp-content/themes/med-spa-classic/style.css">'
            '<script src="https://code.jquery.com/jquery-1.12.4.min.js"></script>'
        )
        result = tech_detect.detect_tech(html, "https://example.test/", fetch_theme=False)
        assert result.builder == "wordpress"
        assert result.theme == "med-spa-classic"
        assert result.theme_year is None
        assert result.has_jquery_legacy is True

    def test_detect_tech_no_network_when_fetch_theme_false(self):
        # fetch_theme=False must never touch the network even for a wordpress+theme match.
        html = '<link href="/wp-content/themes/x/style.css">'
        result = tech_detect.detect_tech(html, "https://nonexistent.invalid/", fetch_theme=False)
        assert result.theme_year is None


# ---------------------------------------------------------------------------
# stats.py — wilson()
# ---------------------------------------------------------------------------


class TestWilson:
    def test_zero_trials(self):
        assert stats.wilson(0, 0) == (0.0, 0.0, 0.0)

    def test_known_50_percent_n_100(self):
        p_hat, low, high = stats.wilson(50, 100)
        assert p_hat == pytest.approx(50.0)
        # Wilson 95% CI for 50/100 is approximately [40.2, 59.8].
        assert low == pytest.approx(40.2, abs=0.5)
        assert high == pytest.approx(59.8, abs=0.5)

    def test_all_success(self):
        p_hat, low, high = stats.wilson(10, 10)
        assert p_hat == 100.0
        assert high == pytest.approx(100.0, abs=0.01)
        assert low < 100.0

    def test_all_failure(self):
        p_hat, low, high = stats.wilson(0, 10)
        assert p_hat == 0.0
        assert low == pytest.approx(0.0, abs=0.01)
        assert high > 0.0

    def test_bounds_stay_in_0_100(self):
        for k, n in [(1, 3), (2, 7), (99, 100)]:
            _, low, high = stats.wilson(k, n)
            assert 0.0 <= low <= high <= 100.0


# ---------------------------------------------------------------------------
# End-to-end --mock CLI runs (audit_site.py, scoring.py --recompute)
# ---------------------------------------------------------------------------


def _run_module(module: str, args: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, f"{module} failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    last_line = [line for line in proc.stdout.strip().splitlines() if line.strip()][-1]
    return json.loads(last_line)


def _seed_discovery_like_businesses(store_root: Path) -> None:
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    st = LocalStore(root=store_root)
    for i, host in enumerate(sorted(MOCK_HOST_TO_FIXTURE), start=1):
        st.upsert_business(
            {
                "place_id": f"place-{i:02d}",
                "name": f"Test Med Spa {i:02d}",
                "slug": f"test-med-spa-{i:02d}",
                "metro": "chicago_north_shore",
                "website_url": f"https://{host}/",
                "is_chain": False,
            }
        )


class TestAuditSiteMockCLI:
    def test_mock_run_matches_expected_totals(self, tmp_path):
        store_root = tmp_path / "store"
        _seed_discovery_like_businesses(store_root)

        stat_line = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            [
                "--metro",
                "chicago_north_shore",
                "--mock",
                "--skip-screenshots",
                "--store",
                "local",
                "--store-root",
                str(store_root),
            ],
        )
        assert stat_line["script"] == "audit_site"
        assert stat_line["in"] == 8
        assert stat_line["audited"] == 8
        assert stat_line["errors"] == 0
        assert stat_line["no_website"] == 1
        assert stat_line["buckets"] == {"qualified": 3, "borderline": 3, "skip": 2}

        from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

        st = LocalStore(root=store_root)
        businesses_by_host = {}
        for b in st.find_businesses(metro="chicago_north_shore"):
            host = b["website_url"].split("//")[1].rstrip("/")
            businesses_by_host[host] = b

        for host, (expected_total, expected_bucket, expected_signals) in EXPECTED_MOCK_AUDITS.items():
            business = businesses_by_host[host]
            audit = st.latest_audit(business["id"])
            assert audit is not None, host
            assert audit["total_score"] == expected_total, host
            assert audit["bucket"] == expected_bucket, host
            actual_signals = {g["signal"] for g in audit["gaps"]}
            assert actual_signals == expected_signals, host

    def test_idempotent_second_run_audits_zero(self, tmp_path):
        store_root = tmp_path / "store"
        _seed_discovery_like_businesses(store_root)

        first = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--store", "local",
             "--store-root", str(store_root)],
        )
        assert first["audited"] == 8

        second = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--store", "local",
             "--store-root", str(store_root)],
        )
        assert second["audited"] == 0
        assert second["buckets"] == {"qualified": 0, "borderline": 0, "skip": 0}

    def test_force_reaudits_everything(self, tmp_path):
        store_root = tmp_path / "store"
        _seed_discovery_like_businesses(store_root)

        _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--store", "local",
             "--store-root", str(store_root)],
        )
        forced = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--force", "--store", "local",
             "--store-root", str(store_root)],
        )
        assert forced["audited"] == 8

    def test_recompute_is_noop_after_run(self, tmp_path):
        store_root = tmp_path / "store"
        _seed_discovery_like_businesses(store_root)

        _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--store", "local",
             "--store-root", str(store_root)],
        )
        recompute_stat = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.scoring",
            ["--recompute", "--metro", "chicago_north_shore", "--store", "local",
             "--store-root", str(store_root)],
        )
        assert recompute_stat["checked"] == 8
        assert recompute_stat["diffs"] == 0

    def test_chain_and_dropped_businesses_are_excluded(self, tmp_path):
        from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

        store_root = tmp_path / "store"
        st = LocalStore(root=store_root)
        st.upsert_business(
            {
                "place_id": "chain-1",
                "name": "Chain Med Spa",
                "slug": "chain-med-spa",
                "metro": "chicago_north_shore",
                "website_url": "https://example-medspa-01.test/",
                "is_chain": True,
            }
        )
        st.upsert_business(
            {
                "place_id": "dropped-1",
                "name": "Dropped Med Spa",
                "slug": "dropped-med-spa",
                "metro": "chicago_north_shore",
                "website_url": "https://example-medspa-02.test/",
                "is_chain": False,
                "drop_reason": "closed",
            }
        )

        stat_line = _run_module(
            "execution.personal_workflows.prodcraft_medspa.audit.audit_site",
            ["--metro", "chicago_north_shore", "--mock", "--skip-screenshots", "--store", "local",
             "--store-root", str(store_root)],
        )
        assert stat_line["in"] == 0
        assert stat_line["audited"] == 0


class TestSampleAuditMockCLI:
    def test_sample_audit_inserts_metro_stats_with_wilson_ci(self, tmp_path):
        from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

        store_root = tmp_path / "store"
        st = LocalStore(root=store_root)
        for i in range(1, 21):
            host = f"example-medspa-{i:02d}.test"
            st.upsert_business(
                {
                    "place_id": f"place-{i:02d}",
                    "name": f"Sample Med Spa {i:02d}",
                    "slug": f"sample-med-spa-{i:02d}",
                    "metro": "chicago_north_shore",
                    "website_url": f"https://{host}/",
                    "is_chain": False,
                }
            )

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "execution.personal_workflows.prodcraft_medspa.audit.sample_audit",
                "--metro",
                "chicago_north_shore",
                "--n",
                "10",
                "--seed",
                "42",
                "--mock",
                "--skip-screenshots",
                "--store",
                "local",
                "--store-root",
                str(store_root),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
        stat_line = json.loads(lines[0])
        metro_stats_row = json.loads(lines[1])

        assert stat_line["sampled"] == 10
        assert metro_stats_row["sampled"] == 10
        assert metro_stats_row["ci_low"] <= metro_stats_row["pct_qualified"] <= metro_stats_row["ci_high"]
        assert metro_stats_row["score_version"] == scoring.SCORE_VERSION

        saved = st._read("metro_stats")  # noqa: SLF001 — verify the row actually persisted
        assert len(saved) == 1
        assert saved[0]["metro"] == "chicago_north_shore"

    def test_seeded_sample_is_deterministic(self, tmp_path):
        from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

        def _seed(root: Path) -> None:
            st = LocalStore(root=root)
            for i in range(1, 21):
                host = f"example-medspa-{i:02d}.test"
                st.upsert_business(
                    {
                        "place_id": f"place-{i:02d}",
                        "name": f"Sample Med Spa {i:02d}",
                        "slug": f"sample-med-spa-{i:02d}",
                        "metro": "chicago_north_shore",
                        "website_url": f"https://{host}/",
                        "is_chain": False,
                    }
                )

        results = []
        for run in (1, 2):
            store_root = tmp_path / f"store{run}"
            _seed(store_root)
            stat = _run_module(
                "execution.personal_workflows.prodcraft_medspa.audit.sample_audit",
                [
                    "--metro", "chicago_north_shore", "--n", "10", "--seed", "42", "--mock",
                    "--skip-screenshots", "--store", "local", "--store-root", str(store_root),
                ],
            )
            results.append(stat["qualified"])

        assert results[0] == results[1]


# ---------------------------------------------------------------------------
# Vision golden set — files must exist; live check only when ANTHROPIC_API_KEY is set.
# ---------------------------------------------------------------------------


class TestVisionGolden:
    GOLDEN_DIR = AUDIT_FIXTURES / "vision_golden"

    def test_golden_files_exist(self):
        golden = json.loads((self.GOLDEN_DIR / "golden.json").read_text(encoding="utf-8"))
        assert len(golden) == 6
        for name, spec in golden.items():
            image_path = self.GOLDEN_DIR / f"{name}.png"
            assert image_path.exists(), name
            assert spec["band"] in ("modern", "dated")
            assert 0 <= spec["min_score"] <= spec["max_score"] <= 10

    def test_bands_are_sane_and_non_overlapping(self):
        golden = json.loads((self.GOLDEN_DIR / "golden.json").read_text(encoding="utf-8"))
        modern_maxes = [s["max_score"] for s in golden.values() if s["band"] == "modern"]
        dated_mins = [s["min_score"] for s in golden.values() if s["band"] == "dated"]
        assert max(modern_maxes) < min(dated_mins)

    @pytest.mark.skipif(
        not __import__("os").environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set — skipping live vision check",
    )
    def test_live_vision_scores_land_in_expected_bands(self):
        from execution.personal_workflows.prodcraft_medspa.audit import vision

        golden = json.loads((self.GOLDEN_DIR / "golden.json").read_text(encoding="utf-8"))
        for name, spec in golden.items():
            png_bytes = (self.GOLDEN_DIR / f"{name}.png").read_bytes()
            result = vision.run_vision_audit(
                "Golden Test Business", "https://golden-test.example/", png_bytes, None, mock=False
            )
            assert spec["min_score"] <= result["vision_dated_score"] <= spec["max_score"], name
