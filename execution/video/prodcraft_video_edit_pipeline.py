"""
description: Video-to-video editing pipeline (Nick Saraev method). Takes a real
             source clip + `trigger + change` prompt, generates N candidates in
             parallel, renders an HTML index for human-select, and promotes the
             chosen candidate to winner.mp4. Phase 1a: dry-run + gates + schema
             + failure handlers. Live mode is stubbed until Higgsfield MCP is
             installed in Phase 2.
inputs:
    CLI:
        --source PATH               real source clip (<=10s per Rule 5)
        --trigger "..."             time- or event-gated trigger moment
        --change "..."              what happens next
        --n INT                     parallel candidates (default 5)
        --model NAME                model choice (default gemini-omni)
        --sensitivity {sensitive,public}   REQUIRED; filters model choice
        --consent-verified PATH     REQUIRED when sensitive
        --out DIR                   working dir (default .tmp/video/<slug>/)
        --dry-run                   schema + gates + cost only; $0
        --live                      real generation (STUB until Phase 2)
        --sequential                debug-only; disables parallel-N
        --winner ID                 promote candidate to winner.mp4
        --check-plan PATH           lint shot list for seam-rule violations
    env: HIGGSFIELD_MCP_TOKEN (reserved for Phase 6 direct-API fallback)
outputs:
    <out>/candidates/candidate_{1..N}.mp4    (Phase 2+)
    <out>/index.html                          human-select interface
    <out>/run.log                             invocation log
    <out>/manifest.json                       pipeline metadata
    <out>/winner.mp4                          after --winner ID
    .tmp/video/spend_log.jsonl                shared daily-rolling counter
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SPEND_LOG = WORKSPACE_ROOT / ".tmp" / "video" / "spend_log.jsonl"
# Currency: EUR per `~/.claude/rules/currency-eur.md`. USD provider prices are
# converted via USD_TO_EUR at load time; every operator-facing surface (manifest,
# stderr, spend log, directive tables) uses EUR.
USD_TO_EUR = 0.92
COST_GATE_EUR = 2.00
DAILY_WARN_EUR = 5.00
SOURCE_MAX_SECONDS = 10.0
MAX_PROMPT_CHARS = 500  # per audit Research-team #5: cap on trigger/change to reduce injection surface.

# Model catalog: (jurisdiction, allowed-for-sensitive, cost-per-10s-clip-eur).
# Provider prices are published in USD (Gemini Omni, Higgsfield, etc.); we
# convert once at catalog-definition time so downstream code is EUR-native.
# Nick's video quotes: Gemini Omni ~$1/clip, Kling ~$0.30, Runway ~$0.50. Others
# from Higgsfield's public catalog per the directive's prior-art pass.
def _eur(usd: float) -> float:
    return round(usd * USD_TO_EUR, 2)


MODEL_CATALOG: dict[str, dict] = {
    "gemini-omni":  {"jurisdiction": "US-Google",   "sensitive_ok": True,  "cost_eur_per_clip": _eur(1.00)},
    "runway-gen3":  {"jurisdiction": "US-Runway",   "sensitive_ok": True,  "cost_eur_per_clip": _eur(0.50)},
    "sora-2":       {"jurisdiction": "US-OpenAI",   "sensitive_ok": True,  "cost_eur_per_clip": _eur(1.00)},
    "veo-3.1":      {"jurisdiction": "US-Google",   "sensitive_ok": True,  "cost_eur_per_clip": _eur(0.75)},
    "kling-3":      {"jurisdiction": "CN-Kuaishou", "sensitive_ok": False, "cost_eur_per_clip": _eur(0.30)},
    "wan-vace":     {"jurisdiction": "CN-Alibaba",  "sensitive_ok": False, "cost_eur_per_clip": _eur(0.00)},  # HF Space
    "seedance-2":   {"jurisdiction": "CN-ByteDance","sensitive_ok": False, "cost_eur_per_clip": _eur(0.30)},
    "hailuo":       {"jurisdiction": "CN-MiniMax",  "sensitive_ok": False, "cost_eur_per_clip": _eur(0.25)},
}


class PipelineError(Exception):
    """Raised for user-recoverable pipeline failures. Message becomes stderr."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


