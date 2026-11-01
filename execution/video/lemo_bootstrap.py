"""
description: Reproducible, pinned bootstrap for the third-party lemo-opuscar film toolkit (clone at a pinned SHA, hashed venv, npm ci, sha256-checked model/sample packs, manifest). Never runs upstream setup.sh, never pulls.
inputs: CLI subcommand check | install | doctor | lock; --target DIR (default .tmp/lemo-opuscar), --cache DIR (or env LEMO_CACHE; default .tmp/lemo-cache), --packs LIST, --mirror URL (or env LEMO_ASSET_MIRROR), --python EXE, --dry-run, --full; lock: --from-venv DIR --out FILE
outputs: <target>/ (git clone at PIN_SHA), <target>/.venv, <target>/node_modules, extracted packs under <target>/core/, <cache>/packs/*.tar, <cache>/whisper/<model>@<rev>/, <target>/bootstrap_manifest.json, <target>/lemo.env; stdout report. Exit 0 ready, 1 a check failed, 2 a fetch/install step failed or usage error.

Directive: directives/video/lemo_opuscar.md

Security model (LEMO_TEARDOWN.md section 5, panel lens 10):
- The toolkit is untrusted third-party code. This script reads it; it never executes upstream
  scripts (setup.sh, tools/fetch.sh). The only programs it runs are git, python -m venv, pip
  (hash-locked, --no-deps, binary only), npm ci --ignore-scripts and curl.
- HEAD must equal PIN_SHA. A mismatch is refused, never "fixed" by fetching, pulling or resetting.
- Every fetched artefact is checked against a sha256 pinned in THIS file (not only the toolkit's
  own tools/assets.json, which lives in the same repo that auto-updates upstream). A mismatch
  fails closed: exit 2, nothing extracted, and no pull or upgrade is attempted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # stdlib-only fallback: the script must run in a bare cloud container
    load_dotenv = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

# ── Pins (change only deliberately, in a reviewed commit) ────────────────────

REPO_URL = "https://github.com/lemomo-ai/lemo-opuscar.git"
PIN_SHA = "bebbbe1aa92a3cb4bb6f83500e61b23a17d1aa00"  # 2026-11-01, audited in LEMO_TEARDOWN.md
RELEASE_BASE = "https://github.com/lemomo-ai/lemo-opuscar/releases/download/assets"
LOCK_PATH = ROOT / "execution" / "video" / "lemo_requirements.lock"
DEFAULT_TARGET = ROOT / ".tmp" / "lemo-opuscar"
DEFAULT_CACHE = ROOT / ".tmp" / "lemo-cache"
MANIFEST_NAME = "bootstrap_manifest.json"
ENV_NAME = "lemo.env"
STATE_DIR = ".lemo-bootstrap"
NPM_PINS = {"playwright-core": "1.63.0", "three": "0.170.0"}
SUPPORTED_PY = ((3, 11), (3, 13))  # kokoro-onnx needs < 3.14 (TECHNIQUE.md, requirements-voice.txt)
ESPEAK_LIMIT = 160  # core/tts/tts.py: espeak-ng data dir real path must be < 160 bytes

# Sparse checkout: what setup.sh skips (demos, gallery, big images) plus the nested CLAUDE.md,
# which is just "@AGENTS.md" and would auto-load into any Claude context that reads the tree.
SPARSE_PATTERNS = [
    "/*", "!/styles/*/demo/", "!/styleboard/", "!/docs/frames/", "!/docs/cover.jpg",
    "!/docs/opuscar98.jpg", "!/styles/*/poster.jpg", "!/CLAUDE.md",
]

# Release packs. tar sha256/size equal tools/assets.json at PIN_SHA. "files" / "tree_sha256" pin the
# extracted content; they were computed from the first build's fetch.sh-verified extraction
# (BUILD_LOG.md). None = not yet pinned beyond the tar hash.
PACKS: dict[str, dict] = {
    "voice": {
        "file": "voice.tar", "size": 353761280,
        "sha256": "6bc6536c9bc3283150a3bfd1859a9841c39ab4ee05e3df35933d9ab38ce327af",
        "prefix": "core/tts/",
        "files": {
            "core/tts/kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
            "core/tts/voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
        },
    },
    "hdri": {
        "file": "hdri.tar", "size": 12533760,
        "sha256": "3b1c41d5ef0b26f7dbdab4fff7bab4ed9a63daa701943375821229dd73029499",
        "prefix": "core/assets/polyhaven/", "tree": None, "tree_sha256": None,
    },
    "instruments-freepats": {
        "file": "instruments-freepats.tar", "size": 415959040,
        "sha256": "ae73707a7c88c8b985cedead751ff52ff8bfcaa3a48fa07ca6f45c0c6da00c83",
        "prefix": "core/audio/instruments/", "tree": "core/audio/instruments/freepats", "tree_sha256": None,
    },
    "instruments-karoryfer": {
        "file": "instruments-karoryfer.tar", "size": 77772800,
        "sha256": "b72822ac2f6569ed33b376448784d542bf039478fbf521db0c4bdc7ee766cac4",
        "prefix": "core/audio/instruments/", "tree": "core/audio/instruments/karoryfer", "tree_sha256": None,
    },
    "instruments-salamander": {
        "file": "instruments-salamander.tar", "size": 229150720,
        "sha256": "7c6a543de04daf6fdd7337ae08bf0484bec2a78b902ca80748bca927f42e189c",
        "prefix": "core/audio/instruments/", "tree": "core/audio/instruments/salamander",
        "tree_sha256": "4d18fed11341945e327b5929725e59535ec2e29cac528190aacdcf71c9d88b64",
    },
    "instruments-vcsl": {
        "file": "instruments-vcsl.tar", "size": 284682240,
        "sha256": "3ed8f753500e629485e323fc7f883b35aca6a77a1ab04522d1d47037d503f6e1",
        "prefix": "core/audio/instruments/", "tree": "core/audio/instruments/vcsl",
        "tree_sha256": "0a5fd0d16bd3c2034090cd254d426c205dfe08e1d5dd4679e73131f1d6ebb8c6",
    },
    "instruments-vsco2ce": {
        "file": "instruments-vsco2ce.tar", "size": 413911040,
        "sha256": "231297103cb4a3123707ddb7b284e5ea3aed0b8d77c0b891360b4d3efe8b586f",
        "prefix": "core/audio/instruments/", "tree": "core/audio/instruments/vsco2ce",
        "tree_sha256": "be072882a3e2efa32b58ea3fd648f03f52196a667375c56d28e51fa28d8c44f4",
    },
}

# Whisper models used by core/tts/asr_check.py, pinned by Hugging Face revision + per-file sha256
# (model.bin's sha256 equals its HF LFS oid). Point WHISPER_MODEL at the verified folder.
WHISPER: dict[str, dict] = {
    "whisper-small.en": {
        "repo": "Systran/faster-whisper-small.en",
        "revision": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
        "files": {
            "config.json": ("666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae", 2657),
            "model.bin": ("62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a", 483545366),
            "tokenizer.json": ("929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df", 2128466),
            "vocabulary.txt": ("ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf", 422309),
        },
    },
    "whisper-small": {  # multilingual (French narration checks)
        "repo": "Systran/faster-whisper-small",
        "revision": "536b0662742c02347bc0e980a01041f333bce120",
        "files": {
            "config.json": ("b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828", 2370),
            "model.bin": ("3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671", 483546902),
            "tokenizer.json": ("fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab", 2203239),
            "vocabulary.txt": ("34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913", 459861),
        },
    },
}

ALIASES = {lib: f"instruments-{lib}" for lib in ("freepats", "karoryfer", "salamander", "vcsl", "vsco2ce")}
DEFAULT_PACKS = ["voice", "instruments-salamander", "instruments-vcsl", "instruments-vsco2ce", "whisper-small.en"]

CHECKSUM_HELP = (
    "Do NOT git pull, re-clone, reset, or upgrade the toolkit or this pin to make the error go away: the pin is "
    "the contract. Either the source changed (upstream re-published the release tag, or the mirror is stale or "
    "tampered with) or the download is corrupt. Retry once later; if it still fails, report it to the operator "
    "with this message. Re-pinning is a reviewed code change to execution/video/lemo_bootstrap.py."
)


# ── Errors and reporting ─────────────────────────────────────────────────────

class CheckFailed(Exception):
    """A verification failed (exit 1)."""


class FetchFailed(Exception):
    """A fetch or install step failed (exit 2)."""


class ChecksumMismatch(FetchFailed):
    """A fetched or cached artefact did not match its pinned sha256 (exit 2, fail closed)."""


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, item: str, detail: str = "") -> None:
        self.rows.append((status, item, detail))
        print(f"  [{status:4}] {item}{(': ' + detail) if detail else ''}", flush=True)

    def ok(self, item: str, detail: str = "") -> None:
        self.add("OK", item, detail)

    def warn(self, item: str, detail: str = "") -> None:
        self.add("WARN", item, detail)

    def fail(self, item: str, detail: str = "") -> None:
        self.add("FAIL", item, detail)

    @property
    def failed(self) -> bool:
        return any(s == "FAIL" for s, _, _ in self.rows)


# ── Small helpers ────────────────────────────────────────────────────────────

def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, check: bool = True,
        timeout: int = 1800) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        raise FetchFailed(f"command failed ({r.returncode}): {' '.join(cmd)}\n{(r.stderr or r.stdout)[-1500:]}")
    return r


def git(target: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(target), *args], check=check, timeout=600)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(root: Path) -> tuple[str, int]:
    """sha256 over sorted 'relpath\\0sha256\\n' lines of every regular file under root (symlinks refused)."""
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise CheckFailed(f"symlink inside pack tree: {p}")
        if p.is_file():
            lines.append(f"{p.relative_to(root).as_posix()}\0{sha256_file(p)}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest(), len(lines)


def resolve_packs(spec: str) -> list[str]:
    if spec.strip() == "all":
        return [*PACKS, *WHISPER]
    out = []
    for raw in (s.strip() for s in spec.split(",") if s.strip()):
        name = ALIASES.get(raw, raw)
        if name not in PACKS and name not in WHISPER:
            raise ValueError(f"unknown pack '{raw}' (known: {', '.join([*PACKS, *ALIASES, *WHISPER])}, all)")
        if name not in out:
            out.append(name)
    return out


def python_version_of(exe: str) -> tuple[int, int, int] | None:
    try:
        r = run([exe, "-c", "import sys;print('.'.join(map(str,sys.version_info[:3])))"], check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", r.stdout.strip()) if r.returncode == 0 else None
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def py_supported(v: tuple[int, ...] | None) -> bool:
    return bool(v) and SUPPORTED_PY[0] <= tuple(v[:2]) <= SUPPORTED_PY[1]  # type: ignore[index]


def find_python(preferred: str | None = None) -> tuple[str, tuple[int, int, int]] | None:
    """The lock was generated on 3.13, so prefer it; 3.12 and 3.11 are accepted."""
    for c in ([preferred] if preferred else ["python3.13", "python3.12", "python3.11", "python3"]):
        exe = shutil.which(c) if c and not os.path.isabs(c) else c
        v = python_version_of(exe) if exe else None
        if exe and py_supported(v):
            return exe, v  # type: ignore[return-value]
    return None


def tool_version(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        r = run(cmd, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  (could not run {cmd[0]}: {exc})", file=sys.stderr)
        return None
    return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else None


def ffmpeg_major(line: str | None) -> int | None:
    m = re.search(r"ffmpeg version n?(\d+)\.", line or "")
    return int(m.group(1)) if m else None


def find_chromium() -> str | None:
    env = os.environ.get("PLAYWRIGHT_CHROME")
    if env and Path(env).is_file():
        return env
    roots = [Path("/opt/pw-browsers"), Path.home() / ".cache" / "ms-playwright"]
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        roots.insert(0, Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    pats = ["chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
            "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell.exe",
            "chromium-*/chrome-linux*/chrome"]
    for root in roots:
        for pat in pats:
            hits = sorted(root.glob(pat), reverse=True) if root.is_dir() else []
            if hits:
                return str(hits[0])
    return None


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_site_packages(venv: Path) -> Path | None:
    hits = sorted(venv.glob("lib/python3.*/site-packages")) or sorted(venv.glob("Lib/site-packages"))
    return hits[0] if hits else None


def venv_distributions(venv: Path) -> dict[str, str]:
    """Installed name→version read from dist-info metadata files only (nothing in the venv is executed)."""
    from importlib import metadata
    site = venv_site_packages(venv)
    if site is None:
        return {}
    out = {}
    for d in metadata.distributions(path=[str(site)]):
        name = d.metadata.get("Name")
        if name:
            out[canon(name)] = d.version
    return out


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(path: Path) -> dict[str, dict]:
    """name→{version, hashes[]} from a pip --require-hashes requirements file."""
    pins: dict[str, dict] = {}
    current = None
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    for line in text.splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line)
        if not m:
            continue
        current = canon(m.group(1))
        pins[current] = {"version": m.group(2), "hashes": re.findall(r"--hash=sha256:([0-9a-f]{64})", line)}
    return pins


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


# ── Pin / clone ──────────────────────────────────────────────────────────────

def head_sha(target: Path) -> str:
    r = git(target, "rev-parse", "HEAD", check=False)
    if r.returncode != 0:
        raise CheckFailed(f"{target} is not a git checkout: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def verify_pin(target: Path, pin: str = PIN_SHA) -> str:
    """Refuse unless HEAD == pin. Never fetches, pulls or resets to fix a mismatch."""
    sha = head_sha(target)
    if sha != pin:
        raise CheckFailed(
            f"toolkit HEAD is {sha}, pin is {pin}. Refusing to use it. Do not pull, fetch or reset this clone; "
            f"point --target at an empty folder to get a fresh clone at the pin, or change the pin in a reviewed commit.")
    return sha


def check_clone_hygiene(target: Path, rep: Report) -> None:
    managed = git(target, "config", "--get", "lemo.managed", check=False).stdout.strip()
    if managed == "true":
        rep.fail("lemo.managed", "set to true: upstream setup.sh would reset this clone to main. "
                 "Run: git -C <target> config --unset lemo.managed")
    else:
        rep.ok("lemo.managed", "unset (setup.sh would never auto-update)")
    url = git(target, "remote", "get-url", "origin", check=False).stdout.strip()
    if url.rstrip("/").removesuffix(".git") != REPO_URL.removesuffix(".git"):
        rep.warn("origin", f"{url or '(none)'} is not {REPO_URL}")
    else:
        rep.ok("origin", url)
    dirty = git(target, "status", "--porcelain", "--untracked-files=no", check=False).stdout.strip()
    if dirty:
        rep.fail("tracked files", "modified vs the pin:\n      " + "\n      ".join(dirty.splitlines()[:10]))
    else:
        rep.ok("tracked files", "unmodified vs the pin")
    if (target / "CLAUDE.md").exists() and is_relative_to(target, ROOT):
        rep.warn("nested CLAUDE.md", "present inside the workspace; it auto-loads @AGENTS.md into any context "
                 "that reads the tree (bootstrap clones exclude it)")


def clone_at_pin(target: Path, pin: str = PIN_SHA, url: str = REPO_URL, full: bool = False) -> None:
    """Fresh clone into an empty/missing folder, fetching exactly the pinned commit (never a branch)."""
    if target.exists() and any(target.iterdir()):
        raise CheckFailed(f"{target} exists and is not empty; refusing to clone into it")
    target.mkdir(parents=True, exist_ok=True)
    git(target, "init", "--quiet")
    git(target, "remote", "add", "origin", url)
    if not full:
        git(target, "config", "core.sparseCheckout", "true")
        git(target, "sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS)
    fetch_args = ["fetch", "--quiet", "--depth", "1"] + ([] if full else ["--filter=blob:none"]) + ["origin", pin]
    r = git(target, *fetch_args, check=False)
    if r.returncode != 0:
        raise FetchFailed(f"git fetch of pinned commit {pin} failed: {r.stderr.strip()[:500]}")
    git(target, "checkout", "--quiet", "--detach", pin)
    verify_pin(target, pin)


# ── Downloads ────────────────────────────────────────────────────────────────

def download(url: str, dest: Path, timeout: int = 1800) -> None:
    """Download url to dest (resuming a partial file). curl when present (proxy- and CA-aware), else urllib."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-L", "--fail", "-sS", "--retry", "3", "--retry-delay", "2",
                            "--connect-timeout", "20", "-C", "-", "-o", str(dest), url],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode != 0:
            raise FetchFailed(f"download failed (curl exit {r.returncode}) {url}: {r.stderr.strip()[:300]}")
        return
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as f:
                shutil.copyfileobj(resp, f, 1 << 20)
            return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise FetchFailed(f"download failed {url}: {last}")


