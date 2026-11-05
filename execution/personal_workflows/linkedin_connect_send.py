"""LinkedIn connection requests from a fixed script: one run per send day, one email table.

description: Send the day's LinkedIn connection requests (20/day, Mon Tue Thu Fri Sat) from a dedicated Chrome profile with Playwright, then email one HTML table.
inputs: CLI `run [--dry-run]`, `login`, `setup [--start]` (Windows: login once, register + optionally start the scheduled task); `--data-dir` (default env LINKEDIN_CONNECT_DIR or <repo>/data/linkedin_connect, holding master.csv / ledger.csv / aliases.csv from linkedin_connect_queue.py); env GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD, optional LINKEDIN_CONNECT_EMAIL_TO (default GMAIL_SMTP_USER).
outputs: ledger.csv / aliases.csv / queue_<date>.csv rows via linkedin_connect_queue.py; emailed_<date>.txt marker and send.log in the data dir; one Gmail SMTP email (or .tmp/linkedin_connect_<date>.eml on --dry-run).

Directive: directives/personal_workflows/linkedin_connect_send.md. No AI, no Drive, no cloud task:
one Windows scheduled task (PowerShell block in the directive) starts `run` once per send day; the queue
module owns master, ledger, plan, mark and the daily cap (Q.DAILY_CAP).

Exit codes: 0 ok (or silent no-op: rest day / today already emailed), 2 stopped early (LinkedIn
warning, not logged in, failure streak, visit/time limit, 0 sent while people remained), 3 config error
(no master, no Gmail credentials, playwright or Chrome missing, run crashed, email not delivered). Every
exit 3 after the Gmail check still emails a STOPPED subject; only missing Gmail credentials cannot.
A second `run` while another holds the queue lock exits 0 without sending.
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
import sys
import time
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
try:  # optional: a missing python-dotenv must not kill the run before it can email (the task runs unattended)
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import linkedin_connect_queue as Q  # noqa: E402  (sibling module: master, ledger, plan, mark)

DEFAULT_DATA_DIR = Path(os.environ.get("LINKEDIN_CONNECT_DIR") or REPO / "data" / "linkedin_connect")
EML_DIR = REPO / ".tmp"

# Operator order 2026-11-03: send Mon, Tue, Thu, Fri, Sat; rest Wed and Sun. The per-day cap (20,
# = 100/week, LinkedIn's observed free-account weekly limit) is Q.DAILY_CAP: one source of truth.
SEND_DAYS = (0, 1, 3, 4, 5)  # datetime.weekday(): Monday = 0
GAP_SECONDS = (45, 120)  # random pause between profiles
MAX_CONSECUTIVE_RETRIES = 3  # three retry outcomes in a row (no Connect / unconfirmed / page load failed) -> stop
VISIT_FACTOR = 2  # never visit more than 2 x cap profiles in one run
# Worst case per profile: 120 s gap + 45 s load + 10 s render + 10 s confirm ~ 3 min, x 40 = ~2 h.
# The budget stops a run before that so it ends well inside the task's 3 h ExecutionTimeLimit.
RUN_BUDGET_S = 110 * 60

NAV_TIMEOUT_MS = 45_000
RENDER_TIMEOUT_MS = 10_000
CONFIRM_TIMEOUT_MS = 10_000
POLL_MS = 250

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
TASK_NAME = "LinkedIn connect send"  # the one Windows scheduled task (`setup` registers it)
TASK_TIME = "10:00"
LOGIN_WAIT_S = 600  # `login` / `setup` wait this long for the operator to sign in, then give up
SMTP_ATTEMPTS, SMTP_RETRY_S = 3, 60

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

def is_send_day(day: dt.date) -> bool:
    return day.weekday() in SEND_DAYS


def room_left(sent_today: int, cap: int | None = None) -> int:
    return max(0, (Q.DAILY_CAP if cap is None else cap) - sent_today)


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


def deliver(subject: str, body_html: str, day: str, dry_run: bool) -> bool:
    """Send via Gmail SMTP (App Password; SMTP_ATTEMPTS tries, SMTP_RETRY_S apart), or write an .eml on --dry-run."""
    if dry_run:
        user, _, to = smtp_config() or ("dry-run@localhost", "", "dry-run@localhost")
        EML_DIR.mkdir(parents=True, exist_ok=True)
        path = EML_DIR / f"linkedin_connect_{day}.eml"
        path.write_bytes(build_message(subject, body_html, user, to).as_bytes())
        log.info("dry-run: email written to %s", path)
        return True
    cfg = smtp_config()
    if not cfg:
        log.error("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set; email not sent")
        return False
    user, pw, to = cfg
    for attempt in range(1, SMTP_ATTEMPTS + 1):
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(user, pw)
                smtp.send_message(build_message(subject, body_html, user, to))
            log.info("emailed %s: %s", to, subject)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            log.error("SMTP attempt %d/%d failed: %s", attempt, SMTP_ATTEMPTS, exc)
        if attempt < SMTP_ATTEMPTS:
            time.sleep(SMTP_RETRY_S)
    return False


# ----------------------------------------------------------------- page logic (takes a URL)

@dataclass
class Outcome:
    status: str | None = None  # ledger status to mark; None = mark nothing
    note: str = ""
    canonical: str | None = None
    stop: str | None = None  # set = end the day now
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
    """Checkpoint URL, or a warning inside a dialog / alert (never body text: a profile's own
    About section may say "security check" or "restricted")."""
    if CHECKPOINT_URL_RE.search(page.url):
        return "security check"
    overlays = page.get_by_role("dialog").or_(page.get_by_role("alertdialog")).or_(page.get_by_role("alert"))
    texts = []
    try:
        for i in range(min(overlays.count(), 10)):
            if overlays.nth(i).is_visible():
                texts.append(_text(overlays.nth(i)))
    except Exception as exc:  # overlay detached mid-check: nothing to read, the next poll re-checks; logged
        log.debug("overlay check failed: %s", exc)
    blob = "\n".join(texts)
    for rx, reason in STOP_PATTERNS:
        if rx.search(blob):
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
        return Outcome("retry", "page_load_failed")
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
        return Outcome("retry", "no_connect_button", canonical=canon)  # not terminal: try again another day
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
    cap = Q.DAILY_CAP
    max_visits = VISIT_FACTOR * cap
    t0 = time.monotonic()
    res = DayResult()
    start_sent = len(Q._sent_on(store.load_ledger(), day))
    seen: set[str] = set()
    retry_streak = 0
    while room_left(start_sent + res.sent_run + len(res.would_send)) > 0:
        queue = [r for r in plan_queue(store, day, cap - len(res.would_send)) if r["slug"] not in seen]
        if not queue:
            return res  # nobody left to try today
        for r in queue:
            if room_left(start_sent + res.sent_run + len(res.would_send)) == 0:
                return res
            if res.processed >= max_visits:
                res.stop = f"{max_visits} profiles visited, cap not reached"
                return res
            if time.monotonic() - t0 > RUN_BUDGET_S:
                res.stop = "time budget reached"
                return res
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
            retry_streak = retry_streak + 1 if out.status == "retry" else 0
            if retry_streak >= MAX_CONSECUTIVE_RETRIES:
                res.stop = f"{MAX_CONSECUTIVE_RETRIES} profiles in a row without Connect or confirmation"
                return res
    return res


def remaining_people(store: Q.Store, day: str) -> int:
    blocked = Q._blocked(store.load_ledger(), day)
    return sum(1 for r in store.load_master() if r["slug"] not in blocked)


# ----------------------------------------------------------------- browser

class ChromeUnavailable(RuntimeError):
    """Google Chrome is missing or would not start with the job's profile."""


