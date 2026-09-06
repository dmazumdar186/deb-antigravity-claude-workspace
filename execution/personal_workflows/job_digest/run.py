"""
description: Orchestrator for job_digest — fetch -> normalize -> dedup -> filter ->
    rank -> cap -> acceptance -> sheet -> email -> state, for one Profile.
inputs:
    - profile_path: path to the friend's profile.yaml
    - mode: "dry" = fixtures only, builds everything (digest, would-be email,
      run stats), NEVER touches the network, a real sheet, a real inbox, or
      state — the offline/CI-safe mode.
      "preview" = a LIVE fetch (real network calls to job sources) but still no
      side effects: no sheet write, no email send, no state mutation — just
      "fetch for real and show me what the digest would contain". Do not loop
      preview — repeated live fetches in a short window can get a source
      (notably LinkedIn) to start blocking the friend's IP.
      "live" = real fetch, real sheet write, real email send, marks state —
      everything happens for real. This is what production/cron runs.
    - state_dir: directory holding seen.json / email_lock.txt
    - out_dir: directory to write summary.json / run_log.jsonl into
    - max_jobs: optional override of profile.digest.max_jobs
    - env: GEMINI_API_KEY, ANTHROPIC_API_KEY (optional ranker rungs),
      SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH (default
      credentials/service_account.json) — read only when mode=="live" and
      profile.sheet.enabled.
outputs:
    - out_dir/summary.json (one run's full stats)
    - out_dir/run_log.jsonl (one line appended per run)
    - live mode only: a Google Sheet write, an email send, state/seen.json +
      state/email_lock.txt updated.
    - a dict (also what summary.json holds) with key "exit_code":
      0 ok, 3 acceptance FAIL, 5 SMTP auth failure, 6 sheet failure.
    - stats never carries a sheet URL or spreadsheet ID (H2) — only
      "sheet_ok": bool. The URL is passed to build_digest() for the email body
      only, never written to disk.

Interface assumptions about sibling modules being written by other agents
(guarded imports — see the try/except ImportError blocks below): each is
expected to exist by the time this pipeline runs live, but a missing module
degrades gracefully (fetch -> no jobs; sheet/email -> skipped with a logged
reason) rather than crashing the whole run:
    - sources.fetch_all(profile, *, dry: bool = False) -> dict[str, list[SourceJob]]
    - notifier.sheet.write_jobs(pairs, profile, spreadsheet_id, service_account_path, *, stats=...) -> str | None
    - notifier.email.build_digest(pairs, profile, stats, sheet_url) -> (subject, text, html)
    - notifier.email.send_digest(subject, text, html, profile, dry: bool, out_dir: Path | None) -> bool
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from . import acceptance
from .contracts import NormalizedJob, RankedJob
from .normalizer.filters import apply_filters
from .normalizer.normalize import batch_normalize
from .normalizer.state import State
from .profile_schema import load_profile
from .ranker.rank import rank

logger = logging.getLogger("job_digest.run")

Mode = Literal["dry", "live", "preview"]

_TIER_ORDER = {"A": 0, "B": 1, "C": 2, "SKIP": 3}
_MIN_TIER_FLOOR = {"A": {"A"}, "B": {"A", "B"}, "C": {"A", "B", "C"}}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_jsonl(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, default=str) + "\n")


def run(
    profile_path: str | Path,
    *,
    mode: Mode,
    state_dir: str | Path,
    out_dir: str | Path,
    max_jobs: int | None = None,
) -> dict:
    started_at = datetime.now(timezone.utc)
    state_dir = Path(state_dir)
    out_dir = Path(out_dir)

    profile = load_profile(profile_path)
    state = State(state_dir)

    result: dict = {
        "started_at": started_at.isoformat(),
        "mode": mode,
        "profile_path": str(profile_path),
        "exit_code": 0,
        "stats": {},
    }

    # ----- fetch -----
    dry_fetch = mode == "dry"  # preview fetches live but never sends/writes
    try:
        from .sources import fetch_all  # noqa: PLC0415 — guarded, sibling agent's module
    except ImportError as exc:
        logger.warning("run: sources.fetch_all not importable yet (%s) — proceeding with zero jobs", exc)
        fetch_all = None  # type: ignore[assignment]

    fetched: dict[str, list] = {}
    if fetch_all is not None:
        try:
            fetched = fetch_all(profile, dry=dry_fetch)
        except Exception as exc:  # noqa: BLE001 — a source-layer failure must not crash the digest
            logger.warning("run: fetch_all raised (%s) — proceeding with zero jobs", exc)
            fetched = {}

    source_jobs = [job for jobs in fetched.values() for job in jobs]
    result["stats"]["fetched_by_source"] = {src: len(jobs) for src, jobs in fetched.items()}
    result["stats"]["fetched_total"] = len(source_jobs)

    # ----- normalize + in-batch dedup -----
    normalized = batch_normalize(source_jobs)
    result["stats"]["normalized"] = len(normalized)

    # ----- persistent dedup -----
    new_jobs = state.filter_new(normalized)
    result["stats"]["new_after_state_dedup"] = len(new_jobs)

    # ----- profile filters -----
    filtered_jobs, filter_stats = apply_filters(new_jobs, profile)
    result["stats"]["filters"] = filter_stats

    # ----- rank -----
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None
    ranked, rungs = rank(filtered_jobs, profile, gemini_key=gemini_key, anthropic_key=anthropic_key)
    result["stats"]["rungs"] = rungs
    ranked_by_hash: dict[str, RankedJob] = {rj.content_hash: rj for rj in ranked}

    # ----- keep tier >= min_tier, sort by score desc, cap -----
    allowed_tiers = _MIN_TIER_FLOOR[profile.digest.min_tier]
    pairs: list[tuple[NormalizedJob, RankedJob]] = [
        (job, ranked_by_hash[job.content_hash])
        for job in filtered_jobs
        if job.content_hash in ranked_by_hash and ranked_by_hash[job.content_hash].tier.value in allowed_tiers
    ]
    pairs.sort(key=lambda pair: pair[1].score, reverse=True)
    cap = max_jobs if max_jobs is not None else profile.digest.max_jobs
    pairs = pairs[:cap]
    result["stats"]["digest_rows"] = len(pairs)

    # ----- acceptance (gates BOTH sheet write and email — M5) -----
    passed, problems = acceptance.check(pairs, profile)
    result["stats"]["acceptance"] = {"passed": passed, "problems": problems}
    if not passed:
        result["exit_code"] = 3
        _finalize(result, out_dir, started_at)
        return result

    # ----- sheet (live + enabled only; only after acceptance passed) -----
    sheet_url: str | None = None  # kept local for the email body only — never written to stats/disk (H2)
    sheet_ok: bool | None = None
    if mode == "live" and profile.sheet.enabled:
        try:
            from .notifier.sheet import SheetError, write_jobs  # noqa: PLC0415 — guarded, sibling agent's module
        except ImportError as exc:
            logger.warning("run: notifier.sheet.write_jobs not importable yet (%s) — skipping sheet write", exc)
            write_jobs = None  # type: ignore[assignment]
            SheetError = RuntimeError  # type: ignore[assignment,misc]

        if write_jobs is not None:
            spreadsheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
            service_account_path = Path(
                os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
            )
            if not spreadsheet_id:
                logger.warning("run: SHEETS_SPREADSHEET_ID not set — skipping sheet write")
            else:
                try:
                    sheet_url = write_jobs(pairs, profile, spreadsheet_id, service_account_path, stats=result["stats"])
                    sheet_ok = True
                except SheetError as exc:
                    logger.error("run: sheet write failed (%s)", exc)
                    sheet_ok = False
                    result["exit_code"] = 6
                    result["error"] = f"sheet write failed: {exc}"
                    result["stats"]["sheet_ok"] = sheet_ok
                    _finalize(result, out_dir, started_at)
                    return result
    result["stats"]["sheet_ok"] = sheet_ok

    # ----- email (gated by acceptance [already passed] + email lock) -----
    lock_ok = state.email_lock_ok(profile.digest.min_hours_between_emails)
    result["stats"]["email_lock_ok"] = lock_ok
    email_sent = False  # True only on a REAL SMTP send in live mode
    email_written = False  # True when a dry/preview digest was written to disk
    if lock_ok:
        try:
            from .notifier.email import SmtpAuthError, build_digest, send_digest  # noqa: PLC0415 — guarded, sibling agent's module
        except ImportError as exc:
            logger.warning("run: notifier.email not importable yet (%s) — skipping email", exc)
            build_digest = send_digest = None  # type: ignore[assignment]
            SmtpAuthError = RuntimeError  # type: ignore[assignment,misc]

        if build_digest is not None and send_digest is not None:
            try:
                subject, text, html = build_digest(pairs, profile, result["stats"], sheet_url)
                sent_or_written = send_digest(
                    subject, text, html, profile, dry=(mode != "live"), out_dir=out_dir
                )
                if mode == "live":
                    email_sent = sent_or_written
                else:
                    email_written = sent_or_written
            except SmtpAuthError as exc:
                logger.error("run: SMTP auth failure (%s)", exc)
                result["exit_code"] = 5
                result["error"] = f"SMTP auth failure: {exc}"
                _finalize(result, out_dir, started_at)
                return result
            except Exception as exc:  # noqa: BLE001 — non-auth email failure is logged, not fatal to the run
                logger.warning("run: email send raised (%s: %s) — not fatal, continuing", type(exc).__name__, exc)
    else:
        logger.info("run: email lock active — skipping send (recent email already sent)")

    result["stats"]["email_sent"] = email_sent
    result["stats"]["email_written"] = email_written

    # ----- mark state (live only; C2 — only rows actually in the digest, and
    # only once the email actually went out. If the lock blocked the send (or
    # a non-auth SMTP failure prevented it), nothing is marked seen so the
    # next run still sees — and can still email — these jobs.) -----
    if mode == "live":
        if email_sent:
            digest_jobs = [job for job, _ in pairs]
            state.mark_seen(digest_jobs)
            state.set_email_lock()
        state.save()

    _finalize(result, out_dir, started_at)
    return result


def _finalize(result: dict, out_dir: Path, started_at: datetime) -> None:
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["duration_s"] = (datetime.now(timezone.utc) - started_at).total_seconds()
    _write_json(out_dir / "summary.json", result)
    _append_jsonl(out_dir / "run_log.jsonl", result)
    logger.info("run: finished exit_code=%s digest_rows=%s", result["exit_code"], result["stats"].get("digest_rows"))
