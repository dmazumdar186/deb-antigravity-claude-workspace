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
    "floors": {"precision": 0.5, "recall": 0.4, "f1": 0.45, "effective_recall": 0.5, "judge_sanity": 0.75,
               "live_precision_kw": 0.5},
    "ceilings": {"noise_rate": 0.2, "avg_inject_chars": 700, "core_chars": 2200, "capture_leak": 0.25,
                 "repeat_mistakes_week": 0, "label_coverage_gap": 0.0},
    # tolerance per metric; the evaluator widens it to 2 standard errors when the sample is small
    "regression": {"f1": 0.05, "precision": 0.05, "recall": 0.05, "effective_recall": 0.05,
                   "noise_rate": 0.05, "live_precision_kw": 0.1, "kw_f1": 0.05},
    "overfit_trigger_overlap_jump": 0.1,
    "fail_on": ["history_tampered", "evidence_deleted", "goalposts_moved", "f1_regression", "f1_drift",
                "core_over_cap", "recall_floor"],
    "budget": {"max_judge_calls": 60, "max_jev_calls": 60, "max_usd": 0.10},
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


def bench_meta() -> dict[str, Any]:
    try:
        return json.loads((eval_dir() / "benchmark_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


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
    # The judge's instructions are part of the key: changing JUDGE_SYSTEM relabels everything.
    return f"{JUDGE_MODEL}|{sha(JUDGE_SYSTEM, 6)}|{sha(prompt)}|{les.id}|{sha(les.rule, 8)}"


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
        # Mirror hook_prompt: core lessons are injected at session start, so live retrieval excludes them.
        core_ids = {x.id for x in brain.core(lessons)}
        got = list(pool.map(lambda p: brain.jev_pick(p, lessons, core_ids), prompts))
    return dict(zip(prompts, got)), {"jev_calls": len(prompts), "jev_empty": sum(1 for g in got if not g)}


# ---------------------------------------------------------------------------------------------
# metrics
def benchmark_metrics(
    bench: list[dict[str, Any]], lessons: list[brain.Lesson], labels: dict[str, float],
    picks: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Score one retriever against the judge. picks=None -> keyword-only; else the deployed hybrid.
    Scores every LABELLED (prompt, lesson) pair; an unlabelled pair is skipped and counted, never
    allowed to blank the prompt (one edited rule must not erase the benchmark)."""
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
    partly_unlabelled: set[str] = set()
    for row in bench:
        prompt = str(row.get("prompt", ""))
        rel: set[str] = set()
        unl: set[str] = set()
        for x in act:
            total_pairs += 1
            k = label_key(prompt, x)
            if k in labels:
                labelled += 1
                if labels[k] >= REL_CUT:
                    rel.add(x.id)
            else:
                unl.add(x.id)
        partly_unlabelled |= unl
        relevant_any |= rel
        # Score the retriever as deployed: hook_prompt excludes the core lessons (already injected at session
        # start), so they never compete for the per-prompt slots. Before 2026-11-13 the replay let core compete,
        # which measured a retriever that does not exist (32 of 51 hits in a 2026-11-13 replay were always-loaded core lessons).
        if picks is None:
            hits = brain.retrieve(prompt, lessons, exclude=core_ids)
        else:
            hits = [(0.0, x) for _, x in brain.retrieve_hybrid(prompt, lessons, exclude=core_ids,
                                                                picks=picks.get(prompt, {}))]
        got = {x.id for _, x in hits}
        chars.append(sum(len(brain.bullet(x)) for _, x in hits))
        got_l = got - unl
        if row.get("kind") == "negative" and not unl:
            author_neg += 1
            author_neg_clean += int(not rel)
        rel_nc = rel - core_ids  # per-prompt retrieval is only responsible for non-core lessons
        tp += len(got_l & rel_nc)
        fp += len(got_l - rel)
        fn += len(rel_nc - got)
        rel_total += len(rel)
        eff_hit += len(rel & (got | core_ids))
        by_id = {x.id: x for x in act}
        for lid in sorted(rel - got - core_ids):
            neg = " (author negative: judge disagreed with the author, not a retrieval miss)" if row.get("kind") == "negative" else ""
            misses.append((labels[label_key(prompt, by_id[lid])], row.get("id", "?"), lid + neg))
        for lid in sorted(got_l - rel):
            noise.append((row.get("id", "?"), lid))
        if not rel and not unl:
            neg_prompts += 1
            neg_noisy += int(bool(got))
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    misses.sort(reverse=True)
    return {
        "precision": _r(prec), "recall": _r(rec), "f1": _r(f1),
        "effective_recall": _r(eff_hit / rel_total if rel_total else None),
        "noise_rate": _r(neg_noisy / neg_prompts if neg_prompts else None),
        "avg_inject_chars": _r(sum(chars) / len(chars) if chars else None, 1),
        "judge_sanity": _r(author_neg_clean / author_neg if author_neg else None),
        "label_coverage_gap": _r(1 - labelled / total_pairs if total_pairs else 0.0),
        "unlabelled_pairs": total_pairs - labelled,
        "n_ret": tp + fp, "n_rel": tp + fn, "n_neg": neg_prompts,
        "prompts": len(bench), "relevant_pairs": rel_total,
        "n_missed": fn, "n_missed_noncore": len(misses), "n_noise": len(noise),
        "n_missed_on_negatives": sum(1 for _, _, lid in misses if "author negative" in lid),
        "top_misses": [f"{b}->{lid} (judge {p:.2f})" for p, b, lid in misses[:8]],
        "top_noise": [f"{b}->{lid}" for b, lid in noise[:8]],
        "_all_misses": [f"{b}->{lid} (judge {p:.2f})" for p, b, lid in misses],
        "_all_noise": [f"{b}->{lid}" for b, lid in noise],
        "_relevant_any": sorted(relevant_any),
        "_partly_unlabelled": sorted(partly_unlabelled),
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
        "jev_picked_injections": sum(
            1 for o in week for i in (o.get("injected") or []) if (o.get("sources") or {}).get(i) == "jev"),
        "live_precision_kw": _r(
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
def _git(*args: str) -> tuple[int, str]:
    import subprocess  # noqa: PLC0415

    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def git_anchor(history: list[dict[str, Any]], obs_total: int) -> list[tuple[str, str]]:
    """Compare the working copy with what git already holds, so deleting or truncating the history or
    the evidence cannot start a clean chain. Only for the real brain dir (tests use temp dirs)."""
    try:
        rel = eval_dir().resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return []
    out: list[tuple[str, str]] = []
    code, committed = _git("show", f"HEAD:{rel}/history.jsonl")
    if code == 0 and committed.strip():
        old = [json.loads(ln).get("row_hash") for ln in committed.splitlines() if ln.strip()]
        cur = [r.get("row_hash") for r in history]
        if cur[: len(old)] != old:
            out.append(("history_tampered", f"history.jsonl no longer starts with the {len(old)} rows committed at HEAD"))
    code, deleted = _git("log", "--diff-filter=D", "--format=%h %ad", "--date=short", "--", f"{rel}/history.jsonl")
    if code == 0 and deleted.strip():
        out.append(("evidence_deleted", f"history.jsonl was deleted in commit {deleted.split()[0]}"))
    code, counts = _git("grep", "-c", "", "HEAD", "--", f"{rel}/observations")
    if code == 0:
        committed_rows = sum(int(ln.rsplit(":", 1)[1]) for ln in counts.splitlines() if ln.rsplit(":", 1)[-1].isdigit())
        if obs_total < committed_rows:
            out.append(("evidence_deleted", f"observation rows {obs_total} < {committed_rows} committed at HEAD"))
    return out


BENCH_METRICS = {"precision", "recall", "f1", "effective_recall", "noise_rate", "avg_inject_chars", "judge_sanity",
                 "kw_precision", "kw_recall", "kw_f1", "kw_effective_recall", "kw_noise_rate", "trigger_overlap"}
SAMPLE_N = {"precision": "n_ret", "recall": "n_rel", "f1": "n_rel", "effective_recall": "n_rel",
            "noise_rate": "n_neg", "kw_precision": "kw_n_ret", "kw_recall": "kw_n_rel", "kw_f1": "kw_n_rel",
            "live_precision_kw": "judged_injections"}


def reference(history: list[dict[str, Any]], metric: str, today: str, bench_hash: str, *, oldest: bool = False,
              min_age_days: int = 6) -> dict[str, Any] | None:
    """Row to compare `metric` against: the most recent row at least `min_age_days` old where the metric was
    measured (so an unmeasured week or a same-day re-run cannot reset the baseline), else the most recent
    measured row. Benchmark metrics only compare with rows on the same benchmark. oldest=True -> first ever."""
    import datetime as _dt  # noqa: PLC0415

    rows = [r for r in history if (r.get("kpis") or {}).get(metric) is not None
            and (metric not in BENCH_METRICS or (r.get("hashes") or {}).get("benchmark") == bench_hash)]
    if not rows:
        return None
    if oldest:
        return rows[0]
    cutoff = (_dt.date.fromisoformat(today) - _dt.timedelta(days=min_age_days)).isoformat()
    aged = [r for r in rows if str(r.get("date", "")) <= cutoff]
    return aged[-1] if aged else rows[-1]


def tolerance(metric: str, base: float, k: dict[str, Any], ref: dict[str, Any]) -> float:
    """Configured tolerance, widened to 2 standard errors of a proportion on the smaller sample."""
    import math  # noqa: PLC0415

    n_key = SAMPLE_N.get(metric)
    n = min(int(k.get(n_key) or 0), int((ref.get("kpis") or {}).get(n_key) or 0)) if n_key else 0
    p = (ref.get("kpis") or {}).get(metric)
    if n <= 0 or not isinstance(p, (int, float)) or metric == "avg_inject_chars":
        return base
    return max(base, 2 * math.sqrt(max(p * (1 - p), 0.01) / n))


def judge(
    k: dict[str, Any],
    history: list[dict[str, Any]],
    th: dict[str, Any],
    ctx: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, fault_lines, alarm_codes). Pure function of numbers, history and thresholds.
    An alarm code acknowledged with --ack (in this run or an earlier history row) drops from FAIL to WARN
    but is still printed with its reason."""
    faults: list[tuple[str, str, str]] = []  # (code, level, message)
    fail_on = set(th.get("fail_on", []))
    acked = {a.get("code") for r in history for a in (r.get("acks") or [])} | {a["code"] for a in ctx.get("acks", [])}

    def add(code: str, msg: str) -> None:
        level = "FAIL" if code in fail_on and code not in acked else "WARN"
        faults.append((code, level, msg + (" (acknowledged)" if code in acked and code in fail_on else "")))

    for p in ctx["chain_problems"]:
        add("history_tampered", f"history: {p}")
    for code, msg in ctx.get("anchor", []):
        add(code, msg)
    if ctx["obs_total"] < ctx["prev_obs_total"]:
        add("evidence_deleted", f"observation rows fell from {ctx['prev_obs_total']} to {ctx['obs_total']}")
    if not history and ctx.get("orphan_reports"):
        add("evidence_deleted", f"no history but {ctx['orphan_reports']} earlier report(s) exist: history was removed")
    for name, cur, old in ctx["moved"]:
        add("goalposts_moved", f"{name} changed since last run ({old} -> {cur}); acknowledge with --ack if intended")
    for m, floor in th["floors"].items():
        v = k.get(m)
        if v is not None and v < floor:
            add(f"{m}_floor", f"{m} {v} below floor {floor}")
        elif v is not None and SAMPLE_N.get(m) and k.get(SAMPLE_N[m]):
            import math  # noqa: PLC0415
            se = math.sqrt(max(v * (1 - v), 0.01) / int(k[SAMPLE_N[m]]))
            if v - floor < se:
                fails = " (a FAIL code)" if f"{m}_floor" in fail_on else ""
                add("near_floor", f"{m} {v} clears its {floor} floor{fails} by {v - floor:.3f}, under one standard "
                                  f"error ({se:.3f}): a re-run of Jev's picks can cross it")
    for m, ceil in th["ceilings"].items():
        v = k.get(m)
        if v is not None and v > ceil:
            add("core_over_cap" if m == "core_chars" else f"{m}_ceiling", f"{m} {v} above ceiling {ceil}")
    for m, base in th["regression"].items():
        a = k.get(m)
        if a is None:
            continue
        for oldest, code in ((False, f"{m}_regression"), (True, f"{m}_drift")):
            ref = reference(history, m, ctx.get("today", brain.today().isoformat()), ctx.get("bench_hash", ""), oldest=oldest)
            if not ref:
                continue
            b = ref["kpis"][m]
            tol = tolerance(m, base, k, ref) * (2 if oldest else 1)
            worse = (a - b) if m == "noise_rate" else (b - a)
            if worse > tol:
                what = "since the first baseline" if oldest else f"vs {ref.get('date')}"
                add(code, f"{m} {b} -> {a} {what} (tolerance {tol:.3f})")
    ref = reference(history, "trigger_overlap", ctx.get("today", brain.today().isoformat()), ctx.get("bench_hash", ""))
    if not ref and k.get("trigger_overlap") is not None:
        add("possible_overfit", f"trigger_overlap {k['trigger_overlap']}: share of active lessons with a trigger found "
                                f"verbatim in the benchmark; no earlier run to compare, so overfitting cannot be ruled out")
    for lid in k.get("lessons_after_freeze", []):
        add("possible_overfit", f"{lid} was written on/after the benchmark freeze date; its triggers could fit the benchmark")
    if ref and k.get("trigger_overlap") is not None:
        jump = k["trigger_overlap"] - ref["kpis"]["trigger_overlap"]
        if jump > float(th.get("overfit_trigger_overlap_jump", 0.1)):
            add("possible_overfit", f"lessons with a trigger copied from a benchmark prompt rose by {jump:.2f}")
    for lid in k.get("repeat_never_shown", []):
        add("repeat_missed_retrieval", f"repeat mistake covered by {lid}, but the brain never showed it (recall gap)")
    for lid in k.get("repeat_shown_ignored", []):
        add("repeat_ignored", f"repeat mistake covered by {lid}, shown in-session and still ignored (wording/force gap)")
    for lid in k.get("retired_unexplained", []):
        add("retired_without_supersede", f"{lid} left the brain without a superseding lesson (decay or deletion): confirm")
    for err in ctx.get("judge_errors", []):
        add("judge_errors", f"judge/retriever error: {err}")
    if ctx.get("skipped_budget"):
        add("budget_skipped", f"{ctx['skipped_budget']} label calls skipped by the budget guard")
    for name in ("precision", "recall", "f1"):
        if k.get(name) is None:
            add("unmeasured", f"{name} unmeasured this run (benchmark not labelled or Jev replay failed); not a pass")
    if k.get("live_precision_kw") is None:
        add("unmeasured", f"live_precision_kw unmeasured: {k.get('injections', 0)} live injections in "
                          f"{k.get('turns_logged', 0)} turn(s), {k.get('jev_picked_injections', 0)} Jev-picked (never "
                          f"self-graded), {k.get('judged_injections', 0)} judged; not a pass")
    if k.get("capture_leak") is None:
        add("unmeasured", "capture_leak unmeasured: no admitted misses logged this week; not a pass")
    if not k.get("corrections"):
        add("unmeasured", f"repeat-mistake rate unmeasured: 0 operator corrections in {k.get('turns_logged', 0)} "
                          f"logged turn(s), so a 0 here is no evidence")
    if k.get("unlabelled_pairs"):
        add("unmeasured", f"{k['unlabelled_pairs']} benchmark pairs unlabelled (run with --label)")
    for lid in k.get("dead_lessons", []):
        add("dead_lesson", f"{lid}: relevant to no benchmark prompt and not injected in the "
                           f"{k.get('turns_logged_ever', 0)} live turn(s) logged so far")
    for lid in k.get("source_missing", []):
        add("source_missing", f"{lid}: source path/sha not found")
    for lid in k.get("lint_issues", []):
        add("lint", f"lint: {lid}")
    order = {"FAIL": 0, "WARN": 1}
    faults.sort(key=lambda f: (order[f[1]], f[0]))
    soft = ("unmeasured", "dead_lesson")
    if any(f[1] == "FAIL" for f in faults):
        verdict = "FAIL"
    elif any(f[1] == "WARN" and f[0] not in soft for f in faults):
        verdict = "WARN"
    else:
        verdict = "PASS-PARTIAL" if any(f[0] == "unmeasured" for f in faults) else "PASS"
    return verdict, [f"[{lvl}] {msg}" for _, lvl, msg in faults], sorted({c for c, _, _ in faults})


# ---------------------------------------------------------------------------------------------
def run(label: bool, dry_run: bool, acks: list[str] | None = None,
        notes: list[str] | None = None) -> tuple[str, dict[str, Any]]:
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
    pairs_total = len(prompts) * len(act)
    pairs_cached = sum(1 for pr in prompts for x in act if label_key(pr, x) in labels)
    picks = None
    if label and bench:
        spend = label_missing(prompts, act, labels, th.get("budget", {}))
        before = brain._spent_today()
        picks, pinfo = jev_picks(prompts, lessons)
        pinfo["jev_usd"] = round(max(0.0, brain._spent_today() - before), 6)
        spend.update(pinfo)
        if pinfo["jev_empty"] == len(prompts):
            picks = None  # Jev unavailable: hybrid cannot be measured this run
            spend["errors"].append("Jev returned nothing for every prompt: hybrid unmeasured")

    spend.setdefault("errors", [])
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
    bench_text = " ".join(prompts)
    bench_norm = brain.norm(bench_text)
    overlap = sum(1 for x in act if any(brain.norm(t).strip() and brain.norm(t) in bench_norm for t in x.triggers))
    snapshot = {x.id: x.strength for x in act}
    prev_snap = (prev or {}).get("snapshot", {})
    hashes = {
        "benchmark": file_sha(eval_dir() / "benchmark.jsonl") + file_sha(eval_dir() / "benchmark_meta.json")[:4],
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
        **{f"kw_{m}": kw[m] for m in ("precision", "recall", "f1", "effective_recall", "noise_rate", "n_ret", "n_rel")},
        "trigger_overlap": _r(overlap / len(act) if act else None),
        "lessons_after_freeze": sorted(x.id for x in act if bench_meta().get("frozen") and x.created >= bench_meta()["frozen"]),
        "turns_logged_ever": len(obs_rows),
        **lm,
        "active": len(act),
        "core": len(core),
        "core_chars": sum(len(brain.bullet(x)) for x in core),
        "added": sorted(set(snapshot) - set(prev_snap)) if prev else [],
        "strengthened": sorted(
            i for i in snapshot if i in prev_snap and snapshot[i] > prev_snap[i]
        ),
        "retired": sorted(set(prev_snap) - set(snapshot)) if prev else [],
        "retired_unexplained": sorted(
            i for i in (set(prev_snap) - set(snapshot)) if not any(i in x.supersedes for x in act)) if prev else [],
        "dead_lessons": sorted(
            i for i in snapshot
            if i not in bm["_relevant_any"] and i not in kw["_relevant_any"]
            and i not in kw["_partly_unlabelled"] and i not in live_ever
        ),
        "all_misses": bm.get("_all_misses", []),
        "all_noise": bm.get("_all_noise", []),
        "lint_issues": [str(e) for e in rep["errors"]]
        + [f"duplicate {a} ~ {b}" for a, b, *_ in rep["duplicates"]],
        **src,
    }
    ack_rows = [{"code": c.split(":", 1)[0].strip(), "reason": c.split(":", 1)[1].strip() if ":" in c else ""}
                for c in (acks or [])]
    ctx = {
        "chain_problems": verify_chain(history),
        "anchor": git_anchor(history, len(obs_rows)),
        "orphan_reports": len(list((eval_dir() / "reports").glob("*.md"))) if (eval_dir() / "reports").is_dir() else 0,
        "obs_total": len(obs_rows),
        "prev_obs_total": int((prev or {}).get("obs_total", 0)),
        "moved": moved,
        "today": today,
        "bench_hash": hashes["benchmark"],
        "acks": ack_rows,
        "judge_errors": list(spend.get("errors", [])),
        "skipped_budget": spend.get("skipped_budget", 0),
    }
    verdict, faults, codes = judge(kpis, history, th, ctx)

    row = {
        "date": today,
        "verdict": verdict,
        "codes": codes,
        "kpis": kpis,
        "snapshot": snapshot,
        "hashes": hashes,
        "obs_total": len(obs_rows),
        "spend_usd": round(spend["usd"] + float(spend.get("jev_usd", 0) or 0), 6),
        "notes": list(notes or []),
        "acks": ack_rows,
        "prev_hash": (
            (prev or {}).get("row_hash", "genesis")
            if not ctx["chain_problems"]
            else "rechained-after-tamper"
        ),
    }
    spend["pairs_total"], spend["pairs_cached"] = pairs_total, pairs_cached
    body = render(row, prev, faults, spend, bm)
    row["report_sha"] = sha(body)
    row["row_hash"] = row_hash(row)
    report = body  # the chain hash lives in history.jsonl, not in the operator's report
    if not dry_run:
        eval_dir().mkdir(parents=True, exist_ok=True)
        live_keys = {label_key(pr, x) for pr in prompts for x in act}
        (eval_dir() / "labels.json").write_text(  # keep only labels the current benchmark x lessons use
            json.dumps({k2: v for k2, v in labels.items() if k2 in live_keys}, sort_keys=True, indent=0) + "\n",
            encoding="utf-8")
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


KPI_ORDER = ["precision", "recall", "f1", "effective_recall", "noise_rate", "avg_inject_chars", "kw_precision", "kw_recall", "kw_f1", "kw_effective_recall", "kw_noise_rate", "judge_sanity", "label_coverage_gap", "live_precision_kw", "corrections", "repeat_mistakes_week", "capture_leak", "turns_logged", "injections", "jev_picked_injections", "judged_injections", "unjudged_rows", "sessions", "active", "core", "core_chars", "added", "strengthened", "retired", "dead_lessons", "trigger_overlap", "unlabelled_pairs"]


DISPLAY = {"effective_recall": "effective_recall (incl. always-loaded core)",
           "noise_rate": "noise_rate (negative prompts that still got an injection)",
           "kw_noise_rate": "kw_noise_rate (negative prompts that still got an injection)",
           "kw_effective_recall": "kw_effective_recall (incl. always-loaded core)"}


def render(
    row: dict[str, Any],
    prev: dict[str, Any] | None,
    faults: list[str],
    spend: dict[str, Any],
    bm: dict[str, Any] | None = None,
) -> str:
    k, pk = row["kpis"], (prev or {}).get("kpis", {})
    bm = bm or {}
    first = "n/a (first committed run)"
    lines = [f"# Brain eval {row['date']}: {row['verdict']}", "", "## Fault lines (printed first)", ""]
    lines += [f"- {f}" for f in faults] or ["- none"]
    if row.get("notes"):
        lines += ["", "## Run notes", ""] + [f"- {n}" for n in row["notes"]]
    lines += ["", "## KPIs", "", "| KPI | this run | last run | delta |", "|---|---|---|---|"]
    no_evidence = not k.get("corrections")
    for name in KPI_ORDER:
        a, b = k.get(name), pk.get(name) if prev else None
        delta = ""
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            delta = f"{a - b:+.3f}".rstrip("0").rstrip(".")
        shown = _fmt(a)
        if name in ("corrections", "repeat_mistakes_week") and no_evidence:
            shown += f" ({k.get('turns_logged', 0)} turn(s), 0 corrections: no evidence)"
        lines.append(f"| {DISPLAY.get(name, name)} | {shown} | {_fmt(b) if prev else first} | {delta} |")
    f1_tol = tolerance("f1", float(thresholds()["regression"].get("f1", 0.05)), k, {"kpis": k})
    checks = "present" if k.get("live_precision_kw") is not None and k.get("corrections") else "absent this run"
    lines += [
        "", "## Evidence", "",
        f"- Benchmark misses ({min(8, k.get('n_missed_noncore', 0))} of {k.get('n_missed_noncore', 0)} misses outside "
        f"the core; {k.get('n_missed', 0)} of {k.get('n_rel', 0)} relevant pairs not retrieved, "
        f"{k.get('n_missed_on_negatives', 0)} of them on author-negative prompts where the judge disagreed with the author): "
        f"{', '.join(k.get('top_misses', [])) or 'none'}",
        f"- Benchmark noise (first {min(8, k.get('n_noise', 0))} of {k.get('n_noise', 0)} shown-but-irrelevant pairs): "
        f"{', '.join(k.get('top_noise', [])) or 'none'}",
        (f"- Repeat mistakes: unmeasured ({k.get('corrections', 0)} corrections in {k.get('turns_logged', 0)} logged turn(s))"
         if not k.get("corrections") else
         f"- Repeat mistakes, never shown: {', '.join(k.get('repeat_never_shown', [])) or 'none'}; "
         f"shown and ignored: {', '.join(k.get('repeat_shown_ignored', [])) or 'none'}"),
        f"- Added: {', '.join(k.get('added', [])) or 'none'}; strengthened: "
        f"{', '.join(k.get('strengthened', [])) or 'none'}; retired: {', '.join(k.get('retired', [])) or 'none'}",
        f"- Sources unverifiable in this clone: {len(k.get('source_unverifiable', []))}",
        f"- Judge: {spend.get('calls', 0)} {JUDGE_MODEL} calls this run; {spend.get('pairs_cached', 0)} of "
        f"{spend.get('pairs_total', 0)} benchmark pairs were already labelled before this run (by {JUDGE_MODEL} with the "
        f"current judge instructions), the rest labelled now. "
        f"Retriever replay: {spend.get('jev_calls', 0)} Jev calls; total run spend_usd {row.get('spend_usd')} (Jev only; "
        f"judge calls run on the subscription and are not metered).",
        "", "## Standing caveats", "",
        f"- The judge is {JUDGE_MODEL}, never the Jev retriever it grades. judge_sanity (above) is its agreement with "
        "the author on negative prompts; a low value makes every benchmark number suspect.",
        f"- The benchmark is visible in the repo, so triggers could be overfitted to it (trigger_overlap "
        f"{k.get('trigger_overlap')} this run). Live precision and repeat mistakes are the check on that; they are "
        f"{checks}.",
        "- Live numbers only cover turns whose sessions committed their observation rows.",
        "- live_precision_kw grades keyword picks only: Jev never grades its own picks, so Jev picks are measured "
        "on the benchmark alone. Repeat-mistake detection is a Jev judgement and can under-count.",
        f"- A drop smaller than max(configured tolerance, 2 standard errors of the smaller sample) is not called a "
        f"regression, and drift since the first baseline tolerates double: on this sample about {f1_tol:.2f} for f1 "
        f"week-on-week and {2 * f1_tol:.2f} since baseline. Floors still apply.",
        "", "## Full miss and noise lists", "",
        f"- Misses ({len(bm.get('_all_misses', []))}): {', '.join(bm.get('_all_misses', [])) or 'none'}",
        f"- Noise ({len(bm.get('_all_noise', []))}): {', '.join(bm.get('_all_noise', [])) or 'none'}",
        "",
    ]
    return "\n".join(lines)


def status() -> str:
    hist = read_jsonl(history_path())
    if not hist:
        return "brain eval: never run"
    last = hist[-1]
    rp = eval_dir() / "reports" / f"{last.get('date')}.md"
    top, note = "", ""
    try:
        text = rp.read_text(encoding="utf-8")
        body = text.rsplit("\nhistory row ", 1)[0]
        if last.get("report_sha") and sha(body) != last["report_sha"]:
            note = " [report edited after the run: trust history.jsonl]"
        for line in text.splitlines():
            if line.startswith("- [FAIL]") or line.startswith("- [WARN]"):
                top = line[2:]
                break
    except OSError:
        note = " [report file missing]"
    return f"brain eval {last.get('date')}: {last.get('verdict')}" + (f" — {top}" if top else "") + note


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
    p.add_argument("--note", action="append", default=[], help="run note recorded in history and the report")
    p.add_argument("--ack", action="append", default=[],
                   help='acknowledge an alarm, recorded in history: --ack "goalposts_moved: fixed evaluator bug X"')
    sub.add_parser("status")
    sub.add_parser("verify")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        report, row = run(a.label, a.dry_run, a.ack, a.note)
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
