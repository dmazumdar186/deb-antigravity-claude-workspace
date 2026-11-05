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
* hook/post-hook/subagent-hook/prompt-hook refuse unless env REDTEAM_HOOK is 1 (set by the hook script).
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
CAL_ACTIONS = {"create_event", "update_event", "quick_add_event"}
CAL_ATTENDEE_KEYS = ("attendees", "attendeeEmails", "addedAttendees", "addedAttendeeEmails")
CAL_META = {"calendarId", "eventId", "start", "end", "startTime", "endTime", "timeZone",
            "attendees", "attendeeEmails", "addedAttendees", "addedAttendeeEmails",
            "removedAttendeeEmails", "sendUpdates", "notificationLevel", "colorId",
            "availability", "eventType", "visibility", "allDay", "addGoogleMeetUrl",
            "googleMeetUrl", "guestPermissions", "overrideReminders", "useDefaultReminders",
            "recurrenceData", "workingLocationProperties", "removedAttachmentFileUrls",
            "attachments", "addedAttachments", "recurrence", "conferenceData", "reminders",
            "transparency", "guestsCanInviteOthers", "guestsCanModify",
            "guestsCanSeeOtherGuests", "guestsCanSeeGuests"}
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
    if _present(subj) and (not isinstance(subj, str) or row.get("subject_sha") != sha_of(subj)):
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
        if r.get("sha256") != result["sha256"] or r.get("waived"):
            continue
        if all(r.get(k) == env[k] for k in env):
            print(f"already recorded: {sha12} {result['draft']}")
            return EXIT_OK
        diff = [k for k in env if r.get(k) != env[k]]
        print(f"REFUSED {sha12} {result['draft']}")
        print(f"- already recorded with a different envelope ({', '.join(diff)}); a pass is bound "
              "to one subject/recipients/attachments set. Change the wording and re-run the lenses "
              "for a new envelope.")
        return EXIT_REFUSED
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

_MAIL_TOOL_RE = re.compile(r"send_email|send_message|create_draft", re.I)


def gmail_action(tool_name: str) -> str | None:
    suffix = tool_name.rsplit("__", 1)[-1]
    if "gmail" not in tool_name.lower():
        # Any MCP mail-like sender (send_email/send_message/create_draft) is gated as email.
        if tool_name.startswith("mcp__") and _MAIL_TOOL_RE.search(suffix) and (
                "mail" in tool_name.lower() or suffix.lower() == "create_draft"):
            return suffix if suffix in GMAIL_KNOWN else "generic"
        return None
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


_ADDR_KEYS_ALL = {"to", "cc", "bcc", "recipients", "recipient", "emailaddress", "emails",
                  "email", "attendees"}


def unparseable_input(ti: dict, meta: set[str]) -> str | None:
    """Outward tool input that the text/recipient checks cannot read: None values, recipient
    fields that are not strings/lists of strings or {email}, and non-text scalars in text slots."""
    for k, v in ti.items():
        if v is None:
            return f"{k} is null (unparseable outward input; omit it or give a value)"
        lk = str(k).lower()
        if lk in _ADDR_KEYS_ALL:
            items = v if isinstance(v, list) else [v]
            if not all(isinstance(x, str) or (isinstance(x, dict) and isinstance(
                    x.get("email"), str)) for x in items):
                return f"{k} has a non-string recipient (unparseable)"
        elif k not in meta and isinstance(v, (int, float)) and not isinstance(v, bool) \
                and lk in ("body", "text", "message", "content", "htmlbody", "subject"):
            return f"{k} is not text (unparseable outward input)"
    return None


def gmail_decision(action: str, ti: dict, state: Path) -> str | None:
    bad = unparseable_input(ti, GMAIL_META)
    if bad:
        return f"{action}: {bad}"
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
        if _present(ti.get("subject")):
            return f"{action} sets a subject with no vetted body text to bind it to"
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
            and not k.lower().startswith("removed") and _present(ti.get(k))
            and (k in CAL_ATTENDEE_KEYS or isinstance(ti.get(k), (list, dict, str)))]


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
    gated = invites or action == "quick_add_event" or (
        action == "update_event" and notif not in ("NONE",))
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
                  "api.send" "grid.com", "re" "send.com", "post" "markapp.com",
                  "messages.se" "nd(", "send-mail" "message", "mailer" "send.com",
                  "mail" "trap.io", "spark" "post.com", "loops" ".so", "@sendgrid/" "mail",
                  "send_transac" "_email", "googleapis.com/upload" "/gmail", "net::" "smtp",
                  "smtp" "://", "smtp" "s://", "--mail" "-rcpt", "mailgun" ".net/v3",
                  "api.brevo" ".com", "api.sendin" "blue.com", "send" "-email", "send-raw" "-email",
                  "send" "_email(", "send" "_raw_email(", "sendgridapi" "client", "yag" "mail",
                  "api.mail" "jet.com", "mandrill" "app.com", "smart" "lead.ai")
_SES_RE = re.compile(r"email(?:-smtp)?\.[a-z0-9-]+\.amazon" r"aws\.com")
# Mail programs: a hit when they are the program a simple command runs.
_MAILERS = {"mail", "mailx", "msmtp", "swaks", "mutt", "send" "mail", "s-nail", "neomutt",
            "ssmtp", "send" "email", "exim", "exim4"}
# Wrappers that run the next word as the program (their own flags/numeric args are skipped).
_WRAPPERS = {"sudo", "env", "exec", "xargs", "nohup", "time", "timeout", "nice", "watch",
             "builtin",
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
               r"mailx?|msmtp|ssmtp|send" r"email|exim4?|swaks|aws|mutt|neomutt|s-nail|"
               r"pwsh|powershell|go|npx|tsx|ts-node|npm|pnpm|yarn|uv|uvx|pdm|poetry|hatch|pipx|"
               r"ipython3?|make|(?:ba|z|da|k)?sh")
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
        for word in command_words(outer):  # quoted program: "python3" x.py, "/usr/bin/python3"
            name = re.split(r"[/\\]", word)[-1]
            if word in ("source", ".", "eval") or (name and _EXEC_WORD_RE.fullmatch(name)):
                return True
        return False


_EXEC_RE = _ExecFinder()


