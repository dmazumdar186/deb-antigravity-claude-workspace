---
paths:
  - "**/*.py"
---

# Python-on-Windows Hardening (Always Active for .py edits)

These 5 rules apply to every Python script in this workspace. They are platform/cross-cutting hazards banked from prior incidents — not stylistic preferences.

## 1. Subprocess encoding

Every `subprocess.run/Popen(text=True)` or `capture_output=True` MUST include `encoding="utf-8", errors="replace"`. Windows cp1252 default crashes on bytes ≥ 0x80 (e.g. 0x9d). The `_readerthread` exception is hard to debug because it's swallowed by `subprocess`.

Scope note: `.anneal/` subdirectories are throwaway audit worktrees (snapshots of other repos created by the anneal tool) and are excluded from this rule. The workspace SAST scanner skips `.anneal/` paths — do not patch files there.

## 2. Threading locks

Any shared mutable state inside `ThreadPoolExecutor` / `threading.Thread` MUST be guarded by `threading.Lock`. GIL protects single reference reads/writes but NOT `+=` (read-modify-write) nor concurrent filesystem writes to the same directory (e.g. `mkdir(exist_ok=True)` is racy across threads writing to a shared output dir).

## 3. LLM-supplied path validation

Any filename derived from LLM output or external API MUST be `.resolve()`ed and checked `resolved.is_relative_to(boundary)` before being passed to filesystem ops or subprocesses.

```python
if not (worktree / user_path).resolve().is_relative_to(worktree.resolve()):
    raise ValueError("path traversal")
```

## 4. Cache-aware Claude pricing

Pricing tables MUST include 4 entries per Claude model: `input`, `cache_read` (0.1× input), `cache_write` (1.25× input), `output`. Flat-rate over-estimates 5–10× under prompt caching. Cost-calc must accept all 4 token counts from `response.usage.cache_read_input_tokens` / `cache_creation_input_tokens` / `input_tokens` / `output_tokens`.

## 5. Never `except Exception: pass`

Without a log line AND a comment explaining why it's safe. Bare swallows mask the bugs you most need to see (e.g. an OAuth token refresh failing silently → 24h of broken cron).

## 6. Never `copy.copy(os.environ)` — use `dict(os.environ)`

`os.environ` is an `_Environ` proxy, not a dict. `copy.copy(os.environ)` returns another `_Environ` that **shares state with the live process environment** — mutations on the "copy" leak into `os.environ`. Use `dict(os.environ)` for a real independent snapshot.

Bug class: subprocess-spawning tests that blank API keys on a "copy" silently pollute the parent process env, making every subsequent test inherit empty keys. Looks like flaky cumulative failure. (Exhibit: 2026-06-15, 13 test failures → 0 after a 1-character-class fix.)

Full rule and minimal repro: `~/.claude/rules/environ-not-copy-copy.md`.

## 7. No bare `#!/usr/bin/env python` shebang — it selects a different interpreter

The Windows `py` launcher **reads the shebang line and dispatches on it**. So on this machine:

| Invocation | Interpreter |
|---|---|
| `py -c "..."` | `C:\Users\deban\AppData\Local\Python\pythoncore-3.14-64\python.exe` |
| `py script.py` (with `#!/usr/bin/env python`) | `C:\Python314\python.exe` |

Two different Python 3.14 installs with **different site-packages**. `py -m pip install X` lands in the first; `py script.py` runs under the second and raises `ImportError` for `X`. The symptom reads as "pip lied" or "the package didn't install" and sends you re-installing a package that is already present.

Rules:
- Do not put a bare `#!/usr/bin/env python` shebang on workspace scripts. Without a shebang, `py script.py` uses the default interpreter — the same one `py -m pip` targets.
- When a script must be invoked with a specific interpreter, pin it at the call site: `py -3.14 execution/{category}/{script}.py`.
- Prefer a stdlib fallback over a hard third-party dependency in any script that might be launched more than one way. (Exhibit: `instantly_guard.py` hard-depended on `dnspython`, died on `--help`, and the real fix was making the dependency optional with a DNS-over-HTTPS fallback.)

Guarded by the workspace SAST rule `py-launcher-shebang`.

## 8. Env-stripped subprocesses on Windows must forward `APPDATA`

A sandboxed child that receives only `SYSTEMROOT` + `PATH` cannot compute its user
site-packages directory (`%APPDATA%\Python\PythonXY\site-packages`), so anything
installed with `pip install --user` is invisible to it. The symptom is
`No module named X` from an interpreter that imports X fine at the prompt.

Exhibit 2026-08-27: `anneal/runner/python_test_runner.py` forwarded
`SYSTEMROOT/PATH/PYTHONPATH` only. Four of anneal's own unit tests had been failing
on this machine, and in production every Red attack would have been scored as
"landed" because `pytest` itself could not import. Adding `APPDATA` to the
passthrough list fixed all four.

Forward `APPDATA` (Python), and for Node/Go children the equivalents they need
(`USERPROFILE`, `HOME`, `LOCALAPPDATA` for npm/go caches). Path variables carry no
secrets; the strip exists to keep API keys out, not directories.

## Reference implementation

`C:\Users\deban\dev\anneal\src\anneal\` has hardened versions of all 5 patterns. Crib from there before writing new code.
