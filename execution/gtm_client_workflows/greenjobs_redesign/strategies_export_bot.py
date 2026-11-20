"""Strategies admin "Download Reports" -> GreenJobs-owned storage, in date windows, with a manifest (promise P16).

description: Signs into the Strategies admin of greenjobs.ie / greenjobs.co.uk, walks date windows (default 3
  months) per report type from the earliest date to today, downloads each CSV, checks its header row against
  build/import/REAL_HEADERS_2026-11-19.json (fail loud on a mismatch), counts rows and records a manifest entry
  (site, report, window, rows, sha256, bytes, downloaded_at). Idempotent: a window in the manifest whose stored
  file still hashes the same is skipped; partial downloads (.part) are discarded and retried. "Members profile
  data" only runs outside 09:00-17:00 UTC. Writes a reconciliation report (rows vs the admin's own totals, M1).
  Dry run by default (offline plan, no network); --live contacts Strategies. --discover saves only the HTML
  structure of the Download Reports page (forms, field names, options), never data.
inputs: env STRATEGIES_USER_IE / STRATEGIES_PASS_IE / STRATEGIES_USER_UK / STRATEGIES_PASS_UK (never printed or
  stored); optional emailed login code from env STRATEGIES_CODE_IE / _UK, --code-file PATH (polled) or a hidden
  stdin prompt; R2 upload env R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_ENDPOINT or
  CLOUDFLARE_ACCOUNT_ID. CLI: --out DIR (outside any git checkout), --r2, --live, --discover, --sites, --reports,
  --months, --since, --until, --pace, --config, --admin-totals FILE, --reconcile.
outputs: CSVs + manifest.json + reconciliation.{json,md} under --out and/or R2 <prefix>/; discover_<site>.json
  under --out; stdout progress lines with counts only (no cell value, no secret). No other file is written.
exit codes: 0 ok / no-op, 2 usage or refusal, 3 data contract failure (header mismatch, not a CSV),
  4 incomplete (profiles deferred by the time window, admin total mismatch), 5 transport failure after retries.

Directive: directives/gtm_client_workflows/greenjobs_redesign.md ("Strategies export bot").
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urljoin, urlsplit

try:  # optional: cloud sessions have no .env and no secret ever lives in one for this script
    from dotenv import load_dotenv

    load_dotenv()
except (
    ImportError
):  # dotenv is a convenience; env vars set by the shell work without it
    pass

import requests

EXIT_OK, EXIT_USAGE, EXIT_DATA, EXIT_INCOMPLETE, EXIT_TRANSPORT = 0, 2, 3, 4, 5
HERE = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / ".git").exists():
            return p
    return HERE.parents[2]


REPO_ROOT = _find_repo_root()
DEFAULT_CONFIG = HERE / "strategies_export_config.json"
REAL_HEADERS = (
    REPO_ROOT
    / "deliverables"
    / "greenjobs_migration_2026-11-06"
    / "build"
    / "import"
    / "REAL_HEADERS_2026-11-19.json"
)
R2_MODULE = (
    REPO_ROOT
    / "execution"
    / "personal_workflows"
    / "prodcraft_medspa"
    / "preview"
    / "r2.py"
)
REPORTS = ("recruiters", "candidates", "profiles", "jobs", "applications", "alerts")
SITES = ("ie", "uk")
UA = "GreenJobs-export/1.0 (data export by the site owner)"
TRIES = 3
NAV_WORDS = re.compile(
    r"report|download|export|log ?out|log ?in|admin|home|search|member|candidate|recruiter|client|job|application|profile|email",
    re.I,
)
MAX_OPTIONS = 50


class Refusal(Exception):
    """Usage error or a guard refusing to run (exit 2)."""


class DataContractError(Exception):
    """The download is not the CSV we expect (exit 3)."""


class TransportError(Exception):
    """Network failure after retries (exit 5)."""


class NotCsv(Exception):
    """The server answered with HTML (usually an expired session)."""


# --------------------------------------------------------------------------- output (redacted, counts only)


class Out:
    """The only way this script prints. Every line passes through redact(): registered secrets never appear."""

    def __init__(self) -> None:
        self.secrets: set[str] = set()

    def secret(self, value: str) -> str:
        if value and len(value) >= 3:
            self.secrets.add(value)
        return value

    def redact(self, s: str) -> str:
        for v in sorted(self.secrets, key=len, reverse=True):
            s = s.replace(v, "[redacted]")
        return s

    def say(self, msg: str) -> None:
        print(self.redact(f"[export] {msg}"), flush=True)


# --------------------------------------------------------------------------- paths


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def check_out_dir(raw: str) -> Path:
    """--out must be GreenJobs storage: never inside a git checkout (this repo or any other), never a .tmp dir."""
    p = Path(raw).expanduser().resolve()
    if _within(p, REPO_ROOT.resolve()):
        raise Refusal(
            "refused: --out is inside the git checkout; exports hold personal data and go to GreenJobs storage outside the repo"
        )
    for q in [p, *p.parents]:
        if (q / ".git").exists():
            raise Refusal(
                "refused: --out is inside a git working tree; choose a directory outside any repository"
            )
    if ".tmp" in p.parts:
        raise Refusal("refused: --out may not be a .tmp scratch directory")
    if p.exists() and not p.is_dir():
        raise Refusal("refused: --out exists and is not a directory")
    return p


# --------------------------------------------------------------------------- config, headers, windows


def load_config(path: Path) -> dict:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refusal(f"config unreadable: {path.name}: {type(e).__name__}") from e
    for k in ("sites", "login", "reports_page", "fields", "reports"):
        if k not in cfg:
            raise Refusal(f"config missing key: {k}")
    return cfg


def load_expected_headers(path: Path = REAL_HEADERS) -> dict[str, dict[str, list[str]]]:
    """{site: {sheet name: [header, ...]}} from the client's real header rows."""
    return json.loads(path.read_text(encoding="utf-8"))["sites"]