def command_words(outer: str) -> list[str]:
    """The program word of each simple command (quotes removed; env assignments and wrapper
    words skipped)."""
    import shlex
    out: list[str] = []
    for seg in _SEGMENT_SPLIT_RE.split(outer):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = [t.strip("'\"") for t in seg.split()]
        i = 0
        while i < len(toks):
            t = toks[i]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t, re.S) or t.lower() in _WRAPPERS or (
                    i > 0 and (t.startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", t))):
                i += 1
                continue
            break
        if i < len(toks):
            out.append(toks[i])
    return out


def _xuser(p: Path) -> Path:
    """expanduser that keeps an unresolvable `~user` path literal instead of raising."""
    try:
        return p.expanduser()
    except RuntimeError:
        return p


_MAKE_RE = re.compile(r"(?:^|[\s;&|(/])g?make(?:\s+(?:\"[^\"]*\"|'[^']*'|[^\s;&|)]+))*")


def makefiles(expanded: str, bases: list[Path]) -> list[Path]:
    """Makefiles a `make` invocation reads: -C/--directory dir, -f/--file/--makefile file."""
    import shlex
    out: list[Path] = []
    for m in _MAKE_RE.finditer(expanded):
        try:
            toks = shlex.split(m.group(0))[1:]
        except ValueError:
            toks = m.group(0).split()[1:]
        dirs: list[Path] = []
        files: list[str] = []
        i = 0
        while i < len(toks):
            t = toks[i]
            for flag, dest in (("-C", dirs), ("--directory", dirs), ("-f", files), ("--file", files),
                               ("--makefile", files)):
                if t == flag and i + 1 < len(toks):
                    dest.append(Path(toks[i + 1]) if dest is dirs else toks[i + 1])
                    i += 1
                    break
                if t.startswith(flag + "=") or (len(flag) == 2 and t.startswith(flag) and len(t) > 2):
                    v = t.split("=", 1)[1] if "=" in t else t[2:]
                    dest.append(Path(v) if dest is dirs else v)
                    break
            i += 1
        roots: list[Path] = []
        for b in bases:
            if dirs:
                for d in dirs:
                    d = _xuser(d)
                    b = d if d.is_absolute() else b / d
                roots.append(b)
            else:
                roots.append(b)
        for r in roots:
            names = files or ["GNUmakefile", "makefile", "Makefile"]
            for n in names:
                fp = _xuser(Path(n))
                out.append(fp if fp.is_absolute() else r / fp)
    return out


_FIND_EXEC_RE = re.compile(r"(?:^|[\s;&|(])find\s+(.*?)\s-(?:exec|execdir|ok|okdir)\s+(\S+)", re.S)


def find_exec_hit(expanded: str, bases: list[Path]) -> str | None:
    """`find ROOT ... -exec <program> {} ;`: scan files under ROOT (matching -name if given),
    bounded by MAX_ARG_FILES (fail closed past it)."""
    import fnmatch
    import shlex
    for m in _FIND_EXEC_RE.finditer(expanded):
        prog = re.split(r"[/\\]", m.group(2).strip("'\""))[-1]
        if not _EXEC_WORD_RE.fullmatch(prog) and not prog.startswith("."):
            continue
        try:
            args = shlex.split(m.group(1))
        except ValueError:
            args = m.group(1).split()
        roots = [a for a in args if not a.startswith(("-", "(", ")", "!"))][:1] or ["."]
        pat = None
        for i, a in enumerate(args):
            if a in ("-name", "-iname") and i + 1 < len(args):
                pat = args[i + 1]
        count = 0
        for b in bases:
            rp = _xuser(Path(roots[0]))
            root = rp if rp.is_absolute() else b / rp
            if not root.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fn in filenames:
                    if pat and not fnmatch.fnmatch(fn, pat):
                        continue
                    count += 1
                    if count > MAX_ARG_FILES:
                        raise ScanLimit(f"find -exec over more than {MAX_ARG_FILES} files")
                    hit = _scan_file(Path(dirpath) / fn, fn)
                    if hit:
                        return f"{hit} (via find -exec {prog})"
            break
    return None


def _is_binary(p: Path) -> bool:
    try:
        with p.open("rb") as fh:
            head = fh.read(4)
    except OSError:
        return True
    return head[:4] == b"\x7fELF" or head[:2] == b"MZ" or head[:4] in (
        b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


def direct_scripts(outer: str, bases: list[Path], path_only: bool | None = False) -> list[Path]:
    """Script files a command runs directly (`./x`, `/abs/x`, `dir/x`, or a bare name found in
    cwd/PATH that is a text file with a shebang). path_only: False = explicit/cwd scripts only
    (these make the command count as executing code), True = PATH-resolved console scripts only
    (scanned themselves, but their arguments are not: `pytest tests/` stays cheap), None = both."""
    import shutil
    found: list[Path] = []
    for w in command_words(outer):
        if not w or w.startswith("$") or _EXEC_WORD_RE.fullmatch(re.split(r"[/\\]", w)[-1]):
            continue
        cands: list[Path] = []
        p = _xuser(Path(w))
        if p.is_absolute():
            cands = [p]
        elif "/" in w or "\\" in w:
            cands = [b / p for b in bases]
        else:
            cands = [b / w for b in bases]
            which = shutil.which(w)
            if which:
                cands.append(Path(which))
        for c in cands:
            via_path = not ("/" in w or "\\" in w) and c.parent not in bases
            if path_only is not None and via_path != path_only:
                continue
            try:
                if not c.is_file() or _is_binary(c):
                    continue
                if "/" not in w and "\\" not in w:
                    with c.open("rb") as fh:
                        if fh.read(2) != b"#!":
                            continue
            except OSError:
                continue
            found.append(c)
            break
    return found


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


def sender_hit(low: str, raw: str | None = None) -> str | None:
    for pat in _SENDER_SIMPLE:
        if pat in low:
            return pat
    if _GMAIL_API in low and "/send" in low:
        return "Gmail REST /send"
    if _INSTANTLY_API in low and ("/emails" in low or "/reply" in low):
        return "Instantly emails/reply API"
    if _SES_RE.search(low):
        return "Amazon SES endpoint"
    m = _SENDER_MULTI_RE.search(low)
    if m:
        return _WS_RE.sub("", m.group(0))
    if _SES_CALL_RE.search(low) and _SES_CTX_RE.search(low):
        return "SES send" "_email("
    if "mail" "gun" in low and _MAILGUN_CALL_RE.search(low):
        return "Mailgun messages.cre" "ate("
    return outward_api_hit(low, raw)


# Non-email outward channels (chat, social, SMS, LinkedIn, cold-email tools). Send endpoints and
# SDK send calls only: reads (conversations.list, GET /me, ...) do not match. Split literals.
_OUTWARD_SIMPLE = (
    ("hooks.sla" "ck.com", "Slack webhook"),
    ("outlook.office" ".com/webhook", "Outlook/Teams webhook"),
    ("outlook.office365" ".com/webhook", "Outlook/Teams webhook"),
    ("files_up" "load(", "Slack files_upload"),
    ("slack.com/api/chat.post" "message", "Slack chat.postMessage"),
    ("slack.com/api/chat.post" "ephemeral", "Slack chat.postEphemeral"),
    ("slack.com/api/chat.schedule" "message", "Slack chat.scheduleMessage"),
    ("slack.com/api/chat.up" "date", "Slack chat.update"),
    ("slack.com/api/chat.me" "message", "Slack chat.meMessage"),
    ("files_upload" "_v2(", "Slack files_upload_v2"),
    ("slack.com/api/files.up" "load", "Slack files.upload"),
    ("slack.com/api/files.complete" "uploadexternal", "Slack files upload"),
    ("chat_post" "message", "Slack chat_post" "Message"),
    ("chat_post" "ephemeral", "Slack chat_post" "Ephemeral"),
    ("chat_schedule" "_message", "Slack chat_scheduleMessage"),
    ("discord.com/api/web" "hooks", "Discord webhook"),
    ("discordapp.com/api/web" "hooks", "Discord webhook"),
    ("webhook.office" ".com", "Teams webhook"),
    ("logic.azure" ".com", "Teams workflow webhook"),
    ("api.lem" "list.com", "lemlist API"),
    ("api.twitter.com/2/tw" "eets", "X/Twitter post"),
    ("api.x.com/2/tw" "eets", "X/Twitter post"),
    ("api.twitter.com/1.1/statuses/up" "date", "X/Twitter post"),
    ("api.twitter.com/2/dm_" "conversations", "X/Twitter DM"),
    ("api.x.com/2/dm_" "conversations", "X/Twitter DM"),
)
_OUTWARD_RES = (
    (re.compile(r"\.chat\s*\.\s*post(?:message|ephemeral)\s*\(|\bchat\s*\.\s*schedulemessage\s*\("),
     "Slack chat.postMessage SDK"),
    (re.compile(r"api\.linked" r"in\.com/[\w./-]*(?:ugcposts|/posts|/messages|/shares|invitations|"
                r"/socialactions)"), "LinkedIn API post/message"),
    (re.compile(r"linked" r"in\.com/voyager/api/[\w./-]*(?:messaging|invitation|normin"
                r"vitations|contentcreation|feed/shares|ugcposts)"), "LinkedIn voyager send"),
    (re.compile(r"api\.instan" r"tly\.ai/api/v\d/(?:campaigns?/[\w-]+/(?:activate|resume|launch)|"
                r"campaign/launch|leads?(?:/(?:add|bulk))?\b|emails/(?:reply|send|forward))"),
     "Instantly campaign/leads API"),
    (re.compile(r"graph\.facebook\.com/[\w./-]*/media_publish"), "Meta Graph publish"),
    (re.compile(r"api\.telegram\.org/bot[^\s/]*/(?:send\w+|forwardmessages?|copymessages?)"),
     "Telegram send"),
    (re.compile(r"discord(?:app)?\.com/api/v\d+/web" r"hooks/"), "Discord webhook"),
    (re.compile(r"\b(?:async)?(?:webhookclient|incomingwebhook)\b[\s\S]{0,300}?\.\s*send\s*\("),
     "Slack webhook SDK send"),
    (re.compile(r"graph\.(?:facebook|instagram)\.com/[\w./-]*/media_publish"), "Meta publish"),
    (re.compile(r"threads\.net/[\w./-]*threads_publish"), "Threads publish"),

    (re.compile(r"\bbot\s*\.\s*(?:telegram\s*\.\s*)?(?:send_?(?:message|photo|document|video|"
                r"audio|media_?group|animation|voice|sticker|poll)|forward_?messages?|"
                r"copy_?messages?)\s*\("),
     "Telegram bot send"),
    (re.compile(r"\bcreate_tweet\s*\(|\bupdate_status\s*\(|\.v2\s*\.\s*tweet\s*\("), "X/Twitter SDK post"),
)


_PORT_RE = re.compile(r"(\.[a-z]{2,}):\d{1,5}(?=[/\s'\"]|$)")
_TWILIO_CALL_RE = re.compile(r"\bmessages\s*\.\s*create\s*\(")
_DISCORD_PY_RE = re.compile(r"\b(?:channel|ctx|user|member|thread|dm)\s*\.\s*send\s*\(")
_DISCORD_CTX_RE = re.compile(r"\bimport\s+discord\b|\bfrom\s+['\"]?discord|require\(['\"]discord|"
                             r"import\s*\(\s*['\"]discord")


# Endpoints that are also readable by GET: a hit needs a write signal in the same text.
_WRITE_ENDPOINT_RES = (
    (re.compile(r"discord(?:app)?\.com/api/(?:v\d+/)?channels/\d+/messages"), "Discord message"),
    (re.compile(r"graph\.microsoft\.com/[\w./-]*(?:chats|channels|teams)/[\w./-]*messages"),
     "MS Graph Teams message"),
    (re.compile(r"chat\.google" r"apis\.com/v\d+/spaces/[\w./-]*messages"), "Google Chat API"),
    (re.compile(r"api\.twilio\.com/[\w./-]*/messages"), "Twilio message"),
    (re.compile(r"api\.github\.com/repos/[\w./-]*/(?:comments|issues|pulls|reviews|releases)\b"),
     "GitHub comment/issue/PR API"),
    (re.compile(r"threads\.net/[\w./-]*/threads\b"), "Threads post"),
    (re.compile(r"graph\.facebook\.com/[\w./-]*(?:/feed|/messages|/photos|/videos)"),
     "Meta Graph post/message"),
)
_WRITE_SIGNAL_RE = re.compile(
    r"(?:-x|--request|--method)[\s=]*['\"]?(?:post|put|patch)\b"
    r"|(?:^|\s)-[dt](?![a-z-])|(?:^|\s)--(?:data|form)[\w-]*|(?:^|\s)--(?:json|upload-file|"
    r"post-data|post-file)\b"
    r"|\b(?:http|https|xh|xhs)\s+(?:-\S+\s+)*(?:post|put|patch)\b"
    r"|\.(?:post|put|patch|create)\s*\(|\.request\s*\(\s*['\"](?:post|put|patch)"
    r"|method\s*[:=]\s*['\"](?:post|put|patch)|\brequest\s*\([^)]*\bdata\s*="
    r"|\b(?:http|https|xh|xhs)\s+(?:-\S+\s+)*\S+\s+[^\s=]+:?=")


# Flags are case-sensitive: curl -F (form, a write) vs -f/--fail (not). With the raw text the
# check is exact; on lowercased-only input (scanned files) -f stays a write (fail safe).
_FORM_FLAG_RE = re.compile(r"(?:^|\s)-F(?![A-Za-z-])")
_F_FLAG_LOW_RE = re.compile(r"(?:^|\s)-f(?![a-z-])")


_EXTRA_SEND_RES = (
    (re.compile(r"\bchat_(?:schedule" r"message|up" r"date|me" r"message)\s*\("), "Slack SDK chat call"),
    (re.compile(r"\bapi_call\s*\(\s*['\"]chat\.(?:post|update|schedule|me)"), "Slack api_call"),
    (re.compile(r"\.\s*files\s*\.\s*upload(?:v2)?\s*\("), "Slack files.upload"),
    (re.compile(r"\bbot\s*\([^)]*\)\s*\.\s*(?:send_?\w+|forward_?\w+|copy_?\w+)\s*\("),
     "Telegram Bot().send"),
    (re.compile(r"\bbot\s*\.\s*api\s*\.\s*(?:send\w+|forward\w+|copy\w+)\s*\("), "Telegram bot.api"),
    (re.compile(r"graph\.microsoft\.com/[\w./-]*/messages/[\w=+-]+/(?:reply|replyall|forward|"
                r"send)\b|graph\.microsoft\.com/[\w./-]*/send" r"mail\b"), "MS Graph mail send"),
)


def outward_api_hit(low: str, raw: str | None = None) -> str | None:
    low = _PORT_RE.sub(r"\1", low)
    if "api.github" ".com/graphql" in low and "mutation" in low:
        return "GitHub GraphQL mutation"
    if "tele" "thon" in low and re.search(r"\.\s*send_(?:message|file)\s*\(", low):
        return "Telethon send"
    for rx, label in _EXTRA_SEND_RES:
        if rx.search(low):
            return label
    for rx, label in _WRITE_ENDPOINT_RES:
        if rx.search(low) and (_WRITE_SIGNAL_RE.search(low) or (
                _FORM_FLAG_RE.search(raw) if raw is not None else _F_FLAG_LOW_RE.search(low))):
            return label
    if "twil" "io" in low and _TWILIO_CALL_RE.search(low):
        return "Twilio messages.cre" "ate("
    if _DISCORD_CTX_RE.search(low) and _DISCORD_PY_RE.search(low):
        return "discord.py send"
    for pat, label in _OUTWARD_SIMPLE:
        if pat in low:
            return label
    for rx, label in _OUTWARD_RES:
        if rx.search(low):
            return label
    return None


# SDK call forms, tolerant of whitespace/newlines inside the chain (lowercased input).
_SENDER_MULTI_RE = re.compile(
    r"(?:messages|drafts)\s*\(\s*\)\s*\.\s*se" r"nd\s*\("
    r"|\.\s*messages\s*\.\s*se" r"nd\s*\("
    r"|\.\s*emails\s*\.\s*se" r"nd\s*\("                       # Resend py/node
    r"|\bsend" r"email(?:withtemplate)?\s*\("                    # Postmark
    r"|\bsend(?:raw)?" r"emailcommand\b"                         # SES JS v3
    r"|\bsend" r"transacemail\s*\(|\bsend_transac" r"tional_email\s*\("
    r"|googleapis\.com/gmail" r"/v1")
_SES_CTX_RE = re.compile(r"client\s*\(\s*['\"]ses(?:v2)?['\"]|\bsesv2\b|\bboto3\b[\s\S]*\bses\b")
_SES_CALL_RE = re.compile(r"\bsend" r"_email\s*\(")
_MAILGUN_CALL_RE = re.compile(r"\bmessages\s*\.\s*create\s*\(")
_PHP_MAIL_RE = re.compile(r"(?<![\w$>:])mail\s*\(")


def _unquoted_mask(line: str, quote: str) -> tuple[list[bool], str]:
    """Per-char 'outside quotes' flags for a line, given the quote state carried in."""
    mask: list[bool] = []
    esc = False
    for ch in line:
        if quote == "'":
            mask.append(False)
            if ch == "'":
                quote = ""
            continue
        if quote == '"':
            mask.append(False)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = ""
            continue
        if esc:
            esc = False
            mask.append(False)
            continue
        if ch == "\\":
            esc = True
            mask.append(False)
        elif ch in "'\"":
            quote = ch
            mask.append(False)
        else:
            mask.append(True)
    return mask, quote


def split_heredocs(command: str) -> tuple[str, list[tuple[str, str]]]:
    """(command text without heredoc bodies, [(opener line, body)]). Quote-aware: a `<<X`
    inside quotes is not a heredoc opener."""
    lines = command.split("\n")
    outer: list[str] = []
    docs: list[tuple[str, str]] = []
    quote = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        outer.append(line)
        i += 1
        mask, quote = _unquoted_mask(line, quote)
        for m in _HEREDOC_RE.finditer(line):
            if not mask[m.start()]:
                continue
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


# ------------------------------------------------------------------ client-visible deploys
_DEPLOY_VAL_FLAGS = {"--project-name", "--branch", "--commit-hash", "--commit-message", "--env",
                     "-e", "-c", "--config", "--name", "--compatibility-date", "--scope",
                     "--token", "-t", "--site", "-s", "--auth", "--alias", "-a", "--message",
                     "-m", "--functions", "-f", "--build-env", "--meta", "--regions", "--target",
                     "--dir", "-d", "--cwd", "--output-dir"}
_VERCEL_NON_DEPLOY = {"ls", "list", "logs", "env", "pull", "link", "login", "whoami", "inspect",
                      "domains", "dns", "project", "projects", "teams", "help", "dev", "build",
                      "rm", "remove", "alias", "certs", "secrets", "switch", "git", "rollback", "init",
                      "open", "redeploy-help"}
_DEPLOY_SKIP_DIRS = ("node_modules/", ".wrangler/", ".vercel/", ".netlify/")
DEPLOY_DENY = ("Client pages deploy only from committed content: commit the source dir (page "
               "text is covered by the build-contract audit), then deploy that clean dir.")


def split_simple_commands(text: str) -> list[str]:
    """Split shell text into simple commands on separators OUTSIDE quotes."""
    out: list[str] = []
    cur: list[str] = []
    quote = ""
    esc = False
    for idx, ch in enumerate(text):
        if esc:
            cur.append(ch)
            esc = False
            continue
        if ch == "\\" and quote != "'":
            esc = True
            cur.append(ch)
            continue
        if quote:
            if ch == quote:
                quote = ""
            cur.append(ch)
            continue
        if ch in "'\"":
            quote = ch
            cur.append(ch)
            continue
        if ch in "{}" and not (
                (ch == "{" and (idx + 1 >= len(text) or text[idx + 1].isspace()))
                or (ch == "}" and (idx == 0 or text[idx - 1] in " \t;\n"))):
            cur.append(ch)  # brace expansion ({a,b}, ${x}), not a command group
            continue
        if ch in "\n;&|(){}`":
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return [c for c in out if c.strip()]


_RUNNERS = {"npx", "pnpx", "bunx"}
_DEPLOY_TOOLS = {"wrangler": "wrangler", "vercel": "vercel", "netlify": "netlify",
                 "ntl": "netlify", "vc": "vercel"}
_DEPLOY_WRAPPERS = {"setsid", "unbuffer", "doas", "corepack", "chronic", "caffeinate",
                    "busybox", "toybox"}
_PKG_VAL_FLAGS = {"--filter", "-F", "-C", "--dir", "--cwd", "-w", "--workspace", "--prefix"}
_PKG_MANAGERS = {"npm", "pnpm", "yarn", "bun"}


def _tool_name(tok: str) -> str | None:
    base = re.split(r"[/\\]", tok)[-1].lower()
    base = re.sub(r"\.(?:c|m)?js$|\.cmd$|\.exe$|\.ps1$", "", base)
    if base.startswith("@"):
        base = base.split("/")[-1]
    base = base.split("@")[0]
    return _DEPLOY_TOOLS.get(base)


_SHELL_KEYWORDS = {"in", "do", "done", "if", "then", "elif", "else", "fi", "while", "until",
                   "!", "{", "}", "time", "coproc", "esac", "[[", "]]"}


def program_argv(toks: list[str]) -> list[str]:
    """Strip env assignments, wrappers (+ their flags/numbers) and package runners
    (npx/pnpx/bunx, `bun x`, `pnpm|yarn dlx|exec`, `npm exec [--]`, `node <bin>`)."""
    i = 0
    if toks and toks[0] in ("for", "select", "case", "function"):
        return []  # loop/case header: its body segments are checked on their own
    while i < len(toks):
        t = toks[i]
        low = re.split(r"[/\\]", t)[-1].lower()
        if t in _SHELL_KEYWORDS:
            i += 1
            continue
        if low == "flock":
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
            i += 1  # the lock file
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t, re.S) or low in _WRAPPERS \
                or low in _RUNNERS or low in _DEPLOY_WRAPPERS:
            i += 1
            while i < len(toks) and (toks[i].startswith("-") or re.fullmatch(r"[\d.]+[smhd]?",
                                                                              toks[i])):
                if toks[i] in ("-S", "--split-string") and i + 1 < len(toks) and low == "env":
                    import shlex
                    try:
                        toks = toks[:i] + shlex.split(toks[i + 1]) + toks[i + 2:]
                    except ValueError:
                        toks = toks[:i] + toks[i + 1].split() + toks[i + 2:]
                    break
                if toks[i] in ("-p", "--package", "-C", "--chdir", "-u", "--unset", "-g",
                               "-n", "-I", "-i", "-L", "-P", "-d", "-E", "-s") and \
                        i + 1 < len(toks):
                    i += 1
                i += 1
            continue
        if low in _PKG_MANAGERS:
            k = i + 1
            while k < len(toks) and toks[k].startswith("-"):
                k += 2 if toks[k] in _PKG_VAL_FLAGS else 1
            if k < len(toks) and toks[k].lower() in ("x", "dlx", "exec") and k > i + 1:
                i = k + 1
                while i < len(toks) and toks[i].startswith("-"):
                    i += 1
                continue
        if low in _PKG_MANAGERS and i + 1 < len(toks) and toks[i + 1].lower() in (
                "x", "dlx", "exec"):
            i += 2
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
            continue
        if re.split(r"[/\\]", low)[-1] in ("node", "node.exe", "bun", "deno") and i + 1 < len(
                toks) and _tool_name(toks[i + 1]):
            i += 1
            continue
        break
    return toks[i:]


def _deploy_target(tool: str, argv: list[str]) -> tuple[bool, str | None]:
    """(is_deploy, explicit_dir or None = the cwd project)."""
    pos: list[str] = []
    named: dict[str, str] = {}
    flags: set[str] = set()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("-"):
            k, eq, v = a.partition("=")
            flags.add(k)
            if eq:
                named[k] = v
            elif i + 1 < len(argv) and (
                    (k == "--dry-run" and argv[i + 1].lower() in (
                        "true", "false", "0", "1", "yes", "no", "on", "off"))
                    or k in _DEPLOY_VAL_FLAGS):
                named[k] = argv[i + 1]
                i += 1
        else:
            pos.append(a)
        i += 1
    if flags & {"--help", "-h"} or pos[:1] == ["help"]:
        return False, None
    if "--dry-run" in flags and str(named.get("--dry-run", "true")).lower() not in (
            "false", "0", "no", "off"):
        return False, None
    if tool == "wrangler":
        if pos[:2] in (["pages", "deploy"], ["pages", "publish"]):
            return True, pos[2] if len(pos) > 2 else named.get("--output-dir")
        if pos[:3] == ["pages", "deployment", "create"]:
            return True, pos[3] if len(pos) > 3 else None
        if pos[:1] in (["deploy"], ["publish"]) or pos[:2] in (
                ["versions", "deploy"], ["versions", "upload"]):
            return True, None
        return False, None
    if tool == "vercel":
        if flags & {"--version", "-v", "--help", "-h"} and not pos:
            return False, None
        if pos[:1] == ["promote"] or pos[:2] == ["alias", "set"]:
            return True, None
        if pos and pos[0] in _VERCEL_NON_DEPLOY:
            return False, None
        rest = pos[1:] if pos[:1] == ["deploy"] else pos
        return True, named.get("--cwd") or (rest[0] if rest else None)
    if pos[:1] == ["deploy"] and flags & {"--prod", "-p", "--production", "--prod-if-unlocked"}:
        return True, named.get("--dir") or named.get("-d")
    return False, None


_HTTPIE = {"http", "https", "xh", "xhs", "httpie"}
_SCRIPT_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".rb", ".pl", ".php"}
_PIPE_SH_RE = re.compile(r"\|\s*(?:\S*/)?(?:(?:ba|z|da|k)?sh|at|batch)\b")
_DEPLOY_SUBST_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
_PIPE_INTERP_RE = re.compile(r"\|\s*(?:\S*/)?(?:python(?:3(?:\.\d+)?)?|node|ruby|perl|php|deno|bun)"
                             r"\b")
_SH_STRING_RE = re.compile(r"(?:^|['\"\s])(?:\S*/)?(?:ba|z|da|k)?sh\s+(?:-\S+\s+)*"
                           r"([\w./-]+\.(?:sh|bash))\b")
_CMD_STRING_PROGS = {"tmux", "screen", "su", "at", "batch", "sg", "runuser", "nsenter",
                     "firejail", "systemd-run"}
# A script file that both names a deploy and executes a subprocess is a deploy.
_DEPLOY_LEX_RE = re.compile(
    r"\bwrangler\b['\"\s,\[]+(?:pages['\"\s,\[]+(?:deploy|publish|deployment)|deploy|publish|"
    r"versions['\"\s,\[]+(?:deploy|upload))"
    r"|['\"](?:vercel|vc)['\"]\s*,\s*\[?\s*['\"](?:deploy|--prod|promote)['\"]"
    r"|['\"](?:netlify|ntl)['\"]\s*,\s*\[?\s*['\"]deploy['\"]"
    r"|\bvercel\b[^\n]{0,80}?(?:--prod|['\"\s,]promote\b|['\"\s,]deploy\b)"
    r"|\b(?:netlify|ntl)\b['\"\s,]+deploy\b[^\n]{0,80}?--prod")
_SPAWN_RE = re.compile(r"subprocess|os\.system|popen|execsync|execfilesync|spawn|child_process|"
                       r"\bexeca\b|\bsystem\s*\(|\$\(|`|shell_exec|passthru|proc_open|"
                       r"\bexec\s*\(|%x\{|\bopen3\b")


def script_deploy_error(text: str, where: Path, proj: Path | None = None) -> str | None:
    low = text.lower()
    m = None
    if where.suffix.lower() in (".sh", ".bash", "", ".mk", ".zsh", ".ps1", ".bat", ".cmd"):
        m = _DEPLOY_LEX_RE.search(low)
    else:
        # code files: the deploy words must sit within 3 lines after a spawn call
        lines = low.splitlines()
        for i, ln in enumerate(lines):
            if _SPAWN_RE.search(ln):
                m = _DEPLOY_LEX_RE.search("\n".join(lines[i:i + 4]))
                if m:
                    break
    if not m:
        return None
    why = project_clean_error(proj or where.parent)
    return f"deploy call ({m.group(0)[:40]}) in {where}: {why}" if why else None


def deploy_error(outer: str, cwd: Path, depth: int = 0) -> str | None:
    """Deny client-visible deploys whose source is not committed (or gitignored build output
    of a clean committed project); follow `npm|pnpm|yarn|bun run X`. Also denies httpie
    (`http`/`https`/`xh`) calls to outward send endpoints (httpie is not an exec word)."""
    import shlex
    base = cwd
    if depth < 3 and ("$(" in outer or "`" in outer):
        def _subst(m: re.Match) -> str:
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            try:
                it = shlex.split(inner)
            except ValueError:
                it = inner.split()
            if it[:1] in (["echo"], ["printf"]):
                return " ".join(it[1:])
            if it[:1] == ["cat"] and len(it) == 2:
                try:
                    return _read_limited(cwd / it[1], it[1]) or ""
                except (OSError, ScanLimit):
                    return ""
            if it[:1] == ["pwd"]:
                return str(cwd)
            return m.group(0)
        for m in _DEPLOY_SUBST_RE.finditer(outer):
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            err = deploy_error(inner, cwd, depth + 1)
            if err:
                return err
        sub = _DEPLOY_SUBST_RE.sub(_subst, outer)
        if sub != outer:
            err = deploy_error(sub, cwd, depth + 1)
            if err:
                return err
    loop_vars: dict[str, list[str]] = {}
    for seg in split_simple_commands(outer):
        lm = re.match(r"\s*(?:for|select)\s+([A-Za-z_]\w*)\s+in\s+(.*)$", seg)
        if lm:
            try:
                loop_vars[lm.group(1)] = shlex.split(lm.group(2))[:10]
            except ValueError:
                loop_vars[lm.group(1)] = lm.group(2).split()[:10]
            continue
        used = [v for v in loop_vars if re.search(r"\$\{?" + v + r"\b", seg)]
        if used and depth < 3:
            for item in loop_vars[used[0]]:
                err = deploy_error(re.sub(r"\$\{" + used[0] + r"\}|\$" + used[0] + r"\b",
                                          lambda _m, it=item: it, seg), base, depth + 1)
                if err:
                    return err
            continue
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        for n, t in enumerate(toks[:-1]):
            if t in ("-C", "--chdir") and "env" in [x.lower() for x in toks[:n]]:
                base = base / toks[n + 1]
        redir = toks.index("<") if "<" in toks[1:] else None
        stdin_file = toks[redir + 1] if redir is not None and redir + 1 < len(toks) else None
        if redir is not None:
            toks = toks[:redir] + toks[redir + 2:]
        argv = program_argv(toks)
        if not argv:
            continue
        prog = argv[0]
        if stdin_file and depth < 3:
            nm = re.split(r"[/\\]", prog.lower())[-1]
            if nm in _SHELLS or _INTERPS.fullmatch(nm):
                err = _exec_file_deploy(base / stdin_file, base, depth,
                                        force_shell=nm in _SHELLS)
                if err:
                    return err
        low = prog.lower()
        name = re.split(r"[/\\]", low)[-1]
        if low in _PKG_MANAGERS and len(argv) > 1:
            k = 2 if argv[1].lower() in ("exec", "x", "dlx") and len(argv) > 2 else 1
            if _tool_name(argv[k]):
                argv = argv[k:]
                prog = argv[0]
                low = prog.lower()
                name = re.split(r"[/\\]", low)[-1]
        if "<<<" in argv:
            k = argv.index("<<<")
            here = argv[k + 1] if k + 1 < len(argv) else ""
            if depth < 3 and here and (name in _SHELLS or _INTERPS.fullmatch(name)):
                err = (deploy_error(here, base, depth + 1) if name in _SHELLS else
                       script_deploy_error(here, Path("inline.py"), base))
                if err:
                    return err if err.startswith("redteam gate") else \
                        f"redteam gate: {err}. {DEPLOY_DENY}"
            argv = argv[:k] + argv[k + 2:]  # keep evaluating the command itself
            if not argv:
                continue
        if name in _SHELLS and any(re.fullmatch(r"-[a-z]*n[a-z]*", a) for a in argv[1:]) \
                and not any(re.fullmatch(r"-[a-z]*c[a-z]*", a) for a in argv[1:]):
            continue  # `bash -n f`: syntax check, nothing runs
        if depth < 3 and name in _SHELLS:
            cflag = next((n for n, a in enumerate(argv[1:], 1)
                          if re.fullmatch(r"-[a-z]*c[a-z]*", a, re.I)), None)
            if cflag is not None:
                code = next((a for a in argv[cflag + 1:] if not a.startswith("-")), None)
                err = deploy_error(code, base, depth + 1) if code else None
                if err:
                    return err
                continue
            fi = _shell_script_index(argv)
            err = None
            for fp in (_glob_paths(base, argv[fi]) if fi else []):
                err = err or _exec_file_deploy(fp, base, depth, args=argv[fi + 1:])
            if err:
                return err
            continue
        if depth < 3 and name in ("awk", "gawk", "mawk", "nawk"):
            for a in argv[1:]:
                err = script_deploy_error(a, Path("inline.awk"), base)
                if err:
                    return f"redteam gate: {err}. {DEPLOY_DENY}"
            continue
        if depth < 3 and name == "find":
            names = [argv[n + 1] for n, a in enumerate(argv[:-1]) if a in ("-name", "-iname")]
            roots = [a for a in argv[1:] if not a.startswith("-")][:1] or ["."]
            for k, a in enumerate(argv):
                if a in ("-exec", "-execdir", "-ok", "-okdir"):
                    end = next((n for n in range(k + 1, len(argv)) if argv[n] in (";", "+")),
                               len(argv))
                    cmd = argv[k + 1:end]
                    hits: list[str] = []
                    if "{}" in cmd:
                        for pat in names or ["*"]:
                            try:
                                hits += [str(x) for x in sorted((base / roots[0]).rglob(pat))[:20]]
                            except (OSError, ValueError):
                                continue
                    import shlex as _sh
                    for h in hits[:20] or [None]:
                        line = " ".join(_sh.quote(c.replace("{}", h)) if h else c for c in cmd)
                        err = deploy_error(line, base, depth + 1)
                        if err:
                            return err
            continue
        if depth < 3 and name == "script" and any(re.fullmatch(r"-[a-z]*c[a-z]*", a)
                                                  for a in argv[1:]):
            k = next(n for n, a in enumerate(argv) if n and re.fullmatch(r"-[a-z]*c[a-z]*", a))
            err = deploy_error(argv[k + 1], base, depth + 1) if k + 1 < len(argv) else None
            if err:
                return err
            continue
        if depth < 3 and name in ("source", "."):
            err = (_exec_file_deploy(base / argv[1], base, depth, args=argv[2:])
                   if len(argv) > 1 else None)
            if err:
                return err
            continue
        if depth < 3 and name == "eval":
            err = deploy_error(" ".join(argv[1:]), base, depth + 1)
            if err:
                return err
            continue
        if depth < 3 and name in ("echo", "printf") and _PIPE_SH_RE.search(outer):
            err = deploy_error(" ".join(argv[1:]).replace("\\n", "\n"), base, depth + 1)
            if err:
                return err
            continue
        if depth < 3 and name in _CMD_STRING_PROGS:
            for k in range(1, min(len(argv), 12)):
                if argv[k].startswith("-"):
                    continue
                err = deploy_error(" ".join(argv[k:]), base, depth + 1) or (
                    deploy_error(argv[k], base, depth + 1) if " " in argv[k] else None)
                if err:
                    return err
            continue
        if depth < 3 and name == "gh":
            err = gh_text_error(argv)
            if err:
                return err
            continue
        if depth < 3 and name in ("cat", "tail", "head") and (
                _PIPE_SH_RE.search(outer) or _PIPE_INTERP_RE.search(outer)):
            shell = bool(_PIPE_SH_RE.search(outer))
            for fa in argv[1:]:
                if not fa.startswith("-") and not fa.lstrip("+").isdigit():
                    fp = base / fa
                    if shell:
                        err = _exec_file_deploy(fp, base, depth, force_shell=True)
                    else:
                        try:
                            txt = _read_limited(fp, str(fp)) if fp.is_file() else None
                        except (OSError, ScanLimit):
                            txt = None
                        e2 = script_deploy_error(txt, Path("piped.py"), base) if txt else None
                        err = f"redteam gate: {e2}. {DEPLOY_DENY}" if e2 else None
                    if err:
                        return err
            continue
        if depth < 3 and name in ("make", "gmake"):
            targets = [a for a in argv[1:] if not a.startswith("-") and "=" not in a]
            for mf in makefiles(" ".join(argv), [base]):
                text = _read_limited(mf, str(mf))
                if text:
                    body = make_recipes(text, targets)
                    err = deploy_error(body, mf.parent, depth + 1)
                    if err:
                        return err
            continue
        if low == "cd":
            nxt = argv[1] if len(argv) > 1 else ""
            base = (base / nxt) if nxt and not any(c in nxt for c in "$`~") else base
            continue
        if name in _HTTPIE:
            hit = sender_hit(seg.lower(), seg)
            if hit:
                return f"redteam gate: Bash command sends outward via httpie ({hit}). {BASH_DENY}"
            continue
        if low in _PKG_MANAGERS and len(argv) > 1 and depth < 3:
            name = argv[2] if argv[1] in ("run", "run-script") and len(argv) > 2 else argv[1]
            try:
                pkg = _package_scripts(f"npm run {name}", [base])
            except ScanLimit as exc:
                return f"redteam gate: {exc}. {DEPLOY_DENY}"
            for label, body in pkg:
                err = deploy_error(body, base, depth + 1)
                if err:
                    return err.replace("redteam gate: ", f"redteam gate: {label}: ", 1)
            k = argv.index(name) if name in argv else -1
            if not pkg and k > 0 and _tool_name(name):
                argv = argv[k:]
                prog = argv[0]
            else:
                continue
        tool = _tool_name(prog)
        if not tool:
            err = _interp_deploy(argv, name, base, depth)
            if err:
                return err
            continue
        is_deploy, d = _deploy_target(tool, argv[1:])
        if not is_deploy:
            continue
        target = (base / d) if d else base
        if any(c in str(target) for c in "$`~*?"):
            return f"redteam gate: deploy dir {target} uses expansion (unverifiable). {DEPLOY_DENY}"
        why = dir_committed_error(target) if d else project_clean_error(target)
        if why:
            return f"redteam gate: {tool} deploy of {target}: {why}. {DEPLOY_DENY}"
    return None


def _shell_script_index(argv: list[str]) -> int | None:
    """Index of the script operand of `bash [opts] script args`, skipping option arguments
    (`-o pipefail`, `-eo pipefail`, `+O extglob`, `--rcfile f`)."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file") or \
                re.fullmatch(r"[-+][A-Za-z]*[oO]", a):
            i += 2
            continue
        if a.startswith(("-", "+")):
            i += 1
            continue
        return i
    return None


_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "ash", "mksh", "yash", "hush"}
_INTERPS = re.compile(r"python(?:3(?:\.\d+)?)?(?:\.exe)?|py|node|deno|bun|ruby|perl|php|tsx|ts-node|"
                      r"pwsh|powershell")


def make_recipes(text: str, targets: list[str], depth: int = 0) -> str:
    """Recipe lines of the invoked targets (first target when none) plus their prerequisites."""
    rules: dict[str, tuple[list[str], list[str]]] = {}
    order: list[str] = []
    cur: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("\t"):
            if cur is not None:
                cur.append(line[1:])
            continue
        m = re.match(r"^([A-Za-z0-9_./%$(){}-][^:=#]*?)\s*::?(?!=)\s*([^=#;]*)(?:;(.*))?$", line)
        if m:
            cur = []
            for t in m.group(1).split():
                if t not in rules:
                    rules[t] = ([], cur)
                    order.append(t)
                rules[t][0].extend(m.group(2).split())
            if m.group(3):
                cur.append(m.group(3))
        elif line.strip() and not line.startswith("#"):
            cur = None
    want = targets or [t for t in order if not t.startswith(".")][:1]
    out: list[str] = []
    seen: set[str] = set()
    stack = list(want)
    while stack and len(seen) < 50:
        t = stack.pop()
        if t in seen:
            continue
        seen.add(t)
        if t in rules:
            out.extend(rules[t][1])
            stack.extend(rules[t][0])
        elif not rules or any("%" in r or "$" in r for r in rules):
            return text  # unparseable / pattern rules: scan everything (fail safe)
    return "\n".join(r.lstrip("@-+") for r in out)


def _script_project(fp: Path) -> Path:
    root = Path(os.path.realpath(REPO_ROOT))
    real = Path(os.path.realpath(fp))
    for anc in real.parents:
        if anc == root or not anc.is_relative_to(root):
            break
        if any((anc / mk).is_file() for mk in _PROJECT_MARKERS):
            return anc
    return real.parent


def _bind_positional(text: str, args: list[str], base: Path) -> str:
    """Substitute $1..$9 / ${1}, ${1:?..}, ${1:-..} with the invoking command's args (paths made
    absolute against the invoking cwd), then simple NAME=value assignments built from them."""
    vals: dict[str, str] = {}
    for n, a in enumerate(args[:9], 1):
        v = a
        if not a.startswith("-") and not re.match(r"^[a-z]+://", a) and ((base / a).exists()
                                                                          or "/" in a):
            v = str(base / a)
        vals[str(n)] = v

    def sub_pos(m: re.Match) -> str:
        return vals.get(m.group(1) or m.group(2), m.group(0))

    text = re.sub(r"\$\{(\d)(?:[:?\-=+][^}]*)?\}|\$(\d)", sub_pos, text)
    names: dict[str, str] = {}
    for seg in split_simple_commands(text):
        m = re.fullmatch(r"\s*(?:export\s+|local\s+|readonly\s+)?([A-Za-z_]\w*)=(\"[^\"$`]*\"|"
                         r"'[^']*'|[^\s$`'\"]*)\s*", seg)
        if m:
            names[m.group(1)] = m.group(2).strip("\"'")
    for k, v in names.items():
        text = re.sub(r"\$\{" + k + r"\}|\$" + k + r"\b", lambda _m, v=v: v, text)
    return text


_PENDING_WRITES: dict[str, str] = {}
_WRITE_TARGET_RE = re.compile(r"(?<![<>&\d])>>?\s*['\"]?([^\s;&|<>'\"]+)")


def _brace_expand(pat: str) -> list[str]:
    m = re.search(r"\{([^{}]*,[^{}]*)\}", pat)
    if not m:
        return [pat]
    out: list[str] = []
    for alt in m.group(1).split(",")[:20]:
        out += _brace_expand(pat[:m.start()] + alt + pat[m.end():])
    return out


def _glob_paths(base: Path, pat: str) -> list[Path]:
    out: list[Path] = []
    for p in _brace_expand(pat):
        if any(c in p for c in "*?["):
            try:
                out += sorted(base.glob(p))[:20] if not os.path.isabs(p) else \
                    [Path(x) for x in sorted(__import__("glob").glob(p))[:20]]
            except (ValueError, OSError):
                continue
        else:
            out.append(base / p)
    return out


def pending_writes(outer: str, docs: list[tuple[str, str]], cwd: Path) -> dict[str, str]:
    """Files this command writes before running them: heredoc bodies redirected to a file and
    `echo|printf … > f`. Keyed by resolved path."""
    import shlex
    out: dict[str, str] = {}
    for opener, body in docs:
        for m in _WRITE_TARGET_RE.finditer(opener):
            out[os.path.realpath(cwd / m.group(1))] = body
    for seg in split_simple_commands(outer):
        m = _WRITE_TARGET_RE.search(seg)
        if not m:
            continue
        try:
            toks = shlex.split(seg[:m.start()])
        except ValueError:
            continue
        if toks[:1] in (["echo"], ["printf"]):
            key = os.path.realpath(cwd / m.group(1))
            out[key] = out.get(key, "") + "\n" + " ".join(toks[1:]).replace("\\n", "\n")
        elif toks[:1] == ["cat"] and len(toks) > 1:
            src = "\n".join(_safe_read(cwd / t) for t in toks[1:] if not t.startswith("-"))
            out[os.path.realpath(cwd / m.group(1))] = src
    for seg in split_simple_commands(outer):
        try:
            toks = shlex.split(seg)
        except ValueError:
            continue
        if toks[:1] == ["tee"]:
            srcs = re.findall(r"(?:^|[\s;&|])cat\s+([^\s|;&<>]+)", outer)
            body = "\n".join(_safe_read(cwd / x) for x in srcs[:10])
            for t in toks[1:]:
                if not t.startswith("-"):
                    out[os.path.realpath(cwd / t)] = body
        if toks[:1] in (["cp"], ["install"], ["mv"], ["ln"]):
            ops = [t for t in toks[1:] if not t.startswith("-")]
            if len(ops) == 2:
                out[os.path.realpath(cwd / ops[1])] = _safe_read(cwd / ops[0])
    return out


def _safe_read(fp: Path) -> str:
    try:
        if fp.is_file() and fp.stat().st_size <= MAX_SCAN_BYTES:
            t = fp.read_text(encoding="utf-8", errors="replace")
            return "" if "\x00" in t[:8192] else t
    except (OSError, ValueError, UnicodeError):
        pass  # unreadable source: nothing to pre-scan (the run itself is still checked)
    return ""


_PATH_LIT_RE = re.compile(r"(?<![\w$.-])((?:\.{1,2}/)?[\w.-]+(?:/[\w.-]+)+)/?")


def _unresolved_target_error(fp: Path, text: str, args: list[str], base: Path,
                             sbase: Path) -> str | None:
    """Tracked clean deploy script whose target dir is not resolvable: every folder the script
    names as a literal (repo- or script-relative) and every path arg must pass the deploy rule;
    with none, the script's project and the whole deliverables/ tree must be clean."""
    root = Path(os.path.realpath(REPO_ROOT))
    cands: list[Path] = []
    for a in args:
        if not a.startswith("-") and (base / a).exists():
            cands.append(base / a)
    for m in _PATH_LIT_RE.finditer(text):
        lit = m.group(1)
        for b in (root, fp.parent, base):
            c = b / lit
            try:
                if c.is_dir() and Path(os.path.realpath(c)).is_relative_to(root) and \
                        Path(os.path.realpath(c)) != root:
                    cands.append(c)
                    break
            except OSError:
                continue
        if len(cands) > 40:
            break
    for c in cands:
        why = dir_committed_error(c) if c.is_dir() else project_clean_error(_script_project(c))
        if why and "outside a committed project" in why:
            continue  # scratch (.tmp/ staging): its source is a separate literal/arg
        if why:
            return f"redteam gate: deploy from {fp}: target {c}: {why}. {DEPLOY_DENY}"
    if cands:
        return None
    why = project_clean_error(sbase)
    deliv = root / "deliverables"
    if not why and deliv.is_dir():
        why = _project_status_error(deliv, root)
    return f"redteam gate: deploy from {fp}: {why}. {DEPLOY_DENY}" if why else None


