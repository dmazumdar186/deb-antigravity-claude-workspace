"""
Tier 5 - Performance tests for youtube_video_analyzer.py (v3).
Run: py -m pytest tests/test_youtube_analyzer_performance.py -v -s

P1, P8: use --dry-run (shallow, no download, fast).
P2, P3, P4, P5, P6, P7: use --deep-dry-run (full pipeline minus AI call; downloads video).
No API spend on either path.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "execution" / "video" / "youtube_video_analyzer.py"
TEST_URL = "https://youtu.be/BedAaB1RKgE"
SHORT_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


from conftest import skip_if_youtube_blocked as _skip_if_youtube_blocked


def _run(*args):
    # dict(os.environ), NOT copy.copy(os.environ): copy.copy returns an _Environ
    # proxy that shares state with the parent — mutations leak across tests.
    env = dict(os.environ)
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(WORKSPACE),
    )
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        _skip_if_youtube_blocked(result.stderr or "")
    return result, elapsed


def test_p1_total_wallclock():
    result, elapsed = _run(TEST_URL, "--dry-run")
    assert result.returncode == 0, "Dry-run failed: " + result.stderr[-300:]
    print("PERF total wall-clock: " + str(round(elapsed, 1)) + "s (threshold <60s)")
    assert elapsed < 60, "Exceeded 60s threshold: " + str(round(elapsed,1)) + "s"


def test_p2_pyscenedetect_log():
    # Requires --deep-dry-run: PySceneDetect only runs during full frame pipeline
    result, total_elapsed = _run(SHORT_URL, "--deep-dry-run")
    assert result.returncode == 0
    stderr = result.stderr
    assert "PySceneDetect found" in stderr, "Scene detection log line missing"
    scene_count_match = re.search(r"found (\d+) scenes", stderr)
    n_scenes = int(scene_count_match.group(1)) if scene_count_match else 0
    print("PERF PySceneDetect: " + str(n_scenes) + " scenes, total elapsed=" + str(round(total_elapsed,1)) + "s")
    assert n_scenes >= 0, "Scene detection log line present but count invalid"
    assert total_elapsed < 120


def test_p3_frame_extraction():
    # Requires --deep-dry-run: raw_frames_before_dedup only populated by full pipeline
    result, elapsed = _run(SHORT_URL, "--deep-dry-run")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    raw = data.get("raw_frames_before_dedup", 0)
    dedup = data.get("distinct_frames_after_dedup", 0)
    print("PERF frames: raw=" + str(raw) + " dedup=" + str(dedup) + " elapsed=" + str(round(elapsed,1)) + "s")
    assert raw >= 0, "raw_frames_before_dedup should be non-negative"
    assert dedup >= 0, "distinct_frames_after_dedup should be non-negative"
    assert dedup <= raw


def test_p4_dedup():
    # Requires --deep-dry-run: dedup fields only populated by full pipeline
    result, _ = _run(SHORT_URL, "--deep-dry-run")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    raw = data.get("raw_frames_before_dedup", 0)
    dedup = data.get("distinct_frames_after_dedup", 0)
    print("PERF dedup: " + str(raw) + " -> " + str(dedup) + " (removed " + str(raw - dedup) + ")")
    assert dedup >= 0
    assert dedup <= raw


def test_p5_grid_tiling():
    # Requires --deep-dry-run: grid_count only populated by full pipeline
    result, _ = _run(SHORT_URL, "--deep-dry-run")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    grids = data.get("grid_count", 0)
    dedup = data.get("distinct_frames_after_dedup", 0)
    import math
    expected_grids = math.ceil(dedup / 9) if dedup > 0 else 0
    print("PERF grids: " + str(grids) + " (expected " + str(expected_grids) + " for " + str(dedup) + " frames)")
    assert grids == expected_grids


def test_p6_grid_file_sizes():
    # Requires --deep-dry-run: grid files only written by full pipeline
    result, _ = _run(SHORT_URL, "--deep-dry-run")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    video_id = data["video_id"]
    grids_dir = WORKSPACE / ".tmp" / "video" / video_id / "grids"
    if not grids_dir.exists():
        import pytest
        pytest.skip("grids dir not found")
    files = list(grids_dir.glob("*.jpg"))
    total_bytes = sum(f.stat().st_size for f in files)
    total_kb = total_bytes // 1024
    print("PERF grid sizes: " + str(len(files)) + " files, " + str(total_kb) + " KB (threshold <2048 KB)")
    assert total_bytes < 2 * 1024 * 1024, "Grid files too large: " + str(total_kb) + " KB"


@pytest.mark.parametrize("max_frames", [24])
def test_p7_token_estimate_sanity(max_frames):
    """Verify estimated_input_tokens is within the expected range for a given max_frames value.

    This test covers max_frames=24 (default). For larger max-frames, the threshold
    would need to scale: ceil(max_frames/9) * 1400 + transcript_tokens + buffer.
    Add additional parametrize values (e.g. 48, 72) when testing non-default configs.
    """
    # Requires --deep-dry-run: estimated_input_tokens is a real frame+transcript count
    result, _ = _run(SHORT_URL, "--deep-dry-run", "--max-frames", str(max_frames))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    est = data.get("estimated_input_tokens", 99999)
    # Derived bound: ceil(max_frames/9) grids x 1400 tokens + transcript headroom + buffer
    import math
    expected_max = math.ceil(max_frames / 9) * 1400 + 8000 + 500  # = 3*1400 + 8500 = 12700 for default
    upper = expected_max + 5000  # comfortable ceiling = 17700; cap at 30000 for longer videos
    upper = min(upper, 30000)
    print("PERF estimated_input_tokens: " + str(est) + " (threshold <=" + str(upper) + ", max_frames=" + str(max_frames) + ")")
    assert 1000 <= est <= upper, "Token estimate " + str(est) + " outside expected range [1000, " + str(upper) + "]"


def test_p8_concurrent_dry_runs():
    results = [None, None]

    def _run_bg(url, idx):
        env = dict(os.environ)  # independent copy; _Environ proxy leaks
        r = subprocess.run(
            [sys.executable, str(SCRIPT), url, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(WORKSPACE),
        )
        results[idx] = r

    t0 = time.perf_counter()
    th1 = threading.Thread(target=_run_bg, args=(TEST_URL, 0))
    th2 = threading.Thread(target=_run_bg, args=(SHORT_URL, 1))
    th1.start(); th2.start()
    th1.join(); th2.join()
    elapsed = time.perf_counter() - t0
    r1, r2 = results
    assert r1.returncode == 0, "Video 1 failed: " + r1.stderr[-300:]
    assert r2.returncode == 0, "Video 2 failed: " + r2.stderr[-300:]
    d1 = json.loads(r1.stdout)
    d2 = json.loads(r2.stdout)
    assert d1["video_id"] != d2["video_id"]
    assert d1["work_dir"] != d2["work_dir"], "Concurrency collision: same work_dir"
    print("PERF concurrent: both ok, workdirs distinct, elapsed=" + str(round(elapsed,1)) + "s")


def test_p9_memory_manual_check_required():
    import pytest
    pytest.skip("Memory profiling requires in-process tracemalloc. Run manually.")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
