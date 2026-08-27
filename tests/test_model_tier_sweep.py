"""Pins the 2026-08-27 tier map in every hand-pinned literal the sweep touched.

The registry moved the judgement tier to claude-fable-5 in 6fa4357; these tests
exist because ~60 literals did NOT follow it, and nothing in the suite noticed.
Each assertion here fails on the pre-sweep tree and passes after it, so a
regression back to Opus (or a new script cloned from a stale template) is caught
by pytest rather than by the operator reading --help.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "execution"
sys.path.insert(0, str(EXEC))
sys.path.insert(0, str(EXEC / "gtm_client_workflows" / "gaia_sourcing"))

JUDGEMENT = "claude-fable-5"
EXECUTION = "claude-sonnet-5"


def _module_dict(path: Path, name: str) -> dict:
    """Read a module-level dict literal without importing the module (no side effects)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name and node.value is not None:
            return ast.literal_eval(node.value)  # `NAME: dict[str, str] = {...}`
    raise AssertionError(f"{name} not found in {path}")


@pytest.mark.parametrize("rel, key", [
    ("_TEMPLATE.py", "MODE_TO_MODEL"),
    ("_TEMPLATE_autoresearch.py", "MODE_TO_MUTATOR_MODEL"),
    ("templates/crm_integration/sync.py", "MODE_TO_MODEL"),
    ("personalization/ai_opener_generator.py", "MODE_TO_MODEL_ANTHROPIC"),
])
def test_premium_mode_is_the_judgement_tier(rel, key):
    d = _module_dict(EXEC / rel, key)
    assert d["premium"] == JUDGEMENT, (rel, d)
    assert d["balanced"] == EXECUTION, (rel, d)
    assert "haiku" not in " ".join(d.values())


@pytest.mark.parametrize("rel, key", [
    ("personalization/ai_opener_generator.py", "MODE_TO_MODEL_OPENROUTER"),
    ("personalization/variant_generator.py", "MODE_TO_MODEL"),
])
def test_premium_mode_openrouter_slug(rel, key):
    d = _module_dict(EXEC / rel, key)
    assert d["premium"] == "anthropic/" + JUDGEMENT, (rel, d)
    assert d["balanced"] == "anthropic/" + EXECUTION, (rel, d)


def test_humanizer_premium_cost_row_is_fable_pricing():
    d = _module_dict(EXEC / "content" / "humanizer.py", "_TIER_COST_PER_M")
    assert d["premium"] == {"input": 10.0, "cache_read": 1.0, "cache_write": 12.5, "output": 50.0}
    assert d["default"] == {"input": 2.0, "cache_read": 0.2, "cache_write": 2.5, "output": 10.0}


def test_gaia_roles_follow_the_tier_map():
    from core import config as GC, providers as GP  # noqa: PLC0415
    assert GC.MODEL_JUDGE == GC.MODEL_MESSAGE == JUDGEMENT
    # L10 is per-candidate rubric scoring: bulk execution (model-tier.md Exhibit D).
    assert GC.MODEL_MOVABILITY == GC.MODEL_EXTRACT == GC.MODEL_PARSE == EXECUTION
    for plan in ("hybrid", "openrouter", "anthropic"):
        for role in (GP.ROLE_JUDGE, GP.ROLE_MESSAGE):
            assert GP.PLANS[plan][role][1].endswith(JUDGEMENT), (plan, role)
        assert not GP.PLANS[plan][GP.ROLE_EXTRACT][1].endswith(JUDGEMENT), plan
    assert GP.ROUTING[GP.ROLE_JUDGE][1].endswith(JUDGEMENT)


def test_gaia_fable_pricing_in_eur():
    from core import config as GC, providers as GP  # noqa: PLC0415
    assert GC.PRICING[JUDGEMENT] == {"input": 10.00, "cache_write": 12.50, "cache_read": 1.00, "output": 50.00}
    one_m = 1_000_000
    assert GP.cost_eur(JUDGEMENT, {"input_tokens": one_m}) == pytest.approx(9.20)
    assert GP.cost_eur(JUDGEMENT, {"output_tokens": one_m}) == pytest.approx(46.00)
    assert GP.cost_eur(JUDGEMENT, {"cache_read_tokens": one_m}) == pytest.approx(0.92)
    assert GP.cost_eur(JUDGEMENT, {"cache_write_tokens": one_m}) == pytest.approx(11.50)


def test_registry_premium_is_fable_and_router_agrees():
    from modules import model_registry as R, model_router as T  # noqa: PLC0415
    assert R.LAST_KNOWN_GOOD["anthropic"]["premium"] == JUDGEMENT
    assert R.LAST_KNOWN_GOOD["anthropic"]["default"] == EXECUTION
    assert R.LAST_KNOWN_GOOD["openrouter"]["premium"] == "anthropic/" + JUDGEMENT
    assert T.validate_against_registry() == []


def test_youtube_analyzer_prices_fable_in_every_table():
    y = EXEC / "video" / "youtube_video_analyzer.py"
    flat = _module_dict(y, "_TIER_COST_PER_M_TOKENS")
    cache = _module_dict(y, "_CLAUDE_PRICES")
    assert flat[JUDGEMENT] == flat["anthropic/" + JUDGEMENT] == 10.00
    assert cache[JUDGEMENT] == {"input": 10.00, "cache_read": 1.00, "cache_write": 12.50, "output": 50.00}


def test_sonnet_rerank_prices_match_its_default_model():
    src = (EXEC / "personal_workflows" / "job_search_v2" / "ranker" / "sonnet_rerank.py").read_text(encoding="utf-8")
    assert 'DEFAULT_MODEL = "claude-sonnet-5"' in src
    assert "PRICE_INPUT_PER_M_USD = 2.0" in src and "PRICE_OUTPUT_PER_M_USD = 10.0" in src
