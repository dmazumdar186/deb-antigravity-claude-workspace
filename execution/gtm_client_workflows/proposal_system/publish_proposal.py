"""
publish_proposal.py
description: Upload a built proposal HTML to the proposal-tracker Worker (KV) and print the tracked URL, or list its opens.
inputs: <slug> (proposals/<slug>.json must have been built); env PROPOSAL_WORKER_URL, PROPOSAL_PUBLISH_SECRET.
outputs: Tracked URL + pixel URL on stdout; --opens prints the open log as JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--opens", action="store_true", help="print the open log instead of publishing")
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()

    base = os.environ.get("PROPOSAL_WORKER_URL", "").rstrip("/")
    secret = os.environ.get("PROPOSAL_PUBLISH_SECRET", "")
    if not base or not secret:
        print("Set PROPOSAL_WORKER_URL and PROPOSAL_PUBLISH_SECRET (see worker/wrangler.toml).", file=sys.stderr)
        return 2
    h = {"x-publish-secret": secret}
    if a.opens:
        r = requests.get(f"{base}/opens/{a.slug}", headers=h, timeout=20)
    elif a.delete:
        r = requests.delete(f"{base}/publish/{a.slug}", headers=h, timeout=20)
    else:
        html_path = HERE / "out" / a.slug / f"{a.slug}.html"
        if not html_path.exists():
            print(f"missing {html_path}; run build_proposal.py first", file=sys.stderr)
            return 2
        r = requests.put(f"{base}/publish/{a.slug}", headers={**h, "content-type": "text/html"},
                         data=html_path.read_bytes(), timeout=30)
    try:
        print(json.dumps(r.json(), indent=2))
    except ValueError:
        print(r.status_code, r.text[:500])
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