def expected_header(headers: dict, site: str, sheet_prefix: str) -> list[str]:
    hits = [h for name, h in headers[site].items() if name.startswith(sheet_prefix)]
    if len(hits) != 1:
        raise Refusal(
            f"REAL_HEADERS: {len(hits)} sheets match {sheet_prefix!r} for {site}"
        )
    return hits[0]


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    last = [
        31,
        29 if (y % 4 == 0 and (y % 100 or y % 400 == 0)) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ][m - 1]
    return date(y, m, min(d.day, last))


def windows(since: date, until: date, months: int) -> list[tuple[date, date]]:
    """Contiguous inclusive windows [start, end] from since to until; the last one is clamped to until."""
    if months < 1 or months > 24:
        raise Refusal("--months must be 1..24")
    if since > until:
        raise Refusal("--since is after --until")
    out, k = [], 0
    while True:
        s = add_months(since, months * k)
        if s > until:
            break
        e = min(add_months(since, months * (k + 1)) - timedelta(days=1), until)
        out.append((s, e))
        k += 1
    return out


def window_key(site: str, report: str, w: tuple[date, date] | None) -> str:
    return f"{site}/{report}/{'all' if w is None else f'{w[0].isoformat()}_{w[1].isoformat()}'}"


def plan(
    cfg: dict,
    sites: list[str],
    reports: list[str],
    since: date,
    until: date,
    months: int,
) -> list[tuple[str, str, tuple[date, date] | None]]:
    items = []
    for site in sites:
        for rep in reports:
            if cfg["reports"][rep].get("dated", True):
                items += [(site, rep, w) for w in windows(since, until, months)]
            else:
                items.append((site, rep, None))
    return items


def quiet_ok(rep_cfg: dict, now: datetime, margin_min: int) -> bool:
    """True when this report may run now. quiet_hours_utc [9, 17] = refused from (09:00 - margin) to 17:00 UTC."""
    q = rep_cfg.get("quiet_hours_utc")
    if not q:
        return True
    now = now.astimezone(timezone.utc)
    start = now.replace(hour=q[0], minute=0, second=0, microsecond=0) - timedelta(
        minutes=margin_min
    )
    end = now.replace(hour=q[1], minute=0, second=0, microsecond=0)
    return not (start <= now < end)


# --------------------------------------------------------------------------- CSV checks


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def looks_html(head: bytes) -> bool:
    t = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return t.startswith(b"<") and (
        b"<html" in t[:2048]
        or b"<!doctype" in t[:64]
        or b"<form" in t[:4096]
        or b"<body" in t[:4096]
    )


def check_csv(path: Path, expected: list[str]) -> int:
    """Header row must equal `expected` (names, order). Returns data row count. Raises DataContractError.
    Error text names only EXPECTED headers that are missing, plus counts: never a value from the file.
    """
    text = decode(path.read_bytes())
    if not text.strip():
        raise DataContractError("empty body (no header row)")
    first = text.splitlines()[0]
    delim = (
        max([",", ";", "\t", "|"], key=first.count)
        if any(c in first for c in ",;\t|")
        else ","
    )
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    got = [h.strip() for h in next(reader)]
    if got != expected:
        missing = [h for h in expected if h not in got]
        extra = sum(1 for h in got if h not in expected)
        order = not missing and not extra
        raise DataContractError(
            "header mismatch: "
            + (f"missing {missing[:8]}" if missing else "")
            + (f" {extra} unexpected column(s)" if extra else "")
            + (" same names, different order or count" if order else "")
            + f" (expected {len(expected)} columns, got {len(got)})"
        )
    rows = 0
    for r in reader:
        if any(c.strip() for c in r):
            rows += 1
    return rows


