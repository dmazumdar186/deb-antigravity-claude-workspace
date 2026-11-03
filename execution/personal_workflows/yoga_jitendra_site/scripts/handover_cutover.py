"""Hand the yogaavecjitendra.fr domain over to the client's own Cloudflare Pages project.

description: Detach yogaavecjitendra.fr from the operator's Pages project and stop its deploys (handover cutover)
inputs: --status | --apply (default dry run); env CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
outputs: stdout status/plan; with --apply, Cloudflare API DELETE domains + PATCH project source config

Run on the OPERATOR's Cloudflare account (project ``yoga-jitendra``), during the
handover screen-share, after the client's zone is Active and BEFORE he adds the
custom domains to his own Pages project. See the handover branch's
HANDOVER_SETUP.md and directives/personal_workflows/yoga_jitendra_site.md.

Modes:
  (default)  dry run: print what --apply would change, change nothing
  --status   print the project's current custom domains and deploy flags
  --apply    (a) remove yogaavecjitendra.fr + www.yogaavecjitendra.fr from the
             project, (b) stop workspace pushes from deploying (production
             deployments off, preview deployments "none")

Env: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID. Stdlib only (Python 3.11+).
Exit codes: 0 ok, 1 API/network failure, 2 missing configuration.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.cloudflare.com/client/v4"
PROJECT = "yoga-jitendra"
DOMAINS = ("yogaavecjitendra.fr", "www.yogaavecjitendra.fr")
TIMEOUT_S = 30


class CloudflareError(RuntimeError):
    """Raised when the Cloudflare API call fails or returns success=false."""


def _call(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise CloudflareError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CloudflareError(f"{method} {path} -> network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CloudflareError(f"{method} {path} -> non-JSON response") from exc
    if not payload.get("success", False):
        raise CloudflareError(f"{method} {path} -> API errors: {payload.get('errors')}")
    return payload.get("result")


def _project_path(account: str) -> str:
    return f"/accounts/{account}/pages/projects/{PROJECT}"


def get_state(account: str, token: str) -> tuple[dict[str, Any], list[str]]:
    project = _call("GET", _project_path(account), token)
    domains = _call("GET", _project_path(account) + "/domains", token) or []
    names = [d.get("name", "") for d in domains]
    return project, names


def print_status(project: dict[str, Any], domains: list[str]) -> None:
    cfg = (project.get("source") or {}).get("config") or {}
    print(f"Project: {PROJECT}")
    print(f"  custom domains: {', '.join(domains) or '(none)'}")
    print(f"  repo: {cfg.get('owner')}/{cfg.get('repo_name')} branch {cfg.get('production_branch')}")
    print(f"  production_deployments_enabled: {cfg.get('production_deployments_enabled')}")
    print(f"  preview_deployment_setting: {cfg.get('preview_deployment_setting')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="make the changes")
    mode.add_argument("--status", action="store_true", help="show current state only")
    args = parser.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token or not account:
        print("ERROR: set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID", file=sys.stderr)
        return 2

    try:
        project, domains = get_state(account, token)
        print_status(project, domains)
        if args.status:
            return 0

        source = project.get("source") or {}
        cfg = dict(source.get("config") or {})
        to_remove = [d for d in DOMAINS if d in domains]
        needs_patch = cfg.get("production_deployments_enabled") is not False or cfg.get(
            "preview_deployment_setting"
        ) != "none"

        print("\nPlan:")
        for d in to_remove:
            print(f"  - remove custom domain {d}")
        if needs_patch:
            print("  - set production_deployments_enabled=false, preview_deployment_setting=none")
        if not to_remove and not needs_patch:
            print("  nothing to do (already cut over)")
            return 0
        if needs_patch and not source:
            raise CloudflareError("project has no git source; refusing to PATCH a fabricated source config")
        if not args.apply:
            print("\nDRY RUN: nothing changed. Re-run with --apply to execute.")
            return 0

        for d in to_remove:
            _call("DELETE", f"{_project_path(account)}/domains/{urllib.parse.quote(d)}", token)
            print(f"  removed {d}")
        if needs_patch:
            cfg["production_deployments_enabled"] = False
            cfg["preview_deployment_setting"] = "none"
            _call("PATCH", _project_path(account), token, {"source": {"type": source.get("type", "github"), "config": cfg}})
            print("  deploys disabled")
        print("\nAfter:")
        print_status(*get_state(account, token))
    except CloudflareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