def launch_context(pw, data_dir: Path):
    try:
        return pw.chromium.launch_persistent_context(
            user_data_dir=str(data_dir / "chrome_profile"), channel="chrome", headless=False, no_viewport=True,
            args=["--disable-blink-features=AutomationControlled"])
    except Exception as exc:  # re-raised with a clear message; cmd_run turns it into a STOPPED email
        raise ChromeUnavailable(
            f"Google Chrome could not start ({str(exc).splitlines()[0]}). Install Chrome, and close any "
            f"window still using {data_dir / 'chrome_profile'}.") from exc


@contextlib.contextmanager
def open_browser(data_dir: Path):
    """Yield one page of the persistent LinkedIn profile; closes the browser on exit."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = launch_context(pw, data_dir)
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


def cmd_run(data_dir: Path, dry_run: bool, today: dt.date | None = None) -> int:
    today = today or dt.date.today()  # local date, same as the queue module's ledger dates
    day = today.isoformat()
    if not is_send_day(today) or marker_path(data_dir, day).exists():
        return 0  # rest day, or today's email already went out: silent no-op
    _setup_logging(data_dir)
    store = Q.Store(data_dir)
    if not dry_run and not smtp_config():
        log.error("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set; refusing to send without a report path")
        return 3
    if not store.master.exists():
        log.error("no master.csv in %s (run linkedin_connect_queue.py consolidate first)", data_dir)
        return _config_stop(day, "no master list", dry_run)
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        log.error("playwright not installed: py -m pip install playwright")
        return _config_stop(day, "playwright not installed", dry_run)
    lock_age = Q._lock_age_min(store)
    if lock_age is not None and lock_age <= Q.LOCK_TTL_MIN:
        log.info("another run holds the lock; exiting without sending")
        return 0
    with contextlib.redirect_stdout(io.StringIO()):
        Q.cmd_lock(store, "acquire")
    try:
        return _run_locked(data_dir, store, day, dry_run)
    finally:
        with contextlib.redirect_stdout(io.StringIO()):
            Q.cmd_lock(store, "release")


def _config_stop(day: str, reason: str, dry_run: bool) -> int:
    """A setup problem found before the browser opens: email it (no marker, so a rerun after the fix
    still sends today) instead of exiting silently. Always exit 3."""
    deliver(build_subject(day, 0, reason), build_table_html([]), day, dry_run)
    return 3


def _run_locked(data_dir: Path, store: Q.Store, day: str, dry_run: bool) -> int:
    log.info("run %s%s: %d already sent today, cap %d", day, " (dry-run)" if dry_run else "",
             len(Q._sent_on(store.load_ledger(), day)), Q.DAILY_CAP)

    code, res = 0, DayResult()
    try:
        with open_browser(data_dir) as page:
            res = run_day(page, store, day, dry_run)
    except ChromeUnavailable as exc:
        log.error("%s", exc)
        res.stop, code = "Chrome not available", 3
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
    if not deliver(subject, build_table_html(rows), day, dry_run):
        return 3
    if not dry_run:
        marker_path(data_dir, day).write_text(subject + "\n", encoding="utf-8")
    return code


def _has_session(ctx) -> bool:
    return any(c.get("name") == "li_at" and c.get("value") for c in ctx.cookies("https://www.linkedin.com"))


def ensure_login(data_dir: Path, wait_s: int = LOGIN_WAIT_S) -> bool:
    """Open the job's Chrome profile; if it has no LinkedIn session, show the login page and wait (up to
    wait_s) until the operator has signed in, then close the window by itself. True = session present."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = launch_context(pw, data_dir)
        try:
            if _has_session(ctx):
                return True
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://www.linkedin.com/login", timeout=NAV_TIMEOUT_MS)
            print("Sign in to LinkedIn in the Chrome window that opened; it closes by itself once you are in.")
            deadline = time.monotonic() + wait_s
            while time.monotonic() < deadline:
                if _has_session(ctx) and "/login" not in page.url and "/checkpoint" not in page.url:
                    page.wait_for_timeout(3_000)  # let LinkedIn finish writing the session
                    return True
                page.wait_for_timeout(2_000)
            return False
        except Exception as exc:  # window closed by hand, Chrome crashed: report, never hang
            print(f"login window closed before sign-in finished ({type(exc).__name__})", file=sys.stderr)
            return False
        finally:
            with contextlib.suppress(Exception):
                ctx.close()