def _exec_file_deploy(fp: Path, base: Path, depth: int, force_shell: bool = False,
                      args: list[str] | None = None) -> str | None:
    """A file this command EXECUTES: shell files are re-parsed as commands; code files are
    checked for a spawned deploy. The project checked is the script's own project folder."""
    try:
        pend = _PENDING_WRITES.get(os.path.realpath(fp))
    except (OSError, ValueError):
        return None
    try:
        if pend is not None:
            text = pend.lower()
        elif not fp.is_file():
            return None
        else:
            text = _read_limited(fp, str(fp))
    except (OSError, ScanLimit, ValueError, UnicodeError):
        return None
    if not text or "\x00" in text[:8192]:
        return None  # empty or binary
    if pend is None and depth < 3 and fp.suffix.lower() not in ("", ".sh", ".bash", ".zsh"):
        # code that launches a shell script: treat as running that script
        for lit in (re.findall(r"['\"]([\w./-]+\.(?:sh|bash))['\"]", text)
                    + _SH_STRING_RE.findall(text))[:10]:
            for b in (fp.parent, base, Path(os.path.realpath(REPO_ROOT))):
                if (b / lit).is_file():
                    err = _exec_file_deploy(b / lit, base, depth + 1)
                    if err:
                        return err
                    break
    if force_shell or fp.suffix.lower() in ("", ".sh", ".bash", ".zsh"):
        bound = _bind_positional(text, args or [], base)
        sbase = _script_project(fp) if not force_shell else base
        err = deploy_error(bound, sbase, depth + 1)
        if err and "uses expansion" in err and pend is None and git_clean(fp):
            # tracked + clean script whose deploy dir is not resolvable from its args: the
            # project of the path args it was given (else the script's own folder) must be clean
            err = _unresolved_target_error(fp, bound, args or [], base, sbase)
        if err:
            return err
        if pend is None and git_clean(fp):
            return None  # tracked script, its commands were checked above
    err = script_deploy_error(text, fp, _script_project(fp))
    return f"redteam gate: {err}. {DEPLOY_DENY}" if err else None


