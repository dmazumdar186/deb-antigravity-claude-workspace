"""
test_redteam_gate.py
description: Unit tests for execution/infrastructure/redteam_gate.py and the outward-gate hook wrapper.
inputs: none (tmp_path state via REDTEAM_DIR; no network, no LLM).
outputs: pytest results.
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution" / "infrastructure"))

import redteam_gate as rg  # noqa: E402

SCRIPT = ROOT / "execution" / "infrastructure" / "redteam_gate.py"
HOOK_SH = ROOT / ".claude" / "hooks" / "redteam-outward-gate.sh"

AV_SOURCE = "# Asset Voyages costs\nUptimeRobot Solo + AI ≈ €30/month; SMS ≈ €3\n"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Temp HMAC key + transcript root; never touch ~/.claude."""
    monkeypatch.setenv("REDTEAM_KEY_FILE", str(tmp_path / "keys" / "hmac.key"))
    monkeypatch.setenv("REDTEAM_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("REDTEAM_HOOK", "1")
    monkeypatch.setenv("REDTEAM_DIR", str(tmp_path / "state"))


@pytest.fixture()
def state(tmp_path, monkeypatch):
    sd = tmp_path / "state"
    monkeypatch.setenv("REDTEAM_DIR", str(sd))
    return sd


def _agent_transcript(agent_id: str, lines: list[dict] | None = None) -> str:
    p = Path(os.environ["REDTEAM_TRANSCRIPT_ROOT"]) / "proj" / "subagents" / f"agent-{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x) + "\n" for x in (lines or [])), encoding="utf-8")
    return str(p)


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _run(argv, capsys):
    rc = rg.main(argv)
    out = capsys.readouterr().out
    return rc, out


def _stdin_main(argv, data: str) -> int:
    old = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(data.encode("utf-8")))
    try:
        rc = rg.main(argv)
    finally:
        sys.stdin = old
    return rc


def _verdict_text(lens: str, sha: str, verdict: str = "PASS") -> str:
    return f"LENS: {lens}\nDRAFT-SHA: {sha}\nVERDICT: {verdict}\nFINDINGS: none\n"


def _log_lens(text: str, agent_type: str = "redteam-lens", **extra) -> None:
    payload = {"hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": agent_type,
               "agent_transcript_path": _agent_transcript("a1"),
               "last_assistant_message": text, **extra}
    assert _stdin_main(["subagent-hook"], json.dumps(payload)) == 0


def _verdicts(tmp_path: Path, sha12: str, overrides: dict | None = None,
              log: bool = True) -> list[str]:
    """Write one verdict file per lens; log each through the SubagentStop handler (a real run)."""
    overrides = overrides or {}
    paths = []
    for lens in rg.LENSES:
        verdict, sha = overrides.get(lens, ("PASS", sha12))
        if verdict is None:
            continue
        text = _verdict_text(lens, sha, verdict)
        if log:
            _log_lens(text)
        p = _write(tmp_path / "verdicts" / f"{lens}.md", text)
        paths.append(str(p))
    return paths


def _hook(payload, capsys, raw: str | None = None, monkeypatch=None):
    data = raw if raw is not None else json.dumps(payload)
    capsys.readouterr()
    rc = _stdin_main(["hook"], data)
    out = capsys.readouterr().out.strip()
    assert rc == 0
    return json.loads(out) if out else None


def _deny_reason(res) -> str:
    assert res is not None, "expected deny"
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"
    return res["hookSpecificOutput"]["permissionDecisionReason"]


def _post(payload, capsys, monkeypatch=None):
    assert _stdin_main(["post-hook"], json.dumps(payload)) == 0
    capsys.readouterr()


def _record_text(tmp_path, text, capsys, name="draft.txt", source="Thread with Marc and Anna.\n",
                 extra: list[str] | None = None):
    draft = _write(tmp_path / name, text)
    src = _write(tmp_path / "src" / "notes.md", source)
    sha12 = rg.sha_of(text, rg.is_html_path(draft))[:12]
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts",
                    *_verdicts(tmp_path, sha12), *(extra or [])], capsys)
    assert rc == 0, out
    return draft


# ------------------------------------------------------------------ normalise

def test_normalise_html_equals_plain():
    plain = "Hello Anna,\n\nThe price is €30 — it’s “final”.\n\nBest"
    htm = ("<div><p>Hello Anna,</p><p>The price is &euro;30 &mdash; it&rsquo;s "
           "&ldquo;final&rdquo;.</p><p>Best</p></div>")
    assert rg.normalise(plain) == rg.normalise(htm, is_html=True)
    assert rg.sha_of(plain) == rg.sha_of(htm, True)
    assert rg.normalise(plain) == "Hello Anna, The price is €30 — it's \"final\". Best"


def test_normalise_preserves_case_and_collapses_ws():
    assert rg.normalise("  A\t b \n\n C ") == "A b C"
    assert rg.sha_of("abc") != rg.sha_of("ABC")


# ------------------------------------------------------------------ extraction

def _kinds(text):
    return [(c["kind"], c["text"]) for c in rg.extract_claims(text)]


def test_money_extraction_variants():
    claims = rg.extract_claims("Cost €30k, then 30 €, $1,200.50, 1 200,50 EUR, "
                               "€30–50 per seat, GBP 12.")
    money = {c["text"]: c["values"] for c in claims if c["kind"] == "money"}
    assert 30000.0 in money["€30k"][0]
    assert 30.0 in money["30 €"][0]
    assert 1200.5 in money["$1,200.50"][0]
    assert 1200.5 in money["1 200,50 EUR"][0]
    rng = money["€30–50"]
    assert 30.0 in rng[0] and 50.0 in rng[1]
    assert 12.0 in money["GBP 12"][0]


def test_percent_unit_extraction_incl_french():
    k = _kinds("A 15% cut, 2,5 pour cent, 3 weeks, 2 jours, 6 mois, 10 users.")
    assert ("percent", "15%") in k
    assert ("percent", "2,5 pour cent") in k
    for t in ("3 weeks", "2 jours", "6 mois", "10 users"):
        assert ("unit", t) in k


def test_date_extraction_normalised():
    claims = rg.extract_claims("Due 28 October 2026, or Oct 28, or 2026-10-28, or 28/10/2026, "
                               "le 3 mars 2027, le 1er août.")
    dates = [c["date"] for c in claims if c["kind"] == "date"]
    assert dates.count((28, 10, 2026)) == 3
    assert (28, 10, None) in dates
    assert (3, 3, 2027) in dates
    assert (1, 8, None) in dates


def test_quote_extraction_min_three_words():
    k = _kinds('He said "ok fine" and “we will ship Friday” and « nous livrons '
               'vendredi soir ».')
    quotes = [t for kind, t in k if kind == "quote"]
    assert len(quotes) == 2
    assert not any("ok fine" in q for q in quotes)


