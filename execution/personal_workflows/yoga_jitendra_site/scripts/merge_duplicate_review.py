"""Merge the duplicate "Vivi E" / "Virginie E" review in the live reviews KV (one-off, 2026-11-03).

description: The same Google review exists twice in DASHBOARD_KV: the Google-synced record
             (name "Vivi E", key ...612640Z:AbFvOqnQ) and an earlier hand-moderated copy
             ("Virginie E", key ...097Z:59cdf544). The cron's content dedup misses it because the
             first names differ. This keeps the Google record (so the daily sync matches it by key),
             copies the moderated name/text/link/featured flag into it, stamps `edited_at` (the sync
             then skips it as a newer local edit), and deletes the hand copy.
inputs:  env CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID. Flags: (none) = dry run, --apply = write.
outputs: prints the plan; with --apply writes 1 key and deletes 1 key. Backups of both records are
         written to .tmp/kv_backup_<date>/ before any write. Rollback: PUT both backup files back.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

NS = "4cdf5cdb6fc14db3b29edcab6c464714"
KEEP = "review:approved:2026-07-14T15:10:37.612640Z:AbFvOqnQ"
DROP = "review:approved:2026-07-24T14:40:07.097Z:59cdf544"


def _req(method: str, key: str, token: str, account: str, body: bytes | None = None) -> bytes:
    url = (f"https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{NS}/values/"
           + urllib.parse.quote(key, safe=""))
    req = urllib.request.Request(url, data=body, method=method, headers={"Authorization": f"Bearer {token}"})
    if body is not None:
        req.add_header("Content-Type", "text/plain")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    token, account = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        print("ERROR: set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID", file=sys.stderr)
        return 2
    apply = "--apply" in sys.argv
    try:
        keep = json.loads(_req("GET", KEEP, token, account))
    except urllib.error.HTTPError as exc:
        print(f"ERROR: cannot read {KEEP}: HTTP {exc.code}", file=sys.stderr)
        return 1
    try:
        drop = json.loads(_req("GET", DROP, token, account))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("Nothing to do: the duplicate is already gone.")
            return 0
        print(f"ERROR: cannot read {DROP}: HTTP {exc.code}", file=sys.stderr)
        return 1
    backup = pathlib.Path(__file__).resolve().parents[4] / ".tmp" / f"kv_backup_{datetime.date.today()}"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "keep_before.json").write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    (backup / "drop_before.json").write_text(json.dumps(drop, ensure_ascii=False), encoding="utf-8")
    merged = dict(keep)
    merged.update(name=drop["name"], body=drop["body"], body_fr=drop["body"],
                  featured=bool(drop.get("featured")), source_url=drop.get("source_url"),
                  edited_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                  dedup_note="2026-11-03: merged moderated duplicate 59cdf544 into this Google record")
    print(f"Plan: update {KEEP} -> name={merged['name']!r}, featured={merged['featured']}; delete {DROP}.")
    print(f"Backups: {backup}")
    if not apply:
        print("DRY RUN: nothing changed. Re-run with --apply.")
        return 0
    try:
        _req("PUT", KEEP, token, account, json.dumps(merged, ensure_ascii=False).encode("utf-8"))
        _req("DELETE", DROP, token, account)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: write failed: HTTP {exc.code} (backups kept in {backup})", file=sys.stderr)
        return 1
    print("Done: 1 record updated, 1 duplicate deleted. The public reviews list updates immediately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
