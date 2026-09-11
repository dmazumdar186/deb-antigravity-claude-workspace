"""
Shortlist Check intake (deliverables/gaia_poc_check/PLAN.md).

Turns a delivered candidate list -- a CSV export, a plain text list, or an
already-parsed iterable -- into `IntakeRow` objects, then matches each row
against the already-assessed person pool in `extract.json` by normalised
full name. Pure and offline: no network call, no LLM, no stage re-run. This
is the layer `run.py --check` uses before it touches any gate.

Matching is name-only (+ an employer tiebreak). It is deliberately NOT
identity resolution (`layers/identity.py`, which clusters RawPersonRecords
from several live sources with linkedin_url/register_number as strong
signals) -- here there is exactly one signal available, the name a human
typed into a spreadsheet, checked against a pool the pipeline already built.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

# The SAME slug rule extract.py/run.py use for every person_id minted
# straight from a name string -- imported, not copied, so a row that fails
# to match anyone in the pool still gets the identical deterministic id a
# real extract run would have given that person.
from .extract import slugify_person_name

__all__ = [
    "IntakeRow", "Match", "load_names", "load_names_report", "normalise_name",
    "normalise_employer", "match_pool", "slug_for_unmatched",
]

# ---------------------------------------------------------------------------
# Post-nominals stripped by normalise_name. Small and explicit rather than a
# general "looks like letters" heuristic -- a wrong strip silently merges two
# different people's names, which is worse than leaving a rare post-nominal
# in place and failing to match.
# ---------------------------------------------------------------------------
_POST_NOMINALS = {
    "bsc", "msc", "beng", "meng", "ceng", "miei", "fiei", "mistructe",
    "mice", "phd", "pe",
}

# Code-review fix 2026-09-11 (item k): header aliases widened past the
# single spelling each originally covered, plus a first-name/last-name pair
# joined when no single name column exists. Every set holds LOWERCASED,
# already-`.strip()`ped header text (spaces, not underscores, are what a
# human-exported CSV actually uses -- "Candidate Name" -- so both spellings
# are listed rather than normalising the header itself, which would also
# have to dodge collapsing "Full Name" and "Full_Name" columns that some
# export genuinely uses as two different fields).
_NAME_HEADERS = {"name", "full_name", "full name", "candidate_name", "candidate name"}
_FIRST_NAME_HEADERS = {"first_name", "first name"}
_LAST_NAME_HEADERS = {"last_name", "last name"}
_EMPLOYER_HEADERS = {
    "employer", "company", "current_company", "current company",
    "organization", "organisation", "company_name", "company name",
}
_TITLE_HEADERS = {"title", "job_title", "job title", "current_title", "current title"}
_LINKEDIN_HEADERS = {"linkedin_url", "linkedin"}
# Which brief gates this row -- role_id, a role's own title, or the
# positional alias "role1"/"role2" -- resolved by run.py's
# `_resolve_role_alias`. Absent/unresolvable falls back to the cached
# person's own delivered role_id.
_ROLE_HEADERS = {"role", "role_id"}
# CSV-supplied contact status, used only when contact.json has no entry for
# the matched person (run.py's `_check_contact_status`). PLAN.md's own
# vocabulary (verified/catch_all/inferred/guess/none) is accepted alongside
# the pipeline's "pattern_guess".
_CONTACT_STATUS_HEADERS = {"contact_status", "email_status"}


@dataclass
class IntakeRow:
    """One row of the list a consultant handed in, before matching."""

    name: str
    employer: str = ""
    title: str = ""
    linkedin_url: str = ""
    role: str = ""
    contact_status: str = ""
    source_row: int = 0


@dataclass
class Match:
    """The result of matching one IntakeRow against the person pool.

    `how`:
      "exact"             -- one person shares the normalised full name.
      "employer_tiebreak" -- several people share the name; the row's
                              employer narrowed it to exactly one.
      "ambiguous"         -- several people share the name and the employer
                              (missing, or matching more than one) could not
                              narrow it -- person_id is None, `candidates`
                              lists every person_id that shared the name.
      "none"              -- nobody in the pool shares the normalised name.
    """

    row: IntakeRow
    person_id: Optional[str]
    person: Optional[dict]
    how: str
    candidates: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------


def _strip_accents(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _clean_tokens(text: str) -> list[str]:
    """Letters-only tokens, for testing whether a comma's tail is ALL
    post-nominals (item j below) -- deliberately not the full normalise_name
    pipeline, which would already have thrown the post-nominals away before
    this check could run."""
    return [t for t in re.sub(r"[^A-Za-z]+", " ", text).split() if t]


def normalise_name(s: Optional[str]) -> str:
    """Casefold, strip accents, drop post-nominals, fold apostrophe variants.

    'John Alcaras BSc CEng MIEI' -> 'john alcaras'
    "Michael O'Reilly" / 'Michael O’Reilly' / 'Michael OReilly' -> all
    'michael oreilly' -- the apostrophe is DELETED (not turned into a space),
    which is what makes the three spellings converge on one string.

    Code-review fix 2026-09-11 (item j): a comma's tail is dropped ONLY when
    every token in it is a post-nominal ("Kate FitzGerald, CEng MIEI" ->
    "kate fitzgerald"). A comma written the other way round -- "Smith, John"
    -- has a tail ("John") that is not a post-nominal at all, so the comma
    is treated as an ordinary word boundary and BOTH parts survive ("smith
    john"), never silently truncated to "smith" and collapsed with every
    other "Smith, <anything>" row in `_dedupe`.
    """
    if not s:
        return ""
    # Curly quotes -> straight, so the delete step below catches both.
    s = s.replace("’", "'").replace("‘", "'")
    # Post-nominals in parentheses: "(BSc CEng)".
    s = re.sub(r"\([^)]*\)", " ", s)
    if "," in s:
        head, tail = s.split(",", 1)
        tail_tokens = _clean_tokens(tail)
        if tail_tokens and all(t.lower() in _POST_NOMINALS for t in tail_tokens):
            s = head
        else:
            s = head + " " + tail
    # Hyphens as spaces, per spec -- "Anne-Marie" -> "anne marie".
    s = s.replace("-", " ")
    s = _strip_accents(s).casefold()
    # Delete apostrophes (not replace with space) so O'Reilly / O'Reilly /
    # OReilly all fold to "oreilly".
    s = s.replace("'", "")
    # Anything else non-alphanumeric becomes a space.
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    tokens = [t for t in s.split() if t and t not in _POST_NOMINALS]
    return " ".join(tokens)


def normalise_employer(s: Optional[str]) -> str:
    """Casefold + accent-fold + non-alnum-to-space, for the employer
    tiebreak in `match_pool` only. Code-review fix 2026-09-11 (item l):
    deliberately NOT `normalise_name` -- an employer name has no
    post-nominals to strip and a comma in one ("Smith, Jones & Co") is not
    a name-vs-letters boundary the way it is for a person's name, so
    running it through the name pipeline risked both a wrong strip and a
    wrong comma-tail decision for reasons that only make sense for people."""
    if not s:
        return ""
    s = _strip_accents(s).casefold()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def slug_for_unmatched(name: str) -> str:
    """Deterministic person_id for a row that matched nobody in the pool --
    the same slug rule extract.py mints person_id from (layers/extract.py::
    slugify_person_name), imported rather than re-derived. Code-review fix
    2026-09-11 (item m): this guarantees the SAME id only for a
    byte-identical spelling of the name -- it is a slug function, not a
    second identity resolver, so "Mike O'Reilly" and "Michael O'Reilly"
    slug to two different ids even though a human reading both would
    recognise the same person. A row that matched nobody in the pool gets
    a stable id for THIS row's own spelling, nothing stronger."""
    return slugify_person_name(name)


# ---------------------------------------------------------------------------
# Loading rows
# ---------------------------------------------------------------------------


def _row_from_dict(rec: dict, source_row: int) -> Optional[IntakeRow]:
    name = str(
        rec.get("name") or rec.get("full_name")
        or (str(rec.get("first_name") or "") + " " + str(rec.get("last_name") or "")).strip()
        or ""
    ).strip()
    if not name:
        return None
    return IntakeRow(
        name=name,
        employer=str(
            rec.get("employer") or rec.get("company") or rec.get("organization")
            or rec.get("organisation") or ""
        ).strip(),
        title=str(rec.get("title") or rec.get("job_title") or "").strip(),
        linkedin_url=str(rec.get("linkedin_url") or rec.get("linkedin") or "").strip(),
        role=str(rec.get("role") or rec.get("role_id") or "").strip(),
        contact_status=str(
            rec.get("contact_status") or rec.get("email_status") or ""
        ).strip(),
        source_row=source_row,
    )


def _rows_from_csv_text(text: str) -> list[IntakeRow]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    col: dict[str, str] = {}
    first_name_col: Optional[str] = None
    last_name_col: Optional[str] = None
    for raw_field in reader.fieldnames:
        # Code-review fix 2026-09-11 (item k): a trailing comma in the
        # header row gives csv.DictReader an empty-string fieldname -- never
        # a real column, and must never be used as one (rec.get("") would
        # silently read whatever OTHER blank-headed value collided there).
        if not raw_field:
            continue
        key = raw_field.strip().lower()
        if key in _NAME_HEADERS and "name" not in col:
            col["name"] = raw_field
        elif key in _FIRST_NAME_HEADERS and first_name_col is None:
            first_name_col = raw_field
        elif key in _LAST_NAME_HEADERS and last_name_col is None:
            last_name_col = raw_field
        elif key in _EMPLOYER_HEADERS and "employer" not in col:
            col["employer"] = raw_field
        elif key in _TITLE_HEADERS and "title" not in col:
            col["title"] = raw_field
        elif key in _LINKEDIN_HEADERS and "linkedin_url" not in col:
            col["linkedin_url"] = raw_field
        elif key in _ROLE_HEADERS and "role" not in col:
            col["role"] = raw_field
        elif key in _CONTACT_STATUS_HEADERS and "contact_status" not in col:
            col["contact_status"] = raw_field

    use_first_last = "name" not in col and first_name_col is not None and last_name_col is not None
    if "name" not in col and not use_first_last:
        raise ValueError(
            "CSV has no name/full_name column, and no first-name+last-name "
            "pair (headers found: " + ", ".join(f for f in reader.fieldnames if f) + ")"
        )

    rows: list[IntakeRow] = []
    for i, rec in enumerate(reader, start=2):  # header occupies row 1
        if use_first_last:
            first = (rec.get(first_name_col) or "").strip()
            last = (rec.get(last_name_col) or "").strip()
            name = (first + " " + last).strip()
        else:
            name = (rec.get(col["name"]) or "").strip()
        if not name:
            continue
        rows.append(
            IntakeRow(
                name=name,
                employer=(rec.get(col.get("employer", ""), "") or "").strip(),
                title=(rec.get(col.get("title", ""), "") or "").strip(),
                linkedin_url=(rec.get(col.get("linkedin_url", ""), "") or "").strip(),
                role=(rec.get(col.get("role", ""), "") or "").strip(),
                contact_status=(rec.get(col.get("contact_status", ""), "") or "").strip(),
                source_row=i,
            )
        )
    return rows


def _rows_from_plain_text(text: str) -> list[IntakeRow]:
    rows = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        rows.append(IntakeRow(name=line, source_row=i))
    return rows


def _rows_from_iterable(items: Iterable) -> list[IntakeRow]:
    rows = []
    for i, item in enumerate(items, start=1):
        if isinstance(item, dict):
            row = _row_from_dict(item, i)
            if row is not None:
                rows.append(row)
        elif item is not None:
            name = str(item).strip()
            if name:
                rows.append(IntakeRow(name=name, source_row=i))
    return rows


def _load_raw_rows(source: Union[str, Path, Iterable]) -> list[IntakeRow]:
    """The same dispatch load_names always did, BEFORE dedup -- factored out
    so load_names_report can report how many rows dedup actually dropped
    without re-implementing the CSV/plain-text/iterable dispatch."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".csv":
            return _rows_from_csv_text(text)
        return _rows_from_plain_text(text)
    if isinstance(source, Iterable):
        return _rows_from_iterable(source)
    raise TypeError(
        "load_names expects a CSV/text path or an iterable of "
        "strings/dicts, got " + repr(type(source))
    )


def _dedupe(rows: list[IntakeRow]) -> list[IntakeRow]:
    """Dedupe by normalised name, preserving first-seen order."""
    seen: set[str] = set()
    out: list[IntakeRow] = []
    for row in rows:
        key = normalise_name(row.name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def load_names_report(source: Union[str, Path, Iterable]) -> tuple[list[IntakeRow], int]:
    """Same loading as `load_names`, but also returns how many rows were
    dropped as a duplicate of an earlier row (by normalised name) --
    code-review fix 2026-09-11 (item e): check_results.json's summary
    records this count rather than silently absorbing it into a smaller
    `submitted` number with no explanation."""
    raw = _load_raw_rows(source)
    deduped = _dedupe(raw)
    return deduped, len(raw) - len(deduped)


def load_names(source: Union[str, Path, Iterable]) -> list[IntakeRow]:
    """Load intake rows from a CSV path, a plain-text path, or an iterable
    of strings/dicts. Strips, drops blanks, dedupes preserving order.

    CSV vs plain text is decided by extension (`.csv` -> CSV; anything else
    -> one name per line), matching how a consultant actually exports a
    list -- never sniffed, so a plain-text list that happens to contain a
    comma (a name written "Lastname, Firstname") is never misread as a CSV
    header row.
    """
    rows, _ = load_names_report(source)
    return rows


# ---------------------------------------------------------------------------
# Matching against the pool
# ---------------------------------------------------------------------------


def match_pool(rows: list[IntakeRow], persons: dict[str, dict]) -> list[Match]:
    """Exact normalised-name match; employer-substring tiebreak on a
    collision; otherwise "ambiguous" with every candidate person_id listed.

    `persons` is extract.json's `persons` dict shape: person_id -> a dict
    carrying at least `full_name` (and normally `current_employer`).
    """
    by_name: dict[str, list[str]] = {}
    for pid, rec in persons.items():
        key = normalise_name((rec or {}).get("full_name"))
        if key:
            by_name.setdefault(key, []).append(pid)

    out: list[Match] = []
    for row in rows:
        key = normalise_name(row.name)
        candidates = by_name.get(key, [])
        if not candidates:
            out.append(Match(row=row, person_id=None, person=None,
                              how="none", candidates=[]))
            continue
        if len(candidates) == 1:
            pid = candidates[0]
            out.append(Match(row=row, person_id=pid, person=persons[pid],
                              how="exact", candidates=candidates))
            continue

        row_employer = normalise_employer(row.employer)
        tiebroken: Optional[str] = None
        if row_employer:
            hits = []
            for pid in candidates:
                cand_employer = normalise_employer((persons[pid] or {}).get("current_employer"))
                if not cand_employer:
                    continue
                if row_employer in cand_employer or cand_employer in row_employer:
                    hits.append(pid)
            if len(hits) == 1:
                tiebroken = hits[0]

        if tiebroken is not None:
            out.append(Match(row=row, person_id=tiebroken, person=persons[tiebroken],
                              how="employer_tiebreak", candidates=candidates))
        else:
            out.append(Match(row=row, person_id=None, person=None,
                              how="ambiguous", candidates=sorted(candidates)))
    return out
