"""Find by meaning: type roughly what you want, Jev points at the right paragraph.

description: Splits a page (markdown / txt / html file, a URL, or a folder of files) into
             paragraph chunks (tiny ones merged to >= 40 words, long ones capped ~120 words,
             each keeps file, line range and heading). Stage 1: batches of <= 25 chunks, ONE
             Jev call per batch (a `choice` over chunk ids with 160-char previews + `none`,
             plus a `noul` "does any option answer the query?" so a batch can abstain), run in
             parallel threads. Stage 2: the winners (<= 25, best per file in --dir mode) go to
             one final `choice` with full chunk text; top-k by probability. The #1 hit gets a
             cheap sentence-level `choice` to mark the best sentence with `>>`.
             Directive: directives/rag/jev_find.md
inputs: --query (required); one of --file path | --url https://... | --dir path [--ext md];
        --top 5; --workers 8; --json; --dry-run (print the chunk plan, no calls).
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: hits on stdout (file, lines, heading, probability, chunk text) or JSON; summary line
         (chunks, batches, calls, latency, cost); ledger row .tmp/jev_ledger.jsonl
         (caller "jev_find").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

MIN_WORDS = 40
MAX_WORDS = 120
BATCH_SIZE = 25
PREVIEW_CHARS = 160
ABSTAIN_BELOW = 0.2  # batch noul below this = batch abstains
UA = "Mozilla/5.0 (compatible; jev-find/1.0; +https://github.com/dmazumdar186)"
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`*\"'(\[-])")


# ---- html -> text --------------------------------------------------------------------------

class _Stripper(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "br", "tr", "table",
             "blockquote", "pre", "header", "footer", "main", "nav", "aside", "figure"}
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0
        self._heading: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading = int(tag[1])
            self.out.append("\n\n" + "#" * self._heading + " ")
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading = 0
            self.out.append("\n\n")
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.out.append(text)


def html_to_text(html: str) -> str:
    """Strip html to blank-line separated paragraphs; h1-h6 become markdown `#` headings."""
    p = _Stripper()
    p.feed(html)
    p.close()
    lines = [ln.strip() for ln in "".join(p.out).split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# ---- chunking ------------------------------------------------------------------------------

def _paragraphs(text: str) -> list[tuple[int, int, list[str]]]:
    """Blank-line split -> (line_start, line_end, lines), 1-based inclusive."""
    out: list[tuple[int, int, list[str]]] = []
    cur: list[str] = []
    start = 0
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not cur:
                start = i
            cur.append(line)
        elif cur:
            out.append((start, i - 1, cur))
            cur = []
    if cur:
        out.append((start, start + len(cur) - 1, cur))
    return out


def chunk_text(text: str, file: str = "") -> list[dict[str, Any]]:
    """Paragraph chunks: merge tiny to >= MIN_WORDS, cap at ~MAX_WORDS, keep heading + lines."""
    pieces: list[dict[str, Any]] = []  # (heading, ls, le, words)
    heading = ""
    in_fm = text.startswith("---\n")
    for ls, le, lines in _paragraphs(text):
        if in_fm:  # skip YAML front matter
            if any(ln.strip() == "---" for ln in lines[1:]):
                in_fm = False
            continue
        body: list[str] = []
        for ln in lines:
            m = _HEADING_RE.match(ln)
            if m:
                heading = m.group(2).strip()
            else:
                body.append(ln.strip())
        words = " ".join(body).split()
        for k in range(0, len(words), MAX_WORDS):
            pieces.append({"heading": heading, "line_start": ls, "line_end": le,
                           "words": words[k:k + MAX_WORDS]})
    chunks: list[dict[str, Any]] = []
    buf: dict[str, Any] | None = None

    def _flush() -> None:
        nonlocal buf
        if buf and buf["words"]:
            chunks.append(buf)
        buf = None

    for p in pieces:
        if buf and len(buf["words"]) + len(p["words"]) > MAX_WORDS:
            _flush()
        if buf is None:
            buf = dict(p, words=list(p["words"]))
        else:
            buf["words"].extend(p["words"])
            buf["line_end"] = p["line_end"]
        if len(buf["words"]) >= MIN_WORDS:
            _flush()
    if buf and buf["words"]:
        if chunks and len(chunks[-1]["words"]) + len(buf["words"]) <= MAX_WORDS + MIN_WORDS:
            chunks[-1]["words"].extend(buf["words"])
            chunks[-1]["line_end"] = buf["line_end"]
        else:
            chunks.append(buf)
    return [{"file": file, "line_start": c["line_start"], "line_end": c["line_end"],
             "heading": c["heading"], "text": " ".join(c["words"])} for c in chunks]


def load_source(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return html_to_text(raw) if path.suffix.lower() in (".html", ".htm") else raw


def fetch_url(url: str) -> str:
    import requests
    if not url.startswith(("http://", "https://")):
        raise ValueError("--url must start with http:// or https://")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "")
    return html_to_text(r.text) if "html" in ctype or "<html" in r.text[:500].lower() else r.text


def safe_path(root: Path, p: Path) -> Path:
    rp = p.resolve()
    if not rp.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes --dir: {p}")
    return rp


def dir_chunks(root: Path, exts: list[str]) -> list[dict[str, Any]]:
    root = root.resolve()
    out: list[dict[str, Any]] = []
    files: set[Path] = set()
    for ext in exts:
        for p in root.rglob(f"*.{ext.lstrip('.')}"):
            if p.is_file() and not any(part.startswith(".") or part == "node_modules"
                                       for part in p.relative_to(root).parts):
                try:
                    files.add(safe_path(root, p))
                except ValueError as exc:  # symlink escaping --dir: skip it, keep going
                    print(f"jev_find: skipping {p}: {exc}", file=sys.stderr)
    for p in sorted(files):
        rel = p.relative_to(root.parent if root.parent != root else root).as_posix()
        out.extend(chunk_text(load_source(p), rel))
    return out


# ---- batching + Jev ------------------------------------------------------------------------

def plan_batches(n: int, size: int = BATCH_SIZE) -> list[list[int]]:
    size = max(1, min(size, BATCH_SIZE))
    return [list(range(i, min(i + size, n))) for i in range(0, n, size)]


def _label(c: dict[str, Any]) -> str:
    h = f"[{c['heading']}] " if c.get("heading") else ""
    return (h + c["text"])


def batch_questions(chunks: list[dict[str, Any]], idxs: list[int]) -> dict[str, dict[str, Any]]:
    opts = {str(i): _label(chunks[i])[:PREVIEW_CHARS] for i in idxs}
    opts["none"] = "none of these passages is about what the query is looking for"
    return {
        "best": jev_client.choice(
            "Which passage is the one the reader is looking for? The words may not match; "
            "judge by meaning.", opts),
        "any": jev_client.noul(
            "Does any option in this batch answer the query?",
            "at least one passage is clearly about what the query describes",
            "no passage is about what the query describes"),
    }


class _Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0
        self.cost = 0.0
        self.tokens = 0
        self.errors: list[str] = []

    def add(self, r: jev_client.JevResult) -> None:
        with self.lock:
            self.calls += 1
            self.cost += r.cost_usd
            self.tokens += r.input_tokens
            if r.error:
                self.errors.append(r.error[:200])


def _state(query: str) -> dict[str, Any]:
    return {"task": "find-by-meaning search inside a document", "query": query}


def find(query: str, chunks: list[dict[str, Any]], *, top: int = 5, workers: int = 8,
         per_file: bool = False, mark_sentence: bool = True) -> dict[str, Any]:
    """Two-stage Jev ranking. Returns {hits, summary}. Fails open (empty hits + errors)."""
    t0 = time.perf_counter()
    stats = _Stats()
    batches = plan_batches(len(chunks))

    def _stage1(idxs: list[int]) -> tuple[int, float] | None:
        r = jev_client.decide(_state(query), batch_questions(chunks, idxs))
        stats.add(r)
        if not r.ok:
            return None
        pick = r.choice("best")
        if pick == "none" or not pick.isdigit() or int(pick) not in idxs:
            return None
        if r.noul("any", 1.0) < ABSTAIN_BELOW:
            return None
        prob = r.probabilities("best").get(pick, r.confidence("best"))
        return int(pick), prob * r.noul("any", 1.0)

    winners: list[tuple[int, float]] = []
    if batches:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            winners = [w for w in pool.map(_stage1, batches) if w]
    if per_file:  # best chunk per file, then global rank
        best: dict[str, tuple[int, float]] = {}
        for i, s in winners:
            f = chunks[i]["file"]
            if f not in best or s > best[f][1]:
                best[f] = (i, s)
        winners = list(best.values())
    winners.sort(key=lambda w: -w[1])
    winners = winners[:BATCH_SIZE]

    ranked: list[tuple[int, float]] = winners
    if len(winners) > 1:
        opts = {str(i): _label(chunks[i]) for i, _ in winners}
        r = jev_client.decide(_state(query), {"best": jev_client.choice(
            "Which passage best answers what the reader is looking for? Judge by meaning.", opts)})
        stats.add(r)
        probs = r.probabilities("best") if r.ok else {}
        if probs:
            ranked = sorted(((i, probs.get(str(i), 0.0)) for i, _ in winners), key=lambda w: -w[1])
    hits = []
    for i, p in ranked[:max(1, top)]:
        hits.append({**chunks[i], "chunk": i, "probability": round(p, 4), "sentence": None})

    if hits and mark_sentence:
        sents = [s for s in _SENT_RE.split(hits[0]["text"]) if s.strip()]
        if len(sents) > 1:
            r = jev_client.decide(_state(query), {"sent": jev_client.choice(
                "Which sentence is the exact spot the reader is looking for?",
                {str(k): s[:300] for k, s in enumerate(sents)})})
            stats.add(r)
            pick = r.choice("sent") if r.ok else ""
            if pick.isdigit() and int(pick) < len(sents):
                hits[0]["sentence"] = sents[int(pick)]

    summary = {"chunks": len(chunks), "batches": len(batches), "calls": stats.calls,
               "latency_ms": int((time.perf_counter() - t0) * 1000),
               "cost_usd": round(stats.cost, 6), "input_tokens": stats.tokens,
               "errors": stats.errors}
    return {"query": query, "hits": hits, "summary": summary}


def render(hit: dict[str, Any]) -> str:
    text = hit["text"]
    if hit.get("sentence") and hit["sentence"] in text:
        text = text.replace(hit["sentence"], f"\n>> {hit['sentence']}\n", 1)
    head = f" [{hit['heading']}]" if hit.get("heading") else ""
    return (f"{hit['file']}:{hit['line_start']}-{hit['line_end']}{head}  p={hit['probability']:.2f}\n"
            f"  {text.strip()}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find by meaning with Jev.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--url")
    src.add_argument("--dir")
    ap.add_argument("--ext", default="md")
    ap.add_argument("--query", required=True)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.file:
            p = Path(a.file)
            chunks = chunk_text(load_source(p), p.as_posix())
        elif a.url:
            chunks = chunk_text(fetch_url(a.url), a.url)
        else:
            root = Path(a.dir)
            if not root.is_dir():
                raise ValueError(f"--dir is not a directory: {root}")
            chunks = dir_chunks(root, [e.strip() for e in a.ext.split(",") if e.strip()])
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # requests errors from --url  # noqa: BLE001
        print(f"error fetching: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 2

    if a.dry_run:
        batches = plan_batches(len(chunks))
        plan = {"chunks": len(chunks), "batches": len(batches),
                "calls_max": len(batches) + 2,
                "files": len({c["file"] for c in chunks}),
                "sample": [{k: c[k] for k in ("file", "line_start", "line_end", "heading")}
                           | {"words": len(c["text"].split())} for c in chunks[:10]]}
        print(json.dumps(plan, indent=2))
        return 0
    if not chunks:
        print("error: no text chunks found", file=sys.stderr)
        return 2
    if not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    res = find(a.query, chunks, top=a.top, workers=a.workers, per_file=bool(a.dir))
    s = res["summary"]
    jev_client.append_ledger({"caller": "jev_find", "calls": s["calls"], "cost_usd": s["cost_usd"],
                              "input_tokens": s["input_tokens"], "latency_ms": s["latency_ms"],
                              "errors": len(s["errors"])})
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if not res["hits"]:
            print("no match (Jev abstained or failed open)")
        for n, h in enumerate(res["hits"], 1):
            print(f"#{n} {render(h)}\n")
        print(f"summary: chunks={s['chunks']} batches={s['batches']} calls={s['calls']} "
              f"latency={s['latency_ms']}ms cost=${s['cost_usd']:.6f} errors={len(s['errors'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
