"""pytest: strategies_export_bot.py against a local mock Strategies admin (classic-ASP-style HTML forms) and a mock R2.

description: login (+ emailed code via env or --code-file), Download Reports form walk per site x report x date
  window, header check against REAL_HEADERS (mismatch -> exit 3), manifest + sha256, skip done windows, resume
  after a crash (.part discarded), open-window supersede, HTML-instead-of-CSV re-login, short-body retry, profile
  time guard, --out refusal inside a git checkout / .tmp, unverified config refusal, --discover structure only,
  R2 upload with SigV4 checked by the mock, M1 reconciliation, and no secret or cell value in stdout/stderr/files.
inputs: deliverables/greenjobs_migration_2026-11-06/build/import/REAL_HEADERS_2026-11-19.json (names only);
  synthetic rows generated in memory. Everything runs on 127.0.0.1; nothing contacts Strategies or R2.
Run: python3 -m pytest -q tests/greenjobs_redesign/test_strategies_export_bot.py
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import sys
import threading
from datetime import date, datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO
    / "execution"
    / "gtm_client_workflows"
    / "greenjobs_redesign"
    / "strategies_export_bot.py"
)
REAL = json.loads(
    (
        REPO
        / "deliverables"
        / "greenjobs_migration_2026-11-06"
        / "build"
        / "import"
        / "REAL_HEADERS_2026-11-19.json"
    ).read_text(encoding="utf-8")
)["sites"]

spec = importlib.util.spec_from_file_location("strategies_export_bot_t", SCRIPT)
bot = importlib.util.module_from_spec(spec)
sys.modules["strategies_export_bot_t"] = bot
spec.loader.exec_module(bot)

USER, PW, CODE = "admin.user@greenjobs.example", "Pw-s3cret-!Zq9", "771204"
R2_AK, R2_SK = "AKIDTESTKEY0001", "r2-secret-key-NEVER-PRINT-55"
TOKEN = "TOKSECRET123"
SENT_EMAIL, SENT_NAME = "zebedee.quux@example.invalid", "Zebedee Quux"
SINCE, UNTIL = "2024-01-01", "2026-11-20"
EVENING = datetime(2026, 11, 20, 20, 0, tzinfo=timezone.utc)
NOON = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

LABELS = {  # what the admin's select might say; the config matches by prefix
    "recruiters": "Recruiters",
    "candidates": "Members registration details (all candidates)",
    "profiles": "Members profile data (only candidates with a profile)",
    "jobs": "Jobs (All jobs only)",
    "alerts": "Jobs By Email (no filtering possible)",
    "applications": "Job Applications",
}
SHEET = {
    "recruiters": "Recruiters",
    "candidates": "Members registration",
    "profiles": "Members profile",
    "jobs": "Jobs (All",
    "alerts": "Jobs By Email",
    "applications": "Job Applications",
}
DATE_COL = {
    "recruiters": "CreateDate",
    "candidates": "registerDate",
    "profiles": "dRegisterDate",
    "jobs": "CreateDate",
    "applications": "ApplicationDate",
}
DATES = [
    date(2024, 1, 15),
    date(2024, 6, 30),
    date(2024, 7, 1),
    date(2025, 2, 28),
    date(2025, 12, 31),
    date(2026, 3, 3),
    date(2026, 11, 10),
    date(2026, 11, 20),
]


def header(site: str, rep: str) -> list[str]:
    return next(h for k, h in REAL[site].items() if k.startswith(SHEET[rep]))


def dataset(
    site: str, rep: str, extra_old: bool
) -> list[tuple[date | None, list[str]]]:
    rows = []
    dates = DATES + ([date(2019, 5, 5)] if extra_old else [])
    n = {
        "recruiters": 3,
        "candidates": 2,
        "profiles": 2,
        "jobs": 3,
        "applications": 1,
        "alerts": 1,
    }[rep]
    for d in dates:
        for i in range(n):
            vals = []
            for col in header(site, rep):
                if col == DATE_COL.get(rep):
                    vals.append(d.strftime("%d/%m/%Y 10:00:00"))
                elif "mail" in col.lower():
                    vals.append(SENT_EMAIL)
                elif "name" in col.lower():
                    vals.append(SENT_NAME)
                elif col in ("JobDescription", "sSynopsis"):
                    vals.append(f'Line one, {SENT_NAME}\nline two "quoted"')
                else:
                    vals.append(f"v{i}")
            rows.append((d if rep in DATE_COL else None, vals))
    return rows


class MockState:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = 0
        self.downloads = 0
        self.sessions: dict[str, str] = {}
        self.pending_code: set[str] = set()
        self.code_required = False
        self.mismatch: tuple[str, str] | None = None
        self.expire_once = False
        self.short_once = False
        self.extra_old = False
        self.show_totals = True
        self.s3: dict[str, tuple[bytes, dict]] = {}
        self.s3_bad_sig = 0
        self._n = 0

    def new_session(self, site: str) -> str:
        with self.lock:
            self._n += 1
            sid = f"S{self._n}"
            self.sessions[sid] = site
            return sid


def login_page() -> str:
    return (
        "<html><body><h1>Admin login</h1><form method='post' action='login.asp'>"
        "<input type='text' name='username'><input type='password' name='password'>"
        "<input type='hidden' name='redir' value='home.asp'>"
        "<input type='submit' name='btnLogin' value='Log in'></form></body></html>"
    )


def reports_page(state: MockState, site: str) -> str:
    opts = "".join(f"<option value='{i + 1}'>{LABELS[r]}" for i, r in enumerate(LABELS))
    tot = ""
    if state.show_totals:
        tot = (
            "<p>"
            + " ".join(
                f"{LABELS[r].split(' (')[0]}: {len(dataset(site, r, state.extra_old))} records<br>"
                for r in LABELS
            )
            + "</p>"
        )
    return (
        "<html><body><h1>Download Reports</h1>"
        + tot
        + "<form method='post' action='download.asp' name='frmReports'>"
        f"<input type='hidden' name='tok' value='{TOKEN}'>"
        f"<select name='ReportType'><option value=''>-- choose --{opts}</select>"
        "<input type='text' name='DateFrom' value=''><input type='text' name='DateTo' value=''>"
        "<input type='checkbox' name='IncludeInactive' value='1' checked>"
        "<input type='submit' name='btnDownload' value='Download'></form>"
        f"<a href='home.asp'>Home</a> <a href='logout.asp'>Log out</a> <a href='cand.asp?id=9'>{SENT_NAME}</a>"
        "</body></html>"
    )


def make_handler(state: MockState):
    rep_by_value = {str(i + 1): r for i, r in enumerate(LABELS)}

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # keep pytest output clean
            pass

        def _send(
            self, code: int, body: bytes, ctype="text/html", headers=None, length=None
        ):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header(
                "Content-Length", str(len(body) if length is None else length)
            )
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            if length is not None:
                self.close_connection = True

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""

        def _sid(self) -> str | None:
            c = SimpleCookie(self.headers.get("Cookie", ""))
            return c["ASPSESSIONID"].value if "ASPSESSIONID" in c else None

        def do_HEAD(self):
            self._s3()

        def do_PUT(self):
            self._s3()

        def do_GET(self):
            if self.path.startswith("/s3/"):
                return self._s3()
            self._admin("GET")

        def do_POST(self):
            self._admin("POST")

        # ---- mock R2 (path-style S3), SigV4 recomputed with the same signer
        def _s3(self):
            body = self._body() if self.command == "PUT" else b""
            auth = self.headers.get("Authorization", "")
            m = re.search(r"SignedHeaders=([^,]+), Signature=(\w+)", auth)
            ok = bool(m) and R2_AK in auth
            if ok:
                names = m.group(1).split(";")
                hdrs = {
                    n: self.headers[n]
                    for n in names
                    if n not in ("host", "x-amz-date", "x-amz-content-sha256")
                }
                dt = datetime.strptime(
                    self.headers["x-amz-date"], "%Y%m%dT%H%M%SZ"
                ).replace(tzinfo=timezone.utc)
                sign = bot._load_sigv4()
                exp = sign(
                    self.command,
                    f"http://{self.headers['Host']}{self.path}",
                    hdrs,
                    body,
                    R2_AK,
                    R2_SK,
                    "auto",
                    "s3",
                    dt,
                )
                ok = exp["Authorization"] == auth
            if not ok:
                state.s3_bad_sig += 1
                return self._send(403, b"bad signature", "text/plain")
            key = self.path[len("/s3/") :]
            if self.command == "PUT":
                state.s3[key] = (
                    body,
                    {"x-amz-meta-sha256": self.headers.get("x-amz-meta-sha256", "")},
                )
                return self._send(200, b"")
            if key not in state.s3:
                return self._send(404, b"", "text/plain")
            data, meta = state.s3[key]
            self._send(200, data, "application/octet-stream", headers=meta, length=None)

        # ---- mock Strategies admin
        def _admin(self, method: str):
            with state.lock:
                state.requests += 1
            u = urlsplit(self.path)
            parts = u.path.strip("/").split("/")
            site, page = parts[0], parts[-1] if len(parts) > 2 else ""
            form = (
                dict(parse_qsl(self._body().decode()))
                if method == "POST"
                else dict(parse_qsl(u.query))
            )
            sid = self._sid()
            authed = sid in state.sessions and state.sessions[sid] == site
            if page == "login.asp" and method == "POST":
                if (
                    form.get("username") == USER
                    and form.get("password") == PW
                    and form.get("btnLogin")
                ):
                    sid = state.new_session("pending")
                    if state.code_required:
                        state.pending_code.add(sid)
                        body = (
                            "<html><body><p>We emailed you a code.</p><form method='post' action='code.asp'>"
                            "<input name='code'><input type='submit' value='Verify'></form></body></html>"
                        )
                    else:
                        state.sessions[sid] = site
                        body = home_page()
                    return self._send(
                        200,
                        body.encode(),
                        headers={"Set-Cookie": f"ASPSESSIONID={sid}; Path=/"},
                    )
                return self._send(200, (login_page() + "<p>Invalid login</p>").encode())
            if page == "code.asp" and method == "POST":
                if sid in state.pending_code and form.get("code") == CODE:
                    state.pending_code.discard(sid)
                    state.sessions[sid] = site
                    return self._send(200, home_page().encode())
                return self._send(200, b"<html><body>bad code</body></html>")
            if not authed:
                return self._send(200, login_page().encode())
            if page == "home.asp":
                return self._send(200, home_page().encode())
            if page == "reports.asp":
                return self._send(200, reports_page(state, site).encode())
            if page == "download.asp" and method == "POST":
                if state.expire_once:
                    state.expire_once = False
                    state.sessions.clear()
                    return self._send(200, login_page().encode())
                if (
                    form.get("tok") != TOKEN
                    or form.get("btnDownload") != "Download"
                    or form.get("IncludeInactive") != "1"
                ):
                    return self._send(400, b"<html>bad form</html>")
                rep = rep_by_value.get(form.get("ReportType", ""))
                if not rep:
                    return self._send(400, b"<html>choose a report</html>")
                head = header(site, rep)
                if state.mismatch == (site, rep):
                    head = [h for h in head if h != head[3]]
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(head)
                lo = (
                    datetime.strptime(form["DateFrom"], "%d/%m/%Y").date()
                    if form.get("DateFrom")
                    else None
                )
                hi = (
                    datetime.strptime(form["DateTo"], "%d/%m/%Y").date()
                    if form.get("DateTo")
                    else None
                )
                for d, vals in dataset(site, rep, state.extra_old):
                    if d is not None and lo and hi and not (lo <= d <= hi):
                        continue
                    w.writerow(vals[: len(head)])
                data = ("﻿" + buf.getvalue()).encode("utf-8")
                with state.lock:
                    state.downloads += 1
                if state.short_once:
                    state.short_once = False
                    return self._send(
                        200, data[: len(data) // 2], "text/csv", length=len(data)
                    )
                return self._send(
                    200,
                    data,
                    "text/csv",
                    headers={"Content-Disposition": f"attachment; filename={rep}.csv"},
                )
            self._send(404, b"<html>not found</html>")

    return H


def home_page() -> str:
    return (
        "<html><body><h1>Admin</h1><a href='reports.asp'>Download Reports</a> "
        "<a href='logout.asp'>Log out</a></body></html>"
    )


@pytest.fixture
def mock(tmp_path, monkeypatch):
    state = MockState()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    root = f"http://127.0.0.1:{srv.server_address[1]}"
    cfg = json.loads(
        (SCRIPT.parent / "strategies_export_config.json").read_text(encoding="utf-8")
    )
    cfg["verified"] = True
    cfg["sites"]["ie"]["base_url"] = f"{root}/ie"
    cfg["sites"]["uk"]["base_url"] = f"{root}/uk"
    for rep in cfg["reports"]:
        cfg["reports"][rep]["total_regex"] = (
            re.escape(LABELS[rep].split(" (")[0]) + r":\s*([\d,]+)\s+records"
        )
    cfgp = tmp_path / "config.json"
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    for s in ("IE", "UK"):
        monkeypatch.setenv(f"STRATEGIES_USER_{s}", USER)
        monkeypatch.setenv(f"STRATEGIES_PASS_{s}", PW)
        monkeypatch.delenv(f"STRATEGIES_CODE_{s}", raising=False)
    monkeypatch.setenv("R2_ENDPOINT", f"{root}/s3")
    monkeypatch.setenv("R2_BUCKET", "greenjobs-archive")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", R2_AK)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", R2_SK)
    state.root, state.cfgp, state.cfg = root, cfgp, cfg
    yield state
    srv.shutdown()


def run(state, out, *extra, clock=EVENING, live=True):
    argv = [
        "--config",
        str(state.cfgp),
        "--since",
        SINCE,
        "--until",
        UNTIL,
        "--months",
        "6",
        "--pace",
        "0",
    ]
    if out is not None:
        argv += ["--out", str(out)]
    if live:
        argv.append("--live")
    return bot.main(
        argv + [str(x) for x in extra], clock=lambda: clock, sleeper=lambda s: None
    )


def manifest(out: Path) -> dict:
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))


def assert_clean(text: str):
    for bad in (USER, PW, CODE, R2_SK, TOKEN, SENT_EMAIL, SENT_NAME, "quux", "Zebedee"):
        assert bad not in text, f"leaked {bad[:3]}..."


PER_SITE = 5 * 6 + 1  # 5 dated reports x 6 windows + Jobs By Email (one undated window)


# --------------------------------------------------------------------------- unit


def test_windows_contiguous_and_clamped():
    ws = bot.windows(date(2024, 1, 31), date(2024, 12, 15), 3)
    assert ws[0] == (date(2024, 1, 31), date(2024, 4, 29))
    assert ws[-1][1] == date(2024, 12, 15)
    for (a, b), (c, _) in zip(ws, ws[1:]):
        assert (c - b).days == 1 and a <= b
    assert bot.windows(date(2026, 11, 20), date(2026, 11, 20), 3) == [
        (date(2026, 11, 20), date(2026, 11, 20))
    ]
    with pytest.raises(bot.Refusal):
        bot.windows(date(2026, 1, 1), date(2025, 1, 1), 3)


def test_quiet_hours_guard():
    rc = {"quiet_hours_utc": [9, 17]}
    at = lambda h, m=0: datetime(2026, 11, 20, h, m, tzinfo=timezone.utc)
    assert (
        bot.quiet_ok(rc, at(8, 0), 15)
        and bot.quiet_ok(rc, at(17, 0), 15)
        and bot.quiet_ok(rc, at(23, 59), 15)
    )
    assert (
        not bot.quiet_ok(rc, at(8, 50), 15)
        and not bot.quiet_ok(rc, at(12), 15)
        and not bot.quiet_ok(rc, at(16, 59), 15)
    )
    assert bot.quiet_ok({}, at(12), 15)


def test_sigv4_matches_aws_documented_example():
    sign = bot._load_sigv4()
    h = sign(
        "GET",
        "https://examplebucket.s3.amazonaws.com/test.txt",
        {"range": "bytes=0-9"},
        b"",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "s3",
        datetime(2013, 5, 24, tzinfo=timezone.utc),
    )
    assert h["Authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


def test_header_check_names_only_expected_columns(tmp_path):
    exp = ["CandidatePK", "FullName", "email"]
    p = tmp_path / "x.csv"
    p.write_text(
        f"{SENT_NAME},{SENT_EMAIL}\n1,2\n", encoding="utf-8"
    )  # header row missing: first row is data
    with pytest.raises(bot.DataContractError) as e:
        bot.check_csv(p, exp)
    assert_clean(str(e.value))
    assert "CandidatePK" in str(e.value)
    p.write_text('CandidatePK,FullName,email\n1,"a,\nb",c\n\n2,x,y\n', encoding="utf-8")
    assert bot.check_csv(p, exp) == 2


@pytest.mark.parametrize("where", ["repo", "repo_tmp", "other_git", "dot_tmp"])
def test_refuses_out_inside_a_checkout_or_tmp(tmp_path, where, mock, capsys):
    if where == "repo":
        out = REPO / "deliverables" / "x_export"
    elif where == "repo_tmp":
        out = REPO / ".tmp" / "export"
    elif where == "other_git":
        (tmp_path / "clone" / ".git").mkdir(parents=True)
        out = tmp_path / "clone" / "data"
    else:
        out = tmp_path / ".tmp" / "export"
    assert run(mock, out) == 2
    assert "refused" in capsys.readouterr().out
    assert not out.exists() and mock.requests == 0


# --------------------------------------------------------------------------- flows against the mock admin


def test_dry_run_default_contacts_nothing(tmp_path, mock, capsys):
    assert run(mock, tmp_path / "gj", live=False) == 0
    o = capsys.readouterr().out
    assert (
        mock.requests == 0 and "dry run" in o and f"plan: {2 * PER_SITE} window(s)" in o
    )
    assert not (tmp_path / "gj").exists()


def test_unverified_config_refuses_live_download(tmp_path, mock, capsys):
    mock.cfg["verified"] = False
    mock.cfgp.write_text(json.dumps(mock.cfg), encoding="utf-8")
    assert run(mock, tmp_path / "gj") == 2
    assert "verified=false" in capsys.readouterr().out and mock.requests == 0


def test_full_run_manifest_reconcile_then_noop(tmp_path, mock, capsys):
    out = tmp_path / "gj"
    assert run(mock, out) == 0
    m = manifest(out)
    assert len(m["entries"]) == 2 * PER_SITE and mock.downloads == 2 * PER_SITE
    for k, e in m["entries"].items():
        f = out / e["file"]
        assert (
            f.is_file()
            and bot.sha256_file(f) == e["sha256"]
            and f.stat().st_size == e["bytes"]
        )
        assert set(e) >= {
            "site",
            "report",
            "window_start",
            "window_end",
            "rows",
            "sha256",
            "bytes",
            "downloaded_at",
        }
    for site in ("ie", "uk"):
        for rep in LABELS:
            got = sum(
                e["rows"]
                for e in m["entries"].values()
                if e["site"] == site and e["report"] == rep
            )
            assert got == len(dataset(site, rep, False)), (site, rep)
    rec = json.loads((out / "reconciliation.json").read_text(encoding="utf-8"))
    assert {r["status"] for r in rec["lines"]} == {"MATCH"}
    assert not list(out.rglob("*.part"))
    before = {p: p.stat().st_mtime_ns for p in out.rglob("*.csv")}
    capsys.readouterr()
    assert (
        run(mock, out) == 0
    )  # re-run: every window skipped, nothing downloaded, files untouched
    o = capsys.readouterr().out
    assert mock.downloads == 2 * PER_SITE and "skipped" in o
    assert before == {p: p.stat().st_mtime_ns for p in out.rglob("*.csv")}


def test_tampered_file_is_downloaded_again(tmp_path, mock):
    out = tmp_path / "gj"
    assert run(mock, out, "--sites", "ie", "--reports", "jobs") == 0
    e = next(iter(manifest(out)["entries"].values()))
    (out / e["file"]).write_text("truncated", encoding="utf-8")
    n = mock.downloads
    assert run(mock, out, "--sites", "ie", "--reports", "jobs") == 0
    assert mock.downloads == n + 1 and bot.sha256_file(out / e["file"]) == e["sha256"]


def test_header_mismatch_fails_loud(tmp_path, mock, capsys):
    mock.mismatch = ("uk", "jobs")
    out = tmp_path / "gj"
    assert run(mock, out, "--sites", "uk", "--reports", "jobs") == 3
    o = capsys.readouterr().out
    assert "header mismatch" in o and "JobTitle" in o
    assert_clean(o)
    assert manifest(out)["entries"] == {} if (out / "manifest.json").exists() else True
    assert not list(out.rglob("*.csv")) and not list(out.rglob("*.part"))


def test_resume_after_crash(tmp_path, mock, monkeypatch):
    out = tmp_path / "gj"
    real = bot.check_csv
    calls = {"n": 0}

    def crash(path, expected):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt(
                "power cut"
            )  # after the .part is written, before it is recorded
        return real(path, expected)

    monkeypatch.setattr(bot, "check_csv", crash)
    with pytest.raises(KeyboardInterrupt):
        run(mock, out, "--sites", "ie", "--reports", "recruiters")
    assert len(manifest(out)["entries"]) == 2 and len(list(out.rglob("*.part"))) == 1
    monkeypatch.setattr(bot, "check_csv", real)
    n = mock.downloads
    assert run(mock, out, "--sites", "ie", "--reports", "recruiters") == 0
    assert mock.downloads == n + 4  # windows 3..6 only; 1..2 skipped
    assert len(manifest(out)["entries"]) == 6 and not list(out.rglob("*.part"))


def test_open_window_superseded_next_day(tmp_path, mock):
    out = tmp_path / "gj"
    assert run(mock, out, "--sites", "ie") == 0
    n = mock.downloads
    argv = [
        "--config",
        str(mock.cfgp),
        "--since",
        SINCE,
        "--until",
        "2026-11-21",
        "--months",
        "6",
        "--pace",
        "0",
        "--out",
        str(out),
        "--live",
        "--sites",
        "ie",
    ]
    assert bot.main(argv, clock=lambda: EVENING, sleeper=lambda s: None) == 0
    assert (
        mock.downloads == n + 5
    )  # only each dated report's last (open) window; Jobs By Email unchanged
    sup = [e for e in manifest(out)["entries"].values() if e.get("superseded_by")]
    assert len(sup) == 5
    rec = json.loads((out / "reconciliation.json").read_text(encoding="utf-8"))
    assert {r["status"] for r in rec["lines"]} == {
        "MATCH"
    }  # superseded windows are not double counted


def test_profiles_time_guard(tmp_path, mock, capsys):
    out = tmp_path / "gj"
    assert run(mock, out, "--reports", "profiles", clock=NOON) == 2
    assert "outside 09:00-17:00 UTC" in capsys.readouterr().out and mock.downloads == 0
    assert (
        run(mock, out, "--sites", "ie", "--reports", "jobs,profiles", clock=NOON) == 4
    )
    o = capsys.readouterr().out
    ents = manifest(out)["entries"].values()
    assert "deferred" in o and {e["report"] for e in ents} == {"jobs"}
    early = datetime(2026, 11, 20, 8, 50, tzinfo=timezone.utc)
    assert (
        run(mock, out, "--sites", "ie", "--reports", "profiles", clock=early) == 2
    )  # 15 min margin
    assert (
        run(mock, out, "--sites", "ie", "--reports", "jobs,profiles") == 0
    )  # evening: completes
    assert {e["report"] for e in manifest(out)["entries"].values()} == {
        "jobs",
        "profiles",
    }


def test_html_instead_of_csv_relogs_once_and_short_body_retries(tmp_path, mock):
    mock.expire_once = True
    mock.short_once = True
    out = tmp_path / "gj"
    assert run(mock, out, "--sites", "ie", "--reports", "applications") == 0
    assert len(manifest(out)["entries"]) == 6


def test_login_code_from_env_and_from_code_file(tmp_path, mock, monkeypatch, capsys):
    mock.code_required = True
    out = tmp_path / "gj"
    assert (
        run(mock, out, "--sites", "ie", "--reports", "alerts") == 2
    )  # no code source: refuses, names the env var
    assert "STRATEGIES_CODE_IE" in capsys.readouterr().out
    monkeypatch.setenv("STRATEGIES_CODE_IE", CODE)
    assert run(mock, out, "--sites", "ie", "--reports", "alerts") == 0
    monkeypatch.delenv("STRATEGIES_CODE_IE")
    cf = tmp_path / "code.txt"
    cf.write_text(CODE + "\n", encoding="utf-8")
    assert (
        run(mock, out, "--sites", "uk", "--reports", "alerts", "--code-file", cf) == 0
    )
    assert not cf.exists()  # read once, then deleted
    assert_clean(capsys.readouterr().out)


def test_discover_saves_structure_only(tmp_path, mock, capsys):
    mock.cfg["verified"] = False
    mock.cfgp.write_text(json.dumps(mock.cfg), encoding="utf-8")
    out = tmp_path / "gj"
    assert run(mock, out, "--discover", "--sites", "ie") == 0
    d = json.loads((out / "discover_ie.json").read_text(encoding="utf-8"))
    form = d["reports_page"]["forms"][0]
    names = [f["name"] for f in form["fields"]]
    assert names[:4] == ["tok", "ReportType", "DateFrom", "DateTo"]
    labels = [o["label"] for o in form["fields"][1]["options"]]
    assert "Jobs By Email (no filtering possible)" in labels
    raw = (out / "discover_ie.json").read_text(encoding="utf-8")
    assert_clean(raw)
    assert "records" not in raw and mock.downloads == 0
    assert_clean(capsys.readouterr().out)


def test_r2_only_upload_signed_and_idempotent(tmp_path, mock, capsys):
    assert run(mock, None, "--r2", "--sites", "uk") == 0
    keys = set(mock.s3)
    assert mock.s3_bad_sig == 0
    assert "greenjobs-archive/strategies_export/manifest.json" in keys
    csvs = [k for k in keys if k.endswith(".csv")]
    assert len(csvs) == PER_SITE
    man = json.loads(mock.s3["greenjobs-archive/strategies_export/manifest.json"][0])
    e = man["entries"]["uk/jobs/2024-01-01_2024-06-30"]
    import hashlib

    assert (
        hashlib.sha256(
            mock.s3["greenjobs-archive/strategies_export/" + e["file"]][0]
        ).hexdigest()
        == e["sha256"]
    )
    n = mock.downloads
    assert run(mock, None, "--r2", "--sites", "uk") == 0
    assert mock.downloads == n
    assert_clean(capsys.readouterr().out)


def test_reconcile_flags_rows_outside_the_windows(tmp_path, mock, capsys):
    mock.extra_old = True  # a 2019 record the 2024+ windows never fetch; the admin total still counts it
    out = tmp_path / "gj"
    assert run(mock, out, "--sites", "ie", "--reports", "recruiters,alerts") == 4
    rec = {
        r["report"]: r
        for r in json.loads((out / "reconciliation.json").read_text(encoding="utf-8"))[
            "lines"
        ]
    }
    assert (
        rec["recruiters"]["status"] == "MISMATCH" and rec["recruiters"]["delta"] == -3
    )
    assert rec["alerts"]["status"] == "MATCH"
    totals = tmp_path / "totals.json"
    totals.write_text(json.dumps({"ie": {"recruiters": 24}}), encoding="utf-8")
    capsys.readouterr()
    argv = [
        "--config",
        str(mock.cfgp),
        "--since",
        SINCE,
        "--until",
        UNTIL,
        "--months",
        "6",
        "--out",
        str(out),
        "--sites",
        "ie",
        "--reports",
        "recruiters,alerts",
        "--reconcile",
        "--admin-totals",
        str(totals),
    ]
    assert (
        bot.main(argv, clock=lambda: EVENING) == 0
    )  # offline, operator-typed total wins
    assert "M1 ie/recruiters: 24 rows, admin 24, MATCH" in capsys.readouterr().out


def test_no_secret_or_cell_value_anywhere(tmp_path, mock, capsys, monkeypatch):
    mock.code_required = True
    mock.expire_once = True
    monkeypatch.setenv("STRATEGIES_CODE_IE", CODE)
    monkeypatch.setenv("STRATEGIES_CODE_UK", CODE)
    out = tmp_path / "gj"
    assert run(mock, out, "--r2") == 0
    mock.mismatch = ("ie", "profiles")
    (out / "manifest.json").unlink()
    run(mock, out, "--sites", "ie", "--reports", "profiles")
    cap = capsys.readouterr()
    assert_clean(cap.out + cap.err)
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in (".json", ".md"):
            assert_clean(p.read_text(encoding="utf-8"))
    for k, (body, _) in mock.s3.items():
        if k.endswith(".json"):
            assert_clean(body.decode())
