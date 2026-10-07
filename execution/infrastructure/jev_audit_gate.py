"""Jev confidence gate on the audit stack — score reviewer reports before they count as evidence.

description: One Jev call per audit report (verdict, worst severity, evidence quality, scope coverage,
             self-consistency, unverified claims); code-side thresholds decide accept / review / reject.
             Weak PASS reports escalate to a re-review instead of counting as audit evidence.
             Directive: directives/infrastructure/jev_audit_gate.md.
inputs: `gate --report path|- [--asked-for "text|@file"] [--json]`;
        `transcript --path file.jsonl [--last N] [--json] [--dry-run]`;
        thresholds in DEFAULT_CFG, overridable via .claude/jev/config.json key `audit_gate`;
        env OPENROUTER_API_KEY (cloud alias OPENROUTER_API_TOEKN).
outputs: decision + reasons + raw signals on stdout; exit 0 accept, 1 review, 3 reject, 2 usage error.
         Ledger row caller=jev_audit_gate in .tmp/jev_ledger.jsonl; decisions appended to
         .tmp/jev_audit_gate_log.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

CONFIG_PATH = _ROOT / ".claude" / "jev" / "config.json"
LOG_PATH = _ROOT / ".tmp" / "jev_audit_gate_log.jsonl"
LEDGER_PATH = _ROOT / ".tmp" / "jev_ledger.jsonl"
HANDBACK_MARKER = "[Subagent hand-back]"
# Agent tool_results that are launch receipts / pointers to a hand-back message, not reports.
_NON_REPORT = ("Async agent launched", "delivered to you as a message from")
EXIT = {"skip": 0, "accept": 0, "review": 1, "reject": 3}
RANK = {"skip": -1, "accept": 0, "review": 1, "reject": 2}

DEFAULT_CFG: dict[str, Any] = {
    "min_verdict_confidence": 0.7,
    "min_evidence": 2.0,
    "min_self_consistent": 0.6,
    "max_unverified_claims": 0.4,
    "min_scope_covered": 0.6,
    "reject_self_consistent_below": 0.4,
    # transcript mode: hand-backs Jev judges not to be audit/review reports are skipped
    "min_is_audit": 0.5,
    "timeout_s": 8.0,
    "hook_timeout_s": 2.0,
    "max_report_chars": 24_000,
}

_log_lock = threading.Lock()


@dataclass
class GateResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_cfg(path: Path | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CFG)
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as fh:
            over = (json.load(fh) or {}).get("audit_gate") or {}
        if isinstance(over, dict):
            cfg.update({k: v for k, v in over.items() if k in DEFAULT_CFG})
    except (OSError, ValueError, AttributeError):
        pass
    return cfg


def questions(has_asked_for: bool) -> dict[str, dict[str, Any]]:
    scope_instr = (
        "Does the report explicitly address each specific check listed in `asked_for`?"
        if has_asked_for else
        "Does the report explicitly address each item of its own stated checklist or scope?"
    )
    return {
        "verdict": jev_client.choice("What does the report conclude?", {
            "pass": "clean pass, no outstanding issues",
            "pass_with_warnings": "passes but lists non-blocking warnings",
            "fail": "fails; blocking findings remain",
            "inconclusive": "no clear verdict, or could not complete the review",
        }),
        "worst_severity": jev_client.choice("Worst severity among the report's findings?", {
            "none": "no findings", "low": "LOW only", "medium": "MEDIUM at worst",
            "high": "at least one HIGH", "critical": "at least one CRITICAL",
        }),
        "evidence": jev_client.score("How well are the findings and the verdict backed by evidence?", [
            "claims only, no locations",
            "some file names but no line numbers or outputs",
            "most findings cite file:line, little shown output",
            "every finding cites file:line and shows a reproduction, command output or test result",
        ]),
        "scope_covered": jev_client.noul(scope_instr,
                                         "every requested/stated check is explicitly addressed",
                                         "some checks are missing or only implied"),
        "self_consistent": jev_client.noul(
            "Does the verdict match the findings (e.g. no HIGH/CRITICAL rows under a PASS, no PASS line under a FAIL)?",
            "verdict and findings agree", "verdict contradicts the findings"),
        "is_audit": jev_client.noul(
            "Is this text an audit, review, QA or verification REPORT about someone else's work "
            "(findings, severities, a verdict), as opposed to an implementation or build summary "
            "describing work the author did themselves?",
            "an audit/review/QA report with findings and a verdict",
            "an implementation summary, status update, launch notice or other non-audit text"),
        "unverified_claims": jev_client.noul(
            "Does the report claim to have run tools/tests without showing their output, or hedge with "
            "'should work', 'likely', 'appears to'?",
            "contains unverified claims or hedges", "every claim of running something shows its output"),
    }


def decide_from_signals(sig: dict[str, Any], cfg: dict[str, Any], has_asked_for: bool) -> tuple[str, list[str]]:
    verdict = sig.get("verdict", "")
    conf = float(sig.get("verdict_confidence", 0.0))
    ev = float(sig.get("evidence", 0.0))
    sc = float(sig.get("self_consistent", 0.0))
    uc = float(sig.get("unverified_claims", 1.0))
    scope = float(sig.get("scope_covered", 0.0))
    if verdict == "fail":
        return "reject", [f"verdict=fail (confidence {conf:.2f})"]
    if sc < cfg["reject_self_consistent_below"]:
        return "reject", [f"self_consistent={sc:.2f} < {cfg['reject_self_consistent_below']}"]
    reasons: list[str] = []
    if verdict not in ("pass", "pass_with_warnings"):
        reasons.append(f"verdict={verdict or 'missing'}")
    if conf < cfg["min_verdict_confidence"]:
        reasons.append(f"verdict_confidence={conf:.2f} < {cfg['min_verdict_confidence']}")
    if ev < cfg["min_evidence"]:
        reasons.append(f"evidence={ev:.2f} < {cfg['min_evidence']}")
    if sc < cfg["min_self_consistent"]:
        reasons.append(f"self_consistent={sc:.2f} < {cfg['min_self_consistent']}")
    if uc >= cfg["max_unverified_claims"]:
        reasons.append(f"unverified_claims={uc:.2f} >= {cfg['max_unverified_claims']}")
    if has_asked_for and scope < cfg["min_scope_covered"]:
        reasons.append(f"scope_covered={scope:.2f} < {cfg['min_scope_covered']}")
    return ("review", reasons) if reasons else ("accept", [])


def _log(entry: dict[str, Any]) -> None:
    try:
        with _log_lock:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": int(time.time()), **entry}, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"audit gate log skipped: {exc}", file=sys.stderr)


def gate_report(text: str, *, asked_for: str | None = None, cfg: dict[str, Any] | None = None,
                timeout_s: float | None = None, label: str = "") -> GateResult:
    """Score one audit report with Jev and return accept / review / reject. Never raises."""
    cfg = cfg or load_cfg()
    has_af = bool(asked_for and asked_for.strip())
    state: dict[str, Any] = {"audit_report": text[: int(cfg["max_report_chars"])]}
    if has_af:
        state["asked_for"] = asked_for
    r = jev_client.decide(state, questions(has_af), timeout_s=float(timeout_s or cfg["timeout_s"]))
    with _log_lock:
        jev_client.append_ledger({"caller": "jev_audit_gate", "cost_usd": r.cost_usd,
                                  "input_tokens": r.input_tokens, "latency_ms": r.latency_ms,
                                  "error": r.error}, LEDGER_PATH)
    if r.error or not r.answers:
        res = GateResult("review", ["jev unavailable"], {}, latency_ms=r.latency_ms,
                         error=r.error or "empty answers", label=label)
    else:
        sig = {
            "verdict": r.choice("verdict"), "verdict_confidence": round(r.confidence("verdict"), 3),
            "worst_severity": r.choice("worst_severity"), "evidence": round(r.score("evidence"), 3),
            "scope_covered": round(r.noul("scope_covered"), 3),
            "self_consistent": round(r.noul("self_consistent"), 3),
            "unverified_claims": round(r.noul("unverified_claims", 1.0), 3),
            "is_audit": round(r.noul("is_audit", 1.0), 3),
        }
        if sig["is_audit"] < float(cfg.get("min_is_audit", 0.5)):
            decision, reasons = "skip", [f"not an audit report (is_audit={sig['is_audit']:.2f})"]
        else:
            decision, reasons = decide_from_signals(sig, cfg, has_af)
        res = GateResult(decision, reasons, sig, r.cost_usd, r.latency_ms, label=label)
    _log({"label": label, "decision": res.decision, "reasons": res.reasons,
          "signals": res.signals, "error": res.error})
    return res


# ---- transcript extraction ----------------------------------------------------------------

def _block_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(str(b.get("text", "")))
            elif isinstance(b, str):
                out.append(b)
    return "\n".join(out)


def extract_reports(path: str | Path, last: int = 5) -> list[dict[str, str]]:
    """Return the last N sub-agent hand-back reports [{label, text}] from a transcript JSONL."""
    # Only the tail matters (hand-backs are recent); a bounded deque keeps big transcripts cheap.
    from collections import deque
    tail: deque[str] = deque(maxlen=600)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                tail.append(ln)
    events: list[dict[str, Any]] = []
    for ln in tail:
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    agent_desc: dict[str, str] = {}
    reports: list[dict[str, str]] = []
    for ev in events:
        msg = ev.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        if ev.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                    inp = b.get("input") or {}
                    agent_desc[str(b.get("id", ""))] = str(inp.get("description") or inp.get("subagent_type") or "")
            continue
        if ev.get("type") != "user":
            continue
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in agent_desc:
                    txt = _block_text(b.get("content"))
                    if HANDBACK_MARKER in txt:
                        txt = txt.split(HANDBACK_MARKER, 1)[1]
                    if txt.strip() and not any(m in txt for m in _NON_REPORT):
                        reports.append({"label": agent_desc[b["tool_use_id"]], "text": txt.strip()})
                    continue
        txt = _block_text(content)
        if HANDBACK_MARKER in txt:
            reports.append({"label": "hand-back", "text": txt.split(HANDBACK_MARKER, 1)[1].strip()})
    return reports[-last:] if last > 0 else reports


def gate_many(reports: list[dict[str, str]], cfg: dict[str, Any], timeout_s: float) -> list[GateResult]:
    if not reports:
        return []

    def _one(r: dict[str, str]) -> GateResult:
        return gate_report(r["text"], cfg=cfg, timeout_s=timeout_s, label=r["label"])

    with ThreadPoolExecutor(max_workers=min(8, len(reports))) as pool:
        return list(pool.map(_one, reports))


# ---- CLI ------------------------------------------------------------------------------------

def _read_arg_text(val: str | None) -> str | None:
    if val is None:
        return None
    if val.startswith("@"):
        return Path(val[1:]).read_text(encoding="utf-8")
    return val


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--report", required=True)
    g.add_argument("--asked-for")
    g.add_argument("--json", action="store_true")
    t = sub.add_parser("transcript")
    t.add_argument("--path", required=True)
    t.add_argument("--last", type=int, default=5)
    t.add_argument("--json", action="store_true")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--timeout", type=float, help="per-call Jev timeout (default cfg hook_timeout_s)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    cfg = load_cfg()

    if args.cmd == "gate":
        try:
            text = sys.stdin.read() if args.report == "-" else Path(args.report).read_text(encoding="utf-8")
            asked = _read_arg_text(args.asked_for)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        res = gate_report(text, asked_for=asked, cfg=cfg)
        if args.json:
            print(json.dumps(res.to_dict(), ensure_ascii=False))
        else:
            print(f"decision: {res.decision}")
            for r in res.reasons:
                print(f"  - {r}")
            print("signals: " + json.dumps(res.signals))
            if res.error:
                print(f"jev error: {res.error}")
        return EXIT[res.decision]

    try:
        reports = extract_reports(args.path, args.last)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        if args.json:
            print(json.dumps({"reports": reports}, ensure_ascii=False))
        else:
            print(f"{len(reports)} hand-back report(s)")
            for i, r in enumerate(reports, 1):
                print(f"--- [{i}] {r['label']} ({len(r['text'])} chars)\n{r['text'][:400]}")
        return 0
    results = gate_many(reports, cfg, float(args.timeout or cfg["hook_timeout_s"]))
    worst = max((res.decision for res in results), key=lambda d: RANK[d], default="accept")
    if args.json:
        print(json.dumps({"worst": worst, "n": len(results),
                          "results": [r.to_dict() for r in results]}, ensure_ascii=False))
    else:
        if not results:
            print("no hand-back reports found")
        for r in results:
            print(f"{r.decision:7s} {r.label or '-'}: {'; '.join(r.reasons) or 'ok'}")
    return EXIT[worst]


if __name__ == "__main__":
    sys.exit(main())
