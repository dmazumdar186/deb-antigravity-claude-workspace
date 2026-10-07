"""Gate an inbox with Jev so only emails that need writing reach the (expensive) AI agent.

description: One Jev call per email tags bucket (needs_reply / brand deal / client / newsletter /
             scam / personal / fyi), reply urgency, scam probability and human-sent probability.
             Code-side routing sends emails to `agent`, `human` (suspected targeted phishing or
             low confidence) or `archive_or_skip`. Writes an agent queue (the only thing Claude
             reads), Gmail labels in gmail_label_apply.py shape, and reports the token savings.
             Directive: directives/google/jev_email_gate.md
inputs: --input JSON list as written by .claude/skills/gmail-label/scripts/gmail_label_fetch.py
        ({id, subject, from, date, snippet}) or flat {id, from, subject, body, date};
        --min-confidence (0.6); --workers (8); --limit; --dry-run.
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: --output JSON (default <input>.gate.json) per-email decisions; --agent-queue JSON list of
         agent-routed emails; --labels-out {label: [ids]} for gmail_label_apply.py --input;
         --csv-out; stdout summary; ledger row in .tmp/jev_ledger.jsonl (caller "jev_email_gate").
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

BUCKETS: dict[str, str] = {
    "needs_reply": "a person asks me a question or for something and expects my written reply",
    "brand_deal_or_partnership": "sponsorship, collaboration, affiliate or partnership proposal",
    "customer_or_client": "an existing customer or client writing about their project, order or account",
    "newsletter_or_notification": "newsletter, marketing blast, receipt, automated alert or digest",
    "scam_or_spam": "unsolicited junk, phishing, fake invoice, prize/crypto scam",
    "personal": "friends or family, personal life, no business reply needed",
    "fyi_no_action": "informational update to me that needs no reply",
}
AGENT_BUCKETS = {"needs_reply", "brand_deal_or_partnership", "customer_or_client"}
URGENCY_LEVELS = ["no rush", "this week", "today"]
LABELS = {
    "needs_reply": "Jev/Needs Reply",
    "brand_deal_or_partnership": "Jev/Brand Deal",
    "customer_or_client": "Jev/Client",
    "newsletter_or_notification": "Jev/Newsletter",
    "scam_or_spam": "Jev/Spam",
    "personal": "Jev/Personal",
    "fyi_no_action": "Jev/FYI",
}
REVIEW_LABEL = "Jev/Review"
DEFAULT_MIN_CONFIDENCE = 0.6
SCAM_THRESHOLD = 0.5
HUMAN_SENT_THRESHOLD = 0.6
MAX_BODY_CHARS = 6_000
REFERENCE_VOLUME = 1_700


def load_emails(path: Path) -> list[dict[str, Any]]:
    """Accept gmail_label_fetch.py output (snippet) or flat {id, from, subject, body, date}."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data.get("emails", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON list of emails")
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        body = r.get("body") or r.get("snippet") or ""
        out.append({**r, "id": str(r.get("id") or i), "from": str(r.get("from", "")),
                    "subject": str(r.get("subject", "")), "body": str(body),
                    "date": str(r.get("date", ""))})
    return out


def email_state(e: dict[str, Any]) -> dict[str, str]:
    return {"from": e["from"], "subject": e["subject"], "date": e["date"],
            "body": e["body"][:MAX_BODY_CHARS]}


def build_questions() -> dict[str, dict[str, Any]]:
    return {
        "bucket": jev_client.choice("Which inbox bucket does this email belong to?", BUCKETS),
        "reply_urgency": jev_client.score("How soon does this email need a reply?", URGENCY_LEVELS),
        "is_scam": jev_client.noul(
            "Is this email a scam or phishing attempt?",
            "phishing, fake invoice, credential/payment request, impersonation of a company or person",
            "legitimate email from who it claims to be"),
        "human_sent": jev_client.noul(
            "Was this email written personally by a human to me?",
            "a person wrote it individually to me",
            "automated, templated or bulk-sent"),
    }


def route(bucket: str, confidence: float, is_scam: float, human_sent: float,
          min_confidence: float = DEFAULT_MIN_CONFIDENCE, error: str | None = None) -> str:
    if error or not bucket:
        return "human"
    if is_scam >= SCAM_THRESHOLD:
        return "human" if human_sent >= HUMAN_SENT_THRESHOLD else "archive_or_skip"
    if confidence < min_confidence:
        return "human"
    if bucket in AGENT_BUCKETS:
        return "agent"
    return "archive_or_skip"


