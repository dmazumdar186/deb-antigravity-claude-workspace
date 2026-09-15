"""
description: Unit tests for normalizer/domain_filter.py — rejects PM/PO jobs
    whose product is non-digital (hardware, electronics, instrumentation,
    semiconductors, embedded/firmware, systems software, mechanical, medical
    devices, automotive/avionics hardware) while keeping software/digital
    product roles, including ones that merely mention hardware-adjacent words
    (IoT, embedded analytics/finance, digital twin) in a software context.
inputs: pytest discovery
outputs: pytest assertions
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType,
    JobSource,
    NormalizedJob,
    RemoteMode,
    canonicalize_url,
    compute_content_hash,
)
from execution.personal_workflows.job_search_v2.normalizer.domain_filter import (  # noqa: E402
    HARDWARE_TITLE_ANCHORS,
    SOFTWARE_CONTEXT_ANCHORS,
    classify_domain,
    filter_by_domain,
)
from execution.personal_workflows.job_search_v2.profile import loader as profile_loader  # noqa: E402


def _job(title: str, description: str = "", url: str = "https://example.com/job/1") -> NormalizedJob:
    canonical = canonicalize_url(url)
    return NormalizedJob(
        source=JobSource.FIXTURE,
        source_id="fixture-1",
        url=url,
        canonical_url=canonical,
        title=title,
        company="Acme",
        location="Paris",
        description_snippet=description,
        posted_at=None,
        contract_type=ContractType.CDI,
        contract_type_raw="CDI",
        remote_mode=RemoteMode.UNKNOWN,
        fetched_at=datetime.now(timezone.utc),
        content_hash=compute_content_hash(title, "Acme", canonical),
        also_seen_on=[],
    )


# ---------------------------------------------------------------------------
# Title-level hardware rejects (EN + FR)
# ---------------------------------------------------------------------------

HARDWARE_TITLES = [
    "Product Manager – Semiconductor Test Solutions",
    "Chef de Produit Instrumentation",
    "Hardware Product Manager",
    "Product Manager Embedded Systems",
    "PM Systems Software (Linux kernel)",
    "Product Owner Électronique de puissance",
    "Product Manager - Microchips",
    "Product Manager Capteurs IoT",
    "Senior PM Medical Devices",
    "Product Manager Firmware & Connectivity",
    "Chef de produit mécanique",
    "Product Manager – Chipset Design",
    "Product Manager ASIC Verification",
    "Product Manager FPGA Platforms",
    "Product Owner SoC Architecture",
    "Product Manager MEMS Sensors",
    "Product Manager Wafer Fab",
    "Product Manager – PCB Design",
    "Product Manager Device Drivers",
    "Product Manager BIOS/UEFI",
    "Product Manager Oscilloscope Line",
    "Chef de Produit Spectromètre",
    "Product Manager Photonics",
    "Product Manager Optical Components",
    "Product Manager Power Electronics",
    "Product Manager Battery Systems",
    "Chef de Produit Dispositifs Médicaux",
    "Automotive ECU Product Manager",
    "Product Manager ADAS",
    "Product Manager Avionics",
    "Product Owner Avionique",
    "Product Manager Robotics Hardware",
    "Chef de Produit Robotique",
    "Product Manager PLC/SCADA",
    "Product Manager Automatisme Industriel",
    "Product Manager HVAC Systems",
    "Product Manager CVC",
    "Product Manager Telecom Equipment",
    "Product Manager Lidar",
    "Product Manager Radar Systems",
    "Product Manager Laboratory Instruments",
    "Product Manager Machine Tools",
    "Product Manager – Produit Matériel Industriel",
    "Product Owner Silicon IP",
    "Product Manager RF Front-End",
    "Product Owner Radiofréquence",
    "Product Manager Test & Measurement",
]


@pytest.mark.parametrize("title", HARDWARE_TITLES)
def test_hardware_titles_rejected(title):
    ok, reason = classify_domain(title, "")
    assert ok is False, f"expected reject for {title!r}, got reason={reason!r}"
    assert reason.startswith("hardware_domain_title:")


# ---------------------------------------------------------------------------
# Software titles kept (including deliberate near-miss traps)
# ---------------------------------------------------------------------------

SOFTWARE_TITLES = [
    "Senior Product Manager – AI Platform",
    "Product Owner Data",
    "Chef de Produit IA",
    "Product Manager – Embedded Finance",
    "PM Embedded Analytics",
    "Product Manager IoT Cloud Platform",
    "Product Manager Chipotle Marketplace",
    "Product Manager – Digital Twin SaaS",
    "Product Manager Embedded Payments",
    "Product Manager Smart Building Software",
    "Product Manager – B2B SaaS Analytics",
    "Product Owner E-commerce Marketplace",
    "Senior Product Manager GenAI / RAG",
]


@pytest.mark.parametrize("title", SOFTWARE_TITLES)
def test_software_titles_kept(title):
    ok, reason = classify_domain(title, "")
    assert ok is True, f"expected keep for {title!r}, got reason={reason!r}"


# ---------------------------------------------------------------------------
# Word-boundary precision checks
# ---------------------------------------------------------------------------

def test_chip_does_not_match_chipotle():
    ok, reason = classify_domain("Product Manager Chipotle Marketplace", "")
    assert ok is True


def test_rf_is_standalone_token_not_substring():
    # "Surfboard" contains the letters "rf" but is not the standalone "RF" token.
    ok, reason = classify_domain("Product Manager Surfboard Marketplace", "")
    assert ok is True, reason
    ok2, reason2 = classify_domain("Product Manager RF Modules", "")
    assert ok2 is False, reason2


def test_sensor_does_not_match_sensorial():
    ok, reason = classify_domain("Product Manager Sensorial Experience Design", "")
    assert ok is True, reason


def test_sensor_matches_standalone():
    # Bare "Sensor" product → hardware. "Sensor Data Platform" (software words in
    # the same title) is rescued — see test_title_software_rescue below.
    ok, reason = classify_domain("Product Manager Sensors", "")
    assert ok is False
    assert "sensor" in reason


def test_title_software_rescue_for_ambiguous_anchor_only():
    assert classify_domain("Product Manager – Sensor Data Platform", "")[1] == "ok_title_software_product"
    # Unambiguous anchors are never rescued by software words.
    assert classify_domain("Product Manager – Firmware Platform", "")[0] is False
    assert classify_domain("Hardware Product Manager – Cloud", "")[0] is False


# ---------------------------------------------------------------------------
# Never-reject-alone words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Product Manager – System Reliability",
    "Product Manager – Data Platform",
    "Product Manager IoT",
    "Product Manager Embedded Analytics",
    "Product Manager Embedded Finance",
    "Product Manager Embedded Payments",
    "Product Manager Digital Twin",
    "Product Manager Smart Building Software",
])
def test_never_reject_alone_words_kept(title):
    ok, reason = classify_domain(title, "")
    assert ok is True, f"{title!r} should be kept, got {reason!r}"


# ---------------------------------------------------------------------------
# Description-level classification
# ---------------------------------------------------------------------------

def test_description_two_distinct_anchors_rejects():
    desc = (
        "You will own our firmware roadmap and work closely with the "
        "semiconductor fab team to ship new silicon revisions."
    )
    ok, reason = classify_domain("Senior Product Manager", desc)
    assert ok is False
    assert reason.startswith("hardware_domain_desc:")


def test_description_single_incidental_mention_kept():
    # "sensor" is description-ambiguous (excluded from description counting since
    # 2026-09-10); "hardware" is the unambiguous single mention exercised here.
    desc = "We integrate with several IoT hardware partners as part of our data pipeline."
    ok, reason = classify_domain("Senior Product Manager – Data Platform", desc)
    assert ok is True
    assert reason == "ok_incidental"


def test_description_ambiguous_terms_never_count():
    # Proton "Senior Product Manager (Inbox)" — live 2026-09-10 false positive:
    # "instrumentation" (telemetry) + "optics" (perception) are software vocabulary.
    desc = ("privacy constraints rule out the instrumentation most B2B products rely on; "
            "we prioritize impact over optics and integrate sensor data from partners.")
    ok, reason = classify_domain("Senior Product Manager (Inbox) - B2B", desc)
    assert ok is True and reason == "ok"


def test_profile_anchor_overlapping_builtin_counts_once():
    # "medical device" is both a built-in anchor and a profile skip_domain_anchor —
    # one mention must be ONE distinct hit (SaMD live false positive, 2026-09-10).
    desc = "Practical experience with SaMD (Software as a Medical Device) projects and FDA guidance."
    ok, reason = classify_domain("Senior Product Owner (SaMD & Discovery)", desc,
                                 extra_anchors=["medical device", "hardware"])
    assert ok is True, reason


def test_description_single_core_requirement_phrase_rejects():
    desc = "Ideal candidates have a background in electrical engineering."
    ok, reason = classify_domain("Senior Product Manager", desc)
    assert ok is False
    assert reason.startswith("hardware_domain_desc:")


def test_description_core_requirement_firmware_rejects():
    desc = "Strong understanding of firmware is required for this role."
    ok, reason = classify_domain("Product Manager", desc)
    assert ok is False


def test_description_mixed_software_dominant_kept():
    desc = (
        "Our SaaS platform exposes a public API on cloud infrastructure; you'll "
        "work with our machine learning team on the data platform. Occasional "
        "collaboration with hardware and PCB suppliers on IoT integrations."
    )
    ok, reason = classify_domain("Senior Product Manager – Cloud Platform", desc)
    assert ok is True
    assert reason == "ok_mixed_software_dominant"


def test_description_two_anchors_no_software_context_rejects_even_without_core_phrase():
    desc = "The team builds custom PCB layouts and qualifies semiconductor packaging."
    ok, reason = classify_domain("Product Manager", desc)
    assert ok is False
    assert reason.startswith("hardware_domain_desc:")


def test_description_zero_anchors_kept():
    ok, reason = classify_domain("Senior Product Manager", "Great team, competitive salary.")
    assert ok is True
    assert reason == "ok"


# ---------------------------------------------------------------------------
# extra_anchors (profile.json hard_filters.skip_domain_anchors)
# ---------------------------------------------------------------------------

def test_extra_anchors_reject_title():
    ok, reason = classify_domain("Product Manager Widgetronics", "", extra_anchors=["widgetronics"])
    assert ok is False
    assert reason == "hardware_domain_title:widgetronics"


def test_extra_anchors_do_not_affect_unrelated_titles():
    ok, reason = classify_domain("Product Manager – Growth", "", extra_anchors=["widgetronics"])
    assert ok is True


def test_profile_skip_domain_anchors_present_and_applied():
    anchors = profile_loader.get_skip_domain_anchors()
    assert isinstance(anchors, list)
    assert len(anchors) >= 10
    assert "semiconductor" in anchors
    # Applying them via extra_anchors should reject a title carrying one.
    ok, reason = classify_domain("Product Manager – Semiconductor Fab", "", extra_anchors=anchors)
    assert ok is False


# ---------------------------------------------------------------------------
# filter_by_domain over NormalizedJob list + stats shape
# ---------------------------------------------------------------------------

def test_filter_by_domain_stats_shape():
    jobs = [
        _job("Senior Product Manager – AI Platform", "", url="https://example.com/1"),
        _job("Hardware Product Manager", "", url="https://example.com/2"),
        _job("Chef de Produit Instrumentation", "", url="https://example.com/3"),
    ]
    kept, stats = filter_by_domain(jobs)
    assert len(kept) == 1
    assert kept[0].title == "Senior Product Manager – AI Platform"
    assert stats["total_in"] == 3
    assert stats["kept"] == 1
    assert stats["rejected"] == 2
    assert isinstance(stats["by_reason"], dict)
    assert sum(stats["by_reason"].values()) == 2
    assert isinstance(stats["rejected_sample"], list)
    assert len(stats["rejected_sample"]) == 2
    for row in stats["rejected_sample"]:
        assert "title" in row and "reason" in row


def test_filter_by_domain_empty_list():
    kept, stats = filter_by_domain([])
    assert kept == []
    assert stats["total_in"] == 0
    assert stats["kept"] == 0
    assert stats["rejected"] == 0


def test_filter_by_domain_with_extra_anchors_from_profile():
    jobs = [
        _job("Product Manager – Firmware Platform", "", url="https://example.com/a"),
        _job("Product Manager – Growth SaaS", "", url="https://example.com/b"),
    ]
    kept, stats = filter_by_domain(jobs, extra_anchors=profile_loader.get_skip_domain_anchors())
    assert len(kept) == 1
    assert kept[0].title == "Product Manager – Growth SaaS"
    assert stats["rejected"] == 1


# ---------------------------------------------------------------------------
# Sanity on anchor tables themselves
# ---------------------------------------------------------------------------

def test_hardware_title_anchors_nonempty_and_compiled():
    assert len(HARDWARE_TITLE_ANCHORS) >= 20
    for name, rx in HARDWARE_TITLE_ANCHORS.items():
        assert rx.search("")  is None or True  # just ensure no crash on empty string
        assert hasattr(rx, "search")


def test_software_context_anchors_nonempty():
    assert len(SOFTWARE_CONTEXT_ANCHORS) >= 8
    assert "saas" in SOFTWARE_CONTEXT_ANCHORS


def test_endovascular_medical_device_product_is_hardware():
    # Cron run 257 (2026-09-14): stents / implants are physical medical devices.
    assert classify_domain("Product Specialist/Chef de produit- Endovasculaire- Rungis", "")[0] is False
    assert classify_domain("Product Manager Implantable Devices", "")[0] is False
    assert classify_domain("Chef de produit Instruments chirurgicaux H/F", "")[0] is False
    # Software adjacent to healthcare stays in scope.
    assert classify_domain("Product Manager – Patient App", "")[0] is True
