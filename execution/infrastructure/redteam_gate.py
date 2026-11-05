"""Red-team gate for outward text: deterministic layer (claim grounding, pass ledger, hooks).

description: Deterministic red-team gate for outward text: grounds draft claims against sources, records HMAC-signed 4-lens passes bound to logged lens runs, gates Gmail/Calendar/Bash senders.
inputs: CLI subcommands sha|ground|record|check|waive|hook|post-hook|subagent-hook|prompt-hook (--draft, --sources, --verdicts, --subject, --to, --cc, --bcc, --attachments, --file); hook JSON on stdin; env REDTEAM_DIR, REDTEAM_KEY_FILE, REDTEAM_HOOK (=1 for hook-only subcommands), REDTEAM_TRANSCRIPT_ROOT.
outputs: stdout claim table/JSON/sha12; .tmp/redteam/{ground/<sha12>.json, passes.jsonl, verdicts.jsonl, waivers.jsonl, drafts.jsonl} (every row HMAC-signed); ~/.claude/redteam/hmac.key (created 0600 on first use); PreToolUse deny JSON; UserPromptSubmit additionalContext JSON. Exit 0 ok, 1 ungrounded/weak, 2 usage, 3 refused/not passed.

Details
-------
Stdlib only, no network, no LLM, no secrets (so no .env is loaded). The semantic half of the gate
(four lens reviewers: counterparty, grounding, downside, reputation) is done by `redteam-lens`
subagents; this script does what can be done deterministically:

* normalise(text, is_html) -> canonical text; its sha256 identifies "this exact wording". HTML
  link/img URLs, alt text and comments become visible text; a non-empty <script>/<style> refuses.
* ground: money / percent / number+unit / date / quote / name claims plus overclaim words, checked
  lexically against sources. `weak` and `ungrounded` both fail.
* Ledger rows carry `mac` = HMAC-SHA256 (key file, see key_path) over canonical JSON of the row;
  readers ignore unsigned/invalid rows. Only hooks and a successful `record` sign.
* hook/post-hook/subagent-hook/prompt-hook refuse unless REDTEAM_HOOK=1 (set by the hook script).
* subagent-hook (SubagentStop): logs every strict LENS/DRAFT-SHA/VERDICT header produced by a
  subagent whose agent_transcript_path is <transcript root>/**/agent-<agent_id>.jsonl.
* record: zero ungrounded/weak claims + four PASS verdict files whose normalised sha256 is in
  verdicts.jsonl (lens + sha12 + PASS, agent_type redteam-lens). Binds subject/recipients/attachments.
* prompt-hook (UserPromptSubmit): `redteam waive <sha12> <reason>` typed by the operator is the
  only waiver path. The `waive` subcommand only prints how to waive (exit 2).
* hook (PreToolUse): Gmail send/reply/forward/draft, Calendar invites (attendees within the
  recorded recipients), Bash inline senders (only commands that execute something are scanned).
* post-hook (PostToolUse): Gmail draft id -> text sha map.

Threat model and limits: directives/infrastructure/redteam_gate.md.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import hmac
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
LENS_AGENT = "redteam-lens"
SOURCE_SUFFIXES = {".md", ".txt", ".html", ".htm", ".csv", ".json", ".eml", ".yaml", ".yml"}
HTML_SUFFIXES = {".html", ".htm"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
MAX_SOURCE_BYTES = 5_000_000
MAX_SOURCE_FILES = 2000
MAX_TRANSCRIPT_BYTES = 64_000_000
MAX_SCAN_BYTES = 2_000_000
MAX_HITS = 5
EXCERPT_CHARS = 160
REASON_EXCERPT_CHARS = 60
SELF_COPY_SHARE = 0.6

PASSES, VERDICTS, WAIVERS, DRAFTS = "passes.jsonl", "verdicts.jsonl", "waivers.jsonl", "drafts.jsonl"
HOOK_CMDS = {"hook", "post-hook", "subagent-hook", "prompt-hook"}
KEY_BYTES = 32

GMAIL_KNOWN = {"send_message", "reply", "forward", "create_draft", "update_draft"}
GMAIL_READ_PREFIXES = ("get_", "list_", "search_", "delete_", "trash_", "untrash_")
GMAIL_META = {"to", "cc", "bcc", "draftId", "messageId", "threadId", "replyThreadId",
              "replyToMessageId", "includeSignature", "replyAll", "attachments"}
CAL_ACTIONS = {"create_event", "update_event"}
CAL_ATTENDEE_KEYS = ("attendees", "attendeeEmails", "addedAttendees", "addedAttendeeEmails")
CAL_META = {"calendarId", "eventId", "start", "end", "startTime", "endTime", "timeZone",
            "attendees", "attendeeEmails", "addedAttendees", "addedAttendeeEmails",
            "removedAttendeeEmails", "sendUpdates", "notificationLevel", "colorId",
            "availability", "eventType", "visibility", "allDay", "addGoogleMeetUrl",
            "googleMeetUrl", "guestPermissions", "overrideReminders", "useDefaultReminders",
            "recurrenceData", "workingLocationProperties", "removedAttachmentFileUrls",
            "attachments", "addedAttachments"}
DENY_SUFFIX = ("Run /redteam on this exact text and envelope (ground + 4 redteam-lens subagents + "
               "record --subject/--to/--cc/--bcc/--attachments) first.")
BASH_DENY = ("Outward email is written via /redteam and sent through the Gmail tool, or sent by a "
             "committed, unmodified pipeline script run directly (e.g. `python3 execution/<cat>/"
             "<script>.py ...`).")

EXIT_OK, EXIT_UNGROUNDED, EXIT_USAGE, EXIT_REFUSED = 0, 1, 2, 3


class UsageError(Exception):
    pass


class ActiveHtmlError(UsageError):
    pass


# --------------------------------------------------------------------------- state

def state_dir() -> Path:
    env = os.environ.get("REDTEAM_DIR", "").strip()
    return Path(env) if env else REPO_ROOT / ".tmp" / "redteam"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def key_path() -> Path:
    env = os.environ.get("REDTEAM_KEY_FILE", "").strip()
    return Path(env).expanduser() if env else Path.home() / ".claude" / "redteam" / "hmac.key"


_KEY_CACHE: dict[str, bytes] = {}


def _chmod(p: Path, mode: int) -> None:
    try:
        os.chmod(p, mode)
    except OSError as exc:  # best-effort (Windows ACLs ignore POSIX modes); the key still works
        print(f"redteam: chmod {p.name} failed ({type(exc).__name__})", file=sys.stderr)


def load_key() -> bytes:
    """HMAC key; created atomically (dir 0700, file 0600) on first use."""
    kp = key_path()
    cached = _KEY_CACHE.get(str(kp))
    if cached:
        return cached
    if not kp.is_file():
        kp.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _chmod(kp.parent, 0o700)
        tmp = kp.with_name(f".{kp.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        try:
            os.write(fd, os.urandom(KEY_BYTES))
        finally:
            os.close(fd)
        _chmod(tmp, 0o600)
        try:
            os.link(tmp, kp)  # fails if another process won the race: then use its key
        except FileExistsError:
            pass
        except OSError:
            if not kp.exists():
                os.replace(tmp, kp)
        finally:
            if tmp.exists():
                tmp.unlink()
    key = kp.read_bytes()
    if len(key) < KEY_BYTES:
        raise UsageError(f"redteam HMAC key {kp} is shorter than {KEY_BYTES} bytes")
    _KEY_CACHE[str(kp)] = key
    return key


def _canonical(row: dict) -> bytes:
    body = {k: v for k, v in row.items() if k != "mac"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sign_row(row: dict) -> dict:
    out = {k: v for k, v in row.items() if k != "mac"}
    out["mac"] = hmac.new(load_key(), _canonical(out), hashlib.sha256).hexdigest()
    return out


def row_signed(row: dict) -> bool:
    mac = row.get("mac")
    if not isinstance(mac, str):
        return False
    good = hmac.new(load_key(), _canonical(row), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, good)


def read_signed(path: Path) -> tuple[list[dict], int]:
    """(rows with a valid HMAC, count of unsigned/invalid rows ignored)."""
    rows = _read_jsonl(path)
    good = [r for r in rows if row_signed(r)]
    return good, len(rows) - len(good)


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
        fh.write(json.dumps(sign_row(row), ensure_ascii=False) + "\n")


def _sha256(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


_SHA12_RE = re.compile(r"[0-9a-f]{12}")


def _is_lens_agent(agent_type: Any) -> bool:
    return isinstance(agent_type, str) and (agent_type == LENS_AGENT
                                            or agent_type.endswith(":" + LENS_AGENT))


class Ledger:
    """HMAC-signed pass rows backed by signed hook logs (verdicts.jsonl / waivers.jsonl)."""

    def __init__(self, state: Path) -> None:
        self.verdicts: dict[str, list[dict]] = {}
        vrows, n1 = read_signed(state / VERDICTS)
        wrows, n2 = read_signed(state / WAIVERS)
        self.all_rows, n3 = read_signed(state / PASSES)
        self.ignored = n1 + n2 + n3
        for r in vrows:
            if isinstance(r.get("out_sha256"), str):
                self.verdicts.setdefault(r["out_sha256"], []).append(r)
        self.waived12 = {str(r.get("sha12")) for r in wrows
                         if _SHA12_RE.fullmatch(str(r.get("sha12")))}
        self.rows = [r for r in self.all_rows if self.row_valid(r)]

    def verdict_ok(self, out_sha: Any, lens: str, sha12: str) -> bool:
        return any(v.get("lens") == lens and v.get("sha12") == sha12 and v.get("verdict") == "PASS"
                   and _is_lens_agent(v.get("agent_type"))
                   for v in self.verdicts.get(str(out_sha), []))

    def row_valid(self, row: dict) -> bool:
        if row.get("waived") is True:
            s12 = str(row.get("sha12"))
            return bool(_SHA12_RE.fullmatch(s12)) and s12 in self.waived12
        sha = row.get("sha256")
        vs = row.get("verdicts")
        if not isinstance(sha, str) or len(sha) != 64 or not isinstance(vs, list):
            return False
        covered = {v.get("lens") for v in vs if isinstance(v, dict)
                   and self.verdict_ok(v.get("out_sha256"), str(v.get("lens")), sha[:12])}
        return covered >= set(LENSES)

    def rows_for(self, sha256: str) -> list[dict]:
        return [r for r in self.rows if r.get("sha256") == sha256
                or (r.get("waived") is True and sha256.startswith(str(r.get("sha12"))))]


# --------------------------------------------------------------------------- normalisation

_QUOTE_MAP = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u00ab": '"', "\u00bb": '"',
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u2039": "'", "\u203a": "'",
})
_HTML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
_HTML_ACTIVE_RE = re.compile(r"<(script|style)\b[^>]*>(.*?)</\1\s*>", re.I | re.S)
_HTML_ACTIVE_OPEN_RE = re.compile(r"<(script|style)\b", re.I)
_HTML_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
_HTML_ATTR_RE = re.compile(r"""(?<![\w-])(href|src|alt)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
                           re.I)
