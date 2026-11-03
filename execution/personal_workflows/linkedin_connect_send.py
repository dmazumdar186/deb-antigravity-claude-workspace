"""LinkedIn connection requests from a fixed script: one run per send day, one email table.

description: Send the day's LinkedIn connection requests (20/day, Mon Tue Thu Fri Sat) from a dedicated Chrome profile with Playwright, then email one HTML table.
inputs: CLI `run [--dry-run] [--headless]`, `login`, `install`, `uninstall`; `--data-dir` (default env LINKEDIN_CONNECT_DIR or <repo>/data/linkedin_connect, holding master.csv / ledger.csv / aliases.csv from linkedin_connect_queue.py); env GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD, optional LINKEDIN_CONNECT_EMAIL_TO (default GMAIL_SMTP_USER).
outputs: ledger.csv / aliases.csv / queue_<date>.csv rows via linkedin_connect_queue.py; emailed_<date>.txt marker and send.log in the data dir; one Gmail SMTP email (or .tmp/linkedin_connect_<date>.eml on --dry-run); one Windows scheduled task on `install`.

Directive: directives/personal_workflows/linkedin_connect_send.md. No AI, no Drive, no cloud task:
the OS scheduler starts `run` once per send day; the queue module owns master, ledger, plan, mark.

Exit codes: 0 ok (or silent no-op: rest day / today already emailed), 2 stopped early (LinkedIn
warning, not logged in, page-load failures, 0 sent while people remained), 3 config error.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import html
import io
import logging
import os
import random
import re
import smtplib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkedin_connect_queue as Q  # noqa: E402  (sibling module: master, ledger, plan, mark)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = Path(os.environ.get("LINKEDIN_CONNECT_DIR") or REPO / "data" / "linkedin_connect")
TZ_NAME = "Europe/Paris"

# Operator order 2026-11-03: send Mon, Tue, Thu, Fri, Sat; rest Wed and Sun. 20 per send day
# (= 100/week, LinkedIn's observed weekly invitation limit on a free account).
SEND_DAYS = (0, 1, 3, 4, 5)  # datetime.weekday(): Monday = 0
DAILY_SEND_CAP = 20
RUN_AT = "10:00"  # local time of the Windows scheduled task
TASK_NAME = "LinkedIn connect send"
GAP_SECONDS = (45, 120)  # random pause between profiles
MAX_CONSECUTIVE_LOAD_FAILURES = 2
MAX_PASSES = 5  # re-plan after skips so skipped people are replaced, bounded

NAV_TIMEOUT_MS = 45_000
RENDER_TIMEOUT_MS = 10_000
CONFIRM_TIMEOUT_MS = 10_000
POLL_MS = 250

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

STOP_PATTERNS = (
    (re.compile(r"captcha", re.I), "captcha"),
    (re.compile(r"security check|security verification", re.I), "security check"),
    (re.compile(r"weekly invitation limit", re.I), "weekly invitation limit"),
    (re.compile(r"restricted your account|account (?:has been |is )?restricted", re.I), "account restricted"),
)
GONE_RE = re.compile(r"this page doesn[’']t exist|page not found|profile is not available", re.I)
EMAIL_REQUIRED_RE = re.compile(r"enter (?:their|the member[’']s) email", re.I)
FIRST_DEGREE_RE = re.compile(r"1st degree connection|·\s*1st\b", re.I)
LOGIN_URL_RE = re.compile(r"linkedin\.com/(?:login|authwall|uas/login|signup)", re.I)
CHECKPOINT_URL_RE = re.compile(r"linkedin\.com/checkpoint/", re.I)
RENDERED_TEXT_RE = re.compile("|".join([GONE_RE.pattern, r"^Sign in$", r"^Join now$"]
                             + [rx.pattern for rx, _ in STOP_PATTERNS]), re.I)

CONNECT_NAME = re.compile(r"^(?:Connect|Invite .+ to connect)$", re.I)
PENDING_NAME = re.compile(r"^Pending", re.I)
MORE_NAME = re.compile(r"^More(?: actions)?$", re.I)
SEND_NO_NOTE = re.compile(r"^Send without a note$", re.I)
SEND_PLAIN = re.compile(r"^Send(?: now| invitation)?$", re.I)

log = logging.getLogger("linkedin_connect_send")


# ----------------------------------------------------------------- calendar, cap, email (pure)

def paris_today() -> dt.date:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo(TZ_NAME)).date()
    except Exception as exc:  # no tz database (Windows without tzdata): local date is the honest fallback
        log.warning("time zone %s unavailable (%s); using the local date", TZ_NAME, exc)
        return dt.date.today()


def is_send_day(day: dt.date) -> bool:
    return day.weekday() in SEND_DAYS


def room_left(sent_today: int, cap: int | None = None) -> int:
    return max(0, (DAILY_SEND_CAP if cap is None else cap) - sent_today)


def marker_path(data_dir: Path, day: str) -> Path:
    return data_dir / f"emailed_{day}.txt"


def build_subject(day: str, n_sent: int, stop: str | None) -> str:
    s = f"LinkedIn connects {day} ({n_sent} sent)"
    return f"{s} — STOPPED: {stop}" if stop else s


def build_table_html(rows: list[dict]) -> str:
    """The whole email body: one table (#, First name, Name, Company, Position, LinkedIn ID)."""
    e = lambda v: html.escape(" ".join((v or "").split()), quote=True)  # noqa: E731
    td = 'style="border:1px solid #ccc;padding:4px 8px"'
    out = ['<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">',
           "<tr>" + "".join(f"<th {td}>{h}</th>" for h in
                            ("#", "First name", "Name", "Company", "Position", "LinkedIn ID")) + "</tr>"]
    for i, r in enumerate(rows, 1):
        name, slug = r.get("name", ""), r.get("slug", "")
        link = f'<a href="{e(f"https://www.linkedin.com/in/{slug}/")}">{e(slug)}</a>'
        cells = (str(i), e(Q._first_name(name)), e(name), e(r.get("company")), e(r.get("position")), link)
        out.append("<tr>" + "".join(f"<td {td}>{c}</td>" for c in cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out) + "\n"


def sent_rows(store: Q.Store, day: str) -> list[dict]:
    master = {r["slug"]: r for r in store.load_master()}
    return [master.get(r["slug"], {"slug": r["slug"], "name": r["name"]}) for r in Q._sent_on(store.load_ledger(), day)]


def build_message(subject: str, body_html: str, sender: str, to: str) -> MIMEText:
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    return msg


def smtp_config() -> tuple[str, str, str] | None:
    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    to = os.environ.get("LINKEDIN_CONNECT_EMAIL_TO", "").strip() or user
    return (user, pw, to) if user and pw else None


def deliver(subject: str, body_html: str, day: str, dry_run: bool, eml_dir: Path | None = None) -> bool:
    """Send via Gmail SMTP (App Password), or write an .eml on --dry-run."""
    if dry_run:
        user, _, to = smtp_config() or ("dry-run@localhost", "", "dry-run@localhost")
        out_dir = eml_dir or REPO / ".tmp"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"linkedin_connect_{day}.eml"
        path.write_bytes(build_message(subject, body_html, user, to).as_bytes())
        log.info("dry-run: email written to %s", path)
        return True
    cfg = smtp_config()
    if not cfg:
        log.error("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set; email not sent")
        return False
    user, pw, to = cfg
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.send_message(build_message(subject, body_html, user, to))
    except (smtplib.SMTPException, OSError) as exc:
        log.error("SMTP send failed: %s", exc)
        return False
    log.info("emailed %s: %s", to, subject)
    return True


# ----------------------------------------------------------------- page logic (takes a URL)

@dataclass
class Outcome:
    status: str | None = None  # ledger status to mark; None = mark nothing
    note: str = ""
    canonical: str | None = None
    stop: str | None = None  # set = end the day now
    load_failed: bool = False
    would_send: bool = False


def _first_visible(loc):
    try:
        for i in range(min(loc.count(), 10)):
            el = loc.nth(i)
            if el.is_visible():
                return el
    except Exception as exc:  # element detached mid-check (SPA re-render): treat as absent, logged
        log.debug("visibility check failed: %s", exc)
    return None


def _text(loc) -> str:
    try:
        return loc.inner_text(timeout=2_000)
    except Exception as exc:  # page navigating / element gone: no text is the safe reading, logged
        log.debug("inner_text failed: %s", exc)
        return ""


def detect_stop(page) -> str | None:
    if CHECKPOINT_URL_RE.search(page.url):
        return "security check"
    body = _text(page.locator("body"))
    for rx, reason in STOP_PATTERNS:
        if rx.search(body):
            return reason
    return None


def is_logged_out(page) -> bool:
    if LOGIN_URL_RE.search(page.url):
        return True
    sign_in = page.get_by_role("link", name=re.compile(r"^Sign in$", re.I)).or_(
        page.get_by_role("button", name=re.compile(r"^Sign in$", re.I)))
    join = page.get_by_role("link", name=re.compile(r"^Join now$", re.I)).or_(
        page.get_by_role("button", name=re.compile(r"^Join now$", re.I)))
    return _first_visible(sign_in) is not None and _first_visible(join) is not None


def top_card(page):
    """The profile's own header. Scoped so 'People also viewed' Connect buttons are never clicked."""
    main = page.locator("main").first
    if not main.count():
        return page.locator("body")
    sec = main.locator("section").first
    return sec if sec.count() else main


def canonical_slug(current_url: str, queued_slug: str) -> str | None:
    s = Q.slug_of(current_url) if "linkedin.com/in/" in (current_url or "").lower() else None
    return s if s and s != queued_slug else None


def _connect_in(scope):
    return _first_visible(scope.get_by_role("button", name=CONNECT_NAME).or_(
        scope.get_by_role("menuitem", name=CONNECT_NAME)))


def process_profile(page, url: str, slug: str, dry_run: bool = False) -> Outcome:
    """Open one profile, read its state, act once. Never adds a note."""
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as exc:  # timeout / net error: a retry for this person, counted toward the stop rule
        log.warning("%s: page load failed: %s", slug, str(exc).splitlines()[0])
        return Outcome("retry", "page_load_failed", load_failed=True)
    try:  # SPA: wait for the header to render a button, or for a 404 / wall / warning text
        page.locator("main button, main [role=button]").or_(page.get_by_text(RENDERED_TEXT_RE)).first.wait_for(
            state="visible", timeout=RENDER_TIMEOUT_MS)
    except Exception as exc:  # nothing rendered in time; the checks below classify what is there
        log.debug("%s: render wait ended: %s", slug, str(exc).splitlines()[0])

    if stop := detect_stop(page):
        return Outcome(stop=stop)
    if is_logged_out(page):
        return Outcome(stop="not logged in")
    if (resp is not None and resp.status == 404) or GONE_RE.search(_text(page.locator("body"))):
        return Outcome("skipped", "profile_gone")
    canon = canonical_slug(page.url, slug)
    card = top_card(page)

    if _first_visible(card.get_by_role("button", name=PENDING_NAME)):
        return Outcome("pending", canonical=canon)
    if FIRST_DEGREE_RE.search(_text(card)):
        return Outcome("already_connected", canonical=canon)

    connect = _connect_in(card)
    if connect is None:
        more = _first_visible(card.get_by_role("button", name=MORE_NAME))
        if more is not None:
            more.click()
            page.wait_for_timeout(600)
            connect = _connect_in(card) or _connect_in(page.get_by_role("menu"))
    if connect is None:
        page.keyboard.press("Escape")
        return Outcome("skipped", "no_connect_button", canonical=canon)
    if dry_run:
        log.info("%s: dry-run, would click %r", slug, connect.get_attribute("aria-label") or "Connect")
        page.keyboard.press("Escape")
        return Outcome(note="would_send", canonical=canon, would_send=True)
    connect.click()
    return _finish_invite(page, card, slug, canon)


def _finish_invite(page, card, slug: str, canon: str | None) -> Outcome:
    clicked_send = False
    deadline = time.monotonic() + CONFIRM_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        if stop := detect_stop(page):
            return Outcome(stop=stop)
        alert = page.get_by_role("alert").filter(has_text=re.compile(r"Invitation sent", re.I))
        if _first_visible(alert) or _first_visible(card.get_by_role("button", name=PENDING_NAME)):
            return Outcome("sent", canonical=canon)
        dlg = _first_visible(page.get_by_role("dialog"))
        if dlg is not None:
            if EMAIL_REQUIRED_RE.search(_text(dlg)):
                page.keyboard.press("Escape")
                return Outcome("skipped", "email_required", canonical=canon)
            if not clicked_send:
                btn = _first_visible(dlg.get_by_role("button", name=SEND_NO_NOTE)) or \
                    _first_visible(dlg.get_by_role("button", name=SEND_PLAIN))
                if btn is not None:
                    btn.click()
                    clicked_send = True
        page.wait_for_timeout(POLL_MS)
    log.warning("%s: no confirmation after the click", slug)
    return Outcome("retry", "unconfirmed", canonical=canon)


# ----------------------------------------------------------------- the day's loop

@dataclass
class DayResult:
    stop: str | None = None
    would_send: list[dict] = field(default_factory=list)
    sent_run: int = 0
    processed: int = 0


def _quiet(fn, *a):
    """Call a queue-module command, routing its stdout to the log."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    for line in buf.getvalue().splitlines():
        log.debug("queue: %s", line)
    return rc


def plan_queue(store: Q.Store, day: str, limit: int) -> list[dict]:
    """Q.cmd_plan subtracts today's sends itself; limit is the cap (minus dry-run would-sends)."""
    if limit < 1 or _quiet(Q.cmd_plan, store, limit, True) != 0:
        return []
    qp = store.queue_path(day)
    return Q.read_csv(qp) if qp.exists() else []


def run_day(page, store: Q.Store, day: str, dry_run: bool = False,
            sleep: Callable[[float], None] | None = None) -> DayResult:
    sleep = sleep or time.sleep
    Q._today = lambda: day  # ledger dates and the plan follow the Europe/Paris send day, same as the gating
    res = DayResult()
    start_sent = len(Q._sent_on(store.load_ledger(), day))
    seen: set[str] = set()
    fails = 0
    for _ in range(MAX_PASSES):
        done = res.sent_run + len(res.would_send)
        if room_left(start_sent + done) == 0:
            break
        queue = [r for r in plan_queue(store, day, DAILY_SEND_CAP - len(res.would_send)) if r["slug"] not in seen]
        if not queue:
            break
        for r in queue:
            if room_left(start_sent + res.sent_run + len(res.would_send)) == 0:
                break
            if res.processed:
                sleep(random.uniform(*GAP_SECONDS))
            seen.add(r["slug"])
            res.processed += 1
            out = process_profile(page, r["linkedin_url"], r["slug"], dry_run)
            what = f"STOP {out.stop}" if out.stop else " ".join(x for x in (out.status, out.note) if x)
            log.info("%s: %s%s", r["slug"], what, f" (redirected to {out.canonical})" if out.canonical else "")
            if out.stop:
                res.stop = out.stop
                return res
            if out.would_send:
                res.would_send.append(r)
            if out.status and not dry_run:
                _quiet(Q.cmd_mark, store, r["slug"], out.status, out.note, out.canonical)
                res.sent_run += out.status == "sent"
            fails = fails + 1 if out.load_failed else 0
            if fails >= MAX_CONSECUTIVE_LOAD_FAILURES:
                res.stop = "two page-load failures"
                return res
    return res


def remaining_people(store: Q.Store, day: str) -> int:
    blocked = Q._blocked(store.load_ledger(), day)
    return sum(1 for r in store.load_master() if r["slug"] not in blocked)


# ----------------------------------------------------------------- browser

def launch_context(pw, data_dir: Path, headless: bool = False):
    kw = dict(user_data_dir=str(data_dir / "chrome_profile"), headless=headless, no_viewport=True,
              args=["--disable-blink-features=AutomationControlled"])
    try:
        return pw.chromium.launch_persistent_context(channel="chrome", **kw)
    except Exception as exc:  # Google Chrome not installed: bundled Chromium works with the same profile dir
        log.warning("Chrome channel unavailable (%s); falling back to bundled Chromium", str(exc).splitlines()[0])
        return pw.chromium.launch_persistent_context(**kw)


@contextlib.contextmanager
def open_browser(data_dir: Path, headless: bool = False):
    """Yield one page of the persistent LinkedIn profile; closes the browser on exit."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = launch_context(pw, data_dir, headless)
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            ctx.close()


def _setup_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for h in list(log.handlers):  # one set of handlers per run, even when called twice in-process
        log.removeHandler(h)
        h.close()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.FileHandler(data_dir / "send.log", encoding="utf-8"), logging.StreamHandler(sys.stderr)):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def cmd_run(data_dir: Path, dry_run: bool, headless: bool, today: dt.date | None = None,
            eml_dir: Path | None = None) -> int:
    today = today or paris_today()
    day = today.isoformat()
    if not is_send_day(today) or marker_path(data_dir, day).exists():
        return 0  # rest day, or today's email already went out: silent no-op
    _setup_logging(data_dir)
    store = Q.Store(data_dir)
    if not store.master.exists():
        log.error("no master.csv in %s (run linkedin_connect_queue.py consolidate first)", data_dir)
        return 3
    if not dry_run and not smtp_config():
        log.error("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set; refusing to send without a report path")
        return 3
    log.info("run %s%s: %d already sent today, cap %d", day, " (dry-run)" if dry_run else "",
             len(Q._sent_on(store.load_ledger(), day)), DAILY_SEND_CAP)

    code, res = 0, DayResult()
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        log.error("playwright not installed: pip install playwright")
        return 3
    try:
        with open_browser(data_dir, headless) as page:
            res = run_day(page, store, day, dry_run)
    except Exception as exc:  # browser could not start or the run crashed: still email, loudly
        log.exception("run failed: %s", exc)
        res.stop, code = f"run failed ({type(exc).__name__})", 3

    rows = res.would_send if dry_run else sent_rows(store, day)
    stop = res.stop
    if not stop and not rows and remaining_people(store, day) > 0:
        stop = "0 sent while people remained"
    if stop and not code:
        code = 2
    subject = build_subject(day, len(rows), stop)
    log.info("subject: %s", subject)
    if not deliver(subject, build_table_html(rows), day, dry_run, eml_dir):
        return 3
    if not dry_run:
        marker_path(data_dir, day).write_text(subject + "\n", encoding="utf-8")
    return code


def cmd_login(data_dir: Path) -> int:
    from playwright.sync_api import sync_playwright
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with sync_playwright() as pw:
        ctx = launch_context(pw, data_dir)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/login", timeout=NAV_TIMEOUT_MS)
        print("Log in to LinkedIn in the opened window, then close the window.")
        try:
            ctx.wait_for_event("close", timeout=0)
        except KeyboardInterrupt:
            ctx.close()
    print(f"profile saved in {data_dir / 'chrome_profile'}")
    return 0


# ----------------------------------------------------------------- Windows Task Scheduler

def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build_install_ps(python: str, script: Path, data_dir: Path) -> str:
    days = ",".join(DAY_NAMES[d] for d in SEND_DAYS)
    arg = f'"{script}" --data-dir "{data_dir}" run'
    return "\n".join([
        f"$a = New-ScheduledTaskAction -Execute {_ps_quote(python)} -Argument {_ps_quote(arg)} "
        f"-WorkingDirectory {_ps_quote(str(REPO))}",
        f"$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek {days} -At {RUN_AT}",
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)",
        '$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\\$env:USERNAME" -LogonType Interactive',
        f"Register-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -Action $a -Trigger $t -Settings $s "
        "-Principal $p -Force | Out-Null",
        f"Get-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} | Select-Object TaskName,State | Format-List",
    ])


def _powershell(script: str) -> int:
    if os.name != "nt":
        print("install/uninstall need Windows (Task Scheduler)", file=sys.stderr)
        return 3
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"powershell failed: {exc}", file=sys.stderr)
        return 3
    print(p.stdout.strip())
    if p.returncode:
        print(p.stderr.strip(), file=sys.stderr)
        return 3
    return 0


def cmd_install(data_dir: Path) -> int:
    script = Path(__file__).resolve()
    rc = _powershell(build_install_ps(sys.executable, script, data_dir.resolve()))
    if rc == 0:
        days = ", ".join(DAY_NAMES[d][:3] for d in SEND_DAYS)
        print(f"registered task {TASK_NAME!r}: {days} at {RUN_AT} local, start when available, "
              f"only while you are logged on, one instance at a time\n"
              f"action: {sys.executable} \"{script}\" --data-dir \"{data_dir.resolve()}\" run")
    return rc


def cmd_uninstall() -> int:
    rc = _powershell(f"Unregister-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -Confirm:$false")
    if rc == 0:
        print(f"removed task {TASK_NAME!r}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                    help=f"state dir shared with linkedin_connect_queue.py (default {DEFAULT_DATA_DIR})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="send today's batch and email the table (no-op on rest days)")
    r.add_argument("--dry-run", action="store_true", help="no Connect/Send clicks; email written to .tmp/*.eml")
    r.add_argument("--headless", action="store_true", help="testing only; the scheduled run is headed")
    sub.add_parser("login", help="open the persistent profile on linkedin.com/login; close the window when done")
    sub.add_parser("install", help="register the Windows scheduled task")
    sub.add_parser("uninstall", help="remove the Windows scheduled task")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a.data_dir, a.dry_run, a.headless)
    if a.cmd == "login":
        return cmd_login(a.data_dir)
    if a.cmd == "install":
        return cmd_install(a.data_dir)
    return cmd_uninstall()


if __name__ == "__main__":
    sys.exit(main())