def test_mot_pour_mot_is_overclaim(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Nous reprenons votre texte mot pour mot, garanti.")
    src = _write(tmp_path / "s.md", "rien\n")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
    res = json.loads(out)
    over = {c["text"].lower() for c in res["claims"] if c["status"] == "overclaim"}
    assert "mot pour mot" in over and "garanti" in over
    assert rc == 0  # overclaims warn, never fail


# ------------------------------------------------------------------ grounding

def test_ungrounded_quote_exit_1(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "As you wrote, “we will pay within ten days”.")
    src = _write(tmp_path / "src" / "thread.txt", "We will pay within thirty days.\n")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src.parent), "--json"],
                   capsys)
    assert rc == 1
    q = [c for c in json.loads(out)["claims"] if c["kind"] == "quote"][0]
    assert q["status"] == "ungrounded"


def test_grounded_quote_curly_vs_straight(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "You said “we’ll pay within 30 days.”")
    src = _write(tmp_path / "t.eml", "From: a@b.c\nSubject: x\n\nHi,\nWe'll pay within\n30 days.\n")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
    assert rc == 0, out


def test_grounded_number_reports_source_line(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "The fee is €1,200 for 3 months.")
    _write(tmp_path / "src" / "a.md", "intro\n\nSetup fee: €1,200 one-off\n")
    _write(tmp_path / "src" / "b.txt", "Term: 3 months\n")
    _write(tmp_path / "src" / "img.png", "binary")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(tmp_path / "src"),
                    "--json"], capsys)
    res = json.loads(out)
    assert rc == 0
    money = [c for c in res["claims"] if c["kind"] == "money"][0]
    assert money["status"] == "grounded" and not money["weak"]
    assert money["source"].endswith("a.md:3")
    assert "Setup fee" in money["source_line"]
    assert any(s["reason"] == "unsupported type" for s in res["skipped"])
    assert (Path(os.environ["REDTEAM_DIR"]) / "ground" / f"{res['sha12']}.json").is_file()


def test_bare_number_grounding_is_weak(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Price: €45.")
    src = _write(tmp_path / "s.csv", "item,qty\nwidgets,45\n")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
    money = json.loads(out)["claims"][0]
    assert rc == 1 and money["status"] == "weak" and money["weak"] is True


def test_date_grounding(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Delivery on 28 October 2026.")
    src = _write(tmp_path / "s.md", "Kickoff 2026-10-28 confirmed\n")
    rc, _ = _run(["ground", "--draft", str(draft), "--sources", str(src)], capsys)
    assert rc == 0
    src.write_text("Kickoff 2026-10-29\n", encoding="utf-8")
    rc, _ = _run(["ground", "--draft", str(draft), "--sources", str(src)], capsys)
    assert rc == 1


def test_asset_voyages_regression_context_is_lens_job(tmp_path, state, capsys):
    """€30 in the source was UptimeRobot + AI cost, not SMS. Lexically it grounds; the reported
    source_line must expose the UptimeRobot context so the grounding lens can catch it."""
    draft = _write(tmp_path / "d.txt", "Paid text alerts up to ≈ €30 per month.")
    src = _write(tmp_path / "av.md", AV_SOURCE)
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
    money = [c for c in json.loads(out)["claims"] if c["kind"] == "money"][0]
    assert rc == 0
    assert money["status"] == "grounded"
    assert "UptimeRobot" in money["source_line"]
    assert money["source"].endswith("av.md:2")


def test_draft_inside_sources_dir_is_skipped(tmp_path, state, capsys):
    d = tmp_path / "work"
    draft = _write(d / "draft.md", "Total €999.")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(d), "--json"], capsys)
    res = json.loads(out)
    assert rc == 1
    assert res["skipped"][0]["reason"] == "is the draft itself"


def test_missing_source_is_usage_error(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "x")
    rc, _ = _run(["ground", "--draft", str(draft), "--sources", str(tmp_path / "nope")], capsys)
    assert rc == 2


# ------------------------------------------------------------------ record / waive / check

def _av_setup(tmp_path):
    draft = _write(tmp_path / "d.txt", "UptimeRobot and AI cost about €30 per month.")
    src = _write(tmp_path / "av.md", AV_SOURCE)
    sha12 = rg.sha_of(draft.read_text(encoding="utf-8"))[:12]
    return draft, src, sha12


def test_record_refuses_missing_lens(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12, {"reputation": (None, None)})
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "reputation" in out


def test_record_refuses_fail_verdict(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12, {"downside": ("FAIL", sha12)})
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "downside verdict is FAIL" in out


def test_record_refuses_stale_sha(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12, {"counterparty": ("PASS", "0123456789ab")})
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "stale DRAFT-SHA 0123456789ab" in out and "counterparty" in out


def test_record_refuses_ungrounded(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Discount of 40% agreed.")
    src = _write(tmp_path / "av.md", AV_SOURCE)
    sha12 = rg.sha_of(draft.read_text(encoding="utf-8"))[:12]
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts",
                    *_verdicts(tmp_path, sha12)], capsys)
    assert rc == 3 and "ungrounded" in out


