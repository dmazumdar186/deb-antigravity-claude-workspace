"""
Cached HTTP client (SPEC.md I9: "Every fetch goes through a cache. No layer
re-fetches on re-run.").

Content is keyed by sha256(url) on disk so that re-running any layer is free
and offline. PDFs are text-extracted once and the extraction cached alongside,
because PyMuPDF extraction is the expensive part for large EIAR documents.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from .config import CONFIG, PKG_ROOT
from .contracts import RawDocument, SourceType

CACHE_DIR = PKG_ROOT / "run" / "_httpcache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Guards both the on-disk write and the per-host rate-limit clock.
# Per ~/.claude/rules/python-hardening.md rule 2: shared mutable state under
# concurrency must be lock-guarded; += and dict writes are not atomic enough.
_LOCK = threading.Lock()
_LAST_HIT: dict[str, float] = {}


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def content_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _paths(url: str) -> tuple[Path, Path]:
    k = url_key(url)
    return CACHE_DIR / f"{k}.body", CACHE_DIR / f"{k}.meta.json"


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    with _LOCK:
        last = _LAST_HIT.get(host, 0.0)
        wait = CONFIG.per_host_delay_s - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _LAST_HIT[host] = time.time()


def _pdf_to_text(raw: bytes) -> str:
    import fitz  # PyMuPDF

    with fitz.open(stream=raw, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def _html_to_text(raw: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n")


def fetch(
    url: str,
    source_type: SourceType = "other",
    force: bool = False,
    timeout: Optional[int] = None,
) -> Optional[RawDocument]:
    """Fetch a URL through the disk cache. Returns None on hard failure.

    Never raises on network errors -- a dead source must degrade the run,
    not kill it. Failures are recorded in the meta file so a re-run does not
    silently retry a permanently-404 URL on every pass.
    """
    body_p, meta_p = _paths(url)

    if meta_p.exists() and not force:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if not meta.get("ok"):
            return None
        text = body_p.read_text(encoding="utf-8", errors="replace")
        return RawDocument(
            doc_id=meta["doc_id"],
            url=url,
            source_type=meta.get("source_type", source_type),
            fetched_at=date.fromisoformat(meta["fetched_at"]),
            content_text=text,
            http_status=meta["http_status"],
            title=meta.get("title"),
            text_source=meta.get("text_source", "text_layer"),
        )

    _throttle(url)
    try:
        resp = requests.get(
            url,
            timeout=timeout or CONFIG.request_timeout_s,
            headers={"User-Agent": CONFIG.user_agent},
        )
    except Exception as exc:  # network-level failure
        # Recorded, not swallowed: the drop is visible in the meta file and
        # in fetch.jsonl. Re-running will not silently retry.
        meta_p.write_text(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "url": url}),
            encoding="utf-8",
        )
        return None

    ctype = resp.headers.get("Content-Type", "").lower()
    if resp.status_code != 200:
        meta_p.write_text(
            json.dumps({"ok": False, "http_status": resp.status_code, "url": url}),
            encoding="utf-8",
        )
        return None

    is_pdf = "pdf" in ctype or url.lower().endswith(".pdf")
    try:
        if is_pdf:
            text = _pdf_to_text(resp.content)
        elif "html" in ctype or "xml" in ctype:
            text = _html_to_text(resp.content)
        else:
            text = resp.content.decode("utf-8", errors="replace")
    except Exception as exc:
        meta_p.write_text(
            json.dumps({"ok": False, "error": f"parse: {exc}", "url": url}),
            encoding="utf-8",
        )
        return None

    text = normalise_ws(text)

    # An image-only PDF has no text layer, and on the ACP corpus that is where
    # a large share of the consultancy witness evidence lives. Recovered by
    # transcription rather than abandoned -- and marked, because a quote
    # verified against a transcription is a weaker claim than one verified
    # against the document's own text. See core/ocr.py.
    text_source: str = "text_layer"
    if not text.strip() and is_pdf:
        from .ocr import transcribe_pdf

        recovered = transcribe_pdf(resp.content, url)
        if recovered and recovered.strip():
            text = normalise_ws(recovered)
            text_source = "ocr"
            log_ocr(url, len(text))

    # A 200 that parses to nothing is a FAILED fetch, not an empty document.
    # An image-only scanned PDF -- and An Coimisiun Pleanala publishes many --
    # returns 1.1 MB of JPEG with no text layer. Cached as ok:true it becomes a
    # zero-length document whose content hash is the SHA of the empty string,
    # so EVERY such document collapses onto one doc_id and the corpus silently
    # keys several distinct sources to a single empty entry. The validator
    # fails closed against it, so nothing false ships -- but the drop then
    # reads as a hallucination rather than as "this source was never readable".
    if not text.strip():
        meta_p.write_text(
            json.dumps(
                {
                    "ok": False,
                    "error": "empty_after_parse",
                    "http_status": resp.status_code,
                    "content_type": ctype,
                    "bytes": len(resp.content),
                    "url": url,
                }
            ),
            encoding="utf-8",
        )
        return None

    doc_id = content_id(text)
    title = _extract_title(resp.content, ctype)

    with _LOCK:
        body_p.write_text(text, encoding="utf-8")
        meta_p.write_text(
            json.dumps(
                {
                    "ok": True,
                    "doc_id": doc_id,
                    "url": url,
                    "source_type": source_type,
                    "http_status": resp.status_code,
                    "fetched_at": date.today().isoformat(),
                    "title": title,
                    "text_source": text_source,
                    "content_type": ctype,
                }
            ),
            encoding="utf-8",
        )

    return RawDocument(
        doc_id=doc_id,
        url=url,
        source_type=source_type,
        fetched_at=date.today(),
        content_text=text,
        http_status=resp.status_code,
        title=title,
        text_source=text_source,
    )


def log_ocr(url: str, chars: int) -> None:
    """Recovered scans are announced, never silent.

    A run where half the corpus arrived by transcription is a materially
    different run from one where none did, and the operator should be able to
    see that in the log without going looking for it.
    """
    print("[cache] OCR recovered " + str(chars) + " chars from a scanned PDF: "
          + url[:90], flush=True)


def _extract_title(raw: bytes, ctype: str) -> Optional[str]:
    if "html" not in ctype:
        return None
    try:
        from bs4 import BeautifulSoup

        t = BeautifulSoup(raw, "html.parser").title
        return t.get_text(strip=True) if t else None
    except Exception:
        return None  # title is cosmetic; never fail a fetch over it


def normalise_ws(text: str) -> str:
    """Collapse the whitespace noise PDF extraction produces.

    Must stay in sync with validator.normalize() -- if this collapses a
    character sequence that the validator does not, verbatim quotes will
    fail to match and every claim gets dropped.
    """
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if ln:
            out.append(ln)
            blank = 0
        else:
            blank += 1
            if blank <= 1:
                out.append("")
    return "\n".join(out).strip()


def head_ok(url: str, timeout: int = 20) -> tuple[bool, int]:
    """Liveness check for L12. Returns (alive, status)."""
    try:
        _throttle(url)
        r = requests.head(
            url, timeout=timeout, allow_redirects=True,
            headers={"User-Agent": CONFIG.user_agent},
        )
        if r.status_code in (403, 405):  # some hosts refuse HEAD
            r = requests.get(
                url, timeout=timeout, allow_redirects=True,
                headers={"User-Agent": CONFIG.user_agent}, stream=True,
            )
        return r.status_code == 200, r.status_code
    except Exception:
        return False, 0


def fetch_raw(url: str, force: bool = False) -> Optional[bytes]:
    """Cached fetch that preserves the ORIGINAL bytes.

    fetch() stores extracted text, which discards href attributes. Link
    discovery on a case page needs the markup, so it gets its own cache slot.
    """
    k = url_key(url)
    raw_p = CACHE_DIR / (k + ".raw")
    if raw_p.exists() and not force:
        return raw_p.read_bytes()
    _throttle(url)
    try:
        resp = requests.get(
            url,
            timeout=CONFIG.request_timeout_s,
            headers={"User-Agent": CONFIG.user_agent},
        )
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    with _LOCK:
        raw_p.write_bytes(resp.content)
    return resp.content


def fetch_rendered(
    url: str, source_type: SourceType = "company_bio", force: bool = False
) -> Optional[RawDocument]:
    """Fetch through Firecrawl so JavaScript-rendered pages yield content.

    Most Irish consultancy sites render their staff directory client-side.
    Plain HTTP returns a shell: ocsc.ie/people/ gave 0 profile links and 0
    occurrences of "CEng" over raw HTML, but 42.7k chars containing 30 "CEng"
    and 32 "MIEI" once rendered. Without this path, Role 1 has no source.

    Cached separately from fetch() so a rendered page and a raw page can
    coexist for the same URL.
    """
    k = url_key("RENDERED::" + url)
    body_p = CACHE_DIR / (k + ".body")
    meta_p = CACHE_DIR / (k + ".meta.json")

    if meta_p.exists() and not force:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if not meta.get("ok"):
            return None
        return RawDocument(
            doc_id=meta["doc_id"],
            url=url,
            source_type=meta.get("source_type", source_type),
            fetched_at=date.fromisoformat(meta["fetched_at"]),
            content_text=body_p.read_text(encoding="utf-8", errors="replace"),
            http_status=200,
            title=meta.get("title"),
        )

    from .config import secret

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v2/scrape",
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            headers={"Authorization": "Bearer " + secret("FIRECRAWL_API_KEY")},
            timeout=180,
        )
        payload = resp.json() if resp.status_code == 200 else {}
        text = (payload.get("data") or {}).get("markdown", "") or ""
        title = ((payload.get("data") or {}).get("metadata") or {}).get("title")
    except Exception as exc:
        meta_p.write_text(
            json.dumps({"ok": False, "error": repr(exc)[:200], "url": url}),
            encoding="utf-8",
        )
        return None

    if not text.strip():
        meta_p.write_text(json.dumps({"ok": False, "url": url}), encoding="utf-8")
        return None

    text = normalise_ws(text)
    doc_id = content_id(text)
    with _LOCK:
        body_p.write_text(text, encoding="utf-8")
        meta_p.write_text(
            json.dumps(
                {
                    "ok": True, "doc_id": doc_id, "url": url,
                    "source_type": source_type, "rendered": True,
                    "fetched_at": date.today().isoformat(), "title": title,
                }
            ),
            encoding="utf-8",
        )
    return RawDocument(
        doc_id=doc_id, url=url, source_type=source_type,
        fetched_at=date.today(), content_text=text, http_status=200, title=title,
    )
