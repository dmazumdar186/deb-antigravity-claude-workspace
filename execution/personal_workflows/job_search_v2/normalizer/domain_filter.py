"""
description: Domain filter for NormalizedJobs. Rejects Product Manager / Product
    Owner jobs whose PRODUCT is not digital/software — hardware, electronics,
    instrumentation, semiconductors/microchips, embedded/firmware, systems
    software, mechanical, medical devices, automotive/avionics hardware, etc.
    The operator's CV is software-only (B2B SaaS, retail tech, GenAI/LLM/RAG
    products); a title_filter/language_filter pass alone lets these through
    because they legitimately say "Product Manager" — the mismatch is on the
    product domain, not the role family.
inputs:
    - list[NormalizedJob]
outputs:
    - (kept, stats) where stats = {total_in, kept, rejected, by_reason, rejected_sample}

Why this exists (operator complaint, 2026-09-10): the sheet contained rows like
"Product Manager - Semiconductor Test Solutions" and "Chef de Produit
Instrumentation" — real PM titles, wrong industry. title_filter only screens
role family (PM vs PO vs PjM); this module screens the PRODUCT DOMAIN and must
run in addition to it, not instead of it.

Design: title-level anchors are a strict word-boundary regex match and reject
outright (a hardware word in the TITLE is a strong, low-noise signal).
Description-level anchors are softer: a single incidental mention ("we
integrate with IoT sensor partners") must not sink an otherwise-software role,
so single hits only reject when they're a "core requirement" phrase (a
regex indicating the hardware domain is a job requirement, not a passing
reference). Two or more DISTINCT anchors in the description is treated as
strong evidence regardless of phrasing, UNLESS the description is clearly
software-dominant (>=3 distinct software-context anchors and no core-requirement
phrase), in which case it is rescued as a mixed/software-dominant role.
"""

from __future__ import annotations

import logging
import re
import sys
import unicodedata
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

logger = logging.getLogger("normalizer.domain_filter")


