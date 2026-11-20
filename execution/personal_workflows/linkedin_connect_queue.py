#!/usr/bin/env python3
"""LinkedIn connection-request queue: consolidate CSVs, pick today's batch, keep a sent ledger.

The script never touches LinkedIn. It owns the deterministic half of the daily routine
(`directives/personal_workflows/linkedin_connect_daily.md`): a de-duplicated master list, a
hard daily cap, a per-person ledger, and the four-field report (name, company, position,
LinkedIn ID). The browser step is done by Cowork on the operator's own logged-in Chrome.

Subcommands
  consolidate --in a.csv b.csv [...]   merge CSVs into master.csv (idempotent, re-runnable)
  plan [--limit 20]                     write/print today's queue (re-prints if it already exists)
  mark SLUG --status sent|skipped|already_connected|pending|withdrawn|retry [--note ..] [--canonical SLUG2]
                                        --canonical records the slug LinkedIn redirected to, as an alias
  report [--date YYYY-MM-DD] [--out f]  the operator's report: ONE markdown table (first name, name,
                                        company, position, LinkedIn ID) and nothing else
  sync --ledger f [--aliases f]         union rows from another copy of the ledger/aliases (Drive snapshot;
                                        pre-2026-10-26 report .md with a ledger block still accepted)
  status                                counts: master / sent / remaining / today
  lock acquire|release|show             run lock so two scheduled slots never send concurrently
                                        (acquire exits 4 if a live lock < LOCK_TTL_MIN old exists)
  health [--json]                       invariants: no double terminal rows, today's sent <= cap,
                                        master present, lock not stale; exit 1 on any breach
  intake [--dry-run]                    pull new prospect lists from Gmail (subject contains "LC list",
                                        .csv attached), keep leaders only, merge into master.csv; each
                                        attachment is ingested once (intake.csv, keyed by sha256)

State lives in --data-dir (default .tmp/linkedin_connect, gitignored):
  master.csv   ledger.csv   aliases.csv   queue_YYYY-MM-DD.csv   report_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import imaplib
import datetime as dt
import os
import random
import re
import sys
from email import message_from_bytes, policy
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

DAILY_CAP = 20
# Operator order 2026-11-03: 20 a day on send days only (Mon, Tue, Thu, Fri, Sat; rest Wed and Sun),
# ~100/week = LinkedIn's observed free-account weekly limit. The send days live in
# linkedin_connect_send.py (SEND_DAYS); this cap is the one source of truth for both scripts.
# There is still no rolling weekly trim here; LinkedIn's "weekly invitation limit" dialog is a stop trigger.
FIELDS = ("slug", "name", "company", "position", "linkedin_url", "source_file")
LEDGER_FIELDS = ("ts", "date", "slug", "name", "status", "note")
STATUSES = ("sent", "skipped", "already_connected", "pending", "withdrawn", "retry")
# Any status but "retry" is terminal: never queue again. "retry" (unconfirmed click, page failed
# to load) keeps the person out of today's queue and eligible from tomorrow.
TERMINAL = frozenset(STATUSES) - {"retry"}
NO_CONNECT_DAYS = 3  # "retry no_connect_button" on this many different days -> skipped no_connect_button_3x
# RCA 2026-11-11: a person failing for any other reason stayed "retry" forever. Any retry on this many different
# days -> skipped retry_<N>x. Safe on a markup break: the sender stops a day after <= 12 retries, drawn at random
# from thousands, so nobody realistically reaches 4 days before the break is fixed.
RETRY_MAX_DAYS = 4
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
LOCK_TTL_MIN = 120  # a run never legitimately exceeds this; older locks are treated as crashed runs

_SLUG_RE = re.compile(r"linkedin\.com/in/([^/?#\s]+)", re.I)

# Column-name aliases, lowercase, matched after stripping non-alphanumerics.
ALIASES = {
    "linkedin_url": ("linkedinurl", "linkedin", "profileurl", "profile", "url", "linkedinprofile",
                     "linkedinprofileurl", "personlinkedinurl", "link"),
    "name": ("name", "fullname", "person", "contact", "contactname"),
    "first": ("firstname", "first", "givenname"),
    "last": ("lastname", "last", "surname", "familyname"),
    "company": ("company", "companyname", "organization", "organisation", "employer", "currentcompany"),
    "position": ("position", "title", "jobtitle", "role", "headline", "currentposition", "currenttitle"),
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _find(headers: list[str], key: str) -> str | None:
    want = ALIASES[key]
    normed = {_norm(h): h for h in headers}
    for alias in want:
        if alias in normed:
            return normed[alias]
    return None


def slug_of(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    if re.search(r"linkedin\.com/(pub|sales|company|school)/", url, re.I):
        return None  # old /pub/, Sales Navigator, company pages: not a connectable /in/ profile
    m = _SLUG_RE.search(url)
    if m:
        return unquote(m.group(1)).strip().lower().rstrip("/") or None
    # bare slug typed into the column
    token = url.strip().strip("/").lower()
    if token and "/" not in token and " " not in token and "." not in token:
        return token
    return None


def read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    text = None
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    assert text is not None
    rows = list(csv.DictReader(text.splitlines()))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None} for row in rows]


def pick_url_column(headers: list[str], rows: list[dict[str, str]]) -> str | None:
    """The column whose values most often contain a linkedin.com/in URL; alias names as fallback."""
    best, best_n = None, 0
    for h in headers:
        n = sum(1 for r in rows[:200] if "linkedin.com/in/" in (r.get(h, "") or "").lower())
        if n > best_n:
            best, best_n = h, n
    return best or _find(headers, "linkedin_url")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    # Atomic: master.csv now also grows unattended (intake); a crash mid-write must never leave a half file.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.master = data_dir / "master.csv"
        self.ledger = data_dir / "ledger.csv"
        self.aliases = data_dir / "aliases.csv"
        self.lock = data_dir / "run.lock"
        self.intake = data_dir / "intake.csv"
        self.lists = data_dir / "lists"

    def load_intake(self) -> list[dict[str, str]]:
        return read_csv(self.intake) if self.intake.exists() else []

    def append_intake(self, row: dict) -> None:
        new = not self.intake.exists()
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.intake.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(INTAKE_FIELDS), extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)

    def load_aliases(self) -> dict[str, str]:
        """redirected slug -> master slug (LinkedIn canonicalises some profile URLs on load)."""
        return {r["alias"]: r["slug"] for r in read_csv(self.aliases)} if self.aliases.exists() else {}

    def add_alias(self, alias: str, slug: str) -> None:
        new = not self.aliases.exists()
        with self.aliases.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["alias", "slug"])
            w.writerow([alias, slug])

    def load_master(self) -> list[dict[str, str]]:
        return read_csv(self.master) if self.master.exists() else []

    def load_ledger(self) -> list[dict[str, str]]:
        return read_csv(self.ledger) if self.ledger.exists() else []

    def append_ledger(self, row: dict[str, str]) -> None:
        new = not self.ledger.exists()
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(LEDGER_FIELDS))
            if new:
                w.writeheader()
            w.writerow(row)

    def queue_path(self, day: str) -> Path:
        return self.dir / f"queue_{day}.csv"


def cmd_consolidate(store: Store, paths: list[str]) -> int:
    return 0 if consolidate(store, paths) is not None else 2


def consolidate(store: Store, paths: list[str]) -> int | None:
    """Merge CSVs into master.csv; returns the number of new people, None if a file has no URL column."""
    existing = {r["slug"]: r for r in store.load_master()}
    aliases = store.load_aliases()
    added = skipped_nourl = dupes = 0
    for p in paths:
        path = Path(p)
        rows = read_csv(path)
        if not rows:
            print(f"[warn] {path}: empty", file=sys.stderr)
            continue
        headers = list(rows[0].keys())
        c_url, c_name = pick_url_column(headers, rows), _find(headers, "name")
        c_first, c_last = _find(headers, "first"), _find(headers, "last")
        c_co, c_pos = _find(headers, "company"), _find(headers, "position")
        if not c_url:
            print(f"[error] {path}: no LinkedIn URL column (headers: {headers})", file=sys.stderr)
            return None
        for r in rows:
            slug = slug_of(r.get(c_url, ""))
            if not slug:
                skipped_nourl += 1
                continue
            slug = aliases.get(slug, slug)  # a fresh export may carry the redirected slug
            name = r.get(c_name, "") if c_name else ""
            if not name and (c_first or c_last):
                name = " ".join(x for x in (r.get(c_first, ""), r.get(c_last, "")) if x)
            rec = {
                "slug": slug,
                "name": name,
                "company": r.get(c_co, "") if c_co else "",
                "position": r.get(c_pos, "") if c_pos else "",
                "linkedin_url": f"https://www.linkedin.com/in/{slug}/",
                "source_file": path.name,
            }
            if not rec["name"]:
                rec["name"] = slug.replace("-", " ").title()
            if slug in existing:
                dupes += 1
                # fill blanks from the later file, never overwrite
                for k in ("name", "company", "position"):
                    if not existing[slug].get(k) and rec[k]:
                        existing[slug][k] = rec[k]
                continue
            existing[slug] = rec
            added += 1
    write_csv(store.master, list(existing.values()), FIELDS)
    print(f"master.csv: {len(existing)} people (+{added} new, {dupes} duplicates merged, "
          f"{skipped_nourl} rows without a LinkedIn URL skipped)")
    return added


# --------------------------------------------------------------------------- list intake
# Operator order 2026-11-20: "I add files with new lists and you add to the existing list", no HITL.
# Transport = the Gmail mailbox the job already reports from (GMAIL_SMTP_USER + app password, over IMAP):
# any message or draft whose subject contains "LC list" with a .csv (or .csv.gz) attached. The Gmail
# connector silently drops a ~1.3 MB attachment on create_draft (2026-11-20), so cloud drafts carry .csv.gz. Prospect lists never go
# through git (public repo). Read-only on the mailbox; idempotent through intake.csv (sha256 per file).
INTAKE_QUERY = '"subject:(LC list) has:attachment"'  # extension filter in csv_attachments
INTAKE_FIELDS = ("ts", "sha256", "filename", "rows_in", "rows_kept", "added", "note")
LEADER_SENIORITY = frozenset({"c_suite", "owner", "founder", "partner", "vp"})
NOT_LEADER_RE = re.compile(r"assistant|president.?s (?:club|council)|\bintern\b|territory|chief of staff"
                           r"|account (?:manager|executive)|sales rep", re.I)
INTAKE_FLOOR = 0.02  # a file of >= 50 rows keeping < 2% = unknown seniority vocabulary: hold it, merge nothing
_LIST_RE = re.compile(r'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$')


def leaders_only(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Top leaders only. An export's Seniority column (Apollo / LeadOcean vocabulary) gates when present;
    the title veto (assistants, assistant VPs, chiefs of staff, reps with "President's Club" titles) always."""
    if not rows:
        return []
    headers = list(rows[0])
    c_sen = next((h for h in headers if _norm(h) == "seniority"), None)
    c_pos = _find(headers, "position")
    return [r for r in rows
            if (not c_sen or r.get(c_sen, "").strip().lower() in LEADER_SENIORITY)
            and not (c_pos and NOT_LEADER_RE.search(r.get(c_pos, "")))]


