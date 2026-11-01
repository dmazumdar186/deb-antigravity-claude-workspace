"""Deterministic evaluation harness for short AI-made explainer films.

description: Scores a rendered explainer film against its captions, script, fact sheet and the
             renderer's drawn-text log. Technical: container, loudness (ebur128), black / frozen
             / silent stretches, sha256. Content: number fidelity per source (narration,
             on-screen text, SRT, drawn text), fact-tag coverage/validity/consistency, quote
             fidelity (quotations vs labels), PII, caption readability, speech rate. Optional:
             --asr (faster-whisper WER + every subtitle number audible), --jev (two-step
             claim -> entailment + contradiction, N repeats, calibrated threshold).
             --calibrate runs the Jev questions over a labelled CSV and writes AUROC, the best
             threshold and the confusion matrix. --compare prints per-metric deltas vs an older report.
             --srt is optional: without it caption metrics are SKIPPED ("no captions supplied"); a
             "(none)" / "none" / em-dash / empty narration section means no narration (speech rate,
             ASR and Jev SKIPPED). --profile linkedin_4x5 accepts 1080x1350 and adds a mobile-feed
             drawn-text size WARN.
             Directive: directives/video/film_eval.md
inputs: --video MP4 [--srt SRT] --script SCRIPT.md --facts FACTS.md [--drawn drawn_text.json]
        [--profile default|linkedin_4x5]
        [--asr --asr-model small.en --asr-lang en --asr-python PY] [--jev --jev-repeats 3]
        [--deny FILE] [--deny-names "Camille,Roux"] [--hold 5] [--max-mb 25] [--expect-sha256 HEX]
        [--compare old.json] [--out JSON] [--md MD]
        Calibration: --calibrate labels.csv --facts FACTS.md [--calib-out MD] [--jev-repeats 3].
        env OPENROUTER_API_KEY (Jev), FILM_EVAL_ASR_PYTHON (fallback interpreter for ASR).
outputs: JSON report (--out), markdown report (--md), summary table on stdout; with --calibrate,
         a markdown calibration report and eval_data/jev_support_thresholds.json. Jev calls append
         to .tmp/jev_ledger.jsonl (caller "film_eval"). Exit 0 = PASS/WARN, 1 = FAIL, 2 = usage.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import itertools
import json
import math
import os
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

VERSION = "2.1.0"
PASS, WARN, FAIL, SKIPPED = "PASS", "WARN", "FAIL", "SKIPPED"
DEFAULT_DENY_NAMES = "Camille,Roux"
EVAL_DATA = Path(__file__).resolve().parent / "eval_data"
JEV_THRESHOLDS_FILE = EVAL_DATA / "jev_support_thresholds.json"

# Every threshold in one place; SOURCES says where each one comes from ("guess" when unsourced).
T: dict[str, Any] = {
    "max_mb": 25.0, "min_w": 1280, "min_h": 720, "fps_lo": 23.9, "fps_hi": 60.0, "max_kbps": 8000,
    "lufs_target": -16.0, "lufs_tol": 1.0, "tp_max": -1.0, "lra_warn": 15.0,
    "head_ignore": 1.0, "hold": 5.0,
    "black_warn": 0.5, "black_fail": 2.0, "freeze_warn": 4.0, "freeze_fail": 10.0,
    "silence_warn": 3.0, "silence_fail": 6.0,
    "cps_warn": 17.0, "cps_fail": 21.0, "cue_min": 1.0, "cue_max": 7.0, "line_max": 42, "lines_max": 2,
    "gap_frames": 2,
    "wpm_lo": 130.0, "wpm_hi": 170.0, "wpm_margin": 15.0,
    "tag_cov_warn": 0.8, "quote_similar": 0.6,
    "wer_pass": 0.05, "wer_warn": 0.10,
    "drawn_min_px": 28, "drawn_min_on": 1.0,
    # --profile linkedin_4x5
    "p45_w": 1080, "p45_h": 1350, "mobile_pt_width": 390, "mobile_ref_px": 1080, "mobile_min_pt": 11.0,
    "jev_claim": 0.5, "jev_entail": 0.5, "jev_contra": 0.5, "jev_auroc_gate": 0.9,
}
SOURCES: dict[str, str] = {
    "file_size": "Gmail attachment limit (25 MB)",
    "resolution": "guess (web-delivery convention)", "fps": "guess", "video_codec": "guess (h264/yuv420p plays everywhere)",
    "audio_codec": "guess", "bitrate": "guess",
    "loudness_integrated": "AES TD1004/TD1008 (-16 LUFS for streamed speech); measured per ITU-R BS.1770 / EBU R128; "
                           "+/-1 LU tolerance per EBU R128",
    "true_peak": "EBU R128 / AES TD1008 (max -1 dBTP)", "loudness_range": "guess",
    "black_frames": "guess", "frozen_frames": "guess", "silence": "guess",
    "caption_cps": "Netflix English Timed Text Style Guide: 17 cps = children's limit (adult 20), used as WARN; "
                   "FAIL 21 = guess",
    "caption_duration": "Netflix TTSG: max 7 s; min 1.0 s = guess (Netflix minimum is 5/6 s)",
    "caption_line_length": "Netflix TTSG: 42 characters per line",
    "caption_lines_per_cue": "Netflix TTSG: max 2 lines",
    "caption_timing": "Netflix TTSG timing guidelines: 2-frame minimum gap between events",
    "speech_rate": "guess, bounded by BBC Subtitle Guidelines (160-180 wpm subtitle rate)",
    "tag_coverage": "guess", "quote_fidelity": "exact match; 0.6 similarity cut = guess",
    "asr_wer": "guess", "drawn_text_size": "guess (28 px at 1080p, >= 1 s on screen)",
    "resolution_linkedin_4x5": "guess (LinkedIn 4:5 feed video, 1080x1350)",
    "drawn_text_mobile": "guess (mobile-feed readability proxy: px x 390/1080 = pt on a 390-pt-wide phone, "
                         "11 pt floor)",
    "jev": "calibrated on eval_data/jev_support_labels.csv (see jev_support_calibration.md)",
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
    n: int | None = None
    source: str = ""
    basis: str = ""          # where the threshold comes from (SOURCES)


def metric(group: str, name: str, value: Any, threshold: str, verdict: str, *, unit: str = "",
           detail: list[str] | None = None, note: str = "", n: int | None = None, source: str = "",
           basis_key: str | None = None) -> Metric:
    return Metric(group, name, value, threshold, verdict, unit, detail or [], note, n, source,
                  SOURCES.get(basis_key or name, ""))


# =========================================================================================
# Text helpers
# =========================================================================================

QUOTE_MAP = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2033": '"', "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
})
DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def norm_quotes(s: str) -> str:
    return s.translate(QUOTE_MAP)


def collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u00a0", " ").replace("\u202f", " ")).strip()


_WORD_RE = re.compile(r"[A-Za-z0-9\u00c0-\u024f]+(?:['\u2019-][A-Za-z0-9\u00c0-\u024f]+)*")


def count_words(text: str) -> int:
    """The one tokenizer for word counts: letters/digits runs; hyphenated and apostrophe compounds
    ("twenty-five", "don't") count as one word; tags and punctuation do not count."""
    return len(_WORD_RE.findall(strip_tags(text)))


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


# ---- number words -> digits -----------------------------------------------------------

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_UNIT_W = {w: i for i, w in enumerate(_ONES[:10])}
_TEEN_W = {w: i + 10 for i, w in enumerate(_ONES[10:])}
_TENS_W = {w: i * 10 for i, w in enumerate(_TENS) if w}
_SCALE_W = {"thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
_NUMWORDS = list(_UNIT_W) + list(_TEEN_W) + list(_TENS_W) + ["hundred"] + list(_SCALE_W)
_NW = "(?:" + "|".join(sorted(_NUMWORDS, key=len, reverse=True)) + r")\b"
NUMWORD_RUN_RE = re.compile(rf"\b{_NW}(?:(?:[\s-]+(?:and[\s-]+)?){_NW})*", re.IGNORECASE)


def _parse_number_run(tokens: list[str]) -> list[str]:
    out: list[str] = []
    st = {"total": 0, "cur": 0, "last": None, "started": False, "scale": None}

    def flush() -> None:
        if st["started"]:
            out.append(str(st["total"] + st["cur"]))
        st.update(total=0, cur=0, last=None, started=False, scale=None)

    for i, w in enumerate(tokens):
        lw = w.lower()
        nxt = tokens[i + 1].lower() if i + 1 < len(tokens) else ""
        if lw == "and":
            if st["started"] and st["last"] in ("hundred", "scale") and (nxt in _UNIT_W or nxt in _TEEN_W
                                                                          or nxt in _TENS_W):
                continue
            flush()
            out.append(w)
        elif lw in _UNIT_W:
            if st["started"] and st["last"] not in ("tens", "hundred", "scale"):
                flush()
            st["cur"] += _UNIT_W[lw]
            st.update(last="unit", started=True)
        elif lw in _TEEN_W or lw in _TENS_W:
            if st["started"] and st["last"] not in ("hundred", "scale"):
                flush()
            st["cur"] += _TEEN_W.get(lw, _TENS_W.get(lw, 0))
            st.update(last="teen" if lw in _TEEN_W else "tens", started=True)
        elif lw == "hundred":
            if st["started"] and st["last"] in ("unit", "teen", "tens") and 0 < st["cur"] < 100:
                st["cur"] *= 100
                st["last"] = "hundred"
            else:
                flush()
                out.append(w)
        else:  # scale word
            s = _SCALE_W[lw]
            if st["started"] and st["cur"] > 0 and (st["scale"] is None or s < st["scale"]):
                st["total"] += st["cur"] * s
                st.update(cur=0, last="scale", scale=s)
            else:
                flush()
                out.append(w)
    flush()
    return out


def words_to_digits(text: str, lone_one: bool = False) -> str:
    """Spoken numbers to digits: "forty-nine" -> 49, "five hundred and twenty-five" -> 525,
    "sixty-eight per cent" -> "68 per cent" (NUMBER_RE then reads 68%). A lone "one" stays a word
    unless lone_one (it is usually a determiner: "one sentence", "one user")."""
    def repl(m: re.Match[str]) -> str:
        tokens = re.split(r"[\s-]+", m.group(0))
        if not lone_one and len(tokens) == 1 and tokens[0].lower() == "one":
            return m.group(0)
        return " ".join(_parse_number_run(tokens))
    return NUMWORD_RUN_RE.sub(repl, text)


# ---- digits ----------------------------------------------------------------------------

_NUM = r"\d{1,3}(?:[,\u00a0\u202f\u2009]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?"
_ID = r"[A-Z]{1,3}\d{2,}"
_TOK = rf"(?:{_ID}|{_NUM})"
NUMBER_RE = re.compile(
    rf"(?<![\w.])(?P<a>{_TOK})(?:\s*[{DASHES}]\s*(?P<b>{_TOK}))?"
    rf"(?P<pct>\s?(?:%|percent\b|per\s+cent\b))?(?![\w])",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(?<![\d.])\d{4}-\d{2}-\d{2}(?![\d])")


@dataclass(frozen=True)
class Num:
    raw: str
    canon: str              # "49", "3.5", "68%", "M0501", "M0501-M0525", "25-30", "2026-10-12"
    parts: tuple[str, ...]  # canonical endpoints (one for a single value)
    kind: str = "num"       # num | id | date

    @property
    def is_single_id(self) -> bool:
        return self.kind == "id" and len(self.parts) == 1


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


def _id_prefix(tok: str) -> str:
    m = re.match(r"[A-Z]+", tok)
    return m.group(0) if m else ""


def extract_numbers(text: str, id_prefixes: set[str] | None = None) -> list[Num]:
    """Every number in `text`: integers, decimals, percentages, ranges, dates, record ids.
    With `id_prefixes`, an id like S02/L01 whose letter prefix is not used by any FACTS id is
    structure (cue/line numbers) and is skipped (rule R2)."""
    out: list[Num] = []
    for m in DATE_RE.finditer(text):
        out.append(Num(m.group(0), m.group(0), (m.group(0),), "date"))
    text = DATE_RE.sub(" ", text)
    for m in NUMBER_RE.finditer(text):
        a, b = m.group("a"), m.group("b")
        toks = [t for t in (a, b) if t]
        if any(re.fullmatch(_ID, t, re.IGNORECASE) and not re.fullmatch(_ID, t) for t in toks):
            continue  # lowercase letter+digits run inside a word, not an id
        ids = [t for t in toks if re.fullmatch(_ID, t)]
        if ids and id_prefixes is not None and any(_id_prefix(t) not in id_prefixes for t in ids):
            continue
        kind = "id" if ids else "num"
        pct = "%" if m.group("pct") else ""
        ca = _canon_one(a) + pct
        if b:
            cb = _canon_one(b) + pct
            out.append(Num(m.group(0).strip(), f"{ca}-{cb}", (ca, cb), kind))
        else:
            out.append(Num(m.group(0).strip(), ca, (ca,), kind))
    return out


_UNITS = (r"s|sec|secs|seconds?|ms|min|mins|minutes?|fps|px|wpm|bpm|kbps|mbps|mb|kb|gb|"
          r"k|p|lufs|db|dbtp|dbfs|lu|hz|khz|x|frames?|f")
STRUCTURAL_PATTERNS = [
    re.compile(r"`[^`]*`"),                                            # inline code / file names
    re.compile(r"https?://\S+"),
    re.compile(r"\]\([^)]*\)"),                                        # markdown link targets
    re.compile(r"#[0-9a-fA-F]{3,8}\b"),                                # hex colours
    re.compile(r"\b\d{2,5}\s*[x\u00d7]\s*\d{2,5}\b"),                   # resolutions (R3)
    re.compile(rf"\b\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:[.,]\d{{1,3}})?"
               rf"(?:\s*(?:[{DASHES}]|-->|to)\s*\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:[.,]\d{{1,3}})?)?"),
    re.compile(r"\b(?:scene|shot|beat|slide|act|part|step|frame|cue|take|section|chapter|page|"
               r"segment|version|speed|crf|v)\s*#?\s*\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(rf"(?<![\w.])\d+(?:[.,]\d+)?(?:\s*[{DASHES}]\s*\d+(?:[.,]\d+)?)?\s?(?:{_UNITS})\b",
               re.IGNORECASE),
    re.compile(r"^\s*(?:[-*+>]\s+)*\d+[.)]\s+"),                       # ordered-list markers
]


def strip_structural(line: str) -> str:
    """Remove numbers that are script structure, not film content (timecodes, scene numbers,
    durations and units, resolutions, list markers, fact tags)."""
    line = strip_tags(line)
    for pat in STRUCTURAL_PATTERNS:
        line = pat.sub(" ", line)
    return line


# ---- quotes ----------------------------------------------------------------------------

_SMART_PAIRS = [("\u201c", "\u201d"), ("\u00ab", "\u00bb"), ("\u201e", "\u201c"), ("\u201e", "\u201d")]


def extract_quotes(text: str) -> list[str]:
    """Quoted strings in one cell. Smart pairs are matched before straight quotes (R4), so a
    straight-quoted label wrapping a smart-quoted phrase yields both, without junk like "|"."""
    found: list[tuple[int, str]] = []
    rest = text
    for op, cl in _SMART_PAIRS:
        for m in re.finditer(rf"{re.escape(op)}([^{re.escape(op)}{re.escape(cl)}\n]+?){re.escape(cl)}", rest):
            found.append((m.start(), m.group(1)))
        rest = re.sub(rf"{re.escape(op)}[^{re.escape(op)}{re.escape(cl)}\n]+?{re.escape(cl)}",
                      lambda mm: " " * len(mm.group(0)), rest)
    for m in re.finditer(r'"([^"\n]+?)"', rest):
        found.append((m.start(), m.group(1)))
    out = []
    for _, q in sorted(found):
        q = collapse_ws(norm_quotes(q)).strip(" \u2014-")
        if len(q) >= 2:
            out.append(q)
    return out


def quote_core(s: str) -> str:
    """Comparison form: straight quotes, ' / ' line breaks as spaces (R5), trailing punctuation off."""
    s = norm_quotes(s).replace(" / ", " ")
    return collapse_ws(s).rstrip(" .,;:!?\u2026")


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
    return bool(cells) and any(cells) and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c)


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
        f = Fact(id=fid(m.group(1)), fact=cells[cols["fact"]] if len(cells) > cols["fact"] else "",
                 value=cells[cols["value"]], source=cells[cols["source"]] if len(cells) > cols["source"] else "")
        # R7: number words in FACTS count too ("Three years" -> 3)
        for part in (f.fact, f.value):
            f.numbers += extract_numbers(words_to_digits(strip_tags(part), lone_one=True))
        f.quotes = extract_quotes(f.value)
        facts[f.id] = f
    return facts


class FactIndex:
    def __init__(self, facts: dict[str, Fact], facts_text: str = ""):
        self.facts = facts
        self.by_canon: dict[str, set[str]] = {}
        self.id_ranges: list[tuple[str, int, int, int, str]] = []  # prefix, width, lo, hi, fid
        self.id_prefixes: set[str] = set()
        self.dates = set(DATE_RE.findall(facts_text))   # e.g. the reference date in the preamble
        for f in facts.values():
            for n in f.numbers:
                self.by_canon.setdefault(n.canon, set()).add(f.id)
                for p in n.parts:
                    self.by_canon.setdefault(p, set()).add(f.id)
                if n.kind == "id":
                    self.id_prefixes.update(_id_prefix(p) for p in n.parts)
                if len(n.parts) == 2:
                    ma = re.fullmatch(r"([A-Z]+)(\d+)", n.parts[0])
                    mb = re.fullmatch(r"([A-Z]+)(\d+)", n.parts[1])
                    if ma and mb and ma.group(1) == mb.group(1):
                        self.id_ranges.append((ma.group(1), len(ma.group(2)), int(ma.group(2)),
                                               int(mb.group(2)), f.id))

    def match(self, n: Num) -> list[str]:
        """Fact ids containing `n` (exact canon, both range endpoints, an id inside an id range,
        or a date written anywhere in FACTS.md)."""
        if n.kind == "date":
            return ["FACTS.md"] if n.canon in self.dates else []
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
# SCRIPT.md -> sources (narration / on-screen text). Nothing else is checked (rule 1).
# =========================================================================================

@dataclass
class Src:
    lineno: int
    kind: str              # narration | onscreen
    text: str              # spoken or displayed text (cells joined with " | ")
    cells: list[str]
    tags: list[str]
    raw: str

    @property
    def loc(self) -> str:
        return f"SCRIPT.md:{self.lineno}"


_STRUCT_COL_RE = re.compile(
    r"^(#|no\.?|n°|nr|num(ber)?|scene|shot|beat|cue|line|sub|row|time|timecode|tc|start|end|in|out|"
    r"dur(ation)?|length|frames?|id|ids|facts?( ids?)?|tags?|sources?|burned in|burn[- ]?in)$", re.IGNORECASE)
_NARR_COL_RE = re.compile(r"\b(vo|v\.o\.|voice[- ]?over|voiceover|voice|narration|narrator|spoken|audio)\b",
                          re.IGNORECASE)
NARR_SEC_RE = re.compile(r"^(narration|voice[- ]?over|voiceover|vo|spoken|script)\b", re.IGNORECASE)
ONSCREEN_SEC_RE = re.compile(r"^(on[- ]?screen|drawn text|supers?\b|text on screen|graphics\b)", re.IGNORECASE)
NARR_LABEL_RE = re.compile(
    r"^\s*(?:[-*+>]\s+)*[*_]{0,2}\s*(?:vo|v\.o\.|voice[- ]?over|voiceover|narration|narrator|voice)\b"
    r"\s*(?:\([^)]*\))?\s*[*_]{0,2}\s*[:\uff1a]\s*[*_]{0,2}\s*(?P<body>.+)$", re.IGNORECASE)
ONSCREEN_LABEL_RE = re.compile(
    r"^\s*(?:[-*+>]\s+)*[*_]{0,2}\s*(?:on[- ]?screen(?: text)?|ost|super|title card|lower third|graphic|card)\b"
    r"\s*[*_]{0,2}\s*[:\uff1a]\s*[*_]{0,2}\s*(?P<body>.+)$", re.IGNORECASE)
ANY_LABEL_RE = re.compile(r"^\s*(?:[-*+>]\s+)*[*_]{0,2}[A-Za-z][A-Za-z ./-]{0,24}[*_]{0,2}\s*[:\uff1a]")


def clean_spoken(text: str) -> str:
    """Narration as it should be spoken: no tags, stage directions or markdown."""
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


def clean_display(text: str) -> str:
    return collapse_ws(re.sub(r"[*_]{2,}", "", strip_tags(text)))


def _table_rows(lines: list[str], start: int) -> tuple[list[str], list[tuple[int, list[str], str]], int]:
    """Parse a markdown table starting at index `start`: (header, [(lineno, cells, raw)], next index)."""
    header = split_row(lines[start])
    rows: list[tuple[int, list[str], str]] = []
    i = start + 1
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = split_row(lines[i])
        if not is_separator_row(cells):
            rows.append((i + 1, cells, lines[i]))
        i += 1
    return header, rows, i


def _is_table_start(lines: list[str], i: int) -> bool:
    return (lines[i].strip().startswith("|") and i + 1 < len(lines)
            and is_separator_row(split_row(lines[i + 1])))


def _row_src(kind: str, header: list[str], lineno: int, cells: list[str], raw: str) -> Src | None:
    keep = [k for k, h in enumerate(header) if not _STRUCT_COL_RE.match(h.strip("*_ "))]
    if keep and len(cells) > len(header):
        # an unescaped "|" inside a text cell: structural columns align from both ends,
        # everything in between is content of the text column(s)
        left, right = keep[0], len(header) - 1 - keep[-1]
        middle = " | ".join(cells[left:len(cells) - right])
        cells = cells[:left] + [middle] + [""] * (len(keep) - 1) + cells[len(cells) - right:]
        cells = (cells + [""] * len(header))[:len(header)]
    if kind == "narration":
        narr = [k for k in keep if _NARR_COL_RE.search(header[k])] or [
            k for k in keep if re.search(r"\btext\b", header[k], re.IGNORECASE)]
        keep = narr[:1] or keep
    chosen = [cells[k] for k in keep if k < len(cells) and cells[k].strip() not in ("", "-", "\u2014")]
    if not chosen:
        return None
    clean = clean_spoken if kind == "narration" else clean_display
    texts = [clean(c) for c in chosen]
    return Src(lineno, kind, " | ".join(t for t in texts if t), texts, extract_tags(raw), raw)


def _skip_noise(lines: list[str]) -> list[bool]:
    """True for lines inside code fences, HTML comments or front matter."""
    skip = [False] * len(lines)
    in_code = in_comment = False
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for k in range(j + 1):
                    skip[k] = True
                break
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith(("```", "~~~")):
            in_code = not in_code
            skip[i] = True
            continue
        if in_code:
            skip[i] = True
            continue
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            skip[i] = True
    return skip


PLACEHOLDER_RE = re.compile(r"^[(\[]?\s*(?:none|[-\u2013\u2014])?\s*[)\]]?\.?$", re.IGNORECASE)
NO_NARRATION = "no narration"
NO_CAPTIONS = "no captions supplied"


def is_placeholder(text: str) -> bool:
    """'(none)', 'none', an em dash or nothing: the section is deliberately empty."""
    return bool(PLACEHOLDER_RE.match(collapse_ws(text)))


def script_sources(text: str) -> tuple[list[Src], str]:
    """Narration and on-screen-text items of SCRIPT.md and the detection mode. Placeholder lines
    ('(none)', 'none', an em dash) are dropped, so a silent film has no narration items."""
    items, mode = _script_sources(text)
    return [s for s in items if not is_placeholder(s.text)], mode


def _script_sources(text: str) -> tuple[list[Src], str]:
    """Raw narration and on-screen-text items of SCRIPT.md and the detection mode.

    1. sections: "## Narration ..." and "## On-screen text ..." (tables or prose; subheadings stay
       inside). Everything outside them (title, metadata line, subtitles table, footnotes) is ignored.
    2. labelled lines: VO: / Narrator: and ON SCREEN: / SUPER: lines.
    3. narration-only fallbacks: a table with a narration column, blockquotes, then all prose.
    """
    lines = text.splitlines()
    skip = _skip_noise(lines)
    items: list[Src] = []
    found_section = False
    kind: str | None = None
    level = 0
    sec_id = 0
    prose: list[tuple[int, Src]] = []     # (section id, item); dropped if that section has a table
    tabled: set[int] = set()
    i = 0
    while i < len(lines):
        if skip[i]:
            i += 1
            continue
        s = lines[i].strip()
        hm = re.match(r"^(#+)\s*(.*)$", s)
        if hm:
            lv, title = len(hm.group(1)), hm.group(2)
            if kind and lv > level:
                i += 1
                continue                       # subheading inside the current section
            kind, level = None, 0
            sec_id += 1
            if NARR_SEC_RE.search(title):
                kind, level = "narration", lv
            elif ONSCREEN_SEC_RE.search(title):
                kind, level = "onscreen", lv
            found_section = found_section or kind is not None
            i += 1
            continue
        if kind and _is_table_start(lines, i):
            header, rows, i = _table_rows(lines, i)
            tabled.add(sec_id)
            for lineno, cells, raw in rows:
                src = _row_src(kind, header, lineno, cells, raw)
                if src:
                    items.append(src)
            continue
        if kind and s and not s.startswith("|"):
            m = NARR_LABEL_RE.match(s) or ONSCREEN_LABEL_RE.match(s)
            body = m.group("body") if m else re.sub(r"^\s*(?:[-*+>]\s+)+", "", s)
            t = clean_spoken(body) if kind == "narration" else clean_display(body)
            if t:
                prose.append((sec_id, Src(i + 1, kind, t, [t], extract_tags(s), lines[i])))
        i += 1
    if found_section:
        # a section that holds a table is that table; prose around it is commentary (footnotes)
        items += [src for sid, src in prose if sid not in tabled]
        items.sort(key=lambda x: x.lineno)
        return items, "sections"
    # 2. labelled lines
    for n, raw in enumerate(lines):
        if skip[n]:
            continue
        m = NARR_LABEL_RE.match(raw)
        if m:
            body = [m.group("body")]
            k = n + 1
            while k < len(lines):
                s = lines[k].strip()
                if not s or s.startswith(("#", "|")) or ANY_LABEL_RE.match(s):
                    break
                body.append(s)
                k += 1
            t = clean_spoken(" ".join(body))
            if t:
                items.append(Src(n + 1, "narration", t, [t], extract_tags(" ".join([raw, *body[1:]])), raw))
            continue
        m = ONSCREEN_LABEL_RE.match(raw)
        if m:
            t = clean_display(m.group("body"))
            if t:
                items.append(Src(n + 1, "onscreen", t, [t], extract_tags(raw), raw))
    if items:
        return items, "labelled"
    # 3. narration-only fallbacks
    for i in range(len(lines)):
        if not skip[i] and _is_table_start(lines, i):
            header, rows, _ = _table_rows(lines, i)
            if any(_NARR_COL_RE.search(h) for h in header):
                for lineno, cells, raw in rows:
                    src = _row_src("narration", header, lineno, cells, raw)
                    if src:
                        items.append(src)
                return items, "table_column"
    bq = [(n + 1, r) for n, r in enumerate(lines) if not skip[n] and r.strip().startswith(">")]
    if bq:
        return [Src(n, "narration", clean_spoken(r.strip()[1:]), [clean_spoken(r.strip()[1:])], extract_tags(r), r)
                for n, r in bq if clean_spoken(r.strip()[1:])], "blockquote"
    for n, raw in enumerate(lines):
        s = raw.strip()
        if skip[n] or not s or s.startswith(("#", "|")):
            continue
        t = clean_spoken(s.lstrip("-*+ "))
        if t:
            items.append(Src(n + 1, "narration", t, [t], extract_tags(s), raw))
    return items, "all_prose"


def src_numbers(src: Src, prefixes: set[str]) -> list[Num]:
    """Numbers a viewer hears or sees in one item. Narration: number words are converted first.
    On-screen text: digits only (words there describe the picture: "four empty slots")."""
    text = strip_structural(src.text)
    if src.kind == "narration":
        text = words_to_digits(text)
    return extract_numbers(text, prefixes)


# =========================================================================================
# SRT and drawn text
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


def speech_seconds(cues: list[Cue]) -> float:
    """Union of cue spans: time during which narration is on screen as captions."""
    total, cur_s, cur_e = 0.0, None, None
    for c in sorted(cues, key=lambda c: c.start):
        if cur_e is None or c.start > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = c.start, c.end
        else:
            cur_e = max(cur_e, c.end)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


@dataclass
class Drawn:
    k: int
    text: str
    t_start: float
    t_end: float
    x: float
    y: float
    px: float
    draws: int = 1

    @property
    def loc(self) -> str:
        return f"drawn#{self.k}@{self.t_start:.2f}s"


def load_drawn(path: Path) -> list[Drawn]:
    """drawn_text.json: [{text, t_start, t_end, x, y, px}, ...] (or {"items": [...]}). Identical
    strings at the same place and size with touching time ranges are merged into one item."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = next((data[k] for k in ("items", "drawn", "texts", "entries") if isinstance(data.get(k), list)), [])
    if not isinstance(data, list):
        raise TypeError("drawn text JSON must be a list of {text, t_start, t_end, x, y, px}")
    raw: list[Drawn] = []
    for e in data:
        if not isinstance(e, dict) or not str(e.get("text", "")).strip():
            continue
        try:
            raw.append(Drawn(0, str(e["text"]), float(e.get("t_start", 0)), float(e.get("t_end", e.get("t_start", 0))),
                             float(e.get("x", 0)), float(e.get("y", 0)), float(e.get("px", 0))))
        except (TypeError, ValueError, KeyError):
            continue
    raw.sort(key=lambda d: (d.text, round(d.x), round(d.y), d.px, d.t_start))
    merged: list[Drawn] = []
    for d in raw:
        last = merged[-1] if merged else None
        if (last and last.text == d.text and round(last.x) == round(d.x) and round(last.y) == round(d.y)
                and last.px == d.px and d.t_start <= last.t_end + 0.1):
            last.t_end = max(last.t_end, d.t_end)
            last.draws += 1
        else:
            merged.append(d)
    merged.sort(key=lambda d: (d.t_start, d.y, d.x))
    for k, d in enumerate(merged):
        d.k = k
    return merged


