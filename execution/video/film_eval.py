"""Deterministic evaluation harness for short AI-made explainer films.

description: Scores a rendered explainer film against its captions, script and fact sheet.
             Technical: container (duration, resolution, fps, codecs, bitrate, size, audio),
             loudness (ebur128: integrated LUFS, true peak, LRA), black / frozen / silent
             stretches, sha256. Content: number fidelity (SRT + SCRIPT vs FACTS), fact-tag
             coverage, quote fidelity, PII scan, caption readability (CPS, duration, line
             length, lines per cue, gaps/overlaps), narration speech rate. Optional AI
             metrics: --asr (faster-whisper WER + audible fact numbers) and --jev (one Jev
             decide_many batch: supported / clarity / claim type per narration line).
             Directive: directives/video/film_eval.md
inputs: --video MP4, --srt SRT, --script SCRIPT.md, --facts FACTS.md (all required);
        optional --asr [--asr-model small --asr-lang en --asr-python /tmp/ext/venv/bin/python],
        --jev, --deny FILE (one name per line), --deny-names "Camille,Roux" (CLI default),
        --hold 5, --max-mb 25, --lufs-target -16, --expect-sha256 HEX, --out JSON, --md MD.
        env OPENROUTER_API_KEY (only for --jev).
outputs: JSON report (--out) and markdown report (--md); a summary table on stdout.
         --jev appends one row to .tmp/jev_ledger.jsonl (caller "film_eval").
         Exit 0 = PASS or WARN, 1 = any FAIL, 2 = usage / missing input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import itertools
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it
    pass

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

VERSION = "1.0.0"
PASS, WARN, FAIL, SKIPPED = "PASS", "WARN", "FAIL", "SKIPPED"
DEFAULT_DENY_NAMES = "Camille,Roux"
DEFAULT_ASR_PYTHON = "/tmp/ext/venv/bin/python"

# Every threshold in one place, so the report can quote it and the directive can document it.
T: dict[str, Any] = {
    "max_mb": 25.0,               # file size, 1 MB = 1,000,000 bytes
    "min_w": 1280, "min_h": 720,
    "fps_lo": 23.9, "fps_hi": 60.0,
    "max_kbps": 8000,
    "lufs_target": -16.0, "lufs_pass_tol": 2.0, "lufs_warn_tol": 4.0,
    "tp_pass": -1.0, "tp_warn": 0.0,
    "lra_warn": 15.0,
    "head_ignore": 1.0,           # black at the very start (fade-in) is ignored up to this point
    "hold": 5.0,                  # final hold excluded from black / freeze / silence checks
    "black_warn": 0.5, "black_fail": 2.0,
    "freeze_warn": 4.0, "freeze_fail": 10.0,
    "silence_warn": 3.0, "silence_fail": 6.0,
    "cps_warn": 17.0, "cps_fail": 21.0,
    "cue_min": 1.0, "cue_max": 7.0,
    "line_max": 42, "lines_max": 2,
    "min_gap": 0.083,             # gaps shorter than ~2 frames flicker
    "wpm_lo": 130.0, "wpm_hi": 170.0, "wpm_margin": 15.0,
    "tag_cov_warn": 0.8,
    "wer_pass": 0.05, "wer_warn": 0.10,
    "jev_flag": 0.5, "jev_mean_pass": 0.8,
    "quote_similar": 0.6,
}


@dataclass
class Metric:
    group: str
    name: str
    value: Any
    threshold: str
    verdict: str
    unit: str = ""
    detail: list[str] = field(default_factory=list)
    note: str = ""


# =========================================================================================
# Text helpers
# =========================================================================================

QUOTE_MAP = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2033": '"', "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
})
DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
_SEP_THOUSANDS = ",\u00a0\u202f\u2009"


def norm_quotes(s: str) -> str:
    return s.translate(QUOTE_MAP)


def collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u00a0", " ").replace("\u202f", " ")).strip()


# ---- fact ids --------------------------------------------------------------------------

TAG_RE = re.compile(rf"(?<![A-Za-z0-9])F0*(\d{{1,3}})(?:\s*[{DASHES}]\s*F?0*(\d{{1,3}}))?(?![A-Za-z0-9])")
TAG_GROUP_RE = re.compile(
    rf"[\[(]\s*F\d{{1,3}}(?:\s*(?:[,;/&{DASHES}]|and)\s*F?\d{{1,3}})*\s*[\])]", re.IGNORECASE)


def fid(n: int | str) -> str:
    return f"F{int(n):02d}"


def extract_tags(line: str) -> list[str]:
    """All fact ids on a line: [F07], (F07, F08), F07-F09 ranges, bare F7. Order kept, deduped."""
    out: list[str] = []
    for m in TAG_RE.finditer(line):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        lo, hi = (a, b) if a <= b and b - a <= 50 else (a, a)
        for n in range(lo, hi + 1):
            if fid(n) not in out:
                out.append(fid(n))
    return out


def strip_tags(line: str) -> str:
    line = TAG_GROUP_RE.sub(" ", line)
    return TAG_RE.sub(" ", line)


# ---- numbers ---------------------------------------------------------------------------

_NUM = r"\d{1,3}(?:[,\u00a0\u202f\u2009]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?"
_ID = r"[A-Z]{1,3}\d{2,}"
_TOK = rf"(?:{_ID}|{_NUM})"
NUMBER_RE = re.compile(
    rf"(?<![\w.])(?P<a>{_TOK})(?:\s*[{DASHES}]\s*(?P<b>{_TOK}))?"
    rf"(?P<pct>\s?(?:%|percent\b|per\s+cent\b))?(?![\w])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Num:
    raw: str
    canon: str        # "49", "3.5", "68%", "M0501", "M0501-M0525", "25-30"
    parts: tuple[str, ...]  # canonical endpoints (one for a single value)


def _canon_one(tok: str) -> str:
    if re.fullmatch(_ID, tok):
        return tok.upper()
    t = tok
    for sep in "\u00a0\u202f\u2009":
        t = t.replace(sep, "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")  # decimal comma
    try:
        d = Decimal(t)
    except InvalidOperation:
        return tok
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def extract_numbers(text: str) -> list[Num]:
    """Every number in `text`: integers, decimals, percentages, ranges, record ids (M0501)."""
    out: list[Num] = []
    for m in NUMBER_RE.finditer(text):
        # an id token must keep its case-sensitive shape (M0501), not "m0501" inside a word
        a, b = m.group("a"), m.group("b")
        if re.fullmatch(_ID, a, re.IGNORECASE) and not re.fullmatch(_ID, a):
            continue
        pct = "%" if m.group("pct") else ""
        ca = _canon_one(a) + pct
        if b:
            cb = _canon_one(b) + pct
            out.append(Num(m.group(0).strip(), f"{ca}-{cb}", (ca, cb)))
        else:
            out.append(Num(m.group(0).strip(), ca, (ca,)))
    return out


_UNITS = (r"s|sec|secs|seconds?|ms|min|mins|minutes?|fps|px|wpm|kbps|mbps|mb|kb|gb|"
          r"k|p|lufs|db|dbtp|dbfs|lu|hz|khz|x|frames?|f")
STRUCTURAL_PATTERNS = [
    re.compile(r"`[^`]*`"),                                            # inline code / file names
    re.compile(r"https?://\S+"),
    re.compile(r"\]\([^)]*\)"),                                        # markdown link targets
    re.compile(r"#[0-9a-fA-F]{3,8}\b"),                                # hex colours
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?\b"),            # dates
    re.compile(rf"\b\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:[.,]\d{{1,3}})?"
               rf"(?:\s*(?:[{DASHES}]|-->|to)\s*\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:[.,]\d{{1,3}})?)?"),
    re.compile(r"\b(?:scene|shot|beat|slide|act|part|step|frame|cue|take|section|chapter|page|"
               r"segment|version|v)\s*#?\s*\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(rf"(?<![\w.])\d+(?:[.,]\d+)?(?:\s*[{DASHES}]\s*\d+(?:[.,]\d+)?)?\s?(?:{_UNITS})\b",
               re.IGNORECASE),
    re.compile(r"^\s*(?:[-*+>]\s+)*\d+[.)]\s+"),                       # ordered-list markers
]


def strip_structural(line: str) -> str:
    """Remove numbers that are script structure, not film content (timecodes, scene numbers,
    durations, units, list markers, dates, fact tags)."""
    line = strip_tags(line)
    for pat in STRUCTURAL_PATTERNS:
        line = pat.sub(" ", line)
    return line


# =========================================================================================
# FACTS.md
# =========================================================================================

@dataclass
class Fact:
    id: str
    fact: str
    value: str
    source: str
    numbers: list[Num] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)


def split_row(line: str) -> list[str]:
    s = line.strip().removeprefix("|")
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = re.split(r"(?<!\\)\|", s)
    return [c.replace("\\|", "|").strip() for c in cells]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c) \
        and any(cells)


QUOTE_RE = re.compile(r'"([^"\n]{2,}?)"')


def extract_quotes(text: str) -> list[str]:
    return [collapse_ws(q) for q in QUOTE_RE.findall(norm_quotes(text)) if q.strip()]


def parse_facts(text: str) -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    cols = {"id": 0, "fact": 1, "value": 2, "source": 3}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = split_row(line)
        if is_separator_row(cells):
            continue
        low = [c.lower() for c in cells]
        if "id" in low and any("value" in c for c in low):
            for key in cols:
                for i, c in enumerate(low):
                    if c == key or (key != "id" and key in c):
                        cols[key] = i
                        break
            continue
        if len(cells) <= max(cols["id"], cols["value"]):
            continue
        m = re.fullmatch(r"F0*(\d{1,3})", cells[cols["id"]], re.IGNORECASE)
        if not m:
            continue
        f = Fact(
            id=fid(m.group(1)),
            fact=cells[cols["fact"]] if len(cells) > cols["fact"] else "",
            value=cells[cols["value"]],
            source=cells[cols["source"]] if len(cells) > cols["source"] else "",
        )
        f.numbers = extract_numbers(strip_tags(f.fact)) + extract_numbers(strip_tags(f.value))
        f.quotes = extract_quotes(f.value)
        facts[f.id] = f
    return facts


class FactIndex:
    def __init__(self, facts: dict[str, Fact]):
        self.facts = facts
        self.by_canon: dict[str, set[str]] = {}
        self.id_ranges: list[tuple[str, int, int, int, str]] = []  # prefix, width, lo, hi, fid
        for f in facts.values():
            for n in f.numbers:
                self.by_canon.setdefault(n.canon, set()).add(f.id)
                for p in n.parts:
                    self.by_canon.setdefault(p, set()).add(f.id)
                if len(n.parts) == 2:
                    ma = re.fullmatch(r"([A-Z]+)(\d+)", n.parts[0])
                    mb = re.fullmatch(r"([A-Z]+)(\d+)", n.parts[1])
                    if ma and mb and ma.group(1) == mb.group(1):
                        self.id_ranges.append((ma.group(1), len(ma.group(2)), int(ma.group(2)),
                                               int(mb.group(2)), f.id))

    def match(self, n: Num) -> list[str]:
        """Fact ids whose numbers contain `n` (exact canon, range endpoints, or id inside an id range)."""
        if n.canon in self.by_canon:
            return sorted(self.by_canon[n.canon])
        if len(n.parts) == 2:
            a, b = (self._match_one(p) for p in n.parts)
            return sorted(set(a) | set(b)) if a and b else []
        return self._match_one(n.canon)

    def _match_one(self, canon: str) -> list[str]:
        if canon in self.by_canon:
            return sorted(self.by_canon[canon])
        m = re.fullmatch(r"([A-Z]+)(\d+)", canon)
        if m:
            hits = [r[4] for r in self.id_ranges
                    if r[0] == m.group(1) and r[1] == len(m.group(2)) and r[2] <= int(m.group(2)) <= r[3]]
            return sorted(set(hits))
        return []


def fact_sheet_text(facts: dict[str, Fact]) -> str:
    return "\n".join(f"{f.id} | {f.fact} | {f.value}" for f in facts.values())


# =========================================================================================
# SCRIPT.md
# =========================================================================================

@dataclass
class ScriptLine:
    lineno: int
    kind: str          # heading | prose | table
    raw: str
    content: str       # text used for number extraction (structural numbers removed)


_STRUCT_COL_RE = re.compile(r"^(#|no\.?|n°|nr|num(ber)?|scene|shot|beat|time|timecode|tc|start|end|"
                            r"in|out|dur(ation)?|length|frames?|id|ids|facts?( ids?)?|tags?|sources?)$",
                            re.IGNORECASE)
_NARR_COL_RE = re.compile(r"\b(vo|v\.o\.|voice[- ]?over|voiceover|voice|narration|narrator|spoken|audio)\b",
                          re.IGNORECASE)
_NARR_HEAD_RE = re.compile(r"\b(narration|voice[- ]?over|voiceover|vo|script)\b", re.IGNORECASE)
NARR_LABEL_RE = re.compile(
    r"^\s*(?:[-*+>]\s+)*[*_]{0,2}\s*(?:vo|v\.o\.|voice[- ]?over|voiceover|narration|narrator|voice)\b"
    r"\s*(?:\([^)]*\))?\s*[*_]{0,2}\s*[:\uff1a]\s*[*_]{0,2}\s*(?P<body>.+)$",
    re.IGNORECASE,
)
ANY_LABEL_RE = re.compile(r"^\s*(?:[-*+>]\s+)*[*_]{0,2}[A-Za-z][A-Za-z ./-]{0,24}[*_]{0,2}\s*[:\uff1a]")


def parse_script(text: str) -> list[ScriptLine]:
    """Content lines of SCRIPT.md (code fences, HTML comments, front matter, table headers skipped)."""
    lines = text.splitlines()
    out: list[ScriptLine] = []
    in_code = in_comment = False
    drop_cols: set[int] = set()
    in_table = False
    i = 0
    if lines and lines[0].strip() == "---":   # YAML front matter
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        lineno = i + 1
        i += 1
        if s.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        if not s:
            in_table = False
            continue
        if s.startswith("|"):
            cells = split_row(s)
            if is_separator_row(cells):
                continue
            nxt = split_row(lines[i]) if i < len(lines) and lines[i].strip().startswith("|") else []
            if not in_table and nxt and is_separator_row(nxt):
                drop_cols = {k for k, c in enumerate(cells) if _STRUCT_COL_RE.match(c.strip("*_ "))}
                in_table = True
                continue
            in_table = True
            kept = " | ".join(c for k, c in enumerate(cells) if k not in drop_cols)
            out.append(ScriptLine(lineno, "table", raw, strip_structural(kept)))
            continue
        in_table = False
        if s.startswith("#"):
            out.append(ScriptLine(lineno, "heading", raw, strip_structural(s.lstrip("#"))))
            continue
        out.append(ScriptLine(lineno, "prose", raw, strip_structural(s)))
    return out


def clean_spoken(text: str) -> str:
    """Narration text as it should be spoken: no tags, stage directions or markdown."""
    t = strip_tags(text)
    t = re.sub(r"\[[^\]]*\]", " ", t)                      # [beat], [pause]
    t = re.sub(r"[*_]\([^)]*\)[*_]", " ", t)               # *(pause)*
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)          # links
    t = re.sub(r"[*_`]+", "", t)
    t = collapse_ws(t)
    nq = norm_quotes(t)
    if len(nq) >= 2 and nq[0] == '"' and nq[-1] == '"' and nq.count('"') == 2:
        t = t[1:-1].strip()
    return t


def extract_narration(text: str) -> tuple[list[tuple[int, str]], str]:
    """Narration lines (lineno, spoken text) and the detection mode used."""
    lines = text.splitlines()
    # 1. labelled lines (VO: / Narration: / **Narrator:**), with continuation lines
    labelled: list[tuple[int, str]] = []
    k = 0
    while k < len(lines):
        m = NARR_LABEL_RE.match(lines[k])
        if not m:
            k += 1
            continue
        body = [m.group("body")]
        start = k + 1
        k += 1
        while k < len(lines):
            s = lines[k].strip()
            if not s or s.startswith(("#", "|")) or ANY_LABEL_RE.match(s):
                break
            body.append(s)
            k += 1
        spoken = clean_spoken(" ".join(body))
        if spoken:
            labelled.append((start, spoken))
    if labelled:
        return labelled, "labelled"
    # 2. table with a narration column
    tab: list[tuple[int, str]] = []
    col = None
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s.startswith("|"):
            col = None
            continue
        cells = split_row(s)
        if is_separator_row(cells):
            continue
        if col is None:
            for ci, c in enumerate(cells):
                if _NARR_COL_RE.search(c):
                    col = ci
                    break
            if col is None:
                col = -1
            continue
        if col >= 0 and col < len(cells):
            spoken = clean_spoken(cells[col])
            if spoken and spoken not in {"-", "\u2014"}:
                tab.append((n, spoken))
    if tab:
        return tab, "table_column"
    # 3. prose under a "Narration" / "Voice-over" / "Script" heading
    sec: list[tuple[int, str]] = []
    level = 0
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        hm = re.match(r"^(#+)\s*(.*)$", s)
        if hm:
            if level and len(hm.group(1)) <= level:
                level = 0
            if not level and _NARR_HEAD_RE.search(hm.group(2)):
                level = len(hm.group(1))
            continue
        if level and s and not s.startswith("|") and not s.startswith("```"):
            spoken = clean_spoken(s.lstrip(">-*+ "))
            if spoken:
                sec.append((n, spoken))
    if sec:
        return sec, "narration_section"
    # 4. blockquotes
    bq = [(n, clean_spoken(r.strip()[1:])) for n, r in enumerate(lines, 1) if r.strip().startswith(">")]
    bq = [(n, t) for n, t in bq if t]
    if bq:
        return bq, "blockquote"
    # 5. every prose line
    prose = [(sl.lineno, clean_spoken(sl.raw.strip().lstrip("-*+ "))) for sl in parse_script(text)
             if sl.kind == "prose"]
    return [(n, t) for n, t in prose if t], "all_prose"


# =========================================================================================
# SRT
# =========================================================================================

@dataclass
class Cue:
    index: int
    start: float
    end: float
    lines: list[str]

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    @property
    def duration(self) -> float:
        return self.end - self.start


_TS = r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
TIMING_RE = re.compile(rf"{_TS}\s*-->\s*{_TS}")


def _ts(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def strip_caption_markup(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\{\\[^}]*\}", "", s)
    return s.strip()


def parse_srt(text: str) -> list[Cue]:
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        rows = block.split("\n")
        for k, row in enumerate(rows):
            m = TIMING_RE.search(row)
            if not m:
                continue
            g = m.groups()
            idx = len(cues) + 1
            if k > 0 and rows[k - 1].strip().isdigit():
                idx = int(rows[k - 1].strip())
            body = [strip_caption_markup(r) for r in rows[k + 1:]]
            cues.append(Cue(idx, _ts(*g[:4]), _ts(*g[4:]), [b for b in body if b]))
            break
    return cues


def cue_cps(cue: Cue) -> float:
    """Characters per second: every visible character incl. spaces, line breaks not counted."""
    chars = sum(len(line) for line in cue.lines)
    return chars / cue.duration if cue.duration > 0 else float("inf")


# =========================================================================================
# WER normalisation (numbers <-> words both ways via one canonical spoken form)
# =========================================================================================

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")]
NUMBER_WORDS = set(_ONES) | set(_TENS[2:]) | {"hundred", "thousand", "million", "billion", "trillion"}


def int_to_words(n: int) -> str:
    if n < 0:
        return "minus " + int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return _ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + int_to_words(rest))
    for value, name in _SCALES:
        if n >= value:
            rest = n % value
            return int_to_words(n // value) + " " + name + ("" if rest == 0 else " " + int_to_words(rest))
    return str(n)


def number_to_words(tok: str) -> str:
    if "." in tok:
        whole, frac = tok.split(".", 1)
        return number_to_words(whole) + " point " + " ".join(_ONES[int(c)] for c in frac if c.isdigit())
    if len(tok) > 1 and tok.startswith("0"):
        return " ".join(_ONES[int(c)] for c in tok)       # record ids: 0501 -> zero five zero one
    return int_to_words(int(tok))


def normalize_for_wer(text: str) -> list[str]:
    """Lowercase, straight quotes, no punctuation; digits and number words map to one spoken form
    ("49", "forty-nine" and "forty nine" all become ["forty", "nine"])."""
    t = strip_tags(norm_quotes(text)).lower()
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)                          # 1,000 -> 1000
    t = re.sub(r"(?<=\d)[\u00a0\u202f\u2009](?=\d{3}\b)", "", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)                              # 3,5 -> 3.5
    t = re.sub(r"\s*%", " percent ", t)
    t = re.sub(r"\bper\s+cent\b", "percent", t)
    t = re.sub(rf"(?<=[\w%])\s*[{DASHES[1:]}]\s*(?=[a-z]?\d)", " to ", t)    # en dash ranges
    t = re.sub(r"(?<=\d)\s*-\s*(?=[a-z]?\d)", " to ", t)                     # 25-30
    t = t.replace("&", " and ")
    t = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", t)           # m0501 -> m 0501
    t = re.sub(r"\d+(?:\.\d+)?", lambda m: " " + number_to_words(m.group(0)) + " ", t)
    t = re.sub(rf"[{DASHES}]", " ", t)
    t = t.replace("'", "")
    t = re.sub(r"[^\w\s]", " ", t)
    toks = t.split()
    out: list[str] = []
    for k, w in enumerate(toks):
        if w == "and" and out and out[-1] in NUMBER_WORDS and k + 1 < len(toks) and toks[k + 1] in NUMBER_WORDS:
            continue   # "one hundred and twelve" == "one hundred twelve"
        out.append(w)
    return out


def word_error_rate(ref: list[str], hyp: list[str]) -> tuple[float, int, int]:
    """(WER, edits, reference length) by token-level Levenshtein distance."""
    if not ref:
        return (0.0 if not hyp else 1.0), len(hyp), 0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref), prev[-1], len(ref)


def contains_seq(hay: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return n > 0 and any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


# =========================================================================================
# PII
# =========================================================================================

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w+])(?:\+|00)?\d(?:[ ().\-\u00a0]{0,2}\d){7,16}(?![\w])")


def _mask(s: str) -> str:
    return s[0] + "***" + s[-1] if len(s) > 2 else "***"


def pii_scan(sources: list[tuple[str, int, str]], deny_names: list[str]) -> list[str]:
    """Hits as 'where: kind masked-match'. sources: (label, lineno, text)."""
    hits: list[str] = []
    name_res = [(n, re.compile(rf"(?<!\w){re.escape(n)}(?!\w)", re.IGNORECASE)) for n in deny_names if n]
    for label, lineno, text in sources:
        where = f"{label}:{lineno}"
        for m in EMAIL_RE.finditer(text):
            hits.append(f"{where}: email {_mask(m.group(0))}")
        for m in PHONE_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 9 <= len(digits) <= 15:
                hits.append(f"{where}: phone {_mask(digits)}")
        for name, rx in name_res:
            if rx.search(text):
                hits.append(f"{where}: denied name '{name}'")
    return hits


def load_deny(names_csv: str, deny_file: Path | None) -> list[str]:
    names = [n.strip() for n in names_csv.split(",") if n.strip()]
    if deny_file:
        for line in deny_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and s not in names:
                names.append(s)
    return names


# =========================================================================================
# ffprobe / ffmpeg
# =========================================================================================

def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, check=False)


def tool_version(binary: str) -> str:
    if not shutil.which(binary):
        return "not found"
    try:
        r = run([binary, "-version"], timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"error: {exc}"
    first = (r.stdout or r.stderr).splitlines()
    return first[0] if first else "unknown"


def ffprobe(video: Path) -> dict[str, Any]:
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)],
            timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def ffmpeg_scan(video: Path, has_audio: bool, duration: float) -> dict[str, Any]:
    """One decode pass: blackdetect + freezedetect on video, ebur128 + silencedetect on audio."""
    graph = f"[0:v:0]blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-60dB:d={T['freeze_warn']}[v]"
    maps = ["-map", "[v]"]
    if has_audio:
        graph += f";[0:a:0]ebur128=peak=true:framelog=verbose,silencedetect=n=-50dB:d={T['silence_warn']}[a]"
        maps += ["-map", "[a]"]
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info", "-i", str(video),
             "-filter_complex", graph, *maps, "-f", "null", "-"])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg analysis failed: {r.stderr.strip()[-400:]}")
    log = r.stderr
    out: dict[str, Any] = {"black": [], "freeze": [], "silence": [], "loudness": {}}
    for m in re.finditer(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)", log):
        out["black"].append((float(m.group(1)), float(m.group(2))))
    out["freeze"] = _pair_events(log, r"freeze_start:\s*([\d.]+)", r"freeze_end:\s*([\d.]+)", duration)
    out["silence"] = _pair_events(log, r"silence_start:\s*(-?[\d.]+)", r"silence_end:\s*([\d.]+)", duration)
    summary = log[log.rfind("Summary:"):] if "Summary:" in log else ""
    for key, pat in (("integrated", r"I:\s*(-?[\d.]+|-inf)\s*LUFS"), ("lra", r"LRA:\s*(-?[\d.]+)\s*LU\b"),
                     ("true_peak", r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS")):
        m = re.search(pat, summary)
        if m:
            out["loudness"][key] = float("-inf") if m.group(1) == "-inf" else float(m.group(1))
    return out


def _pair_events(log: str, start_pat: str, end_pat: str, duration: float) -> list[tuple[float, float]]:
    events: list[tuple[str, float]] = []
    for m in re.finditer(start_pat, log):
        events.append(("s", max(0.0, float(m.group(1)))))
    for m in re.finditer(end_pat, log):
        events.append(("e", float(m.group(1))))
    # log order is chronological per filter; pair each start with the next end
    starts = [v for k, v in events if k == "s"]
    ends = [v for k, v in events if k == "e"]
    pairs = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        pairs.append((s, e))
    return pairs


def _outside(span: tuple[float, float], lo: float, hi: float) -> float:
    """Seconds of `span` inside the evaluated window [lo, hi]."""
    return max(0.0, min(span[1], hi) - max(span[0], lo))


# =========================================================================================
# Metric builders
# =========================================================================================

def _v3(value: float, pass_ok: bool, warn_ok: bool) -> str:
    return PASS if pass_ok else (WARN if warn_ok else FAIL)


def technical_metrics(video: Path, srt_end: float, expect_sha: str | None) -> tuple[list[Metric], dict[str, Any]]:
    M: list[Metric] = []
    info: dict[str, Any] = {}
    g = "technical"
    size = video.stat().st_size
    sha = hashlib.sha256()
    with video.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    info["sha256"] = sha.hexdigest()
    info["size_bytes"] = size
    mb = size / 1_000_000
    M.append(Metric(g, "file_size", round(mb, 2), f"<= {T['max_mb']} MB", PASS if mb <= T["max_mb"] else FAIL, "MB"))
    if expect_sha:
        ok = expect_sha.lower() == info["sha256"]
        M.append(Metric(g, "encode_determinism", info["sha256"][:16], f"sha256 == {expect_sha[:16]}...",
                        PASS if ok else FAIL, detail=[] if ok else [f"actual {info['sha256']}"]))
    if not (shutil.which("ffprobe") and shutil.which("ffmpeg")):
        M.append(Metric(g, "container", None, "-", SKIPPED, note="ffprobe/ffmpeg not on PATH"))
        return M, info
    try:
        probe = ffprobe(video)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        M.append(Metric(g, "container", None, "readable by ffprobe", FAIL, note=str(exc)))
        return M, info
    streams = probe.get("streams", [])
    fmt = probe.get("format", {})
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    info["has_audio"] = a is not None
    duration = float(fmt.get("duration") or (v or {}).get("duration") or 0.0)
    info["duration"] = duration
    dur_ok = duration > 0 and srt_end <= duration + 0.5
    M.append(Metric(g, "duration", round(duration, 3), ">= last caption end",
                    PASS if dur_ok else (FAIL if duration <= 0 else WARN), "s",
                    [] if dur_ok or duration <= 0 else [f"last cue ends {srt_end:.2f}s, video {duration:.2f}s"]))
    if v is None:
        M.append(Metric(g, "video_stream", None, "present", FAIL))
    else:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        M.append(Metric(g, "resolution", f"{w}x{h}", f">= {T['min_w']}x{T['min_h']}",
                        PASS if w >= T["min_w"] and h >= T["min_h"] else WARN))
        num, _, den = str(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0.0
        info["fps"] = fps
        M.append(Metric(g, "fps", round(fps, 3), f"{T['fps_lo']}-{T['fps_hi']}",
                        PASS if T["fps_lo"] <= fps <= T["fps_hi"] else WARN))
        vc, pix = v.get("codec_name", "?"), v.get("pix_fmt", "?")
        M.append(Metric(g, "video_codec", f"{vc}/{pix}", "h264/yuv420p (web-safe)",
                        PASS if vc == "h264" and pix == "yuv420p" else WARN))
    M.append(Metric(g, "audio_present", a is not None, "audio stream present", PASS if a else FAIL))
    if a is not None:
        ac = a.get("codec_name", "?")
        M.append(Metric(g, "audio_codec", f"{ac} {a.get('sample_rate', '?')} Hz {a.get('channels', '?')}ch",
                        "aac", PASS if ac == "aac" else WARN))
    kbps = float(fmt.get("bit_rate") or 0) / 1000
    M.append(Metric(g, "bitrate", round(kbps), f"<= {T['max_kbps']} kbps", PASS if kbps <= T["max_kbps"] else WARN,
                    "kbps"))
    try:
        scan = ffmpeg_scan(video, a is not None, duration)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        M.append(Metric(g, "ffmpeg_scan", None, "-", FAIL, note=str(exc)))
        return M, info
    # loudness
    L = scan["loudness"]
    if a is None:
        M.append(Metric(g, "loudness_integrated", None, "-", SKIPPED, note="no audio stream"))
    elif "integrated" not in L:
        M.append(Metric(g, "loudness_integrated", None, "-", SKIPPED, note="ebur128 summary not found"))
    else:
        tgt = T["lufs_target"]
        i = L["integrated"]
        off = abs(i - tgt) if i != float("-inf") else 99.0
        M.append(Metric(g, "loudness_integrated", i, f"{tgt} +/-{T['lufs_pass_tol']} LUFS (WARN +/-{T['lufs_warn_tol']})",
                        _v3(i, off <= T["lufs_pass_tol"], off <= T["lufs_warn_tol"]), "LUFS"))
        tp = L.get("true_peak", float("-inf"))
        M.append(Metric(g, "true_peak", tp, f"<= {T['tp_pass']} dBTP (WARN <= {T['tp_warn']})",
                        _v3(tp, tp <= T["tp_pass"], tp <= T["tp_warn"]), "dBTP"))
        lra = L.get("lra", 0.0)
        M.append(Metric(g, "loudness_range", lra, f"<= {T['lra_warn']} LU", PASS if lra <= T["lra_warn"] else WARN, "LU"))
    # black / freeze / silence, measured inside [head, duration - hold]
    hi = max(0.0, duration - T["hold"])
    black = [(s, e, _outside((s, e), T["head_ignore"], hi)) for s, e in scan["black"]]
    worst = max((x[2] for x in black), default=0.0)
    M.append(Metric(g, "black_frames", round(worst, 2),
                    f"longest black < {T['black_warn']}s (FAIL >= {T['black_fail']}s), first {T['head_ignore']}s "
                    f"and final {T['hold']}s ignored",
                    PASS if worst < T["black_warn"] else (WARN if worst < T["black_fail"] else FAIL), "s",
                    [f"black {s:.2f}-{e:.2f}s ({o:.2f}s in body)" for s, e, o in black]))
    frz = [(s, e, _outside((s, e), 0.0, hi)) for s, e in scan["freeze"]]
    worst = max((x[2] for x in frz), default=0.0)
    M.append(Metric(g, "frozen_frames", round(worst, 2),
                    f"longest freeze <= {T['freeze_warn']}s outside final {T['hold']}s (FAIL > {T['freeze_fail']}s)",
                    PASS if worst <= T["freeze_warn"] else (WARN if worst <= T["freeze_fail"] else FAIL), "s",
                    [f"freeze {s:.2f}-{e:.2f}s ({o:.2f}s outside hold)" for s, e, o in frz]))
    if a is None:
        M.append(Metric(g, "silence", None, "-", SKIPPED, note="no audio stream"))
    else:
        sil = [(s, e, _outside((s, e), 0.0, hi)) for s, e in scan["silence"]]
        worst = max((x[2] for x in sil), default=0.0)
        M.append(Metric(g, "silence", round(worst, 2),
                        f"longest silence <= {T['silence_warn']}s outside final {T['hold']}s (FAIL > {T['silence_fail']}s)",
                        PASS if worst <= T["silence_warn"] else (WARN if worst <= T["silence_fail"] else FAIL), "s",
                        [f"silence {s:.2f}-{e:.2f}s ({o:.2f}s outside hold)" for s, e, o in sil]))
    return M, info


def number_fidelity(label: str, items: list[tuple[int, str]], index: FactIndex) -> tuple[Metric, list[tuple[int, Num, list[str]]]]:
    found: list[tuple[int, Num, list[str]]] = []
    for lineno, text in items:
        for n in extract_numbers(text):
            found.append((lineno, n, index.match(n)))
    bad = [(ln, n) for ln, n, hits in found if not hits]
    detail = [f"{label}:{ln}: '{n.raw}' not in FACTS -> {_line_preview(items, ln)}" for ln, n in bad]
    value = f"{len(found) - len(bad)}/{len(found)} matched"
    return Metric("content", f"number_fidelity_{label.lower().split('.')[0]}", value,
                  "every number matches a FACTS value", FAIL if bad else PASS, detail=detail), found


def _line_preview(items: list[tuple[int, str]], lineno: int) -> str:
    for ln, t in items:
        if ln == lineno:
            return collapse_ws(t)[:120]
    return ""


def tag_metrics(lines: list[ScriptLine], facts: dict[str, Fact], index: FactIndex) -> list[Metric]:
    M: list[Metric] = []
    invalid: list[str] = []
    numeric = covered = 0
    uncovered: list[str] = []
    mismatched: list[str] = []
    for sl in lines:
        tags = extract_tags(sl.raw)
        for t in tags:
            if t not in facts:
                invalid.append(f"SCRIPT.md:{sl.lineno}: unknown fact id {t}")
        if sl.kind == "heading":
            continue
        nums = extract_numbers(sl.content)
        if not nums:
            continue
        numeric += 1
        valid = [t for t in tags if t in facts]
        if valid:
            covered += 1
            for n in nums:
                hits = index.match(n)
                if hits and not set(hits) & set(valid):
                    mismatched.append(f"SCRIPT.md:{sl.lineno}: '{n.raw}' is in {','.join(hits)}, "
                                      f"line tagged {','.join(valid)}")
        else:
            why = "only unknown ids" if tags else "no fact id"
            uncovered.append(f"SCRIPT.md:{sl.lineno}: {why} -> {collapse_ws(sl.raw)[:100]}")
    share = covered / numeric if numeric else 1.0
    M.append(Metric("content", "tag_coverage", f"{covered}/{numeric} ({share:.0%})",
                    f"100% of numeric lines tagged (WARN >= {T['tag_cov_warn']:.0%})",
                    _v3(share, share >= 1.0, share >= T["tag_cov_warn"]), detail=uncovered))
    M.append(Metric("content", "tag_validity", f"{len(invalid)} unknown ids", "every tagged id exists in FACTS",
                    FAIL if invalid else PASS, detail=invalid))
    M.append(Metric("content", "tag_consistency", f"{len(mismatched)} mismatches",
                    "each number on a tagged line belongs to one of its tagged facts",
                    WARN if mismatched else PASS, detail=mismatched))
    return M


def quote_fidelity(sources: list[tuple[str, int, str]], facts: dict[str, Fact]) -> Metric:
    cands: list[tuple[str, str]] = []
    for f in facts.values():
        for q in f.quotes:
            cands.append((f.id, q))
        plain = collapse_ws(norm_quotes(f.value))
        if plain and not f.quotes:
            cands.append((f.id, plain))
    exact = 0
    bad: list[str] = []
    warn: list[str] = []
    unattributed: list[str] = []
    total = 0

    def core(s: str) -> str:
        return collapse_ws(s).rstrip(" .,;:!?\u2026")

    for label, lineno, text in sources:
        for q in extract_quotes(text):
            total += 1
            cq = core(q)
            status, best = "none", (0.0, "", "")
            for fid_, fq in cands:
                cf = core(fq)
                if cq == cf or (len(cq) >= 12 and re.search(rf"(?<!\w){re.escape(cq)}(?!\w)", cf)):
                    status = "exact"
                    break
                if cq.lower() == cf.lower():
                    status, best = "case", (1.0, fid_, fq)
                    continue
                ratio = difflib.SequenceMatcher(None, cq.lower(), cf.lower()).ratio()
                if ratio > best[0]:
                    best = (ratio, fid_, fq)
            where = f"{label}:{lineno}"
            if status == "exact":
                exact += 1
            elif status == "case":
                warn.append(f"{where}: case differs from {best[1]}: \"{q}\" vs \"{best[2]}\"")
            elif best[0] >= T["quote_similar"]:
                bad.append(f"{where}: misquote of {best[1]} ({best[0]:.0%} similar): \"{q}\" vs \"{best[2]}\"")
            else:
                unattributed.append(f"{where}: quote not in FACTS: \"{q[:80]}\"")
    verdict = FAIL if bad else (WARN if warn or unattributed else PASS)
    return Metric("content", "quote_fidelity", f"{exact}/{total} exact", "quotes match FACTS exactly "
                  "(smart/straight quotes ignored); unattributed quotes WARN", verdict,
                  detail=bad + warn + unattributed)


def caption_metrics(cues: list[Cue], duration: float | None) -> list[Metric]:
    g = "captions"
    if not cues:
        return [Metric(g, "captions_parsed", 0, ">= 1 cue", FAIL, note="no cues parsed from SRT")]
    M: list[Metric] = []
    cps = [(c, cue_cps(c)) for c in cues]
    worst = max(x[1] for x in cps)
    M.append(Metric(g, "caption_cps", round(worst, 1), f"max CPS <= {T['cps_warn']:.0f} (FAIL > {T['cps_fail']:.0f})",
                    _v3(worst, worst <= T["cps_warn"], worst <= T["cps_fail"]), "cps",
                    [f"cue {c.index} ({c.start:.2f}s): {v:.1f} cps \"{c.text[:60]}\"" for c, v in cps
                     if v > T["cps_warn"]]))
    durs = [c for c in cues if not (T["cue_min"] <= c.duration <= T["cue_max"])]
    M.append(Metric(g, "caption_duration",
                    f"{min(c.duration for c in cues):.2f}-{max(c.duration for c in cues):.2f}",
                    f"{T['cue_min']}-{T['cue_max']} s per cue", WARN if durs else PASS, "s",
                    [f"cue {c.index}: {c.duration:.2f}s" for c in durs]))
    longest = max((len(line) for c in cues for line in c.lines), default=0)
    M.append(Metric(g, "caption_line_length", longest, f"<= {T['line_max']} chars per line",
                    PASS if longest <= T["line_max"] else WARN, "chars",
                    [f"cue {c.index}: {len(line)} chars \"{line[:60]}\"" for c in cues for line in c.lines
                     if len(line) > T["line_max"]]))
    most = max(len(c.lines) for c in cues)
    M.append(Metric(g, "caption_lines_per_cue", most, f"<= {T['lines_max']}",
                    PASS if most <= T["lines_max"] else FAIL, "lines",
                    [f"cue {c.index}: {len(c.lines)} lines" for c in cues if len(c.lines) > T["lines_max"]]))
    overlaps, flicker, broken = [], [], []
    gaps = []
    for c in cues:
        if c.end <= c.start:
            broken.append(f"cue {c.index}: end {c.end:.3f}s <= start {c.start:.3f}s")
    for a, b in itertools.pairwise(cues):
        gap = b.start - a.end
        gaps.append(gap)
        if gap < -0.0005:
            overlaps.append(f"cue {a.index}->{b.index}: overlap {-gap:.3f}s")
        elif 0.0005 < gap < T["min_gap"]:
            flicker.append(f"cue {a.index}->{b.index}: gap {gap:.3f}s (< {T['min_gap']}s flickers)")
    past = [f"cue {c.index} ends {c.end:.2f}s after video end {duration:.2f}s" for c in cues
            if duration and c.end > duration + 0.05]
    verdict = FAIL if overlaps or broken else (WARN if flicker or past else PASS)
    M.append(Metric(g, "caption_timing", f"{len(overlaps)} overlaps, {len(flicker)} flicker gaps, "
                    f"max gap {max(gaps, default=0.0):.2f}s",
                    f"no overlaps; gaps 0 or >= {T['min_gap']}s; cues inside the video", verdict,
                    detail=broken + overlaps + flicker + past))
    return M


def speech_rate(narration: list[tuple[int, str]], mode: str, duration: float | None) -> Metric:
    words = sum(len([w for w in t.split() if re.search(r"\w", w)]) for _, t in narration)
    thr = f"{T['wpm_lo']:.0f}-{T['wpm_hi']:.0f} wpm (WARN +/-{T['wpm_margin']:.0f})"
    if not duration:
        return Metric("content", "speech_rate", None, thr, SKIPPED, note="video duration unknown")
    if not words:
        return Metric("content", "speech_rate", None, thr, SKIPPED, note="no narration found in SCRIPT.md")
    wpm = words / (duration / 60.0)
    ok = T["wpm_lo"] <= wpm <= T["wpm_hi"]
    near = T["wpm_lo"] - T["wpm_margin"] <= wpm <= T["wpm_hi"] + T["wpm_margin"]
    return Metric("content", "speech_rate", round(wpm, 1), thr, _v3(wpm, ok, near), "wpm",
                  note=f"{words} narration words / {duration:.1f}s; narration detected via '{mode}'")


# =========================================================================================
# AI metrics
# =========================================================================================

_ASR_CODE = r"""
import json, sys
import faster_whisper
from faster_whisper import WhisperModel
path, name, lang = sys.argv[1], sys.argv[2], (sys.argv[3] or None)
model = WhisperModel(name, device="cpu", compute_type="int8")
segs, info = model.transcribe(path, language=lang, beam_size=5, temperature=0.0,
                              condition_on_previous_text=False)
