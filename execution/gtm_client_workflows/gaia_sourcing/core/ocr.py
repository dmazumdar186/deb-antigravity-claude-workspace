"""
Text recovery for image-only PDFs.

An Coimisiun Pleanala publishes a large share of its oral-hearing evidence as
scans -- 46 of the 72 witness documents discovered across MetroLink and DART+
West have no text layer at all, and `fetch()` correctly records them as
`empty_after_parse` rather than caching an empty document. On DART+ West that
is not a marginal loss: the scanned set is where the consultancy witnesses
are (CS Consulting, Transport Insights, and the Module G evidence), while the
born-digital set is mostly the applicant's own technical appendices.

Tesseract is not installed on this machine and installing a system OCR engine
is not something this pipeline should require. Recovery now tries a free,
local, deterministic path first -- rapidocr-onnxruntime (pure ONNX +
onnxruntime, CPU-only, no system binaries) rasterises each page with PyMuPDF
and reads it directly on this machine, at zero cost and with no API key.
Only if that path is unavailable or fails does recovery fall through to the
Anthropic API's native PDF support, which rasterises each page and reads it
server-side, then to Gemini's free tier.

THE INTEGRITY COST, STATED PLAINLY
----------------------------------
L6 validates every claim's quote character-by-character against the cached
source text. For a born-digital PDF that text IS the document. For a scan, the
text is a MODEL'S TRANSCRIPTION of the document, so L6 is checking one model's
quote against another model's reading of an image. That is a weaker guarantee
than the one the rest of the pipeline makes, and pretending otherwise would
quietly hollow out the promise the dossier is built on.

So it is not hidden. Documents recovered this way are marked
`text_source="ocr"`, the flag rides through to the claim, and the renderer
prints the provenance on the card next to the quote. A reader can see which
evidence came from a scan and weigh it accordingly.

Two further guards keep the transcription honest:

  - The prompt is a transcription instruction, not a summarisation or
    extraction one. The model is told to reproduce the page and to mark
    anything it cannot read as [illegible] rather than guess at it.
  - A transcription that comes back shorter than a floor proportional to the
    page count is rejected outright. A model that summarises instead of
    transcribing produces a short, fluent document, and short-and-fluent is
    exactly the shape that would sail through the validator while containing
    sentences the scan never had.
"""

from __future__ import annotations

import base64
from typing import Optional

# Anthropic's PDF support caps at 100 pages / 32 MB per request. A witness
# statement is far smaller; anything above the cap is a bundle we do not want.
_MAX_BYTES = 24 * 1024 * 1024
_MAX_PAGES = 100

# Below this many characters per page, the model summarised rather than
# transcribed. A real page of a witness statement carries several hundred
# characters; a page of signatures or a figure carries fewer, so the floor is
# deliberately low and only catches wholesale summarisation.
_MIN_CHARS_PER_PAGE = 60

SYSTEM = """You transcribe scanned documents. You do not summarise them.

Reproduce the text of every page in reading order, exactly as it appears.

RULES
1. This is a transcription task. Copy the words on the page. Do not condense,
   do not paraphrase, do not reorder, do not add connecting prose, do not
   describe what the document is about.
2. Preserve paragraph breaks. Preserve headings and numbered list markers as
   they appear.
3. Where the scan is unreadable, write [illegible] at that point. Never guess
   at a word, a name, a number or a date you cannot actually read. A gap is
   correct; an invention is not.
4. Do not add commentary, a preamble, or a closing summary. Output the
   document's text and nothing else.
5. Include headers, footers, signature blocks and stamps where legible -- a
   witness statement's qualifications section and signature are exactly the
   parts that matter here.
"""


def page_count(raw: bytes) -> Optional[int]:
    try:
        import fitz

        with fitz.open(stream=raw, filetype="pdf") as doc:
            return doc.page_count
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Free, local, deterministic OCR -- tried before either paid model.
#
# The operator has $30 of Anthropic credit total and wants it spent on
# extraction, not on reading scans a CPU-only open-source engine can already
# read for free. rapidocr-onnxruntime is pure ONNX + onnxruntime: no system
# binaries (no tesseract, no poppler), CPU-only, MIT-licensed. It is tried
# first; the paid paths only run if it is unavailable, returns nothing, or
# fails the same summarisation/length floor the model paths are held to.
# ---------------------------------------------------------------------------

_LOCAL_ENGINE = None
_LOCAL_ENGINE_TRIED = False