def verify_artefact(path: Path, sha256: str, size: int | None, label: str) -> None:
    if size is not None and path.stat().st_size != size:
        raise ChecksumMismatch(f"{label}: size {path.stat().st_size} != pinned {size} ({path}).\n{CHECKSUM_HELP}")
    got = sha256_file(path)
    if got != sha256:
        raise ChecksumMismatch(f"{label}: sha256 {got} != pinned {sha256} ({path}).\n{CHECKSUM_HELP}")


def fetch_verified(name: str, sha256: str, size: int | None, dest: Path, urls: list[str]) -> str:
    """Make dest a verified copy. Order: existing cache file, then each url (mirror first). Returns the source.

    A checksum mismatch from any source fails closed: no fallthrough to another source, no pull, no upgrade.
    A cached file that mismatches is quarantined (renamed *.mismatch-<ts>) so it can be inspected.
    """
    if dest.exists():
        try:
            verify_artefact(dest, sha256, size, f"{name} (cache)")
            return f"cache:{dest}"
        except ChecksumMismatch:
            bad = dest.with_name(f"{dest.name}.mismatch-{int(time.time())}")
            dest.rename(bad)
            raise
    part = dest.with_name(dest.name + ".part")
    errors = []
    for url in urls:
        try:
            download(url, part)
        except FetchFailed as exc:
            errors.append(str(exc))
            print(f"  ! {exc} (trying next source)", file=sys.stderr)
            continue
        try:
            verify_artefact(part, sha256, size, f"{name} from {url}")
        except ChecksumMismatch:
            part.unlink(missing_ok=True)
            raise
        part.replace(dest)
        return url
    raise FetchFailed(f"{name}: every source failed:\n  " + "\n  ".join(errors))