def test_record_idempotent_and_check(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12)
    argv = ["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs]
    assert _run(argv, capsys)[0] == 0
    rc, out = _run(argv, capsys)
    assert rc == 0 and "already" in out
    rows = (state / "passes.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["sha12"] == sha12 and row["waived"] is False and row["lenses"] == list(rg.LENSES)
    assert row["sources"][0]["sha256"]
    assert [v["lens"] for v in row["verdicts"]] == list(rg.LENSES)
    assert _run(["check", "--file", str(draft)], capsys)[0] == 0
    other = _write(tmp_path / "other.txt", "different text")
    assert _run(["check", "--file", str(other)], capsys)[0] == 3


def test_agent_waive_is_refused(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Quick yes.")
    rc = rg.main(["waive", "--draft", str(draft), "--reason", "operator: send as-is"])
    err = capsys.readouterr().err
    assert rc == 2 and "redteam waive <sha12>" in err
    assert not (state / "passes.jsonl").exists()
    assert _run(["check", "--file", str(draft)], capsys)[0] == 3


# ------------------------------------------------------------------ hook

GM = "mcp__Gmail__"


def test_hook_denies_unpassed_send(state, capsys, monkeypatch):
    res = _hook({"tool_name": GM + "send_message", "tool_input": {"to": "x@y.z",
                 "body": "Paid alerts €30"}}, capsys, monkeypatch=monkeypatch)
    hso = res["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"].startswith("redteam gate: send_message.body")
    assert "/redteam" in hso["permissionDecisionReason"]


def test_hook_allows_after_record_and_html_variant(tmp_path, state, capsys, monkeypatch):
    text = "Hello,\n\nThank you for the call.\n\nBest"
    _record_text(tmp_path, text, capsys)
    assert _hook({"tool_name": GM + "send_message", "tool_input": {"body": text}}, capsys,
                 monkeypatch=monkeypatch) is None
    same_html = "<p>Hello,</p><p>Thank you for the call.</p><p>Best</p>"
    assert _hook({"tool_name": "mcp__claude_ai_Gmail__reply",
                  "tool_input": {"body": text, "htmlBody": same_html}}, capsys,
                 monkeypatch=monkeypatch) is None


def test_hook_denies_html_smuggle(tmp_path, state, capsys, monkeypatch):
    text = "Hello, thank you for the call."
    _record_text(tmp_path, text, capsys)
    res = _hook({"tool_name": GM + "send_message",
                 "tool_input": {"body": text, "htmlBody": "<p>Hello, the price is €9k.</p>"}},
                capsys, monkeypatch=monkeypatch)
    assert "htmlBody" in res["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_fail_closed_on_malformed(state, capsys, monkeypatch):
    res = _hook(None, capsys, raw='{"tool_name": "mcp__Gmail__send_message", oops',
                monkeypatch=monkeypatch)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "fail-closed" in res["hookSpecificOutput"]["permissionDecisionReason"]
    res = _hook({"tool_name": GM + "reply", "tool_input": "oops"}, capsys,
                monkeypatch=monkeypatch)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_non_gated_and_benign_cases(state, capsys, monkeypatch):
    for payload in (
        {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"tool_name": GM + "search_threads", "tool_input": {"query": "x"}},
        {"tool_name": GM + "update_draft", "tool_input": {"draftId": "r1"}},
        {"tool_name": GM + "list_drafts", "tool_input": {"query": "is:draft"}},
        {"tool_name": GM + "create_draft", "tool_input": {}},
        {"tool_name": GM + "forward", "tool_input": {"messageId": "m1", "to": "a@b.c"}},
    ):
        assert _hook(payload, capsys, monkeypatch=monkeypatch) is None, payload
    res = _hook({"tool_name": GM + "forward", "tool_input": {"forwardText": "FYI, all good"}},
                capsys, monkeypatch=monkeypatch)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_reason_excerpt_bounded(state, capsys, monkeypatch):
    body = "secret-ish " * 200
    res = _hook({"tool_name": GM + "create_draft", "tool_input": {"body": body}}, capsys,
                monkeypatch=monkeypatch)
    reason = res["hookSpecificOutput"]["permissionDecisionReason"]
    assert len(reason) < 300 and body.strip() not in reason


def test_draft_id_flow_via_post_hook(tmp_path, state, capsys, monkeypatch):
    passed = "Hi Marc, confirming our call tomorrow."
    _record_text(tmp_path, passed, capsys)
    send = {"tool_name": GM + "send_message", "tool_input": {"draftId": "r-77"}}
    # unknown draft -> deny
    assert _hook(send, capsys, monkeypatch=monkeypatch) is not None
    # create_draft response as JSON string
    _post({"tool_name": GM + "create_draft", "tool_input": {"body": passed},
           "tool_response": json.dumps({"id": "r-77", "message": {"id": "m1"}})},
          capsys, monkeypatch)
    assert _hook(send, capsys, monkeypatch=monkeypatch) is None
    # update_draft with unvetted text -> latest row not passed -> deny
    _post({"tool_name": GM + "update_draft",
           "tool_input": {"draftId": "r-77", "body": "Hi Marc, price is now €5k."},
           "tool_response": [{"type": "text", "text": "ok"}]}, capsys, monkeypatch)
    assert _hook(send, capsys, monkeypatch=monkeypatch) is not None
    # subject-only update is not recorded; content-block response with id in text
    _post({"tool_name": GM + "create_draft", "tool_input": {"body": passed},
           "tool_response": {"content": [{"type": "text", "text": '{"id": "r-88"}'}]}},
          capsys, monkeypatch)
    rows = (state / "drafts.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(r)["draft_id"] for r in rows] == ["r-77", "r-77", "r-88"]


def test_post_hook_never_fails(state, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"garbage")))
    assert rg.main(["post-hook"]) == 0
    assert capsys.readouterr().out == ""


def test_extract_draft_id_variants():
    assert rg.extract_draft_id({"draft": {"id": "d1"}}) == "d1"
    assert rg.extract_draft_id('Draft created. draftId: r-abc123') == "r-abc123"
    assert rg.extract_draft_id(None) is None


# ------------------------------------------------------------------ CLI + shell wrapper

def test_cli_sha_and_help(tmp_path, state):
    draft = _write(tmp_path / "d.html", "<p>Hi</p><p>there</p>")
    out = subprocess.run([sys.executable, str(SCRIPT), "sha", "--draft", str(draft)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert out.returncode == 0 and out.stdout.strip() == rg.sha_of("Hi there")[:12]
    h = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert h.returncode == 0 and "record" in h.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_shell_wrapper_fail_closed_on_garbage(tmp_path):
    env = dict(os.environ)
    env["REDTEAM_DIR"] = str(tmp_path / "state")
    env["CLAUDE_PROJECT_DIR"] = str(ROOT)
    out = subprocess.run(["bash", str(HOOK_SH), "pre"], input="garbage{{", capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env)
    assert out.returncode == 0 and out.stdout == ""  # non-outward crash: allowed, logged
    out = subprocess.run(["bash", str(HOOK_SH), "pre"],
                         input='{"tool_name":"mcp__Gmail__send_message", garbage{{',
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env)
    assert out.returncode == 0
    res = json.loads(out.stdout)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"
    # missing script -> still deny
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    out = subprocess.run(["bash", str(HOOK_SH), "pre"], input=json.dumps(
        {"tool_name": GM + "send_message", "tool_input": {}}), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    # post mode never blocks
    out = subprocess.run(["bash", str(HOOK_SH), "post"], input="garbage", capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env)
    assert out.returncode == 0 and out.stdout == ""


# ------------------------------------------------------------------ tamper evidence (fix 1)

def test_forged_verdict_files_refused(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12, log=False)
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "not produced by a logged redteam-lens subagent run" in out
    # logged, but by a general-purpose agent rather than redteam-lens
    for lens in rg.LENSES:
        _log_lens(_verdict_text(lens, sha12), agent_type="general-purpose")
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "not redteam-lens" in out


def test_bare_appended_pass_row_refused(tmp_path, state, capsys):
    text = "Hi, thanks for the call."
    draft = _write(tmp_path / "d.txt", text)
    sha = rg.sha_of(text)
    rg._append_jsonl(state / "passes.jsonl", {
        "sha256": sha, "sha12": sha[:12], "waived": False,
        "verdicts": [{"lens": lens, "out_sha256": "0" * 64} for lens in rg.LENSES]})
    rg._append_jsonl(state / "passes.jsonl", {"sha12": sha[:12], "waived": True, "reason": "x"})
    rc, out = _run(["check", "--file", str(draft)], capsys)
    assert rc == 3 and "not backed" in out
    res = _hook({"tool_name": GM + "send_message", "tool_input": {"body": text}}, capsys)
    assert "has not passed" in _deny_reason(res)


def test_subagent_hook_from_transcript_file(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    paths = []
    for lens in rg.LENSES:
        text = _verdict_text(lens, sha12)
        head, rest = text.split("VERDICT", 1)
        lines = [
            {"type": "user", "message": {"role": "user", "content": "brief"}},
            {"type": "assistant", "agentId": "a9", "isSidechain": True,
             "message": {"id": "m1", "role": "assistant",
                         "content": [{"type": "tool_use", "name": "Read", "input": {}}]}},
            {"type": "assistant", "agentId": "a9", "isSidechain": True,
             "message": {"id": "m2", "role": "assistant",
                         "content": [{"type": "text", "text": head.rstrip("\n")}]}},
            {"type": "assistant", "agentId": "a9", "isSidechain": True,
             "message": {"id": "m2", "role": "assistant",
                         "content": [{"type": "text", "text": "VERDICT" + rest}]}},
        ]
        tr = _agent_transcript("a9", lines)
        payload = {"agent_id": "a9", "agent_type": "redteam-lens",
                   "agent_transcript_path": tr, "transcript_path": str(tmp_path / "main")}
        assert _stdin_main(["subagent-hook"], json.dumps(payload)) == 0
        paths.append(str(_write(tmp_path / "v" / f"{lens}.md", text)))
    rows = rg._read_jsonl(state / "verdicts.jsonl")
    assert len(rows) == 4 and rows[0]["text_from"] == "agent_transcript_path"
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *paths],
                   capsys)
    assert rc == 0, out


def test_subagent_hook_reads_handback_tool_call(tmp_path, state, capsys):
    """Live shape (2026-11-04): no last_assistant_message; the report is the `message` input
    of a SubagentHandback tool_use, followed by its tool_result."""
    draft, src, sha12 = _av_setup(tmp_path)
    paths = []
    for lens in rg.LENSES:
        text = _verdict_text(lens, sha12)
        lines = [
            {"type": "user", "message": {"role": "user", "content": "brief"}},
            {"type": "assistant", "message": {"id": "m1", "role": "assistant", "content": [
                {"type": "tool_use", "name": "SubagentHandback", "input": {"message": text}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "delivered"}]}},
        ]
        tr = _agent_transcript("a7", lines)
        payload = {"agent_id": "a7", "agent_type": "redteam-lens",
                   "agent_transcript_path": tr, "transcript_path": str(tmp_path / "main")}
        assert _stdin_main(["subagent-hook"], json.dumps(payload)) == 0
        paths.append(str(_write(tmp_path / "hb" / f"{lens}.md", text)))
    assert len(rg._read_jsonl(state / "verdicts.jsonl")) == 4
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *paths],
                   capsys)
    assert rc == 0, out


def test_subagent_hook_ignores_main_agent_text(tmp_path, state, capsys):
    main = tmp_path / "main.jsonl"
    main.write_text(json.dumps({"type": "assistant", "message": {
        "id": "m", "role": "assistant",
        "content": [{"type": "text", "text": _verdict_text("grounding", "a" * 12)}]}}) + "\n",
        encoding="utf-8")
    payload = {"agent_id": "a1", "agent_type": "redteam-lens", "transcript_path": str(main)}
    assert _stdin_main(["subagent-hook"], json.dumps(payload)) == 0
    assert not (state / "verdicts.jsonl").exists()
    assert capsys.readouterr().out == ""


# ------------------------------------------------------------------ operator waiver (fix 2)

def test_prompt_waiver_and_silence(tmp_path, state, capsys):
    text = "Ship it, Marc."
    draft = _write(tmp_path / "d.txt", text)
    sha12 = rg.sha_of(text)[:12]
    for prompt in ("please redteam waive " + sha12, "redteam waive " + sha12 + "x ok",
                   "hello"):
        capsys.readouterr()
        assert _stdin_main(["prompt-hook"], json.dumps({"prompt": prompt})) == 0
        assert capsys.readouterr().out == ""
    assert not (state / "passes.jsonl").exists()
    assert _stdin_main(["prompt-hook"], json.dumps(
        {"prompt": f"  Redteam waive {sha12.upper()} client asked for it today"})) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit",
                                         "additionalContext": f"redteam: operator waived {sha12}"}
    w = rg._read_jsonl(state / "waivers.jsonl")[0]
    assert w["reason"] == "client asked for it today"
    assert _run(["check", "--file", str(draft)], capsys) == (0, f"PASSED {sha12} (waived)\n")
    assert _hook({"tool_name": GM + "send_message",
                  "tool_input": {"to": ["any@x.com"], "body": text}}, capsys) is None


# ------------------------------------------------------------------ envelope + HTML (fix 3)

def test_html_href_and_comment_bound(tmp_path, state, capsys):
    page = '<p>See <a href="https://docs.example.com/v1">the doc</a>.</p>'
    assert "[link: https://docs.example.com/v1]" in rg.normalise(page, True)
    assert "[comment: hidden]" in rg.normalise("<p>x</p><!-- hidden -->", True)
    assert "[img: https://t.example/p.png]" in rg.normalise('<img src="https://t.example/p.png">',
                                                            True)
    _record_text(tmp_path, page, capsys, name="d.html",
                 source="docs.example.com v1 doc\n")
    send = {"tool_name": GM + "send_message", "tool_input": {"htmlBody": page}}
    assert _hook(send, capsys) is None
    send["tool_input"]["htmlBody"] = page.replace("v1", "evil")
    assert "has not passed" in _deny_reason(_hook(send, capsys))
    send["tool_input"]["htmlBody"] = page + "<!-- price is 9k -->"
    assert "has not passed" in _deny_reason(_hook(send, capsys))
    send["tool_input"]["htmlBody"] = page + "<script>alert(1)</script>"
    assert "script" in _deny_reason(_hook(send, capsys))
    send["tool_input"]["htmlBody"] = page + "<style></style>"
    assert _hook(send, capsys) is None
    bad = _write(tmp_path / "x.html", "<p>Hi</p><style>p{color:red}</style>")
    assert rg.main(["sha", "--draft", str(bad)]) == 2


def test_envelope_subject_to_attachment(tmp_path, state, capsys):
    text = "Hi Anna, the proposal is attached."
    att = tmp_path / "p.pdf"
    att.write_bytes(b"%PDF-1 proposal")
    _record_text(tmp_path, text, capsys, extra=[
        "--subject", "Proposal v2", "--to", "Anna@Client.com", "--cc", "boss@client.com",
        "--attachments", str(att)])
    b64 = base64.b64encode(att.read_bytes()).decode()
    ti = {"to": ["anna@client.com"], "subject": "Proposal  v2", "body": text,
          "attachments": [{"content": b64, "filename": "p.pdf"}]}
    send = {"tool_name": GM + "send_message", "tool_input": ti}
    assert _hook(send, capsys) is None
    for key, val, frag in (
            ("subject", "Proposal v3", "subject"),
            ("to", ["anna@client.com", "eve@rival.com"], "eve@rival.com"),
            ("bcc", ["anna@client.com"], "bcc"),
            ("attachments", [{"content": base64.b64encode(b"other").decode()}], "attachment"),
            ("attachments", [{"filename": "x.pdf"}], "attachment")):
        bad = dict(ti, **{key: val})
        assert frag in _deny_reason(_hook({"tool_name": GM + "send_message", "tool_input": bad},
                                          capsys)), key
    # reply has no subject: only the body + recipients are checked
    assert _hook({"tool_name": GM + "reply", "tool_input": {
        "messageId": "m1", "body": text, "cc": ["boss@client.com"]}}, capsys) is None
    # envelope-only update_draft is checked against the draft's recorded text
    _post({"tool_name": GM + "create_draft", "tool_input": {"body": text},
           "tool_response": {"id": "d-1"}}, capsys)
    upd = {"tool_name": GM + "update_draft", "tool_input": {"draftId": "d-1", "subject": "Hack"}}
    assert "subject" in _deny_reason(_hook(upd, capsys))
    upd["tool_input"]["subject"] = "Proposal v2"
    assert _hook(upd, capsys) is None
    assert _deny_reason(_hook({"tool_name": GM + "create_draft",
                               "tool_input": {"subject": "Hello"}}, capsys))


# ------------------------------------------------------------------ unknown fields (fix 4)

def test_unknown_text_keys_gated(tmp_path, state, capsys):
    text = "Hello Marc, see you soon."
    _record_text(tmp_path, text, capsys)
    res = _hook({"tool_name": GM + "send_message",
                 "tool_input": {"body": text, "message": "Also, price doubles."}}, capsys)
    assert "send_message.message" in _deny_reason(res)
    res = _hook({"tool_name": "mcp__claude_ai_Gmail__send_email",
                 "tool_input": {"to": ["a@b.co"], "text": "unvetted"}}, capsys)
    assert "generic.text" in _deny_reason(res)
    assert _hook({"tool_name": "mcp__claude_ai_Gmail__send_email",
                  "tool_input": {"text": text}}, capsys) is None
    assert "to recipient" in _deny_reason(_hook({"tool_name": "mcp__claude_ai_Gmail__send_email",
                                                 "tool_input": {"to": ["marc@x.co"],
                                                                "text": text}}, capsys))


def test_calendar_invites(tmp_path, state, capsys):
    cal = "mcp__Google_Calendar__"
    ti = {"summary": "Kickoff", "description": "Agenda: scope review with Marc.",
          "startTime": "2026-11-10T10:00:00", "endTime": "2026-11-10T11:00:00"}
    assert _hook({"tool_name": cal + "create_event", "tool_input": ti}, capsys) is None
    inv = dict(ti, attendees=[{"email": "marc@client.com"}])
    assert "description" in _deny_reason(
        _hook({"tool_name": cal + "create_event", "tool_input": inv}, capsys))
    _record_text(tmp_path, ti["description"], capsys,
                 extra=["--subject", "Kickoff", "--to", "marc@client.com"])
    assert _hook({"tool_name": cal + "create_event", "tool_input": inv}, capsys) is None
    extra = dict(inv, attendees=[{"email": "marc@client.com"}, {"email": "eve@rival.com"}])
    assert "eve@rival.com" in _deny_reason(
        _hook({"tool_name": cal + "create_event", "tool_input": extra}, capsys))
    assert "eve@rival.com" in _deny_reason(_hook({"tool_name": cal + "update_event", "tool_input": {
        "eventId": "e1", "description": ti["description"], "summary": "Kickoff",
        "addedAttendeeEmails": ["eve@rival.com"]}}, capsys))
    assert "summary" in _deny_reason(_hook({"tool_name": cal + "create_event",
                                            "tool_input": dict(inv, summary="Free audit!")},
                                           capsys))
    upd = {"eventId": "e1", "description": "Moved, bring the contract."}
    assert _deny_reason(_hook({"tool_name": cal + "update_event", "tool_input": upd}, capsys))
    assert _hook({"tool_name": cal + "update_event",
                  "tool_input": dict(upd, notificationLevel="NONE")}, capsys) is None


# ------------------------------------------------------------------ Bash senders (fix 5)

SMTP = "smtp" + "lib"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _bash(cmd: str, capsys, cwd: Path | None = None):
    return _hook({"tool_name": "Bash", "tool_input": {"command": cmd},
                  "cwd": str(cwd or ROOT)}, capsys)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_bash_senders(tmp_path, state, capsys):
    assert _bash("ls -la && git status", capsys) is None
    assert _bash("python3 -m pytest tests/test_redteam_gate.py -q", capsys) is None
    r = _deny_reason(_bash(f'python3 -c "import {SMTP}; {SMTP}.SMTP(\'x\')"', capsys))
    assert SMTP in r and "Gmail tool" in r
    assert _deny_reason(_bash(f"python3 - <<'EOF'\nimport {SMTP}\nEOF", capsys))
    assert _deny_reason(_bash("curl -X POST https://api.send" "grid.com/v3/mail/send", capsys))
    assert _deny_reason(_bash("curl https://api.instan" "tly.ai/api/v2/emails/reply", capsys))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo / "pipe" / "digest.py", f"import {SMTP}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    assert _bash("python3 pipe/digest.py --live", capsys, repo) is None
    assert _bash(f"cd {repo} && python3 -u pipe/digest.py", capsys, tmp_path) is None
    assert _deny_reason(_bash("python3 pipe/digest.py; echo done", capsys, repo))
    _write(repo / "tmp_send.py", f"import {SMTP}\n")
    assert "tmp_send.py" in _deny_reason(_bash("python3 tmp_send.py", capsys, repo))
    _write(repo / "pipe" / "digest.py", f"import {SMTP}  # edited\n")
    assert _deny_reason(_bash("python3 pipe/digest.py", capsys, repo))


def test_bash_mentioning_gate_is_not_forging(state, capsys):
    """Live regression 2026-11-04: commits that merely named the gate files were denied."""
    for cmd in ("git add execution/infrastructure/redteam_gate.py .claude/hooks/"
                "redteam-outward-gate.sh && git commit -m 'fix: SubagentStop hook, prompt-hook "
                "waivers, post-hook drafts, import fixes'",
                "python3 execution/infrastructure/redteam_gate.py ground --draft d.txt "
                "--sources s.md",
                "grep -n hook execution/infrastructure/redteam_gate.py"):
        assert _bash(cmd, capsys) is None, cmd


# ------------------------------------------------------------------ strict verdicts (fix 6)

@pytest.mark.parametrize("text", [
    "> LENS: grounding\n> DRAFT-SHA: {s}\n> VERDICT: PASS\n",
    "# Review\nLENS: grounding\nDRAFT-SHA: {s}\nVERDICT: PASS\n",
    "LENS: grounding\nVERDICT: PASS\nDRAFT-SHA: {s}\n",
    "**LENS:** grounding\nDRAFT-SHA: {s}\nVERDICT: PASS\n",
    "LENS: grounding\nDRAFT-SHA: {s}\nVERDICT: PASS (with caveats)\n",
])
def test_strict_verdict_parsing(text, tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    body = text.format(s=sha12)
    assert "error" in rg.parse_verdict(body)
    _log_lens(body)
    assert not (state / "verdicts.jsonl").exists()
    vs = _verdicts(tmp_path, sha12, {"grounding": (None, None)})
    vf = _write(tmp_path / "bad.md", body)
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs,
                    str(vf)], capsys)
    assert rc == 3 and "malformed verdict" in out


# ------------------------------------------------------------------ grounding (fixes 7, 8)

def test_weak_claim_refused_by_record(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Price: €45.")
    src = _write(tmp_path / "s.csv", "item,qty\nwidgets,45\n")
    sha12 = rg.sha_of(draft.read_text(encoding="utf-8"))[:12]
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts",
                    *_verdicts(tmp_path, sha12)], capsys)
    assert rc == 3 and "1 weak claim" in out


