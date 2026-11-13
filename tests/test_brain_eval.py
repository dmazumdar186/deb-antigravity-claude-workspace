"""Tests for execution/infrastructure/brain_eval.py and the brain's evidence path (offline: no Jev, no judge)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from execution.infrastructure import brain  # noqa: E402
from execution.infrastructure import brain_eval as ev  # noqa: E402


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("BRAIN_TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-12")
    for k in ("OPENROUTER_API_KEY", "OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN"):
        monkeypatch.delenv(k, raising=False)

    # A fake independent judge: a lesson is relevant iff its first trigger word is in the prompt.
    def fake_judge(prompt, chunk):
        return (
            {
                ev.label_key(prompt, x): (
                    1.0 if x.triggers and x.triggers[0] in prompt.lower() else 0.0
                )
                for x in chunk
            },
            0.0,
            "",
        )

    monkeypatch.setattr(ev, "_judge_prompt", fake_judge)
    return tmp_path


def lesson(lid, rule, triggers, strength=2):
    brain.save(
        brain.Lesson(
            id=lid,
            rule=rule,
            why="w",
            triggers=brain._split_list(triggers),
            strength=strength,
            created="2026-11-01",
            confirmed="2026-11-01",
            source="CLAUDE.md",
        )
    )


def bench(rows):
    d = ev.eval_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "benchmark.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def setup_world():
    lesson(
        "deploy", "Deploy client pages to Cloudflare Pages only.", "deploy, client page"
    )
    lesson(
        "cold",
        "Never claim prospect intent in cold email copy.",
        "cold email, campaign",
    )
    lesson("logo", "Keep the client's real logo in a redesign.", "logo, redesign")
    bench(
        [
            {"id": "b1", "prompt": "deploy the client page tonight", "kind": "task"},
            {
                "id": "b2",
                "prompt": "write cold email copy for the campaign",
                "kind": "task",
            },
            {
                "id": "b3",
                "prompt": "the logo looks off on the new hero",
                "kind": "task",
            },
            {"id": "b4", "prompt": "what time is it in paris", "kind": "negative"},
        ]
    )


def test_unlabelled_is_unmeasured_not_pass():
    setup_world()
    report, row = ev.run(label=False, dry_run=True)
    assert row["verdict"] != "PASS"
    assert "kw_precision" in row["kpis"] and row["kpis"]["precision"] is None
    assert "unmeasured" in report


def test_labelled_run_scores_and_writes_only_eval_dir(sandbox):
    setup_world()
    before = {
        p.name: p.read_text(encoding="utf-8")
        for p in (sandbox / "brain" / "lessons").glob("*.md")
    }
    report, row = ev.run(label=True, dry_run=False)
    k = row["kpis"]
    assert (
        k["kw_recall"] is not None
        and k["judge_sanity"] == 1.0
        and k["label_coverage_gap"] == 0.0
    )
    # hybrid unmeasured without Jev -> stated, never silently copied from keyword scores
    assert k["precision"] is None and "hybrid unmeasured" in report
    after = {
        p.name: p.read_text(encoding="utf-8")
        for p in (sandbox / "brain" / "lessons").glob("*.md")
    }
    assert before == after, "the evaluator must never write lessons"
    written = {
        p.relative_to(sandbox / "brain").parts[0]
        for p in (sandbox / "brain").rglob("*")
        if p.is_file()
    }
    assert written <= {"lessons", "eval"}


def test_history_chain_detects_edit_and_fails():
    setup_world()
    ev.run(label=True, dry_run=False)
    hp = ev.history_path()
    row = json.loads(hp.read_text(encoding="utf-8").splitlines()[0])
    row["verdict"] = "PASS"
    row["kpis"]["kw_recall"] = 1.0  # cover-up attempt
    hp.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert ev.verify_chain(ev.read_jsonl(hp))
    _, row2 = ev.run(label=True, dry_run=True)
    assert row2["verdict"] == "FAIL" and "history_tampered" in row2["codes"]


def test_deleted_evidence_fails():
    setup_world()
    od = brain.obs_dir()
    od.mkdir(parents=True)
    (od / "2026-11-12-a.jsonl").write_text(
        json.dumps({"date": "2026-11-12", "injected": ["deploy"]}) + "\n",
        encoding="utf-8",
    )
    ev.run(label=True, dry_run=False)
    (od / "2026-11-12-a.jsonl").unlink()
    _, row = ev.run(label=True, dry_run=True)
    assert row["verdict"] == "FAIL" and "evidence_deleted" in row["codes"]


def test_goalposts_moved_is_flagged_and_blocks_benchmark_deltas():
    setup_world()
    ev.run(label=True, dry_run=False)
    (ev.eval_dir() / "thresholds.json").write_text(
        json.dumps({**ev.DEFAULT_THRESHOLDS, "floors": {}}), encoding="utf-8"
    )
    report, row = ev.run(label=True, dry_run=True)
    assert "goalposts_moved" in row["codes"] and "thresholds changed" in report


def test_regression_beyond_tolerance_fails(monkeypatch):
    setup_world()
    ev.run(label=True, dry_run=False)
    th = {
        **ev.DEFAULT_THRESHOLDS,
        "regression": {"kw_recall": 0.05},
        "fail_on": ["kw_recall_regression"],
    }
    monkeypatch.setattr(ev, "thresholds", lambda: th)
    monkeypatch.setattr(ev, "tolerance", lambda m, base, k, ref: base)  # tiny fixture: bypass the 2-SE widening
    brain.save(
        brain.Lesson(
            id="deploy",
            rule="Deploy client pages to Cloudflare Pages only.",
            why="w",
            triggers=["zzz"],
            strength=2,
            created="2026-11-01",
            confirmed="2026-11-01",
        )
    )
    _, row = ev.run(label=True, dry_run=True)
    assert "kw_recall_regression" in row["codes"] and row["verdict"] == "FAIL"


def test_judge_cannot_be_the_retriever(monkeypatch):
    monkeypatch.setattr(ev, "JUDGE_MODEL", "typesafe/jev-1.13")
    with pytest.raises(SystemExit):
        ev.assert_independent()


def test_live_metrics_split_repeat_mistakes():
    obs = [
        {
            "date": "2026-11-11",
            "sid": "a",
            "injected": ["deploy"],
            "relevance": {"deploy": 0.9},
            "correction": False,
        },
        {
            "date": "2026-11-11",
            "sid": "a",
            "injected": [],
            "correction": True,
            "covered_by": "cold",
            "covered_p": 0.8,
            "covered_was_shown": False,
        },
        {
            "date": "2026-11-12",
            "sid": "b",
            "injected": ["logo"],
            "relevance": {"logo": 0.2},
            "correction": True,
            "covered_by": "logo",
            "covered_p": 0.9,
            "covered_was_shown": True,
            "admitted": True,
            "recorded": False,
        },
        {
            "date": "2026-10-01",
            "sid": "c",
            "correction": True,
            "covered_by": "old",
            "covered_p": 0.9,
        },
    ]
    m = ev.live_metrics(obs, "2026-11-05")
    assert m["repeat_mistakes_week"] == 2 and m["repeat_never_shown"] == ["cold"]
    assert (
        m["repeat_shown_ignored"] == ["logo"]
        and m["live_precision_kw"] == 0.5
        and m["capture_leak"] == 1.0
    )
    verdict, faults, codes = ev.judge(
        {**m, "core_chars": 10},
        [],
        ev.DEFAULT_THRESHOLDS,
        {
            "chain_problems": [],
            "obs_total": 4,
            "prev_obs_total": 0,
            "moved": [],
            "benchmark_moved": False,
        },
    )
    assert (
        "repeat_missed_retrieval" in codes
        and "repeat_ignored" in codes
        and verdict in ("WARN", "FAIL")
    )


def test_hybrid_merges_sources_and_respects_cap():
    setup_world()
    lessons, _ = brain.load()
    out = brain.retrieve_hybrid(
        "deploy the client page", lessons, picks={"logo": 0.9, "deploy": 0.8}
    )
    assert out[0] == ("both", next(x for x in lessons if x.id == "deploy"))
    assert ("jev", next(x for x in lessons if x.id == "logo")) in out and len(
        out
    ) <= brain.PROMPT_TOP_K
    assert (
        brain.retrieve_hybrid("deploy the client page", lessons, use_jev=False)[0][0]
        == "kw"
    )


def test_jev_pick_off_when_jev_disabled_or_capped(monkeypatch):
    setup_world()
    lessons, _ = brain.load()
    monkeypatch.setattr(brain, "_jev_enabled", lambda: False)
    assert brain.jev_pick("deploy", lessons, set()) == {}
    monkeypatch.setattr(brain, "_jev_enabled", lambda: True)
    monkeypatch.setattr(brain, "_spent_today", lambda: 1.0)
    assert brain.jev_pick("deploy", lessons, set()) == {}


def _transcript(path: Path, text: str) -> Path:
    rows = [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_observation_row_is_text_free_and_logged_once(sandbox):
    setup_world()
    secret = "deploy the client page using token sk-SECRET-123 tonight"
    brain.hook_prompt({"session_id": "s1", "prompt": secret})
    tp = _transcript(sandbox / "t.jsonl", "Deployed.")
    brain.hook_stop({"session_id": "s1", "transcript_path": str(tp)})
    brain.hook_stop({"session_id": "s1", "transcript_path": str(tp)})
    files = list(brain.obs_dir().glob("*.jsonl"))
    rows = [
        json.loads(ln)
        for f in files
        for ln in f.read_text(encoding="utf-8").splitlines()
    ]
    assert (
        len(rows) == 1
        and rows[0]["injected"] == ["deploy"]
        and rows[0]["sources"] == {"deploy": "kw"}
    )
    assert "SECRET" not in json.dumps(rows) and "client page" not in json.dumps(rows)


def test_lesson_added_this_turn_is_not_a_repeat(sandbox, monkeypatch):
    setup_world()
    brain.hook_prompt(
        {"session_id": "s2", "prompt": "why did you skip the logo again?"}
    )
    lesson("fresh", "A lesson written during this turn.", "logo")
    seen = {}

    def fake_judge(prompt, injected, known, correction):
        seen["known"] = [x.id for x in known]
        return {}

    monkeypatch.setattr(brain, "judge_turn", fake_judge)
    tp = _transcript(sandbox / "u.jsonl", "Fixed.")
    brain.hook_stop({"session_id": "s2", "transcript_path": str(tp)})
    assert "fresh" not in seen["known"] and "logo" in seen["known"]


def test_session_start_surfaces_non_pass_and_overdue(monkeypatch):
    setup_world()
    d = ev.eval_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "history.jsonl").write_text(
        json.dumps({"date": "2026-10-20", "verdict": "WARN", "codes": ["f1_floor"]})
        + "\n",
        encoding="utf-8",
    )
    out = json.loads(brain.hook_start({"session_id": "z"}))["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "OVERDUE" in out and "WARN (f1_floor)" in out and "Tell the operator" in out


# ---- regressions for the 2026-11-12 evaluator audit ------------------------------------------------
def test_one_edited_rule_does_not_blank_the_benchmark():
    setup_world()
    ev.run(label=True, dry_run=False)
    lesson("deploy", "Deploy client pages to Cloudflare Pages only, never github.io.", "deploy, client page")
    _, row = ev.run(label=False, dry_run=True)
    k = row["kpis"]
    assert k["kw_recall"] is not None and k["unlabelled_pairs"] > 0
    assert "label_coverage_gap_ceiling" in row["codes"] and row["verdict"] != "PASS"


def test_unmeasured_week_cannot_reset_regression_baseline(monkeypatch):
    setup_world()
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-01")
    ev.run(label=True, dry_run=False)
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-08")
    lesson("deploy", "Deploy client pages to Cloudflare Pages only.", "zzz")  # breaks recall
    ev.run(label=False, dry_run=False)  # an offline run in between
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-15")
    monkeypatch.setattr(ev, "tolerance", lambda m, base, k, ref: base)
    th = {**ev.DEFAULT_THRESHOLDS, "regression": {"kw_recall": 0.05}, "fail_on": ["kw_recall_regression"]}
    monkeypatch.setattr(ev, "thresholds", lambda: th)
    _, row = ev.run(label=True, dry_run=True)
    assert "kw_recall_regression" in row["codes"] or "kw_recall_drift" in row["codes"]


def test_goalposts_moved_fails_until_acknowledged():
    setup_world()
    ev.run(label=True, dry_run=False)
    p = ev.eval_dir() / "thresholds.json"
    p.write_text(json.dumps({**ev.DEFAULT_THRESHOLDS, "floors": {}}), encoding="utf-8")
    _, row = ev.run(label=True, dry_run=True)
    assert row["verdict"] == "FAIL" and "goalposts_moved" in row["codes"]
    report, row = ev.run(label=True, dry_run=True, acks=["goalposts_moved: loosened floors on purpose"])
    assert row["verdict"] != "FAIL" and "(acknowledged)" in report
    assert row["acks"][0]["reason"] == "loosened floors on purpose"


def test_deleting_history_with_reports_left_is_flagged():
    setup_world()
    ev.run(label=True, dry_run=False)
    ev.history_path().unlink()
    _, row = ev.run(label=True, dry_run=True)
    assert row["verdict"] == "FAIL" and "evidence_deleted" in row["codes"]


def test_retired_without_supersede_warns():
    setup_world()
    ev.run(label=True, dry_run=False)
    (brain.brain_dir() / "lessons" / "logo.md").unlink()
    _, row = ev.run(label=True, dry_run=True)
    assert "retired_without_supersede" in row["codes"] and row["verdict"] in ("WARN", "FAIL")


def test_edited_report_is_detected_by_status():
    setup_world()
    ev.run(label=True, dry_run=False)
    rp = next((ev.eval_dir() / "reports").glob("*.md"))
    rp.write_text(rp.read_text(encoding="utf-8").replace("Fault lines", "All good"), encoding="utf-8")
    assert "edited after the run" in ev.status()


def test_judge_errors_reach_the_verdict(monkeypatch):
    setup_world()
    monkeypatch.setattr(ev, "_judge_prompt", lambda p, c: ({}, 0.0, "judge returned no JSON"))
    _, row = ev.run(label=True, dry_run=True)
    assert "judge_errors" in row["codes"] and row["verdict"] != "PASS"


def test_tolerance_widens_on_small_samples():
    ref = {"kpis": {"recall": 0.5, "n_rel": 20}}
    assert ev.tolerance("recall", 0.05, {"n_rel": 20}, ref) > 0.2
    assert ev.tolerance("recall", 0.05, {"n_rel": 10000}, {"kpis": {"recall": 0.5, "n_rel": 10000}}) == 0.05


def test_same_prompt_twice_is_two_turns(sandbox):
    setup_world()
    tp = sandbox / "t2.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}), encoding="utf-8")
    for _ in range(2):
        brain.hook_prompt({"session_id": "dup", "prompt": "why did you skip the checklist again?"})
        brain.hook_stop({"session_id": "dup", "transcript_path": str(tp)})
    rows = [ln for f in brain.obs_dir().glob("*.jsonl") for ln in f.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and len({json.loads(r)["turn"] for r in rows}) == 2


def test_spend_counter_is_thread_safe():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: brain._add_spend(0.001), range(200)))
    assert abs(brain._spent_today() - 0.2) < 1e-9


def test_benchmark_scores_retrieval_as_deployed_core_excluded():
    """The live hook excludes core lessons (injected at session start); the eval must too (2026-11-13)."""
    lesson("corelesson", "Always check the deploy log before claiming success.", "deploy, log", strength=5)
    lesson("plain", "Scrub the client logo from concept covers.", "deploy, cover", strength=1)
    lessons, _ = brain.load()
    core_ids = {x.id for x in brain.core(lessons)}
    assert core_ids == {"corelesson"}
    prompt = "deploy the cover page and read the log"
    labels = {ev.label_key(prompt, x): 1.0 for x in lessons}
    rows = [{"id": "b1", "prompt": prompt, "kind": "task"}]
    for picks in (None, {prompt: {"corelesson": 0.95, "plain": 0.9}}):
        m = ev.benchmark_metrics(rows, lessons, labels, picks)
        # the core lesson is relevant and keyword/Jev-matched, yet never retrieved and never a miss
        assert m["recall"] == 1.0 and m["precision"] == 1.0, m
        assert m["effective_recall"] == 1.0
        assert "corelesson" in m["_relevant_any"]
    # retrieve_hybrid drops excluded ids even when replayed picks contain them
    out = brain.retrieve_hybrid(prompt, lessons, exclude={"corelesson"}, picks={"corelesson": 0.95})
    assert all(x.id != "corelesson" for _, x in out)
