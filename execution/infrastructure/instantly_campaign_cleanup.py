"""
instantly_campaign_cleanup -- strip a campaign down to a verified-safe allowlist,
blocklist already-bounced domains, and optionally resume it.

purpose: Recovery path after Bounce Protect pauses a campaign because the lead
         CSV was uploaded without filtering on its own verification columns
         (status / is_safe_to_send / is_catch_all). Deletes every campaign lead
         whose email is not on a "safe" allowlist, blocklists bounced domains,
         then (with --resume) re-activates the campaign.

inputs:  CLI: campaign_id (positional)
              --keep-csv PATH (required; `Email` column = allowlist, case-insensitive)
              --bounces-csv PATH (optional; Instantly bounce export, `Lead` column)
              --also-remove PATH (optional; one email per line, extra deletions)
              --resume (activate after cleanup)
              --no-dry-run (default is DRY RUN: counts only, no writes)
              --api-key-env / --env-file (same semantics as instantly_guard)
              --out PATH (optional JSON summary file)

outputs: JSON summary on stdout (+ --out), one human line on stderr.
         Exit 0 success, 1 API failure, 2 bad args.

notes:   Leads that replied (truthy reply_count) or show positive interest
         (lt_interest_status > 0) are never deleted; the count is reported as
         `spared_replied`. Leads with no `email` field are never deleted.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from instantly_guard import (  # noqa: E402
    Instantly,
    chunked,
    domain_of,
    resolve_api_key,
)

BULK_DELETE_MAX = 100
BLOCKLIST_MAX = 1000


def read_csv_column(path: Path, column: str) -> set[str]:
    """Return lowercased, non-empty values of `column` (header match is case-insensitive)."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = {(f or "").strip().lower(): f for f in (reader.fieldnames or [])}
        key = fields.get(column.lower())
        if key is None:
            raise ValueError(f"{path}: missing column '{column}'")
        return {(row.get(key) or "").strip().lower() for row in reader} - {""}


def read_lines(path: Path) -> set[str]:
    return {ln.strip().lower() for ln in path.read_text(encoding="utf-8").splitlines()} - {""}


def is_engaged(lead: dict) -> bool:
    """True if the lead replied or shows positive interest -- never delete these."""
    if lead.get("reply_count"):
        return True
    interest = lead.get("lt_interest_status")
    try:
        return interest is not None and int(interest) > 0
    except (TypeError, ValueError):
        return False


def select_deletions(leads: list[dict], keep: set[str],
                     also_remove: set[str]) -> tuple[list[dict], int]:
    """Return (leads to delete, count spared because engaged)."""
    doomed: list[dict] = []
    spared = 0
    for lead in leads:
        email = (lead.get("email") or "").strip().lower()
        if not email:
            continue
        if email in keep and email not in also_remove:
            continue
        if is_engaged(lead):
            spared += 1
            continue
        doomed.append(lead)
    return doomed, spared


def bounced_domains(bounced: set[str]) -> list[str]:
    return sorted({d for d in (domain_of(e) for e in bounced) if d})


def run(args: argparse.Namespace) -> dict:
    dry = not args.no_dry_run
    keep = read_csv_column(args.keep_csv, "Email")
    bounced = read_csv_column(args.bounces_csv, "Lead") if args.bounces_csv else set()
    extra = read_lines(args.also_remove) if args.also_remove else set()

    api = Instantly(resolve_api_key(args.api_key_env, args.env_file))
    leads = api.list_leads(args.campaign_id)
    doomed, spared = select_deletions(leads, keep, extra)

    domains = bounced_domains(bounced)
    present = api.already_blocklisted(domains) if domains else set()
    to_block = [d for d in domains if d not in present]

    summary: dict = {
        "campaign_id": args.campaign_id, "dry_run": dry,
        "allowlist_size": len(keep), "campaign_leads": len(leads),
        "spared_replied": spared, "bounced_domains": len(domains),
        "already_blocklisted": len(present),
    }
    if dry:
        summary.update(would_delete=len(doomed), would_blocklist=len(to_block),
                       would_resume=bool(args.resume))
        summary["api_calls"] = api.calls
        return summary

    deleted = 0
    ids = [lead["id"] for lead in doomed if lead.get("id")]
    for batch in chunked(ids, BULK_DELETE_MAX):
        payload = api.expect("DELETE", "/leads", {"campaign_id": args.campaign_id, "ids": batch})
        deleted += int(payload.get("count") or 0)
    blocked = 0
    for batch in chunked(to_block, BLOCKLIST_MAX):
        api.expect("POST", "/block-lists-entries/bulk-create", {"bl_values": batch})
        blocked += len(batch)
    summary.update(deleted=deleted, blocklisted=blocked)
    if args.resume:
        api.expect("POST", f"/campaigns/{args.campaign_id}/activate", {})
        summary["campaign_status"] = api.expect("GET", f"/campaigns/{args.campaign_id}").get("status")
    summary["api_calls"] = api.calls
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    p.add_argument("campaign_id")
    p.add_argument("--keep-csv", type=Path, required=True)
    p.add_argument("--bounces-csv", type=Path)
    p.add_argument("--also-remove", type=Path)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--no-dry-run", action="store_true")
    p.add_argument("--api-key-env", default="INSTANTLY_NOTIFIER_API_KEY")
    p.add_argument("--env-file", type=Path, default=Path("./.env"))
    p.add_argument("--out", type=Path)
    return p


def main() -> int:
    args = build_parser().parse_args()  # argparse exits 2 on bad args
    for path in (args.keep_csv, args.bounces_csv, args.also_remove):
        if path is not None and not path.is_file():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
    try:
        summary = run(args)
    except (ValueError, UnicodeDecodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:  # Instantly.expect / resolve_api_key raise FATAL
        print(str(exc), file=sys.stderr)
        return 1
    text = json.dumps(summary, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if summary["dry_run"]:
        human = (f"DRY RUN: would delete {summary['would_delete']}, blocklist "
                 f"{summary['would_blocklist']}, resume={summary['would_resume']}")
    else:
        human = (f"deleted {summary['deleted']}, blocklisted {summary['blocklisted']}, "
                 f"status={summary.get('campaign_status', 'unchanged')}")
    print(f"{human} (spared {summary['spared_replied']} engaged)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