def _strip_accents(s: str) -> str:
    """Fold accented chars to ASCII so 'matériel' and 'materiel' both match,
    and so \\b regex word boundaries behave consistently on FR text."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# HARDWARE / PHYSICAL-PRODUCT ANCHORS
#
# Each entry: (name, compiled regex). Regexes are matched against the
# accent-stripped, lowercased text. \b boundaries throughout so "chip" cannot
# match "chipotle", "sensor" cannot match "sensorial", "RF" is a standalone
# token, etc. EN + FR.
# ---------------------------------------------------------------------------
_HW_PATTERNS: list[tuple[str, str]] = [
    ("hardware", r"\bhardware\b"),
    ("materiel_produit", r"\bproduit\s+materiel\b"),
    ("semiconductor", r"\bsemi-?conducteurs?\b|\bsemiconductors?\b"),
    ("microchip", r"\bmicrochips?\b|\bchipsets?\b|\bchips?\b|\bpuces?\s+electroniques?\b"),
    ("silicon", r"\bsilicon\b"),
    ("asic", r"\basics?\b"),
    ("fpga", r"\bfpgas?\b"),
    ("soc", r"\bsocs?\b"),
    ("mems", r"\bmems\b"),
    ("wafer", r"\bwafers?\b"),
    ("firmware", r"\bfirmware\b"),
    ("embedded", r"\bembedded\s+(systems?|software|linux|devices?|c\+\+|c)\b|\bsystemes?\s+embarques?\b|\blogiciel\s+embarque\b|\bembarque(e|s|es)?\b"),
    ("pcb", r"\bpcbs?\b|\bprinted\s+circuits?\b"),
    ("systems_software", r"\bsystems?\s+software\b"),
    ("kernel", r"\bkernel\b"),
    ("device_driver", r"\bdevice\s+drivers?\b"),
    ("bios_uefi", r"\bbios\b|\buefi\b"),
    ("instrumentation", r"\binstrumentation\b"),
    ("test_and_measurement", r"\btest\s*&\s*measurement\b|\btest\s+and\s+measurement\b"),
    ("oscilloscope", r"\boscilloscopes?\b"),
    ("spectrometer", r"\bspectrometers?\b|\bspectrometres?\b"),
    ("electronics", r"\belectronics?\b|\belectroniques?\b"),
    ("electrical", r"\belectrical\b|\bgenie\s+electrique\b"),
    ("rf", r"\brf\b|\bradio\s*frequency\b|\bradiofrequences?\b"),
    ("photonics", r"\bphotonics?\b|\bphotoniques?\b"),
    ("optics", r"\boptical\s+components?\b|\boptics?\b(?!\s+fiber)"),
    ("sensor", r"\bsensors?\b|\bcapteurs?\b"),
    ("power_electronics", r"\bpower\s+electronics\b|\belectronique\s+de\s+puissance\b"),
    ("battery", r"\bbatter(y|ies)\b|\bbatteries?\b"),
    ("medical_device", r"\bmedical\s+devices?\b|\bdispositifs?\s+medic(al|aux)\b"),
    ("mechanical", r"\bmechanical\b|\bmecanique\b"),
    ("automotive_ecu", r"\becus?\b|\badas\b|\bvehicle\s+systems?\b"),
    ("avionics", r"\bavionics?\b|\bavioniques?\b"),
    ("aerospace_hardware", r"\baerospace\s+hardware\b"),
    ("robotics_hardware", r"\brobotics?\s+hardware\b|\brobotique\b"),
    ("industrial_automation", r"\bplcs?\b|\bscada\b|\bindustrial\s+automation\b|\bautomatisme\s+industriel\b"),
    ("hvac", r"\bhvac\b|\bcvc\b"),
    ("telecom_equipment", r"\btelecom\s+equipment\b|\bnetwork\s+equipment\b|\bran\b|\b5g\s+radio\b"),
    ("lidar_radar", r"\blidars?\b|\bradars?\b"),
    ("lab_equipment", r"\blab\s+equipment\b|\blaboratory\s+instruments?\b"),
    ("machine_tools", r"\bmachine\s+tools?\b"),
    ("appliances", r"\belectromenager\b|\bhome\s+appliances?\b|\bwhite\s+goods\b|\bconsumer\s+electronics\b"),
]

HARDWARE_TITLE_ANCHORS: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.IGNORECASE) for name, pattern in _HW_PATTERNS
}

# Software-context anchors used to RESCUE description-level hits when the
# posting is clearly a software/digital product despite a passing hardware
# mention (e.g. "we integrate with IoT sensor partners").
SOFTWARE_CONTEXT_ANCHORS: list[str] = [
    "saas", "software as a service", "api", "cloud", "llm",
    "machine learning", "data platform", "web", "mobile app",
    "e-commerce", "ecommerce", "marketplace", "fintech",
    "analytics platform", "b2b software",
    # 2026-09-10 live-run tuning: an Amazon "Fulfillment Technologies" PM
    # (catalog + inventory SOFTWARE, with incidental "hardware" / "sensors"
    # mentions) was rejected. Generic software words count too — the rescue
    # still needs several of them, and never overrides a core-requirement phrase.
    "software", "microservices", "backend", "algorithms", "systems",
    "software as a medical device", "samd", "digital product", "digital products",
]
_SOFTWARE_CONTEXT_RE = [re.compile(rf"\b{re.escape(a)}\b", re.IGNORECASE) for a in SOFTWARE_CONTEXT_ANCHORS]

# Phrases indicating the hardware domain is a CORE REQUIREMENT of the role
# (not just an incidental mention). A single hit among these is enough to
# reject even when only one hardware anchor total is found.
_CORE_REQUIREMENT_PATTERNS = [
    r"\bbackground\s+in\s+(electrical|electronics|hardware|mechanical)\s+engineering\b",
    r"\bexperience\s+(en|dans\s+l')\s*electronique\b",
    r"\bsemiconductor\s+industry\b",
    r"\bhardware\s+products?\b",
    r"\bproduits?\s+hardware\b",
    r"\bdegree\s+in\s+electrical\b",
    r"\bdiplome\s+d'ingenieur\s+en\s+electronique\b",
    r"\bphysical\s+products?\b",
    r"\bproduit\s+physique\b",
    r"\bfirmware\b",
    r"\bsystemes?\s+embarques?\b",
    r"\bembedded\s+systems?\b",
]
_CORE_REQUIREMENT_RE = [re.compile(p, re.IGNORECASE) for p in _CORE_REQUIREMENT_PATTERNS]

# Words that must NEVER trip a reject on their own — explicitly carved out so
# a lazy substring match elsewhere can't regress into false positives.
_NEVER_REJECT_ALONE = (
    "system", "platform", "iot", "embedded analytics", "embedded finance",
    "embedded payments", "digital twin", "smart building software",
)


def _clean(text: str) -> str:
    return _strip_accents((text or "").lower())


def _title_anchor_hits(text: str) -> list[str]:
    return [name for name, rx in HARDWARE_TITLE_ANCHORS.items() if rx.search(text)]


def _extra_anchor_hits(text: str, extra_anchors: list[str] | None) -> list[str]:
    """Plain substring, word-boundary matched, from profile.json's
    hard_filters.skip_domain_anchors."""
    if not extra_anchors:
        return []
    hits = []
    for a in extra_anchors:
        a = (a or "").strip().lower()
        if not a:
            continue
        a_clean = _strip_accents(a)
        if re.search(rf"\b{re.escape(a_clean)}\b", text):
            hits.append(a)
    return hits


# Anchors that are unambiguous in a TITLE but common software vocabulary in a
# DESCRIPTION ("instrumentation" = telemetry, "optics" = product optics,
# "sensor data", "mechanical" keyboard, "battery" of tests, "kernel" of a
# library). Live 2026-09-10: Proton's "Senior Product Manager (Inbox)" was
# rejected on "instrumentation,optics". Title-level matching keeps them.
_DESC_AMBIGUOUS_ANCHORS = {
    "instrumentation", "optics", "sensor", "mechanical", "battery", "rf",
    "lidar_radar", "kernel", "robotics_hardware", "hvac",
}
assert _DESC_AMBIGUOUS_ANCHORS <= set(dict(_HW_PATTERNS)), "ambiguous set must name real anchors"


_TITLE_SOFTWARE_RESCUE_RE = re.compile(
    r"\b(platform|plateforme|saas|software|logiciel|cloud|data|analytics|app|application|api|digital|numerique)\b",
    re.IGNORECASE,
)


def _distinct_matched_terms(text: str, extra_anchors: list[str] | None) -> list[str]:
    """Distinct hardware TERMS actually present in `text` (matched substrings,
    lower-cased, sorted) across built-in and profile anchors.

    2026-09-10 live-run bug: profile.json's `skip_domain_anchors` overlap the
    built-in patterns ("medical device" is both), so ONE mention used to count
    as TWO distinct hits and reject a software-as-a-medical-device role.
    Counting matched text instead of anchor names makes the count honest.
    """
    terms: set[str] = set()
    for name, rx in HARDWARE_TITLE_ANCHORS.items():
        if name in _DESC_AMBIGUOUS_ANCHORS:
            continue
        for m in rx.finditer(text):
            terms.add(re.sub(r"\s+", " ", m.group(0).strip().lower()))
    for a in extra_anchors or []:
        a_clean = _strip_accents((a or "").strip().lower())
        if a_clean and re.search(rf"\b{re.escape(a_clean)}\b", text):
            terms.add(a_clean)
    # Collapse plural/singular of the same word ("sensor" / "sensors").
    collapsed: dict[str, str] = {}
    for t in sorted(terms, key=len):
        key = t[:-1] if t.endswith("s") and t[:-1] in terms else t
        collapsed.setdefault(key, key)
    return sorted(collapsed)


def classify_domain(
    title: str,
    description: str,
    *,
    extra_anchors: list[str] | None = None,
) -> tuple[bool, str]:
    """Return (is_software_ok, reason).

    Rules:
      (a) Any title hardware anchor (incl. extra_anchors) -> reject.
      (b) Description: count DISTINCT strong anchors.
          - >=2 distinct -> reject, UNLESS the description is software-dominant
            (>=3 distinct software-context anchors AND no core-requirement
            phrase), in which case it is kept as ok_mixed_software_dominant.
          - exactly 1 distinct -> reject only if it coincides with a
            core-requirement phrase; otherwise it's an incidental mention ->
            keep.
          - 0 -> keep.
    """
    title_clean = _clean(title)
    desc_clean = _clean(description)

    title_hits = _title_anchor_hits(title_clean)
    title_hits += _extra_anchor_hits(title_clean, extra_anchors)
    if title_hits:
        # Ambiguous anchor + explicit software product words in the SAME title
        # ("Product Manager – Sensor Data Platform") → the product is software.
        unambiguous = [h for h in title_hits if h not in _DESC_AMBIGUOUS_ANCHORS]
        if not unambiguous and _TITLE_SOFTWARE_RESCUE_RE.search(title_clean):
            return True, "ok_title_software_product"
        return False, f"hardware_domain_title:{title_hits[0]}"

    desc_hits = _distinct_matched_terms(desc_clean, extra_anchors)
    if not desc_hits:
        return True, "ok"

    has_core_requirement = any(rx.search(desc_clean) for rx in _CORE_REQUIREMENT_RE)
    software_ctx_count = sum(1 for rx in _SOFTWARE_CONTEXT_RE if rx.search(desc_clean))

    if len(desc_hits) >= 2:
        # Software-dominant rescue: the posting talks about software at least as
        # much as about hardware (and never states a hardware core requirement).
        if not has_core_requirement and (software_ctx_count >= 3 or software_ctx_count >= len(desc_hits)):
            return True, "ok_mixed_software_dominant"
        return False, f"hardware_domain_desc:{','.join(desc_hits[:2])}"

    # Exactly one distinct hardware anchor in the description.
    if has_core_requirement:
        return False, f"hardware_domain_desc:{desc_hits[0]}"
    return True, "ok_incidental"


def filter_by_domain(
    jobs: list[NormalizedJob],
    *,
    extra_anchors: list[str] | None = None,
) -> tuple[list[NormalizedJob], dict]:
    """Partition jobs by domain classifier. Returns (kept, stats).

    stats = {
        "total_in": int,
        "kept": int,
        "rejected": int,
        "by_reason": {"hardware_domain_title:firmware": int, ...},
        "rejected_sample": [{"title": str, "reason": str}, ...],
    }
    """
    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}
    rejected_sample: list[dict] = []
    _REJECT_SAMPLE_CAP = 300

    for job in jobs:
        ok, reason = classify_domain(job.title, job.description_snippet, extra_anchors=extra_anchors)
        if ok:
            kept.append(job)
            continue
        by_reason[reason] = by_reason.get(reason, 0) + 1
        logger.info("domain_filter: rejected title=%r reason=%s", (job.title or "")[:120], reason)
        if len(rejected_sample) < _REJECT_SAMPLE_CAP:
            rejected_sample.append({"title": (job.title or "")[:120], "reason": reason})

    stats = {
        "total_in": len(jobs),
        "kept": len(kept),
        "rejected": len(jobs) - len(kept),
        "by_reason": by_reason,
        "rejected_sample": rejected_sample,
    }
    logger.info("domain_filter: %s", {k: v for k, v in stats.items() if k != "rejected_sample"})
    return kept, stats