def pack_urls(file: str, mirror: str | None) -> list[str]:
    urls = [f"{mirror.rstrip('/')}/{file}"] if mirror else []
    return urls + [f"{RELEASE_BASE}/{file}"]


def whisper_urls(spec: dict, file: str, mirror: str | None) -> list[str]:
    rel = f"{spec['repo']}/resolve/{spec['revision']}/{file}"
    urls = [f"{mirror.rstrip('/')}/whisper/{spec['repo'].split('/')[-1]}@{spec['revision']}/{file}"] if mirror else []
    return urls + [f"https://huggingface.co/{rel}"]


def safe_extract(tar_path: Path, target: Path, prefix: str) -> list[str]:
    """Extract a pack into target. Refuses (nothing extracted) any member outside `prefix`, any link, device,
    absolute path or traversal, and any member that would overwrite a git-tracked toolkit file."""
    tracked = set(git(target, "ls-files", check=False).stdout.splitlines())
    root = target.resolve()
    names = []
    with tarfile.open(tar_path) as t:
        members = t.getmembers()
        for m in members:
            n = m.name.removeprefix("./").rstrip("/")
            dest = (root / n).resolve()
            unsafe = (os.path.isabs(m.name) or ".." in Path(m.name).parts or not (m.isfile() or m.isdir())
                      or not is_relative_to(dest, root))
            # files must live under prefix; directories may also be the prefix's parents (core/, core/tts/)
            in_scope = (n + "/").startswith(prefix) or (m.isdir() and prefix.startswith(n + "/"))
            if unsafe or not in_scope:
                raise CheckFailed(f"{tar_path.name}: unsafe or out-of-scope entry '{m.name}'; nothing was extracted")
            if m.isfile() and n in tracked:
                raise CheckFailed(f"{tar_path.name}: entry '{n}' would overwrite a tracked toolkit file; refused")
            if m.isfile():
                names.append(n)
        if hasattr(tarfile, "data_filter"):
            t.extractall(str(root), members=members, filter="data")
        else:  # members were validated above (regular files and dirs only, inside prefix)
            t.extractall(str(root), members=members)
    return sorted(names)


