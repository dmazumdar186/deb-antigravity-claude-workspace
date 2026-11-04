"""Red-team gate for outward text: deterministic layer (claim grounding, pass ledger, Gmail hook).

description: Deterministic red-team gate for outward text: grounds draft claims against sources, records 4-lens passes, gates Gmail sends (fail-closed).
inputs: CLI subcommands sha|ground|record|waive|check|hook|post-hook (--draft, --sources, --verdicts, --reason, --file); hook JSON on stdin; env REDTEAM_DIR.
outputs: stdout claim table/JSON/sha12; .tmp/redteam/ground/<sha12>.json, passes.jsonl, drafts.jsonl; PreToolUse deny JSON. Exit 0 ok, 1 ungrounded, 2 usage, 3 refused/not passed.

Details
-------
Stdlib only, no network, no LLM, no secrets (so no .env is loaded). The semantic half of the gate
(four lens reviewers: counterparty, grounding, downside, reputation) is done by agents; this script
only does what can be done deterministically:

* normalise(text, is_html) -> canonical text; its sha256 identifies "this exact wording".
* ground: extracts money / percent / number+unit / date / quote claims plus overclaim words and
  checks each against source files. Lexical only: a grounded number can still be attributed to the
  wrong thing (that is the grounding lens's job; every hit line is reported for it).
* record: requires zero ungrounded claims and PASS verdicts from all four lenses stamped with the
  current DRAFT-SHA, then appends to passes.jsonl (idempotent on sha256).
* waive: operator-authorised bypass (reason must start with "operator:").
* hook / post-hook: Claude Code PreToolUse / PostToolUse handlers for the Gmail MCP tools.

Exit codes: 0 ok / allow / all grounded / passed; 1 ground found ungrounded claims;
2 usage error (missing file, bad waiver reason); 3 record refused / check not passed.

Directive: directives/infrastructure/redteam_gate.md
"""
from __future__ import annotations

import argparse
import bisect
import email
import email.policy
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

LENSES = ("counterparty", "grounding", "downside", "reputation")
SOURCE_SUFFIXES = {".md", ".txt", ".html", ".htm", ".csv", ".json", ".eml", ".yaml", ".yml"}
HTML_SUFFIXES = {".html", ".htm"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
MAX_SOURCE_BYTES = 5_000_000
MAX_SOURCE_FILES = 2000
MAX_HITS = 5
EXCERPT_CHARS = 160
REASON_EXCERPT_CHARS = 60

GATED_ACTIONS = {"send_message", "reply", "forward", "create_draft", "update_draft"}
DRAFT_WRITE_ACTIONS = {"create_draft", "update_draft"}
DENY_SUFFIX = "Run /redteam on this exact text (ground + 4 lenses + record) first."

EXIT_OK, EXIT_UNGROUNDED, EXIT_USAGE, EXIT_REFUSED = 0, 1, 2, 3


# --------------------------------------------------------------------------- state

def state_dir() -> Path:
    env = os.environ.get("REDTEAM_DIR", "").strip()
    return Path(env) if env else REPO_ROOT / ".tmp" / "redteam"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # A corrupt row never counts as a pass (fail-closed); note it and keep going.
            print(f"redteam: skipping corrupt row {path.name}:{i}", file=sys.stderr)
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def passed_shas(state: Path) -> set[str]:
    return {str(r.get("sha256")) for r in _read_jsonl(state / "passes.jsonl") if r.get("sha256")}


# --------------------------------------------------------------------------- normalisation

_QUOTE_MAP = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u00ab": '"', "\u00bb": '"',
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u2039": "'", "\u203a": "'",
})
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_HTML_SCRIPT_RE = re.compile(r"<(script|style|head)\b.*?</\1\s*>", re.I | re.S)
_HTML_BLOCK_RE = re.compile(r"<br\s*/?>|</p\s*>|</div\s*>|</li\s*>", re.I)
_HTML_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


def html_to_text(text: str) -> str:
    """Strip HTML to text, keeping block breaks as newlines."""
    text = _HTML_COMMENT_RE.sub("", text)
    text = _HTML_SCRIPT_RE.sub("", text)
    text = _HTML_BLOCK_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)
    return html.unescape(text)


def _clean(text: str, is_html: bool = False, map_quotes: bool = True) -> str:
    if is_html:
        text = html_to_text(text)
    text = unicodedata.normalize("NFC", text)
    if map_quotes:
        text = text.translate(_QUOTE_MAP)
    return _WS_RE.sub(" ", text).strip()


def normalise(text: str, is_html: bool = False) -> str:
    """Canonical form used for hashing: html->text, NFC, ASCII quotes, single spaces, case kept."""
    return _clean(text, is_html, True)


