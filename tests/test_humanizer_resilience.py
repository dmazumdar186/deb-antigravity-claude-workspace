from __future__ import annotations
import subprocess, sys, json, os
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
PY = sys.executable

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

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

def skip(name, reason):
    global SKIP_COUNT
    print("SKIP  " + name + " -- " + reason)
    SKIP_COUNT += 1

def _cli(*args, stdin_text=None, env_override=None):
    env = None
    if env_override:
        import os as _os
        env = _os.environ.copy()
        env.update(env_override)
    return subprocess.run([PY, SCRIPT, *args], input=stdin_text, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", cwd=str(WORKSPACE), env=env)

def r1():
    voice_path = WORKSPACE/"execution"/"content"/"voices"/"debanjan.json"
    bak = WORKSPACE/"execution"/"content"/"voices"/"debanjan.json.bak"
    voice_path.rename(bak)
    try:
        r = _cli("--text", "test", "--voice", "debanjan", "--dry-run")
        assert r.returncode != 0
        combined = r.stdout + r.stderr
        assert any(k in combined.lower() for k in ["not found","available","missing"])
        assert "Traceback" not in combined, "Traceback leaked"
    finally:
        bak.rename(voice_path)

def r2():
    voice_path = WORKSPACE/"execution"/"content"/"voices"/"debanjan.json"
    backup = voice_path.read_text(encoding="utf-8")
    voice_path.write_text(json.dumps({"name":"debanjan"}), encoding="utf-8")
    try:
        r = _cli("--text", "test text here", "--voice", "debanjan", "--dry-run")
        assert "Traceback" not in r.stdout + r.stderr
    finally:
        voice_path.write_text(backup, encoding="utf-8")

def r3():
    cache_path = WORKSPACE/".tmp"/"model_registry.json"
    backup = cache_path.read_text(encoding="utf-8") if cache_path.exists() else None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{corrupt}", encoding="utf-8")
    try:
        r = _cli("--text", "Test text.", "--dry-run")
        assert r.returncode == 0, "Corrupt cache crashed: " + r.stderr[-200:]
        assert "Traceback" not in r.stdout + r.stderr
    finally:
        if backup: cache_path.write_text(backup, encoding="utf-8")
        elif cache_path.exists(): cache_path.unlink()

def r4():
    r = _cli("--text", "Test text.", "--dry-run")
    assert r.returncode == 0, "dry-run failed (should work offline): " + r.stderr
    assert "Traceback" not in r.stdout + r.stderr

def r6():
    """Invalid API key should produce clean error, no traceback, no key leak."""
    r = _cli("--text", "x", "--tier", "default", env_override={"OPENROUTER_API_KEY":"bad-key-xxx", "ANTHROPIC_API_KEY":"", "GEMINI_API_KEY":""})
    combined = r.stdout + r.stderr
    # Should exit non-zero
    assert r.returncode != 0, f"Expected non-zero exit, got {r.returncode}"
    # Should NOT include a traceback
    assert "Traceback" not in combined, f"Traceback leaked: {combined[:500]}"
    # Should NOT leak the key value
    assert "bad-key-xxx" not in combined, "API key value leaked in output"
    # Should have a clean error message
    assert "OpenRouter" in combined or "API" in combined or "401" in combined, \
        f"No clean error message: {combined[:500]}"

if __name__ == "__main__":
    run("resilience 1: voice file missing -- clear error, restore", r1)
    run("resilience 2: voice file missing required keys -- no traceback", r2)
    run("resilience 3: model registry cache corrupted -- fallback", r3)
    run("resilience 4: dry-run works offline (no network needed)", r4)
    skip("resilience 5: LLM returns malformed JSON", "requires mocking internal _call_llm_humanize")
    run("resilience 6: invalid API key -- error surfaced, key not leaked", r6)
    skip("resilience 7: API rate-limited 429", "hard to trigger deterministically")
    print("")
    print("Results: "+str(PASS_COUNT)+" passed, "+str(FAIL_COUNT)+" failed, "+str(SKIP_COUNT)+" skipped")
    if FAILURES:
        print("Failed tests:")
        for nm,er in FAILURES: print("  FAIL  "+nm); print("        "+er)
    sys.exit(0 if FAIL_COUNT == 0 else 1)