# ── Pack verification (no network) ───────────────────────────────────────────

def verify_pack_installed(target: Path, name: str, rep: Report, cache: Path) -> dict:
    spec = PACKS[name]
    info: dict = {"name": name, "file": spec["file"], "sha256": spec["sha256"], "size": spec["size"]}
    cached = cache / "packs" / spec["file"]
    if cached.exists():
        try:
            verify_artefact(cached, spec["sha256"], spec["size"], f"{name} (cache)")
            rep.ok(f"cache {spec['file']}", "sha256 matches pin")
            info["cache"] = str(cached)
        except ChecksumMismatch as exc:
            rep.fail(f"cache {spec['file']}", str(exc).splitlines()[0])
    if spec.get("files"):
        bad = []
        for rel, sha in spec["files"].items():
            p = target / rel
            if not p.is_file():
                bad.append(f"{rel} missing")
            elif sha256_file(p) != sha:
                bad.append(f"{rel} sha256 differs from pin")
        if bad:
            rep.fail(f"pack {name}", "; ".join(bad))
        else:
            rep.ok(f"pack {name}", f"{len(spec['files'])} files match pinned sha256")
            info["files"] = dict(spec["files"])
        return info
    tree = target / spec["tree"] if spec.get("tree") else None
    if tree is None or not tree.is_dir():
        if tree is None and any((target / spec["prefix"]).glob("*.hdr")):
            rep.warn(f"pack {name}", "present; extracted content not pinned (only the tar sha256 is)")
        else:
            rep.fail(f"pack {name}", f"not installed ({spec.get('tree') or spec['prefix']})")
        return info
    digest, count = tree_digest(tree)
    info.update(tree_sha256=digest, tree_files=count)
    if spec.get("tree_sha256"):
        if digest == spec["tree_sha256"]:
            rep.ok(f"pack {name}", f"{count} files, tree sha256 matches pin")
        else:
            rep.fail(f"pack {name}", f"tree sha256 {digest[:12]}… != pin {spec['tree_sha256'][:12]}…")
    else:
        rep.warn(f"pack {name}", f"{count} files present; tree not pinned yet (digest {digest[:12]}…)")
    return info


