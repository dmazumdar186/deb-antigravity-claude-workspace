"""
eval/labels.py -- blind human ground truth (RADAR_CONTRACTS.md section F).

A `Label` records one person's grade / residence country / chartership
status as read by a HUMAN who saw only the source text
(eval/blind_label_prompt.md), never the extractor's own verdict. Comparing
the extractor's output against these labels is the only honest way to know
whether the scorecard's grade_precision / residence_precision numbers mean
anything -- an extractor grading its own homework always looks perfect.

`grade` uses the EXACT ladder `layers.gates._GRADE_ORDER` uses (plus
"unknown", for a labeller who genuinely cannot tell) so a label and the
pipeline's own `_grade_from_title` are always comparing the same categories.
`location_country` uses the coarser, human-facing IE/NI/UK/other/unknown
split named in RADAR_CONTRACTS.md section F; `eval/scorecard.py` maps that
down to gates._location_country's ireland/northern_ireland/outside_ireland/
unknown bucket before comparing (see the mapping there for why).

Labels persist in `eval/labels.jsonl`, append-only, one JSON object per
line. This is a human-authored answer key, not per-run stage output, so it
lives beside the eval code rather than under run/<campaign_id>/ -- the
per-run artifact is the WORKSHEET a labeller reads from
(`run.py --label-export` writes run/<campaign_id>/label_export.jsonl), not
the answers they hand back. Two labellers labelling the same subset is what
makes `cohen_kappa` meaningful.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field

from ..layers.gates import _GRADE_ORDER

# The exact ladder gates._GRADE_ORDER uses, plus "unknown" for a labeller who
# cannot tell from the source text. gates._grade_from_title itself returns
# None in that case (rendered "unknown" throughout this module) -- neither
# side of the comparison ever guesses.
GRADE_VALUES: tuple[str, ...] = tuple(_GRADE_ORDER) + ("unknown",)

# A tuple subscript on Literal is equivalent to Literal[*values] -- Python's
# `obj[a, b, c]` and `obj[(a, b, c)]` both call __class_getitem__((a, b, c)).
# Building it from GRADE_VALUES (rather than retyping the ladder here) is
# the point: this module and gates.py can never drift apart on what a
# "grade" is.
Grade = Literal[GRADE_VALUES]  # type: ignore[valid-type]

LOCATION_VALUES: tuple[str, ...] = ("IE", "NI", "UK", "other", "unknown")
LocationCountry = Literal[LOCATION_VALUES]  # type: ignore[valid-type]

CHARTERED_VALUES: tuple[str, ...] = ("yes", "no", "unknown")
Chartered = Literal[CHARTERED_VALUES]  # type: ignore[valid-type]

PKG_DIR = Path(__file__).resolve().parent
LABELS_PATH = PKG_DIR / "labels.jsonl"

_WRITE_LOCK = threading.Lock()


class Label(BaseModel):
    person_id: str
    grade: Grade
    location_country: LocationCountry
    chartered: Chartered
    labeller: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""  # the verbatim deciding line(s); see blind_label_prompt.md


def append_label(label: Label, path: Path = LABELS_PATH) -> None:
    """Append one label. Never overwrites -- two labellers append to the
    same file (or their own files, then get compared via cohen_kappa)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(label.model_dump_json() + "\n")


def load_labels(path: Path = LABELS_PATH) -> list[Label]:
    """Every well-formed label in `path`. Missing file -> no labels (n/a),
    not an error -- labelling is a manual QA pass, not every run has one."""
    if not path.exists():
        return []
    out: list[Label] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(Label(**json.loads(line)))
        except Exception:
            # A malformed line must not take down the whole scorecard; it is
            # simply not counted as a label. Nothing here can silently
            # fabricate ground truth, so skipping is safe.
            continue
    return out


def labels_by_person(labels: Sequence[Label]) -> dict[str, list[Label]]:
    out: dict[str, list[Label]] = {}
    for lbl in labels:
        out.setdefault(lbl.person_id, []).append(lbl)
    return out


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Cohen's kappa between two raters' aligned categorical judgements.

    Pure Python per RADAR_CONTRACTS.md section F ("cohen_kappa(...)
    implemented in pure Python") -- no numpy/sklearn for one small formula.
    `a` and `b` must already be aligned item-for-item (same person, same
    field); see `kappa_for_field` for that alignment step.
    """
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("cohen_kappa needs two equal-length, non-empty sequences")

    categories = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n

    count_a: dict[str, int] = {c: 0 for c in categories}
    count_b: dict[str, int] = {c: 0 for c in categories}
    for x in a:
        count_a[x] += 1
    for y in b:
        count_b[y] += 1
    pe = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)

    if pe >= 1.0:
        # Both raters used exactly one category, the same one, for every
        # item -- agreement is total but the formula's denominator is zero.
        # Reporting 1.0 (rather than raising) matches the intuition: they
        # agreed on everything, even though a single-category subset proves
        # nothing about reliability on a harder one.
        return 1.0
    return (po - pe) / (1 - pe)


def kappa_for_field(
    labels_a: Sequence[Label], labels_b: Sequence[Label], field: str
) -> tuple[float, int]:
    """Align two labellers' label sets on person_id, then score one field.

    Returns (kappa, n_common). Raises ValueError on zero overlap -- that is
    a setup mistake (wrong files, wrong campaign), not a meaningful 0.0.
    """
    by_a = {lbl.person_id: lbl for lbl in labels_a}
    by_b = {lbl.person_id: lbl for lbl in labels_b}
    common = sorted(set(by_a) & set(by_b))
    if not common:
        raise ValueError("no person_id is labelled in both files")
    a_vals = [getattr(by_a[pid], field) for pid in common]
    b_vals = [getattr(by_b[pid], field) for pid in common]
    return cohen_kappa(a_vals, b_vals), len(common)


def build_worksheet_row(person_id: str, full_name: str, docs: list[dict]) -> dict:
    """One row of the blind labelling worksheet (`run.py --label-export`).

    Carries source text only -- no dimension, no assertion, no tier, no
    extractor grade/chartered/location verdict -- per blind_label_prompt.md's
    contract that the labeller sees ONLY source text. `excerpt` is capped at
    4000 chars: long enough that a witness statement's identifying
    paragraphs are almost always in view, short enough that a worksheet of a
    few hundred people stays megabytes, not the whole corpus.
    """
    return {
        "person_id": person_id,
        "full_name": full_name,
        "source_excerpts": [
            {
                "doc_id": d.get("doc_id"),
                "source_url": str(d.get("url", "")),
                "text_source": d.get("text_source", "text_layer"),
                "excerpt": (d.get("content_text") or "")[:4000],
            }
            for d in docs
        ],
    }
