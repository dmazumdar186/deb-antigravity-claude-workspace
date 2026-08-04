"""
Unit tests for generate.py — hash cache, cost estimation, spend log parsing.
No network. Runs in CI.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))

import generate  # noqa: E402


def test_asset_hash_stable():
    a = generate._asset_hash("a hummingbird", "veo3_1_lite", "video", 4, "9:16")
    b = generate._asset_hash("a hummingbird", "veo3_1_lite", "video", 4, "9:16")
    assert a == b


def test_asset_hash_differs_by_prompt():
    a = generate._asset_hash("a hummingbird", "veo3_1_lite", "video", 4, "9:16")
    b = generate._asset_hash("a cat", "veo3_1_lite", "video", 4, "9:16")
    assert a != b


def test_estimate_cost_eur_zero_for_hf_space():
    plan = [{"kind": "video", "duration_seconds": 4}]
    assert generate._estimate_cost_eur(plan, "hf_space_free", 3) == 0.0


def test_estimate_cost_eur_scales_with_candidates():
    plan = [{"kind": "video", "duration_seconds": 4}]
    c1 = generate._estimate_cost_eur(plan, "veo3_1_lite", 1)
    c3 = generate._estimate_cost_eur(plan, "veo3_1_lite", 3)
    assert c3 == round(c1 * 3, 4)


def test_read_today_spend_empty_log(tmp_path):
    assert generate._read_today_spend_eur(tmp_path / "spend.jsonl", "my_slug") == 0.0


def test_read_today_spend_counts_matching_entries(tmp_path):
    log = tmp_path / "spend.jsonl"
    today = datetime.now(timezone.utc).isoformat()
    entries = [
        {"ts": today, "slug": "my_slug", "cost_eur": 0.5},
        {"ts": today, "slug": "my_slug", "cost_eur": 0.25},
        {"ts": today, "slug": "other_slug", "cost_eur": 10.0},  # not counted
        {"ts": "1999-01-01T00:00:00Z", "slug": "my_slug", "cost_eur": 99.0},  # not today
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    assert generate._read_today_spend_eur(log, "my_slug") == 0.75


def test_read_today_spend_skips_malformed(tmp_path):
    log = tmp_path / "spend.jsonl"
    today = datetime.now(timezone.utc).isoformat()
    log.write_text(
        f'{{"ts":"{today}","slug":"s","cost_eur":1.0}}\n'
        "not json\n"
        f'{{"ts":"{today}","slug":"s","cost_eur":2.0}}\n',
        encoding="utf-8",
    )
    assert generate._read_today_spend_eur(log, "s") == 3.0


def test_model_cost_table_has_free_tier_escape_hatch():
    # veo3_1_lite is our documented free-tier escape hatch — must stay listed.
    assert "veo3_1_lite" in generate.MODEL_COST_EUR
    assert "hf_space_free" in generate.MODEL_COST_EUR
