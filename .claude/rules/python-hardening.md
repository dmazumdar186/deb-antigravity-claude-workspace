---
paths:
  - "**/*.py"
---

# Python-on-Windows Hardening (Always Active for .py edits)

These 5 rules apply to every Python script in this workspace. They are platform/cross-cutting hazards banked from prior incidents — not stylistic preferences.

## 1. Subprocess encoding

Every `subprocess.run/Popen(text=True)` or `capture_output=True` MUST include `encoding="utf-8", errors="replace"`. Windows cp1252 default crashes on bytes ≥ 0x80 (e.g. 0x9d). The `_readerthread` exception is hard to debug because it's swallowed by `subprocess`.

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

## Reference implementation

`C:\Users\deban\dev\anneal\src\anneal\` has hardened versions of all 5 patterns. Crib from there before writing new code.