def _local_engine():
    """Lazily construct and cache the local OCR engine.

    Returns None (never raises) if the package is not installed or fails to
    initialise -- a missing optional dependency must degrade to the paid
    path, not crash the run.
    """
    global _LOCAL_ENGINE, _LOCAL_ENGINE_TRIED
    if _LOCAL_ENGINE_TRIED:
        return _LOCAL_ENGINE
    _LOCAL_ENGINE_TRIED = True
    try:
        from rapidocr_onnxruntime import RapidOCR

        _LOCAL_ENGINE = RapidOCR()
    except Exception as exc:
        print("[ocr-local] engine unavailable: " + repr(exc)[:120])
        _LOCAL_ENGINE = None
    return _LOCAL_ENGINE


def _ocr_page_image(engine, raw_rgb, height: int, width: int, channels: int) -> list:
    """Run the engine on one rasterised page, returning [(y, x, text), ...]
    sorted into reading order (top-to-bottom, then left-to-right)."""
    import numpy as np

    img = np.frombuffer(raw_rgb, dtype=np.uint8).reshape(height, width, channels)
    if channels == 4:
        img = img[:, :, :3]

    result, _ = engine(img)
    if not result:
        return []

    lines = []
    for box, text, _score in result:
        if not text or not text.strip():
            continue
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        lines.append((min(ys), min(xs), text.strip()))
    lines.sort(key=lambda t: (t[0], t[1]))
    return lines


def _rasterize_and_ocr(raw: bytes, engine, max_pages: int) -> list[str]:
    """Rasterise up to `max_pages` pages of `raw` at 200dpi and OCR each with
    `engine`. Split out from transcribe_pdf_local so tests can substitute a
    fake engine while exercising the real PyMuPDF rasterisation, or a fake
    rasteriser to isolate the floor/ordering logic from a real PDF."""
    import fitz

    page_texts = []
    with fitz.open(stream=raw, filetype="pdf") as doc:
        for i in range(max_pages):
            page = doc[i]
            pix = page.get_pixmap(dpi=200)
            lines = _ocr_page_image(
                engine, pix.samples, pix.height, pix.width, pix.n
            )
            page_texts.append("\n".join(text for _y, _x, text in lines))
    return page_texts


def transcribe_pdf_local(raw: bytes, url: str = "") -> Optional[str]:
    """Recover text from a scanned PDF using a free, local, deterministic
    OCR engine. Returns None (never raises) if the engine is unavailable,
    the document is unreadable, or the result fails the same minimum-length
    floor the paid paths enforce.
    """
    if not raw or len(raw) > _MAX_BYTES:
        return None

    pages = page_count(raw)
    if pages is None or pages == 0 or pages > _MAX_PAGES:
        return None

    engine = _local_engine()
    if engine is None:
        return None

    from .config import CONFIG

    max_pages = min(pages, getattr(CONFIG, "ocr_max_pages", 40))

    try:
        page_texts = _rasterize_and_ocr(raw, engine, max_pages)
    except Exception as exc:
        print("[ocr-local] failed for " + url[:60] + ": " + repr(exc)[:120])
        return None

    text = "\n\n".join(t for t in page_texts if t).strip()
    if not text:
        return None

    if len(text) < _MIN_CHARS_PER_PAGE * max_pages:
        print(
            "[ocr-local] rejected a suspiciously short transcription for "
            + url[:55] + " (" + str(len(text)) + " chars for "
            + str(max_pages) + " pages)"
        )
        return None

    print(
        "[ocr-local] " + url[-60:] + ": " + str(max_pages) + " pages, "
        + str(len(text)) + " chars"
    )
    return text