def sha_of(text: str, is_html: bool = False) -> str:
    return hashlib.sha256(normalise(text, is_html).encode("utf-8")).hexdigest()


def is_html_path(path: Path) -> bool:
    return path.suffix.lower() in HTML_SUFFIXES


# --------------------------------------------------------------------------- numbers

_NUM = (r"(?<!\w)(?<!\d[.,])(?:\d{1,3}(?:[,.\u00a0\u202f ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
        r"(?:\s?[kK](?![A-Za-z]))?(?!\d)")
_NUM_RE = re.compile(_NUM)
_SEP = r"\s*(?:-|\u2013|\u2014|to|\u00e0)\s*"
_CUR_PRE = r"(?:[\u20ac$\u00a3]|\b(?:EUR|USD|GBP)\b)"
_CUR_POST = r"(?:[\u20ac$\u00a3]|(?:EUR|USD|GBP)\b|(?i:euros?|dollars?|pounds?)\b)"
_CUR_MARK_RE = re.compile(r"[\u20ac$\u00a3]|\b(?:EUR|USD|GBP)\b|(?i:\b(?:euros?|dollars?|pounds?)\b)")
_PCT_MARK_RE = re.compile(r"%|(?i:\bper\s?cent\b|\bpercent\b|\bpour\s?cent\b)")

_MONEY_PRE_RE = re.compile(rf"{_CUR_PRE}\s?(?P<a>{_NUM})(?:{_SEP}{_CUR_PRE}?\s?(?P<b>{_NUM}))?")
_MONEY_POST_RE = re.compile(rf"(?P<a>{_NUM})(?:{_SEP}(?P<b>{_NUM}))?\s?{_CUR_POST}")
_PCT_RE = re.compile(
    rf"(?P<a>{_NUM})(?:{_SEP}(?P<b>{_NUM}))?\s?(?:%|(?i:per\s?cent|percent|pour\s?cent)\b)")

_UNIT_FAMILIES = {
    "day": ("day", "days", "jour", "jours"),
    "week": ("week", "weeks", "semaine", "semaines"),
    "month": ("month", "months", "mois"),
    "year": ("year", "years", "an", "ans"),
    "hour": ("hour", "hours", "heure", "heures"),
    "minute": ("minute", "minutes"),
    "page": ("page", "pages"),
    "user": ("user", "users"),
}
_UNIT_TO_FAMILY = {w: fam for fam, words in _UNIT_FAMILIES.items() for w in words}
_UNIT_WORDS = "|".join(sorted(_UNIT_TO_FAMILY, key=len, reverse=True))
_UNIT_RE = re.compile(
    rf"(?P<a>{_NUM})(?:{_SEP}(?P<b>{_NUM}))?\s?(?P<unit>(?i:{_UNIT_WORDS}))\b")
_UNIT_MARK_RES = {
    fam: re.compile(r"(?i)\b(?:" + "|".join(words) + r")\b") for fam, words in _UNIT_FAMILIES.items()
}


def _parse_simple(s: str) -> set[float]:
    has_c, has_d = "," in s, "." in s
    if has_c and has_d:
        dec = max(s.rfind(","), s.rfind("."))
        return {float(re.sub(r"[.,]", "", s[:dec]) + "." + s[dec + 1:])}
    sep = "," if has_c else "." if has_d else None
    if sep is None:
        return {float(s)}
    parts = s.split(sep)
    out: set[float] = set()
    if len(parts) == 2:
        out.add(float(parts[0] + "." + parts[1]))  # decimal reading ("3,5" / "1.5")
    if 1 <= len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:]):
        out.add(float("".join(parts)))  # thousands reading ("1,200" / "1.200.000")
    return out or {float(s.replace(sep, ""))}


def parse_number(raw: str) -> set[float]:
    """Candidate values for a number token. Ambiguous '1,200' -> {1200.0, 1.2}."""
    s = raw.strip()
    mult = 1.0
    m = re.search(r"\s?[kK]$", s)
    if m:
        mult, s = 1000.0, s[: m.start()]
    s = s.replace("\u00a0", " ").replace("\u202f", " ").replace(" ", "")
    try:
        cands = _parse_simple(s)
    except ValueError:
        return set()
    return {round(v * mult, 6) for v in cands}


