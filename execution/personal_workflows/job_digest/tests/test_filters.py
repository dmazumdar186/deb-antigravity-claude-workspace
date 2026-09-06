"""
description: Offline tests for normalizer/filters.py.
inputs: none (synthetic NormalizedJob fixtures via tests/_helpers.py)
outputs: pytest assertions
"""

from __future__ import annotations

from ..contracts import ContractType, RemoteMode
from ..normalizer.filters import _language_keeps, _location_keeps, _phrase_regex
from ..normalizer.filters import apply_filters
from ..profile_schema import Profile
from ._helpers import load_test_profile, make_normalized_job


def test_role_and_geography_scenario() -> None:
    """Profile: Sales Manager, countries [FR, IN], cities [Paris].
    Keeps a Paris sales-manager job, keeps a remote one, drops a Berlin one,
    and drops an intern.
    """
    profile = load_test_profile()

    paris_job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        description_snippet="Lead our B2B sales team in Paris.",
        url="https://example.com/jobs/paris",
    )
    remote_job = make_normalized_job(
        title="Regional Sales Manager",
        location="Remote",
        remote_mode=RemoteMode.REMOTE,
        description_snippet="Fully remote sales manager role.",
        url="https://example.com/jobs/remote",
    )
    berlin_job = make_normalized_job(
        title="Sales Manager",
        location="Berlin, Germany",
        description_snippet="Sales manager role based in Berlin.",
        url="https://example.com/jobs/berlin",
    )
    intern_job = make_normalized_job(
        title="Sales Manager Intern",
        location="Paris",
        contract_type=ContractType.INTERNSHIP,
        contract_type_raw="Internship",
        url="https://example.com/jobs/intern",
    )

    kept, stats = apply_filters([paris_job, remote_job, berlin_job, intern_job], profile)
    kept_titles = {(j.title, j.location) for j in kept}

    assert (paris_job.title, paris_job.location) in kept_titles
    assert (remote_job.title, remote_job.location) in kept_titles
    assert berlin_job.content_hash not in {j.content_hash for j in kept}
    assert intern_job.content_hash not in {j.content_hash for j in kept}
    assert stats["kept"] == 2
    assert stats["dropped_location"] == 1
    assert stats["dropped_exclude"] == 1


def test_title_filter_drops_unrelated_role() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Backend Software Engineer", location="Paris")
    kept, stats = apply_filters([job], profile)
    assert kept == []
    assert stats["dropped_title"] == 1


def test_exclude_title_substring_drops_job() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager Trainee", location="Paris")
    kept, stats = apply_filters([job], profile)
    assert kept == []
    assert stats["dropped_exclude"] == 1


def test_contract_filter_drops_disallowed_type() -> None:
    profile = load_test_profile()  # accepts permanent, fixed_term (not freelance)
    job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        contract_type=ContractType.FREELANCE,
        contract_type_raw="Freelance",
    )
    kept, stats = apply_filters([job], profile)
    assert kept == []
    assert stats["dropped_contract"] == 1


def test_unknown_location_is_kept() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Unknown")
    kept, _stats = apply_filters([job], profile)
    assert len(kept) == 1


def test_language_filter_drops_clearly_german_posting() -> None:
    profile = load_test_profile()  # languages derived from FR/IN -> ["fr", "en"]
    job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        description_snippet=(
            "Wir suchen eine erfahrene Vertriebsleitung fur unser Team in Berlin. "
            "Sie sind verantwortlich fur unseren Vertrieb und arbeiten eng mit "
            "unserem Standort zusammen, um Kunden zu betreuen und Umsatz zu "
            "steigern, weil wir stark wachsen."
        ),
    )
    kept, stats = apply_filters([job], profile)
    assert kept == []
    assert stats["dropped_language"] == 1


def _profile(**overrides) -> Profile:
    base = {
        "candidate": {"name": "Test Candidate", "email": "test.candidate@example.com"},
        "roles": [{"title": "Sales Manager"}],
        "locations": {"countries": ["FR", "DE"], "cities": [], "remote_ok": True},
        "screening": {"summary": "A sales manager with several years of B2B experience."},
    }
    base.update(overrides)
    return Profile.model_validate(base)