_HTML_BLOCK_CLOSE = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table",
                     "blockquote"}
_WS_RE = re.compile(r"\s+")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tag_sub(m: re.Match) -> str:
    closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
    out: list[str] = []
    if not closing:
        for a in _HTML_ATTR_RE.finditer(attrs):
            key = a.group(1).lower()
            val = html.unescape(next((g for g in a.group(2, 3, 4) if g is not None), "")).strip()
            if not val:
                continue
            label = ("link" if key == "href" else "alt" if key == "alt"
                     else "img" if name == "img" else "src")
            out.append(f" [{label}: {_esc(val)}] ")
    if name == "br" or (closing and name in _HTML_BLOCK_CLOSE):
        out.append("\n")
    return "".join(out)


def html_to_text(text: str, strict: bool = True) -> str:
    """HTML -> visible-equivalent text. Link/img URLs, alt text and comments are made visible so a
    pass cannot be reused with a swapped href. strict: a non-empty <script>/<style> raises."""
    text = _HTML_COMMENT_RE.sub(
        lambda m: f" [comment: {_esc(m.group(1).strip())}] " if m.group(1).strip() else " ", text)

    def active(m: re.Match) -> str:
        if strict and m.group(2).strip():
            raise ActiveHtmlError(f"HTML contains a non-empty <{m.group(1).lower()}> block")
        return " "

    text = _HTML_ACTIVE_RE.sub(active, text)
    if _HTML_ACTIVE_OPEN_RE.search(text):
        if strict:
            raise ActiveHtmlError("HTML contains an unclosed <script>/<style> tag")
        text = text[: _HTML_ACTIVE_OPEN_RE.search(text).start()]
    text = _HTML_TAG_RE.sub(_tag_sub, text)
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
    return _sha256(normalise(text, is_html))


def is_html_path(path: Path) -> bool:
    return path.suffix.lower() in HTML_SUFFIXES


def _looks_html(text: str) -> bool:
    return bool(re.search(r"<[A-Za-z!/]", text))


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
    "second": ("second", "seconds", "seconde", "secondes", "sec", "s"),
    "millisecond": ("millisecond", "milliseconds", "ms"),
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


# --------------------------------------------------------------------------- names

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_WORD_RE = re.compile(r"[^\W\d_][\w'\u2019-]*")
_SENT_END = set(".!?:;")
_LEAD_SKIP = set(" \t\"'\u201c\u201d\u2018\u2019\u00ab\u00bb([{*\u2022-\u2013\u2014>#")
NAME_ALLOW_EMAILS = {"debanjan@prodcraft.fyi"}
NAME_ALLOW = {
    "Debanjan", "Mazumdar", "Founder", "ProdCraft",
    "Hi", "Hello", "Hey", "Dear", "Thanks", "Thank", "Best", "Regards", "Kind", "Warm", "Warmest",
    "Cheers", "Sincerely", "Yours", "Bonjour", "Bonsoir", "Salut", "Merci", "Cordialement",
    "Bien", "Madame", "Monsieur", "Mr", "Mrs", "Ms", "Dr", "Re", "Fwd", "Fw",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "Mon", "Tue", "Tues", "Wed", "Thu", "Thur", "Thurs", "Fri", "Sat", "Sun",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
} | {m.capitalize() for m in _MONTHS}


def _sentence_start(line: str, pos: int) -> bool:
    i = pos - 1
    while i >= 0 and line[i] in _LEAD_SKIP:
        i -= 1
    return i < 0 or line[i] in _SENT_END