def _interp_deploy(argv: list[str], name: str, base: Path, depth: int) -> str | None:
    """`python3 x.py`, `node x.js`, `python3 -c CODE`, `./x.sh`: scan only the executed file
    or inline code for a spawned deploy."""
    if _INTERPS.fullmatch(name):
        for n, a in enumerate(argv[1:], 1):
            if re.fullmatch(r"-[a-z]*[cer]", a, re.I) or a in ("--eval", "--command"):
                code = argv[n + 1] if n + 1 < len(argv) else ""
                err = script_deploy_error(code, Path("inline.py"), base)
                if err:
                    return f"redteam gate: {err}. {DEPLOY_DENY}"
                for f in (re.findall(r"['\"]([\w./-]+\.(?:sh|bash))['\"]", code)
                          + _SH_STRING_RE.findall(code)):
                    e2 = _exec_file_deploy(base / f, base, depth)
                    if e2:
                        return e2
                for f in re.findall(r"open\s*\(\s*['\"]([^'\"]+)['\"]", code):
                    e2 = _exec_file_deploy(base / f, base, depth)
                    if e2:
                        return e2
                return None
            if a == "-":
                return None  # stdin: heredoc bodies are scanned by the caller
            if a == "-m":
                mod = argv[n + 1] if n + 1 < len(argv) else ""
                mp = resolve_module(mod, base, []) if mod else None
                return _exec_file_deploy(mp, base, depth) if mp else None
            if a.startswith("-"):
                continue
            return _exec_file_deploy(base / a, base, depth)
        return None
    if "/" in argv[0] or "\\" in argv[0]:
        return _exec_file_deploy(base / argv[0], base, depth, args=argv[1:])
    return None


_GH_TEXT_FLAGS = {
    ("issue", "comment"): {"--body": "body", "-b": "body", "--body-file": "@", "-F": "@"},
    ("issue", "create"): {"--body": "body", "-b": "body", "--title": "title", "-t": "title",
                          "--body-file": "@", "-F": "@"},
    ("issue", "edit"): {"--body": "body", "-b": "body", "--title": "title", "-t": "title",
                        "--body-file": "@", "-F": "@"},
    ("issue", "close"): {"--comment": "comment", "-c": "comment"},
    ("issue", "reopen"): {"--comment": "comment", "-c": "comment"},
    ("pr", "comment"): {"--body": "body", "-b": "body", "--body-file": "@", "-F": "@"},
    ("pr", "create"): {"--body": "body", "-b": "body", "--title": "title", "-t": "title",
                       "--body-file": "@", "-F": "@"},
    ("pr", "edit"): {"--body": "body", "-b": "body", "--title": "title", "-t": "title",
                     "--body-file": "@", "-F": "@"},
    ("pr", "review"): {"--body": "body", "-b": "body", "--body-file": "@", "-F": "@"},
    ("pr", "close"): {"--comment": "comment", "-c": "comment"},
    ("pr", "reopen"): {"--comment": "comment", "-c": "comment"},
    ("pr", "merge"): {"--body": "body", "-b": "body", "--subject": "subject", "-t": "subject",
                      "--body-file": "@", "-F": "@"},
    ("release", "create"): {"--notes": "notes", "-n": "notes", "--title": "title", "-t": "title",
                            "--notes-file": "@", "-F": "@"},
    ("release", "edit"): {"--notes": "notes", "-n": "notes", "--title": "title", "-t": "title",
                          "--notes-file": "@", "-F": "@"},
    ("discussion", "create"): {"--body": "body", "-b": "body", "--title": "title", "-t": "title",
                               "--body-file": "@", "-F": "@"},
    ("discussion", "comment"): {"--body": "body", "-b": "body", "--body-file": "@", "-F": "@"},
    ("repo", "create"): {"--description": "description", "-d": "description"},
    ("repo", "edit"): {"--description": "description", "-d": "description"},
    ("gist", "create"): {"--desc": "description", "-d": "description"},
    ("workflow", "run"): {"-f": "kv", "--raw-field": "kv", "-F": "kv", "--field": "kv"},
    ("label", "create"): {"--description": "description", "-d": "description"},
    ("label", "edit"): {"--description": "description", "-d": "description"},
    ("project", "item-create"): {"--title": "title", "--body": "body"},
    ("project", "create"): {"--title": "title"},
}
_GH_API_SHARE_RE = re.compile(r"/(?:collaborators|invitations|memberships|members|outside_"
                              r"collaborators|teams/[^/]+/repos)(?:/|$)")