def test_h3_empty_languages_list_derives_from_countries_and_keeps() -> None:
    """profile.yaml with an explicit `languages: []` must behave like `null`
    (derive from countries), not silently reject every detectable language."""
    profile = _profile(languages=[])
    assert profile.languages == ["fr", "en", "de"]

    fr_job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        description_snippet=(
            "Nous recherchons un responsable des ventes pour notre equipe basee "
            "a Paris, avec une solide experience en gestion d'equipe commerciale."
        ),
    )
    assert _language_keeps(fr_job, profile) is True


def test_h3_language_keeps_true_when_profile_languages_empty_directly() -> None:
    # Defensive check on _language_keeps itself, bypassing _fill_defaults,
    # in case some future caller constructs languages=[] post-validation.
    profile = _profile(languages=["fr"])
    profile.languages = []
    job = make_normalized_job(
        title="Sales Manager",
        description_snippet=(
            "Wir suchen eine erfahrene Vertriebsleitung fur unser Team, "
            "verantwortlich fur unseren Vertrieb und unsere Kunden."
        ),
    )
    assert _language_keeps(job, profile) is True


def test_h4_city_alias_munich_matches_munchen() -> None:
    profile = _profile(locations={"countries": ["DE"], "cities": ["Munich"], "remote_ok": True})
    job = make_normalized_job(title="Sales Manager", location="München, Bayern, Germany")
    assert _location_keeps(job, profile) is True


def test_h4_city_alias_paris_keeps_paris_drops_lyon_unless_remote() -> None:
    profile = _profile(locations={"countries": ["FR"], "cities": ["Paris"], "remote_ok": True})
    paris_job = make_normalized_job(title="Sales Manager", location="Paris, Île-de-France, France")
    lyon_job = make_normalized_job(title="Sales Manager", location="Lyon, France")
    lyon_remote_job = make_normalized_job(
        title="Sales Manager", location="Lyon, France", remote_mode=RemoteMode.REMOTE
    )
    assert _location_keeps(paris_job, profile) is True
    assert _location_keeps(lyon_job, profile) is False
    assert _location_keeps(lyon_remote_job, profile) is True


def test_h4_city_constrains_only_its_own_country() -> None:
    """countries=[FR, DE], cities=['Paris']: a German job outside Paris is
    still kept — the city only constrains France, the country it belongs to."""
    profile = _profile(locations={"countries": ["FR", "DE"], "cities": ["Paris"], "remote_ok": True})
    berlin_job = make_normalized_job(title="Sales Manager", location="Berlin, Germany")
    paris_job = make_normalized_job(title="Sales Manager", location="Paris, France")
    lyon_job = make_normalized_job(title="Sales Manager", location="Lyon, France")
    assert _location_keeps(berlin_job, profile) is True
    assert _location_keeps(paris_job, profile) is True
    assert _location_keeps(lyon_job, profile) is False


def test_h4_fr_only_nantes_city_keeps_nantes_drops_paris() -> None:
    profile = _profile(locations={"countries": ["FR"], "cities": ["Nantes"], "remote_ok": True})
    nantes_job = make_normalized_job(title="Sales Manager", location="Nantes, France")
    paris_job = make_normalized_job(title="Sales Manager", location="Paris, France")
    assert _location_keeps(nantes_job, profile) is True
    assert _location_keeps(paris_job, profile) is False


def test_minor_phrase_regex_matches_non_word_boundary_keywords() -> None:
    assert _phrase_regex("C++").search("c++ developer wanted")
    assert _phrase_regex("C#").search("looking for a c# engineer")
    assert _phrase_regex(".NET").search("senior .net developer")
    # still word-bounded on the alnum side: "cats" must not match "C" alone etc.
    assert not _phrase_regex("C++").search("ccc++ role")