def _transcribe_via_gemini(raw: bytes, pages: int, url: str) -> Optional[str]:
    """Free-tier fallback. Gemini reads PDFs natively too.

    Added after the Anthropic balance ran out 25 documents into a 51-document
    batch, which stranded half the scanned oral-hearing evidence -- and that
    evidence is the only place the transport role's candidates live. A source
    that is reachable for nothing should not be abandoned because one
    provider's balance hit zero.
    """
    import json
    import urllib.request

    from .config import CONFIG, secret

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "application/pdf",
                                 "data": base64.b64encode(raw).decode("ascii")}},
                {"text": "Transcribe this document in full, following the "
                         "rules exactly. Output only the document's text."},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 16000, "temperature": 0.0},
    }
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + secret("GEMINI_API_KEY"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    cands = data.get("candidates") or []
    if not cands:
        return None
    parts = cands[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip() or None


def transcribe_pdf(raw: bytes, url: str = "") -> Optional[str]:
    """Recover text from a scanned PDF. Returns None rather than guessing.

    Never raises: an unreadable source must degrade the run, not end it.
    """
    if not raw or len(raw) > _MAX_BYTES:
        return None

    pages = page_count(raw)
    if pages is None or pages == 0 or pages > _MAX_PAGES:
        return None

    # Free and local first: zero cost, no key required, and it keeps the
    # operator's fixed $30 Anthropic balance for extraction rather than OCR.
    text = transcribe_pdf_local(raw, url)
    if text is not None:
        return text

    from .config import CONFIG

    if getattr(CONFIG, "ocr_local_only", False):
        return None

    text = _transcribe_anthropic(raw, pages, url)
    if text is None:
        # Same floor, same refusal, different provider. Tried second rather
        # than first only because it is the weaker reader of a poor scan.
        try:
            text = _transcribe_gemini_guarded(raw, pages, url)
        except Exception as exc:
            print("[ocr] gemini fallback failed for " + url[:60] + ": "
                  + repr(exc)[:110])
            return None
    return text


def _transcribe_gemini_guarded(raw: bytes, pages: int, url: str) -> Optional[str]:
    text = _transcribe_via_gemini(raw, pages, url)
    if not text:
        return None
    if len(text) < _MIN_CHARS_PER_PAGE * pages:
        print(
            "[ocr] rejected a suspiciously short gemini transcription for "
            + url[:55] + " (" + str(len(text)) + " chars for " + str(pages)
            + " pages)"
        )
        return None
    print("[ocr] recovered via gemini free tier: " + url[:80], flush=True)
    return text


def _transcribe_anthropic(raw: bytes, pages: int, url: str) -> Optional[str]:
    from .providers import _preflight_ceiling
    _preflight_ceiling("ocr transcription")
    try:
        from .providers import _anthropic_client

        client = _anthropic_client()
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=16000,
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(raw).decode("ascii"),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe this document in full, following the "
                            "rules exactly. Output only the document's text."
                        ),
                    },
                ],
            }],
        )
    except Exception as exc:
        print("[ocr] transcription failed for " + url[:70] + ": " + repr(exc)[:120])
        return None

    # Recorded against the SAME run total, and the SAME cumulative ledger, as
    # every other paid call.
    #
    # This path calls the Anthropic client directly rather than going through
    # call_role, so on the first run it spent real money entirely outside the
    # tracker -- which is exactly the defect the tracker had just been built to
    # fix, reintroduced by the next feature. A 51-document transcription batch
    # drained the account's remaining balance and the ceiling never saw a cent
    # of it. Any new paid call site has to register here or the ceiling is
    # decorative again.
    total = None
    cumulative = None
    try:
        from .config import CONFIG
        from .providers import _append_ledger, _record_spend, cost_eur, cumulative_spend_eur

        usage = getattr(resp, "usage", None)
        spent = cost_eur("claude-sonnet-5", {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        })
        total = _record_spend(spent)
        _append_ledger(CONFIG.campaign_id, "ocr", "claude-sonnet-5", spent)
        cumulative = cumulative_spend_eur()
    except Exception as exc:
        # Never fail a completed transcription over its own bookkeeping, but
        # say so -- an unrecorded call is a hole in the ceiling.
        print("[ocr] WARNING: could not record spend: " + repr(exc)[:100])
    else:
        # Deliberately OUTSIDE the try/except above: a ceiling breach must
        # propagate as CostCeilingExceeded, never be caught and logged as an
        # ordinary bookkeeping failure -- same non-negotiable shape as
        # core.providers.call_role's own two checks.
        from .providers import CostCeilingExceeded

        if total > CONFIG.max_cost_eur:
            raise CostCeilingExceeded(
                "Run cost EUR " + format(total, ".2f") + " exceeds the "
                "ceiling of EUR " + format(CONFIG.max_cost_eur, ".2f")
                + " (tripped by an OCR transcription call)."
            )
        if cumulative > CONFIG.max_cost_eur_total:
            raise CostCeilingExceeded(
                "Cumulative spend across runs EUR " + format(cumulative, ".2f")
                + " exceeds the cumulative ceiling of EUR "
                + format(CONFIG.max_cost_eur_total, ".2f")
                + " (tripped by an OCR transcription call)."
            )

    text = "".join(
        getattr(block, "text", "") for block in resp.content
        if getattr(block, "type", "") == "text"
    ).strip()

    if not text:
        return None

    # A summary is short and fluent, and short-and-fluent is the shape that
    # would pass the validator while containing sentences the scan never had.
    if len(text) < _MIN_CHARS_PER_PAGE * pages:
        print(
            "[ocr] rejected a suspiciously short transcription for " + url[:60]
            + " (" + str(len(text)) + " chars for " + str(pages) + " pages)"
        )
        return None

    return text