_GH_GLOBAL_VAL = {"-R", "--repo", "--hostname"}
_GH_API_OUTWARD_RE = re.compile(r"(?:^|/)(?:issues|pulls|comments|reviews|releases|discussions|"
                                r"gists)(?:/|$)|^/?repos/[^/]+/[^/]+/?$|^/?user/repos/?$|"
                                r"^/?orgs/[^/]+/repos/?$")


def _gh_texts_error(where: str, texts: list[tuple[str, str]]) -> str | None:
    ledger = Ledger(state_dir())
    for key, raw in texts:
        if not raw or not raw.strip():
            continue
        norm = normalise(raw)
        sha = _sha256(norm)
        if not ledger.rows_for(sha):
            return f"redteam gate: {_not_passed(where + '.' + key, norm, sha)}. {DENY_SUFFIX}"
    return None


def _gh_api_error(rest: list[str]) -> str | None:
    method = None
    fields: list[tuple[str, str]] = []
    inp = None
    path = None
    i = 0
    while i < len(rest):
        a = rest[i]
        k, eq, v = a.partition("=") if a.startswith("--") else (a[:2], "", a[2:]) \
            if a.startswith("-") and len(a) > 2 else (a, "", "")
        if a.startswith("-"):
            if not eq and not v:
                v = rest[i + 1] if i + 1 < len(rest) else ""
                i += 1
            if k in ("-X", "--method"):
                method = v.upper()
            elif k in ("-f", "-F", "--field", "--raw-field"):
                fk, _e, fv = v.partition("=")
                fields.append((fk, fv))
            elif k == "--input":
                inp = v
        elif path is None:
            path = a
        i += 1
    if path is None:
        return None
    is_gql = path.rstrip("/").endswith("graphql")
    if is_gql:
        blob = []
        for _k, v2 in fields:
            if v2.startswith("@"):
                try:
                    v2 = Path(v2[1:]).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return f"redteam gate: gh api graphql field file {v2[1:]} unreadable"
            blob.append(v2)
        if inp is not None:
            if inp == "-":
                return "redteam gate: gh api graphql --input - (stdin) is unverifiable"
            try:
                blob.append(Path(inp).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                return f"redteam gate: gh api --input {inp} unreadable"
        if re.search(r"\bmutation\b", " ".join(blob), re.I):
            return ("redteam gate: gh api graphql mutation (outward write; use gh issue/pr "
                    "commands with red-teamed text, or ask the operator to waive)")
        return None
    if inp is not None:
        if inp == "-":
            return "redteam gate: gh api --input - (stdin) is unverifiable"
        try:
            data = json.loads(Path(inp).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            return f"redteam gate: gh api --input {inp} unreadable"
        if isinstance(data, dict):
            fields += [(str(k2), v2 if isinstance(v2, str) else json.dumps(v2))
                       for k2, v2 in data.items()]
    eff = method or ("POST" if fields or inp is not None else "GET")
    if path.strip("/") == "graphql":
        blob = " ".join(v2 for _k, v2 in fields).lower()
        if "mutation" in blob:
            return ("redteam gate: gh api graphql mutation (outward write; use gh issue/pr "
                    "commands with red-teamed text, or ask the operator to waive)")
        return None
    if eff in ("POST", "PATCH", "PUT") and _GH_API_SHARE_RE.search(path):
        return (f"redteam gate: gh api {eff} {path} invites/shares access with a GitHub user "
                f"(no passed record can name a username; ask the operator to waive)")
    if eff not in ("POST", "PATCH", "PUT") or not _GH_API_OUTWARD_RE.search(path):
        return None
    texts = [(fk, fv) for fk, fv in fields if fv.startswith("@") is False
             and not _MCP_ID_KEY_RE.search(fk)]
    for fk, fv in fields:
        if fv.startswith("@"):
            try:
                texts.append((fk, Path(fv[1:]).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                return f"redteam gate: gh api field file {fv[1:]} unreadable"
    return _gh_texts_error(f"gh api {path}", texts)


def gh_text_error(argv: list[str]) -> str | None:
    """`gh` outward text: issue/pr/release/discussion/repo subcommands with body/title/comment/
    subject/notes/description flags (incl. attached short forms) and `gh api` writes to
    issues/pulls/comments/reviews/releases/discussions; graphql mutations deny."""
    rest: list[str] = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in _GH_GLOBAL_VAL:
            i += 2
            continue
        if a.split("=")[0] in _GH_GLOBAL_VAL or (a.startswith("-R") and len(a) > 2):
            i += 1
            continue
        rest = argv[i:]
        break
    if not rest:
        return None
    if rest[0] == "api":
        return _gh_api_error(rest[1:])
    sub = tuple(rest[:2])
    if sub in (("repo", "edit"), ("repo", "create")):
        vis = [rest[n + 1] for n, a in enumerate(rest[:-1]) if a == "--visibility"] + \
            [a.split("=", 1)[1] for a in rest if a.startswith("--visibility=")]
        if "--public" in rest or any(v.lower() == "public" for v in vis):
            return (f"redteam gate: gh {' '.join(sub)} makes a repo public (publishes its "
                    f"content); ask the operator to waive")
    if sub == ("gist", "create"):
        gtexts: list[tuple[str, str]] = []
        k = 2
        while k < len(rest):
            a = rest[k]
            if a in ("-d", "--desc", "-f", "--filename"):
                if a in ("-d", "--desc") and k + 1 < len(rest):
                    gtexts.append(("description", rest[k + 1]))
                k += 2
                continue
            if a.startswith("--desc="):
                gtexts.append(("description", a.split("=", 1)[1]))
            elif a == "-":
                return "redteam gate: gh gist create from stdin is unverifiable"
            elif not a.startswith("-"):
                try:
                    gtexts.append((f"file {a}", Path(a).read_text(encoding="utf-8",
                                                                errors="replace")))
                except OSError:
                    return f"redteam gate: gh gist create file {a} unreadable"
            k += 1
        return _gh_texts_error("gh gist create", gtexts)
    flags = _GH_TEXT_FLAGS.get(sub)  # type: ignore[arg-type]
    if not flags:
        return None
    texts: list[tuple[str, str]] = []
    i = 2
    while i < len(rest):
        a = rest[i]
        k, eq, v = a.partition("=")
        if not eq and a.startswith("-") and not a.startswith("--") and len(a) > 2 \
                and a[:2] in flags:
            k, eq, v = a[:2], "=", a[2:]
        if k in flags:
            if not eq:
                v = rest[i + 1] if i + 1 < len(rest) else ""
                i += 1
            if flags[k] == "@":
                if v == "-":
                    return f"redteam gate: gh {' '.join(sub)} reads text from stdin (unverifiable)"
                try:
                    v = Path(v).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return f"redteam gate: gh {' '.join(sub)} text file {v} unreadable"
                texts.append(("body", v))
            elif flags[k] == "kv":
                fk, _e, fv = v.partition("=")
                if not _MCP_ID_KEY_RE.search(fk):
                    texts.append((fk, fv))
            else:
                texts.append((flags[k], v))
        i += 1
    return _gh_texts_error("gh " + " ".join(sub), texts)


def project_clean_error(proj: Path) -> str | None:
    """No explicit dir (a worker deploy, a promote, a versions deploy): the cwd project
    must be a workspace subfolder with tracked files and no modified/untracked files."""
    try:
        real = Path(os.path.realpath(proj))
        root = Path(os.path.realpath(REPO_ROOT))
    except OSError:
        return "path unresolvable"
    if not real.is_dir() or not real.is_relative_to(root) or real == root:
        return "not a committed subdirectory of this workspace"
    return _project_status_error(real, root)


def dir_committed_error(target: Path) -> str | None:
    import subprocess
    try:
        real = Path(os.path.realpath(target))
        root = Path(os.path.realpath(REPO_ROOT))
    except OSError:
        return "path unresolvable"
    if not real.is_dir():
        return "not a directory"
    if not real.is_relative_to(root) or real == root:
        return "not a committed subdirectory of this workspace"
    rel = str(real.relative_to(root))
    if _git_ok(root, "check-ignore", "-q", "--", rel):
        return _build_output_error(real, root)
    try:
        ls = subprocess.run(["git", "-C", str(root), "ls-files", "--", rel], capture_output=True, encoding="utf-8", errors="replace",
                            text=True, timeout=10)
        st = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--ignored",
                             "--untracked-files=all", "--", rel], capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"git check failed ({type(exc).__name__})"
    if ls.returncode or st.returncode or not ls.stdout.strip():
        return "no tracked files (uncommitted content)"
    dirty = [ln[3:] for ln in st.stdout.splitlines()
             if not any(sk in ln[3:] for sk in _DEPLOY_SKIP_DIRS)]
    if dirty:
        return "uncommitted/untracked/ignored files: " + ", ".join(dirty[:3])
    return None


_PROJECT_MARKERS = ("package.json", "wrangler.toml", "wrangler.json", "wrangler.jsonc",
                    "vercel.json", "netlify.toml")


def _build_output_error(real: Path, root: Path) -> str | None:
    """Gitignored build output (dist/, build/, out/, .vercel/output): allowed when its project
    subfolder (nearest ancestor with a project marker, else the parent) is a workspace
    subfolder with tracked files and no modified/untracked non-ignored files."""
    import subprocess
    proj = real.parent
    for anc in [real.parent, *real.parent.parents]:
        if anc == root or not anc.is_relative_to(root):
            break
        if any((anc / mk).is_file() for mk in _PROJECT_MARKERS):
            proj = anc
            break
    if proj == root or not proj.is_relative_to(root):
        return "gitignored output outside a committed project subfolder"
    return _project_status_error(proj, root)


def _project_status_error(proj: Path, root: Path) -> str | None:
    import subprocess
    rel = str(proj.relative_to(root))
    try:
        ls = subprocess.run(["git", "-C", str(root), "ls-files", "--", rel], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=10)
        st = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                             "--untracked-files=all", "--", rel], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"git check failed ({type(exc).__name__})"
    if ls.returncode or st.returncode or not ls.stdout.strip():
        return f"project {rel} has no tracked files"
    dirty = [ln[3:] for ln in st.stdout.splitlines()]
    if dirty:
        return f"project {rel} has uncommitted files: " + ", ".join(dirty[:3])
    return None


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
    """True if the file's realpath is inside this workspace and tracked + unmodified in the
    workspace's own git (a throwaway `git init` elsewhere, or a nested repo, never counts)."""
    try:
        real = Path(os.path.realpath(path))
        root = Path(os.path.realpath(REPO_ROOT))
    except OSError:
        return False
    if not real.is_relative_to(root) or not real.is_file():
        return False
    rel = str(real.relative_to(root))
    return (_git_ok(root, "ls-files", "--error-unmatch", "--", rel)
            and _git_ok(root, "diff", "--quiet", "HEAD", "--", rel))


def resolve_module(mod: str, cwd: Path, extra: Iterable[Path] = ()) -> Path | None:
    """File a `python -m mod` would run (cwd, extra bases such as `cd` targets and PYTHONPATH
    entries, then the repo root), or None."""
    rel = Path(*mod.split("."))
    for base in (cwd, *extra, REPO_ROOT):
        for cand in (base / rel.with_suffix(".py"), base / rel / "__main__.py"):
            if cand.is_file():
                return cand.resolve()
    return None


_FLAG_WITH_VALUE = {"-k", "--kill-after", "-s", "--signal", "-n", "--adjustment", "-c",
                    "--class", "-p", "-u", "-g", "-i", "-o", "-e", "-C", "--chdir", "-S"}
_PREFIX_WRAPPERS = {"timeout", "nice", "stdbuf", "env", "ionice", "nohup", "time", "command",
                    "exec"}


def skip_prefix(toks: list[str]) -> int:
    """Index of the program word after env assignments and wrapper words with their flags
    (`timeout -k 5 --signal=KILL 30`, `nice -n 5`, `stdbuf -oL`, `env -i A=1`)."""
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t, re.S):
            i += 1
            continue
        if t in _PREFIX_WRAPPERS:
            i += 1
            while i < len(toks) and toks[i].startswith("-") and toks[i] != "-":
                i += 2 if toks[i] in _FLAG_WITH_VALUE else 1
            if t == "timeout" and i < len(toks) and re.fullmatch(r"[\d.]+[smhd]?", toks[i]):
                i += 1
            continue
        break
    return i


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
    i = skip_prefix(toks)
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


MAX_ARG_FILES = 64


class ScanLimit(Exception):
    """A scan limit was hit: the gate cannot vouch for the command (fail closed)."""


def _arg_tokens(text: str, depth: int = 0) -> list[str]:
    """Words of a command after shell-style quote removal (redirect sources included). A quoted
    word with spaces is kept whole (`"send mail.py"`) AND re-split (for `sh -c "..."`)."""
    import shlex
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=";&|<>()")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = text.split()
    out: list[str] = []
    for t in toks:
        m = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=(.+)", t, re.S)
        if m:
            t = m.group(1)  # FOO=/tmp/s.py: the value may itself be a script path
        if not t or t.startswith("-") or set(t) <= set(";&|<>()"):
            continue
        out.append(t)
        if any(c.isspace() for c in t) and depth < 2:
            out.extend(_arg_tokens(t, depth + 1))
    return out


_ASSIGN_RE = re.compile(r"(?:^|[\s;&|(])(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)="
                        r"(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)")
_CD_RE = re.compile(r"(?:^|[\s;&|(])(?:cd|pushd)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|)]+)")
_VAR_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_SUBST_RE = re.compile(r"\$\(\s*(pwd|which\s+([\w.+-]+)|command\s+-v\s+([\w.+-]+))\s*\)"
                       r"|`\s*(pwd|which\s+([\w.+-]+))\s*`")
_BRACE_RE = re.compile(r"\{([^{}\s,]*(?:,[^{}\s,]*)+)\}")
# Package installs name packages, not code to run: their arguments are not scanned.
_PIP_INSTALL_RE = re.compile(r"\b(?:pip3?|uv\s+pip|pipx|poetry|pdm|conda|npm|pnpm|yarn)\s+"
                             r"(?:install|add|i)\b[^;&|\n]*", re.I)


def _expand(tok: str, vars_: dict[str, str], cwd: Path | None = None) -> str:
    import shutil

    def subst(m: re.Match) -> str:
        if (m.group(1) or m.group(4) or "").strip() == "pwd":
            return str(cwd or Path.cwd())
        name = m.group(2) or m.group(3) or m.group(5)
        return shutil.which(name) or name if name else m.group(0)

    tok = _SUBST_RE.sub(subst, tok)
    return _VAR_RE.sub(lambda m: vars_.get(m.group(1) or m.group(2), m.group(0)), tok)


def _braces(tok: str, limit: int = MAX_ARG_FILES) -> list[str]:
    out, todo = [], [tok]
    while todo and len(out) + len(todo) <= limit:
        t = todo.pop()
        m = _BRACE_RE.search(t)
        if not m:
            out.append(t)
            continue
        todo.extend(t[:m.start()] + alt + t[m.end():] for alt in m.group(1).split(","))
    if todo:
        raise ScanLimit(f"brace expansion of {tok[:40]} exceeds {limit} words")
    return out


