"""Offline unit tests for execution/video/lemo_bootstrap.py (no network; needs only git).

Run: python3 -m unittest tests.test_lemo_bootstrap -v   (also collected by pytest)
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.video import lemo_bootstrap as lb  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", check=True)
    return r.stdout.strip()


def _make_repo(root: Path, commits: int = 2) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    shas = []
    for i in range(commits):
        (root / "f.txt").write_text(f"v{i}\n", encoding="utf-8")
        _git(root, "add", "f.txt")
        _git(root, "commit", "--quiet", "-m", f"c{i}")
        shas.append(_git(root, "rev-parse", "HEAD"))
    return shas


def _make_tar(path: Path, members: dict[str, bytes]) -> str:
    with tarfile.open(path, "w") as t:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("git"), "git required")
class PinCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "lemo"
        self.shas = _make_repo(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_head_equal_to_pin_passes(self):
        self.assertEqual(lb.verify_pin(self.repo, self.shas[-1]), self.shas[-1])

    def test_head_not_pin_is_refused_and_nothing_fetched(self):
        calls = []
        real_run = lb.run

        def spy(cmd, **kw):
            calls.append(cmd)
            return real_run(cmd, **kw)

        with mock.patch.object(lb, "run", side_effect=spy):
            with self.assertRaises(lb.CheckFailed) as ctx:
                lb.verify_pin(self.repo, self.shas[0])
        self.assertIn("Refusing", str(ctx.exception))
        flat = " ".join(" ".join(c) for c in calls)
        for verb in ("pull", "fetch", "reset", "checkout"):
            self.assertNotIn(f" {verb}", flat)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), self.shas[-1])  # untouched

    def test_check_cli_exit_1_on_pin_mismatch(self):
        with redirect_stdout(io.StringIO()):
            rc = lb.main(["check", "--target", str(self.repo), "--cache", str(self.tmp / "c")])
        self.assertEqual(rc, 1)  # repo HEAD is not lb.PIN_SHA

    def test_lemo_managed_flag_fails_hygiene(self):
        _git(self.repo, "config", "lemo.managed", "true")
        rep = lb.Report()
        with redirect_stdout(io.StringIO()):
            lb.check_clone_hygiene(self.repo, rep)
        self.assertTrue(rep.failed)

    def test_modified_tracked_file_fails_hygiene(self):
        (self.repo / "f.txt").write_text("tampered\n", encoding="utf-8")
        rep = lb.Report()
        with redirect_stdout(io.StringIO()):
            lb.check_clone_hygiene(self.repo, rep)
        self.assertTrue(any(s == "FAIL" and i == "tracked files" for s, i, _ in rep.rows))


class Manifest(unittest.TestCase):
    def test_manifest_written_atomically_with_pin_and_artefacts(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            art = [{"name": "voice", "sha256": "ab" * 32, "size": 3}]
            path = lb.write_manifest(target, {"artefacts": art, "versions": {"node": "v22"}})
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path.name, "bootstrap_manifest.json")
            self.assertEqual(doc["pin_sha"], lb.PIN_SHA)
            self.assertEqual(doc["artefacts"][0]["sha256"], "ab" * 32)
            self.assertEqual(doc["schema"], 1)
            self.assertRegex(doc["written_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
            self.assertEqual([p.name for p in target.iterdir()], ["bootstrap_manifest.json"])  # no temp left

    def test_env_file_quotes_paths(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "a b"
            target.mkdir()
            env = lb.write_env(target, target / ".venv", "/m dir", None, Path(d))
            text = env.read_text(encoding="utf-8")
            self.assertIn(f"export LEMO_PIN={lb.PIN_SHA}", text)
            self.assertIn("WHISPER_MODEL='/m dir'", text)
            self.assertIn("HF_HUB_OFFLINE=1", text)


class Checksum(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "mirror"
        self.src.mkdir()
        self.good = _make_tar(self.src / "pack.tar", {"core/tts/a.bin": b"hello"})
        self.size = (self.src / "pack.tar").stat().st_size

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _url(self) -> str:
        return (self.src / "pack.tar").as_uri()

    def test_good_download_verified_and_cached(self):
        dest = self.tmp / "cache" / "pack.tar"
        src = lb.fetch_verified("pack", self.good, self.size, dest, [self._url()])
        self.assertEqual(src, self._url())
        self.assertTrue(dest.exists())
        # second call is served from the cache, no download
        with mock.patch.object(lb, "download", side_effect=AssertionError("network")):
            self.assertTrue(lb.fetch_verified("pack", self.good, self.size, dest, [self._url()]).startswith("cache:"))

    def test_mismatch_fails_closed_without_pull_or_fallthrough(self):
        dest = self.tmp / "cache" / "pack.tar"
        wrong = "0" * 64
        real = lb.download
        tried = []

        def dl(url, d, timeout=1800):
            tried.append(url)
            real(url, d)

        with mock.patch.object(lb, "download", side_effect=dl), mock.patch.object(lb.subprocess, "run") as sp:
            sp.side_effect = lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "")  # curl "fails"→urllib
            with mock.patch.object(lb.shutil, "which", return_value=None):
                with self.assertRaises(lb.ChecksumMismatch) as ctx:
                    lb.fetch_verified("pack", wrong, self.size, dest, [self._url(), "file:///never-tried"])
        msg = str(ctx.exception)
        self.assertIn("Do NOT git pull", msg)
        self.assertEqual(tried, [self._url()])  # no fallthrough to the second source
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name("pack.tar.part").exists())  # bad download removed
        sp.assert_not_called()  # no git (or any) subprocess was run

    def test_tampered_cache_is_quarantined_and_exit_2(self):
        dest = self.tmp / "cache" / "pack.tar"
        dest.parent.mkdir()
        dest.write_bytes(b"x" * self.size)  # same size, wrong content
        with self.assertRaises(lb.ChecksumMismatch):
            lb.fetch_verified("pack", self.good, self.size, dest, [self._url()])
        self.assertFalse(dest.exists())
        self.assertEqual(len(list(dest.parent.glob("pack.tar.mismatch-*"))), 1)

    def test_size_mismatch_reported(self):
        p = self.tmp / "x"
        p.write_bytes(b"abc")
        with self.assertRaises(lb.ChecksumMismatch):
            lb.verify_artefact(p, hashlib.sha256(b"abc").hexdigest(), 4, "x")

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_extract_refuses_out_of_scope_and_tracked(self):
        repo = self.tmp / "repo"
        _make_repo(repo, 1)
        evil = self.tmp / "evil.tar"
        _make_tar(evil, {"core/tts/ok.bin": b"1", "core/render/video.mjs": b"pwn"})
        with self.assertRaises(lb.CheckFailed):
            lb.safe_extract(evil, repo, "core/tts/")
        self.assertFalse((repo / "core").exists())  # nothing extracted
        tracked = self.tmp / "tracked.tar"
        _make_tar(tracked, {"f.txt": b"overwrite"})
        with self.assertRaises(lb.CheckFailed):
            lb.safe_extract(tracked, repo, "")
        ok = lb.safe_extract(self.src / "pack.tar", repo, "core/tts/")
        self.assertEqual(ok, ["core/tts/a.bin"])


class DryRun(unittest.TestCase):
    def test_install_dry_run_no_network_no_writes(self):
        with tempfile.TemporaryDirectory() as d:
            target, cache = Path(d) / "lemo", Path(d) / "cache"
            boom = AssertionError("network or write during dry run")
            out = io.StringIO()
            with mock.patch.object(lb, "download", side_effect=boom), \
                    mock.patch.object(lb, "clone_at_pin", side_effect=boom), \
                    mock.patch.object(lb, "safe_extract", side_effect=boom), \
                    mock.patch.object(lb, "write_manifest", side_effect=boom), \
                    mock.patch.object(lb, "find_python", return_value=("/usr/bin/python3.13", (3, 13, 0))), \
                    redirect_stdout(out):
                rc = lb.main(["install", "--dry-run", "--target", str(target), "--cache", str(cache),
                              "--packs", "all"])
            self.assertEqual(rc, 0)
            self.assertFalse(target.exists())
            self.assertFalse(cache.exists())
            text = out.getvalue()
            self.assertIn("dry run complete", text)
            self.assertIn(lb.PIN_SHA, text)
            self.assertIn("--require-hashes", text)
            self.assertNotIn("setup.sh", text)

    def test_lock_dry_run_makes_no_request(self):
        with mock.patch.object(lb, "venv_distributions", return_value={"numpy": "2.5.4"}), \
                mock.patch.object(lb.urllib.request, "urlopen", side_effect=AssertionError("network")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(lb.main(["lock", "--from-venv", "/nonexistent", "--dry-run"]), 0)


class LockAndHelpers(unittest.TestCase):
    def test_repo_lock_is_fully_hashed(self):
        pins = lb.parse_lock(lb.LOCK_PATH)
        self.assertGreater(len(pins), 10)
        self.assertEqual([n for n, p in pins.items() if not p["hashes"]], [])
        self.assertIn("kokoro-onnx", pins)

    def test_wheel_filter(self):
        self.assertTrue(lb.wheel_ok("numpy-2.5.4-cp313-cp313-manylinux_2_28_x86_64.whl"))
        self.assertTrue(lb.wheel_ok("x-1-py3-none-any.whl"))
        self.assertTrue(lb.wheel_ok("x-1.tar.gz"))
        self.assertFalse(lb.wheel_ok("numpy-2.5.4-cp313-cp313-win_amd64.whl"))
        self.assertFalse(lb.wheel_ok("numpy-2.5.4-cp313-cp313t-manylinux_2_28_x86_64.whl"))
        self.assertFalse(lb.wheel_ok("numpy-2.5.4-cp310-cp310-manylinux_2_28_x86_64.whl"))

    def test_ffmpeg_major_and_packs(self):
        self.assertEqual(lb.ffmpeg_major("ffmpeg version 6.1.1-3ubuntu5 Copyright"), 6)
        self.assertEqual(lb.ffmpeg_major("ffmpeg version n7.1 Copyright"), 7)
        self.assertIsNone(lb.ffmpeg_major("ffmpeg version N-1234-gabc"))
        self.assertEqual(lb.resolve_packs("salamander,voice,salamander"), ["instruments-salamander", "voice"])
        with self.assertRaises(ValueError):
            lb.resolve_packs("nope")

    def test_pins_match_upstream_assets_shape(self):
        for name, spec in lb.PACKS.items():
            self.assertRegex(spec["sha256"], r"^[0-9a-f]{64}$", name)
            self.assertTrue(spec["prefix"].endswith("/"))
        self.assertRegex(lb.PIN_SHA, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
