"""Link a folder of markdown pages (site content or a second brain) to each other with Jev.

description: Builds a short profile per page (title, headings, first ~600 body chars),
             shortlists the top-N other pages per page by deterministic Jaccard overlap on
             title+heading words, then asks Jev ONE call per page with one `noul` question
             per candidate ("would a reader of PAGE benefit from a link to CANDIDATE?").
             Keeps links >= --min-prob, at most --max-links per page, never to itself.
             --report writes <dir>/.jev_backlinks.json + a markdown table; --apply writes
             an idempotent `## Related` block between jev-backlinks markers in each file.
             Directive: directives/rag/jev_backlinks.md
inputs: --dir path (required); --ext md[,mdx,html]; --exclude globs (default node_modules,
        .git, .tmp, _archived); --candidates 12; --min-prob 0.6; --max-links 5;
        --limit; --workers 8; --report (default) | --apply; --dry-run.
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: <dir>/.jev_backlinks.json (summary + links per page); markdown table on stdout;
         with --apply, updated files (unless --dry-run); ledger row in .tmp/jev_ledger.jsonl
         (caller "jev_backlinks").
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

START = "<!-- jev-backlinks:start -->"
END = "<!-- jev-backlinks:end -->"
REPORT_NAME = ".jev_backlinks.json"
DEFAULT_EXCLUDE = ["node_modules", ".git", ".tmp", "_archived"]
BODY_CHARS = 600
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "into", "is", "it",
    "its", "of", "on", "or", "our", "that", "the", "this", "to", "with", "what", "when", "where",
    "which", "who", "why", "your", "you", "we", "i", "not", "no", "use", "using", "via", "vs",
}
_BLOCK_RE = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


# ---- discovery + profiles ------------------------------------------------------------------

def _excluded(rel: Path, patterns: list[str]) -> bool:
    for part in rel.parts:
        if any(fnmatch.fnmatch(part, p) for p in patterns):
            return True
    return any(fnmatch.fnmatch(rel.as_posix(), p) for p in patterns)


def safe_path(root: Path, p: Path) -> Path:
    """Resolve p and refuse anything outside root."""
    rp = p.resolve()
    if not rp.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes --dir: {p}")
    return rp


def find_pages(root: Path, exts: list[str], exclude: list[str]) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    for ext in exts:
        for p in root.rglob(f"*.{ext.lstrip('.')}"):
            if p.is_file() and not _excluded(p.relative_to(root), exclude):
                out.append(safe_path(root, p))
    return sorted(set(out))


def profile(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _BLOCK_RE.sub("", text)
    title = ""
    fm = _FM_RE.match(text)
    if fm:
        m = re.search(r"^title:\s*(.+)$", fm.group(1), re.M)
        if m:
            title = m.group(1).strip().strip("\"'")
        text = text[fm.end():]
    headings = [h.strip() for h in re.findall(r"^#{1,6}\s+(.+)$", text, re.M)]
    if not title:
        h1 = re.search(r"^#\s+(.+)$", text, re.M)
        title = h1.group(1).strip() if h1 else path.stem.replace("_", " ").replace("-", " ")
    body = re.sub(r"<[^>]+>", " ", text)
    body = re.sub(r"\s+", " ", body).strip()[:BODY_CHARS]
    return {"path": path.relative_to(root.resolve()).as_posix(), "title": title,
            "headings": [h for h in headings if h != title][:15], "summary": body}


def words(p: dict[str, Any]) -> set[str]:
    raw = " ".join([p["title"], *p["headings"], Path(p["path"]).stem.replace("_", " ")]).lower()
    return {w for w in re.findall(r"[a-z0-9]+", raw) if len(w) > 2 and w not in STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def shortlist(profiles: list[dict[str, Any]], k: int) -> list[list[int]]:
    ws = [words(p) for p in profiles]
    out: list[list[int]] = []
    for i in range(len(profiles)):
        scored = [(jaccard(ws[i], ws[j]), j) for j in range(len(profiles)) if j != i]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: (-s[0], s[1]))
        out.append([j for _, j in scored[:k]])
    return out


# ---- Jev -----------------------------------------------------------------------------------

def _brief(p: dict[str, Any]) -> dict[str, Any]:
    return {"title": p["title"], "path": p["path"], "headings": p["headings"][:8],
            "summary": p["summary"][:300]}


def build_call(page: dict[str, Any], cands: list[dict[str, Any]]) -> tuple[dict, dict]:
    state = {"page": {**_brief(page), "summary": page["summary"]},
             "candidates": [{"index": i, **_brief(c)} for i, c in enumerate(cands)]}
    qs = {f"rel_{i}": jev_client.noul(
        f"Would a reader of PAGE benefit from a link to candidate {i} ('{c['title']}')?",
        "the candidate covers a closely related or next-step topic the reader would want",
        "the candidate is unrelated or only shares generic words")
        for i, c in enumerate(cands)}
    return state, qs


def select_links(profiles: list[dict[str, Any]], shortlists: list[list[int]],
                 results: list[jev_client.JevResult | None], min_prob: float,
                 max_links: int) -> list[list[tuple[int, float]]]:
    """Per page: [(target_index, prob)] sorted by prob desc, self excluded, capped."""
    links: list[list[tuple[int, float]]] = []
    for i, (cands, r) in enumerate(zip(shortlists, results)):
        keep: list[tuple[int, float]] = []
        if r is not None and r.ok:
            for qi, j in enumerate(cands):
                if j == i:
                    continue
                prob = r.noul(f"rel_{qi}")
                if prob >= min_prob:
                    keep.append((j, prob))
        keep.sort(key=lambda t: (-t[1], t[0]))
        links.append(keep[:max_links])
    return links


def run_jev(profiles: list[dict[str, Any]], shortlists: list[list[int]],
            workers: int) -> list[jev_client.JevResult | None]:
    def _one(i: int) -> jev_client.JevResult | None:
        if not shortlists[i]:
            return None
        state, qs = build_call(profiles[i], [profiles[j] for j in shortlists[i]])
        return jev_client.decide(state, qs)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(_one, range(len(profiles))))


# ---- apply ---------------------------------------------------------------------------------

def render_block(src_rel: str, targets: list[dict[str, Any]]) -> str:
    lines = [START, "## Related", ""]
    for t in targets:
        rel = os.path.relpath(t["path"], os.path.dirname(src_rel) or ".").replace(os.sep, "/")
        lines.append(f"- [{t['title']}]({rel})")
    lines.append(END)
    return "\n".join(lines)


def upsert_block(text: str, block: str) -> str:
    if _BLOCK_RE.search(text):
        return _BLOCK_RE.sub(lambda _m: block, text, count=1)
    return text.rstrip("\n") + "\n\n" + block + "\n"


# ---- main ----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ext", default="md")
    ap.add_argument("--exclude", nargs="*", default=DEFAULT_EXCLUDE)
    ap.add_argument("--candidates", type=int, default=12)
    ap.add_argument("--min-prob", type=float, default=0.6)
    ap.add_argument("--max-links", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.dir).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    pages = find_pages(root, [e.strip() for e in a.ext.split(",") if e.strip()], a.exclude)
    if a.limit:
        pages = pages[: a.limit]
    profiles = [profile(p, root) for p in pages]
    shortlists = shortlist(profiles, a.candidates)
    results = run_jev(profiles, shortlists, a.workers)
    links = select_links(profiles, shortlists, results, a.min_prob, a.max_links)
    pairs = sum(len(s) for s in shortlists)
    kept = sum(len(lk) for lk in links)
    cost = sum(r.cost_usd for r in results if r is not None)
    errors = [profiles[i]["path"] + ": " + str(r.error) for i, r in enumerate(results)
              if r is not None and r.error]
    mutual = {(i, j) for i, lk in enumerate(links) for j, _ in lk
              if any(k == i for k, _ in links[j])}

    out_pages = [{"path": p["path"], "title": p["title"],
                  "links": [{"path": profiles[j]["path"], "title": profiles[j]["title"],
                             "prob": round(pr, 3), "mutual": (i, j) in mutual}
                            for j, pr in links[i]]} for i, p in enumerate(profiles)]
    wall = time.perf_counter() - t0
    summary = {"pages": len(profiles), "pairs_evaluated": pairs, "links_kept": kept,
               "mutual_links": len(mutual), "errors": len(errors),
               "cost_usd": round(cost, 6), "wall_s": round(wall, 2)}

    if a.apply:
        lock = threading.Lock()
        changed = 0
        for i, pg in enumerate(out_pages):
            if not pg["links"]:
                continue
            fp = safe_path(root, root / pg["path"])
            for t in pg["links"]:
                safe_path(root, root / t["path"])
            text = fp.read_text(encoding="utf-8")
            new = upsert_block(text, render_block(pg["path"], pg["links"]))
            if new != text:
                with lock:
                    changed += 1
                if not a.dry_run:
                    fp.write_text(new, encoding="utf-8")
        summary["files_changed" if not a.dry_run else "files_would_change"] = changed
    else:
        report = safe_path(root, root / REPORT_NAME)
        report.write_text(json.dumps({"summary": summary, "pages": out_pages, "errors": errors},
                                     indent=2, ensure_ascii=False), encoding="utf-8")
        print("| Page | Linked to | p |\n|---|---|---|")
        for pg in out_pages:
            for t in pg["links"]:
                print(f"| {pg['path']} | {t['path']} | {t['prob']:.2f} |")
        print(f"\nreport: {report}")
    for e in errors[:5]:
        print(f"error: {e}", file=sys.stderr)
    print(json.dumps(summary))
    jev_client.append_ledger({"caller": "jev_backlinks", "count": len(profiles),
                              "cost_usd": summary["cost_usd"], "wall_s": summary["wall_s"],
                              "errors": len(errors)}, path=_ROOT / ".tmp" / "jev_ledger.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
