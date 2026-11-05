#!/usr/bin/env python3
"""Front-door synthetic for the proposal-tracker Worker
(execution/gtm_client_workflows/proposal_system/worker).

Offline by default. Live: python3 tests/front_door_proposal_system.py --live [--url SITE_URL]
Read-only: GET /health only; never opens /p/ or /o/, so no Telegram ping or KV log.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _front_door_probe import main  # noqa: E402

CHECKS = [
    {"method": "GET", "path": "/health", "expect_status": 200, "expect_body": '"ok":true'},
]

if __name__ == "__main__":
    sys.exit(main("proposal_system", "https://proposal-tracker.debanjan186.workers.dev", CHECKS))
