"""
Workspace-wide test fixtures for gaia_sourcing.

`core.providers.call_role` and `core.ocr`'s Anthropic transcription path now
append every successful paid call to a PERSISTENT, never-rotated ledger
(`logs/spend_ledger.jsonl`) used to enforce a cumulative, cross-run cost
ceiling (RunConfig.max_cost_eur_total). Without redirecting that path in
tests, the test suite itself would append fabricated spend (some tests
deliberately simulate very large per-call costs) into the REAL ledger file
under this package's own `logs/` directory -- permanently poisoning
`cumulative_spend_eur()` for any actual future run, and worse, doing so a
little more on every test invocation forever.

This autouse fixture redirects `providers.LEDGER_PATH` to a fresh, empty
per-test tmp_path location, so every test starts with cumulative spend at
zero unless it deliberately writes to the ledger itself (e.g. to test
accumulation across two simulated "runs").
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_spend_ledger(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.core import providers

    monkeypatch.setattr(providers, "LEDGER_PATH", tmp_path / "spend_ledger.jsonl")
    yield
