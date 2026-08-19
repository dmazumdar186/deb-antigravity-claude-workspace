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
is not something this pipeline should require, so recovery goes through the
Anthropic API's native PDF support, which rasterises each page and reads it.

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


def transcribe_pdf(raw: bytes, url: str = "") -> Optional[str]:
    """Recover text from a scanned PDF. Returns None rather than guessing.

    Never raises: an unreadable source must degrade the run, not end it.
    """
    if not raw or len(raw) > _MAX_BYTES:
        return None

    pages = page_count(raw)
    if pages is None or pages == 0 or pages > _MAX_PAGES:
        return None

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

    # Recorded against the SAME run total as every other paid call.
    #
    # This path calls the Anthropic client directly rather than going through
    # call_role, so on the first run it spent real money entirely outside the
    # tracker -- which is exactly the defect the tracker had just been built to
    # fix, reintroduced by the next feature. A 51-document transcription batch
    # drained the account's remaining balance and the ceiling never saw a cent
    # of it. Any new paid call site has to register here or the ceiling is
    # decorative again.
    try:
        from .providers import _record_spend, cost_eur

        usage = getattr(resp, "usage", None)
        _record_spend(cost_eur("claude-sonnet-5", {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }))
    except Exception as exc:
        # Never fail a completed transcription over its own bookkeeping, but
        # say so -- an unrecorded call is a hole in the ceiling.
        print("[ocr] WARNING: could not record spend: " + repr(exc)[:100])

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
