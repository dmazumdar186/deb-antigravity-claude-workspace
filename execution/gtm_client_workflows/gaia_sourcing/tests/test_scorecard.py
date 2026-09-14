"""
Tests for eval/scorecard.py against the fixture run directory under
tests/fixtures/eval/sample_run/. Zero network, zero LLM -- pure file reads
and the deterministic gates.py functions the pipeline itself uses.

Fixture shape (see tests/fixtures/eval/sample_run/*.json):
  role1_senior_structural_engineer (ceiling: principal_or_associate)
    alice -- Principal Engineer, Galway  -- delivered, grade OK
    bob   -- Associate Director, Dublin  -- delivered, grade ABOVE ceiling
             (the one deliberate composition_violations hit)
    carol -- Graduate Engineer            -- in pool, not delivered
  role2_transport_major_projects_manager (ceiling: associate_director,
                                           county Cork)
    dave  -- Senior Engineer, Cork        -- delivered, clean
    erin  -- Director, London             -- in pool, not delivered
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.eval import scorecard as sc

FIXTURE_RUN = Path(__file__).parent / "fixtures" / "eval" / "sample_run"
FIXTURE_LABELS_CORRECT = Path(__file__).parent / "fixtures" / "eval" / "labels_correct.jsonl"
FIXTURE_LABELS_MIXED = Path(__file__).parent / "fixtures" / "eval" / "labels_mixed.jsonl"


@pytest.fixture
def run_dir(tmp_path) -> Path:
    """A private, writable copy of the fixture run directory."""
    dest = tmp_path / "run"
    shutil.copytree(FIXTURE_RUN, dest)
    return dest


def test_compute_scorecard_needs_the_stage_files(tmp_path):
    empty = tmp_path / "empty_run"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        sc.compute_scorecard(empty, labels_path=tmp_path / "no_labels.jsonl", spend_eur=0.0)


def test_quote_drop_rate_reads_validate_stats(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    assert result["quote_drop_rate"] == pytest.approx(0.2)


def test_delivered_over_pool_combines_both_roles(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    # delivered = 2 (role1) + 1 (role2) = 3; assessed = 3 + 2 = 5
    assert result["delivered"] == 3
    assert result["profiles_assessed"] == 5
    assert result["delivered_over_pool"] == pytest.approx(3 / 5)


def test_cost_per_delivered_card_divides_spend_by_delivered(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=12.0)
    assert result["cost_per_delivered_card"] == pytest.approx(4.0)  # 12 / 3 delivered


def test_cost_per_delivered_card_is_none_when_nobody_delivered(tmp_path):
    # delivered_over_pool / cost_per_delivered_card read the DENOMINATOR from
    # poolmap.json (the honest, authoritative counts), not by recomputing
    # list lengths off delivery.json -- so a "nobody delivered" scenario has
    # to zero both files out, matching what stage_poolmap itself would write.
    dest = tmp_path / "run"
    shutil.copytree(FIXTURE_RUN, dest)
    (dest / "delivery.json").write_text(
        json.dumps({
            "role1_senior_structural_engineer": [],
            "role2_transport_major_projects_manager": [],
        }),
        encoding="utf-8",
    )
    poolmap = json.loads((dest / "poolmap.json").read_text(encoding="utf-8"))
    for m in poolmap.values():
        m["delivered"] = 0
    (dest / "poolmap.json").write_text(json.dumps(poolmap), encoding="utf-8")

    result = sc.compute_scorecard(dest, labels_path=Path("/does/not/exist.jsonl"), spend_eur=5.0)
    assert result["cost_per_delivered_card"] is None
    assert result["delivered_over_pool"] == 0.0


def test_composition_violations_catches_bob_over_the_ceiling(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    assert result["composition_violations"] == 1
    assert any("Bob Nolan" in v for v in result["composition_violations_detail"])
    assert any("associate_director" in v for v in result["composition_violations_detail"])


def test_composition_violations_is_zero_once_bob_is_not_delivered(run_dir):
    (run_dir / "delivery.json").write_text(
        json.dumps({
            "role1_senior_structural_engineer": ["alice"],
            "role2_transport_major_projects_manager": ["dave"],
        }),
        encoding="utf-8",
    )
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    assert result["composition_violations"] == 0


def test_precision_numbers_are_none_without_labels(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    assert result["grade_precision"] is None
    assert result["residence_precision"] is None
    assert result["n_labels"] == 0


def test_grade_precision_is_perfect_with_correct_labels(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_CORRECT, spend_eur=0.0)
    assert result["grade_precision"] == pytest.approx(1.0)
    assert result["residence_precision"] == pytest.approx(1.0)
    assert result["n_labels"] == 2


def test_grade_precision_drops_with_a_mislabelled_row(run_dir):
    # labels_mixed.jsonl deliberately mislabels erin's grade -- see the fixture.
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_MIXED, spend_eur=0.0)
    assert result["grade_precision"] == pytest.approx(2 / 3)
    assert result["grade_precision"] < sc.SHIP_MIN_GRADE_PRECISION
    # residence_country was NOT mislabelled in that fixture, so it stays 1.0.
    assert result["residence_precision"] == pytest.approx(1.0)


def test_ship_ok_blocks_on_composition_violation_alone(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_CORRECT, spend_eur=0.0)
    ok, reasons = sc.ship_ok(result)
    assert ok is False
    assert any("composition_violations" in r for r in reasons)
    # grade precision is fine here (1.0 from labels_correct), so it must not
    # appear as a reason.
    assert not any("grade_precision" in r for r in reasons)


def test_ship_ok_blocks_on_low_grade_precision_alone(run_dir):
    (run_dir / "delivery.json").write_text(
        json.dumps({
            "role1_senior_structural_engineer": ["alice"],
            "role2_transport_major_projects_manager": ["dave"],
        }),
        encoding="utf-8",
    )
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_MIXED, spend_eur=0.0)
    assert result["composition_violations"] == 0
    ok, reasons = sc.ship_ok(result)
    assert ok is False
    assert any("grade_precision" in r for r in reasons)


def test_ship_ok_passes_clean_pool_with_good_labels(run_dir):
    (run_dir / "delivery.json").write_text(
        json.dumps({
            "role1_senior_structural_engineer": ["alice"],
            "role2_transport_major_projects_manager": ["dave"],
        }),
        encoding="utf-8",
    )
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_CORRECT, spend_eur=0.0)
    assert result["ship_ok"] is True
    assert result["ship_reasons"] == []


def test_ship_ok_does_not_block_on_missing_labels():
    """No labels yet is advisory (n/a), never a ship blocker on its own."""
    ok, reasons = sc.ship_ok({
        "composition_violations": 0,
        "grade_precision": None,
    })
    assert ok is True
    assert reasons == []


def test_render_table_shows_na_without_labels_and_ok_status(run_dir):
    (run_dir / "delivery.json").write_text(
        json.dumps({
            "role1_senior_structural_engineer": ["alice"],
            "role2_transport_major_projects_manager": ["dave"],
        }),
        encoding="utf-8",
    )
    result = sc.compute_scorecard(run_dir, labels_path=Path("/does/not/exist.jsonl"), spend_eur=0.0)
    lines = sc.render_table(result)
    text = "\n".join(lines)
    assert "n/a (no labels)" in text
    assert "SHIP: OK" in text


def test_render_table_shows_blocked_and_reasons(run_dir):
    result = sc.compute_scorecard(run_dir, labels_path=FIXTURE_LABELS_MIXED, spend_eur=0.0)
    lines = sc.render_table(result)
    text = "\n".join(lines)
    assert "SHIP: BLOCKED" in text
    assert "composition_violations" in text


def test_label_to_extractor_country_mapping_is_total():
    """Every value the labelling prompt can produce must map somewhere --
    a KeyError here would mean a label the prompt allows crashes the
    scorecard."""
    from gtm_client_workflows.gaia_sourcing.eval.labels import LOCATION_VALUES

    for value in LOCATION_VALUES:
        assert value in sc.LABEL_TO_EXTRACTOR_COUNTRY
