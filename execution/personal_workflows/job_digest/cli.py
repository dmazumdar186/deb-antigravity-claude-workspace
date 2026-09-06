"""
description: CLI entry point for job_digest — `python -m execution.personal_workflows.job_digest.cli {validate|preview|run|render-workflow|setup|doctor}`.
inputs: argparse subcommands; each takes a profile.yaml path except `setup`.
outputs: stdout (human-readable report per subcommand); `run` also produces
    out_dir/summary.json + run_log.jsonl and, in live mode, side effects
    documented in run.py's docstring. Process exit code communicates pass/fail
    per subcommand (0 = ok).
"""

from __future__ import annotations

import argparse
import logging
import os
import smtplib
import sys
from pathlib import Path

from .profile_schema import load_profile, validate_file
from .run import run as run_pipeline

logger = logging.getLogger("job_digest.cli")

DEFAULT_STATE_DIR = Path("state")
DEFAULT_OUT_DIR = Path(".tmp") / "job_digest"


def _cmd_validate(args: argparse.Namespace) -> int:
    problems = validate_file(args.profile)
    if problems:
        print(f"{args.profile}: {len(problems)} problem(s):")
        for line in problems:
            print(line)
        return 1
    print(f"{args.profile}: OK")
    return 0


def _cmd_preview(args: argparse.Namespace) -> int:
    """Preview mode: one LIVE fetch, prints a table + would-send subject, no side
    effects. Do not loop this — repeated live fetches can get sources (notably
    LinkedIn) to start blocking the friend's IP.
    """
    result = run_pipeline(
        args.profile,
        mode="preview",
        state_dir=Path(args.state_dir),
        out_dir=Path(args.out_dir),
    )
    stats = result.get("stats", {})
    print(f"job_digest preview — {args.profile}")
    print(f"  fetched: {stats.get('fetched_total', 0)}")
    print(f"  normalized: {stats.get('normalized', 0)}")
    print(f"  new (post state-dedup): {stats.get('new_after_state_dedup', 0)}")
    print(f"  post-filter: {stats.get('filters', {}).get('kept', 0)}")
    print(f"  digest rows: {stats.get('digest_rows', 0)}")
    acc = stats.get("acceptance", {})
    print(f"  acceptance: {'PASS' if acc.get('passed') else 'FAIL: ' + '; '.join(acc.get('problems', []))}")
    if stats.get("email_written"):
        print("  email: written to disk (preview — nothing sent)")
    if result.get("exit_code", 0) != 0:
        print(f"  exit_code: {result['exit_code']}")
    if not acc.get("passed", True):
        print(f"  preview FAILED: acceptance gate rejected this run — {'; '.join(acc.get('problems', []))}")
    return result.get("exit_code", 0)


def _cmd_run(args: argparse.Namespace) -> int:
    result = run_pipeline(
        args.profile,
        mode=args.mode,
        state_dir=Path(args.state_dir),
        out_dir=Path(args.out_dir),
        max_jobs=args.max_jobs,
    )
    stats = result.get("stats", {})
    print(f"job_digest run ({args.mode}) — exit_code={result.get('exit_code', 0)}")
    print(f"  stats: {stats}")
    if stats.get("email_sent"):
        print("  email: sent")
    elif stats.get("email_written"):
        print("  email: written to disk (dry run — nothing sent)")
    else:
        print("  email: not sent")
    if "error" in result:
        print(f"  error: {result['error']}")
    return result.get("exit_code", 0)