def whisper_dirs(name: str, cache: Path) -> list[Path]:
    spec = WHISPER[name]
    model = spec["repo"].split("/")[-1]
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    hf = hf_home / "hub" / f"models--{spec['repo'].replace('/', '--')}" / "snapshots" / spec["revision"]
    return [cache / "whisper" / f"{model}@{spec['revision']}", hf]


def verify_whisper(name: str, cache: Path, rep: Report) -> dict:
    spec = WHISPER[name]
    for d in whisper_dirs(name, cache):
        if not d.is_dir():
            continue
        bad = [f for f, (sha, size) in spec["files"].items()
               if not (d / f).is_file() or (d / f).stat().st_size != size or sha256_file(d / f) != sha]
        if bad:
            rep.fail(f"model {name}", f"{d}: {', '.join(bad)} differ from pin")
            return {"name": name, "dir": str(d), "ok": False}
        rep.ok(f"model {name}", f"revision {spec['revision'][:12]} verified at {d}")
        return {"name": name, "repo": spec["repo"], "revision": spec["revision"], "dir": str(d),
                "files": {f: sha for f, (sha, _) in spec["files"].items()}, "ok": True}
    rep.fail(f"model {name}", "not found in the cache or the Hugging Face cache at the pinned revision")
    return {"name": name, "ok": False}


def verify_venv(venv: Path, lock: Path, rep: Report) -> dict:
    if not venv_python(venv).exists():
        rep.fail("venv", f"{venv} has no python")
        return {}
    pins = parse_lock(lock)
    have = venv_distributions(venv)
    wrong = [f"{n} {have.get(n, 'missing')} != {p['version']}" for n, p in pins.items() if have.get(n) != p["version"]]
    extra = sorted(set(have) - set(pins) - {"pip", "setuptools", "wheel"})
    if wrong:
        rep.fail("venv packages", "; ".join(wrong[:8]) + (" …" if len(wrong) > 8 else ""))
    else:
        rep.ok("venv packages", f"{len(pins)} match the lock")
    if extra:
        rep.warn("venv extras", ", ".join(extra[:10]))
    marker = venv / ".lemo-bootstrap-lock"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == sha256_file(lock):
        rep.ok("venv provenance", "installed by this bootstrap with --require-hashes")
    else:
        rep.warn("venv provenance", "not installed by this bootstrap; versions match but hashes were not enforced")
    site = venv_site_packages(venv)
    espeak = site / "espeakng_loader" / "espeak-ng-data" if site else None
    if espeak and espeak.exists():
        n = len(str(espeak.resolve()).encode("utf-8"))
        (rep.ok if n < ESPEAK_LIMIT else rep.fail)("espeak-ng path", f"{n} bytes (limit < {ESPEAK_LIMIT})")
    return {"path": str(venv), "packages": have}


def verify_node(target: Path, rep: Report) -> dict:
    out = {}
    for pkg, want in NPM_PINS.items():
        pj = target / "node_modules" / pkg / "package.json"
        got = json.loads(pj.read_text(encoding="utf-8")).get("version") if pj.exists() else None
        out[pkg] = got
        (rep.ok if got == want else rep.fail)(f"npm {pkg}", f"{got or 'missing'} (lock {want})")
    return out


# ── Manifest / env ───────────────────────────────────────────────────────────