def test_yearless_date_weak_unless_same_or_current_year(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Delivery on 28 October.")
    src = _write(tmp_path / "s.md", "Kickoff 28 October 2020\n")

    def status():
        rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
        return rc, [c for c in json.loads(out)["claims"] if c["kind"] == "date"][0]["status"]

    assert status() == (1, "weak")
    src.write_text("Kickoff 28 October\n", encoding="utf-8")
    assert status() == (0, "grounded")
    src.write_text(f"Kickoff 28/10/{datetime.now().year}\n", encoding="utf-8")
    assert status() == (0, "grounded")


def test_name_claims(tmp_path, state, capsys):
    text = ("Hi Anna,\n\nThanks for the intro to Sarah Connor on Monday. Write to bob@acme.com.\n"
            "Great news. Looking forward.\n\nBest,\nDebanjan\nFounder, ProdCraft\n"
            "debanjan@prodcraft.fyi\n")
    names = sorted(c["text"] for c in rg.extract_claims(text) if c["kind"] == "name")
    assert names == ["Anna", "Sarah Connor", "bob@acme.com"]
    draft = _write(tmp_path / "d.txt", text)
    src = _write(tmp_path / "thread.md", "From: Anna Lee <BOB@acme.com>\nMeet sarah connor\n")
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(src), "--json"], capsys)
    st = {c["text"]: c["status"] for c in json.loads(out)["claims"] if c["kind"] == "name"}
    assert rc == 1 and st == {"Anna": "grounded", "Sarah Connor": "ungrounded",
                              "bob@acme.com": "grounded"}
    src.write_text("From: Anna Lee <bob@acme.com>\nIntro: Sarah Connor (CTO)\n", encoding="utf-8")
    assert _run(["ground", "--draft", str(draft), "--sources", str(src)], capsys)[0] == 0


