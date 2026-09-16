"""
purge_pii.py
description: CLI wrapper over Store.purge_pii() (common/store.py) — blanks a business's PII
    (owner_name/owner_email/phone/email_source) and its outreach rows' PII-adjacent fields (Gmail
    ids, reply_* fields), keeping ids/statuses/do_not_contact/the funnel trail intact, stamps
    pii_purged_at, and logs a `pii_purged` event. See CONTRACTS.md "PII retention" for the policy
    this is the operator-run mechanism for (dnc: within 10 business days; closed_lost: after 180
    days — this script does not schedule itself, it just does one purge per invocation).
inputs: --business-id ID (required), --reason TEXT (required), --mock, --store {local,supabase},
    --store-root PATH.
outputs: Store mutation (see above) + one events row; stdout JSON stat line
    {"script":"purge_pii","business_id":...,"reason":...,"ok":bool}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import reject_mock_with_supabase  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--reason", required=True, help="Why this purge is happening (e.g. 'dnc 10-day retention', 'closed_lost 180-day retention')")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args(argv)

    store_kind = reject_mock_with_supabase(parser, args)  # --mock implies local; never supabase
    store = get_store(kind=store_kind, root=args.store_root)

    try:
        store.purge_pii(args.business_id, args.reason)
    except KeyError as exc:
        print(f"purge_pii failed: {exc}", file=sys.stderr)
        print(json.dumps({"script": "purge_pii", "business_id": args.business_id, "reason": args.reason, "ok": False}))
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        notify.error("prodcraft_medspa.purge_pii", f"{type(exc).__name__}: {exc}")
        raise

    print(json.dumps({"script": "purge_pii", "business_id": args.business_id, "reason": args.reason, "ok": True}))


if __name__ == "__main__":
    main()
