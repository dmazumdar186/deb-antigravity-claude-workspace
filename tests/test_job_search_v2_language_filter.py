"""Unit tests for job_search_v2.normalizer.language_filter — the second gate
(2026-10-26): EN/FR postings that REQUIRE a third language, plus raw-title
German/Dutch tells. Pure functions, no network, no langdetect needed for the
title-only cases (short titles skip langdetect by design).
"""
from __future__ import annotations

import pytest

from execution.personal_workflows.job_search_v2.normalizer.language_filter import (
    _requires_other_language,
    classify_language,
)

DELIVERED_2026_10_24 = "Staff Product Manager - Accounting Europe - German speaking 🇩🇪"


def test_delivered_qonto_title_is_rejected():
    ok, reason = classify_language(DELIVERED_2026_10_24, "")
    assert ok is False and reason == "reject:requires_other_language"


@pytest.mark.parametrize("title, desc", [
    ("Product Manager - German speaking", ""),
    ("Product Manager (German-speaking)", ""),
    ("Senior PM", "You are fluent in German and English."),
    ("Senior PM", "Fluent German required for this role."),
    ("Senior PM", "Native German speaker with 5 years in fintech."),
    ("Senior PM", "Fluency in German is mandatory."),
    ("Senior PM", "Business-level German is required."),
    ("Senior PM", "Deutschkenntnisse auf C1-Niveau erforderlich."),
    ("Senior PM", "Deutsch fließend in Wort und Schrift."),
    ("Senior PM", "Verhandlungssichere Deutschkenntnisse."),
    ("Product Owner", "Dutch speaking candidates only."),
    ("Product Owner", "Je bent nederlandstalig."),
    ("Product Owner", "Fluent in Dutch and English."),
    ("Product Owner", "Fluent in Polish."),
    ("Product Owner", "Fluent in Italian is required."),
    ("Product Owner", "Fluent in Spanish and English."),
    ("Product Owner", "Fluent in Portuguese."),
    ("Product Owner - Polish speaking", ""),
    ("Product Owner - Spanish speaking", ""),
    ("Product Owner - Italian speaking", ""),
    ("Chef de produit", "Langue allemande requise."),
    ("Chef de produit", "Langue allemande exigée."),
    ("Chef de produit", "Langue allemande courante."),
    ("Chef de produit", "Allemand courant indispensable."),
    ("Chef de produit", "Bilingue allemand."),
    ("Chef de produit", "Maîtrise de l'allemand impérative."),
    ("Chef de produit 🇳🇱", ""),
    ("Product Manager 🇵🇱 Warsaw", ""),
    ("Product Manager 🇮🇹", ""),
    ("Product Manager 🇪🇸", ""),
])
def test_requires_other_language_rejects(title, desc):
    ok, reason = classify_language(title, desc)
    assert ok is False, (title, desc, reason)
    assert reason == "reject:requires_other_language"


@pytest.mark.parametrize("title, desc", [
    # "a plus / nice to have" must NOT reject.
    ("Senior Product Manager", "German is a plus. You will work with our Berlin team."),
    ("Senior Product Manager", "Fluent German would be a plus but is not required."),
    ("Senior Product Manager", "German nice to have."),
    ("Senior Product Manager", "German or Dutch is an advantage."),
    ("Chef de produit", "L'allemand serait un plus."),
    ("Chef de produit", "Allemand apprécié."),
    ("Chef de produit", "La maîtrise de l'allemand est un atout."),
    ("Senior Product Manager", "Deutsch ist ein Plus."),
    # EN/FR requirements are fine.
    ("Senior Product Manager", "Fluent in English and French required."),
    ("Chef de produit (H/F)", "Anglais courant exigé. Poste basé à Paris."),
    # Market mentions are not language requirements.
    ("Senior Product Manager", "You will own the product for the German market and the Dutch retail segment."),
    ("Product Manager - DACH", "Lead expansion across Germany, Austria and Switzerland."),
    ("Product Manager 🇫🇷", ""),
    ("Product Manager 🇬🇧🇺🇸 Remote", ""),
])
def test_language_as_a_plus_or_market_mention_is_kept(title, desc):
    ok, reason = classify_language(title, desc)
    assert ok is True, (title, desc, reason)


def test_requires_other_language_helper_returns_matched_phrase():
    assert _requires_other_language("PM", "Fluent in German required.") is not None
    assert _requires_other_language("PM", "German is a plus.") is None
    assert _requires_other_language("PM 🇩🇪", "") == "title_flag:🇩🇪"


@pytest.mark.parametrize("title, want", [
    ("Produktmanager (m/w/d)", "reject:de_title_tell"),
    ("Produktmanagerin Digital", "reject:de_title_tell"),
    ("Product Manager (m/w/d)", "reject:de_title_tell"),
    ("Product Owner (w/m/d)", "reject:de_title_tell"),
    ("Mitarbeiter Produktmanagement", "reject:de_title_tell"),
    ("Product Owner (m/v)", "reject:nl_title_tell"),
    ("Medewerker productbeheer", "reject:nl_title_tell"),
])
def test_short_title_german_dutch_tells_reject_without_langdetect(title, want):
    ok, reason = classify_language(title, "")
    assert ok is False and reason == want


@pytest.mark.parametrize("title", [
    "Product Manager (H/F)",
    "Product Manager (F/H/X)",
    "Product Manager (all genders)",
    "Product Manager (f/m/x) - Berlin",
    "Staff AI Engineer - M/W",
    "Product Owner Secteur Immobilier",
])
def test_en_fr_gender_markers_and_short_titles_still_pass(title):
    ok, reason = classify_language(title, "")
    assert ok is True, (title, reason)


def test_filter_by_language_counts_new_reason():
    from datetime import datetime, timezone
    from execution.personal_workflows.job_search_v2.contracts import (
        ContractType, JobSource, NormalizedJob, RemoteMode, compute_content_hash,
    )
    from execution.personal_workflows.job_search_v2.normalizer.language_filter import filter_by_language

    def mk(title):
        url = "https://example.com/j/" + str(abs(hash(title)))
        return NormalizedJob(
            source=JobSource.FIXTURE, source_id="1", url=url, canonical_url=url, title=title,
            company="Qonto", location="Berlin", description_snippet="", posted_at=None,
            contract_type=ContractType.CDI, contract_type_raw="CDI", remote_mode=RemoteMode.UNKNOWN,
            fetched_at=datetime.now(timezone.utc), content_hash=compute_content_hash(title, "Qonto", url),
        )

    kept, stats = filter_by_language([mk(DELIVERED_2026_10_24), mk("Senior Product Manager")])
    assert [j.title for j in kept] == ["Senior Product Manager"]
    assert stats["by_reason"]["requires_other_language"] == 1
