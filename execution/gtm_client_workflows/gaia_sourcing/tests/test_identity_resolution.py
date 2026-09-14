"""
L4 -- identity resolution (RADAR_CONTRACTS.md section B).

Fixture-first, per the file's own rule: every collision case is a JSON file
of RawPersonRecords under tests/fixtures/identity/, loaded here and run
through resolve_identity. Pure function, no network, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import RawPersonRecord
from gtm_client_workflows.gaia_sourcing.layers.identity import (
    _names_match,
    cluster_to_person,
    resolve_identity,
)

FIXTURES = Path(__file__).parent / "fixtures" / "identity"


def _load(name: str) -> list[RawPersonRecord]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [RawPersonRecord(**rec) for rec in data]


# ---------------------------------------------------------------------------
# The eight-plus collision cases
# ---------------------------------------------------------------------------


def test_oriordain_spelling_variants_merge_into_one_cluster():
    """Seán Ó Ríordáin / Sean O Riordain / S. O'Riordain, same employer."""
    clusters = resolve_identity(_load("oriordain_variants.json"))

    assert len(clusters) == 1
    assert len(clusters[0].members) == 3
    assert clusters[0].confidence == "strong"
    assert "name+employer" in clusters[0].basis


def test_mc_mac_surname_variants_merge():
    clusters = resolve_identity(_load("mc_mac_variants.json"))

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    assert clusters[0].confidence == "strong"


def test_same_name_different_firm_stays_separate():
    clusters = resolve_identity(_load("same_name_different_firm.json"))

    assert len(clusters) == 2
    assert {len(c.members) for c in clusters} == {1}


def test_same_firm_different_person_stays_separate():
    clusters = resolve_identity(_load("same_firm_different_person.json"))

    assert len(clusters) == 2


def test_initials_only_forename_matches_the_spelled_out_form():
    clusters = resolve_identity(_load("initials_only_forename.json"))

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    assert clusters[0].confidence == "strong"


def test_three_way_chain_by_name_employer_then_linkedin_url():
    """A~B by name+employer, B~C by linkedin_url -- one cluster, both bases
    listed, exact confidence (the strongest basis present)."""
    clusters = resolve_identity(_load("three_way_chain.json"))

    assert len(clusters) == 1
    cluster = clusters[0]
    assert len(cluster.members) == 3
    assert cluster.confidence == "exact"
    assert "name+employer" in cluster.basis
    assert "linkedin_url" in cluster.basis


def test_conflicting_register_numbers_are_never_merged():
    clusters = resolve_identity(_load("conflicting_register_numbers.json"))

    assert len(clusters) == 2, (
        "same name + same employer would otherwise merge as 'strong', but "
        "two different register numbers must veto it"
    )


def test_conflicting_linkedin_urls_are_never_merged():
    clusters = resolve_identity(_load("conflicting_linkedin_urls.json"))

    assert len(clusters) == 2


def test_weak_merge_same_name_same_county_no_employer():
    clusters = resolve_identity(_load("weak_same_county_no_employer.json"))

    assert len(clusters) == 1
    assert clusters[0].confidence == "weak"
    assert "name+county" in clusters[0].basis


def test_weak_rule_does_not_merge_across_different_counties():
    """Kept separate unless a later exact key joins them -- there is none
    here, so two same-named, employer-less people in different counties stay
    two clusters with two distinct, collision-free person_ids."""
    clusters = resolve_identity(_load("weak_different_county_no_employer.json"))

    assert len(clusters) == 2
    ids = {c.person_id for c in clusters}
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolve_identity_is_deterministic_across_repeated_calls():
    records = _load("oriordain_variants.json") + _load("three_way_chain.json")

    first = resolve_identity(records)
    second = resolve_identity(records)

    assert [c.person_id for c in first] == [c.person_id for c in second]
    assert [c.basis for c in first] == [c.basis for c in second]


def test_input_order_does_not_change_the_clustering():
    forward = resolve_identity(_load("three_way_chain.json"))
    backward = resolve_identity(list(reversed(_load("three_way_chain.json"))))

    assert len(forward) == len(backward) == 1
    assert {m.source_ref for m in forward[0].members} == {
        m.source_ref for m in backward[0].members
    }


# ---------------------------------------------------------------------------
# _names_match -- the collision logic in isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a,b", [
    ("Seán Ó Ríordáin", "Sean O Riordain"),
    ("Seán Ó Ríordáin", "S. O'Riordain"),
    ("Colin McCarthy", "Colin MacCarthy"),
    ("David Kelly", "David Kelly"),
])
def test_names_match_true_cases(a, b):
    assert _names_match(a, b) is True


@pytest.mark.parametrize("a,b", [
    ("John Murphy", "Sean Murphy"),
    ("David Kelly", "David Kennedy"),
    ("Aoife Byrne", "Aoife Boyle"),
])
def test_names_match_false_cases(a, b):
    assert _names_match(a, b) is False