# --------------------------------------------------------------------------- HTML forms


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self.links: list[dict] = []
        self.scripts = 0
        self.handlers = 0
        self.js_links = 0
        self._form: dict | None = None
        self._select: dict | None = None
        self._option: dict | None = None
        self._a: dict | None = None

    def _add(self, f: dict) -> None:
        if self._form is not None:
            self._form["fields"].append(f)

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if any(k.startswith("on") for k in a):
            self.handlers += 1
        if tag == "form":
            self._form = {
                "action": a.get("action", ""),
                "method": (a.get("method") or "get").lower(),
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "fields": [],
            }
            self.forms.append(self._form)
        elif tag == "input":
            self._add(
                {
                    "tag": "input",
                    "type": (a.get("type") or "text").lower(),
                    "name": a.get("name", ""),
                    "value": a.get("value", ""),
                    "checked": "checked" in a,
                }
            )
        elif tag == "textarea":
            self._add(
                {
                    "tag": "textarea",
                    "type": "textarea",
                    "name": a.get("name", ""),
                    "value": "",
                }
            )
        elif tag == "select":
            self._select = {
                "tag": "select",
                "type": "select",
                "name": a.get("name", ""),
                "options": [],
            }
            self._add(self._select)
        elif tag == "option" and self._select is not None:
            self._option = {
                "value": a.get("value") if "value" in a else None,
                "label": "",
                "selected": "selected" in a,
            }
            self._select["options"].append(self._option)
        elif tag == "a":
            self._a = {"href": a.get("href", ""), "text": ""}
            self.links.append(self._a)
            if self._a["href"].lower().startswith("javascript:"):
                self.js_links += 1
        elif tag == "script":
            self.scripts += 1

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "select":
            self._select, self._option = None, None
        elif tag == "option":
            self._option = None
        elif tag == "a":
            self._a = None

    def handle_data(self, data):
        if self._option is not None:
            self._option["label"] += data
        elif self._a is not None:
            self._a["text"] += data


def parse_page(html: str) -> PageParser:
    p = PageParser()
    p.feed(html)
    p.close()
    return p


def find_form(page: PageParser, has_field: str) -> dict:
    hits = [
        f
        for f in page.forms
        if any(x["name"].lower() == has_field.lower() for x in f["fields"])
    ]
    if not hits:
        raise DataContractError(
            f"no form with a field named {has_field!r} (run --discover and fix the config)"
        )
    return hits[0]


def option_value(form: dict, field_name: str, label_prefix: str) -> str:
    sel = [
        f
        for f in form["fields"]
        if f["tag"] == "select" and f["name"].lower() == field_name.lower()
    ]
    if not sel:
        raise DataContractError(f"no select named {field_name!r} in the report form")
    hits = [
        o
        for o in sel[0]["options"]
        if o["label"].strip().lower().startswith(label_prefix.lower())
    ]
    if len(hits) != 1:
        raise DataContractError(
            f"{len(hits)} options in {field_name!r} start with {label_prefix!r}; need exactly 1"
        )
    o = hits[0]
    return o["value"] if o["value"] is not None else o["label"].strip()


def form_payload(form: dict, overrides: dict[str, str]) -> list[tuple[str, str]]:
    data: list[tuple[str, str]] = []
    submit_done = False
    for f in form["fields"]:
        name = f["name"]
        if not name:
            continue
        t = f["type"]
        if f["tag"] == "select":
            opts = f["options"]
            chosen = [o for o in opts if o["selected"]] or opts[:1]
            if chosen:
                o = chosen[0]
                data.append(
                    (name, o["value"] if o["value"] is not None else o["label"].strip())
                )
        elif t in ("submit", "image"):
            if not submit_done:
                data.append((name, f["value"]))
                submit_done = True
        elif t in ("button", "reset", "file"):
            continue
        elif t in ("checkbox", "radio"):
            if f.get("checked"):
                data.append((name, f["value"] or "on"))
        else:
            data.append((name, f["value"]))
    lower = {k.lower(): k for k in overrides}
    out, seen = [], set()
    for k, v in data:
        if k.lower() in lower:
            if k.lower() in seen:
                continue
            seen.add(k.lower())
            out.append((k, overrides[lower[k.lower()]]))
        else:
            out.append((k, v))
    out += [(k, v) for k, v in overrides.items() if k.lower() not in seen]
    return out


def structure(page: PageParser) -> dict:
    """Forms, field names and option labels only: no field values, no page text, no hidden token values."""
    forms = []
    for f in page.forms:
        fields = []
        for x in f["fields"]:
            d = {"tag": x["tag"], "type": x["type"], "name": x["name"]}
            if x["tag"] == "select":
                if len(x["options"]) <= MAX_OPTIONS:
                    d["options"] = [
                        {"value": o["value"], "label": o["label"].strip()[:80]}
                        for o in x["options"]
                    ]
                else:
                    d["options_count"] = len(x["options"])
            elif x["type"] in ("submit", "radio", "checkbox"):
                d["value"] = x["value"][:40]
            fields.append(d)
        forms.append(
            {
                "action": urlsplit(f["action"]).path,
                "method": f["method"],
                "id": f["id"],
                "name": f["name"],
                "fields": fields,
            }
        )
    links, seen = [], set()
    for a in page.links:
        href = a["href"]
        if href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        path = urlsplit(href).path
        text = " ".join(a["text"].split())[:40]
        text = text if NAV_WORDS.search(text) else ""
        if (path, text) not in seen and path:
            seen.add((path, text))
            links.append({"path": path, "text": text})
    return {
        "forms": forms,
        "links": links[:200],
        "scripts": page.scripts,
        "event_handlers": page.handlers,
        "javascript_links": page.js_links,
        "needs_browser_hint": bool(page.js_links or (page.handlers and not page.forms)),
    }