def extract_names(draft_text: str, is_html: bool = False) -> list[dict]:
    """Title-Case words/sequences not at a sentence start, and email addresses."""
    raw = html_to_text(draft_text) if is_html else draft_text
    out: list[dict] = []
    for line in raw.splitlines():
        line = unicodedata.normalize("NFC", line)
        for m in _EMAIL_RE.finditer(line):
            addr = m.group(0).strip(".")
            if addr.lower() not in NAME_ALLOW_EMAILS:
                out.append({"text": addr, "kind": "name", "tokens": [addr], "email": True})
        line = _EMAIL_RE.sub(" ", _URL_RE.sub(" ", line))
        words: list[tuple[str, bool, int, int]] = []
        for m in _WORD_RE.finditer(line):
            w = re.sub(r"['\u2019]s$", "", m.group(0)).rstrip("'\u2019-")
            if len(w) >= 2 and w[0].isupper() and w[1].islower():
                words.append((w, _sentence_start(line, m.start()), m.start(), m.end()))
            else:
                words.append(("", False, m.start(), m.end()))
        groups: list[list[tuple[str, bool]]] = []
        prev_end = -2
        for w, start, s, e in words:
            if not w:
                prev_end = -2
                continue
            if groups and prev_end >= 0 and line[prev_end:s] == " " and not start:
                groups[-1].append((w, start))
            else:
                groups.append([(w, start)])
            prev_end = e
        for g in groups:
            toks = [w for i, (w, start) in enumerate(g) if not (i == 0 and start)]
            toks = [w for w in toks if w not in NAME_ALLOW]
            if toks:
                out.append({"text": " ".join(toks), "kind": "name", "tokens": toks})
    return out


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

    for c in extract_names(draft_text, is_html):
        p = text.find(c["tokens"][0])
        c["pos"] = p if p >= 0 else len(text)
        claims.append(c)

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
        self.sha256 = _sha256(raw)
        text = _decode_source(path, raw)
        self.lines: list[SourceLine] = []
        kept: list[str] = []
        self.offsets: list[int] = []
        pos = 0
        for i, line in enumerate(text.splitlines(), 1):
            n = normalise(line)
            if not n:
                continue
            self.lines.append(SourceLine(i, n))
            self.offsets.append(pos)
            kept.append(n)
            pos += len(n) + 1
        self.full_text = " ".join(kept)
        self.full_lower = self.full_text.lower()

    def line_at(self, offset: int) -> SourceLine:
        return self.lines[max(0, bisect.bisect_right(self.offsets, offset) - 1)]


def _decode_source(path: Path, raw: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        import email
        import email.policy
        try:
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            parts = [f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h]]
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    body = part.get_content()
                    parts.append(html_to_text(body, strict=False) if ctype == "text/html"
                                 else body)
            return "\n".join(parts)
        except Exception as exc:  # malformed MIME: fall back to the raw bytes as text
            print(f"redteam: .eml parse failed for {path.name} ({type(exc).__name__}); "
                  "using raw text", file=sys.stderr)
    text = raw.decode("utf-8", errors="replace")
    return html_to_text(text, strict=False) if suffix in HTML_SUFFIXES else text


def _display(path: Path) -> str:
    rp = path.resolve()
    for base in (REPO_ROOT, Path.cwd()):
        try:
            return rp.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return rp.as_posix()


def draft_sentences(draft_text: str, is_html: bool) -> list[str]:
    norm = normalise(draft_text, is_html).lower()
    out = []
    for s in re.split(r"(?<=[.!?])\s+", norm):
        s = s.strip(_EDGE_PUNCT)
        if len(s.split()) >= 3:
            out.append(s)
    return out