def cmd_login(data_dir: Path) -> int:
    try:
        ok = ensure_login(data_dir)
    except ChromeUnavailable as exc:
        print(exc, file=sys.stderr)
        return 3
    print(f"LinkedIn session {'saved' if ok else 'NOT saved'} in {data_dir / 'chrome_profile'}")
    return 0 if ok else 3


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"  # PowerShell single-quoted literal


def task_script(python_exe: str, script: Path, repo: Path, start: bool) -> str:
    """PowerShell that (re)registers the one scheduled task (idempotent: -Force) and optionally starts it."""
    action_args = f'"{script}" run'
    lines = [
        f"$a = New-ScheduledTaskAction -Execute {_ps_quote(python_exe)} -Argument {_ps_quote(action_args)}"
        f" -WorkingDirectory {_ps_quote(str(repo))}",
        f"$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Thursday,Friday,Saturday -At {TASK_TIME}",
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries"
        " -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)",
        '$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\\$env:USERNAME" -LogonType Interactive',
        f"Register-ScheduledTask -TaskName {_ps_quote(TASK_NAME)} -Action $a -Trigger $t -Settings $s -Principal $p"
        " -Force | Out-Null",
        f"Write-Output ('registered: ' + (Get-ScheduledTask -TaskName {_ps_quote(TASK_NAME)}).State)",
    ]
    if start:
        lines.append(f"Start-ScheduledTask -TaskName {_ps_quote(TASK_NAME)}; Write-Output 'started'")
    return "; ".join(lines)


