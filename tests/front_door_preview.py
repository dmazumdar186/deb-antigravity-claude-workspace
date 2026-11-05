#!/usr/bin/env python3
"""Front-door synthetic for the prodcraft-preview-host Worker
(execution/personal_workflows/prodcraft_medspa/preview/worker).

Offline by default. Live: SITE_URL=https://<slug>-<suffix>.preview.prodcraft.fyi \
    python3 tests/front_door_preview.py --live
Read-only: GET /robots.txt only (served on any preview host; no R2/KV write).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _front_door_probe import main  # noqa: E402

CHECKS = [
    {"method": "GET", "path": "/robots.txt", "expect_status": 200, "expect_body": "Disallow: /"},
]

if __name__ == "__main__":
    sys.exit(main("preview", "", CHECKS))