def self_copy_share(src: Source, sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    return sum(1 for s in sentences if s in src.full_lower) / len(sentences)


def collect_sources(paths: list[str], draft: Path | None, state: Path,
                    sentences: list[str] | None = None) -> tuple[list[Source], list[dict]]:
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
        src = Source(f, disp, f.read_bytes())
        share = self_copy_share(src, sentences or [])
        if share >= SELF_COPY_SHARE:
            skipped.append({"path": disp, "reason": f"looks like the draft itself "
                                                    f"({round(share * 100)}% of its sentences)"})
            continue
        sources.append(src)
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
        hits.extend(vhits)
    out: list[dict] = []
    seen: set[str] = set()
    for _, h in sorted(hits, key=lambda h: not h[0]):
        if h["source"] not in seen:
            seen.add(h["source"])
            out.append(h)
    return found_all, found_all and not strong, out[:MAX_HITS]


def _ground_date(claim: dict, sources: list[Source]) -> tuple[bool, bool, list[dict]]:
    """A year-less draft date is strong only against a year-less or current-year source date."""
    day, month, year = claim["date"]
    this_year = datetime.now().year
    strong_hits: list[dict] = []
    weak_hits: list[dict] = []
    for src in sources:
        for ln in src.lines:
            for s, _, d in ln.dates:
                if (d[0], d[1]) != (day, month):
                    continue
                hit = {"source": f"{src.display}:{ln.no}", "source_line": _excerpt(ln.text, s)}
                if year is not None:
                    ok = d[2] is None or d[2] == year
                    if ok:
                        strong_hits.append(hit)
                elif d[2] is None or d[2] == this_year:
                    strong_hits.append(hit)
                else:
                    weak_hits.append(hit)
                break
    if strong_hits:
        return True, False, strong_hits[:MAX_HITS]
    if weak_hits:
        return True, True, weak_hits[:MAX_HITS]
    return False, False, []


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


def _ground_name(claim: dict, sources: list[Source]) -> list[dict]:
    """Every token must appear case-sensitively (emails: case-insensitively) in some source."""
    hits: list[dict] = []
    for tok in claim["tokens"]:
        found = None
        if claim.get("email"):
            for src in sources:
                p = src.full_lower.find(tok.lower())
                if p >= 0:
                    found = (src, p)
                    break
        else:
            rx = re.compile(r"(?<![\w])" + re.escape(tok) + r"(?![\w])")
            for src in sources:
                m = rx.search(src.full_text)
                if m:
                    found = (src, m.start())
                    break
        if not found:
            return []
        src, p = found
        ln = src.line_at(p)
        hits.append({"source": f"{src.display}:{ln.no}", "source_line": _excerpt(ln.text)})
    return hits[:MAX_HITS]


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
            weak = False
            if kind in ("money", "percent", "unit"):
                ok, weak, hits = _ground_numeric(c, sources)
            elif kind == "date":
                ok, weak, hits = _ground_date(c, sources)
            elif kind == "name":
                hits = _ground_name(c, sources)
                ok = bool(hits)
            else:
                hits = _ground_quote(c, sources)
                ok = bool(hits)
            if ok and hits:
                r["status"] = "weak" if weak else "grounded"
                r["weak"] = weak
                r["source"] = hits[0]["source"]
                r["source_line"] = hits[0]["source_line"]
            r["hits"] = hits
        if c.get("count", 1) > 1:
            r["count"] = c["count"]
        results.append(r)
    return results


def _read_draft(draft: Path) -> tuple[str, bool]:
    if not draft.is_file():
        raise UsageError(f"draft not found: {draft}")
    return draft.read_text(encoding="utf-8", errors="replace"), is_html_path(draft)


def run_ground(draft: Path, source_args: list[str], state: Path) -> dict:
    text, html_flag = _read_draft(draft)
    sha = sha_of(text, html_flag)
    sources, skipped = collect_sources(source_args, draft, state,
                                       draft_sentences(text, html_flag))
    claims = ground_claims(extract_claims(text, html_flag), sources)
    summary = {
        "total": len(claims),
        "grounded": sum(c["status"] == "grounded" for c in claims),
        "weak": sum(c["status"] == "weak" for c in claims),
        "ungrounded": sum(c["status"] == "ungrounded" for c in claims),
        "overclaims": sum(c["status"] == "overclaim" for c in claims),
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
        where = c["source"] or (c.get("context") and f"ctx: {_cut(c['context'], 70)}") or "-"
        line = f" | {_cut(c['source_line'], 70)}" if c["source_line"] else ""
        print(f"{c['status']:<11} {c['kind']:<9} {_cut(c['text'], 32):<32} {where}{line}")
    s = result["summary"]
    print(f"{s['total']} claims: {s['grounded']} grounded, {s['weak']} WEAK, "
          f"{s['ungrounded']} UNGROUNDED, {s['overclaims']} overclaim warnings")
    for sk in result["skipped"][:10]:
        print(f"skipped: {sk['path']} ({sk['reason']})")
    print("Note: grounding is lexical. A grounded number may still be misattributed; the grounding "
          "lens must read every hit's source_line context. weak = not grounded.")


# --------------------------------------------------------------------------- verdicts

_HEADER_RES = (
    ("lens", re.compile(r"LENS: (" + "|".join(LENSES) + r")")),
    ("sha", re.compile(r"DRAFT-SHA: ([0-9a-f]{12})")),
    ("verdict", re.compile(r"VERDICT: (PASS|FAIL)")),
)


def parse_verdict(text: str) -> dict:
    """Strict: the first 3 non-blank lines must be exactly LENS / DRAFT-SHA / VERDICT."""
    lines = [ln.rstrip() for ln in text.lstrip("\ufeff").splitlines() if ln.strip()]
    if len(lines) < 3:
        return {"error": "fewer than 3 non-blank lines"}
    out: dict[str, str] = {}
    for (key, rx), line in zip(_HEADER_RES, lines[:3]):
        m = rx.fullmatch(line)
        if not m:
            return {"error": f"header line {line[:40]!r} is not exactly "
                             f"'{rx.pattern.split(':')[0]}: ...' in the required order"}
        out[key] = m.group(1)
    return out


def verdict_sha(text: str) -> str:
    return _sha256(normalise(text.lstrip("\ufeff")))


# --------------------------------------------------------------------------- envelope

def parse_addrs(value: Any) -> tuple[set[str], list[str]]:
    """Return (lowercased addresses, unparseable items)."""
    items: list[Any] = value if isinstance(value, list) else [value]
    addrs: set[str] = set()
    bad: list[str] = []
    for it in items:
        if isinstance(it, dict):
            em = it.get("email")
            if not isinstance(em, str) or not _EMAIL_RE.search(em):
                bad.append(json.dumps(it, ensure_ascii=False, sort_keys=True)[:40])
                continue
            it = em
        if not isinstance(it, str):
            bad.append(str(it)[:40])
            continue
        found = [a.lower() for a in _EMAIL_RE.findall(it)]
        if not found and it.strip():
            bad.append(it[:40])
        addrs.update(found)
    return addrs, bad


def _b64decode(s: str) -> bytes:
    import base64
    s = re.sub(r"\s+", "", s)
    s += "=" * (-len(s) % 4)
    if re.fullmatch(r"[A-Za-z0-9+/]*=*", s):
        return base64.b64decode(s, validate=True)
    if re.fullmatch(r"[A-Za-z0-9_-]*=*", s):
        return base64.urlsafe_b64decode(s)
    raise ValueError("attachment content is not base64")


def attachment_shas(value: Any) -> list[str]:
    if not isinstance(value, list):
        value = [value]
    out = []
    for it in value:
        content = it.get("content", it.get("data")) if isinstance(it, dict) else it
        if not isinstance(content, str) or not content.strip():
            raise ValueError("attachment without inline base64 content cannot be verified")
        out.append(_sha256(_b64decode(content)))
    return out


def _present(v: Any) -> bool:
    return v not in (None, "", [], {}) and not (isinstance(v, str) and not v.strip())


def envelope_error(row: dict, ti: dict) -> str | None:
    if row.get("waived") is True:
        return None
    subj = ti.get("subject")
    if _present(subj):
        if not isinstance(subj, str) or row.get("subject_sha") != sha_of(subj):
            return "subject differs from the recorded --subject"
    for key in ("to", "cc", "bcc"):
        if not _present(ti.get(key)):
            continue
        addrs, bad = parse_addrs(ti[key])
        if bad:
            return f"{key} has unparseable recipient(s): {', '.join(bad[:3])}"
        extra = sorted(addrs - set(row.get(key) or []))
        if extra:
            return f"{key} recipient(s) not recorded with --{key}: {', '.join(extra[:5])}"
    if _present(ti.get("attachments")):
        try:
            shas = attachment_shas(ti["attachments"])
        except ValueError as exc:
            return str(exc)
        if not set(shas) <= set(row.get("attachments") or []):
            return "attachment content not recorded with --attachments"
    return None


def first_envelope_error(rows: list[dict], ti: dict) -> str | None:
    errors = [envelope_error(r, ti) for r in rows]
    return None if any(e is None for e in errors) else errors[0]


# --------------------------------------------------------------------------- CLI commands

def cmd_sha(args: argparse.Namespace) -> int:
    try:
        text, h = _read_draft(Path(args.draft))
        print(sha_of(text, h)[:12])
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
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
    s = result["summary"]
    return EXIT_UNGROUNDED if s["ungrounded"] or s["weak"] else EXIT_OK


def _check_verdict_file(vf: str, sha12: str, ledger: Ledger) -> tuple[str | None, dict | None]:
    vp = Path(vf)
    if not vp.is_file():
        return f"verdict file not found: {vf}", None
    text = vp.read_text(encoding="utf-8", errors="replace")
    v = parse_verdict(text)
    if "error" in v:
        return f"{vf}: malformed verdict ({v['error']})", None
    if v["sha"] != sha12:
        return (f"{vf}: stale DRAFT-SHA {v['sha']} for lens {v['lens']} (current draft is "
                f"{sha12}; re-run that lens on the current wording)"), None
    if v["verdict"] != "PASS":
        return f"{vf}: lens {v['lens']} verdict is {v['verdict']}", None
    out_sha = verdict_sha(text)
    logged = ledger.verdicts.get(out_sha, [])
    if not logged:
        return (f"{vf}: not produced by a logged {LENS_AGENT} subagent run (no SubagentStop "
                "record of this exact text; save the lens's returned text verbatim)"), None
    if not ledger.verdict_ok(out_sha, v["lens"], sha12):
        types = sorted({str(r.get("agent_type")) for r in logged})
        return (f"{vf}: logged run was agent_type {', '.join(types)}, not {LENS_AGENT}"), None
    return None, {"lens": v["lens"], "out_sha256": out_sha}


def _envelope_from_args(args: argparse.Namespace) -> dict:
    env: dict[str, Any] = {"subject_sha": None, "to": [], "cc": [], "bcc": [], "attachments": []}
    if args.subject is not None and args.subject.strip():
        env["subject_sha"] = sha_of(args.subject)
    for key in ("to", "cc", "bcc"):
        vals = getattr(args, key) or []
        addrs, bad = parse_addrs(list(vals))
        if bad:
            raise UsageError(f"--{key}: unparseable address(es): {', '.join(bad)}")
        env[key] = sorted(addrs)
    for p in args.attachments or []:
        ap = Path(p)
        if not ap.is_file():
            raise UsageError(f"attachment not found: {p}")
        env["attachments"].append(_sha256(ap.read_bytes()))
    env["attachments"] = sorted(set(env["attachments"]))
    return env


def cmd_record(args: argparse.Namespace) -> int:
    state = state_dir()
    try:
        result = run_ground(Path(args.draft), args.sources, state)
        env = _envelope_from_args(args)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    sha12 = result["sha12"]
    reasons: list[str] = []
    for status in ("ungrounded", "weak"):
        bad = [c for c in result["claims"] if c["status"] == status]
        if bad:
            reasons.append(f"{len(bad)} {status} claim(s): "
                           + "; ".join(_cut(c["text"], 40) for c in bad[:8]))
    ledger = Ledger(state)
    passed: dict[str, dict] = {}
    for vf in args.verdicts:
        err, ref = _check_verdict_file(vf, sha12, ledger)
        if err:
            reasons.append(err)
        elif ref:
            passed[ref["lens"]] = ref
    missing = [lens for lens in LENSES if lens not in passed]
    if missing:
        reasons.append("no valid PASS for lens(es): " + ", ".join(missing))
    if reasons:
        print(f"REFUSED {sha12} {result['draft']}")
        for r in reasons:
            print(f"- {r}")
        return EXIT_REFUSED
    for r in ledger.rows:
        if r.get("sha256") == result["sha256"] and not r.get("waived") and all(
                r.get(k) == env[k] for k in env):
            print(f"already recorded: {sha12} {result['draft']}")
            return EXIT_OK
    s = result["summary"]
    _append_jsonl(state / PASSES, {
        "sha256": result["sha256"], "sha12": sha12, "draft": result["draft"],
        "sources": result["sources"], "lenses": list(LENSES),
        "verdicts": [passed[lens] for lens in LENSES], **env,
        "claims_total": s["total"], "claims_grounded": s["grounded"],
        "overclaims": s["overclaims"], "ts": _now(), "waived": False,
    })
    print(f"recorded: {sha12} {result['draft']} ({s['grounded']}/{s['total']} claims grounded, "
          f"{s['overclaims']} overclaim warnings)")
    return EXIT_OK


def cmd_waive(_args: argparse.Namespace) -> int:
    print("waive is operator-only. Ask the operator to type, as their own prompt:\n"
          "  redteam waive <sha12> <reason>\n"
          "(the UserPromptSubmit hook records it). Get <sha12> from `redteam_gate.py sha --draft D`.",
          file=sys.stderr)
    return EXIT_USAGE


def cmd_check(args: argparse.Namespace) -> int:
    f = Path(args.file)
    try:
        text, h = _read_draft(f)
        sha = sha_of(text, h)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    ledger = Ledger(state_dir())
    if ledger.ignored:
        print(f"ignored unsigned rows: {ledger.ignored}")
    rows = ledger.rows_for(sha)
    if rows:
        print(f"PASSED {sha[:12]}" + (" (waived)" if rows[0].get("waived") else ""))
        return EXIT_OK
    if any(r.get("sha256") == sha for r in ledger.all_rows):
        print(f"NOT PASSED {sha[:12]} (pass row not backed by logged lens verdicts)")
    else:
        print(f"NOT PASSED {sha[:12]}")
    return EXIT_REFUSED


# --------------------------------------------------------------------------- PreToolUse hook

def gmail_action(tool_name: str) -> str | None:
    if "gmail" not in tool_name.lower():
        return None
    suffix = tool_name.rsplit("__", 1)[-1]
    if suffix in GMAIL_KNOWN:
        return suffix
    low = suffix.lower()
    if low.startswith(GMAIL_READ_PREFIXES):
        return None
    return "generic" if re.search(r"send|reply|forward|draft", low) else None


def text_fields(tool_input: dict, meta: set[str], skip: Iterable[str] = ("subject",)
                ) -> list[tuple[str, str, bool]]:
    """Every non-metadata, non-empty textual input as (key, raw, is_html). Unknown keys included."""
    out: list[tuple[str, str, bool]] = []
    skip = set(skip)
    for key, val in tool_input.items():
        if key in meta or key in skip or val is None or isinstance(val, (bool, int, float)):
            continue
        raw = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, sort_keys=True)
        is_html = "html" in key.lower() or (key == "description" and _looks_html(raw))
        try:
            keep = bool(normalise(raw, is_html))
        except ActiveHtmlError:
            keep = True  # reported (and denied) by the caller's own normalise
        if keep:
            out.append((key, raw, is_html))
    return out


def latest_draft_row(state: Path, draft_id: str) -> dict | None:
    row = None
    for r in read_signed(state / DRAFTS)[0]:
        if str(r.get("draft_id")) == draft_id:
            row = r
    return row


def _not_passed(where: str, norm: str, sha: str) -> str:
    exc = _cut(norm, REASON_EXCERPT_CHARS).replace('"', "'")
    return f'{where} (sha {sha[:12]}, "{exc}") has not passed red-team'


def _check_fields(where: str, fields: list[tuple[str, str, bool]], ti: dict, ledger: Ledger,
                  envelope: bool = True) -> str | None:
    for key, raw, is_html in fields:
        try:
            norm = normalise(raw, is_html)
        except ActiveHtmlError as exc:
            return f"{where}.{key}: {exc} (not allowed in outward text)"
        sha = _sha256(norm)
        rows = ledger.rows_for(sha)
        if not rows:
            return _not_passed(f"{where}.{key}", norm, sha)
        if envelope:
            err = first_envelope_error(rows, ti)
            if err:
                return f"{where}.{key} (sha {sha[:12]}): {err}"
    return None


def gmail_decision(action: str, ti: dict, state: Path) -> str | None:
    fields = text_fields(ti, GMAIL_META)
    ledger = Ledger(state)
    if fields:
        return _check_fields(action, fields, ti, ledger)
    has_env = any(_present(ti.get(k)) for k in ("subject", "to", "cc", "bcc", "attachments"))
    did = ti.get("draftId")
    if _present(did) and action != "create_draft":
        did = str(did)
        if action == "update_draft" and not has_env:
            return None
        row = latest_draft_row(state, did)
        if row is None:
            return (f"draft {did[:40]} has no recorded content (create/update it via the gated "
                    "Gmail draft tools so its text is hashed)")
        shas = row.get("sha256s") or [row.get("sha256")]
        for s in shas:
            rows = ledger.rows_for(str(s))
            if not rows:
                return f"draft {did[:40]} content (sha {str(s)[:12]}) has not passed red-team"
            err = first_envelope_error(rows, ti) if action == "update_draft" else None
            if err:
                return f"update_draft {did[:40]}: {err}"
        return None
    if action in ("forward", "generic"):
        if _present(ti.get("attachments")):
            return f"{action} adds attachments with no vetted text to bind them to"
        return None
    if action == "create_draft":
        if has_env:
            return ("create_draft sets subject/recipients/attachments without a body; create the "
                    "draft with its vetted body so the envelope is bound")
        return None
    return f"{action} has no body text to vet"


_ATTENDEE_KEY_RE = re.compile(r"attendee|guest|invitee", re.I)


def attendee_error(ti: dict, rows: list[dict]) -> str | None:
    """Attendees must be a subset of --to/--cc/--bcc of one passing record (waiver: any)."""
    wanted: set[str] = set()
    keys = attendee_keys(ti)
    for k in keys:
        addrs, bad = parse_addrs(ti[k])
        if bad:
            return f"{k} has unparseable attendee(s): {', '.join(bad[:3])}"
        wanted |= addrs
    if not keys:
        return None
    if not wanted:
        return f"{', '.join(keys)} present but no attendee address could be read"
    best: list[str] = sorted(wanted)
    for r in rows:
        if r.get("waived") is True:
            return None
        allowed = {str(a).lower() for k in ("to", "cc", "bcc") for a in (r.get(k) or [])}
        extra = sorted(wanted - allowed)
        if not extra:
            return None
        best = min(best, extra, key=len)
    return ("attendee(s) not recorded with --to/--cc/--bcc: " + ", ".join(best[:5]))


def attendee_keys(ti: dict) -> list[str]:
    """Known attendee keys plus any unknown attendee/guest/invitee-like key (not removals)."""
    return [k for k in ti if (k in CAL_ATTENDEE_KEYS
                              or (k not in CAL_META and _ATTENDEE_KEY_RE.search(k)))
            and not k.lower().startswith("removed") and _present(ti.get(k))]


def calendar_decision(action: str, ti: dict, state: Path) -> str | None:
    akeys = attendee_keys(ti)
    invites = bool(akeys)
    fields = text_fields(ti, CAL_META | set(akeys), skip=())
    if not fields:
        if invites:  # an invite with no vetted text cannot be bound to a passing record
            err = attendee_error(ti, [])
            return f"{action}: {err}" if err else None
        return None
    notif = str(ti.get("notificationLevel") or ti.get("sendUpdates") or "ALL").upper()
    gated = invites or (action == "update_event" and notif not in ("NONE",))
    if not gated:
        return None
    ledger = Ledger(state)
    desc_rows: list[dict] = []
    others = []
    for key, raw, is_html in fields:
        if key == "description":
            try:
                norm = normalise(raw, is_html)
            except ActiveHtmlError as exc:
                return f"{action}.description: {exc}"
            sha = _sha256(norm)
            desc_rows = ledger.rows_for(sha)
            if not desc_rows:
                return _not_passed(f"{action}.description", norm, sha) + (
                    " (invites email attendees; for an event without guests set "
                    "notificationLevel NONE)" if action == "update_event" else "")
        elif key != "summary":
            others.append((key, raw, is_html))
    summ = ti.get("summary")
    summ_rows: list[dict] = []
    if isinstance(summ, str) and summ.strip():
        ssha = sha_of(summ)
        summ_rows = ledger.rows_for(ssha)
        ok = bool(summ_rows) or any(
            r.get("waived") is True or r.get("subject_sha") == ssha for r in desc_rows)
        if not ok:
            return _not_passed(f"{action}.summary", normalise(summ), ssha) + (
                " (record the description with --subject \"<summary>\", or red-team the summary)")
    if invites:
        err = attendee_error(ti, desc_rows or summ_rows)
        if err:
            return f"{action}: {err}"
    # location is outward text too: it passes as its own passed text, or verbatim inside the
    # passed description (normalised substring).
    loc = next(((k, r, h) for k, r, h in others if k == "location"), None)
    if loc is not None:
        others = [f for f in others if f[0] != "location"]
        lnorm = normalise(loc[1])
        desc = ti.get("description")
        in_desc = bool(desc_rows) and isinstance(desc, str) and lnorm in normalise(
            desc, any(k == "description" and h for k, _, h in fields))
        if not in_desc and not ledger.rows_for(_sha256(lnorm)):
            return _not_passed(f"{action}.location", lnorm, _sha256(lnorm)) + (
                " (put the location verbatim in the red-teamed description)")
    return _check_fields(action, others, ti, ledger, envelope=False)


# Literals are split so this file does not match its own patterns when it is scanned.
_SENDER_SIMPLE = ("smtp" "lib", "send" "mail", "messages().se" "nd(", "drafts().se" "nd(",
                  "api.send" "grid.com", "api.re" "send.com", "api.post" "markapp.com",
                  "smtp" "://", "smtp" "s://", "--mail" "-rcpt", "mailgun" ".net/v3",
                  "api.brevo" ".com", "api.sendin" "blue.com", "send" "-email", "send-raw" "-email",
                  "send" "_email(", "send" "_raw_email(")
_SES_RE = re.compile(r"email(?:-smtp)?\.[a-z0-9-]+\.amazon" r"aws\.com")
# Mail programs: a hit when they are the program a simple command runs.
_MAILERS = {"mail", "mailx", "msmtp", "swaks", "mutt", "send" "mail", "s-nail", "neomutt"}
# Wrappers that run the next word as the program (their own flags/numeric args are skipped).
_WRAPPERS = {"sudo", "env", "exec", "xargs", "nohup", "time", "timeout", "nice", "watch",
             "command", "stdbuf", "ionice", "npx", "pipx", "uv", "uvx", "poetry", "pdm",
             "hatch", "pipenv", "conda", "rye", "run", "-m"}
_GMAIL_API = "gmail.googleapis" ".com"
_INSTANTLY_API = "api.instan" "tly.ai"
# The script a command executes directly: `python3 [flags] x.py`, `bash x.sh`, `./x.py`.
_EXEC_SCRIPT_RE = re.compile(
    r"(?:^|[\s;&|(])(?:\S*/)?(?:python(?:3(?:\.\d+)?)?|py|bash|sh|node)(?:\.exe)?\s+"
    r"(?:-[\w.]+\s+)*([^\s;&|<>]+\.(?:py|sh|js|mjs))(?=\s|$|[;&|])"
    r"|(?:^|[\s;&|(])(\.{0,2}/[^\s;&|<>]+\.(?:py|sh))(?=\s|$|[;&|])", re.I)
# A program that executes code or sends mail, in command position (start of a simple command,
# optionally behind env assignments or a wrapper such as sudo/env/xargs/nohup/time/exec).
_EXEC_WORDS = (r"python(?:3(?:\.\d+)?)?|py|node|deno|bun|ruby|perl|php|curl|wget|send" r"mail|"
               r"mailx?|msmtp|swaks|aws|mutt|neomutt|s-nail|(?:ba|z|da|k)?sh")
_EXEC_WORD_RE = re.compile(r"(?:" + _EXEC_WORDS + r")(?:\.exe)?", re.I)
_QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.S)
_SEGMENT_SPLIT_RE = re.compile(r"[\n;&|(){}`]|\$\(")


