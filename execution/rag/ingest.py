"""
description: Ingest URLs / PDFs / text files into a local RAG vector store. Free-path:
             Gemini text-embedding-004 (1500 RPM free) + JSON file as the store.
             Sized for the "custom chatbot in a day" client engagement skeleton —
             escalate to Cloudflare Vectorize / Pinecone only when a paid client signs.
inputs:
  - --source <path-or-url>   File path (.txt/.md/.pdf) or http(s) URL; repeatable.
  - --store <name>           Store name; persists at execution/rag/stores/{name}.json. Default: "default".
  - --chunk-size <n>         Target chunk size in chars. Default: 500.
  - --reset                  Wipe the store before ingesting.
  - Env: GEMINI_API_KEY (required, free tier).
outputs:
  - File: execution/rag/stores/{name}.json — list of {text, embedding, source} chunks.
  - Stderr: chunk count, per-source progress, token estimate.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

# Fix Unicode crash on Windows cp1252 before any other output
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 - reconfigure is best-effort; some streams don't support it
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stderr)
log = logging.getLogger("rag.ingest")

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
STORES_DIR = Path(__file__).resolve().parent / "stores"
STORES_DIR.mkdir(exist_ok=True)

EMBED_MODEL = "gemini-embedding-001"
EMBED_MAX_CHARS = 2000  # Gemini text-embedding-004 ~ 2048 tokens; chars/4 = safe
DEFAULT_CHUNK_SIZE = 500
MAX_RETRY = 2


def _load_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        log.error("pypdf not installed. Run: pip install pypdf")
        raise SystemExit(2)
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
        else:
            log.warning("PDF page %d in %s: no extractable text (scanned image?)", i + 1, path.name)
    return "\n\n".join(pages)


def _load_url(url: str) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("requests / beautifulsoup4 not installed. Run: pip install requests beautifulsoup4")
        raise SystemExit(2)
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "RAG-ingest/0.1"})
    except requests.RequestException as exc:
        log.warning("URL fetch failed for %s: %s", url, exc)
        return ""
    if resp.status_code != 200:
        log.warning("URL %s returned HTTP %s — skipping", url, resp.status_code)
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_source(source: str) -> tuple[str, str]:
    """Return (text, source_label)."""
    if source.startswith("http://") or source.startswith("https://"):
        return _load_url(source), source
    raw_path = Path(source)
    if not raw_path.is_absolute():
        raw_path = (Path.cwd() / source).resolve()
    # LLM/CLI-supplied path validation per ~/.claude/rules/python-hardening.md #3.
    # Allow sources anywhere inside the workspace OR the user's CWD; reject paths
    # that escape both boundaries via .. traversal.
    resolved = raw_path.resolve()
    workspace = WORKSPACE_ROOT.resolve()
    cwd = Path.cwd().resolve()
    if not (resolved.is_relative_to(workspace) or resolved.is_relative_to(cwd)):
        raise ValueError(f"path traversal: {source} resolves outside workspace and cwd")
    if not resolved.exists():
        raise FileNotFoundError(f"source not found: {resolved}")
    suffix = resolved.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(resolved), str(resolved)
    if suffix in {".txt", ".md", ".html", ""}:
        return _load_text_file(resolved), str(resolved)
    raise ValueError(f"unsupported source type: {suffix} ({resolved})")


def _chunk(text: str, chunk_size: int) -> list[str]:
    """Naive paragraph-merge chunker. Paragraphs are merged greedily up to
    chunk_size; oversize paragraphs are hard-split at chunk_size."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > chunk_size * 2:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(para), chunk_size):
                chunks.append(para[i : i + chunk_size])
            continue
        if not buf:
            buf = para
        elif len(buf) + len(para) + 2 <= chunk_size:
            buf += "\n\n" + para
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    # Final cap: nothing exceeds EMBED_MAX_CHARS
    out: list[str] = []
    for c in chunks:
        if len(c) <= EMBED_MAX_CHARS:
            out.append(c)
        else:
            for i in range(0, len(c), EMBED_MAX_CHARS):
                out.append(c[i : i + EMBED_MAX_CHARS])
    return out


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call Gemini text-embedding-004 for a list of texts. Retries once on rate limit."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        log.error("GEMINI_API_KEY not set. Add this line to .env:\n  GEMINI_API_KEY=your_key_here")
        raise SystemExit(2)
    from google import genai

    client = genai.Client(api_key=api_key)
    embeddings: list[list[float]] = []
    for text in texts:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRY + 1):
            try:
                resp = client.models.embed_content(model=EMBED_MODEL, contents=text)
                # google-genai returns either an .embeddings list (current SDK) or a
                # single .embedding (older); handle both for forward-compat.
                if hasattr(resp, "embeddings") and resp.embeddings:
                    vec = list(resp.embeddings[0].values)
                elif hasattr(resp, "embedding"):
                    vec = list(resp.embedding.values)
                else:
                    raise RuntimeError(f"Unexpected embed response shape: {type(resp)}")
                embeddings.append(vec)
                break
            except Exception as exc:  # noqa: BLE001 - retry-then-raise pattern
                last_exc = exc
                msg = str(exc).lower()
                if "rate" in msg or "quota" in msg or "429" in msg:
                    sleep_s = 5 * (attempt + 1)
                    log.warning("Gemini rate-limit hit; sleeping %ds (attempt %d/%d)",
                                sleep_s, attempt + 1, MAX_RETRY + 1)
                    time.sleep(sleep_s)
                    continue
                raise
        else:
            raise RuntimeError(f"Embed retries exhausted: {last_exc}")
    return embeddings


def _store_path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    if not safe:
        raise ValueError(f"invalid store name: {name}")
    return STORES_DIR / f"{safe}.json"


def _load_store(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("Store %s is corrupted: %s. Re-run with --reset to rebuild.", path, exc)
        raise SystemExit(2)
    if not isinstance(data, list):
        raise SystemExit(f"unexpected store schema in {path}; expected list")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest sources into a RAG store.")
    parser.add_argument("--source", action="append", required=True,
                        help="File path or URL. Repeatable.")
    parser.add_argument("--store", default="default", help="Store name (file under execution/rag/stores/).")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--reset", action="store_true", help="Wipe store before ingesting.")
    args = parser.parse_args()

    store_path = _store_path(args.store)
    existing = [] if args.reset else _load_store(store_path)
    log.info("Store: %s (%d existing chunks, reset=%s)", store_path.name, len(existing), args.reset)

    all_new: list[dict] = []
    for source in args.source:
        log.info("Loading: %s", source)
        try:
            text, label = _load_source(source)
        except (FileNotFoundError, ValueError) as exc:
            log.warning("Skipping %s: %s", source, exc)
            continue
        if not text.strip():
            log.warning("Empty content from %s — skipped.", source)
            continue
        chunks = _chunk(text, args.chunk_size)
        if not chunks:
            log.warning("Chunking produced 0 chunks for %s — skipped.", source)
            continue
        log.info("  %d chunks (avg %d chars)", len(chunks), sum(len(c) for c in chunks) // len(chunks))
        embeddings = _embed_batch(chunks)
        for text_chunk, vec in zip(chunks, embeddings):
            all_new.append({"text": text_chunk, "embedding": vec, "source": label})

    if not all_new:
        log.error("No chunks ingested from any source. Store not written.")
        return 1

    combined = existing + all_new
    store_path.write_text(json.dumps(combined, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s — %d total chunks (%d new this run).",
             store_path, len(combined), len(all_new))
    log.info("Token estimate (rough, 4 chars/token): %d input tokens embedded this run.",
             sum(len(c["text"]) for c in all_new) // 4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
