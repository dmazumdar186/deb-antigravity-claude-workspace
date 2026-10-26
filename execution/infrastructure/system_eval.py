"""
system_eval.py
description: Recurring (every 10 days) self-evaluation of the operator's built systems. Six lenses
  (architecture, data, code health, operations, algorithm, security) scored 0-5 from measurable
  checks + behavioural targets per system, compared with the previous run (baseline JSON) to flag
  degradation. Produces a <=350-word executive report (markdown + plain-text email body).
inputs: config/system_eval.json (registry), optional --facts JSON (per-system facts the script
  cannot measure itself, e.g. scheduled-task state), env GITHUB_TOKEN (ops lens via REST API),
  GITHUB_REPOSITORY (optional; else parsed from `git remote`).
outputs: docs/reference/system_eval/<system>/latest.json (+ previous.json, history/<date>.json),
  docs/reference/system_eval/<system>/REPORT_<date>.md, docs/reference/system_eval/REPORT_<date>.md.
  Exit 0 always unless the script itself crashes; degradation is reported, not an exit code.
  The script never sends mail: `--email-body` prints the combined report as plain text for a caller.

Usage:
  python3 execution/infrastructure/system_eval.py run [--systems a,b] [--facts f.json] [--no-network]
                                                      [--timeout 600] [--date YYYY-MM-DD] [--email-body]
  python3 execution/infrastructure/system_eval.py report [--date YYYY-MM-DD] [--email-body]
  python3 execution/infrastructure/system_eval.py compare [--systems a,b]
Directive: directives/infrastructure/system_eval.md
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config" / "system_eval.json"
LENSES = ["architecture", "data", "code_health", "operations", "algorithm", "security"]
LENS_LABELS = {
    "architecture": "Architecture",
    "data": "Data",
    "code_health": "Code health",
    "operations": "Operations",
    "algorithm": "Algorithm",
    "security": "Security",
}
ENV_RE = re.compile(r"(?:os\.environ(?:\.get)?\s*[\[\(]|getenv\()\s*['\"]([A-Z][A-Z0-9_]+)['\"]")
SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "assigned_secret",
        re.compile(
            r"\b[A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD)[A-Za-z0-9_]*\s*[:=]\s*[\"']"
            r"(?:[A-Fa-f0-9]{32,}|[A-Za-z0-9+/=_-]{40,})[\"']"
        ),
    ),
]


# ----------------------------------------------------------------------------- helpers
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run(cmd: str, timeout: int) -> dict[str, Any]:
    """Run a shell command, utf-8 decoded, never raising."""
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return {"cmd": cmd, "rc": proc.returncode, "out": (proc.stdout or "") + (proc.stderr or "")}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "rc": None, "out": f"timeout after {timeout}s", "note": "timeout"}
    except OSError as exc:
        return {"cmd": cmd, "rc": None, "out": str(exc), "note": "os error"}


def _parse_pass_counts(out: str) -> tuple[int, int] | None:
    """Return (passed, total) from pytest or `N/M passed` style output."""
    m = re.search(r"\*{0,2}(\d+)/(\d+) passed", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    passed = failed = errors = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) errors?\b", out)
    if m:
        errors = int(m.group(1))
    if passed or failed or errors:
        return passed, passed + failed + errors
    return None


def _expand_files(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pat in patterns:
        for hit in sorted(glob.glob(str(ROOT / pat), recursive=True)):
            p = Path(hit)
            if p.is_file() and "__pycache__" not in p.parts:
                files.append(p)
    return files


def _git_last_commit(path: str) -> datetime | None:
    res = _run(f"git log -1 --format=%cI -- {path!s}", 60)
    text = (res.get("out") or "").strip().splitlines()
    if res.get("rc") == 0 and text:
        try:
            return datetime.fromisoformat(text[0].strip())
        except ValueError:
            return None
    return None


def _age_days(iso: str | None, today: date) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso)).date()
    except ValueError:
        return None
    return float((today - d).days)


def _clamp(x: float) -> int:
    return int(max(0, min(5, round(x))))


# ----------------------------------------------------------------------------- lenses
def lens_architecture(sysname: str, spec: dict, files: list[Path]) -> dict[str, Any]:
    ev: list[str] = []
    score = 0.0
    directive = ROOT / spec["directive"]
    exists = directive.is_file()
    score += 1 if exists else 0
    ev.append("directive present" if exists else "directive MISSING")

    code_ts = max((t for t in (_git_last_commit(p) for p in spec["code"]) if t), default=None)
    dir_ts = _git_last_commit(spec["directive"]) if exists else None
    synced = None
    if code_ts and dir_ts:
        lag = (code_ts - dir_ts).days
        synced = lag <= 30
        score += 1 if synced else 0
        ev.append(f"directive lag {max(lag, 0)}d" + ("" if synced else " (>30d)"))
    else:
        ev.append("sync unknown (no git history)")

    keys: set[str] = set()
    for f in files:
        if f.suffix == ".py":
            try:
                keys |= set(ENV_RE.findall(f.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    keys -= set(spec.get("env_ignore", []))
    documented: set[str] = set()
    if exists:
        text = directive.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^## Inputs\s*$(.*?)(?=^## )", text, re.S | re.M)
        inputs = m.group(1) if m else text
        documented = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", inputs))
        # Expand shorthand like FRANCE_TRAVAIL_CLIENT_ID/SECRET -> ..._CLIENT_SECRET
        for base, rest in re.findall(r"\b([A-Z][A-Z0-9_]+)((?:/[A-Z0-9_]+)+)", inputs):
            prefix = base.rsplit("_", 1)[0]
            for alt in rest.strip("/").split("/"):
                documented.add(f"{prefix}_{alt}")
    missing = sorted(k for k in keys if k not in documented)
    ratio = (len(keys) - len(missing)) / len(keys) if keys else 1.0
    score += 2 * ratio
    ev.append(f"env keys {len(keys) - len(missing)}/{len(keys)} documented" + (f" (missing {', '.join(missing)})" if missing else ""))

    leaks: list[str] = []
    func_re = re.compile(spec.get("deliverable_func_regex", "email|report|digest"), re.I)
    for rel in spec.get("deliverable_files", []):
        p = ROOT / rel
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and func_re.search(node.name):
                seg = ast.get_source_segment(src, node) or ""
                if "```ledger" in seg or "json.dumps(" in seg:
                    leaks.append(f"{p.name}:{node.name}")
    score += 0 if leaks else 1
    ev.append("no machine payload in deliverables" if not leaks else f"payload leak in {', '.join(leaks)}")
    return {"score": _clamp(score), "evidence": ev, "metrics": {
        "directive_exists": exists, "directive_synced": synced, "env_keys": sorted(keys),
        "env_missing": missing, "payload_leaks": leaks}}


def lens_data(spec: dict, timeout: int) -> dict[str, Any]:
    ev: list[str] = []
    cfg = spec.get("data", {})
    checks: dict[str, bool | None] = {}
    sg = cfg.get("schema_grep")
    if sg:
        try:
            text = (ROOT / sg["file"]).read_text(encoding="utf-8", errors="replace")
            ok = re.search(sg["pattern"], text, re.M) is not None
        except OSError:
            ok = False
        checks["schema_constants"] = ok
        ev.append("schema constants present" if ok else "schema constants MISSING")
    for name, cmd in cfg.get("commands", {}).items():
        res = _run(cmd, timeout)
        counts = _parse_pass_counts(res["out"])
        ok = res["rc"] == 0 if res.get("rc") is not None else None
        checks[name] = ok
        detail = f"{counts[0]}/{counts[1]}" if counts else ("rc=%s" % res["rc"])
        ev.append(f"{name} {'pass' if ok else ('n/a' if ok is None else 'FAIL')} ({detail})")
    known = [v for v in checks.values() if v is not None]
    score = _clamp(5 * sum(known) / len(known)) if known else None
    return {"score": score, "evidence": ev, "metrics": {"checks": checks}}


def lens_code_health(files: list[Path], timeout: int) -> dict[str, Any]:
    py = [f for f in files if f.suffix == ".py"]
    ev: list[str] = []
    metrics: dict[str, Any] = {}
    ruff = shutil.which("ruff")
    ruff_errors: int | None = None
    if ruff and py:
        paths = " ".join(f'"{p}"' for p in py)
        res = _run(f'"{ruff}" check --select E9,F63,F7,F82,F401,F841,B --output-format json {paths}', timeout)
        try:
            ruff_errors = len(json.loads(res["out"].strip() or "[]"))
        except ValueError:
            ruff_errors = None
        ev.append(f"ruff {ruff_errors} findings" if ruff_errors is not None else "ruff n/a (unparsable)")
    else:
        bad = 0
        for p in py:
            res = _run(f'python3 -m py_compile "{p}"', timeout)
            bad += 0 if res.get("rc") == 0 else 1
        ruff_errors = bad
        ev.append(f"py_compile {bad} failures (ruff not installed)")
    bare = long_fn = todo = 0
    for p in py:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        todo += len(re.findall(r"\b(TODO|FIXME)\b", src))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                swallow = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
                if node.type is None or (broad and swallow):
                    bare += 1
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (getattr(node, "end_lineno", node.lineno) - node.lineno) > 120:
                    long_fn += 1
    metrics.update({"ruff_errors": ruff_errors, "bare_excepts": bare, "long_functions": long_fn, "todo_fixme": todo, "py_files": len(py)})
    score = 5.0
    if ruff_errors:
        score -= min(2, 1 + ruff_errors // 10)
    if bare:
        score -= 2 if bare > 5 else 1
    if long_fn:
        score -= 1
    if todo > 10:
        score -= 1
    ev.append(f"bare/swallowed excepts {bare}, functions >120 lines {long_fn}, TODO/FIXME {todo}")
    return {"score": _clamp(score), "evidence": ev, "metrics": metrics}


def _github_repo() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    res = _run("git remote get-url origin", 30)
    m = re.search(r"github\.com[:/]([^/]+/[^/.\s]+)", res.get("out") or "")
    return m.group(1) if m else None


def lens_operations(spec: dict, facts: dict, today: date, no_network: bool, timeout: int) -> dict[str, Any]:
    cfg = spec.get("ops", {})
    ev: list[str] = []
    metrics: dict[str, Any] = {}
    gaps: list[str] = []
    earned = possible = 0.0
    if cfg.get("kind") == "github_workflow":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        repo = _github_repo()
        runs: list[dict] = []
        if no_network:
            gaps.append("network disabled")
        elif not token or not repo:
            gaps.append("GITHUB_TOKEN or repo unknown")
        else:
            url = (f"https://api.github.com/repos/{repo}/actions/workflows/{cfg['workflow_file']}/runs"
                   f"?per_page={cfg.get('runs', 10)}&exclude_pull_requests=true")
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "system_eval"})
            try:
                with urllib.request.urlopen(req, timeout=min(timeout, 60)) as resp:
                    runs = json.loads(resp.read().decode("utf-8")).get("workflow_runs", [])
            except (urllib.error.URLError, OSError, ValueError) as exc:
                gaps.append(f"GitHub API error: {str(exc)[:60]}")
        if runs:
            done = [r for r in runs if r.get("status") == "completed"]
            succ = [r for r in done if r.get("conclusion") == "success"]
            rate = len(succ) / len(done) if done else 0.0
            durs = []
            for r in done:
                try:
                    s = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                    e = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                    durs.append((e - s).total_seconds() / 60)
                except (KeyError, ValueError):
                    continue
            med = statistics.median(durs) if durs else None
            last_ok = None
            if succ:
                try:
                    t = datetime.fromisoformat(succ[0]["updated_at"].replace("Z", "+00:00"))
                    last_ok = (_utcnow() - t).total_seconds() / 3600
                except (KeyError, ValueError):
                    last_ok = None
            metrics.update({"runs": len(done), "success_rate": round(rate, 2), "median_minutes": round(med, 1) if med else None,
                            "last_success_age_h": round(last_ok, 1) if last_ok is not None else None})
            possible += 5
            earned += 2 if rate >= 0.9 else (1 if rate >= 0.7 else 0)
            if last_ok is not None:
                earned += 2 if last_ok <= 36 else (1 if last_ok <= 72 else 0)
            if med is not None:
                earned += 1 if med <= 60 else 0
            ev.append(f"last {len(done)} runs: {int(rate * 100)}% success, median {med:.0f} min, last success {last_ok:.0f}h ago"
                      if med is not None and last_ok is not None else f"last {len(done)} runs: {int(rate * 100)}% success")
    elif cfg.get("kind") == "facts":
        snap = _age_days(facts.get("last_drive_snapshot"), today)
        mail = _age_days(facts.get("last_report_email"), today)
        sent, quota = facts.get("last_day_sent"), facts.get("last_day_quota")
        if snap is not None:
            possible += 2
            earned += 2 if snap <= 1 else (1 if snap <= 3 else 0)
            ev.append(f"Drive snapshot {snap:.0f}d old")
        else:
            gaps.append("snapshot age")
        if mail is not None:
            possible += 2
            earned += 2 if mail <= 1 else (1 if mail <= 2 else 0)
            ev.append(f"report email {mail:.0f}d old")
        else:
            gaps.append("report email age")
        if isinstance(sent, (int, float)) and isinstance(quota, (int, float)) and quota:
            possible += 1
            earned += 1 if sent / quota >= 0.9 else 0
            ev.append(f"last day {int(sent)}/{int(quota)} sent")
        else:
            gaps.append("sent/quota")
        metrics.update({"snapshot_age_days": snap, "report_email_age_days": mail, "last_day_sent": sent, "last_day_quota": quota,
                        "slots_per_day": facts.get("slots_per_day"), "slot_times": facts.get("slot_times")})
    if gaps:
        ev.append("unknown: " + ", ".join(gaps))
    metrics["gaps"] = gaps
    score = _clamp(5 * earned / possible) if possible else None
    if score is None:
        ev.append("n/a")
    return {"score": score, "evidence": ev, "metrics": metrics}


def lens_algorithm(spec: dict, timeout: int) -> dict[str, Any]:
    cmd = spec.get("algorithm", {}).get("command")
    if not cmd:
        return {"score": None, "evidence": ["n/a (no algorithm tests registered)"], "metrics": {}}
    res = _run(cmd, timeout)
    counts = _parse_pass_counts(res["out"])
    if counts and counts[1]:
        score = _clamp(5 * counts[0] / counts[1])
        ev = [f"ranking/caps/filters tests {counts[0]}/{counts[1]} pass"]
    elif res.get("rc") is None:
        score, ev = None, [f"n/a ({res.get('note')})"]
    else:
        score = 5 if res["rc"] == 0 else 0
        ev = ["tests pass" if res["rc"] == 0 else f"tests FAIL rc={res['rc']}"]
    return {"score": score, "evidence": ev, "metrics": {"passed": counts[0] if counts else None, "total": counts[1] if counts else None, "rc": res.get("rc")}}


def lens_security(spec: dict, files: list[Path], env_keys: list[str], timeout: int, no_network: bool) -> dict[str, Any]:
    cfg = spec.get("security", {})
    allow = [a["literal"] for a in cfg.get("allow", []) if a.get("literal")]
    findings: list[str] = []
    for p in files:
        if p.suffix in {".pyc", ".png", ".jpg", ".pdf"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, rx in SECRET_PATTERNS:
            for m in rx.finditer(text):
                if any(a in m.group(0) for a in allow):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"{p.relative_to(ROOT)}:{line} {name}")
    ev = [f"{len(findings)} secret findings" + (f" ({findings[0]})" if findings else f", {len(allow)} allow-listed")]
    score = 5 - 2 * len(findings)
    vulns: int | None = None
    if shutil.which("pip-audit") and (ROOT / "requirements.txt").is_file() and not no_network:
        res = _run("pip-audit -r requirements.txt -f json --progress-spinner off", timeout)
        try:
            data = json.loads(res["out"][res["out"].find("{"):] or "{}")
            vulns = sum(len(d.get("vulns", [])) for d in data.get("dependencies", []))
        except (ValueError, AttributeError):
            vulns = None
        if vulns is not None:
            score -= 1 if vulns else 0
            ev.append(f"pip-audit {vulns} vulns")
        else:
            ev.append("pip-audit n/a (unparsable)")
    else:
        ev.append("pip-audit n/a")
    ev.append(f"{len(env_keys)} env keys, {len(cfg.get('connectors', []))} connectors")
    return {"score": _clamp(score), "evidence": ev, "metrics": {"secret_findings": findings, "pip_audit_vulns": vulns,
                                                               "env_keys": env_keys, "connectors": cfg.get("connectors", [])}}


def eval_targets(spec: dict, facts: dict, ops_metrics: dict) -> list[dict[str, Any]]:
    out = []
    for t in spec.get("targets", []):
        status, note = "unknown", ""
        kind = t.get("kind")
        if kind == "grep":
            try:
                text = (ROOT / t["file"]).read_text(encoding="utf-8", errors="replace")
                ok = True
                if t.get("must_match") and not re.search(t["must_match"], text):
                    ok, note = False, "table header not found"
                if t.get("must_not_match") and re.search(t["must_not_match"], text):
                    ok, note = False, f'"{t["must_not_match"]}" still present'
                status = "met" if ok else "unmet"
            except OSError:
                status, note = "unknown", "file missing"
        elif kind == "ops_success_rate_min":
            rate = ops_metrics.get("success_rate")
            if rate is None:
                note = "no run data"
            else:
                status = "met" if rate >= t["value"] else "unmet"
                note = f"{int(rate * 100)}%"
        elif kind == "fact":
            val = facts.get(t["key"])
            if val is None:
                note = f"fact {t['key']} not supplied"
            elif "equals" in t:
                status = "met" if val == t["equals"] else "unmet"
                note = str(val)
            elif "min" in t:
                try:
                    status = "met" if float(val) >= float(t["min"]) else "unmet"
                except (TypeError, ValueError):
                    status = "unknown"
                note = str(val)
        out.append({"id": t["id"], "label": t.get("label", t["id"]), "status": status, "note": note})
    return out


# ----------------------------------------------------------------------------- orchestration
def evaluate_system(name: str, spec: dict, facts: dict, today: date, no_network: bool, timeout: int) -> dict[str, Any]:
    files = _expand_files(spec["code"] + spec.get("extra_files", []))
    arch = lens_architecture(name, spec, files)
    lenses = {
        "architecture": arch,
        "data": lens_data(spec, timeout),
        "code_health": lens_code_health(files, timeout),
        "operations": lens_operations(spec, facts, today, no_network, timeout),
        "algorithm": lens_algorithm(spec, timeout),
    }
    lenses["security"] = lens_security(spec, files, arch["metrics"]["env_keys"], timeout, no_network)
    targets = eval_targets(spec, facts, lenses["operations"]["metrics"])
    scored = [v["score"] for v in lenses.values() if v["score"] is not None]
    overall = round(sum(scored) / len(scored), 1) if scored else None
    return {"system": name, "date": today.isoformat(), "generated_at": _utcnow().isoformat(timespec="seconds"),
            "overall": overall, "lenses": lenses, "targets": targets, "facts": facts, "fixes": facts.get("fixes", [])}


def compare_runs(cur: dict, prev: dict | None) -> dict[str, Any]:
    deltas: dict[str, int | None] = {}
    dropped: list[str] = []
    for lens in LENSES:
        c = cur["lenses"][lens]["score"]
        p = prev["lenses"][lens]["score"] if prev and lens in prev.get("lenses", {}) else None
        d = (c - p) if (c is not None and p is not None) else None
        deltas[lens] = d
        if d is not None and d <= -1:
            dropped.append(LENS_LABELS[lens])
    unmet = [t["label"] for t in cur["targets"] if t["status"] == "unmet"]
    degraded = bool(dropped or unmet)
    return {"deltas": deltas, "dropped": dropped, "unmet": unmet, "degraded": degraded,
            "prev_scores": {l: (prev["lenses"][l]["score"] if prev and l in prev.get("lenses", {}) else None) for l in LENSES}}


def _fmt(v: Any) -> str:
    """Scores: plain number or em dash."""
    return "—" if v is None else str(v)


def _fmt_delta(v: Any) -> str:
    """Deltas: signed, or em dash when there is no previous run."""
    return "—" if v is None else (f"{v:+d}" if v else "0")


def _headline(evidence: list[str]) -> str:
    """One phrase per lens: the first item that signals a problem, else the first item."""
    bad = re.compile(r"MISSING|FAIL|missing|leak|unknown|>30d|[1-9]\d* findings|[1-9]\d* secret|\b[1-6]\d%|\b0/\d+ pass")
    for e in evidence:
        if bad.search(e):
            return e[:110]
    return evidence[0][:110] if evidence else ""


def render_report(results: list[dict], comparisons: list[dict], today: date, cadence: int) -> str:
    lines = [f"# System evaluation — {today.isoformat()}", ""]
    for r, c in zip(results, comparisons, strict=True):
        verdict = f"DEGRADED ({', '.join(c['dropped'] + c['unmet'])})" if c["degraded"] else "no degradation"
        lines.append(f"{r['system']}: {_fmt(r['overall'])}/5 — {verdict}")
    for r, c in zip(results, comparisons, strict=True):
        lines += ["", f"## {r['system']}", "| Lens | Score | Prev | Delta | Evidence |", "|---|---|---|---|---|"]
        for lens in LENSES:
            L = r["lenses"][lens]
            score = "n/a" if L["score"] is None else str(L["score"])
            prev = c["prev_scores"][lens]
            lines.append(f"| {LENS_LABELS[lens]} | {score} | {_fmt(prev)} | {_fmt_delta(c['deltas'][lens])} | {_headline(L['evidence'])} |")
    lines += ["", "## Behavioural targets"]
    for r in results:
        for t in r["targets"]:
            note = f" ({t['note']})" if t["note"] else ""
            lines.append(f"- {r['system']} / {t['label']}: {t['status']}{note}")
    star: list[str] = []
    for r, c in zip(results, comparisons, strict=True):
        for lens in LENSES:
            d = c["deltas"][lens]
            if d:
                L = r["lenses"][lens]
                star += [f"- Situation: {r['system']} {LENS_LABELS[lens]} moved {d:+d} since the previous evaluation.",
                         f"  Task: confirm whether the change is real degradation or a measurement shift.",
                         f"  Action: evidence this run: {'; '.join(L['evidence'])[:120]}.",
                         f"  Result: lens now {L['score']}/5; {'DEGRADED, fix before next check' if d < 0 else 'improved, keep'}."]
        for fix in r.get("fixes", []):
            if isinstance(fix, dict):
                star += [f"- Situation: {fix.get('situation', '')}", f"  Task: {fix.get('task', '')}",
                         f"  Action: {fix.get('action', '')}", f"  Result: {fix.get('result', '')}"]
    if star:
        lines += ["", "## STAR"] + star
    lines += ["", f"Next check: {(today + timedelta(days=cadence)).isoformat()}", ""]
    return "\n".join(lines)


def to_email_body(md: str) -> str:
    out = []
    for line in md.splitlines():
        if line.startswith("|---"):
            continue
        line = re.sub(r"^#+\s*", "", line)
        out.append(line)
    return "\n".join(out).strip() + "\n"


def _report_dir(reg: dict) -> Path:
    return ROOT / reg.get("report_dir", "docs/reference/system_eval")


def cmd_run(args: argparse.Namespace, reg: dict) -> int:
    today = date.fromisoformat(args.date) if args.date else date.today()
    facts_all: dict = {}
    if args.facts:
        facts_all = _load_json(Path(args.facts)) or {}
        if not facts_all:
            print(f"warning: facts file {args.facts} unreadable; continuing with unknowns", file=sys.stderr)
    names = [s.strip() for s in args.systems.split(",")] if args.systems else list(reg["systems"])
    results, comparisons = [], []
    base = _report_dir(reg)
    for name in names:
        spec = reg["systems"].get(name)
        if not spec:
            print(f"warning: unknown system {name}; skipped", file=sys.stderr)
            continue
        print(f"[system_eval] evaluating {name} ...", file=sys.stderr)
        res = evaluate_system(name, spec, facts_all.get(name, {}), today, args.no_network, args.timeout)
        sdir = base / name
        prev = _load_json(sdir / "latest.json")
        comp = compare_runs(res, prev)
        res["comparison"] = comp
        res["previous_date"] = prev.get("date") if prev else None
        if prev:
            _write_json(sdir / "previous.json", prev)
        _write_json(sdir / "latest.json", res)
        _write_json(sdir / "history" / f"{today.isoformat()}.json", res)
        (sdir / f"REPORT_{today.isoformat()}.md").write_text(render_report([res], [comp], today, reg.get("cadence_days", 10)), encoding="utf-8")
        results.append(res)
        comparisons.append(comp)
    md = render_report(results, comparisons, today, reg.get("cadence_days", 10))
    combined = base / f"REPORT_{today.isoformat()}.md"
    combined.parent.mkdir(parents=True, exist_ok=True)
    combined.write_text(md, encoding="utf-8")
    print(to_email_body(md) if args.email_body else md)
    print(f"[system_eval] wrote {combined.relative_to(ROOT)}", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace, reg: dict) -> int:
    base = _report_dir(reg)
    if args.date:
        path = base / f"REPORT_{args.date}.md"
    else:
        cands = sorted(base.glob("REPORT_*.md"))
        path = cands[-1] if cands else None
    if not path or not path.is_file():
        print("no report found; run `system_eval.py run` first", file=sys.stderr)
        return 0
    md = path.read_text(encoding="utf-8")
    print(to_email_body(md) if args.email_body else md)
    return 0


def cmd_compare(args: argparse.Namespace, reg: dict) -> int:
    base = _report_dir(reg)
    names = [s.strip() for s in args.systems.split(",")] if args.systems else list(reg["systems"])
    for name in names:
        cur = _load_json(base / name / "latest.json")
        prev = _load_json(base / name / "previous.json")
        if not cur:
            print(f"{name}: no baseline yet")
            continue
        comp = compare_runs(cur, prev)
        verdict = f"DEGRADED ({', '.join(comp['dropped'] + comp['unmet'])})" if comp["degraded"] else "no degradation"
        print(f"{name}: {cur.get('date')} vs {prev.get('date') if prev else '—'} — {verdict}")
        for lens in LENSES:
            print(f"  {LENS_LABELS[lens]:<13} {_fmt(cur['lenses'][lens]['score']):>4}  prev {_fmt(comp['prev_scores'][lens]):>4}  delta {_fmt_delta(comp['deltas'][lens])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=str(REGISTRY_PATH))
    sub = ap.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="evaluate systems, write baseline + reports")
    p_run.add_argument("--systems", help="comma-separated subset")
    p_run.add_argument("--facts", help="JSON file: {system: {fact: value}} for things the script cannot measure")
    p_run.add_argument("--no-network", action="store_true")
    p_run.add_argument("--timeout", type=int, default=600, help="seconds per check (default 600)")
    p_run.add_argument("--date", help="override today's date (YYYY-MM-DD)")
    p_run.add_argument("--email-body", action="store_true", help="print plain text instead of markdown")
    p_rep = sub.add_parser("report", help="print an existing combined report")
    p_rep.add_argument("--date")
    p_rep.add_argument("--email-body", action="store_true")
    p_cmp = sub.add_parser("compare", help="latest vs previous per system")
    p_cmp.add_argument("--systems")
    args = ap.parse_args(argv)
    reg = _load_json(Path(args.registry))
    if not reg or "systems" not in reg:
        print(f"registry unreadable: {args.registry}", file=sys.stderr)
        return 2
    return {"run": cmd_run, "report": cmd_report, "compare": cmd_compare}[args.command](args, reg)


if __name__ == "__main__":
    sys.exit(main())
