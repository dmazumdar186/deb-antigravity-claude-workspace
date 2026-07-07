"""
description: Output-acceptance gate for prodcraft_video_edit_pipeline.py
             (per ~/.claude/rules/output-acceptance-gate.md). Runs the 3-triplet
             positive corpus + the 3-triplet negative corpus in dry-run mode
             and hard-fails on any violation.

             Phase 1b scope: exercise schema + sensitivity + consent + cost gates
             + manifest shape. Duration gate is bypassed with --skip-duration-check
             (ffmpeg not on this Windows box; Phase 3 dogfood exercises it).

inputs:
    CLI:
        --dry-run   (only mode supported in Phase 1b)
        --verbose   print per-triplet detail
    env: none
outputs:
    stdout: PASS/FAIL summary + per-triplet verdict lines
    exit 0 on all-pass, 1 on any-fail
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = WORKSPACE_ROOT / "execution" / "video" / "prodcraft_video_edit_pipeline.py"
CORPUS = WORKSPACE_ROOT / "tests" / "fixtures" / "video_edit_pipeline" / "corpus.json"


def ensure_marker_sources(triplets: list[dict]) -> None:
    """Create empty .mp4 marker files for every referenced source_fixture path.
    Phase 1b uses --skip-duration-check so ffprobe isn't invoked; the pipeline
    only needs Path(source).resolve() to succeed and (when duration-checked)
    source.exists(). We satisfy both cheaply.
    """
    seen: set[Path] = set()
    for t in triplets:
        p = WORKSPACE_ROOT / t["source_fixture"]
        if p in seen:
            continue
        seen.add(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()


def _invoke(args: list[str], tmp_out: Path) -> tuple[int, str, str]:
    """Run the pipeline. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, str(PIPELINE), *args, "--out", str(tmp_out), "--skip-duration-check"]
    # Subprocess encoding per python-hardening rule 1.
    r = subprocess.run(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return r.returncode, r.stdout, r.stderr


def check_positive(triplet: dict, tmp_root: Path, verbose: bool) -> tuple[bool, str]:
    """A positive triplet must dry-run successfully AND emit a manifest matching expected shape."""
    tmp_out = tmp_root / triplet["id"]
    args = [
        "--source", str(WORKSPACE_ROOT / triplet["source_fixture"]),
        "--trigger", triplet["trigger"],
        "--change", triplet["change"],
        "--model", triplet["model"],
        "--sensitivity", triplet["sensitivity"],
        "--n", str(triplet["n"]),
        "--dry-run",
    ]
    if triplet.get("consent_verified"):
        args += ["--consent-verified", str(WORKSPACE_ROOT / triplet["consent_verified"])]

    code, out, err = _invoke(args, tmp_out)
    if verbose:
        print(f"  argv: {args}")
        print(f"  exit: {code}")
        if err.strip():
            print(f"  stderr: {err.strip()[:400]}")
    if code != 0:
        return False, f"expected exit 0, got {code}. stderr={err.strip()[:200]}"

    manifest_path = tmp_out / "manifest.json"
    if not manifest_path.exists():
        return False, "manifest.json not written"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"manifest.json invalid JSON: {e}"

    exp = triplet["expected_dry_run"]
    if manifest["generation"]["jurisdiction"] != exp["model_jurisdiction"]:
        return False, (
            f"jurisdiction mismatch: manifest={manifest['generation']['jurisdiction']} "
            f"vs expected={exp['model_jurisdiction']}"
        )
    if abs(manifest["cost"]["estimated_eur"] - exp["cost_estimated_eur"]) > 0.01:
        return False, (
            f"cost mismatch: manifest={manifest['cost']['estimated_eur']} "
            f"vs expected={exp['cost_estimated_eur']}"
        )
    if manifest["prompt"]["trigger"] != triplet["trigger"]:
        return False, "trigger not preserved in manifest"
    if manifest["prompt"]["change"] != triplet["change"]:
        return False, "change not preserved in manifest"
    if triplet["sensitivity"] == "sensitive":
        if not manifest.get("consent_audit"):
            return False, "consent_audit empty for sensitive triplet"
        if "sha256" not in manifest["consent_audit"]:
            return False, "consent_audit missing sha256 hash"

    return True, "OK"


def check_negative(triplet: dict, tmp_root: Path, verbose: bool) -> tuple[bool, str]:
    """A negative triplet must exit non-zero with the expected error code in stderr."""
    tmp_out = tmp_root / f"neg_{triplet['id']}"
    args = [
        "--source", str(WORKSPACE_ROOT / triplet["source_fixture"]),
        "--trigger", triplet["trigger"],
        "--change", triplet["change"],
        "--model", triplet["model"],
        "--sensitivity", triplet["sensitivity"],
        "--n", str(triplet["n"]),
        "--dry-run",
    ]
    if triplet.get("consent_verified"):
        args += ["--consent-verified", str(WORKSPACE_ROOT / triplet["consent_verified"])]

    code, out, err = _invoke(args, tmp_out)
    if verbose:
        print(f"  argv: {args}")
        print(f"  exit: {code}")
        if err.strip():
            print(f"  stderr: {err.strip()[:400]}")
    if code == 0:
        return False, f"expected non-zero exit, got 0. stdout={out.strip()[:200]}"

    expected = triplet["expected_error_code"]
    if f"[{expected}]" not in err:
        return False, f"expected error code {expected!r} in stderr, got: {err.strip()[:400]}"
    return True, "OK"


def check_plan_lint(tmp_root: Path, verbose: bool) -> list[tuple[str, bool, str]]:
    """Exercise --check-plan on the two seam-lint fixtures. Good plan => 0 warnings,
    bad plan => >=1 warning.
    """
    results: list[tuple[str, bool, str]] = []
    for plan_name, expected_min_warnings in [("seam_lint_plan_good.json", 0), ("seam_lint_plan_bad.json", 1)]:
        plan_path = WORKSPACE_ROOT / "tests" / "fixtures" / "video_edit_pipeline" / plan_name
        code, out, err = _invoke(["--check-plan", str(plan_path)], tmp_root / f"lint_{plan_name}")
        if verbose:
            print(f"  {plan_name}: exit={code} stderr={err.strip()[:200]}")
        if code != 0:
            results.append((plan_name, False, f"exit {code}: {err.strip()[:200]}"))
            continue
        try:
            summary = json.loads(out.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as e:
            results.append((plan_name, False, f"cannot parse summary from stdout: {e}"))
            continue
        got_warnings = summary.get("warnings", -1)
        if expected_min_warnings == 0 and got_warnings != 0:
            results.append((plan_name, False, f"expected 0 warnings, got {got_warnings}"))
        elif expected_min_warnings > 0 and got_warnings < expected_min_warnings:
            results.append((plan_name, False, f"expected >={expected_min_warnings} warnings, got {got_warnings}"))
        else:
            results.append((plan_name, True, f"OK ({got_warnings} warnings)"))
    return results


def main() -> int:
    p = argparse.ArgumentParser(description="Output-acceptance gate for prodcraft_video_edit_pipeline.py")
    p.add_argument("--dry-run", action="store_true",
                   help="Phase 1b: only supported mode. Live-mode acceptance arrives in Phase 3.")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if not args.dry_run:
        print("ERROR: only --dry-run supported in Phase 1b.", file=sys.stderr)
        return 1

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    all_source_fixtures = [t["source_fixture"] for t in corpus["triplets"] + corpus["negative_cases"]]
    ensure_marker_sources([{"source_fixture": f} for f in set(all_source_fixtures)])

    passes: list[str] = []
    fails: list[tuple[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="acceptance_v2v_") as tmp:
        tmp_root = Path(tmp)

        print("=== positive corpus ===")
        for t in corpus["triplets"]:
            print(f"[{t['id']}]")
            ok, why = check_positive(t, tmp_root, args.verbose)
            if ok:
                passes.append(t["id"])
                print(f"  PASS")
            else:
                fails.append((t["id"], why))
                print(f"  FAIL: {why}")

        print("\n=== negative corpus ===")
        for t in corpus["negative_cases"]:
            print(f"[{t['id']}]")
            ok, why = check_negative(t, tmp_root, args.verbose)
            if ok:
                passes.append(t["id"])
                print(f"  PASS")
            else:
                fails.append((t["id"], why))
                print(f"  FAIL: {why}")

        print("\n=== --check-plan lint ===")
        for name, ok, msg in check_plan_lint(tmp_root, args.verbose):
            print(f"[{name}]")
            if ok:
                passes.append(f"lint:{name}")
                print(f"  PASS: {msg}")
            else:
                fails.append((f"lint:{name}", msg))
                print(f"  FAIL: {msg}")

    total = len(passes) + len(fails)
    print(f"\n=== SUMMARY ===")
    print(f"passed: {len(passes)}/{total}")
    if fails:
        print("failed:")
        for name, why in fails:
            print(f"  - {name}: {why}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        print(f"WARN: could not reconfigure streams to utf-8: {e}", file=sys.stderr)
    sys.exit(main())
