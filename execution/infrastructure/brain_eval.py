"""Weekly empirical evaluation of the workspace brain — independent of the system it grades.

description: Scores the brain (execution/infrastructure/brain.py) with an algorithm, not with the
             model that runs it, and refuses to let it hide its fault lines:
               * Benchmark: a frozen set of operator prompts written BLIND to the lessons
                 (.claude/brain/eval/benchmark.jsonl). An independent judge (Jev) labels which lessons
                 matter for each prompt; the keyword retriever is scored against those labels
                 (precision, recall, F1, effective recall incl. core, noise on negatives, chars/prompt).
                 Labels are cached per (prompt, lesson, rule text) so week-on-week deltas measure the
                 brain, not judge drift. Judge sanity is measured on the author's negatives.
               * Live outcomes: text-free observation rows written by the Stop hook (Jev relevance of
                 real injections, operator corrections per 100 turns, repeat mistakes = a correction an
                 EXISTING lesson covered, split into "never shown" vs "shown and ignored", capture leak).
               * Growth and health: lesson snapshot diff vs last run, lint issues, dead lessons,
                 unverifiable sources, core size.
               * Anti-cover-up: hash-chained append-only history; alarms when the benchmark, the
                 thresholds or the evaluator change ("goalposts moved") or evidence rows disappear;
                 verdict PASS/WARN/FAIL computed from thresholds.json; every fault line is printed first.
inputs: .claude/brain/lessons/*.md, .claude/brain/eval/{benchmark.jsonl,thresholds.json,labels.json,
        history.jsonl,observations/*.jsonl}; env OPENROUTER_API_KEY (only with --label).
outputs: .claude/brain/eval/reports/<date>.md, a history.jsonl row, labels.json (cache);
         .tmp/jev_ledger.jsonl rows (caller=brain_eval). Never writes lessons.

Usage:
    python3 execution/infrastructure/brain_eval.py run            # offline: cached labels only, spend 0
    python3 execution/infrastructure/brain_eval.py run --label    # label missing pairs with Jev (budget-guarded)
    python3 execution/infrastructure/brain_eval.py run --dry-run  # compute + print, write nothing
    python3 execution/infrastructure/brain_eval.py status         # last verdict + top fault line
    python3 execution/infrastructure/brain_eval.py verify         # history chain integrity only

Directive: directives/infrastructure/brain_eval.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from execution.infrastructure import (
    brain,
)  # noqa: E402  (system under test: read-only use)

REL_CUT = 0.5  # judge probability at which a lesson counts as relevant to a prompt
LIVE_WINDOW_DAYS = 7
DEFAULT_THRESHOLDS = {
    "floors": {
        "precision": 0.5,
        "recall": 0.4,
        "f1": 0.45,
        "effective_recall": 0.5,
        "judge_sanity": 0.75,
        "live_precision": 0.5,
    },
    "ceilings": {
        "noise_rate": 0.2,
        "avg_inject_chars": 700,
        "core_chars": 2200,
        "capture_leak": 0.25,
        "repeat_mistakes_week": 0,
        "label_coverage_gap": 0.05,
    },
    "regression": {
        "f1": 0.05,
        "precision": 0.05,
        "recall": 0.05,
        "effective_recall": 0.05,
        "noise_rate": 0.05,
        "live_precision": 0.1,
    },
    "fail_on": [
        "history_tampered",
        "evidence_deleted",
        "f1_regression",
        "core_over_cap",
        "recall_floor",
    ],
    "budget": {"max_jev_calls": 150, "max_usd": 0.10},
}


def eval_dir() -> Path:
    return brain.brain_dir() / "eval"


def sha(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def file_sha(p: Path) -> str:
    try:
        return sha(p.read_text(encoding="utf-8"))
    except OSError:
        return "missing"


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    rows.append({"_corrupt": line[:80]})
    except OSError:
        return []
    return rows


def thresholds() -> dict[str, Any]:
    p = eval_dir() / "thresholds.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------------------------
# labels (independent judge)
JUDGE_MODEL = "claude-sonnet-5-5"  # must never be the retriever's model (Jev): see assert_independent()


def assert_independent() -> None:
    if "jev" in JUDGE_MODEL.lower():
        raise SystemExit("refused: the judge may not be the model that picks lessons (self-grading)")


def label_key(prompt: str, les: brain.Lesson) -> str:
    return f"{JUDGE_MODEL}|{sha(prompt)}|{les.id}|{sha(les.rule, 8)}"


def load_labels() -> dict[str, float]:
    try:
        return json.loads((eval_dir() / "labels.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


JUDGE_SYSTEM = (
    "You audit a lesson-retrieval system. Given an operator prompt to a coding/business assistant and a numbered "
    "list of lessons learned from past mistakes, list the lessons that genuinely matter for doing THIS prompt's "
    "task correctly (ignoring it could repeat the mistake). Be strict: topical overlap is not enough. "
    'Reply with JSON only: {"relevant": ["L0", ...]} (empty list if none).'
)


def _judge_prompt(prompt: str, chunk: list[brain.Lesson]) -> tuple[dict[str, float], float, str]:
    from execution.modules import llm_client  # noqa: PLC0415

    menu = "\n".join(f"L{i}: {x.rule}" for i, x in enumerate(chunk))
    try:
        text = llm_client.chat_completion(system=JUDGE_SYSTEM, user_message=f"PROMPT:\n{prompt}\n\nLESSONS:\n{menu}",
                                          model=JUDGE_MODEL, max_tokens=300)
        m = re.search(r"\{.*\}", text or "", re.S)
        picked = set(json.loads(m.group(0)).get("relevant", [])) if m else None
    except Exception as exc:  # noqa: BLE001 — a failed judgement leaves the pair unlabelled (reported)
        return {}, 0.0, f"judge: {exc}"[:160]
    if picked is None:
        return {}, 0.0, f"judge returned no JSON: {str(text)[:80]}"
    return {label_key(prompt, x): (1.0 if f"L{i}" in picked else 0.0) for i, x in enumerate(chunk)}, 0.0, ""


def label_missing(prompts: list[str], lessons: list[brain.Lesson], labels: dict[str, float],
                  budget: dict[str, Any]) -> dict[str, Any]:
    """Fill missing (prompt, lesson) labels with the independent judge, inside the call budget."""
    assert_independent()
    info: dict[str, Any] = {"calls": 0, "usd": 0.0, "errors": [], "skipped_budget": 0, "available": True}
    jobs = [(p, [x for x in lessons if label_key(p, x) not in labels]) for p in prompts]
    jobs = [j for j in jobs if j[1]]
    max_calls = int(budget.get("max_judge_calls", 60))
    if len(jobs) > max_calls:
        info["skipped_budget"] = len(jobs) - max_calls
        jobs = jobs[:max_calls]
    with ThreadPoolExecutor(max_workers=4) as pool:  # results are returned, no shared state mutated
        results = list(pool.map(lambda j: _judge_prompt(*j), jobs))
    for got, usd, err in results:
        info["calls"] += 1
        info["usd"] += usd
        if err:
            info["errors"].append(err)
        labels.update(got)
    return info


def jev_picks(prompts: list[str], lessons: list[brain.Lesson]) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Run the deployed semantic retriever (Jev) once per benchmark prompt. Spends ~$0.0002/prompt."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        got = list(pool.map(lambda p: brain.jev_pick(p, lessons, set()), prompts))
    return dict(zip(prompts, got)), {"jev_calls": len(prompts), "jev_empty": sum(1 for g in got if not g)}


# ---------------------------------------------------------------------------------------------
# metrics
def benchmark_metrics(
    bench: list[dict[str, Any]], lessons: list[brain.Lesson], labels: dict[str, float],
    picks: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Score one retriever against the judge. picks=None -> keyword-only; else the deployed hybrid."""
    act = brain.active(lessons)
    core_ids = {x.id for x in brain.core(lessons)}
    tp = fp = fn = eff_hit = rel_total = 0
    labelled = total_pairs = 0
    neg_prompts = neg_noisy = 0
    author_neg = author_neg_clean = 0
    chars: list[int] = []
    misses: list[tuple[float, str, str]] = []
    noise: list[tuple[str, str]] = []
    relevant_any: set[str] = set()
    for row in bench:
        prompt = str(row.get("prompt", ""))
        rel: set[str] = set()
        complete = True
        for x in act:
            total_pairs += 1
            k = label_key(prompt, x)
            if k in labels:
                labelled += 1
                if labels[k] >= REL_CUT:
                    rel.add(x.id)
            else:
                complete = False
        relevant_any |= rel
        if picks is None:
            hits = brain.retrieve(prompt, lessons)
        else:
            hits = [(0.0, x) for _, x in brain.retrieve_hybrid(prompt, lessons, picks=picks.get(prompt, {}))]
        got = {x.id for _, x in hits}
        chars.append(sum(len(brain.bullet(x)) for _, x in hits))
        if row.get("kind") == "negative" and complete:
            author_neg += 1
            author_neg_clean += int(not rel)
        if not complete:
            continue
        tp += len(got & rel)
        fp += len(got - rel)
        fn += len(rel - got)
        rel_total += len(rel)
        eff_hit += len(rel & (got | core_ids))
        for lid in rel - got - core_ids:
            misses.append(
                (
                    labels[label_key(prompt, next(x for x in act if x.id == lid))],
                    row.get("id", "?"),
                    lid,
                )
            )
        for lid in got - rel:
            noise.append((row.get("id", "?"), lid))
        if not rel:
            neg_prompts += 1
            neg_noisy += int(bool(got))
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * prec * rec / (prec + rec)
        if prec and rec
        else (0.0 if prec is not None and rec is not None else None)
    )
    misses.sort(reverse=True)
    return {
        "precision": _r(prec),
        "recall": _r(rec),
        "f1": _r(f1),
        "effective_recall": _r(eff_hit / rel_total if rel_total else None),
        "noise_rate": _r(neg_noisy / neg_prompts if neg_prompts else None),
        "avg_inject_chars": _r(sum(chars) / len(chars) if chars else None, 1),
        "judge_sanity": _r(author_neg_clean / author_neg if author_neg else None),
        "label_coverage_gap": _r(1 - labelled / total_pairs if total_pairs else 0.0),
        "prompts": len(bench),
        "relevant_pairs": rel_total,
        "top_misses": [f"{b}->{lid} (judge {p:.2f})" for p, b, lid in misses[:8]],
        "top_noise": [f"{b}->{lid}" for b, lid in noise[:8]],
        "_relevant_any": sorted(relevant_any),
    }