def decide_row(e: dict[str, Any], r: jev_client.JevResult, min_confidence: float) -> dict[str, Any]:
    bucket = r.choice("bucket")
    conf = r.confidence("bucket")
    scam = r.noul("is_scam")
    human = r.noul("human_sent")
    urg = r.score("reply_urgency")
    idx = max(0, min(len(URGENCY_LEVELS) - 1, round(urg)))
    rt = route(bucket, conf, scam, human, min_confidence, r.error)
    return {"id": e["id"], "from": e["from"], "subject": e["subject"], "bucket": bucket,
            "confidence": round(conf, 4), "reply_urgency": round(urg, 3),
            "urgency_label": URGENCY_LEVELS[idx], "is_scam": round(scam, 4),
            "human_sent": round(human, 4), "route": rt, "cost_usd": r.cost_usd, "error": r.error}


def labels_for(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """{label: [ids]} in gmail_label_merge/apply shape. Scam wins; human-routed also gets Review."""
    out: dict[str, list[str]] = {}
    for d in rows:
        if d["is_scam"] >= SCAM_THRESHOLD:
            label = LABELS["scam_or_spam"]
        else:
            label = LABELS.get(d["bucket"], "")
        if label:
            out.setdefault(label, []).append(d["id"])
        if d["route"] == "human":
            out.setdefault(REVIEW_LABEL, []).append(d["id"])
    return out


def _bytes(items: list[dict[str, Any]]) -> int:
    return sum(len(json.dumps(i, ensure_ascii=False).encode("utf-8")) for i in items)


def summarize(emails: list[dict[str, Any]], rows: list[dict[str, Any]],
              queue: list[dict[str, Any]], wall_s: float) -> dict[str, Any]:
    cost = sum(r["cost_usd"] for r in rows)
    n = len(rows)
    in_b, q_b = _bytes(emails), _bytes(queue)
    per = cost / n if n else 0.0
    return {
        "count": n,
        "buckets": dict(Counter(r["bucket"] or "(none)" for r in rows)),
        "routes": dict(Counter(r["route"] for r in rows)),
        "to_agent": len(queue),
        "agent_share_emails_pct": round(100 * len(queue) / n, 1) if n else 0.0,
        "input_bytes": in_b, "agent_queue_bytes": q_b,
        "agent_share_bytes_pct": round(100 * q_b / in_b, 1) if in_b else 0.0,
        "scam_flags": sum(1 for r in rows if r["is_scam"] >= SCAM_THRESHOLD),
        "errors": sum(1 for r in rows if r["error"]),
        "cost_usd": round(cost, 6), "cost_per_email_usd": per,
        f"projected_cost_{REFERENCE_VOLUME}_usd": round(per * REFERENCE_VOLUME, 4),
        "wall_s": round(wall_s, 2),
    }


def _write_json(path: str, obj: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate an inbox with Jev before an AI agent reads it.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--agent-queue")
    ap.add_argument("--labels-out")
    ap.add_argument("--csv-out")
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="build questions, call nothing")
    a = ap.parse_args(argv)

    try:
        emails = load_emails(Path(a.input))
    except (OSError, ValueError) as exc:
        print(f"error: cannot read {a.input}: {exc}", file=sys.stderr)
        return 2
    if a.limit > 0:
        emails = emails[: a.limit]
    questions = build_questions()
    if a.dry_run:
        print(json.dumps({"emails": len(emails), "questions": questions,
                          "sample_state": email_state(emails[0]) if emails else None}, indent=2))
        return 0
    if not jev_client.available():
        print("error: no OpenRouter key (OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    results = jev_client.decide_many([email_state(e) for e in emails], questions, workers=a.workers)
    wall = time.perf_counter() - t0
    rows = [decide_row(e, r, a.min_confidence) for e, r in zip(emails, results)]
    by_id = {e["id"]: e for e in emails}
    queue = [{**by_id[d["id"]], "jev_bucket": d["bucket"], "jev_urgency": d["urgency_label"]}
             for d in rows if d["route"] == "agent"]
    summary = summarize(emails, rows, queue, wall)

    _write_json(a.output or f"{a.input}.gate.json", {"summary": summary, "emails": rows})
    if a.agent_queue:
        _write_json(a.agent_queue, queue)
    if a.labels_out:
        _write_json(a.labels_out, labels_for(rows))
    if a.csv_out:
        Path(a.csv_out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.csv_out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["id"])
            w.writeheader()
            w.writerows(rows)
    jev_client.append_ledger({"caller": "jev_email_gate", "n": summary["count"],
                              "cost_usd": summary["cost_usd"], "wall_s": summary["wall_s"],
                              "errors": summary["errors"]})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
