"""
preview_gate.py
description: Automated acceptance gate for `previews` rows sitting in status `review`. For every
    review-status, non-takedown preview whose business is in the given metro, runs the same
    Playwright acceptance checks as tests/prodcraft_medspa/acceptance_template.py against that
    preview's own built output (its `local_build_dir`, or an R2-exported copy pulled down first
    when the preview was published via R2), and records a `gate` event with the pass/fail result
    and reasons. Config `auto_approve_previews` (bool, default false, seeded in db/seed_config.json
    and validated by common/config_validate.py) controls what happens next:
      - false (default): only records the gate result. No preview's status changes. This is the
        safe, report-only mode — a human still approves in the dashboard
        (.claude/rules/automation-boundaries.md: the final creative asset is human-picked).
      - true (explicit operator opt-in): a *passing* preview is moved review -> approved through
        the exact same code path preview/approve.py's human-driven CLI uses
        (`preview.approve.approve_preview`), so the two paths can never diverge in what "approved"
        means. A *failing* preview stays in `review` and gets an extra `gate_failed` event; it is
        never auto-rejected, since a failing automated check can itself be wrong and a human should
        still get to look.
    Chromium is located via PLAYWRIGHT_BROWSERS_PATH (same convention as acceptance_template.py's
    `_chromium_executable()`), which the daily workflow now sets before running this script (round-2
    fixops item 1: `python -m playwright install --with-deps chromium`).
inputs: CLI: --metro X [--store {local,supabase}] [--store-root P] [--mock]. Env: whatever the
    acceptance-check reuse needs (PLAYWRIGHT_BROWSERS_PATH), config.auto_approve_previews via the
    store.
outputs: `events` rows (entity=preview, event="gate:pass"/"gate:fail", and "gate_failed" when a
    failing preview stays in review under auto_approve_previews=true); previews.status flips to
    `approved` (auto_approve_previews=true, passing gate only) via approve_preview(); stdout JSON
    stat line {"script":"preview_gate","in":n,"gated_pass":n,"gated_fail":n,"approved":n,
    "auto_approve_previews":bool,"dropped":{...}}.
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import Store, get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.preview.approve import (  # noqa: E402
    approve_preview,
    candidates_for_metro,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)


def _run_acceptance_checks(preview: dict, *, tmp_root: Path) -> tuple[bool, list[str]]:
    """Runs the acceptance_template.py checks against `preview`'s own built output.

    Returns (passed, reasons) — reasons is empty when passed is True. Never raises: any error
    getting to a runnable build (no local_build_dir, R2 download failure, Playwright/Chromium
    missing, etc.) counts as a failed gate with the error recorded as a reason, so one bad preview
    never crashes the whole run.

    This is a thin, monkeypatch-friendly seam: tests replace this function wholesale rather than
    mocking Playwright/Chromium internals.
    """
    build_dir_str = preview.get("local_build_dir")
    cleanup_dir: Path | None = None
    try:
        if build_dir_str:
            build_dir = Path(build_dir_str)
            if not build_dir.is_dir():
                return False, [f"local_build_dir does not exist: {build_dir_str}"]
        else:
            # publish_mode "r2": pull the built export down to a scratch dir so the same
            # acceptance_template.py logic (which serves a local directory over http.server) can
            # run against it.
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                from preview import r2  # type: ignore  # noqa: PLC0415 — another agent's package
            except ImportError as exc:
                return False, [f"cannot import preview/r2.py to fetch R2 export: {exc}"]

            settings = config.bootstrap()
            slug_prefix = (preview.get("subdomain_url") or "").replace("https://", "").split(".")[0]
            prefix = f"previews/{slug_prefix}"
            cleanup_dir = Path(tempfile.mkdtemp(prefix="preview_gate_", dir=str(tmp_root)))
            try:
                r2_client = r2.R2Client(
                    account_id=settings.CLOUDFLARE_ACCOUNT_ID or "",
                    access_key=settings.R2_ACCESS_KEY_ID or "",
                    secret_key=settings.R2_SECRET_ACCESS_KEY or "",
                    bucket=settings.R2_BUCKET or "prodcraft-previews",
                )
                keys = r2_client.list_objects(prefix)
                if not keys:
                    return False, [f"no objects found in R2 under prefix {prefix!r}"]
                for key in keys:
                    dest = cleanup_dir / Path(key).relative_to(prefix.rstrip("/")) if key.startswith(prefix) else cleanup_dir / Path(key).name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    r2_client.download_file(key, dest)  # type: ignore[attr-defined]
            except AttributeError:
                return False, ["preview/r2.py has no download_file/list_objects support yet — gate cannot fetch the R2 export"]
            except Exception as exc:  # noqa: BLE001 — report, never crash the whole gate run
                return False, [f"R2 download failed: {type(exc).__name__}: {exc}"]
            build_dir = cleanup_dir

        acceptance = importlib.import_module("tests.prodcraft_medspa.acceptance_template")
        original_out_dir = acceptance.OUT_DIR
        acceptance.OUT_DIR = build_dir
        try:
            acceptance.run()
        except SystemExit as exc:
            if exc.code:
                return False, [f"acceptance_template checks failed (exit {exc.code}) — see stderr above"]
            return True, []
        except Exception as exc:  # noqa: BLE001 — a gate crash is a fail, not an orchestrator crash
            return False, [f"acceptance run raised {type(exc).__name__}: {exc}"]
        finally:
            acceptance.OUT_DIR = original_out_dir
        return True, []
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def gate_preview(store: Store, preview: dict, *, auto_approve: bool, actor: str, tmp_root: Path) -> dict:
    """Runs the acceptance gate for one preview and applies the auto-approve policy.

    Returns {"preview_id", "passed", "reasons", "approved" (bool)}. Never raises.
    """
    passed, reasons = _run_acceptance_checks(preview, tmp_root=tmp_root)
    store.log_event(
        "preview",
        preview["id"],
        f"gate:{'pass' if passed else 'fail'}",
        {"actor": actor, "reasons": reasons},
    )
    approved = False
    if passed and auto_approve:
        drop_reason = approve_preview(store, preview, actor=actor)
        approved = drop_reason is None
        if not approved:
            # approve_preview() already reasoned about eligibility (takedown/do_not_contact/status);
            # surface that as a gate-adjacent event too so it isn't silently invisible in the log.
            store.log_event("preview", preview["id"], "gate_approve_skipped", {"actor": actor, "reason": drop_reason})
    elif not passed:
        store.log_event("preview", preview["id"], "gate_failed", {"actor": actor, "reasons": reasons})
    return {"preview_id": preview["id"], "passed": passed, "reasons": reasons, "approved": approved}


def run(store: Store, *, metro: str, actor: str = "preview_gate") -> dict:
    settings = config.bootstrap()
    auto_approve = bool(store.get_config("auto_approve_previews", False))
    candidates = [p for p in candidates_for_metro(store, metro) if not p.get("takedown")]

    stat = {
        "script": "preview_gate",
        "in": len(candidates),
        "gated_pass": 0,
        "gated_fail": 0,
        "approved": 0,
        "auto_approve_previews": auto_approve,
        "dropped": {},
    }
    for preview in candidates:
        result = gate_preview(store, preview, auto_approve=auto_approve, actor=actor, tmp_root=settings.TMP)
        if result["passed"]:
            stat["gated_pass"] += 1
        else:
            stat["gated_fail"] += 1
        if result["approved"]:
            stat["approved"] += 1
    return stat


def main(argv: list[str] | None = None) -> None:
    config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metro", required=True)
    parser.add_argument("--actor", default="preview_gate")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    args = parser.parse_args(argv)

    store_kind = reject_mock_with_supabase(parser, args)
    store = get_store(kind=store_kind, root=args.store_root)
    try:
        stat = run(store, metro=args.metro, actor=args.actor)
    except Exception as exc:  # noqa: BLE001 — top-level error channel per CONTRACTS.md
        notify.error("preview.preview_gate", f"{type(exc).__name__}: {exc}", count=1)
        raise
    print(json.dumps(stat))
    if stat["gated_fail"]:
        # non-fatal for the workflow (a failing gate is expected, routine behavior, not a pipeline
        # error) — this script always exits 0 on a clean run; only an actual exception exits non-zero.
        pass


if __name__ == "__main__":
    main()
