"""Row 7 (2026-11-17): every-turn logging, the holdout arm, the independent grader and benchmark sets.
Offline: no Jev, no Claude call (the grader's CLI call is stubbed)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
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
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-17")
    for k in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_API_TOKEN",
        "OPENROUTER_API_TOEKN",
        "BRAIN_HOLDOUT_RATE",
        "BRAIN_GRADE_RATE",
        "BRAIN_GRADE_OFF",
        "BRAIN_GRADE_TEST",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(brain, "_jev_enabled", lambda: True)
    brain.save(
        brain.Lesson(
            id="deploy",
            rule="Deploy client pages to Cloudflare Pages only.",
            why="w",
            triggers=["deploy", "client page"],
            strength=2,
            created="2026-11-01",
            confirmed="2026-11-01",
            source="CLAUDE.md",
        )
    )
    return tmp_path


def _transcript(path: Path) -> Path:
    rows = [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Done."}],
            },
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def _rows(pattern: str = "*.jsonl") -> list[dict]:
    return [
        json.loads(ln)
        for f in sorted(brain.obs_dir().glob(pattern))
        if not f.name.endswith(".grades.jsonl")
        for ln in f.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def _turn(sid: str, prompt: str, tmp: Path) -> str:
    out = brain.hook_prompt({"session_id": sid, "prompt": prompt})
    brain.hook_stop(
        {"session_id": sid, "transcript_path": str(_transcript(tmp / f"{sid}.jsonl"))}
    )
    return out


# ---- holdout ------------------------------------------------------------------------------------
def test_holdout_withholds_and_does_not_inject(monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    out = brain.hook_prompt(
        {"session_id": "h1", "prompt": "deploy the client page tonight please"}
    )
    st = brain.session_get("h1")
    assert out == "" and "Cloudflare" not in out
    assert st["turn"]["holdout"] is True and st["turn"]["injected"] == []
    assert st["turn"]["withheld"] == ["deploy"] and st["turn"]["withheld_sources"] == {
        "deploy": "kw"
    }
    assert "deploy" not in st.get("injected", [])


def test_holdout_still_nudges_corrections(monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    out = brain.hook_prompt(
        {
            "session_id": "h2",
            "prompt": "why did you deploy the client page again? wrong",
        }
    )
    assert "operator correction" in out and "Cloudflare" not in out


def test_rate_zero_disables_holdout(monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "0")
    assert not any(brain.holdout_arm(f"{i:08x}abcd-1") for i in range(0, 2**32, 2**22))
    out = brain.hook_prompt(
        {"session_id": "h3", "prompt": "deploy the client page tonight please"}
    )
    assert "Cloudflare" in out and brain.session_get("h3")["turn"]["holdout"] is False


def test_holdout_is_deterministic_per_sha_and_near_rate(monkeypatch):
    import hashlib

    shas = [
        hashlib.sha256(str(i).encode()).hexdigest()[:12] + "-2" for i in range(4000)
    ]
    first = [brain.holdout_arm(s) for s in shas]
    assert first == [brain.holdout_arm(s) for s in shas]
    assert all(f == (int(s[:8], 16) % 100 < 10) for f, s in zip(first, shas))
    assert 0.08 < sum(first) / len(first) < 0.12
    monkeypatch.setenv(
        "BRAIN_HOLDOUT_RATE", "junk"
    )  # malformed -> default, never raises
    assert [brain.holdout_arm(s) for s in shas] == first


def test_prev_holdout_attributes_correction_to_previous_arm(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    _turn("p1", "deploy the client page tonight please", sandbox)
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "0")
    _turn("p1", "why did you skip the checklist again? wrong", sandbox)
    r1, r2 = _rows()
    assert r1["holdout"] is True and r1["prev_holdout"] is None
    assert (
        r2["holdout"] is False
        and r2["prev_holdout"] is True
        and r2["correction"] is True
    )
    m = ev.live_metrics([r1, r2], "2026-11-10")
    assert m["arm_holdout_corrections"] == 1 and m["arm_injected_corrections"] == 0
    assert m["arm_holdout_turns"] == 1 and m["arm_injected_turns"] == 1


def test_machine_turn_keeps_the_previous_arm(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    _turn("p2", "deploy the client page tonight please", sandbox)
    brain.hook_prompt(
        {"session_id": "p2", "prompt": "<task-notification>done</task-notification>"}
    )
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "0")
    _turn("p2", "you broke it, fix the deploy again", sandbox)
    assert [r["prev_holdout"] for r in _rows()] == [None, True]


# ---- every turn logged ----------------------------------------------------------------------------
def test_every_operator_turn_is_logged_machine_turns_are_not(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "0")
    _turn(
        "e1", "summarise the quarterly numbers for me", sandbox
    )  # no hit, no correction, no admission
    brain.hook_prompt(
        {"session_id": "e1", "prompt": "<task-notification>x</task-notification>"}
    )
    brain.hook_stop(
        {"session_id": "e1", "transcript_path": str(_transcript(sandbox / "m.jsonl"))}
    )
    brain.hook_prompt(
        {"session_id": "e1", "prompt": "ok"}
    )  # short prompt: not an operator turn
    brain.hook_stop(
        {"session_id": "e1", "transcript_path": str(_transcript(sandbox / "m2.jsonl"))}
    )
    rows = _rows()
    assert (
        len(rows) == 1 and rows[0]["every_turn"] is True and rows[0]["injected"] == []
    )
    assert "quarterly" not in json.dumps(rows)
    m = ev.live_metrics(rows, "2026-11-10")
    assert m["turns_all"] == 1 and m["corrections_per_100"] == 0.0


def test_old_rows_without_new_fields_still_load():
    legacy = [
        {
            "v": 1,
            "date": "2026-11-16",
            "sid": "a",
            "turn": "x-1",
            "injected": ["deploy"],
            "sources": {"deploy": "kw"},
            "correction": True,
            "relevance": {"deploy": 0.9},
            "judged": True,
        }
    ]
    m = ev.live_metrics(legacy, "2026-11-10")
    assert (
        m["turns_logged"] == 1
        and m["corrections"] == 1
        and m["live_precision_kw"] == 1.0
    )
    assert m["turns_all"] == 0 and m["corrections_per_100"] is None
    assert m["arm_injected_turns"] == 0 and m["holdout_min_sample_ok"] is False
    assert m["live_precision_jev"] is None and m["graded_injections_jev"] == 0


# ---- per-arm KPIs ----------------------------------------------------------------------------------
def _row(holdout, prev, correction=False, covered=None, p=None):
    return {
        "date": "2026-11-16",
        "sid": "s",
        "turn": f"t{id(object())}",
        "every_turn": True,
        "holdout": holdout,
        "prev_holdout": prev,
        "correction": correction,
        "covered_by": covered,
        "covered_p": p,
    }


def test_per_arm_kpis_and_min_sample_flag():
    rows = [_row(False, False) for _ in range(90)] + [
        _row(True, False) for _ in range(10)
    ]
    rows += [
        _row(False, False, True, "deploy", 0.9) for _ in range(10)
    ]  # injected-arm corrections, all repeats
    rows += [
        _row(False, True, True, "deploy", 0.5) for _ in range(4)
    ]  # holdout-arm corrections, below 0.6
    rows += [_row(False, None, True)]  # first turn of a session: unattributed
    m = ev.live_metrics(rows, "2026-11-10")
    assert m["arm_injected_turns"] == 105 and m["arm_holdout_turns"] == 10
    assert m["arm_injected_corrections"] == 10 and m["arm_holdout_corrections"] == 4
    assert (
        m["arm_injected_repeat_mistakes"] == 10
        and m["arm_holdout_repeat_mistakes"] == 0
    )
    assert m["arm_holdout_corrections_per_100"] == 40.0
    assert (
        m["corrections"] == 15 and m["turns_all"] == 115
    )  # existing meaning unchanged
    assert m["holdout_min_sample_ok"] is False
    assert "too small to conclude anything" in ev.holdout_line(m)
    rows += [_row(False, True, True) for _ in range(6)]
    m2 = ev.live_metrics(rows, "2026-11-10")
    assert m2["holdout_min_sample_ok"] is True and "descriptive" in ev.holdout_line(m2)


# ---- independent grader ----------------------------------------------------------------------------
def test_jev_picks_and_withheld_ids_are_sent_to_the_grader(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_GRADE_TEST", "1")
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    jobs = []
    monkeypatch.setattr(brain, "spawn_grader", lambda job: jobs.append(job) or True)
    _turn("g1", "deploy the client page tonight please", sandbox)
    assert (
        len(jobs) == 1
        and jobs[0]["ids"] == ["deploy"]
        and jobs[0]["turn"] == _rows()[0]["turn"]
    )
    monkeypatch.setenv(
        "BRAIN_HOLDOUT_RATE", "0"
    )  # kw-only injection: Jev judges it, the grader does not run
    _turn("g2", "deploy the client page tonight please", sandbox)
    assert len(jobs) == 1


@pytest.mark.parametrize(
    "env,jev_on",
    [({"BRAIN_GRADE_OFF": "1"}, True), ({"BRAIN_GRADE_RATE": "0"}, True), ({}, False)],
)
def test_grader_skipped_when_off_or_jev_off(sandbox, monkeypatch, env, jev_on):
    monkeypatch.setenv("BRAIN_GRADE_TEST", "1")
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(brain, "_jev_enabled", lambda: jev_on)
    jobs = []
    monkeypatch.setattr(brain, "spawn_grader", lambda job: jobs.append(job) or True)
    _turn("g3", "deploy the client page tonight please", sandbox)
    assert jobs == [] and len(_rows()) == 1


def test_grader_never_runs_under_pytest_by_default(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    monkeypatch.setattr(
        brain,
        "spawn_grader",
        lambda job: pytest.fail("spawned a paid/subscription call in a test"),
    )
    _turn("g4", "deploy the client page tonight please", sandbox)


def test_spawn_is_non_blocking_and_passes_job_on_stdin(sandbox, monkeypatch):
    out = sandbox / "child.json"
    child = (
        f"import sys,time; d=sys.stdin.read(); open({str(out)!r},'w',encoding='utf-8').write(d); "
        f"time.sleep(4)"
    )
    monkeypatch.setattr(brain, "_grader_cmd", lambda: [sys.executable, "-c", child])
    t0 = time.monotonic()
    assert brain.spawn_grader(
        {
            "date": "2026-11-17",
            "sid": "x",
            "turn": "t-1",
            "prompt": "SECRET",
            "ids": ["a"],
        }
    )
    assert (
        time.monotonic() - t0 < 1.5
    )  # the child sleeps 4 s; the hook did not wait for it
    for _ in range(100):
        if out.exists() and out.read_text(encoding="utf-8"):
            break
        time.sleep(0.05)
    assert json.loads(out.read_text(encoding="utf-8"))["prompt"] == "SECRET"


def test_spawn_failure_is_logged_and_never_raises_into_the_hook(sandbox, monkeypatch):
    def boom(*a, **k):
        raise OSError("no such interpreter")

    monkeypatch.setattr(subprocess, "Popen", boom)
    assert brain.spawn_grader({"ids": ["deploy"]}) is False
    assert "spawn failed" in brain._grader_log().read_text(encoding="utf-8")
    # end to end through the Stop hook: the row is still written, the hook returns cleanly
    monkeypatch.setenv("BRAIN_GRADE_TEST", "1")
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "100")
    assert _turn("g5", "deploy the client page tonight please", sandbox) == ""
    assert len(_rows()) == 1 and _rows()[0]["withheld"] == ["deploy"]


def test_grade_turn_writes_row_and_eval_merges_it(sandbox, monkeypatch):
    monkeypatch.setattr(
        brain, "_claude_grade", lambda system, user: 'Sure: {"relevant": ["L0"]}'
    )
    row = brain.grade_turn(
        {
            "date": "2026-11-17",
            "sid": "g6",
            "turn": "abc-2",
            "prompt": "p",
            "ids": ["deploy"],
        }
    )
    assert row["grader"] == "claude-sonnet-5-5" and row["relevance_indep"] == {
        "deploy": 1
    }
    grades = [
        json.loads(ln)
        for f in brain.obs_dir().glob("*.grades.jsonl")
        for ln in f.read_text(encoding="utf-8").splitlines()
    ]
    assert grades == [row] and '"p"' not in json.dumps(grades)
    obs = [
        {
            "date": "2026-11-17",
            "sid": "g6",
            "turn": "abc-2",
            "every_turn": True,
            "holdout": False,
            "injected": ["deploy", "kwonly"],
            "sources": {"deploy": "jev", "kwonly": "kw"},
            "relevance": {"kwonly": 0.2},
            "withheld": [],
        },
        {
            "date": "2026-11-17",
            "sid": "g6",
            "turn": "abc-3",
            "every_turn": True,
            "holdout": True,
            "injected": [],
            "sources": {},
            "withheld": ["deploy"],
        },
    ]
    grades.append(
        {
            "v": 1,
            "date": "2026-11-17",
            "sid": "g6",
            "turn": "abc-3",
            "relevance_indep": {"deploy": 0},
        }
    )
    m = ev.live_metrics(obs, "2026-11-10", None, grades)
    assert m["live_precision_jev"] == 1.0 and m["graded_injections_jev"] == 1
    assert m["live_precision_withheld"] == 0.0 and m["graded_withheld"] == 1
    assert (
        m["live_precision_kw"] == 0.0 and m["judged_injections"] == 1
    )  # the grader never feeds the kw metric


def test_grade_rows_are_not_counted_as_observations(sandbox, monkeypatch):
    monkeypatch.setenv("BRAIN_HOLDOUT_RATE", "0")
    _turn("g7", "deploy the client page tonight please", sandbox)
    monkeypatch.setattr(brain, "_claude_grade", lambda s, u: '{"relevant": []}')
    brain.grade_turn(
        {
            "date": "2026-11-17",
            "sid": "g7",
            "turn": _rows()[0]["turn"],
            "prompt": "p",
            "ids": ["deploy"],
        }
    )
    _, row = ev.run(label=False, dry_run=True)
    assert row["obs_total"] == 1 and row["grades_total"] == 1
    assert ev._committed_counts(
        "HEAD:o/a.jsonl:5\nHEAD:o/a.grades.jsonl:3\nHEAD:o/b.jsonl:2"
    ) == (7, 3)


def test_deleted_grade_rows_raise_evidence_deleted():
    ctx = {
        "chain_problems": [],
        "anchor": [],
        "obs_total": 5,
        "prev_obs_total": 5,
        "grades_total": 1,
        "prev_grades_total": 3,
        "moved": [],
        "acks": [],
    }
    verdict, faults, codes = ev.judge({}, [], ev.DEFAULT_THRESHOLDS, ctx)
    assert (
        "evidence_deleted" in codes
        and verdict == "FAIL"
        and any("grader rows fell" in f for f in faults)
    )


def test_grade_job_path_safety_and_independence(monkeypatch):
    monkeypatch.setattr(brain, "_claude_grade", lambda s, u: '{"relevant": []}')
    for bad in (
        {"date": "../../x", "sid": "a", "turn": "t"},
        {"date": "2026-11-17", "sid": "../a", "turn": "t"},
        {"date": "2026-11-17", "sid": "a", "turn": ""},
    ):
        with pytest.raises(ValueError):
            brain.grade_turn({**bad, "ids": ["deploy"]})
    monkeypatch.setattr(brain, "GRADE_MODEL", "typesafe/jev-1.13")
    with pytest.raises(SystemExit):
        brain.grade_turn(
            {"date": "2026-11-17", "sid": "a", "turn": "t", "ids": ["deploy"]}
        )


def test_cmd_grade_logs_failure_and_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setenv("BRAIN_GRADE_TEST", "1")
    monkeypatch.setattr(
        brain,
        "_claude_grade",
        lambda s, u: (_ for _ in ()).throw(RuntimeError("CLI missing")),
    )
    monkeypatch.setattr(
        sys,
        "stdin",
        __import__("io").StringIO(
            json.dumps(
                {"date": "2026-11-17", "sid": "a", "turn": "t", "ids": ["deploy"]}
            )
        ),
    )
    assert brain.cmd_grade() == 1 and "CLI missing" in capsys.readouterr().err


# ---- benchmark sets --------------------------------------------------------------------------------
def test_per_set_kpis_match_overall_scoring():
    brain.save(
        brain.Lesson(
            id="cold",
            rule="Never claim prospect intent in cold email copy.",
            why="w",
            triggers=["cold email", "campaign"],
            strength=2,
            created="2026-11-01",
            confirmed="2026-11-01",
            source="CLAUDE.md",
        )
    )
    lessons, _ = brain.load()
    bench = [
        {"id": "b1", "prompt": "deploy the client page tonight", "kind": "task"},
        {
            "id": "b2",
            "prompt": "write cold email copy for the campaign",
            "kind": "task",
            "set": "v2",
        },
        {
            "id": "b3",
            "prompt": "deploy the client page now",
            "kind": "task",
            "set": "v1",
        },
    ]
    labels = {
        ev.label_key(b["prompt"], x): float(x.triggers[0] in b["prompt"])
        for b in bench
        for x in lessons
    }
    m = ev.per_set_metrics(bench, lessons, labels, {})
    v1 = ev.benchmark_metrics([bench[0], bench[2]], lessons, labels, {})
    assert (
        m["precision_v1"] == v1["precision"]
        and m["recall_v1"] == v1["recall"]
        and m["f1_v1"] == v1["f1"]
    )
    assert m["prompts_v1"] == 2 and m["prompts_v2"] == 1 and m["recall_v2"] == 1.0
    assert (
        ev.per_set_metrics([bench[0]], lessons, labels, {}) == {}
    )  # no set field anywhere: no extra KPIs
    assert (
        ev.per_set_metrics(bench, lessons, labels, None)["f1_v2"] is None
    )  # hybrid not replayed: unmeasured