def _candidate_files(tok: str, bases: list[Path]) -> list[Path]:
    import glob
    out: list[Path] = []
    for word in _braces(tok):
        p = _xuser(Path(word))
        for r in ([p] if p.is_absolute() else [b / p for b in bases]):
            s = str(r)
            if any(c in s for c in "*?["):
                hits = glob.glob(s)
                if len(hits) > MAX_ARG_FILES:
                    raise ScanLimit(f"glob {word[:40]} matches more than {MAX_ARG_FILES} files")
                out.extend(Path(g) for g in hits)
            else:
                out.append(r)
    return out


def command_context(outer: str, cwd: Path) -> tuple[dict[str, str], list[Path], list[Path]]:
    """(variables, base dirs for relative paths, PYTHONPATH dirs) seen in the command."""
    vars_ = dict(os.environ)
    for m in _ASSIGN_RE.finditer(outer):
        vars_[m.group(1)] = _expand(m.group(2).strip("\"'"), vars_, cwd)
    bases = [cwd]
    for m in _CD_RE.finditer(outer):
        d = _xuser(Path(_expand(m.group(1).strip("\"'"), vars_, cwd)))
        bases.append(d if d.is_absolute() else bases[-1] / d)
    pp = [Path(x) for x in vars_.get("PYTHONPATH", "").split(os.pathsep) if x]
    pp = [x if x.is_absolute() else cwd / x for x in pp]
    return vars_, bases, pp


_CLAUDE_RE = re.compile(r"(?:^|[\s;&|(`/\\])claude(?:\.exe|\.cmd|\.js)?(?=[\s;&|)]|$)", re.I)
_WAIVE_TEXT = "redteam" " waive"
_PKG_RUN_RE = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run(?:-script)?\s+)?([\w:.-]+)", re.I)


def _read_limited(p: Path, label: str) -> str | None:
    """File text (lowercased) or None if not a file; ScanLimit if too large to vouch for."""
    try:
        if not p.is_file():
            return None
        if p.stat().st_size > MAX_SCAN_BYTES:
            with p.open("rb") as fh:
                magic = fh.read(4)
            if magic[:4] == b"\x7fELF" or magic[:2] == b"MZ" or magic[:4] in (
                    b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                return None  # a compiled program (the interpreter itself), not a script
            raise ScanLimit(f"{label} is larger than {MAX_SCAN_BYTES // 1_000_000} MB")
        return p.read_text(encoding="utf-8", errors="replace").lower()
    except OSError as exc:
        print(f"redteam: could not scan {label} ({type(exc).__name__})", file=sys.stderr)
        return None


def _scan_file(p: Path, label: str) -> str | None:
    text = _read_limited(p, label)
    hit = sender_hit(text) if text is not None else None
    if not hit and text is not None and p.suffix.lower() in (".php", ".phtml") and \
            _PHP_MAIL_RE.search(text):
        hit = "PHP mail("
    if not hit and text is not None:
        hk = hook_text_hit(text)
        if hk:
            hit = f"harness-only hook path: {hk}"
    return f"{hit} in {label}" if hit else None


def _arg_files(expanded: str, bases: list[Path]) -> list[tuple[Path, str]]:
    seen: dict[Path, str] = {}
    for tok in _arg_tokens(expanded):
        for p in _candidate_files(tok, bases):
            try:
                if p not in seen and p.is_file():
                    seen[p] = tok
            except OSError:
                continue
            if len(seen) > MAX_ARG_FILES:
                raise ScanLimit(f"command names more than {MAX_ARG_FILES} files")
    return list(seen.items())


def _package_scripts(expanded: str, bases: list[Path]) -> list[tuple[str, str]]:
    """(label, script text) for `npm|pnpm|yarn|bun run X` (best effort, package.json in bases)."""
    out: list[tuple[str, str]] = []
    for m in _PKG_RUN_RE.finditer(expanded):
        name = m.group(1)
        for b in bases:
            text = _read_limited(b / "package.json", "package.json")
            if text is None:
                continue
            try:
                scripts = json.loads(text).get("scripts") or {}
            except (json.JSONDecodeError, AttributeError):
                continue
            body = scripts.get(name.lower()) if isinstance(scripts, dict) else None
            if isinstance(body, str):
                out.append((f"package.json script {name}", body))
            break
    return out


def _nested_waiver(command: str, outer: str, cwd: Path) -> str | None:
    if not _CLAUDE_RE.search(_QUOTED_RE.sub(" ", outer)):
        return None
    texts = [command.lower()]
    vars_, bases, _pp = command_context(outer, cwd)
    try:
        for p, tok in _arg_files(_expand(outer, vars_, cwd), bases):
            t = _read_limited(p, tok)
            if t:
                texts.append(t)
    except ScanLimit:
        return ("redteam gate: a claude invocation names files the gate cannot fully scan for "
                "`redteam waive`.")
    if any(_WAIVE_TEXT in t for t in texts):
        return ("redteam gate: a nested claude session cannot carry `redteam waive`; waivers "
                "are typed by the operator in their own session.")
    return None


# Environment variables that make an interpreter (or the loader) run extra code.
CODE_ENV = ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTHONUSERBASE", "BASH_ENV", "ENV",
            "NODE_OPTIONS", "NODE_PATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "RUBYOPT", "RUBYLIB",
            "PERL5OPT", "PERL5LIB", "PHP_INI_SCAN_DIR")
_CODE_ENV_RE = re.compile(r"(?:^|[\s;&|(])(?:export\s+|env\s+(?:-\S+\s+)*)?(" + "|".join(CODE_ENV)
                          + r")=(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)")
_DIR_HOOK_FILES = ("sitecustomize.py", "usercustomize.py")


def _env_paths(name: str, value: str) -> list[str]:
    if name in ("NODE_OPTIONS", "RUBYOPT", "PERL5OPT"):
        import shlex
        try:
            toks = shlex.split(value)
        except ValueError:
            toks = value.split()
        out: list[str] = []
        for i, t in enumerate(toks):
            m = re.fullmatch(r"(?:--require|--import|--loader|--experimental-loader|-r)=?(.*)", t)
            if m:
                v = m.group(1) or (toks[i + 1] if i + 1 < len(toks) else "")
                if v:
                    out.append(v)
            elif name != "NODE_OPTIONS" and re.fullmatch(r"-[rIM]\S+", t):
                out.append(t[2:])  # ruby -rlib / -Idir, perl -Mmod
        return out
    seps = r"[\s:]" if name == "LD_PRELOAD" else re.escape(os.pathsep)
    return [x for x in re.split(seps, value) if x]


_PY_DIR_ENV = {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE"}
_SYS_LIB_RE = re.compile(r"/(?:usr/(?:local/)?lib|lib)[^/]*(?:/.*)?|/opt/[^/]+/lib[^/]*(?:/.*)?")


def _system_lib_dir(p: Path) -> bool:
    """Root-owned, not writable by us, under /usr/lib*, /usr/local/lib*, /lib*, /opt/*/lib*."""
    try:
        real = Path(os.path.realpath(p))
        if not _SYS_LIB_RE.fullmatch(real.as_posix()) or not real.is_dir():
            return False
        st = real.stat()
        return getattr(st, "st_uid", 1) == 0 and not os.access(real, os.W_OK)
    except OSError:
        return False


def _dir_tracked_clean(p: Path) -> bool:
    """A workspace directory with every file tracked and unmodified (bounded)."""
    try:
        root = Path(os.path.realpath(REPO_ROOT))
        real = Path(os.path.realpath(p))
    except OSError:
        return False
    if not real.is_relative_to(root):
        return False
    rel = str(real.relative_to(root)) or "."
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--ignored", "--",
                            rel], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"redteam: git check failed ({type(exc).__name__})", file=sys.stderr)
        return False
    tracked = _git_ok(root, "ls-files", "--error-unmatch", "--", rel)
    return r.returncode == 0 and not r.stdout.strip() and tracked


_XARGS_RE = re.compile(r"(?:^|[\s;&|(])xargs\b((?:\s+-\S+(?:\s+(?!-)[^\s|;&]+)?)*?)\s+"
                       r"(?:\S*/)?(" + _EXEC_WORDS + r")(?:\.exe)?(?=[\s|;&)]|$)([^|;&\n]*)", re.I)


def xargs_error(outer: str, cwd: Path) -> str | None:
    """`xargs <interpreter>` runs code from its input: allowed only when the interpreter is
    given a named script file (which the normal scan reads)."""
    import shlex
    for m in _XARGS_RE.finditer(_QUOTED_RE.sub(" ''", outer)):
        try:
            rest = shlex.split(m.group(3))
        except ValueError:
            rest = m.group(3).split()
        script = next((t for t in rest if not t.startswith("-")), None)
        sp = _xuser(Path(script)) if script else None
        if sp is None or "-c" in rest or not (sp if sp.is_absolute() else cwd / sp).is_file():
            return f"xargs feeds input to {m.group(2)} (unscannable)"
    return None


def code_env_error(outer: str, cwd: Path) -> str | None:
    """Deny code-loading env vars set in the command unless each value is a tracked, unmodified
    workspace path, or a file/dir the scan clears."""
    vars_ = dict(os.environ)
    for m in _CODE_ENV_RE.finditer(outer):
        name, raw = m.group(1), m.group(2).strip("\"'")
        value = _expand(raw, {**vars_, **{k: v for k, v in vars_.items()}}, cwd)
        if not value:
            continue
        if "$" in value or "`" in value:
            return f"{name}={raw[:40]} cannot be resolved"
        for item in _env_paths(name, value):
            p = _xuser(Path(item))
            p = p if p.is_absolute() else cwd / p
            if name == "LD_PRELOAD" or (name == "LD_LIBRARY_PATH" and not _system_lib_dir(p)):
                return f"{name} loads native code ({item[:40]})"
            if name == "LD_LIBRARY_PATH":
                continue
            if not p.exists():
                if name in ("RUBYOPT", "PERL5OPT", "NODE_OPTIONS"):
                    continue  # a library name (-rjson), not a path
                return f"{name} path {item[:40]} does not exist"
            if p.is_file():
                if git_clean(p):
                    continue
                if _is_binary(p):
                    return f"{name} loads binary {item[:40]}"
                hit = _scan_file(p, f"{name} file {item[:40]}")
                if hit:
                    return f"sends email inline ({hit})"
                continue
            if name not in _PY_DIR_ENV:
                if _dir_tracked_clean(p):
                    continue
                return f"{name} points at directory {item[:40]} (loader runs code from it)"
            files = [p / f for f in _DIR_HOOK_FILES] + sorted(p.glob("*.pth"))[:MAX_ARG_FILES]
            for f in files:
                if f.is_file() and not git_clean(f):
                    hit = _scan_file(f, f"{name} dir file {f.name}")
                    if hit:
                        return f"sends email inline ({hit})"
                    if f.suffix == ".pth" and re.search(r"(?m)^\s*import\b",
                                                        f.read_text(errors="replace")):
                        return f"{name} dir {item[:40]} has an executable .pth ({f.name})"
                    if f.name in _DIR_HOOK_FILES:
                        return f"{name} dir {item[:40]} injects {f.name}"
        vars_[name] = value
    return None


def _bash_hit(command: str, outer: str, docs: list[tuple[str, str]], cwd: Path,
              vars_: dict[str, str], bases: list[Path], pp: list[Path],
              expanded: str) -> str | None:
    mh = mailer_hit(expanded)
    if mh:
        return mh
    # The command runs something, so every heredoc body counts (a body written to z.py and
    # run later in the same command is code, not a fixture).
    scan = _PIP_INSTALL_RE.sub(" ", "\n".join([expanded] + [body for _o, body in docs]))
    hit = sender_hit(scan.lower(), scan)
    if hit:
        return hit
    for label, body in _package_scripts(expanded, bases):
        hit = sender_hit(body.lower(), body) or (
            f"harness-only hook path: {hook_text_hit(body)}" if hook_text_hit(body) else None)
        if hit:
            return f"{hit} in {label}"
        for p, tok in _arg_files(_expand(body, vars_, cwd), bases):
            hit = _scan_file(p, f"{tok} (from {label})")
            if hit:
                return hit
    for p in direct_scripts(expanded, bases, path_only=None):
        hit = _scan_file(p, str(p))
        if hit:
            return hit
        hit = _shell_children_hit(p, cwd)
        if hit:
            return hit
    for mf in makefiles(expanded, bases):
        hit = _scan_file(mf, str(mf))
        if hit:
            return hit
    for wpath, wtext in list(_PENDING_WRITES.items())[:20]:
        hit = sender_hit(wtext.lower(), wtext) or (
            f"harness-only hook path: {hook_text_hit(wtext)}" if hook_text_hit(wtext) else None)
        if hit:
            return f"{hit} in {wpath} (written then run by this command)"
    hit = find_exec_hit(expanded, bases)
    if hit:
        return hit
    if re.search(r"\bphp\s+(?:\S+\s+)*?-r\b", expanded) and _PHP_MAIL_RE.search(scan.lower()):
        return "PHP mail("
    for p, tok in _arg_files(_PIP_INSTALL_RE.sub(" ", _non_reader_text(expanded)), bases):
        hit = _scan_file(p, tok) or _shell_children_hit(p, cwd)
        if hit:
            return hit
    for m in _PY_MOD_RE.finditer(expanded):
        mp = resolve_module(m.group(1), cwd, [*bases[1:], *pp])
        hit = _scan_file(mp, f"module {m.group(1)}") if mp else None
        if hit:
            return hit
    return None


_OUT_REDIR_RE = re.compile(r"(?:\d?>>?|&>>?)\s*(?:&\d|[^\s;&|<>]+)")
_SEG_OPS = ("&&", "||", ";", "\n")


_SINKS = {"tail", "head", "tee", "grep", "egrep", "fgrep", "wc", "less", "cat", "sort", "uniq",
          "more"}


def _split_top(command: str, sinks: list[int] | None = None) -> list[str] | None:
    """Split on unquoted &&, ||, ; and newlines. None if a pipe, background `&`, subshell or
    command substitution appears outside quotes (those are not simple chains)."""
    mask, quote = _unquoted_mask(command, "")
    if quote:
        return None
    segs: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(command):
        ch = command[i]
        if mask[i]:
            two = command[i:i + 2]
            if two in ("&&", "||"):
                segs.append("".join(cur))
                cur = []
                i += 2
                continue
            if ch in ";\n":
                segs.append("".join(cur))
                cur = []
                i += 1
                continue
            redirect_amp = ch == "&" and (command[i + 1:i + 2] == ">"
                                          or command[i - 1:i] == ">")  # 2>&1, &>f
            if ch == "|" and sinks is not None and command[i + 1:i + 2] != "&":
                segs.append("".join(cur))
                cur = []
                sinks.append(len([x for x in segs if x.strip()]))  # index of the sink segment
                i += 1
                continue
            if (ch in "|&`(" and not redirect_amp) or command.startswith("$(", i):
                return None
        cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return [x.strip() for x in segs if x.strip()]