# --------------------------------------------------------------------------- R2 (S3-compatible)


def _load_sigv4():
    spec = importlib.util.spec_from_file_location("greenjobs_r2_sigv4", R2_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.sigv4_sign


class R2:
    """Minimal S3 client for one bucket (path-style), signed with the workspace's SigV4 (prodcraft_medspa/preview/r2.py)."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        prefix: str,
        out: Out,
    ):
        self.endpoint, self.bucket, self.prefix = (
            endpoint.rstrip("/"),
            bucket,
            prefix.strip("/"),
        )
        self._ak, self._sk = out.secret(access_key), out.secret(secret_key)
        self._sign = _load_sigv4()

    @classmethod
    def from_env(cls, prefix: str, out: Out) -> "R2":
        need = ["R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]
        missing = [n for n in need if not os.environ.get(n)]
        ep = os.environ.get("R2_ENDPOINT") or (
            f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com"
            if os.environ.get("CLOUDFLARE_ACCOUNT_ID")
            else ""
        )
        if not ep:
            missing.append("R2_ENDPOINT or CLOUDFLARE_ACCOUNT_ID")
        if missing:
            raise Refusal(f"--r2 needs env: {', '.join(missing)}")
        return cls(
            ep,
            os.environ["R2_BUCKET"],
            os.environ["R2_ACCESS_KEY_ID"],
            os.environ["R2_SECRET_ACCESS_KEY"],
            prefix,
            out,
        )

    def key(self, rel: str) -> str:
        return f"{self.prefix}/{rel}" if self.prefix else rel

    def _call(
        self, method: str, rel: str, body: bytes = b"", headers: dict | None = None
    ) -> requests.Response:
        url = f"{self.endpoint}/{self.bucket}/{quote(self.key(rel), safe='/~')}"
        last = None
        for i in range(TRIES):
            try:
                signed = self._sign(
                    method, url, headers or {}, body, self._ak, self._sk, "auto", "s3"
                )
                r = requests.request(
                    method, url, headers=signed, data=body, timeout=120
                )
                if r.status_code >= 500 or r.status_code == 429:
                    last = f"HTTP {r.status_code}"
                    time.sleep(2**i)
                    continue
                return r
            except requests.RequestException as e:
                last = type(e).__name__
                time.sleep(2**i)
        raise TransportError(f"R2 {method} failed after {TRIES} tries: {last}")

    def put_file(
        self,
        rel: str,
        path: Path,
        sha: str,
        content_type: str = "text/csv; charset=utf-8",
    ) -> None:
        r = self._call(
            "PUT",
            rel,
            path.read_bytes(),
            {"content-type": content_type, "x-amz-meta-sha256": sha},
        )
        if r.status_code not in (200, 201):
            raise TransportError(f"R2 PUT HTTP {r.status_code}")

    def head_sha(self, rel: str) -> str | None:
        r = self._call("HEAD", rel)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise TransportError(f"R2 HEAD HTTP {r.status_code}")
        return r.headers.get("x-amz-meta-sha256")

    def get_json(self, rel: str) -> dict | None:
        r = self._call("GET", rel)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise TransportError(f"R2 GET HTTP {r.status_code}")
        return r.json()

    def put_json(self, rel: str, obj: dict) -> None:
        body = json.dumps(obj, indent=1, sort_keys=True).encode("utf-8")
        r = self._call("PUT", rel, body, {"content-type": "application/json"})
        if r.status_code not in (200, 201):
            raise TransportError(f"R2 PUT HTTP {r.status_code}")


# --------------------------------------------------------------------------- manifest


@dataclass
class Store:
    """Where exports land: a local dir (--out) and/or R2. The manifest lives beside the CSVs."""

    out_dir: Path | None
    r2: R2 | None
    manifest: dict = field(
        default_factory=lambda: {"version": 1, "entries": {}, "admin_totals": {}}
    )

    def load(self) -> None:
        m = None
        if self.out_dir and (self.out_dir / "manifest.json").is_file():
            m = json.loads((self.out_dir / "manifest.json").read_text(encoding="utf-8"))
        elif self.r2 and not self.out_dir:
            m = self.r2.get_json("manifest.json")
        if m:
            m.setdefault("entries", {})
            m.setdefault("admin_totals", {})
            self.manifest = m

    def save(self) -> None:
        if self.out_dir:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.out_dir / "manifest.json.tmp"
            tmp.write_text(
                json.dumps(self.manifest, indent=1, sort_keys=True), encoding="utf-8"
            )
            os.replace(tmp, self.out_dir / "manifest.json")
        if self.r2:
            self.r2.put_json("manifest.json", self.manifest)

    def is_done(self, key: str) -> bool:
        e = self.manifest["entries"].get(key)
        if not e:
            return False
        if self.out_dir:
            p = self.out_dir / e["file"]
            if not p.is_file() or sha256_file(p) != e["sha256"]:
                return False
        if self.r2 and self.r2.head_sha(e["file"]) != e["sha256"]:
            return False
        return True

    def record(self, key: str, entry: dict) -> None:
        ents = self.manifest["entries"]
        for (
            k,
            e,
        ) in (
            ents.items()
        ):  # an earlier open window with the same start is superseded by this one
            if (
                k != key
                and e["site"] == entry["site"]
                and e["report"] == entry["report"]
                and e["window_start"] == entry["window_start"]
                and not e.get("superseded_by")
            ):
                e["superseded_by"] = key
        ents[key] = entry
        self.save()


# --------------------------------------------------------------------------- the admin session


class Admin:
    def __init__(
        self,
        site: str,
        cfg: dict,
        out: Out,
        pace: float,
        sleeper: Callable[[float], None],
        code_file: Path | None,
        code_wait_s: int,
    ):
        self.site, self.cfg, self.out, self.pace, self.sleep = (
            site,
            cfg,
            out,
            pace,
            sleeper,
        )
        sc = cfg["sites"][site]
        self.base = sc["base_url"].rstrip("/") + "/"
        self.timeout = cfg.get("timeout_s", 180)
        self.code_file, self.code_wait_s = code_file, code_wait_s
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        user, pw = os.environ.get(sc["user_env"], ""), os.environ.get(
            sc["pass_env"], ""
        )
        if not user or not pw:
            raise Refusal(f"missing env {sc['user_env']} / {sc['pass_env']}")
        self._user, self._pw = out.secret(user), out.secret(pw)
        self.code_env = sc.get("code_env", "")
        self.page_url, self.page_html, self.landing_url = "", "", ""

    def url(self, path: str) -> str:
        return urljoin(self.base, path.lstrip("/"))

    def req(self, method: str, url: str, **kw) -> requests.Response:
        last = None
        for i in range(TRIES):
            self.sleep(self.pace)
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                    ra = r.headers.get("Retry-After", "")
                    self.sleep(min(int(ra), 60) if ra.isdigit() else self.pace * (2**i))
                    continue
                return r
            except requests.RequestException as e:
                last = type(e).__name__
                self.sleep(self.pace * (2**i))
        raise TransportError(
            f"{self.site}: {method} {urlsplit(url).path} failed after {TRIES} tries: {last}"
        )

    def submit(
        self, page_url: str, form: dict, overrides: dict[str, str], stream: bool = False
    ) -> requests.Response:
        action = urljoin(page_url, form["action"] or page_url)
        data = form_payload(form, overrides)
        if form["method"] == "post":
            return self.req(
                "POST", action, data=data, stream=stream, allow_redirects=True
            )
        return self.req("GET", action, params=data, stream=stream, allow_redirects=True)

    def _read_code(self) -> str:
        code = os.environ.get(self.code_env, "") if self.code_env else ""
        if code:
            return code
        if self.code_file:
            self.out.say(
                f"{self.site}: login code requested; waiting up to {self.code_wait_s}s for {self.code_file.name}"
            )
            deadline = time.monotonic() + self.code_wait_s
            while time.monotonic() < deadline:
                if self.code_file.is_file():
                    code = self.code_file.read_text(encoding="utf-8").strip()
                    self.code_file.unlink()
                    if code:
                        return code
                self.sleep(5)
        if sys.stdin and sys.stdin.isatty():
            return getpass.getpass(
                f"{self.site}: login code from the email (hidden): "
            ).strip()
        raise Refusal(
            f"{self.site}: the admin asked for an emailed login code; set {self.code_env or 'the code env'} or pass --code-file"
        )

    def login(self) -> str:
        lc = self.cfg["login"]
        url = self.url(lc["path"])
        r = self.req("GET", url)
        form = find_form(parse_page(r.text), lc["form_has_field"])
        r = self.submit(
            r.url, form, {lc["user_field"]: self._user, lc["pass_field"]: self._pw}
        )
        page = parse_page(r.text)
        code_field = lc.get("code_form_has_field")
        if code_field and any(
            any(x["name"].lower() == code_field.lower() for x in f["fields"])
            for f in page.forms
        ):
            code = self.out.secret(self._read_code())
            r = self.submit(
                r.url, find_form(page, code_field), {lc["code_field"]: code}
            )
        if lc["ok_marker"].lower() not in r.text.lower():
            raise Refusal(
                f"{self.site}: login did not reach the admin (marker {lc['ok_marker']!r} absent); check the credentials or the config"
            )
        self.landing_url = r.url
        self.out.say(f"{self.site}: logged in")
        return r.text

    def reports_page(self, landing_html: str | None = None) -> tuple[str, str]:
        rp = self.cfg["reports_page"]
        url = self.url(rp["path"])
        if landing_html and rp.get("link_text"):
            for a in parse_page(landing_html).links:
                if rp["link_text"].lower() in " ".join(
                    a["text"].split()
                ).lower() and not a["href"].lower().startswith("javascript:"):
                    url = urljoin(self.landing_url or self.base, a["href"])
                    break
        r = self.req("GET", url)
        self.page_url, self.page_html = r.url, r.text
        return r.url, r.text


# --------------------------------------------------------------------------- run


@dataclass
class Ctx:
    cfg: dict
    out: Out
    store: Store
    headers: dict
    clock: Callable[[], datetime]
    margin_min: int
    staging: Path


def admin_totals_from(html: str, cfg: dict, site: str) -> dict[str, int]:
    found = {}
    text = re.sub(r"<[^>]+>", " ", html)
    for rep, rc in cfg["reports"].items():
        rx = rc.get("total_regex")
        if rx:
            m = re.search(rx, text, re.I)
            if m:
                found[rep] = int(m.group(1).replace(",", ""))
    return found


def fetch_to(admin: Admin, part: Path, form: dict, ov: dict[str, str], key: str) -> tuple[str, int]:
    """Stream one download into `part`. Retries transport errors and short bodies; raises NotCsv on HTML."""
    for attempt in range(TRIES):
        try:
            r = admin.submit(admin.page_url, form, ov, stream=True)
            if r.status_code != 200:
                raise DataContractError(f"{key}: HTTP {r.status_code} for the download")
            if "text/html" in r.headers.get("content-type", "").lower():
                raise NotCsv()
            h, n, first = hashlib.sha256(), 0, True
            with part.open("wb") as fh:
                for chunk in r.iter_content(1 << 16):
                    if first and looks_html(chunk[:4096]):
                        raise NotCsv()
                    first = False
                    fh.write(chunk)
                    h.update(chunk)
                    n += len(chunk)
            cl = r.headers.get("content-length", "")
            if cl.isdigit() and int(cl) != n:
                raise requests.exceptions.ChunkedEncodingError("short body")
            return h.hexdigest(), n
        except requests.RequestException as e:
            part.unlink(missing_ok=True)
            if attempt == TRIES - 1:
                raise TransportError(f"{key}: download failed after {TRIES} tries: {type(e).__name__}") from e
            admin.sleep(admin.pace * (2**attempt))
        except NotCsv:
            part.unlink(missing_ok=True)
            raise
    raise TransportError(f"{key}: download failed")  # unreachable: the loop returns or raises


def download_one(ctx: Ctx, admin: Admin, site: str, rep: str, w: tuple[date, date] | None) -> dict:
    cfg, rc, fields = ctx.cfg, ctx.cfg["reports"][rep], ctx.cfg["fields"]
    key = window_key(site, rep, w)
    rel = key + ".csv"
    part = ctx.staging / (rel + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    part.unlink(missing_ok=True)  # a partial file from a crashed run is never trusted
    fmt = cfg.get("date_format", "%d/%m/%Y")
    for relogged in (False, True):
        form = find_form(parse_page(admin.page_html), cfg["reports_page"]["form_has_field"])
        ov = {fields["type"]: option_value(form, fields["type"], rc["option_label"])}
        if w is not None:
            ov[fields["from"]], ov[fields["to"]] = w[0].strftime(fmt), w[1].strftime(fmt)
        try:
            sha, n = fetch_to(admin, part, form, ov, key)
            break
        except NotCsv:
            if relogged:
                raise DataContractError(f"{key}: the server returned HTML, not a CSV, after a fresh login") from None
            ctx.out.say(f"{key}: got HTML instead of CSV; logging in again once")
            admin.reports_page(admin.login())
    try:
        rows = check_csv(part, expected_header(ctx.headers, site, rc["header_sheet"]))
    except DataContractError as e:
        part.unlink(missing_ok=True)
        raise DataContractError(f"{key}: {e}") from None
    entry = {
        "site": site,
        "report": rep,
        "window_start": w[0].isoformat() if w else None,
        "window_end": w[1].isoformat() if w else None,
        "rows": rows,
        "sha256": sha,
        "bytes": n,
        "downloaded_at": ctx.clock().astimezone(timezone.utc).isoformat(timespec="seconds"),
        "file": rel,
    }
    if ctx.store.r2:
        ctx.store.r2.put_file(rel, part, sha)
    if ctx.store.out_dir:
        final = ctx.store.out_dir / rel
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(part, final)
    else:
        part.unlink(missing_ok=True)
    ctx.store.record(key, entry)
    return entry


def run_live(
    ctx: Ctx, admin_factory: Callable[[str], Admin], items: list, sites: list[str]
) -> int:
    deferred = 0
    for site in sites:
        todo = [
            it
            for it in items
            if it[0] == site and not ctx.store.is_done(window_key(*it))
        ]
        skipped = sum(1 for it in items if it[0] == site) - len(todo)
        if skipped:
            ctx.out.say(
                f"{site}: {skipped} window(s) already in the manifest with a matching hash: skipped"
            )
        if not todo:
            continue
        admin = admin_factory(site)
        admin.reports_page(admin.login())
        tot = admin_totals_from(admin.page_html, ctx.cfg, site)
        if tot:
            ctx.store.manifest["admin_totals"].setdefault(site, {}).update(tot)
            ctx.store.save()
        for _, rep, w in todo:
            if not quiet_ok(ctx.cfg["reports"][rep], ctx.clock(), ctx.margin_min):
                deferred += 1
                continue
            e = download_one(ctx, admin, site, rep, w)
            ctx.out.say(
                f"{window_key(site, rep, w)}: {e['rows']} rows, {e['bytes']} bytes, sha256 {e['sha256'][:12]}"
            )
    if deferred:
        ctx.out.say(
            f"INCOMPLETE: {deferred} profile window(s) deferred: 'Members profile data' runs only outside "
            f"09:00-17:00 UTC; run again after 17:00 UTC"
        )
    return deferred


def reconcile(
    ctx: Ctx, items: list, sites: list[str], reports: list[str], manual: dict
) -> tuple[dict, bool]:
    ents = ctx.store.manifest["entries"]
    live_tot = ctx.store.manifest.get("admin_totals", {})
    rows_out, bad = [], False
    for site in sites:
        for rep in reports:
            planned = {
                window_key(*it) for it in items if it[0] == site and it[1] == rep
            }
            active = [
                e
                for k, e in ents.items()
                if e["site"] == site
                and e["report"] == rep
                and not e.get("superseded_by")
            ]
            done = sum(1 for k in planned if k in ents)
            total = sum(e["rows"] for e in active)
            admin_total = manual.get(site, {}).get(rep, live_tot.get(site, {}).get(rep))
            if done < len(planned):
                status = "INCOMPLETE"
            elif admin_total is None:
                status = "NO_ADMIN_TOTAL"
            elif int(admin_total) == total:
                status = "MATCH"
            else:
                status = "MISMATCH"
            bad |= status in ("INCOMPLETE", "MISMATCH")
            rows_out.append(
                {
                    "site": site,
                    "report": rep,
                    "windows_planned": len(planned),
                    "windows_done": done,
                    "rows": total,
                    "bytes": sum(e["bytes"] for e in active),
                    "admin_total": admin_total,
                    "delta": None if admin_total is None else total - int(admin_total),
                    "status": status,
                }
            )
    rep_obj = {
        "generated_at": ctx.clock()
        .astimezone(timezone.utc)
        .isoformat(timespec="seconds"),
        "metric": "M1",
        "lines": rows_out,
    }
    md = [
        "# Strategies export reconciliation (M1)",
        "",
        f"Generated {rep_obj['generated_at']}. Rows downloaded vs the "
        "admin's own totals (where the admin shows them or the operator entered them).",
        "",
        "| Site | Report | Windows | Rows | Admin total | Delta | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows_out:
        md.append(
            f"| {r['site']} | {r['report']} | {r['windows_done']}/{r['windows_planned']} | {r['rows']} | "
            f"{'' if r['admin_total'] is None else r['admin_total']} | {'' if r['delta'] is None else r['delta']} | {r['status']} |"
        )
    if ctx.store.out_dir:
        ctx.store.out_dir.mkdir(parents=True, exist_ok=True)
        (ctx.store.out_dir / "reconciliation.json").write_text(
            json.dumps(rep_obj, indent=1), encoding="utf-8"
        )
        (ctx.store.out_dir / "reconciliation.md").write_text(
            "\n".join(md) + "\n", encoding="utf-8"
        )
    if ctx.store.r2:
        ctx.store.r2.put_json("reconciliation.json", rep_obj)
    for r in rows_out:
        ctx.out.say(
            f"M1 {r['site']}/{r['report']}: {r['rows']} rows, admin {r['admin_total']}, {r['status']}"
        )
    return rep_obj, bad


def discover(ctx: Ctx, admin: Admin) -> Path:
    landing = admin.login()
    url, html = admin.reports_page(landing)
    obj = {
        "site": admin.site,
        "landing": structure(parse_page(landing)),
        "reports_page_path": urlsplit(url).path,
        "reports_page": structure(parse_page(html)),
        "note": "Structure only: forms, field names, option labels, nav link paths. No values, no page text.",
    }
    p = ctx.store.out_dir / f"discover_{admin.site}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    f = obj["reports_page"]
    ctx.out.say(
        f"{admin.site}: discover saved {p.name}: {len(f['forms'])} form(s), "
        f"{sum(len(x['fields']) for x in f['forms'])} field(s), browser needed: {f['needs_browser_hint']}"
    )
    return p


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Strategies Download Reports -> GreenJobs storage (dry run by default)"
    )
    ap.add_argument(
        "--live",
        action="store_true",
        help="contact Strategies (default: offline plan only)",
    )
    ap.add_argument(
        "--discover",
        action="store_true",
        help="with --live: save the Download Reports page structure and stop",
    )
    ap.add_argument(
        "--reconcile",
        action="store_true",
        help="offline: rebuild the reconciliation report from the manifest",
    )
    ap.add_argument(
        "--out", help="local destination directory, outside any git checkout"
    )
    ap.add_argument(
        "--r2",
        action="store_true",
        help="also upload to R2 (env R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT|CLOUDFLARE_ACCOUNT_ID)",
    )
    ap.add_argument("--r2-prefix", default="strategies_export")
    ap.add_argument("--sites", default="ie,uk")
    ap.add_argument("--reports", default=",".join(REPORTS))
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--since", help="YYYY-MM-DD (default: config earliest)")
    ap.add_argument("--until", help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--pace", type=float, default=3.0, help="seconds between requests")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument(
        "--admin-totals",
        help="JSON {site: {report: total}} typed from the admin screens",
    )
    ap.add_argument(
        "--code-file",
        help="file the operator writes the emailed login code into (read once, then deleted)",
    )
    ap.add_argument("--code-wait", type=int, default=600)
    ap.add_argument(
        "--profile-margin-min",
        type=int,
        default=15,
        help="no profile download starts this close to 09:00 UTC",
    )
    return ap.parse_args(argv)


def main(
    argv: list[str] | None = None,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    out = Out()
    clock = clock or (lambda: datetime.now(timezone.utc))
    sleeper = sleeper or time.sleep
    try:
        a = parse_args(argv)
        cfg = load_config(Path(a.config))
        sites = [s.strip() for s in a.sites.split(",") if s.strip()]
        reports = [r.strip() for r in a.reports.split(",") if r.strip()]
        if not sites or any(s not in SITES or s not in cfg["sites"] for s in sites):
            raise Refusal(f"--sites must be from {SITES}")
        if not reports or any(
            r not in REPORTS or r not in cfg["reports"] for r in reports
        ):
            raise Refusal(f"--reports must be from {REPORTS}")
        if not a.out and not a.r2:
            raise Refusal(
                "give a destination: --out DIR (outside the repo) and/or --r2"
            )
        out_dir = check_out_dir(a.out) if a.out else None
        if a.discover and not out_dir:
            raise Refusal("--discover needs --out")
        headers = load_expected_headers()
        for s in sites:
            for r in reports:
                expected_header(headers, s, cfg["reports"][r]["header_sheet"])
        now = clock()
        until = (
            date.fromisoformat(a.until)
            if a.until
            else now.astimezone(timezone.utc).date()
        )
        since = (
            date.fromisoformat(a.since)
            if a.since
            else date.fromisoformat(cfg.get("earliest", "2005-01-01"))
        )
        items = plan(cfg, sites, reports, since, until, a.months)
        manual = (
            json.loads(Path(a.admin_totals).read_text(encoding="utf-8"))
            if a.admin_totals
            else {}
        )

        if not a.live:  # offline: no network, no R2, no credentials read
            store = Store(out_dir, None)
            if out_dir:
                store.load()
            done = sum(
                1 for it in items if window_key(*it) in store.manifest["entries"]
            )
            for s in sites:
                env = cfg["sites"][s]
                have = all(os.environ.get(env[k]) for k in ("user_env", "pass_env"))
                out.say(
                    f"{s}: credentials env {env['user_env']}/{env['pass_env']} {'set' if have else 'MISSING'}"
                )
            out.say(
                f"plan: {len(items)} window(s) over {len(sites)} site(s) x {len(reports)} report(s), "
                f"{done} already in the local manifest; config verified={cfg.get('verified', False)}"
            )
            if "profiles" in reports and not quiet_ok(
                cfg["reports"]["profiles"], now, a.profile_margin_min
            ):
                out.say("note: profiles would be deferred now (09:00-17:00 UTC)")
            if a.reconcile and out_dir:
                _, bad = reconcile(
                    Ctx(cfg, out, store, headers, clock, a.profile_margin_min, out_dir),
                    items,
                    sites,
                    reports,
                    manual,
                )
                return EXIT_INCOMPLETE if bad else EXIT_OK
            out.say("dry run: nothing contacted (add --live to download)")
            return EXIT_OK

        if not a.discover and not cfg.get("verified"):
            raise Refusal(
                "config verified=false: run --live --discover, fix strategies_export_config.json, set verified=true"
            )
        if (
            not a.discover
            and reports == ["profiles"]
            and not quiet_ok(cfg["reports"]["profiles"], now, a.profile_margin_min)
        ):
            raise Refusal(
                "refused: 'Members profile data' runs only outside 09:00-17:00 UTC (and not in the "
                f"{a.profile_margin_min} min before 09:00)"
            )
        r2 = R2.from_env(a.r2_prefix, out) if a.r2 else None
        store = Store(out_dir, r2)
        store.load()
        code_file = Path(a.code_file).expanduser().resolve() if a.code_file else None
        if code_file and _within(code_file, REPO_ROOT.resolve()):
            raise Refusal("refused: --code-file must live outside the repo")

        def factory(site: str) -> Admin:
            return Admin(site, cfg, out, a.pace, sleeper, code_file, a.code_wait)

        with tempfile.TemporaryDirectory(prefix="gj_export_") as td:
            staging = out_dir if out_dir else Path(td)
            ctx = Ctx(cfg, out, store, headers, clock, a.profile_margin_min, staging)
            if a.discover:
                for s in sites:
                    discover(ctx, factory(s))
                return EXIT_OK
            deferred = run_live(ctx, factory, items, sites)
            _, bad = reconcile(ctx, items, sites, reports, manual)
        if deferred or bad:
            out.say("INCOMPLETE: see reconciliation (exit 4)")
            return EXIT_INCOMPLETE
        out.say("done")
        return EXIT_OK
    except Refusal as e:
        out.say(str(e))
        return EXIT_USAGE
    except DataContractError as e:
        out.say(f"FAIL (data contract): {e}")
        return EXIT_DATA
    except TransportError as e:
        out.say(f"FAIL (transport): {e}")
        return EXIT_TRANSPORT


if __name__ == "__main__":
    sys.exit(main())