def _r(v: float | None, n: int = 3) -> float | None:
    return None if v is None else round(v, n)


def live_metrics(obs: list[dict[str, Any]], since: str) -> dict[str, Any]:
    week = [o for o in obs if str(o.get("date", "")) >= since and "_corrupt" not in o]
    rel_vals = [p for o in week for p in (o.get("relevance") or {}).values()]
    injected = sum(len(o.get("injected") or []) for o in week)
    corrections = [o for o in week if o.get("correction")]
    repeats = [
        o
        for o in corrections
        if o.get("covered_by") and (o.get("covered_p") or 0) >= 0.6
    ]
    admitted = [o for o in week if o.get("admitted")]
    return {
        "turns_logged": len(week),
        "sessions": len({o.get("sid") for o in week}),
        "injections": injected,
        "judged_injections": len(rel_vals),
        "live_precision": _r(
            sum(1 for p in rel_vals if p >= REL_CUT) / len(rel_vals)
            if rel_vals
            else None
        ),
        "corrections": len(corrections),
        "repeat_mistakes_week": len(repeats),
        "repeat_never_shown": [
            o["covered_by"] for o in repeats if not o.get("covered_was_shown")
        ],
        "repeat_shown_ignored": [
            o["covered_by"] for o in repeats if o.get("covered_was_shown")
        ],
        "capture_leak": _r(
            sum(1 for o in admitted if not o.get("recorded")) / len(admitted)
            if admitted
            else None
        ),
        "unjudged_rows": sum(
            1
            for o in week
            if not o.get("judged") and (o.get("injected") or o.get("correction"))
        ),
        "corrupt_rows": sum(1 for o in obs if "_corrupt" in o),
    }


