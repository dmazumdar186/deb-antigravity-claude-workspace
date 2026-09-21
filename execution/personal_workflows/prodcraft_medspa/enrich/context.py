"""
context.py
description: Shared StepContext/StepResult dataclasses threaded through every enrichment waterfall step.
inputs: N/A (imported by waterfall.py and each step module — not runnable on its own).
outputs: dataclass definitions only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from execution.personal_workflows.prodcraft_medspa.common.config import Settings


@dataclass
class StepContext:
    """Per-business mutable state, threaded through the waterfall so a later step can use a name
    or domain an earlier step found. `domain` is computed once by the waterfall from the business's
    website_url/final_url; `owner_name`/`owner_first`/`generic_email` accumulate as steps run."""

    mock: bool
    fixtures_root: Path
    settings: Settings
    session: requests.Session
    domain: str | None = None
    owner_name: str | None = None
    owner_first: str | None = None
    generic_email: str | None = None


@dataclass
class StepResult:
    """One waterfall step's outcome. `hit=True` requires a non-empty `email` — a step that only finds
    a name (e.g. state_registry) reports hit=False but still writes its finding into StepContext."""

    hit: bool
    source: str | None = None
    owner_name: str | None = None
    owner_first: str | None = None
    email: str | None = None
    evidence: str = ""
    cost_usd: float = 0.0
