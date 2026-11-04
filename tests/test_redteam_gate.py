"""
test_redteam_gate.py
description: Unit tests for execution/infrastructure/redteam_gate.py and the outward-gate hook wrapper.
inputs: none (tmp_path state via REDTEAM_DIR; no network, no LLM).
outputs: pytest results.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution" / "infrastructure"))

import redteam_gate as rg  # noqa: E402

SCRIPT = ROOT / "execution" / "infrastructure" / "redteam_gate.py"
HOOK_SH = ROOT / ".claude" / "hooks" / "redteam-outward-gate.sh"

AV_SOURCE = "# Asset Voyages costs\nUptimeRobot Solo + AI ≈ €30/month; SMS ≈ €3\n"


@pytest.fixture()
def state(tmp_path, monkeypatch):
    sd = tmp_path / "state"
    monkeypatch.setenv("REDTEAM_DIR", str(sd))
    return sd


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _run(argv, capsys):
    rc = rg.main(argv)
    out = capsys.readouterr().out
    return rc, out


def _verdicts(tmp_path: Path, sha12: str, overrides: dict | None = None) -> list[str]:
    overrides = overrides or {}
    paths = []
    for lens in rg.LENSES:
        verdict, sha = overrides.get(lens, ("PASS", sha12))
        if verdict is None:
            continue
        p = _write(tmp_path / "verdicts" / f"{lens}.md",
                   f"# Review\nLENS: {lens}\nDRAFT-SHA: {sha}\nVERDICT: {verdict}\nNotes...\n")
        paths.append(str(p))
    return paths


def _hook(payload, capsys, raw: str | None = None, monkeypatch=None):
    data = raw if raw is not None else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data.encode("utf-8"))))
    rc = rg.main(["hook"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    return json.loads(out) if out else None


def _post(payload, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin",
                        io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8"))))
    assert rg.main(["post-hook"]) == 0
    capsys.readouterr()


def _record_text(tmp_path, text, capsys, name="draft.txt"):
    draft = _write(tmp_path / name, text)
    src = _write(tmp_path / "src" / "notes.md", "nothing numeric here\n")
    sha12 = rg.sha_of(text, rg.is_html_path(draft))[:12]
    rc, out = _run(["record", "--draft", str(draft), "--sources", str(src), "--verdicts",
                    *_verdicts(tmp_path, sha12)], capsys)
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
    assert rc == 0 and money["status"] == "grounded" and money["weak"] is True


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
    assert _run(["check", "--file", str(draft)], capsys)[0] == 0
    other = _write(tmp_path / "other.txt", "different text")
    assert _run(["check", "--file", str(other)], capsys)[0] == 3


def test_waive_requires_operator_prefix(tmp_path, state, capsys):
    draft = _write(tmp_path / "d.txt", "Quick yes.")
    assert _run(["waive", "--draft", str(draft), "--reason", "looks fine"], capsys)[0] == 2
    assert _run(["waive", "--draft", str(draft), "--reason", "operator:"], capsys)[0] == 2
    rc, out = _run(["waive", "--draft", str(draft), "--reason",
                    "Operator: send as-is, 2026-11-04"], capsys)
    assert rc == 0 and out.startswith("**Red-team waiver**:")
    rc, _ = _run(["waive", "--draft", str(draft), "--reason", "operator: again"], capsys)
    assert rc == 0
    rows = (state / "passes.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["waived"] is True
    assert _run(["check", "--file", str(draft)], capsys)[0] == 0


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
    res = _hook(None, capsys, raw="{not json", monkeypatch=monkeypatch)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "fail-closed" in res["hookSpecificOutput"]["permissionDecisionReason"]
    res = _hook({"tool_name": GM + "reply", "tool_input": "oops"}, capsys,
                monkeypatch=monkeypatch)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_allows_non_gated_and_benign_cases(state, capsys, monkeypatch):
    for payload in (
        {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"tool_name": GM + "search_threads", "tool_input": {"query": "x"}},
        {"tool_name": GM + "update_draft", "tool_input": {"draftId": "r1", "subject": "New"}},
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
    assert out.returncode == 0
    res = json.loads(out.stdout)
    assert res["hookSpecificOutput"]["permissionDecision"] == "deny"
    # missing script -> still deny
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    out = subprocess.run(["bash", str(HOOK_SH), "pre"], input="{}", capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    # post mode never blocks
    out = subprocess.run(["bash", str(HOOK_SH), "post"], input="garbage", capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env)
    assert out.returncode == 0 and out.stdout == ""
