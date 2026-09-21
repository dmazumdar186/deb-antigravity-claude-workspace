"""
Tests for eval/labels.py -- blind human ground truth + Cohen's kappa.
Zero network, zero LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gtm_client_workflows.gaia_sourcing.eval.labels import (
    GRADE_VALUES,
    Label,
    append_label,
    build_worksheet_row,
    cohen_kappa,
    kappa_for_field,
    labels_by_person,
    load_labels,
)
from gtm_client_workflows.gaia_sourcing.layers.gates import _GRADE_ORDER

FIXTURES = Path(__file__).parent / "fixtures" / "eval"


def test_grade_values_is_the_gates_ladder_plus_unknown():
    """The label ladder and the gate ladder must never drift apart -- that
    is the whole point of grade_precision comparing like with like."""
    assert GRADE_VALUES == tuple(_GRADE_ORDER) + ("unknown",)


def test_label_accepts_a_well_formed_row():
    lbl = Label(
        person_id="alice",
        grade="principal_or_associate",
        location_country="IE",
        chartered="yes",
        labeller="sam",
        notes="grade: \"Principal Engineer\"",
    )
    assert lbl.person_id == "alice"
    assert lbl.chartered == "yes"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("grade", "senior_associate"),   # not on the ladder
        ("location_country", "England"),  # must be the coarse bucket
        ("chartered", "maybe"),           # not yes/no/unknown
    ],
)
def test_label_rejects_a_value_off_its_literal(field, bad_value):
    kwargs = dict(
        person_id="alice", grade="engineer", location_country="IE",
        chartered="unknown", labeller="sam",
    )
    kwargs[field] = bad_value
    with pytest.raises(ValidationError):
        Label(**kwargs)


def test_append_and_load_roundtrip(tmp_path):
    path = tmp_path / "labels.jsonl"
    lbl1 = Label(
        person_id="alice", grade="principal_or_associate",
        location_country="IE", chartered="yes", labeller="sam",
    )
    lbl2 = Label(
        person_id="bob", grade="associate_director",
        location_country="IE", chartered="unknown", labeller="pat",
    )
    append_label(lbl1, path=path)
    append_label(lbl2, path=path)

    loaded = load_labels(path)
    assert [l.person_id for l in loaded] == ["alice", "bob"]
    assert loaded[0].grade == "principal_or_associate"


def test_load_labels_missing_file_is_empty_not_an_error(tmp_path):
    assert load_labels(tmp_path / "nope.jsonl") == []


def test_load_labels_skips_a_malformed_line_without_crashing(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text(
        json.dumps({
            "person_id": "alice", "grade": "engineer",
            "location_country": "IE", "chartered": "unknown", "labeller": "sam",
        }) + "\n"
        + "not even json\n"
        + json.dumps({"person_id": "bob", "grade": "not_on_the_ladder"}) + "\n",
        encoding="utf-8",
    )
    loaded = load_labels(path)
    assert [l.person_id for l in loaded] == ["alice"]


def test_labels_by_person_groups_multiple_labellers():
    labels = [
        Label(person_id="alice", grade="engineer", location_country="IE",
              chartered="unknown", labeller="sam"),
        Label(person_id="alice", grade="engineer", location_country="IE",
              chartered="unknown", labeller="pat"),
        Label(person_id="bob", grade="director", location_country="UK",
              chartered="no", labeller="sam"),
    ]
    grouped = labels_by_person(labels)
    assert len(grouped["alice"]) == 2
    assert len(grouped["bob"]) == 1


def test_cohen_kappa_perfect_agreement_is_one():
    a = ["yes", "no", "yes", "unknown"]
    b = ["yes", "no", "yes", "unknown"]
    assert cohen_kappa(a, b) == pytest.approx(1.0)


def test_cohen_kappa_no_variability_and_full_agreement_returns_one():
    # Both raters used exactly one category throughout -- pe would divide by
    # zero; the documented behaviour is to report perfect agreement.
    a = ["yes", "yes", "yes"]
    b = ["yes", "yes", "yes"]
    assert cohen_kappa(a, b) == pytest.approx(1.0)


def test_cohen_kappa_known_partial_agreement_value():
    # Hand-checkable: po=4/6, pe=1/3 -> kappa=(2/3-1/3)/(1-1/3)=1/3.
    a = ["A", "A", "B", "B", "A", "B"]
    b = ["A", "B", "B", "B", "A", "A"]
    k = cohen_kappa(a, b)
    assert k == pytest.approx(1 / 3)


def test_cohen_kappa_rejects_mismatched_or_empty_sequences():
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_kappa_for_field_uses_the_fixture_raters():
    labels_a = load_labels(FIXTURES / "labels_rater_a.jsonl")
    labels_b = load_labels(FIXTURES / "labels_rater_b.jsonl")
    k, n = kappa_for_field(labels_a, labels_b, "grade")
    assert n == 4
    # rater_a/rater_b agree on alice/dave/erin, disagree on bob's grade.
    # po=0.75 (3/4 raw agreement), pe=0.25 -> kappa=(0.75-0.25)/(1-0.25).
    assert k == pytest.approx(2 / 3, abs=0.01)

    k_loc, n_loc = kappa_for_field(labels_a, labels_b, "location_country")
    assert n_loc == 4
    assert k_loc == pytest.approx(1.0)  # raters agree on location throughout


def test_kappa_for_field_raises_on_no_overlap():
    labels_a = [Label(person_id="only_a", grade="engineer",
                       location_country="IE", chartered="unknown", labeller="a")]
    labels_b = [Label(person_id="only_b", grade="engineer",
                       location_country="IE", chartered="unknown", labeller="b")]
    with pytest.raises(ValueError):
        kappa_for_field(labels_a, labels_b, "grade")


def test_build_worksheet_row_carries_no_extractor_verdict():
    row = build_worksheet_row(
        "alice", "Alice Byrne",
        [{"doc_id": "d1", "url": "https://example.ie/p", "text_source": "text_layer",
          "content_text": "Alice Byrne is a Principal Engineer based in Galway."}],
    )
    assert row["person_id"] == "alice"
    assert row["full_name"] == "Alice Byrne"
    assert len(row["source_excerpts"]) == 1
    excerpt = row["source_excerpts"][0]
    assert excerpt["excerpt"].startswith("Alice Byrne is a Principal Engineer")
    # No extractor verdict fields anywhere in the row -- the labeller must
    # see raw text only.
    for forbidden in ("grade", "tier", "chartered", "location_country",
                       "dimension", "assertion", "confidence"):
        assert forbidden not in row
        assert forbidden not in excerpt


def test_build_worksheet_row_truncates_a_long_excerpt():
    long_text = "x" * 10_000
    row = build_worksheet_row(
        "alice", "Alice Byrne",
        [{"doc_id": "d1", "url": "https://example.ie/p", "content_text": long_text}],
    )
    assert len(row["source_excerpts"][0]["excerpt"]) == 4000
