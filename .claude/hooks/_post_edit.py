"""Shared body of the PostToolUse(Edit|Write) helper hooks: format | note | documenter.

Claude Code passes hook input as JSON on stdin (tool_input.file_path, tool_input.new_string,
session_id). The old shell hooks read $CLAUDE_TOOL_INPUT_FILE_PATH, which Claude Code never sets,
so they never fired (probe 2026-11-12). A path given as argv[2] still wins, for manual runs.

  format      black (else ruff) on .py files. Edit: only the edited lines (--line-ranges), so a
              one-line change in one of the 488 non-black files doesn't reformat the whole file.
              Write: the whole file. Silent.
  note        once per file per session: reminder to capture learnings (directives/ or execution/).
  documenter  once per file per session: reminder to sync the directive (execution/**/*.py).
Reminders go out as PostToolUse additionalContext JSON (plain stdout is discarded).
Every mode fails open: any error -> stderr line, exit 0.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

AM_LOCKED = ("accessory", "hedgestone", "elite-broker", "elitebrokergroup")


def read_payload() -> dict:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def emit(msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


def project_root(payload: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()


def rel_posix(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        # e.g. a Git Bash root like /c/Users/... vs C:\Users\...: fall back to the workspace segment
        p = Path(path).as_posix().replace("\\", "/")
        for seg in ("/directives/", "/execution/"):
            if (i := p.find(seg)) != -1:
                return p[i + 1:]
        return p


def first_time(kind: str, payload: dict, key: str, root: Path) -> bool:
    """Per-session dedupe; one ledger per kind so concurrent async hooks never share a file."""
    ledger = root / ".tmp" / f"hook_reminders_{kind}.json"
    sid = str(payload.get("session_id") or "_")
    try:
        seen = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {}
        if not isinstance(seen, dict):
            seen = {}
    except (OSError, ValueError):
        seen = {}  # corrupt or unreadable ledger: start fresh, worst case one repeat reminder
    if key in seen.get(sid, []):
        return False
    if not isinstance(seen.get(sid), list):
        seen[sid] = []
    seen[sid].append(key)
    seen = dict(list(seen.items())[-20:])  # keep the last 20 sessions
    try:
        ledger.parent.mkdir(exist_ok=True)
        tmp = ledger.with_name(f"{ledger.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(seen), encoding="utf-8")
        os.replace(tmp, ledger)  # atomic: a reader never sees a half-written ledger
    except OSError as e:
        print(f"post-edit: ledger write failed: {e}", file=sys.stderr)
    return True


def edited_ranges(path: Path, payload: dict) -> list:
    """1-based (start, end) line ranges of new_string in the file; [] means format the whole file."""
    ti = payload.get("tool_input") or {}
    new = ti.get("new_string") if isinstance(ti, dict) else None
    if payload.get("tool_name") != "Edit":
        return []
    if not isinstance(new, str) or not new.strip():
        return [(1, 0)]  # pure deletion: nothing new to format
    text = path.read_text(encoding="utf-8", errors="replace")
    ranges, start = [], 0
    while (i := text.find(new, start)) != -1:
        first = text.count("\n", 0, i) + 1
        ranges.append((first, first + new.rstrip("\n").count("\n")))
        start = i + max(len(new), 1)
    return ranges or [(1, 0)]  # not found (e.g. already reformatted): sentinel = skip


def do_format(path: str, payload: dict) -> None:
    p = Path(path)
    low = p.as_posix().lower()
    if p.suffix.lower() != ".py" or not p.is_file() or "/.anneal/" in low or any(x in low for x in AM_LOCKED):
        return
    ranges = edited_ranges(p, payload)
    if ranges == [(1, 0)]:
        return
    run = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 30}
    if shutil.which("black"):
        cmd = ["black", "--quiet", *[f"--line-ranges={a}-{b}" for a, b in ranges], "--", str(p)]
    elif shutil.which("ruff"):
        cmd = ["ruff", "format", "--quiet", "--", str(p)]
        if ranges:  # ruff takes one range: span all edits (may format a little extra)
            a, b = min(r[0] for r in ranges), max(r[1] for r in ranges)
            cmd[3:3] = [f"--range={a}-{b}"]
    else:
        return  # no formatter installed: helper degrades silently
    r = subprocess.run(cmd, **run)
    if r.returncode not in (0, 123):  # 123 = black couldn't parse (syntax error): leave the file alone
        print(f"post-edit format: {cmd[0]} exit {r.returncode}: {r.stderr.strip()[:200]}", file=sys.stderr)


def do_note(path: str, payload: dict, root: Path) -> None:
    rel = rel_posix(path, root)
    if not rel.startswith(("directives/", "execution/")) or not first_time("note", payload, rel, root):
        return
    emit(f"note-taker: {rel} changed. If you learned something new (an unexpected error, an API limit, "
         f"a cross-cutting pattern), log it in .claude/notes/ ([tag] subject: detail; "
         f"directives/subagent/note_taker.md).")


def do_documenter(path: str, payload: dict, root: Path) -> None:
    rel = rel_posix(path, root)
    if not (rel.startswith("execution/") and rel.lower().endswith(".py")):
        return
    if any(x in rel.lower() for x in AM_LOCKED) or not first_time("documenter", payload, rel, root):
        return
    emit(f"documenter: {rel} was edited. When the script is done, spawn the documenter sub-agent "
         f"(directives/subagent/documenter.md) to sync its directive.")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = read_payload()
    ti = payload.get("tool_input")
    path = (sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None) or (
        ti.get("file_path") if isinstance(ti, dict) else None)
    if not isinstance(path, str) or not path:
        return
    root = project_root(payload)
    if mode == "format":
        do_format(path, payload)
    elif mode == "note":
        do_note(path, payload, root)
    elif mode == "documenter":
        do_documenter(path, payload, root)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — helper hooks must never fail an edit; logged to stderr
        print(f"post-edit {sys.argv[1:2]}: internal error, skipped: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)
