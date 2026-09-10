"""
sample_audit.py
description: Audit a random seeded sample of businesses in a metro; record a metro_stats row with a Wilson CI.
inputs: --metro X --n 40 [--mock] [--seed 42] [--store ...] [--store-root PATH] [--skip-vision] [--skip-screenshots]
outputs: One `audits` row per sampled business, one `metro_stats` row, stdout stat line + the metro_stats row.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.audit import audit_site, scoring  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.audit.stats import wilson  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common import config, store  # noqa: E402

MAX_WORKERS = 4


def main() -> None:
    """description: Audit a random n-sized sample of a metro's businesses and record metro_stats.
    inputs: --metro X --n 40 [--mock] [--seed 42] [--store ...] [--store-root PATH] [--skip-vision] [--skip-screenshots]
    outputs: audits rows, one metro_stats row, stdout stat line.
    """
    parser = argparse.ArgumentParser(description="Audit-only random sample of a metro to measure % qualified")
    parser.add_argument("--metro", required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-screenshots", action="store_true")
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = args.store or ("local" if args.mock else settings.store_kind)
    st = store.get_store(kind=store_kind, root=args.store_root)

    eligible = st.find_businesses(metro=args.metro, is_chain=False, drop_reason_is_null=True)
    # Sort on place_id (stable/deterministic across stores) rather than `id` (a random uuid4
    # minted at insert time) so the same --seed reproduces the same sample across runs/stores.
    eligible.sort(key=lambda b: b.get("place_id") or b["id"])

    rng = random.Random(args.seed)
    sample = eligible[:]
    rng.shuffle(sample)
    sample = sample[: args.n]

    mock_map = audit_site._load_mock_map() if args.mock else None  # noqa: SLF001 — internal reuse, same package

    qualified = 0
    audited = 0
    errors = 0
    llm_cost_usd = 0.0
    lock = threading.Lock()

    def _run(business: dict) -> None:
        nonlocal qualified, audited, errors, llm_cost_usd
        audit_row, error = audit_site.audit_one_business(
            business,
            settings=settings,
            mock=args.mock,
            mock_map=mock_map,
            skip_vision=args.skip_vision,
            skip_screenshots=args.skip_screenshots,
            store_kind=store_kind,
        )
        with lock:
            if error:
                errors += 1
            st.insert_audit(audit_row)
            st.log_event("business", business["id"], "sample_audited", {"bucket": audit_row.get("bucket")})
            audited += 1
            if audit_row.get("bucket") == "qualified":
                qualified += 1
            llm_cost_usd += audit_row.get("llm_cost_usd", 0.0)

    if sample:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(_run, b) for b in sample]
            for future in as_completed(futures):
                future.result()

    pct_qualified, ci_low, ci_high = wilson(qualified, audited)

    metro_stats_row = {
        "metro": args.metro,
        "sampled": audited,
        "qualified": qualified,
        "pct_qualified": round(pct_qualified, 2),
        "ci_low": round(ci_low, 2),
        "ci_high": round(ci_high, 2),
        "score_version": scoring.SCORE_VERSION,
    }
    saved = st.insert_metro_stats(metro_stats_row)

    stats = {
        "script": "sample_audit",
        "metro": args.metro,
        "in": len(eligible),
        "sampled": audited,
        "qualified": qualified,
        "errors": errors,
        "llm_cost_usd": round(llm_cost_usd, 6),
    }
    print(json.dumps(stats))
    print(json.dumps(saved, default=str))


if __name__ == "__main__":
    main()
