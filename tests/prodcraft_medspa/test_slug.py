"""
test_slug.py
description: Tests for common/slug.py — slugify, random_suffix, preview_host.
inputs: N/A (pytest).
outputs: N/A (pytest).
"""

from __future__ import annotations

import re

from execution.personal_workflows.prodcraft_medspa.common.slug import (
    preview_host,
    random_suffix,
    slugify,
)


def test_slugify_basic():
    assert slugify("Glow Aesthetics") == "glow-aesthetics"


def test_slugify_strips_llc_and_inc():
    assert slugify("Radiant Med Spa, LLC") == "radiant-med-spa"
    assert slugify("Skinly Aesthetics Inc") == "skinly-aesthetics"


def test_slugify_does_not_strip_med_spa():
    # CONTRACTS.md: "med spa" suffix noise is NOT stripped.
    assert slugify("Winnetka Med Spa") == "winnetka-med-spa"


def test_slugify_lowercase_ascii_hyphens():
    slug = slugify("Château Beauté & Co.")
    assert slug == re.sub(r"[^a-z0-9-]", "", slug)
    assert slug.islower() or slug == slug.lower()


def test_slugify_max_length():
    long_name = "A" * 100 + " Medical Aesthetics And Wellness Spa Center"
    slug = slugify(long_name)
    assert len(slug) <= 40


def test_slugify_empty_fallback():
    assert slugify("") == "business"
    assert slugify("LLC") == "business"


def test_slugify_no_leading_trailing_hyphen():
    slug = slugify("  --Glow!! Aesthetics--  ")
    assert not slug.startswith("-")
    assert not slug.endswith("-")


def test_random_suffix_length_and_alphabet():
    suffix = random_suffix()
    assert len(suffix) == 6
    assert re.fullmatch(r"[a-z0-9]{6}", suffix)


def test_random_suffix_custom_length():
    assert len(random_suffix(10)) == 10


def test_random_suffix_is_random():
    suffixes = {random_suffix() for _ in range(50)}
    assert len(suffixes) > 1


def test_preview_host():
    host = preview_host("glow-aesthetics", "k3x9qa", "preview.prodcraft.fyi")
    assert host == "glow-aesthetics-k3x9qa.preview.prodcraft.fyi"