def test_self_copy_source_skipped(tmp_path, state, capsys):
    text = "The fee is €4,000 for the audit. Delivery takes 3 weeks from signature. We start soon."
    draft = _write(tmp_path / "drafts" / "d.txt", text)
    copy = _write(tmp_path / "drafts" / "d.v1.md", "# old\n" + text.replace("soon", "Monday"))
    rc, out = _run(["ground", "--draft", str(draft), "--sources", str(copy.parent), "--json"],
                   capsys)
    res = json.loads(out)
    assert rc == 1
    assert any(s["reason"].startswith("looks like the draft itself") for s in res["skipped"])
    assert res["summary"]["ungrounded"] == 2


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_shell_wrapper_subagent_and_prompt_modes(tmp_path):
    env = dict(os.environ)
    env["REDTEAM_DIR"] = str(tmp_path / "state")
    env["CLAUDE_PROJECT_DIR"] = str(ROOT)
    tr = _agent_transcript("w1")

    def run(mode, data):
        return subprocess.run(["bash", str(HOOK_SH), mode], input=data, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env=env)

    out = run("subagent", json.dumps({"agent_type": "redteam-lens", "agent_id": "w1",
                                      "agent_transcript_path": tr,
                                      "last_assistant_message": _verdict_text("downside",
                                                                              "b" * 12)}))
    assert out.returncode == 0 and out.stdout == ""
    assert (tmp_path / "state" / "verdicts.jsonl").is_file()
    out = run("prompt", json.dumps({"prompt": "redteam waive " + "c" * 12 + " ok"}))
    assert json.loads(out.stdout)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    out = run("prompt", json.dumps({"prompt": "hi"}))
    assert out.returncode == 0 and out.stdout == ""
    out = run("subagent", "garbage")
    assert out.returncode == 0 and out.stdout == ""