# =========================================================================================
# WER normalisation (digits and number words -> one spoken form)
# =========================================================================================

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
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    t = re.sub(r"(?<=\d)[\u00a0\u202f\u2009](?=\d{3}\b)", "", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"\s*%", " percent ", t)
    t = re.sub(r"\bper\s+cent\b", "percent", t)
    t = re.sub(rf"(?<=[\w%])\s*[{DASHES[1:]}]\s*(?=[a-z]?\d)", " to ", t)
    t = re.sub(r"(?<=\d)\s*-\s*(?=[a-z]?\d)", " to ", t)
    t = t.replace("&", " and ")
    t = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", t)
    t = re.sub(r"\d+(?:\.\d+)?", lambda m: " " + number_to_words(m.group(0)) + " ", t)
    t = re.sub(rf"[{DASHES}]", " ", t)
    t = t.replace("'", "")
    t = re.sub(r"[^\w\s]", " ", t)
    toks = t.split()
    out: list[str] = []
    for k, w in enumerate(toks):
        if w == "and" and out and out[-1] in NUMBER_WORDS and k + 1 < len(toks) and toks[k + 1] in NUMBER_WORDS:
            continue
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


def spoken_numbers(transcript: str) -> set[str]:
    """Canonical numbers heard in a transcript (words converted, lone "one" included)."""
    out: set[str] = set()
    for n in extract_numbers(words_to_digits(transcript, lone_one=True)):
        out.add(n.canon)
        out.update(n.parts)
    return out


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
    starts = [max(0.0, float(m.group(1))) for m in re.finditer(start_pat, log)]
    ends = [float(m.group(1)) for m in re.finditer(end_pat, log)]
    return [(s, ends[i] if i < len(ends) else duration) for i, s in enumerate(starts)]