class _ExecFinder:
    """Exec detection on the command with quoted strings removed: a program word anywhere in a
    simple command (so `timeout 30 python3`, `uv run python`, `poetry run python` count), while
    quoted text (commit messages, echo/printf payloads) never does."""

    def search(self, outer: str) -> bool:
        bare = _QUOTED_RE.sub(" ", outer)
        for tok in bare.split():
            name = re.split(r"[/\\]", tok.strip("<>"))[-1]
            if name and _EXEC_WORD_RE.fullmatch(name):
                return True
        return False


_EXEC_RE = _ExecFinder()


def mailer_hit(outer: str) -> str | None:
    """A mail program run as the program of a simple command (behind env/wrappers)."""
    bare = _QUOTED_RE.sub(" ''", outer)
    for seg in _SEGMENT_SPLIT_RE.split(bare):
        toks = seg.split()
        i = 0
        while i < len(toks):
            t = toks[i]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t) or t.lower() in _WRAPPERS or (
                    i > 0 and (t.startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", t))):
                i += 1
                continue
            break
        if i < len(toks):
            name = re.sub(r"\.exe$", "", re.split(r"[/\\]", toks[i])[-1].lower())
            if name in _MAILERS:
                return f"mail program {name}"
    return None
_PY_MOD_RE = re.compile(r"(?:^|[\s;&|(])(?:\S*/)?python(?:3(?:\.\d+)?)?(?:\.exe)?\s+"
                        r"(?:-[A-Za-z]+\s+)*-m\s*([A-Za-z_][\w.]*)", re.I)
_B64_PIPE_RE = re.compile(
    r"base64\s+(?:\S+\s+)*?(?:-d|-D|--decode)\b[^\n]*\|\s*(?:\S*/)?(?:" + _EXEC_WORDS + r")\b",
    re.I)
_HEREDOC_RE = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][\w-]*)\2")