def chain_allowed(command: str, cwd: Path) -> bool:
    """True if every segment of a simple chain is allowed on its own: a tracked, unmodified
    script run (output redirects and `timeout`/env prefixes ok) or a segment the scan allows.
    Stdin redirects keep the normal rules (the scan of the `<` source decides)."""
    command = command.replace("\\\n", " ")
    if split_heredocs(command)[1]:
        return False
    sink_idx: list[int] = []
    segs = _split_top(command, sink_idx)
    if not segs:
        return False
    for k in sink_idx:
        if k >= len(segs):
            return False
        sink = segs[k]
        words = command_words(sink)
        if (len(words) != 1 or re.split(r"[/\\]", words[0])[-1] not in _SINKS
                or _EXEC_RE.search(sink) or "<" in sink):
            return False  # a pipe may only feed a read-only sink
    start_cwd, rest, tracked = cwd, [], 0
    for seg in segs:
        m = re.fullmatch(r"(?:cd|pushd)\s+(\"[^\"]+\"|'[^']+'|\S+)", seg)
        if m:
            cwd = (cwd / _xuser(Path(m.group(1).strip("\"'")))).resolve()
            rest.append(seg)  # keep for context (relative paths in the remainder)
            continue
        bare = _OUT_REDIR_RE.sub(" ", seg).strip()
        if "<" not in bare and tracked_script_run(bare, cwd):
            tracked += 1
            continue
        rest.append(seg)
    if not tracked:
        return False
    # Everything that is not a tracked run is scanned together, so context such as
    # `F=x.py; python3 $F` or `cd d && python3 s.py` is kept.
    return _bash_decision("\n".join(rest), str(start_cwd), allow_tracked=False) is None


def bash_decision(ti: dict, cwd_raw: Any) -> str | None:
    """Deny inline email senders. Only commands that execute something are scanned; pure file
    writes, reads, greps and commits pass untouched (see directive: limits)."""
    command = ti.get("command")
    if command is None:
        return None
    if not isinstance(command, str):
        raise TypeError("Bash command is not a string")
    return _bash_decision(command, cwd_raw)


_HOOK_WRAPPER = "redteam-outward-gate" ".sh"
_HOOK_SUB_RE = re.compile(r"redteam_gate(?:\.py)?['\"]?\s+(?:hook|post-hook|subagent-hook|"
                          r"prompt-hook)\b", re.I)
_HOOK_ENV_RE = re.compile(r"(?:^|[\s;&|(\"'])(?:export\s+|env\s+(?:-\S+\s+)*)?REDTEAM" r"_HOOK=",
                          re.I)


_HOOK_SH_CALL_RE = re.compile(r"(?:^|[\s;&|(\"'`])(?:\S*/)?(?:(?:ba|z|da)?sh\s+(?:-\S+\s+)*['\"]?)?"
                              r"\S*" + re.escape(_HOOK_WRAPPER) + r"['\"]?\s+(?:pre|post|subagent|"
                              r"prompt)\b")


def hook_text_hit(text: str) -> str | None:
    """Hook entry points in code/command text: a hook subcommand of redteam_gate.py, a
    REDTEAM_HOOK assignment, or a call of the hook wrapper with a mode."""
    low = text.lower()
    # literal prefilters keep this linear: the regexes only run when their anchor is present
    if "redteam_gate" in low and _HOOK_SUB_RE.search(text):
        return "gate hook subcommand"
    if "redteam" "_hook=" in low and _HOOK_ENV_RE.search(text):
        return "REDTEAM_HOOK assignment"
    if _HOOK_WRAPPER in text:
        for m in re.finditer(re.escape(_HOOK_WRAPPER), text):
            window = text[max(0, m.start() - 300):m.end() + 40]
            if _HOOK_SH_CALL_RE.search(window):
                return "hook wrapper call"
    return None


_HOOK_READERS = {"cat", "git", "grep", "egrep", "fgrep", "rg", "diff", "ls", "head", "tail",
                 "less", "more", "wc", "echo", "printf", "stat", "file", "sha256sum", "md5sum",
                 "cp", "mv", "touch", "chmod", "bat", "nl", "sort", "uniq", "readlink",
                 "realpath", "dirname", "basename", "test", "[", "shellcheck", "code", "vim",
                 "nano", "ruff", "black", "pytest", "gh"}


def _shell_children_hit(p: Path, cwd: Path) -> str | None:
    """One level down: files a shell script itself runs or names (`sh wrap.sh` -> send.py)."""
    if p.suffix.lower() not in ("", ".sh", ".bash", ".zsh"):
        return None
    body = _safe_read(p)
    if not body:
        return None
    try:
        for q, tok in _arg_files(_non_reader_text(body), [p.parent, cwd])[:20]:
            hit = _scan_file(q, f"{tok} (from {p})")
            if hit:
                return hit
    except ScanLimit:
        return f"script {p} names too many files to vouch for"
    return None


def _non_reader_text(text: str) -> str:
    """Drop simple commands whose program only reads/names files (cat, grep, ls, diff …)
    unless the command pipes into a shell/interpreter: their file args are not executed."""
    import shlex
    if _PIPE_SH_RE.search(text) or _PIPE_INTERP_RE.search(text):
        return text
    keep: list[str] = []
    for seg in split_simple_commands(text):
        try:
            argv = program_argv(shlex.split(seg))
        except ValueError:
            keep.append(seg)
            continue
        if argv and re.split(r"[/\\]", argv[0])[-1].lower() in _HOOK_READERS - {"pytest"}:
            continue
        keep.append(seg)
    return "\n".join(keep)


def hook_path_error(outer: str) -> str | None:
    """Hook entry points are harness-only. Deny only when a simple command EXECUTES them (as
    the program, an interpreter/shell/source argument, inside -c/eval text, or a reader piped
    into a shell) or sets REDTEAM_HOOK for something it runs. Merely naming them (cat, git,
    grep, diff, ls, commit messages) stays allowed even next to an unrelated exec."""
    import shlex
    invoked = any(re.split(r"[/\\]", w)[-1] == _HOOK_WRAPPER for w in command_words(outer))
    if not invoked:
        piped_sh = bool(_PIPE_SH_RE.search(outer))
        for seg in split_simple_commands(outer):
            try:
                toks = shlex.split(seg)
            except ValueError:
                toks = seg.split()
            hit = hook_text_hit(seg) or hook_text_hit(" ".join(toks))
            if not hit:
                continue
            argv = program_argv(toks)
            name = re.split(r"[/\\]", argv[0])[-1].lower() if argv else ""
            if name in _HOOK_READERS and not (piped_sh and name in ("cat", "echo", "printf",
                                                                    "head", "tail")):
                continue
            if not argv and not _EXEC_RE.search(outer):
                continue  # a bare assignment with nothing executed
            invoked = True
            break
    if invoked:
        return ("redteam gate: hook paths are harness-only (the hook wrapper, redteam_gate.py "
                "hook subcommands and REDTEAM_HOOK are run by the harness, not from Bash).")
    return None


def _bash_decision(command: str, cwd_raw: Any, allow_tracked: bool = True,
                   depth: int = 0) -> str | None:
    cwd = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    command = re.sub(r"\$\{PWD\}|\$PWD\b|\$\(\s*pwd\s*\)|`\s*pwd\s*`",
                     lambda _m: str(cwd), command)
    command = re.sub(r"\$\(\s*echo\s+([^()`$;|&<>]*?)\s*\)|`\s*echo\s+([^`$;|&<>]*?)\s*`",
                     lambda m: (m.group(1) if m.group(1) is not None else m.group(2)).strip(),
                     command)
    outer, docs = split_heredocs(command)
    he = hook_path_error(outer)
    if not he and _EXEC_RE.search(outer):
        for _o, body in docs:
            hk = hook_text_hit(body)
            if hk:
                he = f"redteam gate: hook paths are harness-only ({hk} in a heredoc)."
                break
    if he:
        return he
    # Heredoc bodies fed to a program are commands/code themselves: resolve them like the
    # outer text (bounded recursion).
    for opener, body in docs:
        # Only shell bodies are shell commands; a python/node body is code (its text is still
        # scanned for senders and hook paths below), so it is not re-parsed as shell.
        shell_fed = any(re.split(r"[/\\]", w)[-1] in ("bash", "sh", "zsh", "dash", "ksh",
                                                      "source", ".", "eval")
                        for w in command_words(opener)) or bool(
            re.search(r"\|\s*(?:\S*/)?(?:ba|z|da|k)?sh\b", opener))
        if shell_fed:
            if depth >= 3:
                return f"redteam gate: heredocs nested too deep to scan. {BASH_DENY}"
            r = _bash_decision(body, str(cwd), allow_tracked=False, depth=depth + 1)
            if r:
                return r
    try:
        nw = _nested_waiver(command, outer, cwd)
    except ScanLimit as exc:
        nw = f"redteam gate: {exc}; cannot vouch for this claude invocation."
    if nw:
        return nw
    _PENDING_WRITES.clear()
    _PENDING_WRITES.update(pending_writes(outer, docs, cwd))
    de = deploy_error(outer, cwd)
    if not de and _EXEC_RE.search(outer):
        for opener, body in docs:
            if re.search(r"\b(?:python(?:3(?:\.\d+)?)?|node|deno|bun|ruby|perl|php)\b", opener):
                err = script_deploy_error(body, Path("heredoc.py"), cwd)
                if err:
                    de = f"redteam gate: {err}. {DEPLOY_DENY}"
                    break
    if not de and ("$" in outer or "`" in outer):
        v0 = {m.group(1): m.group(2).strip("\"'") for m in _ASSIGN_RE.finditer(outer)}
        ex = _expand(outer, v0, cwd)
        de = deploy_error(ex, cwd) or deploy_error(_expand(ex, v0, cwd), cwd)
    if de:
        return de
    if not _EXEC_RE.search(outer) and not direct_scripts(outer, command_context(outer, cwd)[1]):
        try:
            for p in direct_scripts(outer, command_context(outer, cwd)[1], path_only=True):
                hit = _scan_file(p, str(p))
                if hit:
                    return f"redteam gate: Bash command sends email inline ({hit}). {BASH_DENY}"
        except ScanLimit as exc:
            return f"redteam gate: {exc}. {BASH_DENY}"
        vars0 = {m.group(1): m.group(2).strip("\"'") for m in _ASSIGN_RE.finditer(outer)}
        if "$" not in outer and "`" not in outer:
            return None
        if not _EXEC_RE.search(_expand(outer, vars0, cwd)):
            return None  # nothing runs (P=python3; $P x.py is caught via the expansion)
    err = code_env_error(outer, cwd) or xargs_error(outer, cwd)
    if err:
        return f"redteam gate: {err}. {BASH_DENY}"
    if _B64_PIPE_RE.search(outer):
        return (f"redteam gate: Bash pipes base64-decoded data into an interpreter "
                f"(unscannable). {BASH_DENY}")
    vars_, bases, pp = command_context(outer, cwd)
    expanded = _expand(outer, vars_, cwd)
    try:
        hit = _bash_hit(command, outer, docs, cwd, vars_, bases, pp, expanded)
    except ScanLimit as exc:
        return f"redteam gate: {exc}; the gate cannot vouch for a command that runs code. {BASH_DENY}"
    if hit is None or (allow_tracked and (tracked_script_run(command, cwd)
                                          or chain_allowed(command, cwd))):
        return None
    return f"redteam gate: Bash command sends email inline ({hit}). {BASH_DENY}"


_RISKY_RE = re.compile(
    r"wrangler|vercel|netlify|\bntl\b|\bvc\b|\bgh\b|smtp|\bmail|slack|discord|telegram|"
    r"twilio|linkedin|instantly|lemlist|smartlead|webhook|graph\.|tweet|\bpost|send|/messages|"
    r"deploy|publish|\bapi\.|googleapis|\.sh\b|\.py\b|\.js\b|\.mjs\b|\.ts\b")
_RISKY_PROG_RE = re.compile(r"(?:^|[\s;&|(`])(?:\S*/)?(?:wrangler|vercel|netlify|ntl|vc|gh|http|"
                            r"https|xh)\b")


MAX_BASH_CHARS = 64_000
# Programs that run other text (shells, eval, source, make, xargs, find -exec …) in a big command.
_CMD_STRING_RE_BIG = re.compile(r"(?:^|[\s;&|(`])(?:\S*/)?(?:eval|source|\.|make|gmake|xargs|"
                                r"find|tmux|screen|su|at|batch|script|awk|gawk|env|builtin|"
                                r"exec|command)(?=\s|$)")
BASH_BUDGET_S = 5.0


class _BudgetExceeded(Exception):
    pass