def _inside(span: tuple[float, float], lo: float, hi: float) -> float:
    """Seconds of `span` inside the evaluated window [lo, hi]."""
    return max(0.0, min(span[1], hi) - max(span[0], lo))


# =========================================================================================
# Metric builders
# =========================================================================================

def _v3(pass_ok: bool, warn_ok: bool) -> str:
    return PASS if pass_ok else (WARN if warn_ok else FAIL)


def technical_metrics(video: Path, srt_end: float, expect_sha: str | None,
                      profile: str = "default") -> tuple[list[Metric], dict[str, Any]]:
    M: list[Metric] = []
    info: dict[str, Any] = {}
    g, vs = "technical", video.name
    size = video.stat().st_size
    sha = hashlib.sha256()
    with video.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    info["sha256"] = sha.hexdigest()
    info["size_bytes"] = size
    mb = size / 1_000_000
    M.append(metric(g, "file_size", round(mb, 2), f"<= {T['max_mb']} MB", PASS if mb <= T["max_mb"] else FAIL,
                    unit="MB", n=1, source=vs))
    if expect_sha:
        ok = expect_sha.lower() == info["sha256"]
        M.append(metric(g, "encode_determinism", info["sha256"][:16], f"sha256 == {expect_sha[:16]}...",
                        PASS if ok else FAIL, detail=[] if ok else [f"actual {info['sha256']}"], n=1, source=vs,
                        basis_key="file_size"))
        M[-1].basis = "exact byte equality"
    if not (shutil.which("ffprobe") and shutil.which("ffmpeg")):
        M.append(metric(g, "container", None, "-", SKIPPED, note="ffprobe/ffmpeg not on PATH", source=vs))
        return M, info
    try:
        probe = ffprobe(video)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        M.append(metric(g, "container", None, "readable by ffprobe", FAIL, note=str(exc), source=vs))
        return M, info
    streams, fmt = probe.get("streams", []), probe.get("format", {})
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    info["has_audio"] = a is not None
    duration = float(fmt.get("duration") or (v or {}).get("duration") or 0.0)
    info["duration"] = duration
    dur_ok = duration > 0 and srt_end <= duration + 0.5
    M.append(metric(g, "duration", round(duration, 3), ">= last caption end" if srt_end else "> 0 s (no captions)",
                    PASS if dur_ok else (FAIL if duration <= 0 else WARN), unit="s",
                    detail=[] if dur_ok or duration <= 0 else [f"last cue ends {srt_end:.2f}s, video {duration:.2f}s"],
                    n=1, source=vs, basis_key="fps"))
    M[-1].basis = "consistency check"
    if v is None:
        M.append(metric(g, "video_stream", None, "present", FAIL, n=1, source=vs))
    else:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        info["height"], info["width"] = h, w
        if profile == "linkedin_4x5":
            ok = w >= T["p45_w"] and h >= T["p45_h"] and abs(w * 5 - h * 4) <= 0.01 * h * 4
            M.append(metric(g, "resolution", f"{w}x{h}", f">= {T['p45_w']}x{T['p45_h']}, 4:5 (profile linkedin_4x5)",
                            PASS if ok else WARN, n=1, source=vs, basis_key="resolution_linkedin_4x5"))
        else:
            M.append(metric(g, "resolution", f"{w}x{h}", f">= {T['min_w']}x{T['min_h']}",
                            PASS if w >= T["min_w"] and h >= T["min_h"] else WARN, n=1, source=vs))
        num, _, den = str(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0.0
        info["fps"] = fps
        M.append(metric(g, "fps", round(fps, 3), f"{T['fps_lo']}-{T['fps_hi']}",
                        PASS if T["fps_lo"] <= fps <= T["fps_hi"] else WARN, n=1, source=vs))
        vc, pix = v.get("codec_name", "?"), v.get("pix_fmt", "?")
        M.append(metric(g, "video_codec", f"{vc}/{pix}", "h264/yuv420p",
                        PASS if vc == "h264" and pix == "yuv420p" else WARN, n=1, source=vs))
    M.append(metric(g, "audio_present", a is not None, "audio stream present", PASS if a else FAIL, n=1, source=vs,
                    basis_key="audio_codec"))
    if a is not None:
        ac = a.get("codec_name", "?")
        M.append(metric(g, "audio_codec", f"{ac} {a.get('sample_rate', '?')} Hz {a.get('channels', '?')}ch",
                        "aac", PASS if ac == "aac" else WARN, n=1, source=vs))
    kbps = float(fmt.get("bit_rate") or 0) / 1000
    M.append(metric(g, "bitrate", round(kbps), f"<= {T['max_kbps']} kbps", PASS if kbps <= T["max_kbps"] else WARN,
                    unit="kbps", n=1, source=vs))
    try:
        scan = ffmpeg_scan(video, a is not None, duration)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        M.append(metric(g, "ffmpeg_scan", None, "-", FAIL, note=str(exc), source=vs))
        return M, info
    L = scan["loudness"]
    if a is None or "integrated" not in L:
        M.append(metric(g, "loudness_integrated", None, "-", SKIPPED, source=vs,
                        note="no audio stream" if a is None else "ebur128 summary not found"))
    else:
        tgt, tol = T["lufs_target"], T["lufs_tol"]
        i = L["integrated"]
        off = abs(i - tgt) if i != float("-inf") else 99.0
        M.append(metric(g, "loudness_integrated", i, f"{tgt} +/-{tol} LUFS", PASS if off <= tol else FAIL,
                        unit="LUFS", n=1, source=vs, note=f"{duration:.1f}s of programme measured"))
        tp = L.get("true_peak", float("-inf"))
        M.append(metric(g, "true_peak", tp, f"<= {T['tp_max']} dBTP", PASS if tp <= T["tp_max"] else FAIL,
                        unit="dBTP", n=1, source=vs))
        lra = L.get("lra", 0.0)
        M.append(metric(g, "loudness_range", lra, f"<= {T['lra_warn']} LU", PASS if lra <= T["lra_warn"] else WARN,
                        unit="LU", n=1, source=vs))
    hi = max(0.0, duration - T["hold"])
    black = [(s, e, _inside((s, e), T["head_ignore"], hi)) for s, e in scan["black"]]
    worst = max((x[2] for x in black), default=0.0)
    M.append(metric(g, "black_frames", round(worst, 2),
                    f"longest black < {T['black_warn']}s (FAIL >= {T['black_fail']}s); first {T['head_ignore']}s, "
                    f"final {T['hold']}s ignored",
                    PASS if worst < T["black_warn"] else (WARN if worst < T["black_fail"] else FAIL), unit="s",
                    detail=[f"black {s:.2f}-{e:.2f}s ({o:.2f}s in body)" for s, e, o in black], n=len(black), source=vs))
    frz = [(s, e, _inside((s, e), 0.0, hi)) for s, e in scan["freeze"]]
    worst = max((x[2] for x in frz), default=0.0)
    M.append(metric(g, "frozen_frames", round(worst, 2),
                    f"longest freeze <= {T['freeze_warn']}s outside final {T['hold']}s (FAIL > {T['freeze_fail']}s)",
                    PASS if worst <= T["freeze_warn"] else (WARN if worst <= T["freeze_fail"] else FAIL), unit="s",
                    detail=[f"freeze {s:.2f}-{e:.2f}s ({o:.2f}s outside hold)" for s, e, o in frz], n=len(frz), source=vs))
    if a is None:
        M.append(metric(g, "silence", None, "-", SKIPPED, note="no audio stream", source=vs))
    else:
        sil = [(s, e, _inside((s, e), 0.0, hi)) for s, e in scan["silence"]]
        worst = max((x[2] for x in sil), default=0.0)
        M.append(metric(g, "silence", round(worst, 2),
                        f"longest silence <= {T['silence_warn']}s outside final {T['hold']}s (FAIL > {T['silence_fail']}s)",
                        PASS if worst <= T["silence_warn"] else (WARN if worst <= T["silence_fail"] else FAIL),
                        unit="s", detail=[f"silence {s:.2f}-{e:.2f}s ({o:.2f}s outside hold)" for s, e, o in sil],
                        n=len(sil), source=vs))
    return M, info


def number_fidelity(name: str, source: str, items: list[tuple[str, str, list[Num]]], index: FactIndex) -> Metric:
    """items: (location, preview text, numbers). Unmatched number = FAIL; a single record id with a
    FACTS prefix but outside every FACTS id range is an anonymous record stub (INFO, allowed by
    the FACTS hard rules)."""
    total, bad, stubs = 0, [], []
    for loc, preview, nums in items:
        for n in nums:
            total += 1
            if index.match(n):
                continue
            if n.is_single_id:
                stubs.append(f"INFO {loc}: record stub '{n.raw}' (not a fact number)")
            else:
                bad.append(f"{loc}: '{n.raw}' not in FACTS -> {collapse_ws(preview)[:110]}")
    if total == 0:
        return metric("content", name, "0 numbers", "every number matches a FACTS value", PASS, n=0, source=source,
                      note="no numbers in this source", basis_key="number_fidelity")
    return metric("content", name, f"{total - len(bad) - len(stubs)}/{total} matched",
                  "every number matches a FACTS value", FAIL if bad else PASS, detail=bad + stubs, n=total,
                  source=source, basis_key="number_fidelity")


def tag_metrics(srcs: list[Src], facts: dict[str, Fact], index: FactIndex, script_name: str) -> list[Metric]:
    invalid, uncovered, mismatched = [], [], []
    numeric = covered = 0
    for s in srcs:
        for t in s.tags:
            if t not in facts:
                invalid.append(f"{s.loc}: unknown fact id {t}")
        nums = [n for n in src_numbers(s, index.id_prefixes) if not (n.is_single_id and not index.match(n))]
        if not nums:
            continue
        numeric += 1
        valid = [t for t in s.tags if t in facts]
        if not valid:
            why = "only unknown ids" if s.tags else "no fact id"
            uncovered.append(f"{s.loc} [{s.kind}]: {why} -> {collapse_ws(s.text)[:100]}")
            continue
        covered += 1
        for n in nums:
            hits = index.match(n)
            if hits and hits != ["FACTS.md"] and not set(hits) & set(valid):
                mismatched.append(f"{s.loc} [{s.kind}]: '{n.raw}' is in {','.join(hits)}, line tagged {','.join(valid)}")
    share = covered / numeric if numeric else 1.0
    src = f"{script_name} (narration + on-screen)"
    return [
        metric("content", "tag_coverage", f"{covered}/{numeric} ({share:.0%})",
               f"100% of numeric lines tagged (WARN >= {T['tag_cov_warn']:.0%})",
               _v3(share >= 1.0, share >= T["tag_cov_warn"]), detail=uncovered, n=numeric, source=src),
        metric("content", "tag_validity", f"{len(invalid)} unknown ids", "every tagged id exists in FACTS",
               FAIL if invalid else PASS, detail=invalid, n=sum(len(s.tags) for s in srcs), source=src,
               basis_key="tag_coverage"),
        metric("content", "tag_consistency", f"{len(mismatched)} mismatches",
               "each number on a tagged line belongs to one of its tagged facts", WARN if mismatched else PASS,
               detail=mismatched, n=numeric, source=src, basis_key="tag_coverage"),
    ]


ATTRIBUTION_RE = re.compile(r"\b(verbatim|said|says|put it|quoted?|quotes|in (?:his|her|their) words)\b", re.IGNORECASE)


def _first_ci(s: str) -> str:
    return s[:1].lower() + s[1:]


def _quote_matches(cq: str, cf: str) -> str:
    """'exact' | 'case' | '' for quote core `cq` against fact core `cf`."""
    if _first_ci(cq) == _first_ci(cf):
        return "exact"
    if len(cq) >= 12:
        pat = rf"(?<!\w)[{re.escape(cq[0].lower())}{re.escape(cq[0].upper())}]{re.escape(cq[1:])}(?!\w)"
        if re.search(pat, cf):
            return "exact"
    if cq.lower() == cf.lower():
        return "case"
    return ""


def quote_fidelity(entries: list[tuple[str, str, list[str]]], facts: dict[str, Fact], source: str) -> Metric:
    """entries: (location, context, cells). context: 'quotation' (narration, subtitles, attributed or
    quoted-fact lines) or 'label' (other on-screen / drawn text). Rule R6:
      exact match -> ok; similar (>= cut) but altered -> FAIL for quotations, WARN for labels;
      unrelated -> WARN for narration/subtitle quotations, INFO for labels."""
    cands: list[tuple[str, str]] = []
    for f in facts.values():
        cands += [(f.id, q) for q in f.quotes]
        plain = collapse_ws(norm_quotes(f.value))
        if plain and not f.quotes:
            cands.append((f.id, plain))
    exact = total = 0
    bad, warn, info = [], [], []
    for loc, context, cells in entries:
        for cell in cells:
            for q in extract_quotes(cell):
                total += 1
                cq = quote_core(q)
                status, best = "", (0.0, "", "")
                for fid_, fq in cands:
                    st = _quote_matches(cq, quote_core(fq))
                    if st == "exact":
                        status = "exact"
                        break
                    if st == "case":
                        status, best = "case", (1.0, fid_, fq)
                        continue
                    ratio = difflib.SequenceMatcher(None, cq.lower(), quote_core(fq).lower()).ratio()
                    if ratio > best[0] and status != "case":
                        best = (ratio, fid_, fq)
                if status == "exact":
                    exact += 1
                elif status == "case":
                    warn.append(f"{loc}: case differs from {best[1]}: \"{q}\" vs \"{best[2]}\"")
                elif best[0] >= T["quote_similar"]:
                    msg = f"{loc}: altered quote of {best[1]} ({best[0]:.0%} similar): \"{q}\" vs \"{best[2]}\""
                    (bad if context.startswith("quotation") else warn).append(msg)
                elif context == "quotation:spoken":
                    warn.append(f"{loc}: quotation not in FACTS: \"{q[:80]}\"")
                else:
                    info.append(f"INFO {loc}: label \"{q[:80]}\" (wording not checked; numbers are)")
    verdict = FAIL if bad else (WARN if warn else PASS)
    return metric("content", "quote_fidelity", f"{exact}/{total} exact", "quotations match FACTS exactly "
                  "(smart/straight quotes and line breaks ignored)", verdict, detail=bad + warn + info,
                  n=total, source=source)


CAPTION_METRICS = {"caption_cps": "max CPS <= 17 (FAIL > 21)", "caption_duration": "1.0-7.0 s per cue",
                   "caption_line_length": "<= 42 chars per line", "caption_lines_per_cue": "<= 2",
                   "caption_timing": "no overlaps; gaps 0 or >= 2 frames; cues inside the video"}


def captions_skipped(reason: str = NO_CAPTIONS) -> list[Metric]:
    """No --srt: every caption metric is SKIPPED (burned-in / drawn text is checked via --drawn)."""
    return [metric("captions", name, None, thr, SKIPPED, note=reason, n=0, source="no SRT")
            for name, thr in CAPTION_METRICS.items()]


def caption_metrics(cues: list[Cue], duration: float | None, fps: float | None, srt_name: str) -> list[Metric]:
    g = "captions"
    if not cues:
        return [metric(g, "captions_parsed", 0, ">= 1 cue", FAIL, note="no cues parsed from SRT", n=0,
                       source=srt_name, basis_key="caption_timing")]
    nc = len(cues)
    M: list[Metric] = []
    cps = [(c, cue_cps(c)) for c in cues]
    worst = max(x[1] for x in cps)
    M.append(metric(g, "caption_cps", round(worst, 1), f"max CPS <= {T['cps_warn']:.0f} (FAIL > {T['cps_fail']:.0f})",
                    _v3(worst <= T["cps_warn"], worst <= T["cps_fail"]), unit="cps",
                    detail=[f"cue {c.index} ({c.start:.2f}s): {v:.1f} cps \"{c.text[:60]}\"" for c, v in cps
                            if v > T["cps_warn"]], n=nc, source=srt_name))
    durs = [c for c in cues if not (T["cue_min"] <= c.duration <= T["cue_max"])]
    M.append(metric(g, "caption_duration", f"{min(c.duration for c in cues):.2f}-{max(c.duration for c in cues):.2f}",
                    f"{T['cue_min']}-{T['cue_max']} s per cue", WARN if durs else PASS, unit="s",
                    detail=[f"cue {c.index}: {c.duration:.2f}s" for c in durs], n=nc, source=srt_name))
    longest = max((len(line) for c in cues for line in c.lines), default=0)
    M.append(metric(g, "caption_line_length", longest, f"<= {T['line_max']} chars per line",
                    PASS if longest <= T["line_max"] else WARN, unit="chars",
                    detail=[f"cue {c.index}: {len(line)} chars \"{line[:60]}\"" for c in cues for line in c.lines
                            if len(line) > T["line_max"]], n=sum(len(c.lines) for c in cues), source=srt_name))
    most = max(len(c.lines) for c in cues)
    M.append(metric(g, "caption_lines_per_cue", most, f"<= {T['lines_max']}", PASS if most <= T["lines_max"] else FAIL,
                    unit="lines", detail=[f"cue {c.index}: {len(c.lines)} lines" for c in cues
                                          if len(c.lines) > T["lines_max"]], n=nc, source=srt_name))
    min_gap = T["gap_frames"] / fps if fps else T["gap_frames"] / 24.0
    overlaps, flicker, broken, gaps = [], [], [], []
    for c in cues:
        if c.end <= c.start:
            broken.append(f"cue {c.index}: end {c.end:.3f}s <= start {c.start:.3f}s")
    for a, b in itertools.pairwise(cues):
        gap = b.start - a.end
        gaps.append(gap)
        if gap < -0.0005:
            overlaps.append(f"cue {a.index}->{b.index}: overlap {-gap:.3f}s")
        elif 0.0005 < gap < min_gap - 0.0005:
            flicker.append(f"cue {a.index}->{b.index}: gap {gap:.3f}s (< {T['gap_frames']} frames = {min_gap:.3f}s; "
                           "close it to 0 or open it to 2 frames)")
    past = [f"cue {c.index} ends {c.end:.2f}s after video end {duration:.2f}s" for c in cues
            if duration and c.end > duration + 0.05]
    M.append(metric(g, "caption_timing", f"{len(overlaps)} overlaps, {len(flicker)} sub-2-frame gaps",
                    f"no overlaps; gaps 0 or >= {T['gap_frames']} frames; cues inside the video",
                    FAIL if overlaps or broken else (WARN if flicker or past else PASS),
                    detail=broken + overlaps + flicker + past, n=max(0, nc - 1), source=srt_name))
    return M


def speech_rate(narration: list[Src], cues: list[Cue], duration: float | None, script_name: str) -> Metric:
    words = sum(count_words(s.text) for s in narration)
    thr = f"{T['wpm_lo']:.0f}-{T['wpm_hi']:.0f} wpm (WARN +/-{T['wpm_margin']:.0f})"
    secs, basis = speech_seconds(cues), "caption-covered time"
    if not secs and duration:
        secs, basis = max(1.0, duration - T["hold"]), "video duration minus final hold"
    if not secs or not words:
        return metric("content", "speech_rate", None, thr, SKIPPED, n=words, source=script_name,
                      note=NO_NARRATION if not words else "no timing (no cues, no duration)")
    wpm = words / (secs / 60.0)
    ok = T["wpm_lo"] <= wpm <= T["wpm_hi"]
    near = T["wpm_lo"] - T["wpm_margin"] <= wpm <= T["wpm_hi"] + T["wpm_margin"]
    return metric("content", "speech_rate", round(wpm, 1), thr, _v3(ok, near), unit="wpm", n=words,
                  source=f"{script_name} narration + " + ("SRT timing" if cues else "video duration"),
                  note=f"{words} words (count_words) / {secs:.1f}s {basis}")


def drawn_metrics(drawn: list[Drawn], index: FactIndex, src_name: str, height: int | None,
                  profile: str = "default") -> list[Metric]:
    M = [number_fidelity("number_fidelity_drawn", src_name,
                         [(d.loc, d.text, extract_numbers(d.text, index.id_prefixes)) for d in drawn], index)]
    small = [d for d in drawn if 0 < d.px < T["drawn_min_px"] and d.t_end - d.t_start >= T["drawn_min_on"]]
    M.append(metric("content", "drawn_text_size", min((d.px for d in drawn if d.px > 0), default=None),
                    f"no text < {T['drawn_min_px']} px on screen >= {T['drawn_min_on']:.0f} s", WARN if small else PASS,
                    unit="px", detail=[f"{d.loc}: {d.px:g}px for {d.t_end - d.t_start:.1f}s \"{d.text[:50]}\"" for d in small],
                    n=len(drawn), source=src_name,
                    note=f"{len(drawn)} distinct strings from {sum(d.draws for d in drawn)} draw records"
                         + (f"; video height {height}px" if height else "")))
    if profile == "linkedin_4x5":
        scale = T["mobile_pt_width"] / T["mobile_ref_px"]
        on = [d for d in drawn if d.px > 0 and d.t_end - d.t_start >= T["drawn_min_on"]]
        tiny = [d for d in on if d.px * scale < T["mobile_min_pt"]]
        least = min((d.px for d in on), default=None)
        M.append(metric("content", "drawn_text_mobile", None if least is None else round(least * scale, 1),
                        f"no text < {T['mobile_min_pt']:g} pt at px x {T['mobile_pt_width']}/{T['mobile_ref_px']} "
                        f"(on screen >= {T['drawn_min_on']:.0f} s)", WARN if tiny else PASS, unit="pt",
                        detail=[f"{d.loc}: {d.px:g}px = {d.px * scale:.1f} pt \"{d.text[:50]}\"" for d in tiny],
                        n=len(on), source=src_name, note="profile linkedin_4x5; mobile-feed readability proxy"))
    return M


# =========================================================================================
# AI metrics: ASR
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
    """(result, interpreter) or (None, reason). Tries this interpreter, then `asr_python`."""
    interpreters: list[str] = []
    try:
        import faster_whisper  # noqa: F401
        interpreters.append(sys.executable)
    except ImportError:
        pass  # not installed here; the external interpreter below is the fallback
    if asr_python and Path(asr_python).exists():
        try:
            chk = run([asr_python, "-I", "-c", "import faster_whisper"], timeout=60)
            if chk.returncode == 0:
                interpreters.append(asr_python)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"asr interpreter check failed: {exc}", file=sys.stderr)
    if not interpreters:
        return None, f"faster_whisper not importable in {sys.executable} or {asr_python or '(no --asr-python)'}"
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
            return json.loads(r.stdout.strip().splitlines()[-1]), py
        except (ValueError, IndexError) as exc:
            reasons.append(f"{py}: bad output ({exc})")
    return None, "; ".join(reasons)


