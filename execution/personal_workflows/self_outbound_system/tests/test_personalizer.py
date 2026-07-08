"""
test_personalizer.py
description: Dry-run tests for personalizer.py against the 3 seed leads. Assert every subject/opener conforms to tone.json constraints (word counts, banned words, no leaked template tokens).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from personalizer import personalize_dry_run, _subject_ok, _opener_ok

ROOT = Path(__file__).resolve().parent.parent
TONE_JSON = ROOT / "config" / "tone.json"
LEADS_SEED = ROOT / "tests" / "fixtures" / "leads_seed.json"


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def tone_cfg() -> dict:
    return _load(TONE_JSON)


@pytest.fixture(scope="module")
def seed_leads() -> list[dict]:
    payload = _load(LEADS_SEED)
    leads = payload["leads"]
    # personalizer expects an assigned segment field
    for lead in leads:
        lead["segment"] = lead.get("segment_hint")
    return leads


def test_all_seed_leads_personalize_without_refusal(seed_leads, tone_cfg):
    personalized, refused, cost = personalize_dry_run(seed_leads, tone_cfg)
    assert cost == 0.0
    assert refused == [], f"seed leads were refused: {refused}"
    assert len(personalized) == len(seed_leads)


def test_subjects_conform_to_constraints(seed_leads, tone_cfg):
    personalized, _refused, _cost = personalize_dry_run(seed_leads, tone_cfg)
    constraints = tone_cfg["subject_constraints"]
    for lead in personalized:
        ok, reason = _subject_ok(lead["subject"], constraints)
        assert ok, f"subject failed: {lead['subject']} -> {reason}"


def test_openers_conform_to_constraints(seed_leads, tone_cfg):
    personalized, _refused, _cost = personalize_dry_run(seed_leads, tone_cfg)
    constraints = tone_cfg["opener_constraints"]
    buzz = tone_cfg["voice"]["buzzwords_never_use"]
    for lead in personalized:
        ok, reason = _opener_ok(lead["opener"], constraints, buzz)
        assert ok, f"opener failed: {lead['opener']} -> {reason}"


def test_no_leaked_template_tokens_in_body(seed_leads, tone_cfg):
    """Body may contain footer placeholders ({{unsubscribe_link}} / {{postal_address}})
    but the opener + subject must be fully expanded."""
    personalized, _refused, _cost = personalize_dry_run(seed_leads, tone_cfg)
    for lead in personalized:
        assert "{company}" not in lead["opener"]
        assert "{company}" not in lead["subject"]
        assert "{product}" not in lead["opener"]
        assert "{role}" not in lead["opener"]


def test_subject_rejects_banned_words(tone_cfg):
    """Sanity-check: a subject with a banned word must fail validation."""
    ok, reason = _subject_ok("free money urgent", tone_cfg["subject_constraints"])
    assert not ok
    assert "banned-word" in reason
