"""
description: Tests for execution/gtm_icp_filters/prospect_evidence_pack.py (qualification rule, edge cases).
inputs: none (builds temp pack dirs)
outputs: pytest results
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "execution" / "gtm_icp_filters" / "prospect_evidence_pack.py"


def run(d):
    return subprocess.run([sys.executable, str(SCRIPT), "--dir", str(d)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def row(name, finder="PASS", verifier="PASS", visual="DATED", png=None):
    return {"company": name, "url": "https://x.example", "vertical": "v", "hq": "h", "size": "s", "size_source": "src",
            "trigger_quote": "q", "trigger_url": "https://src.example", "trigger_date": "2026-09-01",
            "markers": ["© 2019"], "visual_verdict": visual, "visual_notes": "n", "desk_png": png, "mob_png": png,
            "finder_status": finder, "verifier_status": verifier, "verifier_notes": "", "jev_score": 3.0}


def test_missing_rows_dir_fails_loud(tmp_path):
    r = run(tmp_path / "nope")
    assert r.returncode != 0 and "no rows/ folder" in r.stderr


def test_empty_rows_dir(tmp_path):
    (tmp_path / "rows").mkdir()
    r = run(tmp_path)
    assert r.returncode == 0 and "rows=0 qualified=0" in r.stdout
    assert (tmp_path / "pack.html").exists() and (tmp_path / "pack.csv").exists()


def test_bad_json_fails_loud(tmp_path):
    (tmp_path / "rows").mkdir()
    (tmp_path / "rows" / "x.json").write_text("[{bad", encoding="utf-8")
    r = run(tmp_path)
    assert r.returncode != 0 and "bad row file" in r.stderr


def test_qualification_rule_and_hostile_text(tmp_path):
    (tmp_path / "rows").mkdir()
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG")
    rows = [row("<script>alert(1)</script>", png=str(png)), row("Disagree", finder="FAIL"),
            row("Modern", visual="MODERN"), row("VerifierFail", verifier="FAIL")]
    (tmp_path / "rows" / "v.json").write_text(json.dumps(rows), encoding="utf-8")
    r = run(tmp_path)
    assert "rows=4 qualified=1" in r.stdout
    html = (tmp_path / "pack.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert (tmp_path / "img" / "a.png").exists()


def test_rerun_is_idempotent(tmp_path):
    (tmp_path / "rows").mkdir()
    (tmp_path / "rows" / "v.json").write_text(json.dumps([row("A")]), encoding="utf-8")
    run(tmp_path)
    first = (tmp_path / "pack.csv").read_text(encoding="utf-8")
    run(tmp_path)
    assert (tmp_path / "pack.csv").read_text(encoding="utf-8") == first
