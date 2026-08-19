"""
L6 -- the claim validator.

SPEC.md section 7: "This is the product. Everything else is scaffolding."

Every claim emitted by the LLM in L5 carries a verbatim evidence_quote. This
module checks, deterministically, that the quote actually appears in the
cached source document. Claims that fail are DROPPED -- not flagged, not
shown with a warning. Dropped.

The drop rate is the hallucination metric. It is logged to
logs/drops.jsonl and surfaced by the run; above CONFIG.max_drop_rate the
L5 prompt is wrong and the run should be fixed before shipping.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from ..core.contracts import Claim, RawDocument, ValidatedClaim

# Characters that PDF extraction mangles and that an LLM will silently
# normalise when copying a quote. Mapped to ASCII on BOTH sides of the
# comparison so a curly apostrophe in the PDF still matches a straight one
# in the model's copy.
_PUNCT_MAP = {
    "’": "'", "‘": "'", "ʼ": "'", "´": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    "…": "...",
    " ": " ", " ": " ", " ": " ", "​": "",
    "�": "",  # the replacement char PDF extraction leaves behind
    "ﬁ": "fi", "ﬂ": "fl",
}


def normalize(s: str) -> str:
    """Normalise text for substring comparison.

    Deliberately aggressive: NFKD, punctuation folding, whitespace collapse,
    lowercase. The goal is to eliminate false NEGATIVES (a true quote failing
    to match because a PDF used a ligature) without creating false POSITIVES
    (a fabricated quote matching by accident). Collapsing whitespace and
    punctuation cannot make an invented sentence appear in a document.
    """
    s = unicodedata.normalize("NFKD", s)
    for src, dst in _PUNCT_MAP.items():
        s = s.replace(src, dst)
    # Strip combining marks left by NFKD so "Réalis" matches "Realis".
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[\s]+", " ", s)
    return s.strip().lower()


def validate_claim(claim: Claim, corpus: dict[str, RawDocument]) -> bool:
    """True iff the claim's evidence_quote is a substring of its source doc."""
    doc = corpus.get(claim.source_doc_id)
    if doc is None:
        return False
    return normalize(claim.evidence_quote) in normalize(doc.content_text)


def validate_all(
    claims: Iterable[Claim],
    corpus: dict[str, RawDocument],
    drops_log: Path | None = None,
) -> tuple[list[ValidatedClaim], dict]:
    """Validate a batch. Returns (surviving claims, stats).

    Only claims that pass are returned, and they are returned with
    quote_verified=True so that a downstream renderer cannot accidentally
    display an unverified claim.
    """
    kept: list[ValidatedClaim] = []
    dropped: list[dict] = []

    for claim in claims:
        if validate_claim(claim, corpus):
            kept.append(ValidatedClaim(**claim.model_dump(), quote_verified=True))
        else:
            doc = corpus.get(claim.source_doc_id)
            dropped.append(
                {
                    "person_id": claim.subject_person_id,
                    "dimension": claim.dimension,
                    "assertion": claim.assertion,
                    "evidence_quote": claim.evidence_quote,
                    "source_doc_id": claim.source_doc_id,
                    "source_url": str(claim.source_url),
                    "reason": "source_doc_missing" if doc is None else "quote_not_found",
                }
            )

    total = len(kept) + len(dropped)
    stats = {
        "claims_in": total,
        "claims_kept": len(kept),
        "claims_dropped": len(dropped),
        "drop_rate": (len(dropped) / total) if total else 0.0,
    }

    if drops_log is not None and dropped:
        drops_log.parent.mkdir(parents=True, exist_ok=True)
        with drops_log.open("a", encoding="utf-8") as fh:
            for d in dropped:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    return kept, stats