# ------------------------------------------------------------------ HMAC ledger (2026-11-05)

def test_unsigned_tampered_wrong_key_rows_ignored(tmp_path, state, capsys, monkeypatch):
    text = "Hello Marc, see you soon."
    draft = _record_text(tmp_path, text, capsys)
    assert _run(["check", "--file", str(draft)], capsys)[0] == 0
    passes = state / "passes.jsonl"
    good = passes.read_text(encoding="utf-8")
    # tampered: flip a field but keep the old mac
    row = json.loads(good.splitlines()[0])
    row["to"] = ["eve@rival.com"]
    passes.write_text(json.dumps(row) + "\n", encoding="utf-8")
    rc, out = _run(["check", "--file", str(draft)], capsys)
    assert rc == 3 and "ignored unsigned rows: 1" in out
    # unsigned: mac stripped
    row.pop("mac")
    passes.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert _run(["check", "--file", str(draft)], capsys)[0] == 3
    # wrong key: original rows, different key file
    passes.write_text(good, encoding="utf-8")
    assert _run(["check", "--file", str(draft)], capsys)[0] == 0
    monkeypatch.setenv("REDTEAM_KEY_FILE", str(tmp_path / "other" / "hmac.key"))
    rc, out = _run(["check", "--file", str(draft)], capsys)
    assert rc == 3 and "ignored unsigned rows" in out
    res = _hook({"tool_name": GM + "send_message", "tool_input": {"body": text}}, capsys)
    assert "has not passed" in _deny_reason(res)


def test_unsigned_verdict_rows_do_not_back_record(tmp_path, state, capsys):
    draft, src, sha12 = _av_setup(tmp_path)
    vs = _verdicts(tmp_path, sha12, log=False)
    state.mkdir(parents=True, exist_ok=True)
    with (state / "verdicts.jsonl").open("a", encoding="utf-8") as fh:
        for lens in rg.LENSES:
            fh.write(json.dumps({"lens": lens, "sha12": sha12, "verdict": "PASS",
                                 "agent_type": "redteam-lens",
                                 "out_sha256": rg.verdict_sha(_verdict_text(lens, sha12))}) + "\n")
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs],
                   capsys)
    assert rc == 3 and "not produced by a logged" in out


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_key_file_created_0600(tmp_path):
    kp = Path(os.environ["REDTEAM_KEY_FILE"])
    rg._KEY_CACHE.clear()
    key = rg.load_key()
    assert len(key) == 32 and kp.read_bytes() == key
    assert (kp.stat().st_mode & 0o777) == 0o600
    assert (kp.parent.stat().st_mode & 0o777) == 0o700
    assert rg.load_key() == key


