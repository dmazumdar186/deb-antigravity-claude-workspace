#!/usr/bin/env python3
"""Front-door synthetic for the med-spa dashboard Pages project
(execution/personal_workflows/prodcraft_medspa/dashboard).

Offline by default. Live: python3 tests/front_door_prodcraft_medspa.py --live [--url SITE_URL]
Read-only: an unauthenticated GET must be refused with Basic Auth (no credentials sent).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _front_door_probe import main  # noqa: E402

CHECKS = [
    {"method": "GET", "path": "/", "expect_status": 401, "expect_header": "WWW-Authenticate"},
]

if __name__ == "__main__":
    sys.exit(main("prodcraft_medspa", "https://prodcraft-medspa-dashboard.pages.dev", CHECKS))
