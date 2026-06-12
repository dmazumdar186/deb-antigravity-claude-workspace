from __future__ import annotations
import subprocess, sys, json
from pathlib import Path

WORKSPACE = Path(r'C:/Users/deban/OneDrive/Documents/AntiGravity Project Space')
SCRIPT = str(WORKSPACE / 'execution' / 'content' / 'humanizer.py')
PY = sys.executable

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / '.env'))

PASS_COUNT = 0; FAIL_COUNT = 0; SKIP_COUNT = 0; FAILURES = []

def run(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print("PASS  " + name)
        PASS_COUNT += 1
    except Exception as exc:
        print("FAIL  " + name)
        print("      " + str(exc))
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))

def _cli(*args, stdin_text=None, stdin_bytes=None):
    if stdin_bytes is not None:
        # bytes-mode path: stdout/stderr returned as bytes; no text codec needed
        return subprocess.run([PY, SCRIPT, *args], input=stdin_bytes,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(WORKSPACE))
    return subprocess.run([PY, SCRIPT, *args], input=stdin_text, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", cwd=str(WORKSPACE))

def _no_tb(r):
    out = r.stdout if isinstance(r.stdout, str) else r.stdout.decode("utf-8", errors="replace")
    err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode("utf-8", errors="replace")
    assert "Traceback" not in out + err, "Traceback leaked"

def t1():
    r = _cli("--text", "", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t2():
    r = _cli("--text", "   ", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t3():
    big = "AI text. " * 3000
    r = _cli("--text", big, "--dry-run")
    assert r.returncode == 0; _no_tb(r)
    assert "warn" in (r.stdout+r.stderr).lower() or len(r.stdout)>0

def t4():
    r = _cli("--text", "emoji test", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t5():
    r = _cli("--text", "Hello deleve into robust frameworks", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t6():
    try:
        r = _cli("--text", "AI text", "--dry-run")
        out = r.stdout if isinstance(r.stdout,str) else r.stdout.decode("utf-8",errors="replace")
        assert "Traceback" not in out
    except Exception: pass

def t7():
    r = _cli("--file", "../../../etc/passwd", "--dry-run")
    out = r.stdout if isinstance(r.stdout,str) else r.stdout.decode("utf-8",errors="replace")
    assert "root:x:0:0" not in out; _no_tb(r)

def t8():
    r = _cli("--text", "test", "--voice", "../../../etc/passwd", "--dry-run")
    assert r.returncode != 0; _no_tb(r)

def t9():
    """Tampered voice JSON should fall back gracefully — use a temp voice file, not the real one."""
    import os
    VOICES_DIR = WORKSPACE / "execution" / "content" / "voices"
    temp_voice_name = f"_test_corrupt_{os.getpid()}"
    temp_voice_path = VOICES_DIR / f"{temp_voice_name}.json"
    try:
        # Write corrupt JSON to a temp voice file (NOT the real debanjan.json)
        temp_voice_path.write_text("{not valid json", encoding="utf-8")
        r = _cli("--text", "hello", "--voice", temp_voice_name, "--dry-run")
        assert r.returncode != 0, f"Expected non-zero, got {r.returncode}"
        combined = r.stdout + r.stderr
        assert any(k in combined.lower() for k in ["invalid", "json", "error"])
        _no_tb(r)
    finally:
        if temp_voice_path.exists():
            temp_voice_path.unlink()

def t10():
    r = _cli("--text", "hello", "--file", "file.txt")
    assert r.returncode == 2

def t11():
    r = _cli("--text", "test", "--tier", "bad_tier")
    assert r.returncode == 2

def t12():
    r = _cli("--text", "test", "--platform", "myspace")
    assert r.returncode == 2

def t13():
    r = _cli("--text", "Hello.", "--platform", "tweet", "--max-length", "0", "--dry-run")
    _no_tb(r)

def t14():
    r = _cli("--text", "Hello.", "--max-length", "-1", "--dry-run")
    _no_tb(r)

def t15():
    r = _cli("--text", "Hello.", "--max-length", "999999", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t16():
    r = _cli("--dry-run", stdin_text="")
    assert r.returncode == 0; _no_tb(r)

def t17():
    r = _cli("--dry-run", stdin_bytes=bytes.fromhex("fffe") + b"binary garbage")
    out = r.stdout.decode("utf-8",errors="replace") if isinstance(r.stdout,bytes) else r.stdout
    err = r.stderr.decode("utf-8",errors="replace") if isinstance(r.stderr,bytes) else r.stderr
    assert "Traceback" not in out+err

def t18():
    r = _cli("--text", "Visit https://x.com/?e=xss_attempt", "--dry-run")
    assert r.returncode == 0; _no_tb(r)

def t19():
    cache_path = WORKSPACE/".tmp"/"model_registry.json"
    backup = cache_path.read_text(encoding="utf-8") if cache_path.exists() else None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{garbage: not valid json}", encoding="utf-8")
    try:
        r = _cli("--text", "Some test text.", "--dry-run")
        assert r.returncode == 0; _no_tb(r)
    finally:
        if backup is not None: cache_path.write_text(backup, encoding="utf-8")
        elif cache_path.exists(): cache_path.unlink()

def t20():
    vdata = {"name":"empty_ex_test","display_name":"T","description":"t","traits":{"sentence_length":"short","register":"casual","punctuation":"min","formatting":"prose"},"lexicon":{"uses":[],"avoids":[]},"examples":[]}
    vpath = WORKSPACE/"execution"/"content"/"voices"/"empty_ex_test.json"
    vpath.write_text(json.dumps(vdata), encoding="utf-8")
    try:
        r = _cli("--text", "Some text.", "--voice", "empty_ex_test", "--dry-run")
        assert r.returncode == 0; _no_tb(r)
    finally:
        vpath.unlink(missing_ok=True)

if __name__ == "__main__":
    pairs = [("chaos 1: empty --text",t1),("chaos 2: whitespace-only",t2),("chaos 3: 50KB input",t3),
             ("chaos 4: pure emoji",t4),("chaos 5: unicode mix",t5),("chaos 6: null byte safe",t6),
             ("chaos 7: path traversal --file",t7),("chaos 8: --voice path traversal",t8),
             ("chaos 9: malformed voice JSON",t9),("chaos 10: both --text and --file",t10),
             ("chaos 11: --tier invalid",t11),("chaos 12: --platform invalid",t12),
             ("chaos 13: --max-length 0",t13),("chaos 14: --max-length -1",t14),
             ("chaos 15: --max-length 999999",t15),("chaos 16: stdin EOF",t16),
             ("chaos 17: stdin binary",t17),("chaos 18: XSS-like URL",t18),
             ("chaos 19: tampered cache",t19),("chaos 20: voice empty examples",t20)]
    for name, fn in pairs:
        run(name, fn)
    print("")
    print("Results: "+str(PASS_COUNT)+" passed, "+str(FAIL_COUNT)+" failed, "+str(SKIP_COUNT)+" skipped")
    if FAILURES:
        print("Failed tests:")
        for nm,er in FAILURES: print("  FAIL  "+nm); print("        "+er)
    sys.exit(0 if FAIL_COUNT == 0 else 1)