def test_hook_subcommands_require_env(monkeypatch, state, capsys):
    monkeypatch.delenv("REDTEAM_HOOK")
    for sub in ("hook", "post-hook", "subagent-hook", "prompt-hook"):
        rc = _stdin_main([sub], json.dumps({"prompt": "redteam waive " + "a" * 12 + " x"}))
        assert rc != 0, sub
        assert "hook-only" in capsys.readouterr().err
    assert not (state / "passes.jsonl").exists()


def test_subagent_hook_transcript_root_check(tmp_path, state):
    text = _verdict_text("grounding", "a" * 12)
    outside = _write(tmp_path / "elsewhere" / "agent-a1.jsonl", "")
    misnamed = _agent_transcript("zz")
    for payload in (
            {"agent_id": "a1", "agent_type": "redteam-lens", "last_assistant_message": text},
            {"agent_id": "a1", "agent_type": "redteam-lens", "last_assistant_message": text,
             "agent_transcript_path": str(outside)},
            {"agent_id": "a1", "agent_type": "redteam-lens", "last_assistant_message": text,
             "agent_transcript_path": misnamed},
            {"agent_id": "a1", "agent_type": "redteam-lens", "last_assistant_message": text,
             "agent_transcript_path": str(Path(os.environ["REDTEAM_TRANSCRIPT_ROOT"])
                                          / ".." / "elsewhere" / "agent-a1.jsonl")}):
        assert _stdin_main(["subagent-hook"], json.dumps(payload)) == 0
    assert not (state / "verdicts.jsonl").exists()
    _log_lens(text)
    assert len(rg._read_jsonl(state / "verdicts.jsonl")) == 1