def sender_hit(low: str) -> str | None:
    for pat in _SENDER_SIMPLE:
        if pat in low:
            return pat
    if _GMAIL_API in low and "/send" in low:
        return "Gmail REST /send"
    if _INSTANTLY_API in low and ("/emails" in low or "/reply" in low):
        return "Instantly emails/reply API"
    if _SES_RE.search(low):
        return "Amazon SES endpoint"
    return None


def split_heredocs(command: str) -> tuple[str, list[tuple[str, str]]]:
    """(command text without heredoc bodies, [(opener line, body)])."""
    lines = command.split("\n")
    outer: list[str] = []
    docs: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        outer.append(line)
        i += 1
        for m in _HEREDOC_RE.finditer(line):
            strip_tabs, delim = m.group(1) == "-", m.group(3)
            body: list[str] = []
            while i < len(lines):
                cur = lines[i].lstrip("\t") if strip_tabs else lines[i]
                i += 1
                if cur == delim:
                    break
                body.append(lines[i - 1])
            docs.append((line, "\n".join(body)))
    return "\n".join(outer), docs


def _git_ok(cwd: Path, *args: str) -> bool:
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"redteam: git check failed ({type(exc).__name__})", file=sys.stderr)
        return False
    return r.returncode == 0


def git_clean(path: Path) -> bool:
    """True if the file is git-tracked and identical to HEAD."""
    cwd = path.parent
    return (_git_ok(cwd, "ls-files", "--error-unmatch", "--", str(path))
            and _git_ok(cwd, "diff", "--quiet", "HEAD", "--", str(path)))


def resolve_module(mod: str, cwd: Path) -> Path | None:
    """Repo file a `python -m mod` would run (cwd first, then the repo root), or None."""
    rel = Path(*mod.split("."))
    for base in (cwd, REPO_ROOT):
        for cand in (base / rel.with_suffix(".py"), base / rel / "__main__.py"):
            if cand.is_file():
                return cand.resolve()
    return None