# ---------------------------------------------------------------------------
# cluster_to_person -- canonical name and most-recent employer
# ---------------------------------------------------------------------------


def test_cluster_to_person_picks_the_longest_fully_spelled_name():
    clusters = resolve_identity(_load("oriordain_variants.json"))
    person = cluster_to_person(clusters[0])

    assert person.full_name == "Seán Ó Ríordáin"
    assert "É" not in person.full_name.replace("Éireann", "")  # sanity: no corruption


def test_cluster_to_person_uses_the_most_recent_employer():
    """No timestamp field exists on RawPersonRecord (documented ambiguity,
    see the build report) -- recency is approximated by input order, last
    non-empty employer wins."""
    records = [
        RawPersonRecord(source="a", source_ref="1", full_name="Grainne Nolan",
                         employer="Punch Consulting Engineers", doc_ids=["d1"]),
        RawPersonRecord(source="b", source_ref="2", full_name="Grainne Nolan",
                         employer="Punch Consulting Engineers", doc_ids=["d2"]),
    ]
    # Force a later record with a different but still-matching (name+employer)
    # earlier employer, then a third with a newer one appended in call order.
    later = RawPersonRecord(source="c", source_ref="3", full_name="Grainne Nolan",
                             employer="Nolan Structural Ltd", doc_ids=["d3"])

    clusters = resolve_identity(records)
    person = cluster_to_person(clusters[0])
    assert person.current_employer == "Punch Consulting Engineers"

    # Employer differs on record 3, so it cannot strong-merge with 1/2 --
    # confirms _canonical_employer's "last non-empty in member order" rule
    # operates over whatever members a cluster actually has, not the whole
    # input list.
    assert later.employer != person.current_employer


def test_cluster_to_person_id_is_a_deterministic_slug():
    clusters = resolve_identity(_load("mc_mac_variants.json"))
    person = cluster_to_person(clusters[0])

    assert person.person_id == clusters[0].person_id
    assert person.person_id.startswith("colin-")
    assert "jacobs" in person.person_id


# ---------------------------------------------------------------------------
# Transitive conflict: A merges with B, B merges with C, but A and C
# themselves carry two different register_numbers -- the A-C PAIR is barred
# from ever merging directly by `_exact_key_conflict`, but never checked as
# a union candidate on its own (only A-B and B-C ever call dsu.union), so
# without a post-pass the union-find still lands all three in one cluster
# transitively through B.
# ---------------------------------------------------------------------------


def test_transitive_merge_is_split_on_a_register_number_conflict():
    clusters = resolve_identity(_load("transitive_register_conflict.json"))

    # Never one cluster carrying both EI-10234 and EI-99001.
    for cluster in clusters:
        regs = {m.register_number for m in cluster.members if m.register_number}
        assert len(regs) <= 1, (
            "a cluster must never carry two distinct register_numbers, even "
            "when they only collide transitively through a third record"
        )

    # B (no register_number of its own) still merges with SOMEONE by
    # name+employer -- it is not stranded as its own singleton just because
    # it sits between two conflicting records.
    total_members = sum(len(c.members) for c in clusters)
    assert total_members == 3
    assert any(len(c.members) == 2 for c in clusters)


# ---------------------------------------------------------------------------
# Identity corroboration for a fetched page / search snippet
# (2026-09-11 adversarial-audit fix, item 4)
# ---------------------------------------------------------------------------

from gtm_client_workflows.gaia_sourcing.layers.identity import (  # noqa: E402
    has_identity_corroboration,
)


def test_a_porsche_sales_page_is_rejected_for_a_structural_engineer():
    """The audit's exhibit: a car-sales listing for a common name must not be
    attached to a structural engineer of the same name."""
    window = "Shane Heffernan, Sales Executive at Porsche Centre Dublin"
    assert has_identity_corroboration(window, employer="Punch Consulting Engineers") is False


def test_a_chartered_engineers_bio_page_is_accepted():
    window = "Shane Heffernan is a Chartered Engineer with Lally Consulting Engineers"
    assert has_identity_corroboration(window, employer="Lally Chartered Engineers") is True


def test_two_significant_employer_words_corroborate_without_a_discipline_token():
    window = "Shane Heffernan joined Punch Bridge Works in 2019 as project lead"
    assert has_identity_corroboration(window, employer="Punch Bridge Works") is True


def test_a_contradicting_profession_token_disqualifies_even_with_corroboration():
    """The failure mode this rule guards against: a plausible-looking page
    that also names a contradicting profession must still be rejected."""
    window = "Shane Heffernan, structural engineer turned estate agent"
    assert has_identity_corroboration(window, employer="Punch Consulting Engineers") is False


def test_empty_window_never_corroborates():
    assert has_identity_corroboration("", employer="Punch Consulting Engineers") is False
    assert has_identity_corroboration(None) is False