def asr_metrics(video: Path, narration: list[Src], cues: list[Cue], index: FactIndex, args: argparse.Namespace,
                versions: dict[str, str], has_audio: bool, srt_name: str) -> tuple[list[Metric], str]:
    wer_thr = f"<= {T['wer_pass']:.0%} (WARN <= {T['wer_warn']:.0%})"
    aud_thr = "every subtitle number heard in the transcript"
    if not narration:
        data, how = None, NO_NARRATION
    elif not has_audio:
        data, how = None, "no audio stream"
    else:
        data, how = transcribe(video, args.asr_model, args.asr_lang, args.asr_python)
    if data is None:
        return [metric("ai", "asr_wer", None, wer_thr, SKIPPED, note=how, source=video.name),
                metric("ai", "asr_numbers_audible", None, aud_thr, SKIPPED, note=how, source=srt_name,
                       basis_key="asr_wer")], ""
    versions["faster_whisper"] = f"{data.get('version', '?')} ({how}, model {args.asr_model})"
    hyp_text = " ".join(s["text"] for s in data.get("segments", []))
    ref, hyp = normalize_for_wer(" ".join(s.text for s in narration)), normalize_for_wer(hyp_text)
    wer, edits, n = word_error_rate(ref, hyp)
    M = [metric("ai", "asr_wer", round(wer * 100, 2), wer_thr, _v3(wer <= T["wer_pass"], wer <= T["wer_warn"]),
                unit="%", n=n, source=f"{video.name} vs SCRIPT narration",
                note=f"{edits} edits over {n} normalised reference tokens; language {data.get('language')}")]
    heard = spoken_numbers(hyp_text)
    checked, missing = 0, []
    for c in cues:
        for num in extract_numbers(c.text, index.id_prefixes):
            if num.kind == "date":
                continue
            checked += 1
            if not (num.canon in heard or all(p in heard for p in num.parts)):
                missing.append(f"cue {c.index} ({c.start:.2f}s): '{num.raw}' not heard")
    if checked == 0:
        M.append(metric("ai", "asr_numbers_audible", "0 checked", aud_thr, SKIPPED, n=0, source=srt_name,
                        note=NO_CAPTIONS if not srt_name or srt_name == "no SRT" else "no digits in the SRT to check",
                        basis_key="asr_wer"))
    else:
        M.append(metric("ai", "asr_numbers_audible", f"{checked - len(missing)}/{checked}", aud_thr,
                        FAIL if missing else PASS, detail=missing, n=checked, source=f"{srt_name} vs ASR transcript",
                        note="transcript number words converted to digits before matching", basis_key="asr_wer"))
    return M, hyp_text