# --------------------------------------------------------------------------- dates

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "janvier": 1, "janv": 1, "f\u00e9vrier": 2, "fevrier": 2, "f\u00e9vr": 2, "mars": 3,
    "avril": 4, "avr": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "ao\u00fbt": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "d\u00e9cembre": 12, "decembre": 12,
    "d\u00e9c": 12,
}
_MON = "(?i:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + ")"
_DATE_RES = [
    ("iso", re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")),
    ("num", re.compile(r"\b(?P<d>\d{1,2})[/.](?P<m>\d{1,2})[/.](?P<y>\d{4}|\d{2})\b")),
    ("dmy", re.compile(
        rf"\b(?P<d>[0-3]?\d)(?:st|nd|rd|th|er)?\s+(?P<mon>{_MON})\.?(?:,?\s+(?P<y>\d{{4}}))?\b")),
    ("mdy", re.compile(
        rf"\b(?P<mon>{_MON})\.?\s+(?P<d>[0-3]?\d)(?:st|nd|rd|th)?(?:,?\s+(?P<y>\d{{4}}))?\b")),
]

DateT = tuple  # (day, month, year|None)


def _date_from_match(m: re.Match) -> DateT | None:
    gd = m.groupdict()
    try:
        day = int(gd["d"])
        month = _MONTHS[gd["mon"].lower()] if gd.get("mon") else int(gd["m"])
        year = int(gd["y"]) if gd.get("y") else None
    except (KeyError, ValueError, TypeError):
        return None
    if year is not None and year < 100:
        year += 2000
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    return (day, month, year)


def find_dates(text: str) -> list[tuple[int, int, DateT]]:
    out: list[tuple[int, int, DateT]] = []
    taken: list[tuple[int, int]] = []
    for _, rx in _DATE_RES:
        for m in rx.finditer(text):
            if _overlaps(m.start(), m.end(), taken):
                continue
            d = _date_from_match(m)
            if d:
                taken.append((m.start(), m.end()))
                out.append((m.start(), m.end(), d))
    return sorted(out)


def _dates_match(a: DateT, b: DateT) -> bool:
    return a[0] == b[0] and a[1] == b[1] and (a[2] is None or b[2] is None or a[2] == b[2])


# --------------------------------------------------------------------------- overclaims / quotes

_OVERCLAIM_TERMS = [
    "guaranteed", "guarantees", "guarantee", "always", "never", "every", "all", "any", "confirms",
    "proven", r"at\s+no\s+cost", r"free\s+of\s+charge", "unlimited", r"100\s?%", "instantly",
    r"risk[-\s]free", r"mot\s+pour\s+mot", "garanties", "garantis", "garantie", "garanti",
    "toujours", "jamais", "toutes", "tous", "aucune", "aucun", r"sans\s+frais",
    "gratuites", "gratuits", "gratuite", "gratuit",
]
_OVERCLAIM_RE = re.compile(r"(?<!\w)(?:" + "|".join(_OVERCLAIM_TERMS) + r")(?!\w)", re.I)

_QUOTE_RES = [
    re.compile(r'"([^"\n]+?)"'),
    re.compile("\u201c([^\u201d]+?)\u201d"),
    re.compile("\u201e([^\u201c\u201d]+?)[\u201c\u201d]"),
    re.compile("\u00ab\\s*([^\u00bb]+?)\\s*\u00bb"),
    re.compile("\u2018([^\u2019]+?)\u2019"),
]
_ELLIPSIS_SPLIT_RE = re.compile(r"\s*(?:\[\s*(?:\.\.\.|\u2026)\s*\]|\.\.\.|\u2026)\s*")
_EDGE_PUNCT = " .,;:!?\u2026'\""


def _overlaps(s: int, e: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(s < te and ts < e for ts, te in spans)


# --------------------------------------------------------------------------- claim extraction

def extract_claims(draft_text: str, is_html: bool = False) -> list[dict]:
    """Return internal claim dicts: {text, kind, values?, family?, date?, quote?, context?}."""
    text = _clean(draft_text, is_html, map_quotes=False)
    claims: list[dict] = []
    taken: list[tuple[int, int]] = []

    for s, e, d in find_dates(text):
        taken.append((s, e))
        claims.append({"text": text[s:e], "kind": "date", "date": d, "pos": s})

    def numeric(rx: re.Pattern, kind: str) -> None:
        for m in rx.finditer(text):
            if _overlaps(m.start(), m.end(), taken):
                continue
            values = [parse_number(m.group("a"))]
            if m.group("b"):
                values.append(parse_number(m.group("b")))
            values = [v for v in values if v]
            if not values:
                continue
            taken.append((m.start(), m.end()))
            c = {"text": m.group(0).strip(), "kind": kind, "values": values, "pos": m.start()}
            if kind == "unit":
                c["family"] = _UNIT_TO_FAMILY[m.group("unit").lower()]
            claims.append(c)

    numeric(_MONEY_PRE_RE, "money")
    numeric(_MONEY_POST_RE, "money")
    numeric(_PCT_RE, "percent")
    numeric(_UNIT_RE, "unit")

    for rx in _QUOTE_RES:
        for m in rx.finditer(text):
            inner = m.group(1).strip()
            if len(inner.split()) >= 3:
                claims.append({"text": m.group(0)[:200], "kind": "quote", "quote": inner,
                               "pos": m.start()})

    for m in _OVERCLAIM_RE.finditer(text):
        ctx = text[max(0, m.start() - 40): m.end() + 40]
        claims.append({"text": m.group(0), "kind": "overclaim", "context": ctx, "pos": m.start()})

    claims.sort(key=lambda c: c["pos"])
    seen: dict[tuple[str, str], dict] = {}
    unique: list[dict] = []
    for c in claims:
        key = (c["kind"], c["text"].lower() if c["kind"] == "overclaim" else c["text"])
        if key in seen:
            seen[key]["count"] = seen[key].get("count", 1) + 1
            continue
        seen[key] = c
        unique.append(c)
    return unique


# --------------------------------------------------------------------------- sources

class SourceLine:
    __slots__ = ("no", "text", "nums", "dates")

    def __init__(self, no: int, text: str) -> None:
        self.no = no
        self.text = text
        self.nums: list[tuple[set[float], int]] = []
        for m in _NUM_RE.finditer(text):
            cands = parse_number(m.group(0))
            if cands:
                self.nums.append((cands, m.start()))
        self.dates = find_dates(text)


class Source:
    def __init__(self, path: Path, display: str, raw: bytes) -> None:
        self.path = path
        self.display = display
        self.sha256 = hashlib.sha256(raw).hexdigest()
        text = _decode_source(path, raw)
        self.lines: list[SourceLine] = []
        lowered: list[str] = []
        self.offsets: list[int] = []
        pos = 0
        for i, line in enumerate(text.splitlines(), 1):
            n = normalise(line)
            if not n:
                continue
            self.lines.append(SourceLine(i, n))
            low = n.lower()
            self.offsets.append(pos)
            lowered.append(low)
            pos += len(low) + 1
        self.full_lower = " ".join(lowered)

    def line_at(self, offset: int) -> SourceLine:
        return self.lines[max(0, bisect.bisect_right(self.offsets, offset) - 1)]


def _decode_source(path: Path, raw: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        try:
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            parts = [f"{h}: {msg[h]}" for h in ("From", "To", "Date", "Subject") if msg[h]]
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    body = part.get_content()
                    parts.append(html_to_text(body) if ctype == "text/html" else body)
            return "\n".join(parts)
        except Exception as exc:  # malformed MIME: fall back to the raw bytes as text
            print(f"redteam: .eml parse failed for {path.name} ({type(exc).__name__}); "
                  "using raw text", file=sys.stderr)
    text = raw.decode("utf-8", errors="replace")
    return html_to_text(text) if suffix in HTML_SUFFIXES else text


def _display(path: Path) -> str:
    rp = path.resolve()
    for base in (REPO_ROOT, Path.cwd()):
        try:
            return rp.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return rp.as_posix()


class UsageError(Exception):
    pass


def collect_sources(paths: list[str], draft: Path | None, state: Path
                    ) -> tuple[list[Source], list[dict]]:
    files: list[Path] = []
    for p in paths:
        P = Path(p)
        if not P.exists():
            raise UsageError(f"source not found: {p}")
        if P.is_dir():
            for root, dirs, names in os.walk(P):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                files.extend(Path(root) / n for n in sorted(names))
        else:
            files.append(P)

    draft_res = draft.resolve() if draft else None
    state_res = state.resolve()
    seen: set[Path] = set()
    sources: list[Source] = []
    skipped: list[dict] = []
    for f in files:
        rp = f.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        disp = _display(f)
        reason = None
        if draft_res is not None and rp == draft_res:
            reason = "is the draft itself"
        elif rp.is_relative_to(state_res):
            reason = "red-team state file"
        elif f.suffix.lower() not in SOURCE_SUFFIXES:
            reason = "unsupported type"
        elif rp.stat().st_size > MAX_SOURCE_BYTES:
            reason = "too large"
        elif len(sources) >= MAX_SOURCE_FILES:
            reason = "file limit reached"
        if reason:
            skipped.append({"path": disp, "reason": reason})
            continue
        sources.append(Source(f, disp, f.read_bytes()))
    return sources, skipped


# --------------------------------------------------------------------------- grounding

def _excerpt(text: str, pos: int = 0, width: int = EXCERPT_CHARS) -> str:
    if len(text) <= width:
        return text
    inner = width - 2
    start = max(0, min(pos - inner // 3, len(text) - inner))
    out = text[start: start + inner]
    return ("\u2026" if start > 0 else "") + out + ("\u2026" if start + inner < len(text) else "")


def _marker_ok(claim: dict, line: str) -> bool:
    kind = claim["kind"]
    if kind == "money":
        return bool(_CUR_MARK_RE.search(line))
    if kind == "percent":
        return bool(_PCT_MARK_RE.search(line))
    if kind == "unit":
        return bool(_UNIT_MARK_RES[claim["family"]].search(line))
    return True


def _ground_numeric(claim: dict, sources: list[Source]) -> tuple[bool, bool, list[dict]]:
    hits: list[tuple[bool, dict]] = []
    found_all, strong = True, True
    for cands in claim["values"]:
        vhits: list[tuple[bool, dict]] = []
        for src in sources:
            for ln in src.lines:
                for ncands, npos in ln.nums:
                    if ncands & cands:
                        vhits.append((_marker_ok(claim, ln.text), {
                            "source": f"{src.display}:{ln.no}",
                            "source_line": _excerpt(ln.text, npos)}))
                        break
        if not vhits:
            found_all = False
            continue
        if not any(ok for ok, _ in vhits):
            strong = False
        vhits.sort(key=lambda h: not h[0])
        hits.extend(vhits)
    out: list[dict] = []
    seen: set[str] = set()
    for _, h in sorted(hits, key=lambda h: not h[0]):
        if h["source"] not in seen:
            seen.add(h["source"])
            out.append(h)
    return found_all, found_all and not strong, out[:MAX_HITS]


def _ground_date(claim: dict, sources: list[Source]) -> list[dict]:
    hits: list[dict] = []
    for src in sources:
        for ln in src.lines:
            for s, _, d in ln.dates:
                if _dates_match(claim["date"], d):
                    hits.append({"source": f"{src.display}:{ln.no}",
                                 "source_line": _excerpt(ln.text, s)})
                    break
            if len(hits) >= MAX_HITS:
                return hits
    return hits


def _ground_quote(claim: dict, sources: list[Source]) -> list[dict]:
    needle = normalise(claim["quote"]).lower().strip(_EDGE_PUNCT)
    frags = [f.strip(_EDGE_PUNCT) for f in _ELLIPSIS_SPLIT_RE.split(needle)]
    frags = [f for f in frags if len(f) >= 2]
    if not frags:
        return []
    for src in sources:
        positions = [src.full_lower.find(f) for f in frags]
        if all(p >= 0 for p in positions):
            ln = src.line_at(positions[0])
            return [{"source": f"{src.display}:{ln.no}", "source_line": _excerpt(ln.text)}]
    return []


def ground_claims(claims: list[dict], sources: list[Source]) -> list[dict]:
    results: list[dict] = []
    for c in claims:
        kind = c["kind"]
        r: dict[str, Any] = {"text": c["text"], "kind": kind, "status": "ungrounded",
                             "weak": False, "source": None, "source_line": None}
        if kind == "overclaim":
            r["status"] = "overclaim"
            r["context"] = c["context"]
        else:
            if kind in ("money", "percent", "unit"):
                ok, weak, hits = _ground_numeric(c, sources)
                r["weak"] = weak
            elif kind == "date":
                hits = _ground_date(c, sources)
                ok = bool(hits)
            else:
                hits = _ground_quote(c, sources)
                ok = bool(hits)
            if ok and hits:
                r["status"] = "grounded"
                r["source"] = hits[0]["source"]
                r["source_line"] = hits[0]["source_line"]
            r["hits"] = hits
        if c.get("count", 1) > 1:
            r["count"] = c["count"]
        results.append(r)
    return results


def run_ground(draft: Path, source_args: list[str], state: Path) -> dict:
    if not draft.is_file():
        raise UsageError(f"draft not found: {draft}")
    text = draft.read_text(encoding="utf-8", errors="replace")
    html_flag = is_html_path(draft)
    sha = sha_of(text, html_flag)
    sources, skipped = collect_sources(source_args, draft, state)
    claims = ground_claims(extract_claims(text, html_flag), sources)
    summary = {
        "total": len(claims),
        "grounded": sum(c["status"] == "grounded" for c in claims),
        "ungrounded": sum(c["status"] == "ungrounded" for c in claims),
        "overclaims": sum(c["status"] == "overclaim" for c in claims),
        "weak": sum(bool(c["weak"]) for c in claims),
    }
    result = {
        "sha256": sha, "sha12": sha[:12], "draft": _display(draft), "ts": _now(),
        "sources": [{"path": s.display, "sha256": s.sha256} for s in sources],
        "skipped": skipped, "claims": claims, "summary": summary,
    }
    out = state / "ground" / f"{sha[:12]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _cut(s: str | None, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def print_table(result: dict) -> None:
    print(f"DRAFT-SHA: {result['sha12']}  draft: {result['draft']}  "
          f"sources: {len(result['sources'])}  skipped: {len(result['skipped'])}")
    print(f"{'STATUS':<11} {'KIND':<9} {'CLAIM':<32} SOURCE | LINE")
    for c in result["claims"]:
        status = c["status"] + ("*" if c["weak"] else "")
        where = c["source"] or (c.get("context") and f"ctx: {_cut(c['context'], 70)}") or "-"
        line = f" | {_cut(c['source_line'], 70)}" if c["source_line"] else ""
        print(f"{status:<11} {c['kind']:<9} {_cut(c['text'], 32):<32} {where}{line}")
    s = result["summary"]
    print(f"{s['total']} claims: {s['grounded']} grounded ({s['weak']} weak*), "
          f"{s['ungrounded']} UNGROUNDED, {s['overclaims']} overclaim warnings")
    for sk in result["skipped"][:10]:
        print(f"skipped: {sk['path']} ({sk['reason']})")
    print("Note: grounding is lexical. A grounded number may still be misattributed; the grounding "
          "lens must read every hit's source_line context.")


# --------------------------------------------------------------------------- verdicts / ledger

_LENS_RE = re.compile(r"(?im)^[\s>*#\-]*LENS\s*\**\s*:\s*\**\s*([A-Za-z_-]+)")
_VERDICT_RE = re.compile(r"(?im)^[\s>*#\-]*VERDICT\s*\**\s*:\s*\**\s*(PASS|FAIL)\b")
_DSHA_RE = re.compile(r"(?im)^[\s>*#\-]*DRAFT-SHA\s*\**\s*:\s*\**\s*`?([0-9a-f]{12,64})")


def parse_verdict(text: str) -> dict:
    out: dict[str, str | None] = {}
    for key, rx in (("lens", _LENS_RE), ("verdict", _VERDICT_RE), ("sha", _DSHA_RE)):
        m = rx.search(text)
        out[key] = m.group(1).lower() if m else None
    if out["verdict"]:
        out["verdict"] = out["verdict"].upper()
    return out


def cmd_sha(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"draft not found: {draft}", file=sys.stderr)
        return EXIT_USAGE
    print(sha_of(draft.read_text(encoding="utf-8", errors="replace"), is_html_path(draft))[:12])
    return EXIT_OK


def cmd_ground(args: argparse.Namespace) -> int:
    try:
        result = run_ground(Path(args.draft), args.sources, state_dir())
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_table(result)
    return EXIT_UNGROUNDED if result["summary"]["ungrounded"] else EXIT_OK


def cmd_record(args: argparse.Namespace) -> int:
    state = state_dir()
    try:
        result = run_ground(Path(args.draft), args.sources, state)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    sha12 = result["sha12"]
    reasons: list[str] = []
    ung = [c for c in result["claims"] if c["status"] == "ungrounded"]
    if ung:
        reasons.append(f"{len(ung)} ungrounded claim(s): "
                       + "; ".join(_cut(c["text"], 40) for c in ung[:8]))
    passed: set[str] = set()
    for vf in args.verdicts:
        vp = Path(vf)
        if not vp.is_file():
            reasons.append(f"verdict file not found: {vf}")
            continue
        v = parse_verdict(vp.read_text(encoding="utf-8", errors="replace"))
        missing = [k.upper() if k != "sha" else "DRAFT-SHA" for k in ("lens", "verdict", "sha")
                   if not v[k]]
        if missing:
            reasons.append(f"{vf}: missing {', '.join(missing)} line(s)")
            continue
        if v["lens"] not in LENSES:
            reasons.append(f"{vf}: unknown lens '{v['lens']}' (expected one of {', '.join(LENSES)})")
        elif v["sha"][:12] != sha12:
            reasons.append(f"{vf}: stale DRAFT-SHA {v['sha'][:12]} for lens {v['lens']} "
                           f"(current draft is {sha12}; re-run that lens on the current wording)")
        elif v["verdict"] != "PASS":
            reasons.append(f"{vf}: lens {v['lens']} verdict is {v['verdict']}")
        else:
            passed.add(v["lens"])
    missing_lenses = [lens for lens in LENSES if lens not in passed]
    if missing_lenses:
        reasons.append("no current PASS for lens(es): " + ", ".join(missing_lenses))
    if reasons:
        print(f"REFUSED {sha12} {result['draft']}")
        for r in reasons:
            print(f"- {r}")
        return EXIT_REFUSED
    passes = state / "passes.jsonl"
    if result["sha256"] in passed_shas(state):
        print(f"already recorded: {sha12} {result['draft']}")
        return EXIT_OK
    s = result["summary"]
    _append_jsonl(passes, {
        "sha256": result["sha256"], "sha12": sha12, "draft": result["draft"],
        "sources": result["sources"], "lenses": list(LENSES),
        "claims_total": s["total"], "claims_grounded": s["grounded"],
        "overclaims": s["overclaims"], "ts": _now(), "waived": False,
    })
    print(f"recorded: {sha12} {result['draft']} ({s['grounded']}/{s['total']} claims grounded, "
          f"{s['overclaims']} overclaim warnings)")
    return EXIT_OK


def cmd_waive(args: argparse.Namespace) -> int:
    reason = (args.reason or "").strip()
    if not reason.lower().startswith("operator:") or not reason.split(":", 1)[1].strip():
        print("waiver reason must start with 'operator:' and quote the operator's instruction",
              file=sys.stderr)
        return EXIT_USAGE
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"draft not found: {draft}", file=sys.stderr)
        return EXIT_USAGE
    state = state_dir()
    sha = sha_of(draft.read_text(encoding="utf-8", errors="replace"), is_html_path(draft))
    disp = _display(draft)
    if sha in passed_shas(state):
        print(f"already in ledger: {sha[:12]} {disp}")
        return EXIT_OK
    _append_jsonl(state / "passes.jsonl", {
        "sha256": sha, "sha12": sha[:12], "draft": disp, "sources": [], "lenses": [],
        "claims_total": 0, "claims_grounded": 0, "overclaims": 0, "ts": _now(),
        "waived": True, "reason": reason,
    })
    print(f"**Red-team waiver**: {sha[:12]} {disp} \u2014 {reason}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    f = Path(args.file)
    if not f.is_file():
        print(f"file not found: {f}", file=sys.stderr)
        return EXIT_USAGE
    sha = sha_of(f.read_text(encoding="utf-8", errors="replace"), is_html_path(f))
    rows = [r for r in _read_jsonl(state_dir() / "passes.jsonl") if r.get("sha256") == sha]
    if rows:
        print(f"PASSED {sha[:12]}" + (" (waived)" if rows[0].get("waived") else ""))
        return EXIT_OK
    print(f"NOT PASSED {sha[:12]}")
    return EXIT_REFUSED


# --------------------------------------------------------------------------- hooks

def gated_action(tool_name: str) -> str | None:
    if "gmail" not in tool_name.lower():
        return None
    suffix = tool_name.rsplit("__", 1)[-1]
    return suffix if suffix in GATED_ACTIONS else None


def text_fields(action: str, tool_input: dict) -> list[tuple[str, str, bool]]:
    """Non-empty outward text fields as (field, raw_text, is_html)."""
    plain = "forwardText" if action == "forward" else "body"
    out: list[tuple[str, str, bool]] = []
    for key, is_html in ((plain, False), ("htmlBody", True)):
        val = tool_input.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            val = json.dumps(val, ensure_ascii=False)
        if normalise(val, is_html):
            out.append((key, val, is_html))
    return out


def latest_draft_row(state: Path, draft_id: str) -> dict | None:
    row = None
    for r in _read_jsonl(state / "drafts.jsonl"):
        if str(r.get("draft_id")) == draft_id:
            row = r
    return row


def hook_decision(payload: dict, state: Path) -> str | None:
    """Return a deny reason, or None to allow."""
    name = payload.get("tool_name") or ""
    if not isinstance(name, str):
        raise TypeError("tool_name is not a string")
    action = gated_action(name)
    if action is None:
        return None
    ti = payload.get("tool_input")
    if ti is None:
        ti = {}
    if not isinstance(ti, dict):
        raise TypeError("tool_input is not an object")
    fields = text_fields(action, ti)
    passed = passed_shas(state)
    if not fields:
        if action in ("create_draft", "update_draft", "forward"):
            return None
        if action == "send_message" and ti.get("draftId"):
            did = str(ti["draftId"])
            row = latest_draft_row(state, did)
            if row is None:
                return (f"draft {did[:40]} has no recorded content (create/update it via the gated "
                        "Gmail draft tools so its text is hashed)")
            shas = row.get("sha256s") or [row.get("sha256")]
            bad = [s for s in shas if s not in passed]
            if bad:
                return f"draft {did[:40]} content (sha {str(bad[0])[:12]}) has not passed red-team"
            return None
        return f"{action} has no body text to vet"
    for key, raw, is_html in fields:
        norm = normalise(raw, is_html)
        sha = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if sha not in passed:
            exc = _cut(norm, REASON_EXCERPT_CHARS).replace('"', "'")
            return f'{action}.{key} (sha {sha[:12]}, "{exc}") has not passed red-team'
    return None


def _emit_deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}, separators=(",", ":")))


def _read_stdin() -> str:
    return sys.stdin.buffer.read().decode("utf-8", errors="replace")


def cmd_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(_read_stdin())
        if not isinstance(payload, dict):
            raise TypeError("hook payload is not an object")
        reason = hook_decision(payload, state_dir())
    except Exception as exc:  # fail-closed: any error denies the outward action
        _emit_deny(f"redteam gate error (fail-closed): {type(exc).__name__}")
        return EXIT_OK
    if reason:
        _emit_deny(f"redteam gate: {reason}. {DENY_SUFFIX}")
    return EXIT_OK


_ID_TEXT_RES = [
    re.compile(r'"(?:draftId|draft_id|id)"\s*:\s*"([^"]+)"'),
    re.compile(r"(?i)\bdraft[\s_-]*id\W{0,3}([A-Za-z0-9_-]{4,})"),
]


def extract_draft_id(obj: Any, depth: int = 0) -> str | None:
    if obj is None or depth > 5:
        return None
    if isinstance(obj, dict):
        for key in ("draftId", "draft_id", "id"):
            val = obj.get(key)
            if isinstance(val, (str, int)) and str(val).strip():
                return str(val).strip()
        for key in ("draft", "result", "data", "content", "structuredContent"):
            found = extract_draft_id(obj.get(key), depth + 1)
            if found:
                return found
        for val in obj.values():
            if isinstance(val, (dict, list, str)):
                found = extract_draft_id(val, depth + 1)
                if found:
                    return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = extract_draft_id(item, depth + 1)
            if found:
                return found
        return None
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in "{[":
            try:
                return extract_draft_id(json.loads(s), depth + 1)
            except json.JSONDecodeError:
                pass  # not JSON after all; fall through to the regex scan below
        for rx in _ID_TEXT_RES:
            m = rx.search(s)
            if m:
                return m.group(1)
    return None


def cmd_post_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(_read_stdin())
        if not isinstance(payload, dict):
            return EXIT_OK
        action = gated_action(str(payload.get("tool_name") or ""))
        if action not in DRAFT_WRITE_ACTIONS:
            return EXIT_OK
        ti = payload.get("tool_input") or {}
        if not isinstance(ti, dict):
            return EXIT_OK
        fields = text_fields(action, ti)
        if not fields:
            return EXIT_OK  # recipient/subject-only change: draft text unchanged
        did = str(ti.get("draftId") or "") if action == "update_draft" else ""
        did = did or extract_draft_id(payload.get("tool_response")) or ""
        if not did:
            print("redteam post-hook: no draft id in tool_response", file=sys.stderr)
            return EXIT_OK
        shas = [sha_of(raw, is_html) for _, raw, is_html in fields]
        _append_jsonl(state_dir() / "drafts.jsonl",
                      {"draft_id": did, "sha256": shas[0], "sha256s": shas, "ts": _now()})
    except Exception as exc:  # PostToolUse must never break the session; a missing row only
        # makes a later send-by-draftId deny (fail-closed), so logging is enough.
        print(f"redteam post-hook error: {type(exc).__name__}", file=sys.stderr)
    return EXIT_OK


# --------------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="redteam_gate.py",
        description="Deterministic red-team gate for outward text (directives/infrastructure/"
                    "redteam_gate.md). Exit codes: 0 ok/allow/passed, 1 ungrounded claims, "
                    "2 usage error, 3 refused/not passed. State: $REDTEAM_DIR or .tmp/redteam/.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sha", help="print the 12-hex DRAFT-SHA of a draft file")
    s.add_argument("--draft", required=True)
    s.set_defaults(func=cmd_sha)

    s = sub.add_parser("ground", help="extract claims and ground them against sources (exit 1 if "
                                      "any ungrounded)")
    s.add_argument("--draft", required=True)
    s.add_argument("--sources", nargs="+", required=True, help="files or directories")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_ground)

    s = sub.add_parser("record", help="record a pass: 0 ungrounded + PASS from all 4 lenses on the "
                                      "current DRAFT-SHA (exit 3 if refused)")
    s.add_argument("--draft", required=True)
    s.add_argument("--sources", nargs="+", required=True)
    s.add_argument("--verdicts", nargs="+", required=True)
    s.set_defaults(func=cmd_record)

    s = sub.add_parser("waive", help="operator-authorised bypass (reason must start 'operator:')")
    s.add_argument("--draft", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_waive)

    s = sub.add_parser("check", help="exit 0 if this file's text passed (or was waived), else 3")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("hook", help="PreToolUse handler for Gmail tools (stdin JSON, fail-closed)")
    s.set_defaults(func=cmd_hook)

    s = sub.add_parser("post-hook", help="PostToolUse handler: map draft id -> text sha")
    s.set_defaults(func=cmd_post_hook)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