def write_manifest(target: Path, data: dict) -> Path:
    """Atomically write <target>/bootstrap_manifest.json."""
    path = target / MANIFEST_NAME
    doc = {"schema": 1, "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "repo": REPO_URL, "pin_sha": PIN_SHA, **data}
    fd, tmp = tempfile.mkstemp(dir=str(target), prefix=".manifest.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return path


def write_env(target: Path, venv: Path, whisper_dir: str | None, chromium: str | None, cache: Path) -> Path:
    lines = ["# generated by execution/video/lemo_bootstrap.py; source before running toolkit tools",
             f"export LEMO_OPUSCAR_HOME={shlex.quote(str(target))}",
             f"export LEMO_PIN={PIN_SHA}",
             f"export LEMO_PYTHON={shlex.quote(str(venv_python(venv)))}",
             f"export LEMO_CACHE={shlex.quote(str(cache))}",
             "export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1",
             "export HF_HUB_OFFLINE=1"]
    if whisper_dir:
        lines.append(f"export WHISPER_MODEL={shlex.quote(whisper_dir)}")
    if chromium:
        lines.append(f"export PLAYWRIGHT_CHROME={shlex.quote(chromium)}")
    path = target / ENV_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── Subcommands ──────────────────────────────────────────────────────────────

def cmd_doctor(args) -> int:
    rep = Report()
    print("lemo_bootstrap doctor")
    ff = tool_version(["ffmpeg", "-version"])
    major = ffmpeg_major(ff)
    if ff is None:
        rep.fail("ffmpeg", "not found (7.x recommended)")
    elif major is None:
        rep.warn("ffmpeg", f"version not parsed: {ff}")
    elif major >= 7:
        rep.ok("ffmpeg", ff)
    elif major == 6:
        rep.warn("ffmpeg", f"{ff}: 7+ recommended (TECHNIQUE.md); 6.1 built the first film, but check the "
                 "final duration against the timeline")
    else:
        rep.fail("ffmpeg", f"{ff}: too old (need 6.1+, 7+ recommended)")
    nv = tool_version(["node", "--version"])
    m = re.match(r"v(\d+)", nv or "")
    (rep.ok if m and int(m.group(1)) >= 20 else rep.fail)("node", nv or "not found (need 20+)")
    npm = tool_version(["npm", "--version"])
    (rep.ok if npm else rep.fail)("npm", npm or "not found")
    gv = tool_version(["git", "--version"])
    (rep.ok if gv else rep.fail)("git", gv or "not found")
    py = find_python(args.python)
    if py:
        rep.ok("python", f"{py[0]} {'.'.join(map(str, py[1]))} (3.11–3.13 required for kokoro-onnx)")
    else:
        rep.fail("python", "no Python 3.11–3.13 found (kokoro-onnx does not support 3.14)")
    ch = find_chromium()
    (rep.ok if ch else rep.fail)("chromium", ch or "no headless Chromium found; set PLAYWRIGHT_CHROME")
    rep.ok("curl", shutil.which("curl")) if shutil.which("curl") else rep.warn("curl", "absent; urllib fallback")
    for var in ("LEMO_OPUSCAR_REPO",):
        if os.environ.get(var):
            rep.warn(var, "set; it can redirect upstream setup.sh to another repo. Unset it")
    cache = Path(args.cache)
    probe = cache if cache.exists() else next((p for p in cache.parents if p.exists()), Path("/"))
    free = shutil.disk_usage(probe).free / 1e9
    (rep.ok if free >= 4 else rep.warn)("disk", f"{free:.1f} GB free at {probe} (default packs need ~3.5 GB)")
    print("doctor:", "FAIL" if rep.failed else "OK")
    return 1 if rep.failed else 0


def cmd_check(args) -> int:
    rep = Report()
    target, cache = Path(args.target).resolve(), Path(args.cache).resolve()
    print(f"lemo_bootstrap check (no network): target={target}")
    if not (target / ".git").exists():
        rep.fail("clone", f"{target} is not a git checkout; run install")
        print("check: FAIL")
        return 1
    try:
        rep.ok("pin", verify_pin(target))
    except CheckFailed as exc:
        rep.fail("pin", str(exc))
        print("check: FAIL")
        return 1
    check_clone_hygiene(target, rep)
    lock = Path(args.lock)
    if not lock.exists():
        rep.fail("lock", f"{lock} missing")
    else:
        pins = parse_lock(lock)
        unhashed = [n for n, p in pins.items() if not p["hashes"]]
        (rep.warn if unhashed else rep.ok)("lock", f"{len(pins)} pins" + (f"; no hashes: {', '.join(unhashed)}"
                                                                         if unhashed else ", all hashed"))
        venv = Path(args.venv) if args.venv else target / ".venv"
        verify_venv(venv, lock, rep)
    verify_node(target, rep)
    for name in resolve_packs(args.packs):
        if name in PACKS:
            verify_pack_installed(target, name, rep, cache)
        else:
            verify_whisper(name, cache, rep)
    mf = target / MANIFEST_NAME
    if mf.exists():
        doc = json.loads(mf.read_text(encoding="utf-8"))
        (rep.ok if doc.get("pin_sha") == PIN_SHA else rep.fail)("manifest", f"{mf.name} pin {doc.get('pin_sha')}")
    else:
        rep.warn("manifest", f"no {MANIFEST_NAME} (this tree was not built by the bootstrap)")
    print("check:", "FAIL" if rep.failed else "OK")
    return 1 if rep.failed else 0


def cmd_install(args) -> int:
    target, cache = Path(args.target).resolve(), Path(args.cache).resolve()
    lock = Path(args.lock).resolve()
    venv = Path(args.venv).resolve() if args.venv else target / ".venv"
    packs = resolve_packs(args.packs)
    mirror = args.mirror
    dry = args.dry_run
    tag = "[dry-run] " if dry else ""
    print(f"lemo_bootstrap install {'(dry run: no network, no writes)' if dry else ''}")
    print(f"  target={target}\n  cache={cache}\n  venv={venv}\n  packs={','.join(packs)}\n  mirror={mirror or '(none)'}")

    if not lock.exists():
        raise CheckFailed(f"lock file {lock} missing")
    if is_relative_to(target, ROOT) and not is_relative_to(target, ROOT / ".tmp"):
        raise CheckFailed(f"target {target} is inside the workspace but outside .tmp/ (it would be committed)")

    # 1. clone or verify
    if (target / ".git").exists():
        print(f"  {tag}verify existing clone HEAD == {PIN_SHA[:12]} (never fetched or reset)")
        verify_pin(target)
    else:
        print(f"  {tag}git clone (sparse{'' if not args.full else ' off'}) {REPO_URL} at {PIN_SHA} → {target}")
        if not dry:
            clone_at_pin(target, full=args.full)

    # 2. venv from the hashed lock
    pins = parse_lock(lock)
    unhashed = [n for n, p in pins.items() if not p["hashes"]]
    if unhashed:
        raise CheckFailed(f"lock has unhashed pins ({', '.join(unhashed)}); refusing an unverified install")
    marker = venv / ".lemo-bootstrap-lock"
    lock_sha = sha256_file(lock)
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == lock_sha:
        print("  venv: already installed from this lock (skip)")
    elif venv.exists() or venv.is_symlink():
        raise CheckFailed(f"{venv} exists but was not created by this bootstrap; refusing to modify it "
                          "(pass --venv to a new path, or delete it yourself)")
    else:
        py = find_python(args.python)
        if not py:
            raise CheckFailed("no Python 3.11–3.13 interpreter found (see doctor)")
        pip_cmd = [str(venv_python(venv)), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                   "--require-hashes", "--no-deps", "--only-binary", ":all:", "-r", str(lock)]
        print(f"  {tag}{py[0]} -m venv {venv}")
        print(f"  {tag}{' '.join(pip_cmd)}")
        if not dry:
            run([py[0], "-m", "venv", str(venv)], timeout=600)
            run(pip_cmd, timeout=3600)
            r = run([str(venv_python(venv)), "-m", "pip", "check"], check=False, timeout=300)
            if r.returncode != 0:
                raise FetchFailed(f"pip check failed after hashed install:\n{r.stdout[-1500:]}")
            marker.write_text(lock_sha + "\n", encoding="utf-8")

    # 3. npm ci from the toolkit's committed lockfile, no install scripts, no browser download
    npm_env = {**dict(os.environ), "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"}
    nm_marker = target / "node_modules" / ".lemo-bootstrap"
    pl = target / "package-lock.json"
    pl_sha = sha256_file(pl) if pl.exists() else None
    if pl_sha and nm_marker.exists() and nm_marker.read_text(encoding="utf-8").strip() == pl_sha:
        print("  npm: already installed from this package-lock (skip)")
    else:
        print(f"  {tag}npm ci --ignore-scripts --no-audit --no-fund (cwd {target})")
        if not dry:
            run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error"],
                cwd=target, env=npm_env, timeout=1800)
            nm_marker.write_text(f"{pl_sha}\n", encoding="utf-8")

    # 4. packs (cache → extract) and whisper models
    artefacts, whisper_info = [], []
    state = target / STATE_DIR
    for name in packs:
        if name in PACKS:
            spec = PACKS[name]
            dest = cache / "packs" / spec["file"]
            done = state / f"{name}.json"
            if done.exists() and json.loads(done.read_text(encoding="utf-8")).get("sha256") == spec["sha256"]:
                print(f"  pack {name}: already extracted from the pinned tar (skip)")
                artefacts.append(json.loads(done.read_text(encoding="utf-8")))
                continue
            print(f"  {tag}fetch {spec['file']} ({spec['size'] / 1e6:.0f} MB, sha256 {spec['sha256'][:12]}…) "
                  f"from {'cache, ' if dest.exists() else ''}{', '.join(pack_urls(spec['file'], mirror))}")
            print(f"  {tag}extract into {target / spec['prefix']} (scope- and tracked-file-checked)")
            if dry:
                continue
            source = fetch_verified(name, spec["sha256"], spec["size"], dest, pack_urls(spec["file"], mirror))
            files = safe_extract(dest, target, spec["prefix"])
            rec = {"name": name, "file": spec["file"], "sha256": spec["sha256"], "size": spec["size"],
                   "source": source, "cache": str(dest), "extracted_files": len(files)}
            if spec.get("tree") and (target / spec["tree"]).is_dir():
                rec["tree_sha256"], rec["tree_files"] = tree_digest(target / spec["tree"])
                if spec.get("tree_sha256") and rec["tree_sha256"] != spec["tree_sha256"]:
                    raise ChecksumMismatch(f"{name}: extracted tree differs from pin.\n{CHECKSUM_HELP}")
            for rel, sha in (spec.get("files") or {}).items():
                verify_artefact(target / rel, sha, None, f"{name}:{rel}")
            state.mkdir(exist_ok=True)
            done.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            artefacts.append(rec)
        else:
            spec = WHISPER[name]
            mdir = whisper_dirs(name, cache)[0]
            print(f"  {tag}fetch {spec['repo']}@{spec['revision'][:12]} ({len(spec['files'])} files, sha256-pinned) "
                  f"→ {mdir}")
            if dry:
                continue
            files = {}
            for f, (sha, size) in spec["files"].items():
                src = fetch_verified(f"{name}/{f}", sha, size, mdir / f, whisper_urls(spec, f, mirror))
                files[f] = {"sha256": sha, "size": size, "source": src}
            whisper_info.append({"name": name, "repo": spec["repo"], "revision": spec["revision"],
                                 "dir": str(mdir), "files": files})

    if dry:
        print(f"  {tag}write {target / MANIFEST_NAME} and {target / ENV_NAME}, then run check")
        print("install: dry run complete (nothing fetched or written)")
        return 0

    # 5. manifest + env, then a full offline check
    chromium = find_chromium()
    versions = {
        "python": ".".join(map(str, python_version_of(str(venv_python(venv))) or ())),
        "node": tool_version(["node", "--version"]), "npm": tool_version(["npm", "--version"]),
        "ffmpeg": tool_version(["ffmpeg", "-version"]), "git": tool_version(["git", "--version"]),
        "npm_packages": verify_node(target, Report()),
    }
    wdir = next((w["dir"] for w in whisper_info if w["name"] == "whisper-small.en"),
                whisper_info[0]["dir"] if whisper_info else None)
    write_manifest(target, {
        "head_sha": head_sha(target), "target": str(target), "cache": str(cache),
        "lock": {"path": str(lock), "sha256": lock_sha}, "python_packages": venv_distributions(venv),
        "versions": versions, "chromium": chromium, "artefacts": artefacts, "whisper": whisper_info,
    })
    write_env(target, venv, wdir, chromium, cache)
    print(f"  wrote {target / MANIFEST_NAME} and {target / ENV_NAME}")
    args.venv = str(venv)
    return cmd_check(args)


def wheel_ok(filename: str) -> bool:
    """Keep sdists and wheels usable on CPython 3.11–3.13 (Linux, macOS, any); drop Windows and free-threaded."""
    if not filename.endswith(".whl"):
        return True
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return False
    py, abi, plat = parts[-3], parts[-2], parts[-1]
    if any(p.startswith("win") for p in plat.split(".")) or abi.endswith("t"):
        return False
    pys = py.split(".")
    return "py3" in pys or abi == "abi3" or any(p in ("cp311", "cp312", "cp313") for p in pys)


def pypi_hashes(name: str, version: str) -> list[str]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise FetchFailed(f"PyPI lookup failed for {name}=={version}: {exc}") from exc
    return sorted({u["digests"]["sha256"] for u in data.get("urls", []) if wheel_ok(u["filename"])})


def cmd_lock(args) -> int:
    venv = Path(args.from_venv)
    dists = venv_distributions(venv)
    dists = {n: v for n, v in sorted(dists.items()) if n not in ("pip", "setuptools", "wheel")}
    if not dists:
        raise CheckFailed(f"no distributions found in {venv}")
    pyv = next(iter(sorted(venv.glob("lib/python3.*"))), None)
    print(f"lock: {len(dists)} packages from {venv} ({pyv.name if pyv else '?'})")
    if args.dry_run:
        for n, v in dists.items():
            print(f"  [dry-run] {n}=={v}: query https://pypi.org/pypi/{n}/{v}/json")
        return 0
    lines = ["# lemo-opuscar Python environment, hash-locked. Generated by:",
             f"#   python3 execution/video/lemo_bootstrap.py lock --from-venv {venv} --out <this file>",
             f"# Source: the venv that built the first film ({pyv.name if pyv else '?'}, linux x86_64), dist-info read",
             "# without executing it; sha256 digests from PyPI's JSON API for exactly these versions (CPython",
             "# 3.11-3.13 wheels for Linux/macOS, plus sdists). Install only with:",
             "#   pip install --require-hashes --no-deps --only-binary :all: -r lemo_requirements.lock",
             f"# Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. Toolkit pin {PIN_SHA[:12]}. Do not hand-edit.",
             ""]
    missing = []
    for n, v in dists.items():
        hashes = pypi_hashes(n, v)
        if not hashes:
            missing.append(n)
            lines.append(f"{n}=={v}  # NO HASH: no matching file on PyPI")
            continue
        lines.append(f"{n}=={v} \\")
        lines.extend(f"    --hash=sha256:{h}" + (" \\" if i < len(hashes) - 1 else "") for i, h in enumerate(hashes))
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}" + (f"; NO HASH for: {', '.join(missing)}" if missing else "; every pin hashed"))
    return 1 if missing else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pinned, offline-verifiable bootstrap for the lemo-opuscar toolkit.")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--target", default=str(DEFAULT_TARGET), help="toolkit clone (default .tmp/lemo-opuscar)")
    common.add_argument("--cache", default=os.environ.get("LEMO_CACHE", str(DEFAULT_CACHE)),
                        help="download cache; point at durable storage (env LEMO_CACHE)")
    common.add_argument("--lock", default=str(LOCK_PATH))
    common.add_argument("--venv", default=None, help="venv path (default <target>/.venv)")
    common.add_argument("--packs", default=",".join(DEFAULT_PACKS),
                        help="comma list (voice, hdri, salamander, vcsl, vsco2ce, freepats, karoryfer, "
                             "whisper-small.en, whisper-small) or 'all'")
    common.add_argument("--python", default=None, help="interpreter for the venv (3.11–3.13)")
    common.add_argument("--dry-run", action="store_true", help="print the plan; no network, no writes")
    sub.add_parser("check", parents=[common], help="verify only, no network")
    ins = sub.add_parser("install", parents=[common], help="clone/verify, venv, npm ci, packs, manifest")
    ins.add_argument("--mirror", default=os.environ.get("LEMO_ASSET_MIRROR"),
                     help="base URL tried before upstream (env LEMO_ASSET_MIRROR)")
    ins.add_argument("--full", action="store_true", help="full checkout (demos too) instead of sparse")
    sub.add_parser("doctor", parents=[common], help="toolchain prerequisites")
    lk = sub.add_parser("lock", parents=[common], help="regenerate the hashed lock from a venv (needs PyPI)")
    lk.add_argument("--from-venv", required=True)
    lk.add_argument("--out", default=str(LOCK_PATH))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return {"check": cmd_check, "install": cmd_install, "doctor": cmd_doctor, "lock": cmd_lock}[args.cmd](args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except CheckFailed as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except FetchFailed as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
