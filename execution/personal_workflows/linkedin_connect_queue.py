#!/usr/bin/env python3
"""LinkedIn connection-request queue: consolidate CSVs, pick today's batch, keep a sent ledger.

The script never touches LinkedIn. It owns the deterministic half of the daily routine
(`directives/personal_workflows/linkedin_connect_daily.md`): a de-duplicated master list, a
hard daily cap, a per-person ledger, and the four-field report (name, company, position,
LinkedIn ID). The browser step is done by Cowork on the operator's own logged-in Chrome.

Subcommands
  consolidate --in a.csv b.csv [...]   merge CSVs into master.csv (idempotent, re-runnable)
  plan [--limit 25]                     write/print today's queue (re-prints if it already exists)
  mark SLUG --status sent|skipped|already_connected|pending|withdrawn|retry [--note ..] [--canonical SLUG2]
                                        --canonical records the slug LinkedIn redirected to, as an alias
  report [--date YYYY-MM-DD] [--out f]  markdown report of what was sent that day
  status                                counts: master / sent / remaining / today

State lives in --data-dir (default .tmp/linkedin_connect, gitignored):
  master.csv   ledger.csv   aliases.csv   queue_YYYY-MM-DD.csv   report_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import unquote

DAILY_CAP = 25
WEEKLY_SOFT_CAP = 100  # LinkedIn's own weekly ceiling is ~100; warn before we get near it
FIELDS = ("slug", "name", "company", "position", "linkedin_url", "source_file")
LEDGER_FIELDS = ("ts", "date", "slug", "name", "status", "note")
STATUSES = ("sent", "skipped", "already_connected", "pending", "withdrawn", "retry")
# Any status but "retry" is terminal: never queue again. "retry" (unconfirmed click, page failed
# to load) keeps the person out of today's queue and eligible from tomorrow.
TERMINAL = frozenset(STATUSES) - {"retry"}
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.master = data_dir / "master.csv"
        self.ledger = data_dir / "ledger.csv"
        self.aliases = data_dir / "aliases.csv"

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
            return 2
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
    return 0


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
    week = _sent_last_7_days(ledger)
    if week + room > WEEKLY_SOFT_CAP:
        room = max(0, WEEKLY_SOFT_CAP - week)
        print(f"[warn] weekly soft cap: {week} sent in last 7 days, trimming today to {room}", file=sys.stderr)
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


def cmd_report(store: Store, day: str | None, out: str | None) -> int:
    day = day or _today()
    master = {r["slug"]: r for r in store.load_master()}
    sent = _sent_on(store.load_ledger(), day)
    lines = [f"# LinkedIn connection requests sent {day}", "", f"{len(sent)} request(s) sent.", "",
             "| # | Name | Company | Position | LinkedIn ID |", "|---|---|---|---|---|"]
    for i, r in enumerate(sent, 1):
        m = master.get(r["slug"], {})
        lines.append(f"| {i} | {m.get('name', r['name'])} | {m.get('company', '')} | "
                     f"{m.get('position', '')} | [{r['slug']}](https://www.linkedin.com/in/{r['slug']}/) |")
    text = "\n".join(lines) + "\n"
    path = Path(out) if out else store.dir / f"report_{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"[written {path}]", file=sys.stderr)
    return 0


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
    print(f"today sent: {len(_sent_on(ledger, _today()))}/{DAILY_CAP}  last 7 days: {_sent_last_7_days(ledger)}/{WEEKLY_SOFT_CAP}")
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
    return cmd_status(store)


if __name__ == "__main__":
    sys.exit(main())
