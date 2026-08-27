"""Model-tier guardrails (2026-08-27): no tier ladder may reach Haiku, and the
pinned fallbacks resolve to the 5-series judgement/execution split."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

from modules import model_registry as R  # noqa: E402
from modules import model_router as T  # noqa: E402


def test_no_family_ladder_contains_haiku():
    for name in dir(R):
        if name.startswith("_FAMILY_RANK"):
            assert "haiku" not in getattr(R, name), name


def test_offline_resolution_is_5_series_and_never_haiku():
    for prov, tier, expect in [
        ("anthropic", "premium", "claude-fable-5"),
        ("anthropic", "default", "claude-sonnet-5"),
        ("openrouter", "premium", "anthropic/claude-fable-5"),
        ("openrouter", "default", "anthropic/claude-sonnet-5"),
    ]:
        got = R.resolve_model(prov, tier, allow_network=False)
        assert got == expect, (prov, tier, got)
        assert "haiku" not in got


def test_router_aliases_all_known_to_registry():
    assert T.validate_against_registry() == []