def test_bash_false_positive_regressions(tmp_path, state, capsys):
    for cmd in ("cat .tmp/redteam/passes.jsonl 2>/dev/null",
                "git commit -m 'fix: redteam_gate.py hook and prompt-hook paths'",
                "grep -n _append_jsonl execution/infrastructure/redteam_gate.py",
                f"cat > tests/fixtures/mailer.py <<'EOF'\nimport {SMTP}\nsmtp = {SMTP}.SMTP('h')\nEOF",
                f"echo 'import {SMTP}' > fixture.py",
                "printf 'curl https://api.send" "grid.com/v3/mail/send' > notes.txt",
                "echo '{}' >> .tmp/redteam/passes.jsonl"):
        assert _bash(cmd, capsys) is None, cmd


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_bash_module_and_obfuscation(tmp_path, state, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo / "pipe" / "__init__.py", "")
    _write(repo / "pipe" / "digest.py", f"import {SMTP}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    assert _bash("python3 -m pipe.digest --live", capsys, repo) is None
    _write(repo / "pipe" / "sender.py", f"import {SMTP}\n")
    assert "module pipe.sender" in _deny_reason(_bash("python3 -m pipe.sender", capsys, repo))
    _write(repo / "pipe" / "digest.py", f"import {SMTP}  # edited\n")
    assert _deny_reason(_bash("python3 -m pipe.digest", capsys, repo))
    payload = base64.b64encode(f"import {SMTP}".encode()).decode()
    assert "base64" in _deny_reason(_bash(f"echo {payload} | base64 -d | python3", capsys, repo))
    assert _deny_reason(_bash(f"python3 <<'EOF'\nimport {SMTP}\nEOF", capsys, repo))
    assert _deny_reason(_bash(f"cat <<'EOF' | python3 -\nimport {SMTP}\nEOF", capsys, repo))


# ------------------------------------------------------------------ audit warnings (2026-11-05)

@pytest.mark.parametrize("cmd", [
    "echo hi | mail -s s x@y.z",
    "msmtp x@y.z < m",
    "swaks --to x@y.z --server smtp.example.com",
    "mutt -s hi x@y.z < body.txt",
    "curl --url smtp" "s://smtp.gmail.com:465 --mail" "-rcpt x@y.z -T m.txt",
    "curl smtp" "://localhost:25 -T m.txt",
    "curl -X POST https://api.mailgun" ".net/v3/d/messages",
    "curl https://api.brevo" ".com/v3/smtp/email",
    "aws ses send" "-email --from a@b.co",
    "aws sesv2 send" "-email --from-email-address a@b.co",
    "curl https://email.eu-west-1.amazon" "aws.com/",
    'python3 -c "svc.users().drafts().se' 'nd(userId=\'me\', body=b).execute()"',
    "timeout 30 python3 -c 'import " + "smtp" "lib" "'",
    "poetry run python -c 'import " + "smtp" "lib" "'",
    "uv run python -c 'import " + "smtp" "lib" "'",
    "FOO=1 sudo -E mail x@y.z < m",
])
def test_bash_more_senders_denied(cmd, state, capsys):
    assert _deny_reason(_bash(cmd, capsys)), cmd


def test_bash_crash_or_null_command_allows(state, capsys):
    assert _hook({"tool_name": "Bash", "tool_input": {"command": None}}, capsys) is None
    capsys.readouterr()
    assert _stdin_main(["hook"], "{not json") != 0
    assert capsys.readouterr().out == ""
    assert _stdin_main(["hook"], json.dumps({"tool_name": "Bash", "tool_input": "x"})) != 0
    assert capsys.readouterr().out == ""
    for cmd in ("grep -rn mail docs/", "git log --grep 'mail'", "ls mail/"):
        assert _bash(cmd, capsys) is None, cmd


def test_calendar_location_gated(tmp_path, state, capsys):
    cal = "mcp__Google_Calendar__"
    desc = "Agenda: scope review with Marc at Cafe Lumen."
    _record_text(tmp_path, desc, capsys, source="Thread with Marc and Anna at Cafe Lumen.\n",
                 extra=["--subject", "Kickoff", "--to", "marc@client.com"])
    ti = {"summary": "Kickoff", "description": desc, "attendees": [{"email": "marc@client.com"}]}
    assert _hook({"tool_name": cal + "create_event",
                  "tool_input": dict(ti, location="Cafe Lumen")}, capsys) is None
    assert "location" in _deny_reason(_hook({"tool_name": cal + "create_event", "tool_input": dict(
        ti, location="Free audit worth 5k, reply now")}, capsys))
    assert _hook({"tool_name": cal + "create_event", "tool_input": {
        "summary": "Solo", "location": "Anywhere"}}, capsys) is None


# ------------------------------------------------------------------ re-audit (2026-11-05)

def test_bash_write_then_run_denied(tmp_path, state, capsys):
    cmd = f"cat > z.py <<'EOF'\nimport {SMTP}\nEOF\npython3 z.py"
    assert _deny_reason(_bash(cmd, capsys, tmp_path))
    # pure fixture write (no exec) still allowed
    assert _bash(f"cat > z.py <<'EOF'\nimport {SMTP}\nEOF", capsys, tmp_path) is None


def test_bash_any_file_argument_scanned(tmp_path, state, capsys):
    _write(tmp_path / "s.py", f"import {SMTP}\n")
    _write(tmp_path / "s.pyw", f"import {SMTP}\n")
    _write(tmp_path / "sendit", f"import {SMTP}\n")
    for cmd in ('python3 "s.py"', "python3 s.pyw", "python3 sendit", "python3 < s.py",
                'sh -c "python3 s.py"', "bash -c 'cd . && python3 sendit'"):
        assert _deny_reason(_bash(cmd, capsys, tmp_path)), cmd
    _write(tmp_path / "ok.py", "print(1)\n")
    assert _bash('python3 "ok.py"', capsys, tmp_path) is None


def test_dict_recipient_without_email_unparseable(tmp_path, state, capsys):
    addrs, bad = rg.parse_addrs([{"address": "x@y.z"}, {"displayName": "Eve"}, {"email": "a@b.co"}])
    assert addrs == {"a@b.co"} and len(bad) == 2
    text = "Hello Marc, see you soon."
    _record_text(tmp_path, text, capsys, extra=["--to", "marc@x.co"])
    res = _hook({"tool_name": GM + "send_message", "tool_input": {
        "to": [{"address": "eve@rival.com"}], "body": text}}, capsys)
    assert "unparseable" in _deny_reason(res)


def test_calendar_unknown_attendee_keys(tmp_path, state, capsys):
    cal = "mcp__Google_Calendar__"
    desc = "Agenda: scope review with Marc."
    _record_text(tmp_path, desc, capsys, extra=["--subject", "Kickoff", "--to", "marc@client.com"])
    base = {"summary": "Kickoff", "description": desc}
    assert _hook({"tool_name": cal + "create_event", "tool_input": dict(
        base, guests=["marc@client.com"])}, capsys) is None
    assert "eve@rival.com" in _deny_reason(_hook({"tool_name": cal + "create_event",
                                                  "tool_input": dict(base, guests=["eve@rival.com"])},
                                                 capsys))
    assert _deny_reason(_hook({"tool_name": cal + "create_event", "tool_input": {
        "startTime": "2026-11-10T10:00:00", "invitees": ["eve@rival.com"]}}, capsys))
    assert _deny_reason(_hook({"tool_name": cal + "create_event", "tool_input": dict(
        base, attendees=[{"displayName": "Eve"}])}, capsys))
    assert _hook({"tool_name": cal + "create_event", "tool_input": dict(
        base, guestPermissions={"canInviteOthers": False}, attendees=["marc@client.com"])},
        capsys) is None
    assert _hook({"tool_name": cal + "create_event", "tool_input": dict(
        base, attendees=["marc@client.com"], guestsCanInviteOthers=False, guestsCanModify=True,
        guestsCanSeeOtherGuests=True)}, capsys) is None


# ------------------------------------------------------------------ third audit (2026-11-05)

WAIVE = "redteam" " waive"


def test_bash_nested_claude_waiver_denied(tmp_path, state, capsys):
    s12 = "a" * 12
    _write(tmp_path / "p.txt", f"{WAIVE} {s12} ok\n")
    for cmd in (f'claude -p "{WAIVE} {s12} ok"', f"npx claude -p '{WAIVE.upper()} {s12}'",
                f"timeout 60 /opt/claude-code/bin/claude -p \"$(cat p.txt)\" < p.txt",
                f"claude -p < p.txt", f"claude -p <<'EOF'\n{WAIVE} {s12}\nEOF"):
        assert "nested claude" in _deny_reason(_bash(cmd, capsys, tmp_path)), cmd
    assert _bash('claude -p "summarise the README"', capsys, tmp_path) is None
    assert _bash(f"git commit -m 'doc: {WAIVE} is operator-only'", capsys, tmp_path) is None


def test_prompt_hook_refuses_in_nested_session(tmp_path, state, capsys, monkeypatch):
    s12 = "b" * 12
    monkeypatch.setenv("REDTEAM_MIN_CLAUDE_DEPTH", "2")
    capsys.readouterr()
    assert _stdin_main(["prompt-hook"], json.dumps({"prompt": f"{WAIVE} {s12} ok"})) == 0
    assert "NOT recorded" in capsys.readouterr().out
    assert not (state / "waivers.jsonl").exists()
    monkeypatch.setenv("REDTEAM_MIN_CLAUDE_DEPTH", "0")  # cannot lower the real depth
    assert rg.nested_claude_depth() >= 0
    assert rg._is_claude_cmdline(["/opt/claude-code/bin/claude", "--preload", "x"])
    assert rg._is_claude_cmdline(["node", "/x/@anthropic-ai/claude-code/cli.js"])
    assert not rg._is_claude_cmdline(["/bin/bash", "-c", "claude"])


def test_record_refuses_envelope_rebinding(tmp_path, state, capsys):
    text = "Hi Anna, the proposal is attached."
    draft = _record_text(tmp_path, text, capsys, extra=["--to", "anna@client.com"])
    src = tmp_path / "src" / "notes.md"
    sha12 = rg.sha_of(text)[:12]
    vs = [str(tmp_path / "verdicts" / f"{lens}.md") for lens in rg.LENSES]
    base = ["record", "--draft", str(draft), "--sources", str(src), "--verdicts", *vs]
    rc, out = _run(base + ["--to", "anna@client.com"], capsys)
    assert rc == 0 and "already recorded" in out
    rc, out = _run(base + ["--to", "anna@client.com", "eve@rival.com"], capsys)
    assert rc == 3 and "different envelope" in out and sha12 in out
    rc, out = _run(base + ["--to", "anna@client.com", "--subject", "New"], capsys)
    assert rc == 3 and "subject_sha" in out


def test_bash_path_indirection_scanned(tmp_path, state, capsys):
    side = tmp_path / "side"
    _write(side / "s.py", f"import {SMTP}\n")
    _write(side / "pkg" / "__init__.py", "")
    _write(side / "pkg" / "mailer.py", f"import {SMTP}\n")
    for cmd in (f"F={side}/s.py; python3 $F", f"F={side}/s.py python3 ${{F}}",
                f"export D={side} && python3 $D/s.py", f"python3 {side}/s*.py",
                f"cd {side} && python3 -m s", f"cd {side}; python3 s.py",
                f"PYTHONPATH={side} python3 -m pkg.mailer", f"cd {tmp_path} && cd side && python3 s.py"):
        assert _deny_reason(_bash(cmd, capsys, tmp_path)), cmd
    _write(side / "ok.py", "print(1)\n")
    assert _bash(f"F={side}/ok.py; python3 $F", capsys, tmp_path) is None
    assert _bash("python3 $UNSET_VAR_XYZ/run.py", capsys, tmp_path) is None


@pytest.mark.parametrize("cmd", [
    "python3 -c 'from sendgrid import SendGrid" "APIClient'",
    "python3 -c 'import yag" "mail'",
    "curl https://api.mail" "jet.com/v3.1/send",
    "curl https://mandrill" "app.com/api/1.0/messages/send",
    "curl https://server.smart" "lead.ai/api/v1/campaigns",
    "ssmtp x@y.z < m",
    "send" "email -f a@b.co -t x@y.z -m hi",
    "exim -t < m",
    "exim4 -t < m",
])
def test_bash_more_hosts_and_clis(cmd, state, capsys):
    assert _deny_reason(_bash(cmd, capsys)), cmd