def gmail_folders(list_lines: list) -> list[str]:
    """All Mail and Drafts by IMAP special-use flag (names are localised: "Brouillons", "Tous les messages")."""
    found: dict[str, str] = {}
    for raw in list_lines or []:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        m = _LIST_RE.match(line)
        if m:
            for flag in ("\\All", "\\Drafts"):
                if flag in m.group("flags").split():
                    found[flag] = m.group("name").strip()
    return [found[f] for f in ("\\All", "\\Drafts") if f in found]


def csv_attachments(raw_msg: bytes) -> list[tuple[str, bytes]]:
    msg = message_from_bytes(raw_msg, policy=policy.default)
    out = []
    for part in msg.iter_attachments():
        name = part.get_filename() or ""
        low = name.lower()
        data = part.get_payload(decode=True) if low.endswith((".csv", ".csv.gz")) else None
        if data and low.endswith(".gz"):
            data, name = gzip.decompress(data), name[:-3]
        if data:
            out.append((name, data))
    return out


def ingest_file(store: Store, name: str, data: bytes, dry_run: bool = False) -> dict:
    """One attachment -> leaders -> master.csv. Returns the intake row (appended to intake.csv unless dry_run)."""
    sha = hashlib.sha256(data).hexdigest()
    safe = re.sub(r"[^\w.-]+", "_", Path(name).name)[:80] or "list.csv"
    row = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "sha256": sha, "filename": name,
           "rows_in": 0, "rows_kept": 0, "added": 0, "note": ""}
    raw_path = store.lists / f"{_today()}_{sha[:8]}_{safe}"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(data)
    rows = read_csv(raw_path)
    kept = leaders_only(rows)
    row["rows_in"], row["rows_kept"] = len(rows), len(kept)
    if len(rows) >= 50 and len(kept) < INTAKE_FLOOR * len(rows):
        row["note"] = f"held: leader filter kept {len(kept)}/{len(rows)} (unknown seniority values?)"
    elif not kept:
        row["note"] = "no leader rows"
    elif dry_run:
        row["note"] = "dry-run"
    else:
        clean = raw_path.with_name(raw_path.stem + "_leaders.csv")
        write_csv(clean, kept, tuple(rows[0].keys()))
        added = consolidate(store, [str(clean)])
        row["added"] = added or 0
        row["note"] = "ok" if added is not None else "held: no LinkedIn URL column"
    if dry_run:
        raw_path.unlink(missing_ok=True)
    else:
        store.append_intake(row)
    return row