def _cmd_render_workflow(args: argparse.Namespace) -> int:
    try:
        from .workflow_render import render_workflow  # noqa: PLC0415 — guarded, sibling agent's module
    except ImportError as exc:
        print(f"render-workflow: workflow_render module not available yet ({exc})")
        return 1
    profile = load_profile(args.profile)
    yaml_text = render_workflow(profile)
    print(yaml_text)
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    try:
        from . import setup_wizard  # noqa: PLC0415 — guarded, sibling agent's module
    except ImportError as exc:
        print(f"setup: setup_wizard module not available yet ({exc})")
        return 1

    # Forward to setup_wizard's own argv contract: `--answers <json> --out <yaml>`.
    wizard_argv: list[str] = []
    if args.answers:
        wizard_argv += ["--answers", args.answers]
    if args.out:
        wizard_argv += ["--out", args.out]
    return setup_wizard.main(wizard_argv or None) or 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    print(f"job_digest doctor — {args.profile}")
    ok = True

    problems = validate_file(args.profile)
    if problems:
        ok = False
        print("  [FAIL] profile validation:")
        for line in problems:
            print(f"    {line}")
    else:
        print("  [OK] profile validation")

    # Optional keys — informational only, the pipeline degrades gracefully
    # without them (heuristic-only ranking, sheet write skipped).
    for env_name in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        present = bool(os.environ.get(env_name, "").strip())
        print(f"  [{'OK' if present else 'INFO'}] env {env_name}: {'set' if present else 'not set (optional)'}")

    # Mandatory for any real send — a live run cannot email without these.
    smtp_user_set = bool(os.environ.get("GMAIL_SMTP_USER", "").strip())
    smtp_pass_set = bool(os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip())
    for env_name, present in (("GMAIL_SMTP_USER", smtp_user_set), ("GMAIL_SMTP_APP_PASSWORD", smtp_pass_set)):
        if present:
            print(f"  [OK] env {env_name}: set")
        else:
            ok = False
            print(f"  [FAIL] env {env_name}: not set (required for live email send)")

    state_dir = Path(args.state_dir)
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        probe = state_dir / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"  [OK] state dir writable: {state_dir}")
    except OSError as exc:
        ok = False
        print(f"  [FAIL] state dir not writable ({state_dir}): {exc}")

    if smtp_user_set and smtp_pass_set:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
                smtp.login(os.environ["GMAIL_SMTP_USER"].strip(), os.environ["GMAIL_SMTP_APP_PASSWORD"].strip())
            print("  [OK] SMTP login test")
        except smtplib.SMTPAuthenticationError as exc:
            ok = False
            print(f"  [FAIL] SMTP login test: {exc}")
        except OSError as exc:
            ok = False
            print(f"  [FAIL] SMTP connection failed: {exc}")
    else:
        print("  [INFO] skipping SMTP login test (already flagged missing credentials above)")

    if not problems:
        profile = load_profile(args.profile)
        if profile.sheet.enabled:
            spreadsheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
            service_account_path = Path(
                os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
            )
            if not spreadsheet_id:
                ok = False
                print("  [FAIL] sheet.enabled but SHEETS_SPREADSHEET_ID not set")
            elif not service_account_path.exists():
                ok = False
                print(f"  [FAIL] sheet.enabled but service account file not found: {service_account_path}")
            else:
                try:
                    from .notifier import sheet as sheet_module  # noqa: PLC0415 — guarded, sibling agent's module
                except ImportError:
                    print("  [INFO] notifier.sheet not available yet — skipping sheet open test")
                else:
                    open_test = getattr(sheet_module, "open_test", None)
                    if open_test is None:
                        print("  [INFO] notifier.sheet has no open_test() yet — skipping sheet open test")
                    else:
                        try:
                            open_test(spreadsheet_id, service_account_path)
                            print("  [OK] sheet open test")
                        except Exception as exc:  # noqa: BLE001 — doctor surfaces any failure, never crashes
                            ok = False
                            print(f"  [FAIL] sheet open test: {exc}")

    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job_digest", description="job_digest CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a profile.yaml")
    p_validate.add_argument("profile")
    p_validate.set_defaults(func=_cmd_validate)

    p_preview = sub.add_parser(
        "preview",
        help=(
            "One LIVE fetch (real network calls) with no side effects — no email, sheet, "
            "or state writes; shows what the digest would contain. Do not loop it — "
            "LinkedIn blocks repeated fetches. Exit code 3 means the acceptance gate "
            "failed (printed above the exit_code line); 0 otherwise."
        ),
    )
    p_preview.add_argument("profile")
    p_preview.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p_preview.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_preview.set_defaults(func=_cmd_preview)

    p_run = sub.add_parser(
        "run",
        help=(
            "Run the pipeline. --mode dry = fixtures only, no network/side effects. "
            "--mode live = real fetch, real sheet write, real email send, marks state."
        ),
    )
    p_run.add_argument("profile")
    p_run.add_argument("--mode", choices=["dry", "live"], required=True)
    p_run.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p_run.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_run.add_argument("--max-jobs", type=int, default=None)
    p_run.set_defaults(func=_cmd_run)

    p_render = sub.add_parser("render-workflow", help="Render the GitHub Actions workflow YAML for this profile")
    p_render.add_argument("profile")
    p_render.set_defaults(func=_cmd_render_workflow)

    p_setup = sub.add_parser("setup", help="Interactive setup wizard (or non-interactive with --answers)")
    p_setup.add_argument("--out", default="profile.yaml", help="Where to write profile.yaml")
    p_setup.add_argument(
        "--answers",
        default=None,
        help="Path to a JSON file with pre-filled answers (profile.yaml-shaped), for non-interactive use.",
    )
    p_setup.set_defaults(func=_cmd_setup)

    p_doctor = sub.add_parser("doctor", help="Diagnose a profile's environment")
    p_doctor.add_argument("profile")
    p_doctor.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p_doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
