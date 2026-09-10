"""
publish.py
description: Talks to the preview/worker Cloudflare Worker's control-plane API — POST /api/publish,
    POST /api/extend, GET /api/meta, plus a takedown() helper that POSTs the Worker's public /remove
    endpoint (see "Honest gaps" in this module's header comment below re: /api/publish's takedown field).
    Also the CLI entry point for `preview.extend` (see module note).
inputs: Imported by build_preview.py/takedown.py: publish()/extend()/get_meta()/takedown(). Standalone CLI:
    `python3 -m ...preview.publish extend --preview-id ID --days 30 [--mock] [--store ...]` (see note below).
outputs: HTTPS POST/GET to the Worker (live) or JSON files under .tmp/prodcraft_medspa/kv/{host}.json (mock).

Env: PREVIEW_PUBLISH_SECRET — bearer token for /api/publish, /api/extend, /api/meta. Must equal the Worker's
own REMOVE_WEBHOOK_SECRET (see preview/worker/README.md "wrangler secret put REMOVE_WEBHOOK_SECRET"); the two
env var names differ because the Python side and the Worker were authored independently, but they must be
set to the same value.

NOTE on the CLI contract: the orchestrating agent's file list for this package is
`{__init__,build_preview,extract_services,content_lint,r2,publish,takedown}.py` — there is no `extend.py`.
The pipeline's documented CLI contract is `python3 -m ...preview.extend --preview-id ID --days 30`. Since a
separate `extend.py` module is out of scope here, the `extend` subcommand is exposed on THIS module's CLI
instead (`python3 -m ...preview.publish extend ...`). Flagged in the build report for whoever owns the CLI
contract to either add a 2-line `extend.py` wrapper that calls `publish.main(["extend", ...])`, or update the
documented invocation to `preview.publish extend`.

NOTE on takedown: preview/worker/src/index.ts's POST /api/publish only ever writes {takedown: false,
status: "active"} — it does not accept a `takedown` field. The Worker's actual programmatic takedown path is
POST https://{host}/remove (handleRemove in index.ts), which needs no bearer auth, deletes the R2 prefix
itself, flips KV meta to takedown, and (when Supabase env is set on the Worker) patches previews/businesses
directly. `takedown()` below calls that endpoint. takedown.py additionally calls r2.delete_prefix() directly
from the Python side so the R2 prefix is removed even if the Worker call fails or (in --mock) there is no
Worker running at all. See CONTRACTS.md / preview/worker/README.md for the endpoint set as built.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, http, models  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import Store, get_store  # noqa: E402

_SECRET_ENV = "PREVIEW_PUBLISH_SECRET"


def _base_url(host: str) -> str:
    return f"https://{host}"


def _kv_path(meta_dir: Path, host: str) -> Path:
    meta_dir.mkdir(parents=True, exist_ok=True)
    return meta_dir / f"{host}.json"


def _mock_read_kv(meta_dir: Path, host: str) -> dict | None:
    path = _kv_path(meta_dir, host)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mock_write_kv(meta_dir: Path, host: str, meta: dict) -> dict:
    path = _kv_path(meta_dir, host)
    path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta


def _secret(explicit: str | None) -> str:
    secret = explicit or os.environ.get(_SECRET_ENV)
    if not secret:
        raise RuntimeError(f"{_SECRET_ENV} is not set (required for a live publish/extend/meta call)")
    return secret


def publish(
    host: str,
    expires_at: str,
    business_id: str,
    preview_id: str,
    *,
    mock: bool = False,
    secret: str | None = None,
    meta_dir: Path | None = None,
) -> dict:
    """POST /api/publish — arms `host` in the Worker's KV so it starts serving the just-uploaded R2 prefix."""
    payload = {"host": host, "expires_at": expires_at, "business_id": business_id, "preview_id": preview_id}
    if mock:
        meta = {**payload, "takedown": False, "status": "active"}
        return {"ok": True, "meta": _mock_write_kv(meta_dir or Path(".tmp/prodcraft_medspa/kv"), host, meta)}
    resp = http.post(
        f"{_base_url(host)}/api/publish",
        json=payload,
        headers={"Authorization": f"Bearer {_secret(secret)}"},
    )
    resp.raise_for_status()
    return resp.json()


