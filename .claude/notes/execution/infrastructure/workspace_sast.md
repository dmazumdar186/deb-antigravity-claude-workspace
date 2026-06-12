# workspace_sast.py Notes

Captured from .claude/upgrades/other_categories.md on 2026-06-12.

- [technical] HOME/USERPROFILE workaround: semgrep on Windows requires a valid `HOME` or `USERPROFILE` environment variable to locate its rule cache. When run in hook context (e.g. from `.claude/hooks/`), these vars may not be set. The workaround is already in the script header — sets `os.environ.setdefault("HOME", str(Path.home()))` before invoking semgrep. This is WHY the workaround exists: semgrep raises `RuntimeError: Could not determine home directory` without it.
- [technical] semgrep Windows/Python 3.14 incompatibility: semgrep may not be installable on Python 3.14 due to native extension ABI requirements. If `pip install semgrep` fails, the script falls back to ruff-only mode (exit 2 = no tools installed). Do not block the hook on semgrep availability.
- [technical] Exit code semantics: Exit 0 = no critical/high findings. Exit 1 = critical/high findings found. Exit 2 = no SAST tools installed (ruff and semgrep both absent). Exit 2 is a soft failure — the workspace still works, but SAST coverage is reduced.
- [pattern] Subprocess encoding satisfied: All `subprocess.run` calls use `encoding="utf-8", errors="replace"` (verified at lines 104, 148, 187 per audit). No threading used.
- [constraint] No /api/health equivalent: The script has no self-check endpoint exposing whether ruff/semgrep are installed. Runs as a hook — if neither tool is present, exit 2 fires silently with no operator dashboard signal.

## See also

- .claude/upgrades/other_categories.md
- directives/infrastructure/workspace_sast.md