def _slugify(path: Path) -> str:
    stem = path.stem.lower()
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in stem)[:40] or "clip"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ffprobe_duration_seconds(source: Path) -> float:
    """Read the source clip duration via ffprobe. Returns seconds as float.
    Raises PipelineError on missing ffprobe or unreadable source.
    """
    if not source.exists():
        raise PipelineError("SOURCE_NOT_FOUND", f"Source clip not found: {source}")
    if shutil.which("ffprobe") is None:
        raise PipelineError(
            "FFPROBE_MISSING",
            "ffprobe not on PATH. Install ffmpeg (winget install ffmpeg) or run with --skip-duration-check.",
        )
    try:
        # Subprocess encoding hardening per ~/.claude/rules/python-hardening.md rule 1.
        r = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(source),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except subprocess.TimeoutExpired as e:
        raise PipelineError("FFPROBE_TIMEOUT", f"ffprobe timed out reading {source}") from e
    if r.returncode != 0:
        raise PipelineError("FFPROBE_FAILED", f"ffprobe exit {r.returncode}: {r.stderr.strip()}")
    try:
        return float(r.stdout.strip())
    except ValueError as e:
        raise PipelineError("FFPROBE_PARSE", f"Cannot parse duration from ffprobe: {r.stdout!r}") from e


# Per audit Research-team #5: reject prompts that smuggle URLs (SSRF surface into
# downstream MCP tool calls) or that exceed MAX_PROMPT_CHARS. This is a small
# defense: it does NOT stop prompt-injection sophistication in general, but it
# closes the two most obvious channels (URL smuggling + oversize buffer).
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def validate_schema(trigger: str, change: str) -> None:
    """Enforce Nick's Rule 2: trigger + change both required + non-empty + specific.
    Also sanitize surface: length cap + URL rejection (audit Research-team #5).
    """
    if not trigger or not trigger.strip():
        raise PipelineError("SCHEMA_TRIGGER_EMPTY", "--trigger is required and must be non-empty (Rule 2).")
    if not change or not change.strip():
        raise PipelineError("SCHEMA_CHANGE_EMPTY", "--change is required and must be non-empty (Rule 2).")
    trigger_s = trigger.strip()
    change_s = change.strip()
    if len(trigger_s) < 8:
        raise PipelineError(
            "SCHEMA_TRIGGER_VAGUE",
            f"--trigger too short ({len(trigger_s)} chars). Nick's Rule 2: be specific. "
            "Example: 'at exactly 2.9 seconds' or 'when the man snaps his fingers'.",
        )
    if len(change_s) < 8:
        raise PipelineError(
            "SCHEMA_CHANGE_VAGUE",
            f"--change too short ({len(change_s)} chars). Nick's Rule 2: be specific. "
            "Example: 'change his outfit to a cool looking hoodie with a chain'.",
        )
    if len(trigger_s) > MAX_PROMPT_CHARS:
        raise PipelineError(
            "SCHEMA_TRIGGER_TOO_LONG",
            f"--trigger is {len(trigger_s)} chars; cap is {MAX_PROMPT_CHARS}. Shorten and re-run.",
        )
    if len(change_s) > MAX_PROMPT_CHARS:
        raise PipelineError(
            "SCHEMA_CHANGE_TOO_LONG",
            f"--change is {len(change_s)} chars; cap is {MAX_PROMPT_CHARS}. Shorten and re-run.",
        )
    if _URL_RE.search(trigger_s) or _URL_RE.search(change_s):
        raise PipelineError(
            "SCHEMA_URL_IN_PROMPT",
            "URL detected in --trigger or --change. Prompts are forwarded verbatim to the "
            "video model; URLs would be a SSRF/exfil surface. Describe the intent in words instead.",
        )


def validate_sensitivity_gate(model: str, sensitivity: str) -> dict:
    """Enforce ~/.claude/rules/model-tier.md sensitivity guardrail per model jurisdiction."""
    if model not in MODEL_CATALOG:
        raise PipelineError(
            "MODEL_UNKNOWN",
            f"Model '{model}' not in catalog. Choose from: {sorted(MODEL_CATALOG)}",
        )
    info = MODEL_CATALOG[model]
    if sensitivity == "sensitive" and not info["sensitive_ok"]:
        blocked = [m for m, i in MODEL_CATALOG.items() if not i["sensitive_ok"]]
        allowed = [m for m, i in MODEL_CATALOG.items() if i["sensitive_ok"]]
        raise PipelineError(
            "SENSITIVITY_BLOCKED",
            f"Model '{model}' ({info['jurisdiction']}) is blocked for --sensitivity sensitive. "
            f"Chinese-jurisdiction models cannot process PII/faces. Blocked: {blocked}. "
            f"Allowed for sensitive: {allowed}.",
        )
    return info