class _time_budget:
    """SIGALRM-based budget where available (POSIX main thread); elsewhere a no-op (the size
    cap still bounds the work)."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.armed = False

    def __enter__(self) -> "_time_budget":
        import signal
        import threading
        if hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread():
            def _raise(_sig: int, _frm: Any) -> None:
                raise _BudgetExceeded()
            self.prev = signal.signal(signal.SIGALRM, _raise)
            signal.setitimer(signal.ITIMER_REAL, self.seconds)
            self.armed = True
        return self

    def __exit__(self, *_exc: Any) -> bool:
        if self.armed:
            import signal
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self.prev)
        return False


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
        cmd0 = ti.get("command") if isinstance(ti.get("command"), str) else ""
        if len(cmd0) > MAX_BASH_CHARS:
            # Too large to parse within the hook timeout: deny anything that may run code,
            # deploy, post or touch the hook; a pure write/read of a big literal passes.
            bare_tokens = {re.split(r"[/\\]", t.strip("<>\"'"))[-1] for t in cmd0.split()}
            if (any(t and _EXEC_WORD_RE.fullmatch(t) for t in bare_tokens)
                    or _RISKY_PROG_RE.search(cmd0) or _HOOK_WRAPPER in cmd0
                    or "redteam" in cmd0.lower() or "/" in cmd0.split(None, 1)[0]
                    or _CMD_STRING_RE_BIG.search(cmd0)):
                return (f"redteam gate: command is {len(cmd0)} chars (> {MAX_BASH_CHARS}) and "
                        f"may run code; too large to scan. Write it to a file and run that, or "
                        f"split it.")
            return None
        try:
            with _time_budget(BASH_BUDGET_S):
                return bash_decision(ti, payload.get("cwd"))
        except _BudgetExceeded:
            if _EXEC_RE.search(cmd0) or _RISKY_PROG_RE.search(cmd0):
                return (f"redteam gate: scan exceeded {BASH_BUDGET_S:g} s on a command that runs "
                        f"code; simplify or split it.")
            return None
        except Exception as exc:  # noqa: BLE001 - see below; logged to stderr
            # Keep sessions unbrickable, but never fail open on a command that may send.
            cmd = ti.get("command") if isinstance(ti.get("command"), str) else ""
            print(f"redteam gate: scanner error {type(exc).__name__}: {exc}", file=sys.stderr)
            if cmd and (_EXEC_RE.search(cmd) or _RISKY_PROG_RE.search(cmd)) \
                    and _RISKY_RE.search(cmd.lower()):
                return (f"redteam gate: gate error ({type(exc).__name__}) on a command that may "
                        f"send or deploy; rephrase it (simpler form) or report the gate bug.")
            return None
    action = gmail_action(name)
    if action is not None:
        reason = gmail_decision(action, ti, state)
    elif "calendar" in name.lower() and name.rsplit("__", 1)[-1] in CAL_ACTIONS:
        reason = calendar_decision(name.rsplit("__", 1)[-1], ti, state)
    elif mcp_outward_kind(name):
        reason = mcp_outward_decision(mcp_outward_kind(name) or "", name.rsplit("__", 1)[-1],
                                      ti, state)
    else:
        return None
    return f"redteam gate: {reason}. {DENY_SUFFIX}" if reason else None


# --------------------------------------------------------- generic MCP share / post / send
_MCP_SHARE_RE = re.compile(r"share|permission", re.I)
_MCP_POST_RE = re.compile(r"post_message|postmessage|send_|publish|reply_to_thread|create_post|"
                          r"post_tweet|tweet|create_message|send_dm|comment|schedule_message|"
                          r"files_upload|create_issue|update_issue|create_pull_request|"
                          r"pull_request_review_write", re.I)
# Repo content pushes are code (covered by the build-contract audit), not outward text.
MCP_NOT_OUTWARD = ("push_files", "create_or_update_file", "delete_file", "create_file",
                   "update_file", "copy_file", "run_secret_scanning", "guide", "create_branch",
                   "fork_repository")
# Explicit decisions for ambiguous verbs: check_in posts a status to others; search_replace
# is a local text edit (read verb rule).
MCP_OUTWARD_EXACT = {"check_in", "checkin", "checkIn".lower()}
MCP_HARNESS_SERVERS = {"claude-code-remote", "ccd_session"}
MCP_READ_VERBS = {"get", "list", "search", "read", "fetch", "download", "query", "resolve",
                  "describe", "view", "count", "check", "suggest", "lookup", "find"}
# Local/no-text mailbox and storage actions (nothing reaches another person).
MCP_LOCAL_VERBS = {"delete", "trash", "untrash", "label", "unlabel", "mark", "unmark",
                   "archive", "apply", "remove", "revoke", "unshare"}
# Any of these words anywhere in the tool name makes it outward, whatever its first verb.
MCP_OUTWARD_WORDS = {"send", "post", "share", "publish", "reply", "forward", "comment", "tweet",
                     "message", "create", "update", "write", "invite", "upload", "schedule",
                     "and", "then"}


def mcp_name_words(seg: str) -> list[str]:
    """snake_case and camelCase words of a tool-name segment, lowercased."""
    out: list[str] = []
    for part in re.split(r"[_\-.\s]+", seg):
        out += [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", part)]
    return [w for w in out if w]
# Outward post/send tools: every string field is text EXCEPT these id/target/enum keys.
_MCP_ID_KEY_RE = re.compile(
    r"(?:^|_)ids?$|[a-z]Ids?$|^(?:owner|repo|repository|org|organization|number|issue_number|"
    r"pull_number|pr_number|channel|channel_id|channel_name|chat_id|thread_ts|ts|visibility|"
    r"branch|base|head|sha|commit_id|path|line|side|start_line|start_side|state|state_reason|"
    r"labels|assignees|reviewers|team_reviewers|milestone|type|draft|method|event|page|per_page|"
    r"limit|cursor|user|username|handle|to|cc|bcc|recipients?|emails?|emailaddress|role|"
    r"mimetype|filename|file_type|maintainer_can_modify|unfurl_links|unfurl_media|"
    r"reply_broadcast|mrkdwn|icon_emoji|icon_url|as_user|parse|link_names|scheduled_at|"
    r"post_at|subject_type|position|in_reply_to|reply_to_tweet_id|quote_tweet_id|media_ids|"
    r"subjecttype|startside|startline|statereason|merge_method|mergemethod|commitid|"
    r"pullnumber|issuenumber|reviewers?|commit_title_hidden|expected_head_sha|inputs|"
    r"from_branch|ref|tag|tag_name|name|key|url|uri|slug|dir|mode|format|scope|kind|level|"
    r"sort|order|direction|query|q|engine|answering|opid|verbose|container|calendarid|"
    r"timezone|start|end|starttime|endtime|response|sendupdates|notificationlevel|"
    r"destination|destinationcalendar|calendar)$"
    r"|(?:Id|Ids|Sha|Ref|Name|Number|Branch|Path|Url|Type|Mode|Method|State|Side|Line)$",
    re.I)
# Recipient keys parsed as email addresses; target keys are non-address audiences.
MCP_ADDR_KEYS = ("emailAddress", "emailAddresses", "email", "emails", "recipient", "recipients",
                 "to", "cc", "bcc", "users", "members", "invitees")
MCP_TARGET_KEYS = ("chatSpaceId", "permissionId", "domain", "channel", "channelId", "channel_id",
                   "chat_id", "chatId", "spaceId", "space", "audience", "webhook_url",
                   "conversationId")
MCP_META = set(MCP_ADDR_KEYS) | set(MCP_TARGET_KEYS) | {
    "fileId", "file_id", "role", "type", "expirationTime", "sendNotificationEmail",
    "transferOwnership", "allowFileDiscovery", "supportsAllDrives", "id", "ids", "messageId",
    "draftId", "postId", "pageId", "documentId", "parentId", "folderId", "visibility",
    "mimeType", "scheduled_at", "unfurl_links", "unfurl_media", "reply_broadcast", "thread_ts",
    "threadId"}
MCP_SHARE_TEXT_KEYS = ("message", "emailMessage", "note", "text")
# Post/send/comment tools: only these keys are outward text; ids/handles are targets/metadata.
_MCP_TEXT_KEY_RE = re.compile(
    r"^(?:body|text|message|content|comment|title|description|subject|caption|status|note|"
    r"reply|markdown|html|summary|headline|commentary|blocks|attachments|embeds|post|tweet)"
    r"(?:_?(?:text|html|markdown|body|md))?$|(?:body|text|message|content|caption|comment)$",
    re.I)


def mcp_outward_kind(name: str) -> str | None:
    """'share' | 'post' for MCP tools that publish/share/send outward; None for reads.
    Gmail/Calendar are routed earlier; this covers every other server."""
    if not isinstance(name, str) or not name.startswith("mcp__"):
        return None
    parts = name.split("__")
    if len(parts) < 3 or parts[1].lower() in MCP_HARNESS_SERVERS:
        return None
    seg = parts[-1]
    low = seg.lower()
    if low in MCP_NOT_OUTWARD:
        return None
    if low in MCP_OUTWARD_EXACT:
        return "post"
    words = mcp_name_words(seg)
    outward_word = any(w in MCP_OUTWARD_WORDS or w.rstrip("s") in MCP_OUTWARD_WORDS
                       for w in words)
    if len(words) == 1 and not outward_word:
        w = words[0]
        verb = next((v for v in MCP_READ_VERBS | MCP_LOCAL_VERBS if w.startswith(v)), None)
        if verb and not any(o in w[len(verb):] for o in MCP_OUTWARD_WORDS - {"and"}):
            return None  # getpermissions, listfiles
    readish = bool(words) and (words[0] in MCP_READ_VERBS or words[-1] == "read"
                               or words[0] in MCP_LOCAL_VERBS)
    if readish and not outward_word:
        return None
    if readish:
        return "post"  # read verb + outward word (resolve_share_link): text rule decides
    if _MCP_SHARE_RE.search(low):
        return "share"
    return "post"  # structural: every other MCP tool is outward (ids/enums-only calls pass)


def _mcp_recipients(ti: dict) -> tuple[set[str], list[str], list[str]]:
    addrs: set[str] = set()
    bad: list[str] = []
    targets: list[str] = []
    for k in MCP_ADDR_KEYS:
        if _present(ti.get(k)):
            a, b = parse_addrs(ti[k])
            addrs |= a
            bad += b
    tkeys = {k.lower() for k in MCP_TARGET_KEYS} | {"channel_name", "channelname"} | \
        _USER_TARGET_KEYS
    for k, v in ti.items():
        if isinstance(k, str) and k.lower() in tkeys and _present(v):
            targets.append(f"{k}={str(v)[:40]}")
    if str(ti.get("visibility", "")).lower() in ("public", "anyone", "everyone", "connections",
                                                  "unlisted"):
        targets.append(f"visibility={ti['visibility']}")
    if str(ti.get("type", "")).lower() in ("anyone", "domain"):
        targets.append(f"type={ti['type']}")
    return addrs, bad, targets


_RELEASE_TEXT_KEYS = {"name", "tag_name", "tagname"}
_USER_TARGET_KEYS = {"user", "username", "handle", "screen_name", "screenname"}


def _mcp_id_key(action: str, key: str) -> bool:
    lk = key.lower()
    if "release" in action.lower() and lk in _RELEASE_TEXT_KEYS:
        return False
    if lk in _USER_TARGET_KEYS:
        return True  # handled as a target below
    return bool(_MCP_ID_KEY_RE.search(key))


def mcp_outward_decision(kind: str, action: str, ti: dict, state: Path) -> str | None:
    """share: text = message-like field (if any); recipients must be within one passed record's
    --to/--cc/--bcc. post/send/publish: every non-metadata text field must be passed."""
    bad = unparseable_input(ti, MCP_META)
    if bad:
        return f"{action}: {bad}"
    ledger = Ledger(state)
    fields = text_fields(ti, MCP_META, skip=())
    if kind == "share":
        fields = [f for f in fields if f[0] in MCP_SHARE_TEXT_KEYS]
    else:
        fields = [f for f in text_fields(ti, set(MCP_TARGET_KEYS) | set(MCP_ADDR_KEYS), skip=())
                  if not _mcp_id_key(action, f[0])
                  and f[0].lower() not in {k.lower() for k in MCP_TARGET_KEYS}]
    addrs, bad, targets = _mcp_recipients(ti)
    if bad:
        return f"{action}: unparseable recipient(s): {', '.join(bad[:3])}"
    if fields:
        err = _check_fields(action, fields, ti, ledger, envelope=False)
        if err:
            return err
        _k, raw, h = fields[0]
        rows = ledger.rows_for(_sha256(normalise(raw, h)))
    elif kind == "post":
        rows = []  # only ids/enums (approve a review, close an issue): no outward text
    else:
        rows = [r for r in ledger.rows if r.get("waived") is not True]
    if any(r.get("waived") is True for r in rows):
        return None
    if targets:
        return (f"{action}: non-address audience ({', '.join(targets[:3])}) needs a red-teamed "
                f"message waived by the operator, or address recipients")
    if not addrs:
        return None if kind == "post" else f"{action}: no recipient could be read"
    if kind == "post" and not fields:
        return f"{action}: recipients given but no red-teamed text to bind them to"
    for r in rows:
        allowed = {str(a).lower() for k in ("to", "cc", "bcc") for a in (r.get(k) or [])}
        if addrs <= allowed:
            return None
    return (f"{action}: recipient(s) not recorded with --to/--cc/--bcc of a passed record: "
            + ", ".join(sorted(addrs)[:5]))


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
        return low.startswith("mcp__") and ("gmail" in low or "calendar" in low
                                            or bool(_MAIL_TOOL_RE.search(low))
                                            or mcp_outward_kind(name) is not None)
    return bool(_OUTWARD_RAW_RE.search(raw) or re.search(
        r'"tool_name"\s*:\s*"mcp__[^"]*(?:send_email|send_message|create_draft)', raw, re.I))


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
    except (OSError, RuntimeError):
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


def _is_claude_cmdline(argv: list[str]) -> bool:
    if not argv:
        return False
    if re.fullmatch(r"claude(?:\.exe)?", re.split(r"[/\\]", argv[0])[-1], re.I):
        return True
    # node-launched CLI: `node .../@anthropic-ai/claude-code/cli.js`
    return (re.split(r"[/\\]", argv[0])[-1].lower().startswith("node") and len(argv) > 1
            and "claude-code" in argv[1])


def nested_claude_depth(pid: int | None = None) -> int:
    """Number of Claude CLI processes among this process's ancestors (Linux /proc). A top-level
    session's hook sees 1; a `claude -p` started from that session's Bash sees 2. Returns 0 when
    /proc is unavailable (Windows/macOS: rely on the Bash rule). Test hook: REDTEAM_MIN_CLAUDE_DEPTH
    can only raise the result, never lower it."""
    floor = os.environ.get("REDTEAM_MIN_CLAUDE_DEPTH", "")
    floor_n = int(floor) if floor.isdigit() else 0
    pid = os.getpid() if pid is None else pid
    depth, hops = 0, 0
    while pid > 1 and hops < 64:
        hops += 1
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            break
        if _is_claude_cmdline([a.decode("utf-8", "replace") for a in argv if a]):
            depth += 1
        try:
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (IndexError, ValueError):
            break
    return max(depth, floor_n)


def _user_text(row: dict) -> str | None:
    """Text of a genuine operator prompt row, or None (tool results, meta, sidechains)."""
    if row.get("type") != "user" or row.get("isMeta") or row.get("isSidechain"):
        return None
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict)
                         and b.get("type") == "text" and isinstance(b.get("text"), str))
    return None


def genuine_prompt(payload: dict, prompt: str) -> bool:
    """The payload's transcript lives under the transcript root and its last user row is a
    genuine operator prompt containing this waive line."""
    tp = payload.get("transcript_path")
    if not isinstance(tp, str) or not tp:
        return False
    try:
        rp = Path(tp).expanduser().resolve()
        root = transcript_root().resolve()
        if not rp.is_relative_to(root) or not rp.is_file():
            return False
        size = rp.stat().st_size
        with rp.open("rb") as fh:
            fh.seek(max(0, size - 4_000_000))
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, RuntimeError):
        return False
    line = _WS_RE.sub(" ", prompt).strip().lower()
    # The last 2 genuine operator prompts: covers a harness that writes the current prompt
    # before the hook (last entry) and one that writes it after (the operator re-sends the same
    # line, which then finds the first copy). Tool results, meta and sidechain rows never count.
    seen = 0
    for raw in reversed(lines):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("type") != "user":
            continue
        text = _user_text(row)
        if text is None:
            continue
        if line in _WS_RE.sub(" ", text).strip().lower():
            return True
        seen += 1
        if seen >= 2:
            break
    return False


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
        if not genuine_prompt(payload, prompt):
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"redteam: waiver NOT recorded for {sha12}: waiver not "
                                     "recorded yet; send the same `redteam waive …` line "
                                     "once more"}},
                separators=(",", ":")))
            return EXIT_OK
        nested = nested_claude_depth()
        if nested >= 2:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"redteam: waiver for {sha12} NOT recorded (nested Claude "
                                     "session; the operator must type it in their own session)"}},
                separators=(",", ":")))
            return EXIT_OK
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
              "with REDTEAM_HOOK set to 1); verdicts come from SubagentStop, waivers from the operator.",
              file=sys.stderr)
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