def cmd_setup(data_dir: Path, start: bool) -> int:
    """One-time Windows setup: LinkedIn login (only if the profile has no session), register the task,
    optionally start it now. Re-runnable: an existing session and task are kept/replaced, never doubled."""
    import subprocess
    if os.name != "nt":
        print("setup registers a Windows scheduled task; run it on the Windows laptop", file=sys.stderr)
        return 3
    if not smtp_config():
        print("GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD missing from .env: the job could not email its report",
              file=sys.stderr)
        return 3
    if not Q.Store(data_dir).master.exists():
        print(f"no master.csv in {data_dir}", file=sys.stderr)
        return 3
    try:
        if not ensure_login(data_dir):
            print("No LinkedIn session yet: run this again and sign in within 10 minutes.", file=sys.stderr)
            return 3
    except ChromeUnavailable as exc:
        print(exc, file=sys.stderr)
        return 3
    print("LinkedIn session: ok")
    ps = task_script(sys.executable, Path(__file__).resolve(), REPO, start)
    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],  # noqa: S603,S607 fixed argv; values are constants + _ps_quote()d paths
                         capture_output=True, text=True, timeout=120)
    print(res.stdout.strip())
    if res.returncode != 0:
        print(res.stderr.strip(), file=sys.stderr)
        return 3
    print(f"Task '{TASK_NAME}' runs Mon Tue Thu Fri Sat at {TASK_TIME}; each run emails one table.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                    help=f"state dir shared with linkedin_connect_queue.py (default {DEFAULT_DATA_DIR})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="send today's batch and email the table (no-op on rest days)")
    r.add_argument("--dry-run", action="store_true", help="no Connect/Send clicks; email written to .tmp/*.eml")
    sub.add_parser("login", help="sign in to LinkedIn in the job's Chrome profile (window closes by itself)")
    st = sub.add_parser("setup", help="Windows, once: login if needed, register the scheduled task")
    st.add_argument("--start", action="store_true", help="also start the task now (today's run)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a.data_dir, a.dry_run)
    if a.cmd == "setup":
        return cmd_setup(a.data_dir, a.start)
    return cmd_login(a.data_dir)


if __name__ == "__main__":
    sys.exit(main())