def tracked_script_run(command: str, cwd: Path) -> bool:
    """True if the command only runs a committed, unmodified script or `-m` module."""
    import shlex
    m = re.match(r"^\s*cd\s+(\"[^\"]+\"|'[^']+'|\S+)\s*&&\s*", command)
    if m:
        cwd = (cwd / m.group(1).strip("\"'")).resolve()
        command = command[m.end():]
    if "\n" in command or "$(" in command or any(ch in command for ch in ";&|`<>"):
        return False
    try:
        toks = shlex.split(command)
    except ValueError:
        return False
    i = 0
    while i < len(toks) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", toks[i]):
        i += 1
    if i >= len(toks):
        return False
    interp = re.sub(r"\.exe$", "", Path(toks[i]).name.lower())
    is_py = bool(re.fullmatch(r"python(?:3(?:\.\d+)?)?|py", interp))
    is_sh = interp in ("bash", "sh")
    if not (is_py or is_sh):
        return False
    i += 1
    while i < len(toks) and toks[i].startswith("-"):
        flag = toks[i]
        if is_py and flag == "-m" and i + 1 < len(toks):
            path = resolve_module(toks[i + 1], cwd)
            return path is not None and git_clean(path)
        if not is_py or not (flag in {"-u", "-B", "-E", "-s", "-I", "-O", "-OO"}
                             or re.fullmatch(r"-\d+(?:\.\d+)?", flag)):
            return False
        i += 1
    if i >= len(toks):
        return False
    script = toks[i]
    if not script.endswith(".py" if is_py else ".sh"):
        return False
    path = (cwd / script).resolve()
    return path.is_file() and git_clean(path)


MAX_ARG_FILES = 40


def _arg_tokens(text: str, depth: int = 0) -> list[str]:
    """Unquoted words of a command (redirect sources included), recursing into quoted
    `sh -c "..."`-style strings; every one that names an existing file gets scanned."""
    import shlex
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=";&|<>()")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = text.split()
    out: list[str] = []
    for t in toks:
        t = t.strip("'\"")
        if not t or t.startswith("-") or set(t) <= set(";&|<>()"):
            continue
        if any(c.isspace() for c in t) and depth < 2:
            out.extend(_arg_tokens(t, depth + 1))
        elif len(out) < MAX_ARG_FILES:
            out.append(t)
    return out[:MAX_ARG_FILES]


def _scan_file(p: Path, label: str) -> str | None:
    try:
        if p.is_file() and p.stat().st_size <= MAX_SCAN_BYTES:
            hit = sender_hit(p.read_text(encoding="utf-8", errors="replace").lower())
            return f"{hit} in {label}" if hit else None
    except OSError as exc:
        print(f"redteam: could not scan {label} ({type(exc).__name__})", file=sys.stderr)
    return None


def bash_decision(ti: dict, cwd_raw: Any) -> str | None:
    """Deny inline email senders. Only commands that execute something are scanned; pure file
    writes, reads, greps and commits pass untouched (see directive: limits)."""
    command = ti.get("command")
    if command is None:
        return None
    if not isinstance(command, str):
        raise TypeError("Bash command is not a string")
    outer, docs = split_heredocs(command)
    if not _EXEC_RE.search(outer):
        return None
    mh = mailer_hit(outer)
    if mh:
        return f"redteam gate: Bash command sends email inline ({mh}). {BASH_DENY}"
    if _B64_PIPE_RE.search(outer):
        return (f"redteam gate: Bash pipes base64-decoded data into an interpreter "
                f"(unscannable). {BASH_DENY}")
    cwd = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    # The command runs something, so every heredoc body counts (a body written to z.py and
    # run later in the same command is code, not a fixture).
    scan = "\n".join([outer] + [body for _opener, body in docs])
    hit = sender_hit(scan.lower())
    if hit is None:
        for tok in _arg_tokens(outer):
            p = Path(tok).expanduser()
            hit = _scan_file(p if p.is_absolute() else cwd / p, tok)
            if hit:
                break
    if hit is None:
        for m in _PY_MOD_RE.finditer(outer):
            mp = resolve_module(m.group(1), cwd)
            hit = _scan_file(mp, f"module {m.group(1)}") if mp else None
            if hit:
                break
    if hit is None or tracked_script_run(command, cwd):
        return None
    return f"redteam gate: Bash command sends email inline ({hit}). {BASH_DENY}"


def hook_decision(payload: dict, state: Path) -> str | None:
    """Return a full deny reason, or None to allow."""
    name = payload.get("tool_name") or ""
    if not isinstance(name, str):
        raise TypeError("tool_name is not a string")
    ti = payload.get("tool_input")
    if ti is None:
        ti = {}
    if not isinstance(ti, dict):
        raise TypeError("tool_input is not an object")
    if name == "Bash":
        return bash_decision(ti, payload.get("cwd"))
    action = gmail_action(name)
    if action is not None:
        reason = gmail_decision(action, ti, state)
    elif "calendar" in name.lower() and name.rsplit("__", 1)[-1] in CAL_ACTIONS:
        reason = calendar_decision(name.rsplit("__", 1)[-1], ti, state)
    else:
        return None
    return f"redteam gate: {reason}. {DENY_SUFFIX}" if reason else None


def _emit_deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}, separators=(",", ":")))


def _read_stdin() -> str:
    return sys.stdin.buffer.read().decode("utf-8", errors="replace")


_OUTWARD_RAW_RE = re.compile(r'"tool_name"\s*:\s*"mcp__[^"]*(?:gmail|calendar)', re.I)


def _is_outward(payload: Any, raw: str) -> bool:
    name = payload.get("tool_name") if isinstance(payload, dict) else None
    if isinstance(name, str):
        low = name.lower()
        return low.startswith("mcp__") and ("gmail" in low or "calendar" in low)
    return bool(_OUTWARD_RAW_RE.search(raw))


def cmd_hook(_args: argparse.Namespace) -> int:
    raw, payload = "", None
    try:
        raw = _read_stdin()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("hook payload is not an object")
        reason = hook_decision(payload, state_dir())
    except Exception as exc:  # fail-closed for outward tools only; Bash/other: exit 1 (allow)
        if _is_outward(payload, raw):
            _emit_deny(f"redteam gate error (fail-closed): {type(exc).__name__}")
            return EXIT_OK
        print(f"redteam gate error (non-outward tool allowed): {type(exc).__name__}",
              file=sys.stderr)
        return EXIT_UNGROUNDED
    if reason:
        _emit_deny(reason)
    return EXIT_OK


# --------------------------------------------------------------------------- PostToolUse hook

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
        action = gmail_action(str(payload.get("tool_name") or ""))
        if action not in ("create_draft", "update_draft"):
            return EXIT_OK
        ti = payload.get("tool_input") or {}
        if not isinstance(ti, dict):
            return EXIT_OK
        fields = text_fields(ti, GMAIL_META)
        if not fields:
            return EXIT_OK  # recipient/subject-only change: draft text unchanged
        did = str(ti.get("draftId") or "") if action == "update_draft" else ""
        did = did or extract_draft_id(payload.get("tool_response")) or ""
        if not did:
            print("redteam post-hook: no draft id in tool_response", file=sys.stderr)
            return EXIT_OK
        shas = [sha_of(raw, is_html) for _, raw, is_html in fields]
        _append_jsonl(state_dir() / DRAFTS,
                      {"draft_id": did, "sha256": shas[0], "sha256s": shas, "ts": _now()})
    except Exception as exc:  # PostToolUse must never break the session; a missing row only
        # makes a later send-by-draftId deny (fail-closed), so logging is enough.
        print(f"redteam post-hook error: {type(exc).__name__}", file=sys.stderr)
    return EXIT_OK


