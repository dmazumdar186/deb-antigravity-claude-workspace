"""
conftest.py
description: Shared pytest fixtures for the ProdCraft med-spa test suite.
inputs: N/A (pytest fixtures, auto-discovered).
outputs: tmp_path-scoped LocalStore instances; skip marker for Supabase-dependent tests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore  # noqa: E402

PKG_ROOT = REPO_ROOT / "execution" / "personal_workflows" / "prodcraft_medspa"


@pytest.fixture
def local_store(tmp_path) -> LocalStore:
    return LocalStore(root=tmp_path / "store")


@pytest.fixture
def fixtures_root() -> Path:
    return PKG_ROOT / "fixtures"


def supabase_available() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


skip_without_supabase = pytest.mark.skipif(
    not supabase_available(), reason="SUPABASE_URL/SUPABASE_SERVICE_KEY not set"
)