# =========================================================================================
# AI metrics: Jev (two-step, repeated, calibrated)
# =========================================================================================

def jev_questions(jev: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    step1 = {
        "claim": jev.noul(
            "Does `line` make a factual claim: a number, statistic, finding, or checkable statement about "
            "the data, the users or the product?",
            "the line asserts something that could be checked against a fact sheet",
            "the line is rhetoric, a transition, a question, a greeting, a slogan or an instruction to the viewer"),
        "contradiction": jev.noul(
            "Does `line` contradict `facts`?",
            "the line states a number, quote or finding that conflicts with a value written in facts",
            "nothing in the line conflicts with facts (claims that facts does not mention are not contradictions)"),
    }
    step2 = {
        "entailed": jev.noul(
            "Is every factual claim in `line` stated in the fact sheet `facts`? Judge entailment only: is it "
            "written in facts, verbatim or as a faithful paraphrase? Do not judge whether it is true in the world.",
            "each number and claim in the line appears in facts with the same value and meaning",
            "at least one number or claim in the line is absent from facts or differs from it"),
    }
    return step1, step2


def questions_hash(*qs: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(qs, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run_jev(lines: list[str], sheet: str, repeats: int, claim_override: list[bool] | None = None,
            all_claims: bool = False) -> dict[str, Any]:
    """Two-step Jev pass, `repeats` times. Step 1 (claim, contradiction) on every line; step 2
    (entailment) only on claim lines: Jev's claim mean >= T['jev_claim'], OR claim_override[i] (fact tag
    or number, so Jev cannot silence a factual line), OR all_claims (calibration)."""
    from execution.modules import jev_client as jev
    if not jev.available():
        return {"error": "no OpenRouter key"}
    q1, q2 = jev_questions(jev)
    states = [{"facts": sheet, "line": t} for t in lines]
    out: dict[str, Any] = {"claim": [[] for _ in lines], "contradiction": [[] for _ in lines],
                           "entailed": [[] for _ in lines], "models": set(), "cost": 0.0, "errors": [],
                           "calls": 0, "prompt_hash": questions_hash(q1, q2)}

    def absorb(results: list[Any], idx: list[int], names: list[str]) -> None:
        for i, r in zip(idx, results):
            out["calls"] += 1
            out["cost"] += r.cost_usd
            if not r.ok:
                out["errors"].append(r.error or "?")
                continue
            if r.model:
                out["models"].add(r.model)
            for nm in names:
                out[nm][i].append(r.noul(nm))

    for _ in range(repeats):
        absorb(jev.decide_many(states, q1, workers=8), list(range(len(lines))), ["claim", "contradiction"])
    mean = [sum(v) / len(v) if v else 0.0 for v in out["claim"]]
    claim_idx = [i for i in range(len(lines)) if all_claims or mean[i] >= T["jev_claim"]
                 or (claim_override and claim_override[i])]
    for _ in range(repeats):
        if claim_idx:
            absorb(jev.decide_many([states[i] for i in claim_idx], q2, workers=8), claim_idx, ["entailed"])
    out["claim_idx"] = claim_idx
    out["models"] = sorted(out["models"])
    jev.append_ledger({"caller": "film_eval", "items": len(lines), "repeats": repeats, "calls": out["calls"],
                       "cost_usd": out["cost"], "errors": len(out["errors"])}, path=_ROOT / ".tmp" / "jev_ledger.jsonl")
    return out


def _mean(v: list[float]) -> float:
    return sum(v) / len(v) if v else float("nan")


def _spread(v: list[float]) -> float:
    return (max(v) - min(v)) if v else float("nan")


def load_jev_calibration() -> dict[str, Any]:
    try:
        return json.loads(JEV_THRESHOLDS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def jev_metrics(narration: list[Src], facts: dict[str, Fact], index: FactIndex, versions: dict[str, str],
                repeats: int, script_name: str) -> list[Metric]:
    cal = load_jev_calibration()
    t_ent = float(cal.get("entailed", {}).get("threshold", T["jev_entail"]))
    t_con = float(cal.get("contradiction", {}).get("threshold", T["jev_contra"]))
    T["jev_claim"] = float(cal.get("claim", {}).get("threshold", T["jev_claim"]))   # used by run_jev step 1
    auroc = float(cal.get("entailed", {}).get("auroc", 0.0))
    gate = auroc >= T["jev_auroc_gate"]
    thr = (f"entailment mean >= {t_ent:.3f} per claim line (calibrated, AUROC {auroc:.2f}); "
           + ("FAIL when flagged" if gate else "advisory (AUROC < 0.9): max WARN"))
    src = f"{script_name} narration"
    if not narration:
        return [metric("ai", "jev_entailment", None, thr, SKIPPED, note=NO_NARRATION, source=src, basis_key="jev")]
    try:
        res = run_jev([s.text for s in narration], fact_sheet_text(facts), repeats,
                      claim_override=[bool(s.tags) or bool(src_numbers(s, index.id_prefixes)) for s in narration])
    except ImportError as exc:
        return [metric("ai", "jev_entailment", None, thr, SKIPPED, note=f"jev_client import failed: {exc}",
                       source=src, basis_key="jev")]
    if res.get("error") or not res["models"]:
        reason = res.get("error") or (res["errors"][0] if res.get("errors") else "no answers")
        return [metric("ai", "jev_entailment", None, thr, SKIPPED, note=f"Jev: {reason}", source=src, basis_key="jev")]
    versions["jev_model"] = ", ".join(res["models"])
    stale = cal.get("prompt_hash") and cal.get("prompt_hash") != res["prompt_hash"]
    model_drift = cal.get("models") and sorted(cal.get("models")) != res["models"]
    common = (f"N={repeats} repeats; cost ${res['cost']:.6f}; {res['calls']} calls; model {versions['jev_model']}; "
              f"prompt {res['prompt_hash']}" + ("; CALIBRATION STALE (prompt changed)" if stale else "")
              + ("; calibration used a different model" if model_drift else "")
              + (f"; {len(res['errors'])} errors" if res["errors"] else ""))
    M: list[Metric] = []
    ent_means, spreads, flagged = [], [], []
    for i in res["claim_idx"]:
        v = res["entailed"][i]
        if not v:
            continue
        m_, sp = _mean(v), _spread(v)
        ent_means.append(m_)
        spreads.append(sp)
        if m_ < t_ent:
            s = narration[i]
            flagged.append(f"{s.loc}: entailment {m_:.2f} (range {min(v):.2f}-{max(v):.2f}) {s.text[:90]}")
    verdict = (FAIL if gate else WARN) if flagged else PASS
    M.append(metric("ai", "jev_entailment", round(_mean(ent_means), 3) if ent_means else None, thr, verdict,
                    unit="mean noul", detail=flagged, n=len(ent_means), source=src, basis_key="jev",
                    note=f"mean spread across repeats {_mean(spreads):.3f} (max {max(spreads, default=0):.3f}); " + common))
    con_flags, con_means = [], []
    for i, v in enumerate(res["contradiction"]):
        if not v:
            continue
        con_means.append(_mean(v))
        if _mean(v) >= t_con:
            s = narration[i]
            con_flags.append(f"{s.loc}: contradiction {_mean(v):.2f} (range {min(v):.2f}-{max(v):.2f}) {s.text[:90]}")
    con_auroc = float(cal.get("contradiction", {}).get("auroc", 0.0))
    con_gate = con_auroc >= T["jev_auroc_gate"]
    M.append(metric("ai", "jev_contradiction", f"{len(con_flags)} flagged",
                    f"no line >= {t_con:.3f} (calibrated, AUROC {con_auroc:.2f}); "
                    + ("FAIL when flagged" if con_gate else "advisory: max WARN"),
                    (FAIL if con_gate else WARN) if con_flags else PASS, detail=con_flags, n=len(con_means),
                    source=src, basis_key="jev", note=f"max {max(con_means, default=0):.2f}"))
    claim_means = [_mean(v) for v in res["claim"]]
    jev_claims = sum(1 for c in claim_means if c >= T["jev_claim"])
    overridden = [narration[i].loc for i in res["claim_idx"] if claim_means[i] < T["jev_claim"]]
    M.append(metric("ai", "jev_claims", f"{len(res['claim_idx'])}/{len(narration)} claim lines",
                    f"claim noul >= {T['jev_claim']} or fact tag/number", PASS, n=len(narration), source=src,
                    basis_key="jev", detail=[f"INFO {loc}: Jev said no claim; checked anyway (tag/number)" for loc in overridden],
                    note=f"Jev alone: {jev_claims}; mean claim spread {_mean([_spread(v) for v in res['claim'] if v]):.3f}"))
    return M


# =========================================================================================
# Calibration
# =========================================================================================

def auroc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney AUROC: P(score of a positive > score of a negative), ties count half."""
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def best_threshold(scores: list[float], labels: list[int]) -> dict[str, Any]:
    """Threshold maximising Youden's J (TPR - FPR); predict positive when score >= t."""
    cands = sorted(set(scores))
    cuts = [0.0] + [(a + b) / 2 for a, b in itertools.pairwise(cands)] + [1.0001]
    best: dict[str, Any] = {}
    P = sum(labels)
    N = len(labels) - P
    for t in cuts:
        tp = sum(1 for s, y in zip(scores, labels) if s >= t and y)
        fp = sum(1 for s, y in zip(scores, labels) if s >= t and not y)
        fn, tn = P - tp, N - fp
        j = (tp / P if P else 0) - (fp / N if N else 0)
        if not best or j > best["youden_j"] + 1e-12:
            best = {"threshold": round(t, 4), "youden_j": round(j, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return best


def calibrate(labels_csv: Path, facts_path: Path, out_md: Path, repeats: int) -> int:
    rows = list(csv.DictReader(labels_csv.read_text(encoding="utf-8").splitlines()))
    need = {"id", "category", "line", "claim", "supported", "contradiction"}
    if not rows or not need <= set(rows[0]):
        print(f"film_eval: {labels_csv} needs columns {sorted(need)}", file=sys.stderr)
        return 2
    facts = parse_facts(facts_path.read_text(encoding="utf-8"))
    res = run_jev([r["line"] for r in rows], fact_sheet_text(facts), repeats, all_claims=True)
    if res.get("error") or not res["models"]:
        print(f"film_eval: Jev unavailable: {res.get('error') or res.get('errors', ['?'])[:1]}", file=sys.stderr)
        return 1
    def col(name: str) -> list[float]:
        return [_mean(v) for v in res[name]]
    claim_s, ent_s, con_s = col("claim"), col("entailed"), col("contradiction")
    y_claim = [int(r["claim"]) for r in rows]
    claim_rows = [i for i, r in enumerate(rows) if r["claim"] == "1"]
    y_sup = [int(rows[i]["supported"]) for i in claim_rows]
    y_con = [int(rows[i]["contradiction"]) for i in claim_rows]
    s_ent = [ent_s[i] for i in claim_rows]
    s_con = [con_s[i] for i in claim_rows]
    report: dict[str, Any] = {"date": dt.datetime.now(dt.timezone.utc).date().isoformat(), "models": res["models"], "repeats": repeats,
                              "prompt_hash": res["prompt_hash"], "labels": str(labels_csv.name),
                              "facts_sha256": hashlib.sha256(facts_path.read_bytes()).hexdigest()[:16],
                              "cost_usd": round(res["cost"], 6)}
    for name, scores, ys in (("claim", claim_s, y_claim), ("entailed", s_ent, y_sup), ("contradiction", s_con, y_con)):
        pos = [s for s, y in zip(scores, ys) if y]
        neg = [s for s, y in zip(scores, ys) if not y]
        b = best_threshold(scores, ys)
        report[name] = {"auroc": round(auroc(pos, neg), 4), "n": len(ys), "n_pos": len(pos), "n_neg": len(neg),
                        "min_pos": round(min(pos, default=float("nan")), 4),
                        "max_neg": round(max(neg, default=float("nan")), 4), **b}
    # recall-95 point for entailment: lowest cut that still flags >= 95 % of unsupported lines
    neg_ent = sorted(s for s, y in zip(s_ent, y_sup) if not y)
    if neg_ent:
        k = max(0, round(0.95 * len(neg_ent)) - 1)
        t95 = neg_ent[k] + 1e-4
        pos_ent = [s for s, y in zip(s_ent, y_sup) if y]
        report["entailed"]["recall95_threshold"] = round(t95, 4)
        report["entailed"]["recall95_false_flags"] = sum(1 for s in pos_ent if s < t95)
    spreads = [_spread(v) for v in res["entailed"] if v] + [_spread(v) for v in res["claim"] if v]
    report["mean_repeat_spread"] = round(_mean(spreads), 4)
    report["max_repeat_spread"] = round(max(spreads, default=0.0), 4)
    JEV_THRESHOLDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JEV_THRESHOLDS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_calibration_md(report, rows, claim_s, ent_s, con_s, res), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("claim", "entailed", "contradiction")}, indent=1))
    print(f"wrote {out_md} and {JEV_THRESHOLDS_FILE}")
    return 0


def render_calibration_md(rep: dict[str, Any], rows: list[dict[str, str]], claim_s: list[float],
                          ent_s: list[float], con_s: list[float], res: dict[str, Any]) -> str:
    e, c, k = rep["entailed"], rep["contradiction"], rep["claim"]
    out = ["# Jev support calibration (film_eval)", "",
           (f"Date {rep['date']} · model {', '.join(rep['models'])} · N={rep['repeats']} repeats · "
            f"prompt {rep['prompt_hash']} · FACTS sha256 {rep['facts_sha256']} · cost ${rep['cost_usd']}"), "",
           (f"Labelled set: `{rep['labels']}`, {len(rows)} lines hand-labelled against the case FACTS.md "
            "(state.facts). Scores are the mean noul over the repeats. Threshold = max Youden J; "
            "a line is predicted positive when its score >= threshold."), "",
           "| Question | n (pos/neg) | AUROC | Best threshold | TP | FP | FN | TN |", "|---|---|---|---|---|---|---|---|"]
    for name, d in (("(a) claim: makes a factual claim", k), ("(b) entailed: stated in the fact sheet", e),
                    ("(c) contradiction", c)):
        out.append(f"| {name} | {d['n']} ({d['n_pos']}/{d['n_neg']}) | {d['auroc']:.3f} | {d['threshold']} | "
                   f"{d['tp']} | {d['fp']} | {d['fn']} | {d['tn']} |")
    out += ["", "(b) and (c) are scored on the claim lines only (gold `claim=1`), as in the film run. "
            "Separation margin (lowest positive score vs highest negative): "
            + "; ".join(f"{nm} {d['min_pos']} vs {d['max_neg']}" for nm, d in (("claim", k), ("entailed", e),
                                                                             ("contradiction", c))), ""]
    if "recall95_threshold" in e:
        out.append(f"Recall-95 point for (b): flag below {e['recall95_threshold']} catches >= 95 % of unsupported "
                   f"lines with {e['recall95_false_flags']} supported lines falsely flagged.")
    out += [f"Repeat stability: mean spread {rep['mean_repeat_spread']}, max {rep['max_repeat_spread']} (noul units).",
            "", ("film_eval reads `jev_support_thresholds.json`: entailment flags a claim line whose mean is below the "
                 "(b) threshold, contradiction flags a line at or above the (c) threshold. Flags FAIL only when that "
                 "question's AUROC >= 0.9, otherwise they WARN."), "",
            "## Per-category means", "", "| Category | n | claim | entailed | contradiction |", "|---|---|---|---|---|"]
    cats: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        cats.setdefault(r["category"], []).append(i)
    for cat, idx in cats.items():
        out.append(f"| {cat} | {len(idx)} | {_mean([claim_s[i] for i in idx]):.2f} | "
                   f"{_mean([ent_s[i] for i in idx]):.2f} | {_mean([con_s[i] for i in idx]):.2f} |")
    t = e["threshold"]
    errs = [(r, ent_s[i]) for i, r in enumerate(rows) if r["claim"] == "1"
            and ((ent_s[i] >= t) != (r["supported"] == "1"))]
    out += ["", f"## Entailment errors at threshold {t}", ""]
    out += [f"- {r['id']} [{r['category']}] gold supported={r['supported']} score {s:.2f}: {r['line']}" for r, s in errs] or ["- none"]
    return "\n".join(out) + "\n"


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


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.match(r"\s*(-?\d+(?:\.\d+)?)(?=[\s/%(]|$)", v)
        return float(m.group(1)) if m else None
    return None


def compare_reports(old: dict[str, Any], new_metrics: list[Metric]) -> list[dict[str, Any]]:
    """Per-metric delta (new - old) where both values are numeric, plus verdict change."""
    om = {m["name"]: m for m in old.get("metrics", [])}
    rows = []
    for m in new_metrics:
        o = om.pop(m.name, None)
        if o is None:
            rows.append({"name": m.name, "old": "(new)", "new": _fmt(m.value, m.unit), "delta": "",
                         "verdict": f"- -> {m.verdict}"})
            continue
        a, b = _num(o.get("value")), _num(m.value)
        delta = f"{b - a:+g}" if a is not None and b is not None and not (math.isnan(a) or math.isnan(b)) else ""
        rows.append({"name": m.name, "old": _fmt(o.get("value"), o.get("unit", "")), "new": _fmt(m.value, m.unit),
                     "delta": delta, "verdict": f"{o.get('verdict')} -> {m.verdict}"})
    for name, o in om.items():
        rows.append({"name": name, "old": _fmt(o.get("value"), o.get("unit", "")), "new": "(removed)",
                     "delta": "", "verdict": f"{o.get('verdict')} -> -"})
    return rows


def render_md(report: dict[str, Any], metrics: list[Metric]) -> str:
    out = [f"# Film evaluation: {Path(report['inputs']['video']['path']).name}", "",
           (f"**Overall: {report['overall']}** · film_eval {report['version']} · run {report['run_timestamp']} · "
            f"sha256 `{report['inputs']['video'].get('sha256', '?')}`"), "",
           "| Group | Metric | Value | n | Source | Threshold | Basis | Verdict |",
           "|---|---|---|---|---|---|---|---|"]
    for m in metrics:
        cells = [m.group, m.name, _fmt(m.value, m.unit), "-" if m.n is None else str(m.n), m.source, m.threshold,
                 m.basis or "-", f"**{m.verdict}**"]
        out.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    findings = [m for m in metrics if m.verdict in (FAIL, WARN) and (m.detail or m.note)]
    if findings:
        out += ["", "## Findings"]
        for m in findings:
            out += ["", f"### {m.verdict} · {m.name}"]
            if m.note:
                out.append(f"_{m.note}_")
            real = [d for d in m.detail if not d.startswith("INFO ")]
            out += [f"- {d}" for d in real[:25]]
            if len(real) > 25:
                out.append(f"- ... {len(real) - 25} more in the JSON report")
    infos = [(m.name, d) for m in metrics for d in m.detail if d.startswith("INFO ")]
    if infos:
        out += ["", "## Info (not counted)"] + [f"- {n}: {d[5:]}" for n, d in infos[:40]]
    skipped = [m for m in metrics if m.verdict == SKIPPED]
    if skipped:
        out += ["", "## Skipped"] + [f"- {m.name}: {m.note}" for m in skipped]
    notes = [m for m in metrics if m.verdict == PASS and m.note]
    if notes:
        out += ["", "## Notes"] + [f"- {m.name}: {m.note}" for m in notes]
    if report.get("compare"):
        out += ["", f"## Delta vs {report['compare']['against']}", "", "| Metric | Old | New | Delta | Verdict |",
                "|---|---|---|---|---|"]
        out += [f"| {r['name']} | {r['old']} | {r['new']} | {r['delta']} | {r['verdict']} |".replace("||", "|")
                for r in report["compare"]["rows"]]
    out += ["", "## Tool versions"] + [f"- {k}: {v}" for k, v in report["tool_versions"].items()]
    return "\n".join(out) + "\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], list[Metric]]:
    if args.hold is not None:
        T["hold"] = args.hold
    if args.max_mb is not None:
        T["max_mb"] = args.max_mb
    video, script_p, facts_p = (Path(p) for p in (args.video, args.script, args.facts))
    srt_p = Path(args.srt) if args.srt else None
    profile = getattr(args, "profile", "default") or "default"
    facts_text = facts_p.read_text(encoding="utf-8")
    facts = parse_facts(facts_text)
    index = FactIndex(facts, facts_text)
    script_text = script_p.read_text(encoding="utf-8")
    cues = parse_srt(srt_p.read_text(encoding="utf-8", errors="replace")) if srt_p else []
    srt_end = max((c.end for c in cues), default=0.0)
    versions = {"film_eval": VERSION, "python": platform.python_version(),
                "ffmpeg": tool_version("ffmpeg"), "ffprobe": tool_version("ffprobe")}
    sn, srn = script_p.name, (srt_p.name if srt_p else "no SRT")

    metrics: list[Metric] = []
    tech, vinfo = technical_metrics(video, srt_end, args.expect_sha256, profile)
    metrics += tech
    duration = vinfo.get("duration")
    if not facts:
        metrics.append(metric("content", "facts_parsed", 0, ">= 1 fact row", FAIL, note=f"no fact rows in {facts_p}",
                              n=0, source=facts_p.name))

    srcs, mode = script_sources(script_text)
    narration = [s for s in srcs if s.kind == "narration"]
    onscreen = [s for s in srcs if s.kind == "onscreen"]
    P = index.id_prefixes
    if narration:
        metrics.append(number_fidelity("number_fidelity_narration", f"{sn} narration ({mode})",
                                       [(s.loc, s.text, src_numbers(s, P)) for s in narration], index))
    else:
        metrics.append(metric("content", "number_fidelity_narration", None, "every number matches a FACTS value",
                              SKIPPED, note=NO_NARRATION, n=0, source=f"{sn} narration ({mode})",
                              basis_key="number_fidelity"))
    if onscreen or mode == "sections":
        metrics.append(number_fidelity("number_fidelity_onscreen", f"{sn} on-screen text",
                                       [(s.loc, s.text, src_numbers(s, P)) for s in onscreen], index))
    if srt_p:
        metrics.append(number_fidelity("number_fidelity_srt", srn,
                                       [(f"SRT:{c.index}", c.text, extract_numbers(c.text, P)) for c in cues], index))
    else:
        metrics.append(metric("content", "number_fidelity_srt", None, "every number matches a FACTS value", SKIPPED,
                              note=NO_CAPTIONS, n=0, source=srn, basis_key="number_fidelity"))
    drawn: list[Drawn] = []
    if args.drawn:
        dp = Path(args.drawn)
        try:
            drawn = load_drawn(dp)
            metrics += drawn_metrics(drawn, index, dp.name, vinfo.get("height"), profile)
        except (ValueError, TypeError, OSError) as exc:
            metrics.append(metric("content", "number_fidelity_drawn", None, "-", FAIL, note=f"unreadable: {exc}",
                                  source=dp.name, basis_key="number_fidelity"))
    metrics += tag_metrics(srcs, facts, index, sn)

    quoted_facts = {f.id for f in facts.values() if f.quotes}
    entries: list[tuple[str, str, list[str]]] = [(s.loc, "quotation:spoken", s.cells) for s in narration]
    for s in onscreen:
        quoted = ATTRIBUTION_RE.search(s.raw) or set(s.tags) & quoted_facts
        entries.append((s.loc, "quotation:onscreen" if quoted else "label", s.cells))
    if cues:
        entries.append(("SRT", "quotation:spoken", [" ".join(c.text for c in cues)]))   # quotes span cues
    entries += [(d.loc, "label", [d.text]) for d in drawn]
    metrics.append(quote_fidelity(entries, facts, sn + (f" + {srn}" if srt_p else "") + (" + drawn" if drawn else "")))

    deny = load_deny(args.deny_names, Path(args.deny) if args.deny else None)
    pii_src = ([("SRT", c.index, c.text) for c in cues] + [(sn, n + 1, ln) for n, ln in enumerate(script_text.splitlines())]
               + [("drawn", d.k, d.text) for d in drawn])
    metrics += caption_metrics(cues, duration, vinfo.get("fps"), srn) if srt_p else captions_skipped()
    metrics.append(speech_rate(narration, cues, duration, sn))

    transcript = ""
    if args.asr:
        asr_m, transcript = asr_metrics(video, narration, cues, index, args, versions,
                                        bool(vinfo.get("has_audio", True)), srn)
        metrics += asr_m
    if transcript:
        pii_src.append(("ASR", 0, transcript))
    hits = pii_scan(pii_src, deny)
    metrics.append(metric("content", "pii_scan", f"{len(hits)} hits", f"no e-mail, phone or denied name ({', '.join(deny)})",
                          FAIL if hits else PASS, detail=hits, n=len(pii_src),
                          source=(f"{srn} + " if srt_p else "") + sn + (" + drawn" if drawn else "")
                          + (" + ASR" if transcript else "")))
    metrics[-1].basis = "FACTS hard rules (no member data)"
    if args.jev:
        metrics += jev_metrics(narration, facts, index, versions, args.jev_repeats, sn)
    order = {"technical": 0, "content": 1, "captions": 2, "ai": 3}
    metrics.sort(key=lambda m: order.get(m.group, 9))

    report: dict[str, Any] = {
        "tool": "film_eval", "version": VERSION,
        "run_timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall": overall(metrics),
        "inputs": {
            "video": {"path": str(video.resolve()), **vinfo},
            "srt": ({"path": str(srt_p.resolve()), "sha256": _sha(srt_p), "cues": len(cues)} if srt_p
                    else {"path": None, "note": NO_CAPTIONS, "cues": 0}),
            "script": {"path": str(script_p.resolve()), "sha256": _sha(script_p), "mode": mode,
                       "narration_items": len(narration), "onscreen_items": len(onscreen)},
            "facts": {"path": str(facts_p.resolve()), "sha256": _sha(facts_p), "facts": len(facts)},
        },
        "profile": profile, "thresholds": dict(T), "threshold_sources": dict(SOURCES),
        "tool_versions": versions,
        "metrics": [asdict(m) for m in metrics],
    }
    if args.drawn:
        report["inputs"]["drawn"] = {"path": str(Path(args.drawn).resolve()), "items": len(drawn)}
    if transcript:
        report["asr_transcript"] = transcript
    if args.compare:
        old = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        report["compare"] = {"against": f"{Path(args.compare).name} (film_eval {old.get('version', '?')}, "
                                        f"sha256 {str(old.get('inputs', {}).get('video', {}).get('sha256', '?'))[:16]})",
                             "rows": compare_reports(old, metrics)}
    return report, metrics


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic evaluation of a short explainer film.")
    p.add_argument("--video")
    p.add_argument("--srt", help="captions; optional (absent = caption metrics SKIPPED, 'no captions supplied')")
    p.add_argument("--script")
    p.add_argument("--facts")
    p.add_argument("--drawn", help="renderer log of every drawn string: [{text, t_start, t_end, x, y, px}]")
    p.add_argument("--profile", choices=("default", "linkedin_4x5"), default="default",
                   help="delivery profile: linkedin_4x5 accepts 1080x1350 and adds the mobile drawn-text WARN")
    p.add_argument("--asr", action="store_true", help="faster-whisper WER + numbers audible (SKIPPED if unavailable)")
    p.add_argument("--asr-model", default="small.en")
    p.add_argument("--asr-lang", default="en", help="language code; empty string = auto-detect")
    p.add_argument("--asr-python", default=os.environ.get("FILM_EVAL_ASR_PYTHON", "/tmp/ext/venv/bin/python"),
                   help="fallback interpreter with faster_whisper (env FILM_EVAL_ASR_PYTHON)")
    p.add_argument("--jev", action="store_true", help="Jev claim / entailment / contradiction per narration line")
    p.add_argument("--jev-repeats", type=int, default=3)
    p.add_argument("--calibrate", help="labelled CSV: run the Jev questions and write the calibration")
    p.add_argument("--calib-out", default=str(EVAL_DATA / "jev_support_calibration.md"))
    p.add_argument("--deny", help="file with one denied name per line (added to --deny-names)")
    p.add_argument("--deny-names", default=DEFAULT_DENY_NAMES, help="comma-separated denied names")
    p.add_argument("--hold", type=float, default=None, help=f"final hold seconds (default {T['hold']})")
    p.add_argument("--max-mb", type=float, default=None, help=f"max file size MB (default {T['max_mb']})")
    p.add_argument("--expect-sha256", help="FAIL unless the video's sha256 equals this (re-render determinism)")
    p.add_argument("--compare", help="older film_eval JSON report: print per-metric deltas")
    p.add_argument("--out", help="JSON report path")
    p.add_argument("--md", help="markdown report path")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.calibrate:
        missing = [p for p in (args.calibrate, args.facts) if not p or not Path(p).is_file()]
        if missing or not args.facts:
            print("film_eval: --calibrate needs an existing labels CSV and --facts", file=sys.stderr)
            return 2
        return calibrate(Path(args.calibrate), Path(args.facts), Path(args.calib_out), max(1, args.jev_repeats))
    req = ("video", "script", "facts")
    missing = [f"--{k} {getattr(args, k)}" for k in req if not getattr(args, k) or not Path(getattr(args, k)).is_file()]
    for opt in ("srt", "deny", "drawn", "compare"):
        if getattr(args, opt) and not Path(getattr(args, opt)).is_file():
            missing.append(f"--{opt} {getattr(args, opt)}")
    if missing:
        print("film_eval: missing input file(s): " + ", ".join(missing), file=sys.stderr)
        return 2
    try:
        report, metrics = evaluate(args)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"film_eval: cannot read inputs: {exc}", file=sys.stderr)
        return 2
    md = render_md(report, metrics)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md, encoding="utf-8")
    width = max(len(m.name) for m in metrics)
    for m in metrics:
        print(f"{m.verdict:<8} {m.name:<{width}}  {_fmt(m.value, m.unit)}  (n={m.n if m.n is not None else '-'})")
    print(f"OVERALL  {report['overall']}")
    if report.get("compare"):
        print(f"\nDelta vs {report['compare']['against']}")
        w2 = max(len(r["name"]) for r in report["compare"]["rows"])
        for r in report["compare"]["rows"]:
            print(f"  {r['name']:<{w2}}  {r['old']:>18} -> {r['new']:<18} {r['delta']:>9}  {r['verdict']}")
    return 1 if report["overall"] == FAIL else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. under some test runners); default encoding is used
    sys.exit(main())
