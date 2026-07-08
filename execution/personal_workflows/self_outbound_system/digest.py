"""
digest.py
description: Build the daily or weekly digest message from today's .tmp/self_outbound/*.json artifacts. Dry-run prints to stdout; live mode (STUB) would send to Telegram + CC debolshop@gmail.com. Includes anomaly flags (opens<10%, replies<1%, bounces>3%, canary FAIL).
inputs: --period <daily|weekly>, --tmp <path>, --dry-run/--live. Env (live only): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
outputs: stdout (dry-run) and .tmp/self_outbound/digest_<date>.txt.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #8).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    today_str,
)

load_dotenv()
log = get_logger("digest")


def _latest(pattern: str, tmp_dir: Path) -> Path | None:
    matches = sorted(tmp_dir.glob(pattern))
    return matches[-1] if matches else None


def _read_or_none(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        # Safe to swallow with logging: a corrupt tmp file should not crash the
        # digest, but the operator must see it. Per hardening rule 5.
        log.warning("could not read %s: %s — treating as absent", path, exc)
        return None


def build_digest(tmp_dir: Path, period: str) -> dict:
    """Read today's artifacts and assemble the digest structure."""
    stats_result = _read_or_none(_latest("instantly_result_*.json", tmp_dir)) or {}
    canary_result = _read_or_none(_latest("canary_*.json", tmp_dir)) or {}
    enriched = _read_or_none(_latest("enriched_leads_*.json", tmp_dir)) or {}
    personalized = _read_or_none(_latest("personalized_leads_*.json", tmp_dir)) or {}

    sends = int(stats_result.get("sends", 0))
    opens = int(stats_result.get("opens", 0))
    replies = int(stats_result.get("replies", 0))
    bounces = int(stats_result.get("bounces", 0))
    unsubs = int(stats_result.get("unsubscribes", 0))

    open_rate = (opens / sends) if sends > 0 else 0.0
    reply_rate = (replies / sends) if sends > 0 else 0.0
    bounce_rate = (bounces / sends) if sends > 0 else 0.0

    warnings: list[str] = []
    if sends > 0 and open_rate < 0.10:
        warnings.append(f"WARN opens {open_rate*100:.1f}% < 10%")
    if sends > 0 and reply_rate < 0.01:
        warnings.append(f"WARN replies {reply_rate*100:.2f}% < 1%")
    if sends > 0 and bounce_rate > 0.03:
        warnings.append(f"WARN bounces {bounce_rate*100:.1f}% > 3%")
    canary_status = canary_result.get("status", "UNKNOWN")
    if canary_status != "PASS":
        warnings.append(f"WARN canary={canary_status}")

    cost_eur = float(enriched.get("cost_eur", 0.0)) + float(personalized.get("cost_eur_total", 0.0))

    digest = {
        "period": period,
        "date": today_str(),
        "sent": sends,
        "opened": opens,
        "replied": replies,
        "positive": 0,   # populated by reply-classifier telemetry in a later phase
        "hot": 0,
        "bounced": bounces,
        "unsubscribed": unsubs,
        "canary": canary_status,
        "warmup_day": "n/a (dry-run)",
        "cost_eur": round(cost_eur, 4),
        "warnings": warnings,
    }
    return digest


def format_digest_text(digest: dict) -> str:
    lines = [
        f"[{digest['period'].upper()} digest -- {digest['date']}]",
        f"sent {digest['sent']} / opened {digest['opened']} / replied {digest['replied']} / "
        f"positive {digest['positive']} / hot {digest['hot']} / "
        f"bounced {digest['bounced']} / unsubscribed {digest['unsubscribed']}",
        f"canary={digest['canary']} / warmup day {digest['warmup_day']} / cost_eur={digest['cost_eur']}",
    ]
    if digest["warnings"]:
        lines.append("ANOMALIES:")
        lines.extend(f"  - {w}" for w in digest["warnings"])
    else:
        lines.append("no anomalies detected")
    return "\n".join(lines)


def send_live(text: str) -> dict:
    """Send digest via Telegram + email CC. STUBBED."""
    raise NotImplementedError(
        "Live digest send not implemented. Would POST to Telegram bot API "
        "and mail via Gmail API. Run --dry-run for now."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--period", choices=["daily", "weekly"], default="daily",
                   help="Digest period. Default: daily.")
    p.add_argument("--tmp", type=Path, default=TMP_DIR,
                   help="Directory holding today's tmp artifacts.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Prints to stdout.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Sends to Telegram + email.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    digest = build_digest(args.tmp, args.period)
    text = format_digest_text(digest)
    print(text)

    out_path = args.tmp / f"digest_{today_str()}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    if not args.dry_run:
        send_live(text)

    print_stat("digest", {
        "period": args.period,
        "warnings": len(digest["warnings"]),
        "dry_run": args.dry_run,
        "output": str(out_path),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
