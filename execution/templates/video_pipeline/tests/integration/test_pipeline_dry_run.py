"""
Integration test: full pipeline in --dry-run mode. No network, no MCP, €0.
Asserts every stage exits 0 and emits its expected plan output.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2]
PY = sys.executable


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Copy the template into a temp dir so tests don't pollute .tmp/."""
    dest = tmp_path / "video_pipeline"
    shutil.copytree(HERE, dest, ignore=shutil.ignore_patterns(
        "node_modules", ".tmp", "out", "__pycache__", "*.pyc",
    ))
    # Override slug so cache paths land inside sandbox
    cfg_path = dest / "config" / "pipeline.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["slug"] = "sandbox_test"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return dest


def _run(cmd, cwd):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )


def test_analyze_dry_run_exit_zero(sandbox):
    r = _run([PY, "analyze.py", "--input", "https://youtu.be/abc", "--dry-run"], sandbox)
    assert r.returncode == 0, f"stderr:\n{r.stderr}"
    payload = json.loads(r.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["plan"]["would_extract_frames"] == 24
    assert payload["plan"]["cost_eur_estimate"] == 0.0


def test_generate_dry_run_from_stub_plan(sandbox):
    # Write a minimal analysis.json by hand — we're testing generate in isolation.
    slug_dir = sandbox / ".tmp" / "sandbox_test"
    slug_dir.mkdir(parents=True, exist_ok=True)
    plan_path = slug_dir / "analysis.json"
    plan_path.write_text(json.dumps({
        "source": "test",
        "asset_plan": [
            {"kind": "video", "prompt": "a hummingbird", "duration_seconds": 4,
             "aspect_ratio": "9:16"},
        ],
    }), encoding="utf-8")

    r = _run([PY, "generate.py", "--plan", str(plan_path), "--dry-run"], sandbox)
    assert r.returncode == 0, f"stderr:\n{r.stderr}"
    payload = json.loads(r.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["plan"]["n_assets"] == 1
    assert payload["plan"]["would_generate"] >= 1
    assert payload["plan"]["cost_eur_estimate"] >= 0.0


def test_publish_dry_run_emits_manual_bundle(sandbox):
    # Fabricate a "video" file
    slug_dir = sandbox / ".tmp" / "sandbox_test"
    slug_dir.mkdir(parents=True, exist_ok=True)
    fake_video = slug_dir / "final.mp4"
    fake_video.write_bytes(b"\x00" * 1024)  # 1KB placeholder

    r = _run([PY, "publish.py", "--video", str(fake_video),
              "--platforms", "tiktok,youtube"], sandbox)
    assert r.returncode == 0, f"stderr:\n{r.stderr}"
    payload = json.loads(r.stdout)
    assert payload["mode"] == "dry-run"
    assert "tiktok" in payload["platforms"]
    receipts = Path(payload["receipts"])
    assert receipts.exists()


def test_generate_kill_switch_on_ceiling(sandbox):
    slug_dir = sandbox / ".tmp" / "sandbox_test"
    slug_dir.mkdir(parents=True, exist_ok=True)

    # Set daily ceiling to €0.01 so any live estimate trips it
    cfg_path = sandbox / "config" / "pipeline.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["cost"]["daily_cost_ceiling_eur"] = 0.01
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    plan_path = slug_dir / "analysis.json"
    plan_path.write_text(json.dumps({
        "source": "test",
        "asset_plan": [{"kind": "video", "prompt": "x", "duration_seconds": 4,
                        "aspect_ratio": "9:16"}],
    }), encoding="utf-8")

    r = _run([PY, "generate.py", "--plan", str(plan_path), "--live"], sandbox)
    assert r.returncode == 3, f"expected DAILY_COST_CEILING_HIT exit 3, got {r.returncode}"
    assert "DAILY_COST_CEILING_HIT" in r.stderr