def extend(
    host: str,
    expires_at: str,
    *,
    mock: bool = False,
    secret: str | None = None,
    meta_dir: Path | None = None,
) -> dict:
    """POST /api/extend — renews `expires_at` and clears any expired status."""
    if mock:
        meta_dir = meta_dir or Path(".tmp/prodcraft_medspa/kv")
        existing = _mock_read_kv(meta_dir, host) or {}
        updated = {**existing, "expires_at": expires_at, "takedown": False, "status": "active"}
        return {"ok": True, "meta": _mock_write_kv(meta_dir, host, updated)}
    resp = http.post(
        f"{_base_url(host)}/api/extend",
        json={"host": host, "expires_at": expires_at},
        headers={"Authorization": f"Bearer {_secret(secret)}"},
    )
    resp.raise_for_status()
    return resp.json()


def get_meta(host: str, *, mock: bool = False, secret: str | None = None, meta_dir: Path | None = None) -> dict | None:
    """GET /api/meta?host= — reads back the Worker's current KV record for `host`."""
    if mock:
        return _mock_read_kv(meta_dir or Path(".tmp/prodcraft_medspa/kv"), host)
    resp = http.get(
        f"{_base_url(host)}/api/meta",
        params={"host": host},
        headers={"Authorization": f"Bearer {_secret(secret)}"},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def takedown(host: str, *, mock: bool = False, meta_dir: Path | None = None) -> dict:
    """POST /remove — the Worker's public takedown endpoint (no bearer auth; see module docstring)."""
    if mock:
        meta_dir = meta_dir or Path(".tmp/prodcraft_medspa/kv")
        existing = _mock_read_kv(meta_dir, host) or {}
        updated = {
            **existing,
            "takedown": True,
            "takedown_at": models.now_iso(),
            "status": "takedown",
        }
        return {"ok": True, "meta": _mock_write_kv(meta_dir, host, updated)}
    resp = http.post(f"{_base_url(host)}/remove", data={})
    resp.raise_for_status()
    return {"ok": True, "status_code": resp.status_code}


# ---------------------------------------------------------------------------
# CLI — carries the `extend` subcommand documented as `preview.extend` (see module docstring NOTE).
# ---------------------------------------------------------------------------


def _find_preview(store: Store, preview_id: str) -> dict | None:
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore, SupabaseStore

    if isinstance(store, LocalStore):
        for row in store._read("previews"):  # noqa: SLF001 — Store protocol has no by-id preview lookup
            if row.get("id") == preview_id:
                return row
        return None
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", f"previews?id=eq.{preview_id}", headers=store._headers())  # noqa: SLF001
        data = resp.json()
        return data[0] if data else None
    return None


def _cmd_extend(args: argparse.Namespace) -> dict:
    settings = config.bootstrap()
    store = get_store(kind=args.store, root=args.store_root)
    preview = _find_preview(store, args.preview_id)
    if preview is None:
        raise SystemExit(f"preview not found: {args.preview_id}")

    new_expires = (date.today() + timedelta(days=args.days)).isoformat()
    host = preview["subdomain_url"].split("//", 1)[-1].split("/", 1)[0]
    meta_dir = settings.TMP / "kv"

    extend(host, new_expires, mock=args.mock, meta_dir=meta_dir)
    updated = store.update_preview(args.preview_id, {"expires_at": new_expires, "status": "active"})
    store.log_event("preview", args.preview_id, "extended", {"days": args.days, "expires_at": new_expires})
    return {"script": "publish.extend", "preview_id": args.preview_id, "expires_at": new_expires, "status": updated.get("status")}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    p_extend = sub.add_parser("extend", help="Extend a preview's expires_at by N days (documented as preview.extend)")
    p_extend.add_argument("--preview-id", required=True)
    p_extend.add_argument("--days", type=int, default=30)
    p_extend.add_argument("--mock", action="store_true")
    p_extend.add_argument("--store", choices=["local", "supabase"], default=None)
    p_extend.add_argument("--store-root", default=None)

    args = parser.parse_args(argv)

    if args.action == "extend":
        try:
            result = _cmd_extend(args)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 — top-level CLI failure, reported then re-raised as exit 1
            from execution.personal_workflows.prodcraft_medspa.common import notify

            notify.error("preview.publish.extend", str(exc))
            print(json.dumps({"script": "publish.extend", "error": str(exc)}))
            sys.exit(1)
        print(json.dumps(result))
        return


if __name__ == "__main__":
    main()
