#!/usr/bin/env python3
"""Front-door synthetic for the greenjobs-ask Worker
(execution/gtm_client_workflows/greenjobs_redesign/worker).

Offline by default. Live: SITE_URL=<worker url> python3 tests/front_door_greenjobs_redesign.py --live
Read-only: CORS preflight + the 404 route hint; never POSTs /ask, so no LLM spend.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _front_door_probe import main  # noqa: E402

CHECKS = [
    {"method": "OPTIONS", "path": "/ask", "expect_status": 204},
    {"method": "GET", "path": "/", "expect_status": 404, "expect_body": "POST /ask"},
]

if __name__ == "__main__":
    sys.exit(main("greenjobs_redesign", "", CHECKS))
