"""
description: Find Claude Code sessions killed by an oversized attached file ("Prompt is too long").
inputs:
  CLI: --projects-dir <dir> (default ~/.claude/projects), --min-kb <int> (default 200),
       --preview <int> (default 120), --json
  env: none
outputs:
  stdout: one row per oversized `document` attachment - session id, size, est. tokens, preview
  exit:   0 if none found, 1 if at least one oversized attachment was found

Notes:
  - Diagnostic, not a gate. Nothing can block an attachment before it is sent, because
    the attachment IS the request. See ~/.claude/rules/no-large-file-attachments.md.
  - Transcript lines are NOT read in text mode. Attachment payloads can contain raw \\r
    and \\n bytes inside the JSON string, which universal-newline translation would split
    mid-record and make unparseable. We read bytes and split on b"\\n" only, then fall
    back to a regex when a record still will not parse.
  - Token estimates use chars/token ratios that differ sharply by content type; a
    lead CSV tokenizes near 2.3 chars/token where prose is near 4.0. Underestimating
    here is worse than overestimating, so dense-looking payloads use the low ratio.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Rough chars-per-token by payload shape. See the rule file's table.
RATIO_DENSE = 2.3   # CSV/JSONL: emails, URLs, IDs, heavy punctuation
RATIO_PROSE = 4.0   # natural language

_DOC_RE = re.compile(rb'"type"\s*:\s*"document"')
_DATA_RE = re.compile(rb'"data"\s*:\s*"(.{0,200})', re.DOTALL)


def _looks_dense(sample: str) -> bool:
    """Heuristic: does this payload tokenize like a CSV rather than like prose?"""
    if not sample:
        return True
    punct = sum(sample.count(c) for c in ',;|@/:"')
    return (punct / max(len(sample), 1)) > 0.03


def scan_file(path: Path, min_bytes: int, preview: int) -> list[dict]:
    """Return one record per oversized document attachment in a transcript."""
    hits: list[dict] = []
    raw = path.read_bytes()
    for lineno, line in enumerate(raw.split(b"\n")):
        if len(line) < min_bytes or not _DOC_RE.search(line):
            continue
        sample = ""
        try:
            rec = json.loads(line.decode("utf-8", "replace"))
            content = rec.get("message", {}).get("content")
            blocks = content if isinstance(content, list) else []
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "document":
                    sample = str(b.get("source", {}).get("data", ""))
                    break
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            # Payload contains bytes that break strict parsing; recover the head only.
            m = _DATA_RE.search(line)
            sample = m.group(1).decode("utf-8", "replace") if m else ""
        n_chars = len(sample) if len(sample) > preview else len(line)
        ratio = RATIO_DENSE if _looks_dense(sample[:2000]) else RATIO_PROSE
        hits.append({
            "session": path.stem,
            "project": path.parent.name,
            "line": lineno,
            "bytes": len(line),
            "est_tokens": int(n_chars / ratio),
            "preview": sample[:preview].replace("\n", " ").replace("\r", " "),
        })
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find sessions killed by an oversized attached file.")
    ap.add_argument("--projects-dir", type=Path,
                    default=Path.home() / ".claude" / "projects",
                    help="Root of Claude Code session transcripts")
    ap.add_argument("--min-kb", type=int, default=200,
                    help="Only report attachments at least this large (default 200 KB)")
    ap.add_argument("--preview", type=int, default=120, help="Preview characters to show")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    args = ap.parse_args()

    if not args.projects_dir.is_dir():
        print(f"ERROR: projects dir not found: {args.projects_dir}", file=sys.stderr)
        return 2

    transcripts = sorted(args.projects_dir.glob("*/*.jsonl"))
    hits: list[dict] = []
    for t in transcripts:
        try:
            hits.extend(scan_file(t, args.min_kb * 1024, args.preview))
        except OSError as e:
            # A transcript being written right now can vanish or lock mid-scan; the
            # scan is best-effort across many files, so report and keep going.
            print(f"WARN: could not read {t.name}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(hits, indent=2))
    else:
        print(f"Scanned {len(transcripts)} transcripts under {args.projects_dir}")
        if not hits:
            print(f"No attachments >= {args.min_kb} KB found. Nothing to report.")
        else:
            print(f"\n{len(hits)} oversized attachment(s) found "
                  f"(>= {args.min_kb} KB). These are what blow the context window:\n")
            for h in sorted(hits, key=lambda x: -x["bytes"]):
                print(f"  {h['bytes']/1024:8.0f} KB  ~{h['est_tokens']:>9,} tok  "
                      f"session {h['session'][:8]}  line {h['line']}")
                print(f"            {h['preview']}")
            print("\nFix: pass these files by PATH, not as attachments.")
            print("See ~/.claude/rules/no-large-file-attachments.md")

    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