def intake_gmail(store: Store, user: str, password: str, dry_run: bool = False,
                 log: Callable[[str], None] = print, imap_factory: Callable | None = None) -> list[dict]:
    """Pull every not-yet-ingested "LC list" CSV from the mailbox into master.csv. Raises on IMAP errors;
    the daily run logs them and keeps sending from the current master (fail-open helper)."""
    seen = {r.get("sha256", "") for r in store.load_intake()}
    done: list[dict] = []
    imap = (imap_factory or (lambda: imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)))()
    try:
        imap.login(user, password)
        for folder in gmail_folders(imap.list()[1]):
            if imap.select(folder, readonly=True)[0] != "OK":
                continue
            typ, data = imap.search(None, "X-GM-RAW", INTAKE_QUERY)
            ids = (data[0] or b"").split() if typ == "OK" and data else []
            for mid in ids:
                typ, parts = imap.fetch(mid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
                if typ != "OK" or not raw:
                    continue
                for name, blob in csv_attachments(raw):
                    sha = hashlib.sha256(blob).hexdigest()
                    if sha in seen:
                        continue
                    seen.add(sha)
                    row = ingest_file(store, name, blob, dry_run)
                    log(f"intake {name}: {row['rows_in']} rows, {row['rows_kept']} leaders, "
                        f"+{row['added']} new ({row['note']})")
                    done.append(row)
    finally:
        try:
            imap.logout()
        except Exception as exc:  # logout after a dropped connection: nothing left to clean up
            log(f"intake: imap logout failed ({type(exc).__name__})")
    if not done:
        log("intake: no new lists")
    return done


def cmd_intake(store: Store, dry_run: bool) -> int:
    with contextlib.suppress(ImportError):  # python-dotenv is optional, env vars may already be set
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    if not (user and pw):
        print("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set", file=sys.stderr)
        return 3
    rows = intake_gmail(store, user, pw, dry_run)
    return 1 if any(r["note"].startswith("held") for r in rows) else 0


def _today() -> str:
    return dt.date.today().isoformat()


def _sent_on(ledger: list[dict], day: str) -> list[dict]:
    return [r for r in ledger if r["date"] == day and r["status"] == "sent"]


def _sent_last_7_days(ledger: list[dict]) -> int:
    cutoff = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    return sum(1 for r in ledger if r["status"] == "sent" and r["date"] > cutoff)


def _print_rows(rows: list[dict]) -> None:
    for i, r in enumerate(rows, 1):
        print(f"{i:2d}. {r['name'] or '(no name)'} | {r['company']} | {r['position']} | {r['linkedin_url']}")


def _blocked(ledger: list[dict], day: str) -> set[str]:
    """Slugs that must not be queued today: any terminal status, or a retry logged today."""
    out = set()
    for r in ledger:
        if r["status"] in TERMINAL or (r["status"] == "retry" and r["date"] == day):
            out.add(r["slug"])
    return out


def cmd_plan(store: Store, limit: int, shuffle: bool) -> int:
    if limit < 1:
        print("--limit must be >= 1", file=sys.stderr)
        return 2
    limit = min(limit, DAILY_CAP)
    day = _today()
    ledger = store.load_ledger()
    master = store.load_master()
    if not master:
        print("master.csv is empty; run consolidate first", file=sys.stderr)
        return 2
    blocked = _blocked(ledger, day)
    already = len(_sent_on(ledger, day))
    room = max(0, limit - already)
    qp = store.queue_path(day)
    queue = [r for r in read_csv(qp) if r["slug"] not in blocked] if qp.exists() else []
    queued = {r["slug"] for r in queue} | ({r["slug"] for r in read_csv(qp)} if qp.exists() else set())
    # top up: people still to do must be able to fill the remaining room
    if len(queue) < room:
        pool = [r for r in master if r["slug"] not in blocked and r["slug"] not in queued]
        if shuffle:
            random.Random(day).shuffle(pool)  # deterministic per day
        queue.extend(pool[:room - len(queue)])
    queue = queue[:room]
    write_csv(qp, queue, FIELDS)
    remaining = sum(1 for r in master if r["slug"] not in blocked) - len(queue)
    print(f"queue for {day}: {len(queue)} to do, {already} already sent today, {remaining} remain after today")
    _print_rows(queue)
    return 0


def cmd_mark(store: Store, slug: str, status: str, note: str, canonical: str | None = None) -> int:
    slug = slug_of(slug) or slug.lower()
    master = {r["slug"]: r for r in store.load_master()}
    aliases = store.load_aliases()
    slug = aliases.get(slug, slug)
    if canonical:
        canonical = slug_of(canonical) or canonical.lower()
        if canonical != slug and canonical not in aliases and canonical not in master:
            store.add_alias(canonical, slug)
    if slug not in master:
        print(f"unknown slug {slug!r} (not in master.csv)", file=sys.stderr)
        return 2
    ledger = store.load_ledger()
    if any(r["slug"] == slug and r["status"] in TERMINAL for r in ledger):
        print(f"{slug}: already in ledger with a final status, not marking again")
        return 0
    day = _today()
    if status == "retry" and note == "no_connect_button":
        days = {r["date"] for r in ledger if r["slug"] == slug and r["status"] == "retry"
                and r["note"] == "no_connect_button"} | {day}
        if len(days) >= NO_CONNECT_DAYS:  # follow-only profile: stop re-trying it forever
            status, note = "skipped", "no_connect_button_3x"
    if status == "retry":
        days = {r["date"] for r in ledger if r["slug"] == slug and r["status"] == "retry"} | {day}
        if len(days) >= RETRY_MAX_DAYS:
            status, note = "skipped", f"retry_{RETRY_MAX_DAYS}x" + (f":{note}" if note else "")
    if status == "sent" and len(_sent_on(ledger, day)) >= DAILY_CAP:
        print(f"REFUSED: daily cap of {DAILY_CAP} already reached for {day}", file=sys.stderr)
        return 3
    store.append_ledger({
        "ts": dt.datetime.now().isoformat(timespec="seconds"), "date": day, "slug": slug,
        "name": master[slug]["name"], "status": status, "note": note,
    })
    n = len(_sent_on(ledger, day)) + (1 if status == "sent" else 0)
    print(f"{slug}: {status}  (today sent {n}/{DAILY_CAP})")
    return 0


def _first_name(full: str) -> str:
    parts = (full or "").split()
    return parts[0] if parts else ""


def _cell(v: str) -> str:
    """One markdown table cell: collapse whitespace/newlines, escape pipes so a row never splits."""
    return " ".join((v or "").split()).replace("|", "\\|")


def cmd_report(store: Store, day: str | None, out: str | None) -> int:
    """The operator's report: ONE markdown table, nothing else (operator order 2026-10-26).

    Columns: # | First name | Name | Company | Position | LinkedIn ID. No title, no counts, no
    status note, no ledger dump; diagnostics go to stderr only. The slot uploads this file to Drive as
    report_<date>.md and the 20:00 Europe/Paris cloud task emails its body. Machine state travels via
    the Drive ledger snapshot, never via this report."""
    day = day or _today()
    master = {r["slug"]: r for r in store.load_master()}
    sent = _sent_on(store.load_ledger(), day)
    lines = ["| # | First name | Name | Company | Position | LinkedIn ID |",
             "|---|---|---|---|---|---|"]
    for i, r in enumerate(sent, 1):
        m = master.get(r["slug"], {})
        name = m.get("name") or r["name"]
        lines.append(f"| {i} | {_cell(_first_name(name))} | {_cell(name)} | {_cell(m.get('company', ''))} | "
                     f"{_cell(m.get('position', ''))} | [{r['slug']}](https://www.linkedin.com/in/{r['slug']}/) |")
    text = "\n".join(lines) + "\n"
    path = Path(out) if out else store.dir / f"report_{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"[written {path}; {len(sent)} sent on {day}]", file=sys.stderr)
    return 0


def _extract_ledger_block(path: Path) -> list[dict[str, str]]:
    """Accept a plain ledger CSV, or a legacy (pre-2026-10-26) report .md with a ```ledger block."""
    text = path.read_text(encoding="utf-8")
    if "```ledger" in text:
        text = text.split("```ledger", 1)[1].split("```", 1)[0].strip()
    rows = list(csv.DictReader(text.splitlines()))
    return [r for r in rows if r.get("slug") and r.get("status") in STATUSES]


def cmd_sync(store: Store, ledger_path: str | None, aliases_path: str | None) -> int:
    added = 0
    if ledger_path:
        mine = store.load_ledger()
        seen = {(r["slug"], r["status"], r["date"]) for r in mine}
        for r in _extract_ledger_block(Path(ledger_path)):
            key = (r["slug"], r["status"], r["date"])
            if key in seen:
                continue
            if r["status"] in TERMINAL and any(m["slug"] == r["slug"] and m["status"] in TERMINAL for m in mine):
                continue  # already final here; keep ours
            store.append_ledger({k: r.get(k, "") for k in LEDGER_FIELDS})
            mine.append(r); seen.add(key); added += 1
    a_added = 0
    if aliases_path:
        have = store.load_aliases()
        for r in read_csv(Path(aliases_path)):
            if r.get("alias") and r.get("slug") and r["alias"] not in have:
                store.add_alias(r["alias"], r["slug"]); have[r["alias"]] = r["slug"]; a_added += 1
    print(f"sync: +{added} ledger row(s), +{a_added} alias(es); ledger now {len(store.load_ledger())} rows")
    return 0


def _lock_age_min(store: Store) -> float | None:
    """Minutes since the lock was taken; None if no live lock. A released lock is a file whose
    first field is 'released' (we never delete files: Windows device shells may lack delete rights)."""
    if not store.lock.exists():
        return None
    first = store.lock.read_text(encoding="utf-8").strip().split("|")[0]
    if first == "released" or not first:
        return None
    try:
        ts = dt.datetime.fromisoformat(first)
    except ValueError:
        return float("inf")
    return (dt.datetime.now() - ts).total_seconds() / 60


def cmd_lock(store: Store, action: str) -> int:
    age = _lock_age_min(store)
    if action == "show":
        print("no lock" if age is None else f"lock age {age:.0f} min ({'stale' if age > LOCK_TTL_MIN else 'live'})")
        return 0
    if action == "release":
        store.dir.mkdir(parents=True, exist_ok=True)
        store.lock.write_text(f"released|{dt.datetime.now().isoformat(timespec='seconds')}", encoding="utf-8")
        print("lock released")
        return 0
    if age is not None and age <= LOCK_TTL_MIN:
        print(f"REFUSED: another run holds the lock ({age:.0f} min old); exit without sending", file=sys.stderr)
        return 4
    if age is not None:
        print(f"[warn] stale lock ({age:.0f} min) from a crashed run, taking over", file=sys.stderr)
    store.dir.mkdir(parents=True, exist_ok=True)
    store.lock.write_text(f"{dt.datetime.now().isoformat(timespec='seconds')}|{os.uname().nodename if hasattr(os, 'uname') else os.environ.get('COMPUTERNAME', '')}", encoding="utf-8")
    print("lock acquired")
    return 0


def cmd_health(store: Store, as_json: bool) -> int:
    import json
    master, ledger = store.load_master(), store.load_ledger()
    day = _today()
    term: dict[str, int] = {}
    for r in ledger:
        if r["status"] in TERMINAL:
            term[r["slug"]] = term.get(r["slug"], 0) + 1
    doubles = sorted(s for s, n in term.items() if n > 1)
    slugs = {r["slug"] for r in master}
    sent_today = len(_sent_on(ledger, day))
    age = _lock_age_min(store)
    checks = {
        "master_present": len(master) > 0,
        "no_double_terminal_rows": not doubles,
        "sent_today_within_cap": sent_today <= DAILY_CAP,
        "ledger_statuses_valid": all(r["status"] in STATUSES for r in ledger),
        "no_orphan_ledger_rows": all(r["slug"] in slugs for r in ledger) if master else True,
        "lock_not_stale": age is None or age <= LOCK_TTL_MIN,
    }
    out = {"date": day, "ok": all(checks.values()), "checks": checks, "sent_today": sent_today,
           "cap": DAILY_CAP, "remaining": sum(1 for r in master if r["slug"] not in term),
           "doubles": doubles[:10], "lock_age_min": None if age is None else round(age)}
    if as_json:
        print(json.dumps(out, indent=1))
    else:
        print(("HEALTHY" if out["ok"] else "UNHEALTHY") + f": sent today {sent_today}/{DAILY_CAP}, remaining {out['remaining']}")
        for k, v in checks.items():
            if not v:
                print(f"  FAIL {k}" + (f" {doubles[:5]}" if k == "no_double_terminal_rows" else ""))
    return 0 if out["ok"] else 1


def cmd_status(store: Store) -> int:
    master, ledger = store.load_master(), store.load_ledger()
    done = {r["slug"] for r in ledger}
    by = {s: sum(1 for r in ledger if r["status"] == s) for s in STATUSES}
    slugs = {r["slug"] for r in master}
    orphans = [r["slug"] for r in ledger if r["slug"] not in slugs]
    bad = [r for r in ledger if r["status"] not in STATUSES]
    done = {r["slug"] for r in ledger if r["status"] in TERMINAL}
    print(f"master: {len(master)}  handled: {len(done)}  remaining: {len(master) - len(done)}")
    if orphans or bad:
        print(f"[warn] ledger integrity: {len(orphans)} orphan slug(s), {len(bad)} bad status row(s)", file=sys.stderr)
    print(f"today sent: {len(_sent_on(ledger, _today()))}/{DAILY_CAP}  last 7 days: {_sent_last_7_days(ledger)} (no weekly cap)")
    print("by status: " + ", ".join(f"{k}={v}" for k, v in by.items()))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("LINKEDIN_CONNECT_DIR", ".tmp/linkedin_connect"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consolidate"); c.add_argument("--in", dest="inputs", nargs="+", required=True)
    p = sub.add_parser("plan"); p.add_argument("--limit", type=int, default=DAILY_CAP)
    p.add_argument("--shuffle", action="store_true", help="randomise pick order (seeded by date)")
    m = sub.add_parser("mark"); m.add_argument("slug"); m.add_argument("--status", choices=STATUSES, required=True)
    m.add_argument("--note", default="")
    m.add_argument("--canonical", help="slug LinkedIn redirected to; stored as an alias of SLUG")
    r = sub.add_parser("report"); r.add_argument("--date"); r.add_argument("--out")
    sub.add_parser("status")
    y = sub.add_parser("sync"); y.add_argument("--ledger"); y.add_argument("--aliases")
    lk = sub.add_parser("lock"); lk.add_argument("action", choices=("acquire", "release", "show"))
    h = sub.add_parser("health"); h.add_argument("--json", action="store_true")
    it = sub.add_parser("intake"); it.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    store = Store(Path(a.data_dir))
    if a.cmd == "consolidate":
        return cmd_consolidate(store, a.inputs)
    if a.cmd == "plan":
        return cmd_plan(store, a.limit, a.shuffle)
    if a.cmd == "mark":
        return cmd_mark(store, a.slug, a.status, a.note, a.canonical)
    if a.cmd == "report":
        return cmd_report(store, a.date, a.out)
    if a.cmd == "sync":
        return cmd_sync(store, a.ledger, a.aliases)
    if a.cmd == "lock":
        return cmd_lock(store, a.action)
    if a.cmd == "health":
        return cmd_health(store, a.json)
    if a.cmd == "intake":
        return cmd_intake(store, a.dry_run)
    return cmd_status(store)


if __name__ == "__main__":
    sys.exit(main())