def validate_consent_gate(sensitivity: str, consent_path: Path | None) -> dict:
    """Enforce Phase 1a consent gate. Returns audit dict (path + sha256 + mtime + size).
    Content of the release is NOT validated — operator attests fitness. Log enables
    post-hoc catch of stale-release reuse (per skeptic round-2 residual concern).
    """
    if sensitivity != "sensitive":
        return {}
    if consent_path is None:
        raise PipelineError(
            "CONSENT_MISSING_FLAG",
            "--sensitivity sensitive requires --consent-verified <path-to-signed-release>. "
            "See directives/gtm_client_workflows/likeness_release_template.md (Phase 4).",
        )
    if not consent_path.exists():
        raise PipelineError("CONSENT_FILE_NOT_FOUND", f"Consent file not found: {consent_path}")
    if consent_path.stat().st_size == 0:
        raise PipelineError("CONSENT_FILE_EMPTY", f"Consent file is empty: {consent_path}")
    h = hashlib.sha256()
    with consent_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return {
        "path": str(consent_path.resolve()),
        "sha256": h.hexdigest(),
        "mtime_iso": datetime.fromtimestamp(consent_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "size_bytes": consent_path.stat().st_size,
    }


def validate_duration_gate(source: Path) -> float:
    """Enforce Rule 5: source must be <=10s. Returns duration in seconds."""
    dur = ffprobe_duration_seconds(source)
    if dur > SOURCE_MAX_SECONDS:
        raise PipelineError(
            "SOURCE_TOO_LONG",
            f"Source clip is {dur:.2f}s; models cap at {SOURCE_MAX_SECONDS:.0f}s. "
            f"Chunk source per Rule 5 or use prodcraft_longform_chain.py (Phase 7).",
        )
    return dur


def cost_estimate_eur(model: str, n: int) -> float:
    return round(MODEL_CATALOG[model]["cost_eur_per_clip"] * n, 2)


def daily_spend_today_eur() -> float:
    """Sum today's UTC spend entries from the shared rolling counter."""
    if not SPEND_LOG.exists():
        return 0.0
    today = date.today().isoformat()
    total = 0.0
    with SPEND_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Skip corrupt lines rather than crash; log to stderr so it doesn't
                # get lost silently (per python-hardening rule 5).
                print(f"WARN: skipping corrupt spend_log line: {line!r}", file=sys.stderr)
                continue
            if row.get("date_utc") == today:
                total += float(row.get("cost_eur", 0.0))
    return round(total, 2)


def append_spend_entry(cost_eur: float, model: str, n: int, slug: str) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "date_utc": date.today().isoformat(),
        "ts_utc": _iso_now(),
        "cost_eur": cost_eur,
        "model": model,
        "n_candidates": n,
        "slug": slug,
    }
    with SPEND_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def cost_gate(model: str, n: int, dry_run: bool) -> float:
    """Enforce per-invocation (€2) + per-day-rolling (€5) cost gates. Returns
    estimated EUR. Prompts operator on per-invocation excess (skipped in dry-run
    since no charge is imminent).
    """
    est = cost_estimate_eur(model, n)
    today = daily_spend_today_eur()
    print(
        f"[cost] estimate: EUR {est:.2f} for {n}x {model}; today's spend so far: EUR {today:.2f}",
        file=sys.stderr,
    )
    if today + est > DAILY_WARN_EUR:
        print(
            f"WARN: today's cumulative spend would reach EUR {today + est:.2f} "
            f"(daily warn threshold EUR {DAILY_WARN_EUR:.2f}).",
            file=sys.stderr,
        )
    if est > COST_GATE_EUR and not dry_run:
        print(f"Per-invocation cost estimate EUR {est:.2f} exceeds EUR {COST_GATE_EUR:.2f}.", file=sys.stderr)
        try:
            answer = input("Confirm proceed? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "y":
            raise PipelineError("COST_GATE_REJECTED", f"Operator did not confirm EUR {est:.2f} spend.")
    return est


def write_manifest(out_dir: Path, args: argparse.Namespace, consent_audit: dict,
                   duration_sec: float, model_info: dict, cost_est_eur: float) -> Path:
    manifest = {
        "schema_version": 2,
        "created_utc": _iso_now(),
        "currency": "EUR",
        "source": {
            "path": str(Path(args.source).resolve()),
            "duration_sec": round(duration_sec, 3),
        },
        "prompt": {
            "trigger": args.trigger,
            "change": args.change,
        },
        "generation": {
            "model": args.model,
            "jurisdiction": model_info["jurisdiction"],
            "n_candidates": args.n,
            "sequential": bool(args.sequential),
            "sensitivity": args.sensitivity,
        },
        "consent_audit": consent_audit,
        "cost": {
            "estimated_eur": cost_est_eur,
            "per_clip_eur": model_info["cost_eur_per_clip"],
        },
        "mode": "dry-run" if args.dry_run else ("live" if args.live else "check-only"),
        "workspace_root": str(WORKSPACE_ROOT),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def append_run_log(out_dir: Path, event: str, detail: dict | None = None) -> None:
    log_path = out_dir / "run.log"
    entry = {"ts_utc": _iso_now(), "event": event}
    if detail:
        entry["detail"] = detail
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def check_plan_lint(plan_path: Path) -> int:
    """Rule 4 discipline aid: lint operator-authored plan.json for same-shot-type
    transitions after AI-edited shots. Returns count of warnings emitted.
    Real frame-analysis enforcement is Phase 8.
    """
    if not plan_path.exists():
        raise PipelineError("PLAN_NOT_FOUND", f"Plan file not found: {plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PipelineError("PLAN_INVALID_JSON", f"{plan_path}: {e}") from e
    shots = plan.get("shots", [])
    warnings = 0
    for i, shot in enumerate(shots[:-1]):
        if not shot.get("ai_edited"):
            continue
        next_shot = shots[i + 1]
        if shot.get("shot_type") == next_shot.get("shot_type"):
            print(
                f"WARN: shot[{i}] ai_edited + shot[{i+1}] same shot_type "
                f"'{shot.get('shot_type')}' violates Rule 4 (720p seam-hiding).",
                file=sys.stderr,
            )
            warnings += 1
    print(f"[check-plan] {len(shots)} shots scanned, {warnings} Rule-4 warnings.", file=sys.stderr)
    return warnings


def dispatch_live(args: argparse.Namespace, out_dir: Path) -> None:
    """Phase 2+ live dispatch via Higgsfield MCP. STUBBED in Phase 1a."""
    raise PipelineError(
        "LIVE_MODE_NOT_YET_WIRED",
        "Live-mode dispatch is stubbed in Phase 1a. Install Higgsfield MCP first "
        "(Phase 2): claude mcp add --transport http --scope user higgsfield "
        "https://mcp.higgsfield.ai/mcp",
    )


def promote_winner(out_dir: Path, winner_id: str) -> Path:
    """Copy chosen candidate to winner.mp4 (Phase 2+ real path; Phase 1a informs)."""
    candidates_dir = out_dir / "candidates"
    candidate = candidates_dir / f"candidate_{winner_id}.mp4"
    if not candidate.exists():
        raise PipelineError(
            "WINNER_NOT_FOUND",
            f"Candidate {winner_id} not found at {candidate}. "
            f"Available: {[p.name for p in candidates_dir.glob('candidate_*.mp4')] if candidates_dir.exists() else []}",
        )
    winner_path = out_dir / "winner.mp4"
    shutil.copy2(candidate, winner_path)
    return winner_path


def _reconfigure_streams() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001 -- Python 3.14 always supports reconfigure; safe fallback for older.
        # Non-fatal: streams remain at platform default. Log so it doesn't hide.
        print(f"WARN: could not reconfigure streams to utf-8: {e}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Video-to-video editing pipeline (Nick Saraev method). See "
                    "directives/video/prodcraft_video_edit_pipeline.md.",
    )
    # Check-plan mode is standalone (no source/prompt needed).
    p.add_argument("--check-plan", type=Path, default=None,
                   help="Lint operator-authored shot list for Rule-4 seam violations. Standalone mode.")

    # Winner-promote mode (post-select).
    p.add_argument("--winner", default=None,
                   help="Promote candidate_<ID> to winner.mp4 (run after human-select). Requires --out.")

    # Main pipeline args.
    p.add_argument("--source", type=Path, help="Real source clip (<=10s per Rule 5).")
    p.add_argument("--trigger", default="", help="Time- or event-gated trigger moment (Rule 2).")
    p.add_argument("--change", default="", help="What happens next after the trigger (Rule 2).")
    p.add_argument("--n", type=int, default=5, help="Parallel candidates (Rule 3, default 5).")
    p.add_argument("--model", default="gemini-omni", help=f"Model. Catalog: {sorted(MODEL_CATALOG)}")
    p.add_argument("--sensitivity", choices=("sensitive", "public"),
                   help="REQUIRED when running the pipeline. Filters model choice per jurisdiction.")
    p.add_argument("--consent-verified", dest="consent_verified", type=Path, default=None,
                   help="REQUIRED when --sensitivity sensitive. Path to signed release.")
    p.add_argument("--out", type=Path, default=None, help="Output dir (default .tmp/video/<slug>/).")
    p.add_argument("--dry-run", action="store_true", help="Validate + estimate; no API calls; $0.")
    p.add_argument("--live", action="store_true", help="Real generation (STUB until Phase 2).")
    p.add_argument("--sequential", action="store_true", help="Debug-only; disables parallel-N.")
    p.add_argument("--skip-duration-check", action="store_true",
                   help="Skip ffprobe duration gate. Debug only.")
    args = p.parse_args()

    try:
        # Mode 1: --check-plan standalone.
        if args.check_plan is not None:
            warnings = check_plan_lint(args.check_plan)
            print(json.dumps({"ok": True, "mode": "check-plan", "warnings": warnings}))
            return 0

        # Mode 2: --winner standalone (needs --out).
        if args.winner is not None:
            if args.out is None:
                raise PipelineError("WINNER_MISSING_OUT", "--winner requires --out <dir> of the prior run.")
            winner_path = promote_winner(args.out.resolve(), args.winner)
            append_run_log(args.out.resolve(), "winner_promoted", {"candidate_id": args.winner, "path": str(winner_path)})
            print(json.dumps({"ok": True, "mode": "winner", "winner_path": str(winner_path)}))
            return 0

        # Mode 3: full pipeline.
        if args.source is None:
            raise PipelineError("MISSING_SOURCE", "--source is required (or use --check-plan / --winner modes).")
        if args.sensitivity is None:
            raise PipelineError(
                "MISSING_SENSITIVITY",
                "--sensitivity {sensitive,public} is required. This is a rule-tier gate, no default.",
            )
        if args.n < 1:
            raise PipelineError("BAD_N", f"--n must be >= 1 (got {args.n}).")
        if args.dry_run and args.live:
            raise PipelineError("MODE_CONFLICT", "Cannot combine --dry-run and --live.")

        source = args.source.resolve()
        slug = _slugify(source)
        out_dir = (args.out or (WORKSPACE_ROOT / ".tmp" / "video" / slug)).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        append_run_log(out_dir, "start", {"argv": sys.argv[1:], "slug": slug})

        # Gates in order. Each raises PipelineError on failure.
        validate_schema(args.trigger, args.change)
        model_info = validate_sensitivity_gate(args.model, args.sensitivity)
        consent_audit = validate_consent_gate(args.sensitivity, args.consent_verified)
        if consent_audit:
            append_run_log(out_dir, "consent_verified", consent_audit)

        if args.skip_duration_check:
            duration_sec = 0.0
            print("WARN: --skip-duration-check bypasses Rule 5.", file=sys.stderr)
        else:
            duration_sec = validate_duration_gate(source)

        cost_est = cost_gate(args.model, args.n, args.dry_run)

        manifest_path = write_manifest(out_dir, args, consent_audit, duration_sec, model_info, cost_est)
        append_run_log(out_dir, "manifest_written", {"path": str(manifest_path)})

        if args.dry_run:
            summary = {
                "ok": True,
                "mode": "dry-run",
                "manifest": str(manifest_path),
                "cost_estimated_eur": cost_est,
                "gates_passed": ["schema", "sensitivity", "consent", "duration", "cost"],
                "next": "Re-run with --live once Phase 2 (Higgsfield MCP install) is complete.",
            }
            append_run_log(out_dir, "dry_run_complete", summary)
            print(json.dumps(summary, indent=2))
            return 0

        # Live-mode is stubbed until Phase 2.
        dispatch_live(args, out_dir)
        # Would append spend + render index.html + exit in Phase 2.
        # append_spend_entry(cost_est, args.model, args.n, slug)
        return 0

    except PipelineError as e:
        # Deliberate: user-facing structured error, not a bare swallow (per python-hardening rule 5).
        print(f"ERROR: {e}", file=sys.stderr)
        # Best-effort audit trail; ignore if out_dir wasn't created yet.
        try:
            if args.out:
                append_run_log(args.out.resolve(), "error", {"code": e.code, "message": str(e)})
        except Exception:  # noqa: BLE001 -- audit-log write is best-effort; main error already surfaced.
            pass
        # Machine-readable exit code lookup for tests + orchestrators.
        return 2


if __name__ == "__main__":
    _reconfigure_streams()
    sys.exit(main())
