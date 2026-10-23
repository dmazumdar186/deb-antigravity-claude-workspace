#!/usr/bin/env python3
"""LinkedIn connection-request queue: consolidate CSVs, pick today's batch, keep a sent ledger.

The script never touches LinkedIn. It owns the deterministic half of the daily routine
(`directives/personal_workflows/linkedin_connect_daily.md`): a de-duplicated master list, a
hard daily cap, a per-person ledger, and the four-field report (name, company, position,
LinkedIn ID). The browser step is done by Cowork on the operator's own logged-in Chrome.

Subcommands
  consolidate --in a.csv b.csv [...]   merge CSVs into master.csv (idempotent, re-runnable)
  plan [--limit 25]                     write/print today's queue (re-prints if it already exists)
  mark SLUG --status sent|skipped|already_connected|pending|withdrawn [--note ..]
  report [--date YYYY-MM-DD] [--out f]  markdown report of what was sent that day
  status                                counts: master / sent / remaining / today

State lives in --data-dir (default .tmp/linkedin_connect, gitignored):
  master.csv   ledger.csv   queue_YYYY-MM-DD.csv   report_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from pathlib import Path

DAILY_CAP = 25
WEEKLY_SOFT_CAP = 100  # LinkedIn's own weekly ceiling is ~100; warn before we get near it
FIELDS = ("slug", "name", "company", "position", "linkedin_url", "source_file")
LEDGER_FIELDS = ("ts", "date", "slug", "name", "status", "note")
STATUSES = ("sent", "skipped", "already_connected", "pending", "withdrawn")
TERMINAL = set(STATUSES)  # any ledger entry means: never queue again

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
    m = _SLUG_RE.search(url.strip())
    if m:
        return m.group(1).strip().lower().rstrip("/")
    # bare slug typed into the column
    token = url.strip().strip("/").lower()
    if token and "/" not in token and " " not in token and "." not in token:
        return token
    return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


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
    added = skipped_nourl = dupes = 0
    for p in paths:
        path = Path(p)
        rows = read_csv(path)
        if not rows:
            print(f"[warn] {path}: empty", file=sys.stderr)
            continue
        headers = list(rows[0].keys())
        c_url, c_name = _find(headers, "linkedin_url"), _find(headers, "name")
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


def cmd_plan(store: Store, limit: int) -> int:
    limit = min(limit, DAILY_CAP)
    day = _today()
    ledger = store.load_ledger()
    master = store.load_master()
    if not master:
        print("master.csv is empty; run consolidate first", file=sys.stderr)
        return 2
    done = {r["slug"] for r in ledger}
    qp = store.queue_path(day)
    if qp.exists():
        queue = [r for r in read_csv(qp) if r["slug"] not in done]
        print(f"queue for {day} already exists; {len(queue)} still to do:")
        _print_rows(queue)
        return 0
    already = len(_sent_on(ledger, day))
    room = max(0, limit - already)
    week = _sent_last_7_days(ledger)
    if week + room > WEEKLY_SOFT_CAP:
        room = max(0, WEEKLY_SOFT_CAP - week)
        print(f"[warn] weekly soft cap: {week} sent in last 7 days, trimming today to {room}", file=sys.stderr)
    queue = [r for r in master if r["slug"] not in done][:room]
    write_csv(qp, queue, FIELDS)
    print(f"queue for {day}: {len(queue)} people ({len(master) - len(done) - len(queue)} remain after today)")
    _print_rows(queue)
    return 0


def cmd_mark(store: Store, slug: str, status: str, note: str) -> int:
    slug = slug_of(slug) or slug.lower()
    master = {r["slug"]: r for r in store.load_master()}
    if slug not in master:
        print(f"unknown slug {slug!r} (not in master.csv)", file=sys.stderr)
        return 2
    ledger = store.load_ledger()
    if any(r["slug"] == slug for r in ledger):
        print(f"{slug}: already in ledger, not marking again")
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
    print(f"master: {len(master)}  handled: {len(done)}  remaining: {len(master) - len(done)}")
    print(f"today sent: {len(_sent_on(ledger, _today()))}/{DAILY_CAP}  last 7 days: {_sent_last_7_days(ledger)}/{WEEKLY_SOFT_CAP}")
    print("by status: " + ", ".join(f"{k}={v}" for k, v in by.items()))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("LINKEDIN_CONNECT_DIR", ".tmp/linkedin_connect"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consolidate"); c.add_argument("--in", dest="inputs", nargs="+", required=True)
    p = sub.add_parser("plan"); p.add_argument("--limit", type=int, default=DAILY_CAP)
    m = sub.add_parser("mark"); m.add_argument("slug"); m.add_argument("--status", choices=STATUSES, required=True)
    m.add_argument("--note", default="")
    r = sub.add_parser("report"); r.add_argument("--date"); r.add_argument("--out")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    store = Store(Path(a.data_dir))
    if a.cmd == "consolidate":
        return cmd_consolidate(store, a.inputs)
    if a.cmd == "plan":
        return cmd_plan(store, a.limit)
    if a.cmd == "mark":
        return cmd_mark(store, a.slug, a.status, a.note)
    if a.cmd == "report":
        return cmd_report(store, a.date, a.out)
    return cmd_status(store)


if __name__ == "__main__":
    sys.exit(main())