out = {"language": info.language, "version": getattr(faster_whisper, "__version__", ""),
       "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in segs]}
print(json.dumps(out))
"""


def transcribe(video: Path, model: str, lang: str, asr_python: str) -> tuple[dict[str, Any] | None, str]:
    """(result, how) or (None, reason). Tries in-process faster_whisper, then the external venv."""
    try:
        import faster_whisper  # noqa: F401
        interpreters = [sys.executable]
    except ImportError:
        interpreters = []
    if asr_python and Path(asr_python).exists():
        try:
            chk = run([asr_python, "-I", "-c", "import faster_whisper"], timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            chk = None
            print(f"asr venv check failed: {exc}", file=sys.stderr)
        if chk is not None and chk.returncode == 0:
            interpreters.append(asr_python)
    if not interpreters:
        return None, (f"faster_whisper not importable in {sys.executable} or {asr_python or '(no venv)'}")
    reasons = []
    for py in interpreters:
        try:
            r = run([py, "-I", "-c", _ASR_CODE, str(video), model, lang or ""], timeout=3600)
        except (OSError, subprocess.SubprocessError) as exc:
            reasons.append(f"{py}: {exc}")
            continue
        if r.returncode != 0:
            tail = [ln for ln in r.stderr.strip().splitlines() if ln.strip()]
            reasons.append(f"{py}: {tail[-1][:300] if tail else 'exit ' + str(r.returncode)}")
            continue
        try:
            data = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            reasons.append(f"{py}: bad output ({exc})")
            continue
        return data, py
    return None, "; ".join(reasons)


def asr_metrics(video: Path, narration: list[tuple[int, str]], args: argparse.Namespace,
                versions: dict[str, str], has_audio: bool = True) -> tuple[list[Metric], str]:
    if not has_audio:
        data, how = None, "no audio stream"
    else:
        data, how = transcribe(video, args.asr_model, args.asr_lang, args.asr_python)
    if data is None:
        return [Metric("ai", "asr_wer", None, f"<= {T['wer_pass']:.0%} (WARN <= {T['wer_warn']:.0%})", SKIPPED,
                       note=how),
                Metric("ai", "asr_fact_numbers_audible", None, "every narrated number heard", SKIPPED, note=how)], ""
    versions["faster_whisper"] = f"{data.get('version', '?')} ({how}, model {args.asr_model})"
    hyp_text = " ".join(s["text"] for s in data.get("segments", []))
    ref_text = " ".join(t for _, t in narration)
    ref, hyp = normalize_for_wer(ref_text), normalize_for_wer(hyp_text)
    wer, edits, n = word_error_rate(ref, hyp)
    M = [Metric("ai", "asr_wer", round(wer * 100, 2), f"<= {T['wer_pass']:.0%} (WARN <= {T['wer_warn']:.0%})",
                _v3(wer, wer <= T["wer_pass"], wer <= T["wer_warn"]), "%",
                note=f"{edits} edits over {n} reference words; language {data.get('language')}")]
    missing = []
    total = 0
    for ln, text in narration:
        for num in extract_numbers(text):
            total += 1
            if not contains_seq(hyp, normalize_for_wer(num.raw)):
                missing.append(f"SCRIPT.md:{ln}: '{num.raw}' not heard")
    M.append(Metric("ai", "asr_fact_numbers_audible", f"{total - len(missing)}/{total}", "every narrated number heard",
                    WARN if missing else PASS, detail=missing))
    return M, hyp_text


JEV_QUESTIONS_DOC = "supported (noul), clarity (score), claim_type (choice)"


def jev_metrics(narration: list[tuple[int, str]], facts: dict[str, Fact], versions: dict[str, str]) -> list[Metric]:
    thr = f"mean supported >= {T['jev_mean_pass']}, no fact line < {T['jev_flag']} (advisory: max WARN)"
    try:
        from execution.modules import jev_client as jev
    except ImportError as exc:
        return [Metric("ai", "jev_supported", None, thr, SKIPPED, note=f"jev_client import failed: {exc}")]
    if not jev.available():
        return [Metric("ai", "jev_supported", None, thr, SKIPPED, note="no OpenRouter key")]
    if not narration:
        return [Metric("ai", "jev_supported", None, thr, SKIPPED, note="no narration lines")]
    levels = ["confusing", "ok", "clear"]
    questions = {
        "supported": jev.noul(
            "Is every claim in `line` fully supported by `fact_sheet`?",
            "every number, quote and factual claim in the line appears in or follows directly from the fact sheet",
            "the line states a number, quote or claim the fact sheet does not contain, or contradicts it"),
        "clarity": jev.score("How clear is this narration line for a first-time viewer of a short explainer film?",
                             levels),
        "claim_type": jev.choice("What kind of statement is this narration line?", {
            "fact": "states a number or verifiable fact from the case",
            "interpretation": "draws a conclusion or insight from the facts",
            "call_to_action": "asks the viewer to act, or pitches the product",
            "none": "transition, greeting, or no claim at all",
        }),
    }
    sheet = fact_sheet_text(facts)
    states = [{"fact_sheet": sheet, "line": t} for _, t in narration]
    try:
        results = jev.decide_many(states, questions, workers=8)
    except Exception as exc:  # noqa: BLE001 -- Jev must fail open; the error is reported, not swallowed
        return [Metric("ai", "jev_supported", None, thr, SKIPPED, note=f"Jev error: {exc}")]
    ok = [(ln, t, r) for (ln, t), r in zip(narration, results) if r.ok]
    errors = [r.error for r in results if not r.ok]
    cost = sum(r.cost_usd for r in results)
    jev.append_ledger({"caller": "film_eval", "items": len(states), "ok": len(ok),
                       "cost_usd": cost, "input_tokens": sum(r.input_tokens for r in results)},
                      path=_ROOT / ".tmp" / "jev_ledger.jsonl")
    if not ok:
        return [Metric("ai", "jev_supported", None, thr, SKIPPED, note=f"Jev error: {errors[0] if errors else '?'}")]
    versions["jev_model"] = ok[0][2].model or jev.JEV_MODEL
    sup = [r.noul("supported") for _, _, r in ok]
    mean = sum(sup) / len(sup)
    dist = {lv: 0 for lv in levels}
    types: dict[str, int] = {}
    flagged = []
    for ln, t, r in ok:
        lv = levels[max(0, min(len(levels) - 1, round(r.score("clarity"))))]
        dist[lv] += 1
        ct = r.choice("claim_type") or "?"
        types[ct] = types.get(ct, 0) + 1
        if r.noul("supported") < T["jev_flag"]:
            flagged.append(f"SCRIPT.md:{ln}: supported {r.noul('supported'):.2f} [{ct}] {t[:90]}")
    fact_flags = [f for f in flagged if "[fact]" in f or "[interpretation]" in f]
    verdict = PASS if mean >= T["jev_mean_pass"] and not fact_flags else WARN
    note = f"cost ${cost:.6f}; {len(ok)}/{len(states)} lines answered"
    if errors:
        note += f"; {len(errors)} errors (first: {errors[0][:120]})"
    return [
        Metric("ai", "jev_supported", round(mean, 3), thr, verdict, "mean noul", flagged, note),
        Metric("ai", "jev_clarity", ", ".join(f"{k} {v}" for k, v in dist.items()), "advisory",
               WARN if dist["confusing"] else PASS),
        Metric("ai", "jev_claim_types", ", ".join(f"{k} {v}" for k, v in sorted(types.items())), "advisory", PASS),
    ]


# =========================================================================================
# Report
# =========================================================================================

def overall(metrics: list[Metric]) -> str:
    vs = {m.verdict for m in metrics}
    return FAIL if FAIL in vs else (WARN if WARN in vs else PASS)


def _fmt(v: Any, unit: str) -> str:
    if v is None:
        return "-"
    s = f"{v}" if not isinstance(v, float) else f"{v:g}"
    return f"{s} {unit}".strip() if unit and not unit.startswith("mean") else s


def render_md(report: dict[str, Any], metrics: list[Metric]) -> str:
    out = [f"# Film evaluation: {Path(report['inputs']['video']['path']).name}", "",
           (f"**Overall: {report['overall']}** · run {report['run_timestamp']} · "
            f"sha256 `{report['inputs']['video'].get('sha256', '?')[:16]}`"), "",
           "| Group | Metric | Value | Threshold | Verdict |", "|---|---|---|---|---|"]
    for m in metrics:
        thr = m.threshold.replace("|", "/")
        val = _fmt(m.value, m.unit).replace("|", "/")
        out.append(f"| {m.group} | {m.name} | {val} | {thr} | **{m.verdict}** |")
    findings = [m for m in metrics if m.verdict in (FAIL, WARN) and (m.detail or m.note)]
    if findings:
        out += ["", "## Findings"]
        for m in findings:
            out += ["", f"### {m.verdict} · {m.name}"]
            if m.note:
                out.append(f"_{m.note}_")
            out += [f"- {d}" for d in m.detail[:25]]
            if len(m.detail) > 25:
                out.append(f"- ... {len(m.detail) - 25} more in the JSON report")
    skipped = [m for m in metrics if m.verdict == SKIPPED]
    if skipped:
        out += ["", "## Skipped"] + [f"- {m.name}: {m.note}" for m in skipped]
    notes = [m for m in metrics if m.verdict == PASS and m.note]
    if notes:
        out += ["", "## Notes"] + [f"- {m.name}: {m.note}" for m in notes]
    out += ["", "## Tool versions"] + [f"- {k}: {v}" for k, v in report["tool_versions"].items()]
    return "\n".join(out) + "\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], list[Metric]]:
    if args.hold is not None:
        T["hold"] = args.hold
    if args.max_mb is not None:
        T["max_mb"] = args.max_mb
    if args.lufs_target is not None:
        T["lufs_target"] = args.lufs_target
    video, srt_p, script_p, facts_p = (Path(p) for p in (args.video, args.srt, args.script, args.facts))
    facts = parse_facts(facts_p.read_text(encoding="utf-8"))
    index = FactIndex(facts)
    script_text = script_p.read_text(encoding="utf-8")
    cues = parse_srt(srt_p.read_text(encoding="utf-8", errors="replace"))
    srt_end = max((c.end for c in cues), default=0.0)
    versions = {"film_eval": VERSION, "python": platform.python_version(),
                "ffmpeg": tool_version("ffmpeg"), "ffprobe": tool_version("ffprobe")}

    metrics: list[Metric] = []
    tech, vinfo = technical_metrics(video, srt_end, args.expect_sha256)
    metrics += tech
    duration = vinfo.get("duration")

    lines = parse_script(script_text)
    narration, mode = extract_narration(script_text)
    if not facts:
        metrics.append(Metric("content", "facts_parsed", 0, ">= 1 fact row", FAIL, note=f"no fact rows in {facts_p}"))
    srt_items = [(c.index, c.text) for c in cues]
    m_srt, _ = number_fidelity("SRT", srt_items, index)
    m_scr, _ = number_fidelity("SCRIPT.md", [(sl.lineno, sl.content) for sl in lines if sl.kind != "heading"], index)
    metrics += [m_srt, m_scr]
    metrics += tag_metrics(lines, facts, index)
    narr_by_line = dict(narration)
    quote_src = [("SCRIPT.md", sl.lineno, narr_by_line.get(sl.lineno, sl.raw)) for sl in lines] + \
                [("SRT", c.index, c.text) for c in cues]
    metrics.append(quote_fidelity(quote_src, facts))
    deny = load_deny(args.deny_names, Path(args.deny) if args.deny else None)
    pii_src = [("SRT", c.index, c.text) for c in cues] + [("SCRIPT.md", sl.lineno, sl.raw) for sl in lines]

    metrics += caption_metrics(cues, duration)
    metrics.append(speech_rate(narration, mode, duration))

    transcript = ""
    if args.asr:
        asr_m, transcript = asr_metrics(video, narration, args, versions, bool(vinfo.get("has_audio", True)))
        metrics += asr_m
    if transcript:
        pii_src.append(("ASR", 0, transcript))
    hits = pii_scan(pii_src, deny)
    metrics.append(Metric("content", "pii_scan", f"{len(hits)} hits",
                          f"no e-mail, phone or denied name ({', '.join(deny)})", FAIL if hits else PASS,
                          detail=hits))
    if args.jev:
        metrics += jev_metrics(narration, facts, versions)
    order = {"technical": 0, "content": 1, "captions": 2, "ai": 3}
    metrics.sort(key=lambda m: order.get(m.group, 9))   # stable: keeps order within a group

    report = {
        "tool": "film_eval", "version": VERSION,
        "run_timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall": overall(metrics),
        "inputs": {
            "video": {"path": str(video.resolve()), **vinfo},
            "srt": {"path": str(srt_p.resolve()), "sha256": _sha(srt_p), "cues": len(cues)},
            "script": {"path": str(script_p.resolve()), "sha256": _sha(script_p),
                       "narration_lines": len(narration), "narration_mode": mode},
            "facts": {"path": str(facts_p.resolve()), "sha256": _sha(facts_p), "facts": len(facts)},
        },
        "thresholds": dict(T),
        "tool_versions": versions,
        "metrics": [asdict(m) for m in metrics],
    }
    if transcript:
        report["asr_transcript"] = transcript
    return report, metrics


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic evaluation of a short explainer film.")
    p.add_argument("--video", required=True)
    p.add_argument("--srt", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--facts", required=True)
    p.add_argument("--asr", action="store_true", help="faster-whisper WER vs narration (SKIPPED if unavailable)")
    p.add_argument("--asr-model", default="small")
    p.add_argument("--asr-lang", default="en", help="language code; empty string = auto-detect")
    p.add_argument("--asr-python", default=DEFAULT_ASR_PYTHON, help="fallback interpreter with faster_whisper")
    p.add_argument("--jev", action="store_true", help="Jev support/clarity/claim-type per narration line")
    p.add_argument("--deny", help="file with one denied name per line (added to --deny-names)")
    p.add_argument("--deny-names", default=DEFAULT_DENY_NAMES, help="comma-separated denied names")
    p.add_argument("--hold", type=float, default=None, help=f"final hold seconds (default {T['hold']})")
    p.add_argument("--max-mb", type=float, default=None, help=f"max file size MB (default {T['max_mb']})")
    p.add_argument("--lufs-target", type=float, default=None, help=f"integrated target (default {T['lufs_target']})")
    p.add_argument("--expect-sha256", help="FAIL unless the video's sha256 equals this (re-render determinism)")
    p.add_argument("--out", help="JSON report path")
    p.add_argument("--md", help="markdown report path")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    missing = [f"--{k} {getattr(args, k)}" for k in ("video", "srt", "script", "facts")
               if not Path(getattr(args, k)).is_file()]
    if args.deny and not Path(args.deny).is_file():
        missing.append(f"--deny {args.deny}")
    if missing:
        print("film_eval: missing input file(s): " + ", ".join(missing), file=sys.stderr)
        return 2
    try:
        report, metrics = evaluate(args)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"film_eval: cannot read inputs: {exc}", file=sys.stderr)
        return 2
    md = render_md(report, metrics)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                                  encoding="utf-8")
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md, encoding="utf-8")
    width = max(len(m.name) for m in metrics)
    for m in metrics:
        print(f"{m.verdict:<8} {m.name:<{width}}  {_fmt(m.value, m.unit)}")
    print(f"OVERALL  {report['overall']}")
    return 1 if report["overall"] == FAIL else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. under some test runners); default encoding is used
    sys.exit(main())