# --------------------------------------------------------------------------- SubagentStop hook

HANDBACK_TOOL = "SubagentHandback"

def _content_text(c: Any) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict) and b.get("type", "text") == "text" and isinstance(
                    b.get("text"), str):
                parts.append(b["text"])
            elif (isinstance(b, dict) and b.get("type") == "tool_use"
                  and b.get("name") == HANDBACK_TOOL
                  and isinstance((b.get("input") or {}).get("message"), str)):
                # Some harnesses return a subagent's final report through a hand-back tool
                # call instead of a plain text message (observed live 2026-11-04).
                parts.append(b["input"]["message"])
        return "\n".join(parts)
    if isinstance(c, dict):
        if isinstance(c.get("text"), str):
            return c["text"]
        if "content" in c:
            return _content_text(c["content"])
    return ""


def transcript_final_text(path: Path, agent_id: str, main_transcript: bool) -> str:
    """Text of the last assistant message (all its text blocks) in a JSONL transcript."""
    if not path.is_file() or path.stat().st_size > MAX_TRANSCRIPT_BYTES:
        return ""
    last_id: Any = object()
    last_text = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        if obj.get("type") != "assistant" and msg.get("role") != "assistant":
            continue
        aid = obj.get("agentId")
        if agent_id and aid and aid != agent_id:
            continue
        if main_transcript and not (obj.get("isSidechain") is True or (agent_id and aid == agent_id)):
            continue  # never take the main agent's own text as a lens verdict
        text = _content_text(msg.get("content"))
        if not text.strip():
            continue
        mid = msg.get("id")
        if mid is not None and mid == last_id:
            last_text = last_text + "\n" + text
        else:
            last_text = text
        last_id = mid if mid is not None else object()
    return last_text


def transcript_root() -> Path:
    env = os.environ.get("REDTEAM_TRANSCRIPT_ROOT", "").strip()
    return Path(env).expanduser() if env else Path.home() / ".claude" / "projects"


def agent_transcript(payload: dict) -> Path | None:
    """The subagent's own transcript, only if it lives under the transcript root and is named
    agent-<agent_id>.jsonl (a SubagentStop payload the harness wrote); else None."""
    aid, p = payload.get("agent_id"), payload.get("agent_transcript_path")
    if not (isinstance(aid, str) and re.fullmatch(r"[\w-]{1,128}", aid)
            and isinstance(p, str) and p):
        return None
    try:
        rp = Path(p).expanduser().resolve()
        root = transcript_root().resolve()
    except OSError:
        return None
    if rp.name != f"agent-{aid}.jsonl" or not rp.is_relative_to(root) or not rp.is_file():
        return None
    return rp


def subagent_final_text(payload: dict) -> tuple[str, str]:
    tp = agent_transcript(payload)
    if tp is None:
        return "", ""
    text = _content_text(payload.get("last_assistant_message"))
    if text.strip():
        return text, "last_assistant_message"
    return transcript_final_text(tp, str(payload["agent_id"]), False), "agent_transcript_path"


def cmd_subagent_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(_read_stdin())
        if not isinstance(payload, dict):
            return EXIT_OK
        text, origin = subagent_final_text(payload)
        if not text.strip():
            return EXIT_OK
        v = parse_verdict(text)
        if "error" in v:
            return EXIT_OK
        _append_jsonl(state_dir() / VERDICTS, {
            "lens": v["lens"], "sha12": v["sha"], "verdict": v["verdict"],
            "out_sha256": verdict_sha(text), "agent_id": str(payload.get("agent_id") or ""),
            "agent_type": str(payload.get("agent_type") or ""),
            "transcript_path": str(payload.get("agent_transcript_path") or ""),
            "text_from": origin, "ts": _now()})
    except Exception as exc:  # SubagentStop must never block; a missing row only makes record
        # refuse (fail-closed), so logging is enough.
        print(f"redteam subagent-hook error: {type(exc).__name__}", file=sys.stderr)
    return EXIT_OK


# --------------------------------------------------------------------------- UserPromptSubmit hook

_WAIVE_RE = re.compile(r"^\s*redteam waive ([0-9a-f]{12})\b\s*(.*)", re.I | re.S)


def cmd_prompt_hook(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(_read_stdin())
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        if not isinstance(prompt, str):
            return EXIT_OK
        m = _WAIVE_RE.match(prompt)
        if not m:
            return EXIT_OK
        sha12 = m.group(1).lower()
        reason = _WS_RE.sub(" ", m.group(2)).strip()[:500] or "(no reason given)"
        ts = _now()
        state = state_dir()
        _append_jsonl(state / WAIVERS, {"sha12": sha12, "reason": reason, "ts": ts,
                                        "session_id": str(payload.get("session_id") or ""),
                                        "source": "UserPromptSubmit"})
        _append_jsonl(state / PASSES, {"sha12": sha12, "waived": True, "reason": reason,
                                       "ts": ts, "by": "operator"})
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"redteam: operator waived {sha12}"}}, separators=(",", ":")))
    except Exception as exc:  # UserPromptSubmit must never block the operator's prompt
        print(f"redteam prompt-hook error: {type(exc).__name__}", file=sys.stderr)
    return EXIT_OK


# --------------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="redteam_gate.py",
        description="Deterministic red-team gate for outward text (directives/infrastructure/"
                    "redteam_gate.md). Exit codes: 0 ok/allow/passed, 1 ungrounded/weak claims, "
                    "2 usage error, 3 refused/not passed. State: $REDTEAM_DIR or .tmp/redteam/.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sha", help="print the 12-hex DRAFT-SHA of a draft file")
    s.add_argument("--draft", required=True)
    s.set_defaults(func=cmd_sha)

    s = sub.add_parser("ground", help="extract claims and ground them against sources (exit 1 if "
                                      "any ungrounded or weak)")
    s.add_argument("--draft", required=True)
    s.add_argument("--sources", nargs="+", required=True, help="files or directories")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_ground)

    s = sub.add_parser("record", help="record a pass: 0 ungrounded/weak + 4 logged lens PASS "
                                      "verdicts on the current DRAFT-SHA (exit 3 if refused)")
    s.add_argument("--draft", required=True)
    s.add_argument("--sources", nargs="+", required=True)
    s.add_argument("--verdicts", nargs="+", required=True)
    s.add_argument("--subject", help="exact subject line (Calendar: event summary)")
    s.add_argument("--to", nargs="+", metavar="ADDR")
    s.add_argument("--cc", nargs="+", metavar="ADDR")
    s.add_argument("--bcc", nargs="+", metavar="ADDR")
    s.add_argument("--attachments", nargs="+", metavar="PATH")
    s.set_defaults(func=cmd_record)

    s = sub.add_parser("waive", help="operator-only: prints how the operator waives (exit 2)")
    s.add_argument("rest", nargs="*")
    s.add_argument("--draft")
    s.add_argument("--reason")
    s.set_defaults(func=cmd_waive)

    s = sub.add_parser("check", help="exit 0 if this file's text passed (or was waived), else 3")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_check)

    for name, func, hlp in (
            ("hook", cmd_hook, "PreToolUse handler (stdin JSON, fail-closed)"),
            ("post-hook", cmd_post_hook, "PostToolUse handler: map draft id -> text sha"),
            ("subagent-hook", cmd_subagent_hook, "SubagentStop handler: log lens verdicts"),
            ("prompt-hook", cmd_prompt_hook, "UserPromptSubmit handler: operator waivers")):
        s = sub.add_parser(name, help=hlp)
        s.set_defaults(func=func)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.cmd in HOOK_CMDS and os.environ.get("REDTEAM_HOOK") != "1":
        print(f"redteam: `{args.cmd}` is hook-only (run by .claude/hooks/redteam-outward-gate.sh "
              "with REDTEAM_HOOK=1); verdicts come from SubagentStop, waivers from the operator.",
              file=sys.stderr)
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
