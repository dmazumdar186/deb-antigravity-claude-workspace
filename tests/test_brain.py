"""Tests for execution/infrastructure/brain.py (offline: Jev key blanked)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from execution.infrastructure import brain  # noqa: E402

SCRIPT = ROOT / "execution" / "infrastructure" / "brain.py"


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("BRAIN_TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("BRAIN_TODAY", "2026-11-12")
    for k in ("OPENROUTER_API_KEY", "OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def add(*args: str) -> int:
    return brain.main(["add", *args])


def write(
    lid: str, rule: str, triggers: str, strength: int = 2, confirmed: str = "2026-11-01"
) -> None:
    les = brain.Lesson(
        id=lid,
        rule=rule,
        why="w",
        triggers=brain._split_list(triggers),
        strength=strength,
        created=confirmed,
        confirmed=confirmed,
    )
    brain.save(les)


def test_roundtrip_render_parse():
    les = brain.Lesson(
        id="x",
        rule="Do the thing.",
        why="Because.",
        triggers=["a b", "c"],
        strength=3,
        created="2026-01-01",
        confirmed="2026-01-01",
        supersedes=["y"],
    )
    back = brain.parse(les.render())
    assert (
        back.id,
        back.rule,
        back.why,
        back.triggers,
        back.strength,
        back.supersedes,
    ) == ("x", "Do the thing.", "Because.", ["a b", "c"], 3, ["y"])


def test_bad_file_reported_not_fatal(sandbox):
    d = sandbox / "brain" / "lessons"
    d.mkdir(parents=True)
    (d / "broken.md").write_text("no frontmatter", encoding="utf-8")
    write("ok", "Rule.", "deploy")
    lessons, errors = brain.load()
    assert [x.id for x in lessons] == ["ok"] and errors and "broken.md" in errors[0]


def test_retrieve_word_boundary_and_dedupe():
    write(
        "pat",
        "Check the recipient's eye view before a reply to Pat.",
        "pat, acme agency",
    )
    write("dep", "Deploy to Cloudflare Pages, never github.io.", "deploy, github pages")
    lessons, _ = brain.load()
    assert brain.retrieve("this is a pattern match", lessons) == []  # 'pat' != 'pattern'
    hits = brain.retrieve("draft the reply to Pat at Acme Agency", lessons)
    assert [h[1].id for h in hits] == ["pat"]
    assert brain.retrieve("reply to Pat", lessons, exclude={"pat"}) == []


def test_hook_prompt_injects_once_per_session():
    write("dep", "Deploy client pages to Cloudflare Pages only.", "deploy, client page")
    payload = {"session_id": "s1", "prompt": "please deploy the client page now"}
    first = json.loads(brain.hook_prompt(payload))
    assert "Cloudflare" in first["hookSpecificOutput"]["additionalContext"]
    assert brain.hook_prompt(payload) == ""  # deduped


def test_hook_prompt_correction_reminder():
    out = json.loads(
        brain.hook_prompt(
            {"session_id": "s2", "prompt": "why did you skip the reviewer again?"}
        )
    )
    assert "operator correction" in out["hookSpecificOutput"]["additionalContext"]


def test_machine_turns_ignored():
    write("p", "Payment terms are 50/50.", "payment terms, proposal", strength=3)
    for pr in ("<task-notification>proposal payment terms</task-notification>",
               "[SYSTEM NOTIFICATION] subagent: proposal payment terms, I missed it"):
        assert brain.hook_prompt({"session_id": "m", "prompt": pr}) == ""


def test_short_prompt_noop():
    assert brain.hook_prompt({"session_id": "s", "prompt": "ok"}) == ""


def test_hook_start_core_cap_and_upkeep():
    for i in range(20):
        write(f"c{i:02d}", f"Core rule number {i} " + "x" * 150, f"t{i}", strength=3)
    out = json.loads(brain.hook_start({"session_id": "s3"}))["hookSpecificOutput"][
        "additionalContext"
    ]
    assert out.count("\n- ") <= brain.CORE_MAX_ITEMS
    assert "Brain upkeep" in out  # deep check never ran
    # core lessons are not re-injected per prompt in the same session
    assert (
        brain.hook_prompt({"session_id": "s3", "prompt": "something about t0 here"})
        == ""
    )


def test_hook_start_empty_brain_is_silent():
    assert brain.hook_start({"session_id": "x"}) == ""


def test_add_duplicate_strengthens_instead(capsys):
    write(
        "a",
        "Run the red-team gate before any outward email is sent.",
        "email, outward, redteam",
    )
    assert (
        add(
            "--rule",
            "Run the red-team gate before any outward email is sent.",
            "--triggers",
            "email",
        )
        == 0
    )
    lessons, _ = brain.load()
    assert len(lessons) == 1 and lessons[0].strength == 3
    assert "duplicate of a" in capsys.readouterr().out


def test_add_new_and_validation(capsys):
    assert add("--rule", "x" * 300, "--triggers", "a") == 2
    assert add("--rule", "Fine rule.", "--triggers", "") == 2
    assert add("--rule", "Fine rule.", "--triggers", "a", "--scope", "bogus") == 2
    assert (
        add(
            "--rule",
            "Ask before changing a deliverable format.",
            "--triggers",
            "format, report",
        )
        == 0
    )
    lessons, _ = brain.load()
    assert lessons[0].id.startswith("2026-11-12-") and lessons[0].strength == 2


def test_add_dry_run_writes_nothing():
    assert add("--rule", "Something new here.", "--triggers", "zzz", "--dry-run") == 0
    assert brain.load()[0] == []


def test_repeat_promotes_to_core():
    write("r", "Rule.", "t", strength=2)
    brain.main(["repeat", "r"])
    les = brain.find("r")
    assert les.strength == 3 and les.confirmed == "2026-11-12"
    assert [x.id for x in brain.core(brain.load()[0])] == ["r"]


def test_supersede_and_restore(sandbox):
    write("old", "Old rule.", "t")
    write("new", "New rule.", "t")
    brain.main(["supersede", "old", "new"])
    assert (sandbox / "brain" / "archive" / "old.md").exists()
    assert not (sandbox / "brain" / "lessons" / "old.md").exists()
    assert brain.find("new").supersedes == ["old"]
    brain.main(["restore", "old"])
    assert brain.find("old").status == "active"


def test_lint_decay_and_duplicate_apply():
    write(
        "stale",
        "Minor stale rule about widgets.",
        "widgets",
        strength=1,
        confirmed="2026-01-01",
    )
    write(
        "d1",
        "Always paginate every list API call fully.",
        "paginate, list api",
        strength=2,
    )
    write(
        "d2",
        "Always paginate every list API call fully please.",
        "paginate",
        strength=1,
    )
    lessons, errors = brain.load()
    rep = brain.lint(lessons, errors)
    assert rep["decay"] == ["stale"] and rep["duplicates"]
    done = brain.apply_lint(rep)
    act = {x.id for x in brain.active(brain.load()[0])}
    assert act == {"d1"} and any("merged d2 -> d1" in d for d in done)


def test_lint_deep_records_state():
    write("a", "Rule.", "t")
    brain.main(["lint", "--deep"])
    assert brain.read_state()["last_deep"] == "2026-11-12"
    out = brain.hook_start({"session_id": "z"})
    assert "Brain upkeep" not in out


def _transcript(path: Path, assistant_text: str, cmd: str = "") -> Path:
    rows = [
        {"type": "user", "message": {"role": "user", "content": "fix it"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": assistant_text}]
                + ([{"type": "tool_use", "input": {"command": cmd}}] if cmd else []),
            },
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_hook_stop_blocks_once_on_admission(sandbox):
    tp = _transcript(sandbox / "t.jsonl", "Nice catch, I overlooked the pagination.")
    out = json.loads(brain.hook_stop({"session_id": "q", "transcript_path": str(tp)}))
    assert out["decision"] == "block"
    assert (
        brain.hook_stop(
            {"session_id": "q", "transcript_path": str(tp), "stop_hook_active": True}
        )
        == ""
    )


def test_hook_stop_quiet_when_recorded_or_clean(sandbox):
    tp = _transcript(
        sandbox / "a.jsonl",
        "My mistake.",
        "python3 execution/infrastructure/brain.py add --rule x",
    )
    assert brain.hook_stop({"session_id": "q2", "transcript_path": str(tp)}) == ""
    tp2 = _transcript(sandbox / "b.jsonl", "Done. Tests pass.")
    assert brain.hook_stop({"session_id": "q3", "transcript_path": str(tp2)}) == ""


def test_hook_stop_nudge_cap(sandbox):
    tp = _transcript(sandbox / "c.jsonl", "My bad.")
    outs = [
        brain.hook_stop({"session_id": "cap", "transcript_path": str(tp)})
        for _ in range(5)
    ]
    assert sum(1 for o in outs if o) == 3


def test_hook_cli_fails_open_on_garbage(sandbox):
    env = {
        "BRAIN_DIR": str(sandbox / "brain"),
        "BRAIN_TMP": str(sandbox / "tmp"),
        "PATH": "/usr/bin:/bin",
    }
    for mode in ("hook-start", "hook-prompt", "hook-stop"):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            input="not json{",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30,
        )
        assert r.returncode == 0 and r.stdout == ""


def test_add_refuses_contradiction_then_supersede(monkeypatch, capsys):
    write("old", "Cap the red-team at two rounds and never add hedges.", "redteam, hedge, rounds")
    monkeypatch.setattr(brain, "jev_relations", lambda new, others: {o.id: ("contradicts", 0.95) for o in others})
    rule = "Run as many red-team rounds as needed and add hedges freely."
    assert add("--rule", rule, "--triggers", "redteam, hedge") == 3
    assert "contradicts old" in capsys.readouterr().out
    assert len(brain.load()[0]) == 1 and brain.find("old").status == "active"
    assert add("--rule", rule, "--triggers", "redteam, hedge", "--supersede", "old") == 0
    assert brain.find("old").status == "archived"


def test_add_refuses_restatement_unless_forced(monkeypatch):
    write("old", "Re-fetch a third party site before calling it dated.", "third party, site")
    monkeypatch.setattr(brain, "jev_relations", lambda new, others: {o.id: ("refines", 0.9) for o in others})
    rule = "Open an outside site today and look before you call it dated."
    assert add("--rule", rule, "--triggers", "homepage") == 3
    assert add("--rule", rule, "--triggers", "homepage", "--force") == 0


def test_id_path_traversal_refused(sandbox):
    assert add("--rule", "x rule", "--triggers", "t", "--id", "../../../../tmp/pwn", "--force") == 2
    assert add("--rule", "x rule", "--triggers", "t", "--id", "sub/dir", "--force") == 2
    with pytest.raises(ValueError):
        brain.save(brain.Lesson(id="../evil", rule="r"))


def test_stop_ignores_quotes_and_soft_phrases(sandbox):
    for text in ('The client wrote "sorry about that, my mistake, we pay Friday".',
                 "You're right, cloud runs python 3.11. Nothing to change.",
                 "I didn't run them because you asked for dry-run only.",
                 "> my mistake was quoted here"):
        tp = _transcript(sandbox / "s.jsonl", text)
        assert brain.hook_stop({"session_id": "fp", "transcript_path": str(tp)}) == "", text


def test_verbatim_duplicate_caught_even_when_jev_disagrees(monkeypatch):
    write("c", "In cold copy never claim a prospect's intent or need; bound every ask.", "cold copy, intent")
    monkeypatch.setattr(brain, "jev_relations", lambda new, others: {o.id: ("unrelated", 0.9) for o in others})
    assert add("--rule", "In cold copy never claim a prospect's intent or need; bound every ask.",
               "--triggers", "cold copy") == 0
    assert len(brain.load()[0]) == 1


def test_single_generic_trigger_does_not_inject():
    write("r", "Approver drafts list blockers first.", "reply, pat", strength=3)
    lessons, _ = brain.load()
    assert brain.retrieve("build the mobile app for pat with eas", lessons) == []
    assert [h[1].id for h in brain.retrieve("draft the reply to pat", lessons)] == ["r"]


def test_restore_clears_dangling_supersedes():
    write("old", "Old rule.", "t")
    write("new", "New rule.", "t")
    brain.main(["supersede", "old", "new"])
    brain.main(["restore", "old"])
    assert brain.find("new").supersedes == []


def test_lint_apply_skips_weak_lexical_merge():
    write("a", "Paginate every list API call fully before counting.", "paginate")
    write("b", "Paginate the Pages project list before deciding a project is missing.", "pages")
    lessons, errors = brain.load()
    rep = brain.lint(lessons, errors)
    rep["duplicates"] = [("a", "b", 0.55, "lex")]
    assert brain.apply_lint(rep) == []


def test_plural_folding_keeps_les_distinct():
    write("c", "Never claim prospect intent in cold copy.", "cold email, campaign, pat")
    lessons, _ = brain.load()
    assert [h[1].id for h in brain.retrieve("prepare cold emails for the campaigns", lessons)] == ["c"]
    assert brain.retrieve("this is less of a priority", lessons) == []