def source_check(lessons: list[brain.Lesson]) -> dict[str, list[str]]:
    import subprocess  # noqa: PLC0415

    missing, unverifiable = [], []
    for x in brain.active(lessons):
        src = (x.source or "").split()[0] if x.source else ""
        if not src:
            missing.append(x.id)
            continue
        path = src.split(":")[0]
        if (ROOT / path).exists():
            continue
        if all(c in "0123456789abcdef" for c in src.lower()) and 7 <= len(src) <= 40:
            r = subprocess.run(
                ["git", "-C", str(ROOT), "cat-file", "-e", f"{src}^{{commit}}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if r.returncode != 0:
                unverifiable.append(
                    x.id
                )  # shallow clone or bad sha: reported, never silently passed
            continue
        missing.append(x.id)
    return {"source_missing": missing, "source_unverifiable": unverifiable}


# ---------------------------------------------------------------------------------------------
# history (hash-chained, append-only)
def history_path() -> Path:
    return eval_dir() / "history.jsonl"


def row_hash(row: dict[str, Any]) -> str:
    body = {k: v for k, v in row.items() if k != "row_hash"}
    return sha(json.dumps(body, sort_keys=True), 16)


def verify_chain(rows: list[dict[str, Any]]) -> list[str]:
    problems, prev = [], "genesis"
    for i, r in enumerate(rows):
        if r.get("prev_hash") != prev:
            problems.append(f"row {i} ({r.get('date')}): prev_hash breaks the chain")
        if r.get("row_hash") != row_hash(r):
            problems.append(
                f"row {i} ({r.get('date')}): row edited after it was written"
            )
        prev = r.get("row_hash", "")
    return problems


# ---------------------------------------------------------------------------------------------
# verdict
def judge(
    k: dict[str, Any],
    prev: dict[str, Any] | None,
    th: dict[str, Any],
    ctx: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, fault_lines, alarm_codes). Pure function of numbers + thresholds."""
    faults: list[tuple[str, str, str]] = []  # (code, level, message)
    fail_on = set(th.get("fail_on", []))

    def add(code: str, msg: str) -> None:
        faults.append((code, "FAIL" if code in fail_on else "WARN", msg))

    for p in ctx["chain_problems"]:
        add("history_tampered", f"history: {p}")
    if ctx["obs_total"] < ctx["prev_obs_total"]:
        add(
            "evidence_deleted",
            f"observation rows fell from {ctx['prev_obs_total']} to {ctx['obs_total']}",
        )
    for name, cur, old in ctx["moved"]:
        add(
            "goalposts_moved",
            f"{name} changed since last run ({old} -> {cur}); deltas on it are not comparable",
        )
    for m, floor in th["floors"].items():
        v = k.get(m)
        if v is None:
            continue
        if v < floor:
            add(f"{m}_floor", f"{m} {v} below floor {floor}")
    for m, ceil in th["ceilings"].items():
        v = k.get(m)
        if v is None:
            continue
        if v > ceil:
            code = "core_over_cap" if m == "core_chars" else f"{m}_ceiling"
            add(code, f"{m} {v} above ceiling {ceil}")
    if prev and not ctx["benchmark_moved"]:
        for m, tol in th["regression"].items():
            a, b = k.get(m), (prev.get("kpis") or {}).get(m)
            if a is None or b is None:
                continue
            worse = (a - b) if m == "noise_rate" else (b - a)
            if worse > tol:
                add(f"{m}_regression", f"{m} regressed {b} -> {a} (tolerance {tol})")
    for lid in k.get("repeat_never_shown", []):
        add(
            "repeat_missed_retrieval",
            f"repeat mistake covered by {lid}, but the brain never showed it (trigger gap)",
        )
    for lid in k.get("repeat_shown_ignored", []):
        add(
            "repeat_ignored",
            f"repeat mistake covered by {lid}, shown in-session and still ignored (rule wording/force gap)",
        )
    for name in ("precision", "recall", "f1", "live_precision", "capture_leak"):
        if k.get(name) is None:
            add(
                "unmeasured",
                f"{name} unmeasured this run (no labelled data); not counted as a pass",
            )
    for lid in k.get("dead_lessons", []):
        add(
            "dead_lesson",
            f"{lid}: relevant to no benchmark prompt and never injected live",
        )
    for lid in k.get("source_missing", []):
        add("source_missing", f"{lid}: source path/sha not found")
    for lid in k.get("lint_issues", []):
        add("lint", f"lint: {lid}")
    order = {"FAIL": 0, "WARN": 1}
    faults.sort(key=lambda f: (order[f[1]], f[0]))
    verdict = (
        "FAIL"
        if any(f[1] == "FAIL" for f in faults)
        else (
            "WARN"
            if any(
                f[1] == "WARN" and f[0] not in ("unmeasured", "dead_lesson")
                for f in faults
            )
            else ("PASS-PARTIAL" if any(f[0] == "unmeasured" for f in faults) else "PASS")
        )
    )
    return (
        verdict,
        [f"[{lvl}] {msg}" for _, lvl, msg in faults],
        sorted({c for c, _, _ in faults}),
    )


# ---------------------------------------------------------------------------------------------
def run(label: bool, dry_run: bool) -> tuple[str, dict[str, Any]]:
    today = brain.today().isoformat()
    lessons, errors = brain.load()
    act = brain.active(lessons)
    bench = read_jsonl(eval_dir() / "benchmark.jsonl")
    th = thresholds()
    labels = load_labels()
    spend: dict[str, Any] = {
        "calls": 0,
        "usd": 0.0,
        "errors": [],
        "skipped_budget": 0,
        "available": None,
    }
    prompts = [str(b.get("prompt", "")) for b in bench]
    picks = None
    if label and bench:
        spend = label_missing(prompts, act, labels, th.get("budget", {}))
        picks, pinfo = jev_picks(prompts, lessons)
        spend.update(pinfo)
        if pinfo["jev_empty"] == len(prompts):
            picks = None  # Jev unavailable: hybrid cannot be measured this run
            spend["errors"].append("Jev returned nothing for every prompt: hybrid unmeasured")

    kw = benchmark_metrics(bench, lessons, labels)
    bm = benchmark_metrics(bench, lessons, labels, picks) if picks is not None else {
        **kw, **{m: None for m in ("precision", "recall", "f1", "effective_recall", "noise_rate", "avg_inject_chars")}}
    obs_rows: list[dict[str, Any]] = []
    for p in sorted((eval_dir() / "observations").glob("*.jsonl")):
        obs_rows += read_jsonl(p)
    since = (
        brain.today() - __import__("datetime").timedelta(days=LIVE_WINDOW_DAYS)
    ).isoformat()
    lm = live_metrics(obs_rows, since)
    live_ever = {i for o in obs_rows for i in (o.get("injected") or [])}
    core = brain.core(lessons)
    rep = brain.lint(lessons, errors)
    src = source_check(lessons)

    history = read_jsonl(history_path())
    prev = history[-1] if history else None
    snapshot = {x.id: x.strength for x in act}
    prev_snap = (prev or {}).get("snapshot", {})
    hashes = {
        "benchmark": file_sha(eval_dir() / "benchmark.jsonl"),
        "thresholds": file_sha(eval_dir() / "thresholds.json"),
        "evaluator": file_sha(Path(__file__)),
        "brain": file_sha(Path(brain.__file__)),
    }
    moved = [
        (n, hashes[n], (prev or {}).get("hashes", {}).get(n))
        for n in ("benchmark", "thresholds", "evaluator")
        if prev and (prev.get("hashes") or {}).get(n) not in (None, hashes[n])
    ]
    kpis: dict[str, Any] = {
        **{k: v for k, v in bm.items() if not k.startswith("_")},
        **{f"kw_{m}": kw[m] for m in ("precision", "recall", "f1", "effective_recall", "noise_rate")},
        **lm,
        "active": len(act),
        "core": len(core),
        "core_chars": sum(len(brain.bullet(x)) for x in core),
        "added": sorted(set(snapshot) - set(prev_snap)) if prev else [],
        "strengthened": sorted(
            i for i in snapshot if i in prev_snap and snapshot[i] > prev_snap[i]
        ),
        "retired": sorted(set(prev_snap) - set(snapshot)) if prev else [],
        "dead_lessons": (
            sorted(
                i
                for i in snapshot
                if i not in bm["_relevant_any"] and i not in live_ever
            )
            if bm["label_coverage_gap"] == 0
            else []
        ),
        "lint_issues": [str(e) for e in rep["errors"]]
        + [f"duplicate {a} ~ {b}" for a, b, *_ in rep["duplicates"]],
        **src,
    }
    ctx = {
        "chain_problems": verify_chain(history),
        "obs_total": len(obs_rows),
        "prev_obs_total": int((prev or {}).get("obs_total", 0)),
        "moved": moved,
        "benchmark_moved": any(n == "benchmark" for n, *_ in moved),
    }
    verdict, faults, codes = judge(kpis, prev, th, ctx)
    if spend["errors"]:
        faults.append("[WARN] judge errors: " + "; ".join(spend["errors"][:3]))
    if spend.get("skipped_budget"):
        faults.append(
            f"[WARN] {spend['skipped_budget']} label calls skipped by the budget guard"
        )

    row = {
        "date": today,
        "verdict": verdict,
        "codes": codes,
        "kpis": kpis,
        "snapshot": snapshot,
        "hashes": hashes,
        "obs_total": len(obs_rows),
        "spend_usd": round(spend["usd"], 6),
        "prev_hash": (
            (prev or {}).get("row_hash", "genesis")
            if not ctx["chain_problems"]
            else "rechained-after-tamper"
        ),
    }
    row["row_hash"] = row_hash(row)
    report = render(row, prev, faults, spend)
    if not dry_run:
        eval_dir().mkdir(parents=True, exist_ok=True)
        (eval_dir() / "labels.json").write_text(
            json.dumps(labels, sort_keys=True, indent=0) + "\n", encoding="utf-8"
        )
        if not (eval_dir() / "thresholds.json").exists():
            (eval_dir() / "thresholds.json").write_text(
                json.dumps(DEFAULT_THRESHOLDS, indent=2) + "\n", encoding="utf-8"
            )
        with history_path().open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        rd = eval_dir() / "reports"
        rd.mkdir(exist_ok=True)
        (rd / f"{today}.md").write_text(report, encoding="utf-8", newline="\n")
    return report, row


def _fmt(v: Any) -> str:
    if v is None:
        return "unmeasured"
    if isinstance(v, list):
        return str(len(v))
    return str(v)


KPI_ORDER = ["precision", "recall", "f1", "effective_recall", "noise_rate", "avg_inject_chars", "kw_precision", "kw_recall", "kw_f1", "kw_effective_recall", "kw_noise_rate", "judge_sanity", "label_coverage_gap", "live_precision", "corrections", "repeat_mistakes_week", "capture_leak", "turns_logged", "sessions", "active", "core", "core_chars", "added", "strengthened", "retired", "dead_lessons"]


def render(
    row: dict[str, Any],
    prev: dict[str, Any] | None,
    faults: list[str],
    spend: dict[str, Any],
) -> str:
    k, pk = row["kpis"], (prev or {}).get("kpis", {})
    lines = [
        f"# Brain eval {row['date']}: {row['verdict']}",
        "",
        "## Fault lines (printed first, never filtered)",
        "",
    ]
    lines += [f"- {f}" for f in faults] or ["- none"]
    lines += [
        "",
        "## KPIs",
        "",
        "| KPI | this run | last run | delta |",
        "|---|---|---|---|",
    ]
    for name in KPI_ORDER:
        a, b = k.get(name), pk.get(name) if prev else None
        delta = ""
        if (
            isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and not isinstance(a, bool)
        ):
            delta = f"{a - b:+.3f}".rstrip("0").rstrip(".")
        lines.append(
            f"| {name} | {_fmt(a)} | {_fmt(b) if prev else 'n/a (first run)'} | {delta} |"
        )
    lines += [
        "",
        "## Evidence",
        "",
        f"- Benchmark misses (relevant per judge, not shown): {', '.join(k.get('top_misses', [])) or 'none'}",
        f"- Benchmark noise (shown, judged irrelevant): {', '.join(k.get('top_noise', [])) or 'none'}",
        f"- Repeat mistakes, never shown: {', '.join(k.get('repeat_never_shown', [])) or 'none'}; "
        f"shown and ignored: {', '.join(k.get('repeat_shown_ignored', [])) or 'none'}",
        f"- Added: {', '.join(k.get('added', [])) or 'none'}; strengthened: "
        f"{', '.join(k.get('strengthened', [])) or 'none'}; retired: {', '.join(k.get('retired', [])) or 'none'}",
        f"- Sources unverifiable in this clone: {len(k.get('source_unverifiable', []))}",
        f"- Judge: {spend.get('calls', 0)} Sonnet calls (subscription, $0); retriever replay: {spend.get('jev_calls', 0)} Jev calls",
        "",
        "## Standing caveats (true every run)",
        "",
        "- The judge is Claude Sonnet (subscription), never the Jev retriever it grades; its sanity on the author's negatives is reported above, and a low "
        "value means every benchmark number is suspect.",
        "- The benchmark is visible in the repo, so triggers could be overfitted to it; the live precision "
        "and repeat-mistake numbers are the check on that.",
        "- Live numbers only cover turns whose sessions committed their observation rows.",
        "",
        f"history row {row['row_hash']} (prev {row['prev_hash']})",
        "",
    ]
    return "\n".join(lines)


def status() -> str:
    hist = read_jsonl(history_path())
    if not hist:
        return "brain eval: never run"
    last = hist[-1]
    rp = eval_dir() / "reports" / f"{last.get('date')}.md"
    top = ""
    try:
        for line in rp.read_text(encoding="utf-8").splitlines():
            if line.startswith("- [FAIL]") or line.startswith("- [WARN]"):
                top = line[2:]
                break
    except OSError:
        top = "(report file missing)"
    return f"brain eval {last.get('date')}: {last.get('verdict')}" + (
        f" — {top}" if top else ""
    )


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="brain_eval.py")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("run")
    p.add_argument(
        "--label",
        action="store_true",
        help="label missing pairs with Jev (spends, budget-guarded)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="compute and print; write nothing"
    )
    sub.add_parser("status")
    sub.add_parser("verify")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        report, row = run(a.label, a.dry_run)
        print(report)
        return 2 if row["verdict"] == "FAIL" else 0
    if a.cmd == "verify":
        probs = verify_chain(read_jsonl(history_path()))
        print("\n".join(probs) or "history chain intact")
        return 1 if probs else 0
    print(status())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
