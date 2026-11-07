"""Strategies "Download Reports" CSV -> GreenJobs D1: offline validator, mapper and SQL emitter.

description: Validates one Strategies report type (recruiters, candidates, profiles, jobs, applications)
  for one site against strategies_mapping.json: encoding/delimiter sniff, header aliases (fail loud on
  a required field with no header), hostile-input checks (formula / prompt injection, path traversal,
  control chars, invalid emails, max lengths), retention filter, cross-batch dedupe, and bounded
  yield / reject-rate gates. Dry run by default: prints a JSON summary that never carries a full
  email, name or phone. --emit-sql writes idempotent SQL (the exact upsert shapes of
  d1/upserts.sql) plus an import_batches skip-if-done row per input file.
  No network, no D1 call: the operator applies the SQL with `npx wrangler@4 d1 execute`.
inputs: --site ie|uk, --report TYPE, --csv PATH (repeatable; outside the repo, or tests/**/fixtures/)
outputs: stdout JSON summary; optional --report-out (no PII; outside repo or <repo>/.tmp/);
  optional --emit-sql (outside the repo only)
exit codes: 0 ok / no-op, 2 usage, config or mapping error, 3 gate failure

Directive: directives/gtm_client_workflows/greenjobs_redesign.md ("Strategies data import").
Mapping doc: deliverables/greenjobs_migration_2026-11-06/build/import/IMPORT_MAPPING.md
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

EXIT_OK, EXIT_USAGE, EXIT_GATE = 0, 2, 3
HERE = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / ".git").exists():
            return p
    return HERE.parents[2]


REPO_ROOT = _find_repo_root()
DEFAULT_MAPPING = HERE / "strategies_mapping.json"
DEFAULT_UPSERTS = REPO_ROOT / "deliverables" / "greenjobs_migration_2026-11-06" / "build" / "d1" / "upserts.sql"

REPORTS = ("recruiters", "candidates", "profiles", "jobs", "applications")
TYPES = {"text", "email", "date", "int", "money", "bool", "list", "id", "url", "filename"}
MAX_FILE_BYTES = 200 * 1024 * 1024
RETENTION_MIN, RETENTION_MAX = 6, 84
STDOUT_ISSUE_CAP = 50
SITE_CURRENCY = {"ie": "EUR", "uk": "GBP"}
LOGO_KEY_TEMPLATE = "strategies/{site}/logos/{filename}"

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NUMERICISH_RE = re.compile(r"[+-][\d\s().\-/]*")
EMAIL_RE = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}")
EMAIL_IN_TEXT_RE = re.compile(r"[^\s@<>\"',;]+@[^\s@<>\"',;]+")
DIGITS_RE = re.compile(r"\d[\d\s()-]{5,}\d")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.I)
PROMPT_INJECTION_RE = re.compile(
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions|prompts?)|disregard (?:all |the )?"
    r"(?:previous|prior|above)|system prompt|you are now|</?script|javascript:|<iframe|onerror\s*=",
    re.I,
)
BOOL_MAP = {"1": 1, "y": 1, "yes": 1, "true": 1, "on": 1, "t": 1, "x": 1,
            "0": 0, "n": 0, "no": 0, "false": 0, "off": 0, "f": 0}
PERIOD_MAP = {"year": "year", "yearly": "year", "annum": "year", "perannum": "year", "pa": "year", "annual": "year",
              "annually": "year", "peryear": "year", "day": "day", "daily": "day", "perday": "day", "pd": "day",
              "hour": "hour", "hourly": "hour", "perhour": "hour", "ph": "hour", "month": "month",
              "monthly": "month", "permonth": "month", "pm": "month"}
CURRENCY_MAP = {"eur": "EUR", "euro": "EUR", "euros": "EUR", "€": "EUR",
                "gbp": "GBP", "stg": "GBP", "sterling": "GBP", "£": "GBP"}


class UsageError(Exception):
    """Usage, config or mapping error -> exit 2."""


class RowReject(Exception):
    def __init__(self, reason: str, column: str | None, evidence: str = ""):
        super().__init__(reason)
        self.reason, self.column, self.evidence = reason, column, evidence


class RowExclude(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Raw:
    """A trusted SQL expression built by this script (never from input text)."""
    sql: str


# --------------------------------------------------------------------------- evidence (never PII)

def mask_email(s: str) -> str:
    s = s.strip()
    if "@" in s:
        local, _, domain = s.rpartition("@")
        return f"{local[:1]}***@{domain}"[:40]
    return f"{s[:1]}*** len={len(s)}"[:40]


def safe_text_evidence(s: str) -> str:
    s = EMAIL_IN_TEXT_RE.sub(lambda m: mask_email(m.group(0)), s)
    s = DIGITS_RE.sub("#", s)
    s = CONTROL_RE.sub("?", s).replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return s[:40]


def pii_shape(s: str) -> str:
    lead = s[:1]
    lead_part = f" lead={lead!r}" if lead and not lead.isalnum() else ""
    return f"len={len(s)}{lead_part}"[:40]


def evidence_for(value: str | None, spec: dict) -> str:
    if value is None:
        return ""
    s = str(value)
    if spec.get("type") == "email":
        return mask_email(s)
    if spec.get("pii"):
        return pii_shape(s)
    return safe_text_evidence(s)


# --------------------------------------------------------------------------- mapping

def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", h).lower())


def load_mapping(path: Path) -> dict:
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise UsageError(f"mapping unreadable: {path.name}: {e}") from e
    if not isinstance(m, dict) or not isinstance(m.get("reports"), dict) or not m.get("date_formats"):
        raise UsageError("mapping: needs 'reports' and 'date_formats'")
    for r in REPORTS:
        rep = m["reports"].get(r)
        if not isinstance(rep, dict) or not isinstance(rep.get("fields"), dict) or not rep.get("activity_chain"):
            raise UsageError(f"mapping: report '{r}' needs 'fields' and 'activity_chain'")
        for fname, spec in rep["fields"].items():
            if spec.get("type") not in TYPES:
                raise UsageError(f"mapping: {r}.{fname} has unknown type {spec.get('type')!r}")
            if spec.get("on_invalid", "reject_row") not in ("reject_row", "drop_value"):
                raise UsageError(f"mapping: {r}.{fname} bad on_invalid")
            if spec.get("on_too_long", "reject_row") not in ("reject_row", "truncate"):
                raise UsageError(f"mapping: {r}.{fname} bad on_too_long")
            aliases = spec.get("aliases")
            if not aliases or not all(isinstance(a, str) and norm_header(a) for a in aliases):
                raise UsageError(f"mapping: {r}.{fname} needs non-empty aliases")
        for f in rep["activity_chain"]:
            if f not in rep["fields"]:
                raise UsageError(f"mapping: {r} activity_chain names unknown field {f}")
    return m


def map_headers(report: str, rep: dict, header: list[str]) -> tuple[dict[str, int], dict[str, str], list[str], list[str]]:
    """Return (field->column index, field->header text, unmapped headers, duplicate headers)."""
    index: dict[str, int] = {}
    dupes: list[str] = []
    for i, h in enumerate(header):
        n = norm_header(h)
        if not n:
            continue
        if n in index:
            dupes.append(h[:60])
            continue
        index[n] = i
    fields = rep["fields"]
    mapped: dict[str, int] = {}
    claimed: set[int] = set()
    max_rank = max(len(s["aliases"]) for s in fields.values())
    for rank in range(max_rank):  # most specific alias first across all fields
        for fname, spec in fields.items():
            if fname in mapped or rank >= len(spec["aliases"]):
                continue
            idx = index.get(norm_header(spec["aliases"][rank]))
            if idx is not None and idx not in claimed:
                mapped[fname] = idx
                claimed.add(idx)
    missing = [f for f, s in fields.items() if s.get("required") and f not in mapped]
    for group in rep.get("require_one_of", []):
        if not any(g in mapped for g in group):
            missing.append("one of " + "/".join(group))
    if missing:
        detail = "; ".join(
            f"{f} (aliases: {', '.join(fields[f]['aliases'])})" if f in fields else f for f in missing
        )
        raise UsageError(
            f"mapping: report '{report}' has no header for required field(s): {detail}. "
            f"Headers seen: {[h[:60] for h in header]}. Add the real header as an alias in strategies_mapping.json."
        )
    unmapped = [header[i][:60] for i in range(len(header)) if i not in claimed and norm_header(header[i])]
    return mapped, {f: header[i][:60] for f, i in mapped.items()}, unmapped, dupes


# --------------------------------------------------------------------------- reading

def read_csv(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise UsageError(f"{path.name}: {len(raw)} bytes exceeds the {MAX_FILE_BYTES}-byte ceiling; split the batch")
    try:
        text, encoding = raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        try:
            text, encoding = raw.decode("cp1252"), "cp1252"
        except UnicodeDecodeError as e:
            raise UsageError(f"{path.name}: neither UTF-8 nor Windows-1252: {e}") from e
    nul = text.count("\x00")
    text = text.replace("\x00", "")
    first = text.split("\n", 1)[0]
    counts = {d: first.count(d) for d in (",", ";", "\t", "|")}
    delimiter = max(counts, key=lambda d: counts[d]) if max(counts.values()) else ","
    csv.field_size_limit(10 * 1024 * 1024)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    rows: list[tuple[int, list[str]]] = []
    header: list[str] | None = None
    try:
        for cells in reader:
            if header is None:
                if not any(c.strip() for c in cells):
                    continue
                header = [c.strip() for c in cells]
                continue
            if not any(c.strip() for c in cells):
                continue
            rows.append((reader.line_num, cells))
    except csv.Error as e:
        raise UsageError(f"{path.name}: CSV parse error near line {reader.line_num}: {e}") from e
    return {"sha256": hashlib.sha256(raw).hexdigest(), "encoding": encoding,
            "delimiter": {"\t": "tab"}.get(delimiter, delimiter), "header": header or [],
            "rows": rows, "nul_removed": nul}


# --------------------------------------------------------------------------- cell conversion

@dataclass
class Ctx:
    site: str
    report: str
    as_of: date
    cutoff_iso: str
    date_formats: list[str]
    file: str = ""
    line: int = 0
    rejects: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    flags: dict[str, int] = field(default_factory=lambda: {
        "formula_injection": 0, "prompt_injection": 0, "control_chars": 0, "truncated": 0, "nul_removed": 0})

    def warn(self, column: str | None, reason: str, evidence: str = "") -> None:
        self.warnings.append({"file": self.file, "row": self.line, "column": column,
                              "reason": reason, "evidence": evidence[:40]})


def parse_date(s: str, formats: list[str]) -> str | None:
    s = re.sub(r"\s+", " ", s.strip())
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if not 1990 <= dt.year <= 2100:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def parse_money(s: str) -> int | None:
    t = re.sub(r"[€£$,\s]|eur|gbp|stg", "", s.lower())
    mult = 1
    if t.endswith("k"):
        mult, t = 1000, t[:-1]
    if not re.fullmatch(r"\d+(?:\.\d+)?", t):
        return None
    v = int(round(float(t) * mult))
    return v if 0 <= v <= 10_000_000 else None


def unsafe_filename_token(s: str) -> str | None:
    decoded = urllib.parse.unquote(s)
    for cand in (s, decoded):
        for tok in ("..", "/", "\\", ":"):
            if tok in cand:
                return tok
        if cand.startswith("~"):
            return "~"
    return None


def convert(fname: str, spec: dict, raw: str | None, ctx: Ctx):
    """Clean and type one cell. Returns the value or None; raises RowReject."""
    if raw is None:
        return None
    ftype = spec["type"]
    s = raw
    if CONTROL_RE.search(s):
        ctx.flags["control_chars"] += 1
        s = CONTROL_RE.sub("", s)
    leading_ws_formula = s.lstrip(" ")[:1] in ("\t", "\r", "\n") and s.strip() != ""
    s = s.strip()
    if ftype != "text":
        s = re.sub(r"\s+", " ", s)
    if not s:
        return None
    formula = leading_ws_formula or s[:1] in ("=", "@") or (
        s[:1] in ("+", "-") and len(s) > 1 and not NUMERICISH_RE.fullmatch(s))

    def invalid(reason: str, ev: str | None = None):
        if spec.get("on_invalid", "reject_row") == "drop_value":
            ctx.warn(fname, reason + "_dropped", ev if ev is not None else evidence_for(s, spec))
            return None
        raise RowReject(reason, fname, ev if ev is not None else evidence_for(s, spec))

    if formula:
        ctx.flags["formula_injection"] += 1
        if ftype not in ("text", "list"):
            return invalid("formula_injection")
        # Flag only (#11): the raw text goes to D1 unchanged, so the live board never shows a stray "'".
        # Neutralising is an export-time concern: this script writes no CSV (only SQL + a JSON report);
        # the Worker's toCsvCell() in platform_worker/src/validate.js neutralises on every CSV export.
        ctx.warn(fname, "formula_injection_flagged", evidence_for(s, spec))
    if ftype == "text":
        m = PROMPT_INJECTION_RE.search(s)
        if m:
            ctx.flags["prompt_injection"] += 1
            ctx.warn(fname, "prompt_injection_flagged", f"match={m.group(0)[:30]!r}")
    max_len, min_len = spec.get("max_len"), spec.get("min_len")
    if max_len and len(s) > max_len and ftype not in ("list",):
        if spec.get("on_too_long", "reject_row") == "truncate" and ftype == "text":
            ctx.flags["truncated"] += 1
            ctx.warn(fname, "truncated", f"len={len(s)} max={max_len}")
            s = s[:max_len].rstrip()
        else:
            raise RowReject("too_long", fname, f"len={len(s)} max={max_len}")
    if min_len and len(s) < min_len:
        raise RowReject("too_short", fname, f"len={len(s)} min={min_len}")

    if ftype == "text":
        return s
    if ftype == "id":
        s = re.sub(r"^(\d+)\.0+$", r"\1", s)
        return s if ID_RE.fullmatch(s) else invalid("invalid_id")
    if ftype == "email":
        e = s.lower()
        return e if len(e) <= 254 and EMAIL_RE.fullmatch(e) else invalid("invalid_email")
    if ftype == "date":
        d = parse_date(s, ctx.date_formats)
        return d if d else invalid("invalid_date")
    if ftype == "int":
        return int(s) if re.fullmatch(r"\d{1,12}", s) else invalid("invalid_int")
    if ftype == "money":
        v = parse_money(s)
        return v if v is not None else invalid("invalid_money")
    if ftype == "bool":
        b = BOOL_MAP.get(s.lower())
        return b if b is not None else invalid("invalid_bool")
    if ftype == "url":
        if spec.get("column") == "apply_url" and not s.lower().startswith("https://"):
            return invalid("invalid_url", "not https")
        if not URL_RE.fullmatch(s):
            return invalid("invalid_url", "not an http(s) url")
        return s
    if ftype == "filename":
        tok = unsafe_filename_token(s)
        if tok:
            return invalid("unsafe_filename", f"contains {tok!r} len={len(s)}")
        return s
    if ftype == "list":
        items: list[str] = []
        for part in re.split(r"[;|,]", s):
            p = part.strip()
            if not p:
                continue
            if p[:1] in "=+-@":
                ctx.warn(fname, "list_item_dropped", "formula-like item")
                continue
            if p not in items and len(p) <= 80:
                items.append(p)
        return json.dumps(items[:30], ensure_ascii=False)
    raise UsageError(f"unhandled type {ftype}")  # unreachable: load_mapping validated types


# --------------------------------------------------------------------------- record builders

def stable_id(site: str, sid: str) -> str:
    return f"{site}:strat:{sid}"


def name_norm(name: str) -> str:
    s = unicodedata.normalize("NFKC", name).lower().lstrip("'")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(ltd|limited|plc)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def activity(rep: dict, v: dict) -> str | None:
    for f in rep["activity_chain"]:
        if v.get(f):
            return v[f]
    return None


def join_name(*parts) -> str | None:
    s = " ".join(p for p in parts if p)
    return s or None


def build(report: str, rep: dict, v: dict, ctx: Ctx, aux: dict) -> dict:
    site = ctx.site
    act = activity(rep, v)
    if act is None:
        raise RowExclude("no_activity_date")
    if act < ctx.cutoff_iso:
        raise RowExclude("outside_retention")
    if report != "jobs" and act[:10] > (ctx.as_of + timedelta(days=1)).isoformat():
        ctx.warn(None, "future_activity_date", act[:10])
    rec: dict = {"_activity": act}
    if report == "recruiters":
        sid = v["strategies_id"]
        logo = v.get("logo")
        rec.update(id=stable_id(site, sid), source_id=sid, name=v["name"], name_norm=name_norm(v["name"]) or v["name"].lower(),
                   contact_name=v.get("contact_name") or join_name(v.get("contact_first_name"), v.get("contact_last_name")),
                   contact_email=v.get("contact_email"), phone=v.get("phone"), website=v.get("website"),
                   logo_key=LOGO_KEY_TEMPLATE.format(site=site, filename=logo) if logo else None,
                   last_active_at=act)
        rec["_key"], rec["_key2"] = sid, None
    elif report == "candidates":
        sid = v["strategies_id"]
        rec.update(id=stable_id(site, sid), source_id=sid, email_norm=v["email"], first_name=v.get("first_name"),
                   last_name=v.get("last_name"), phone=v.get("phone"), location=v.get("location"), headline=None,
                   sectors_json=v.get("sectors") or "[]", consent_marketing=v.get("consent_marketing") or 0,
                   consent_at=None, registered_at=v.get("registered"), last_active_at=act)
        rec["_key"], rec["_key2"] = v["email"], sid
    elif report == "profiles":
        cid = v["candidate_id"]
        email = v.get("email")
        cmap = aux.get("candidate_emails")
        if not email and cmap is not None:
            email = cmap.get(cid)
        if not email:
            raise RowReject("unknown_candidate", "candidate_id", f"candidate_id={cid}"[:40])
        rec.update(id=stable_id(site, cid), source_id=cid, email_norm=email, first_name=None, last_name=None,
                   phone=None, location=v.get("location"), headline=v.get("headline"),
                   sectors_json=v.get("sectors") or "[]", consent_marketing=0, consent_at=None,
                   registered_at=None, last_active_at=act)
        rec["_key"], rec["_key2"] = cid, None
    elif report == "jobs":
        sid = v["strategies_id"]
        sal_min, sal_max = v.get("sal_min"), v.get("sal_max")
        if sal_min is not None and sal_max is not None and sal_min > sal_max:
            ctx.warn("sal_min", "salary_range_invalid_dropped", f"{sal_min}>{sal_max}")
            sal_min = sal_max = None
        cur = CURRENCY_MAP.get((v.get("currency") or "").strip().lower().lstrip("'"))
        if cur is None and (sal_min is not None or sal_max is not None):
            cur = SITE_CURRENCY[site]
        period = PERIOD_MAP.get(re.sub(r"[^a-z]", "", (v.get("period") or "").lower()))
        closing = v.get("closing")
        status = "live" if closing and closing[:10] >= ctx.as_of.isoformat() else "closed"
        emp = v.get("employer_id")
        rec.update(id=stable_id(site, sid), source_id=sid,
                   employer_id=Raw(f"(SELECT id FROM employers WHERE id = {sql_lit(stable_id(site, emp))})") if emp else None,
                   title=v["title"], location=v["location"], region=v.get("region"), job_type=v.get("job_type"),
                   sal_min=sal_min, sal_max=sal_max, currency=cur, period=period, sal_text=v.get("sal_text"),
                   sectors_json=v.get("sectors") or "[]", summary=v.get("summary"), description=v["description"],
                   apply_mode="url" if v.get("apply_url") else "inbox", apply_email=v.get("apply_email"),
                   apply_url=v.get("apply_url"), status=status, posted_at=v.get("posted"), closing_at=closing)
        rec["_key"], rec["_key2"] = sid, None
    elif report == "applications":
        job_sid = v["job_id"]
        known = aux.get("job_ids")
        if known is not None and job_sid not in known:
            raise RowReject("orphan_job", "job_id", f"job_id={job_sid}"[:40])
        name = v.get("applicant_name") or join_name(v.get("first_name"), v.get("last_name"))
        if not name:
            raise RowReject("missing_required", "applicant_name", "")
        if len(name) > 120:
            raise RowReject("too_long", "applicant_name", f"len={len(name)} max=120")
        job_id = stable_id(site, job_sid)
        email = v["applicant_email"]
        dk = hashlib.sha256(f"{site}|{job_id}|{email}".encode("utf-8")).hexdigest()
        app_sid = v.get("strategies_id")
        rec.update(id=stable_id(site, app_sid) if app_sid else stable_id(site, f"app-{dk[:24]}"), source_id=app_sid,
                   job_id=job_id,
                   candidate_id=Raw(f"(SELECT id FROM candidates WHERE site = {sql_lit(site)} AND email_norm = {sql_lit(email)})"),
                   applicant_name=name, applicant_email=email, phone=v.get("phone"), cover_note=v.get("cover_note"),
                   cv_key=None, routed_to=None, delivery_status="imported", dedupe_key=dk, submitted_at=act)
        rec["_key"], rec["_key2"] = dk, app_sid
    return rec


def collapse(records: list[dict], ctx: Ctx) -> tuple[list[dict], int]:
    """Keep the latest record per _key, then per _key2 (stable sort keeps file order on ties)."""
    collapsed = 0
    best: dict[str, dict] = {}
    for r in records:
        old = best.get(r["_key"])
        if old is not None:
            collapsed += 1
            if r["_activity"] < old["_activity"]:
                continue
        best[r["_key"]] = r
    out = list(best.values())
    by2: dict[str, dict] = {}
    final: list[dict] = []
    for r in out:
        k2 = r.get("_key2")
        if k2 is None:
            final.append(r)
            continue
        old = by2.get(k2)
        if old is not None:
            collapsed += 1
            ctx.warnings.append({"file": r["_file"], "row": r["_line"], "column": None,
                                 "reason": "duplicate_id_different_key_kept_latest",
                                 "evidence": f"also {old['_file']}:{old['_line']}"[:40]})
            if r["_activity"] < old["_activity"]:
                continue
        by2[k2] = r
    final.extend(by2.values())
    final.sort(key=lambda r: (r["_file_idx"], r["_line"]))
    return final, collapsed


# --------------------------------------------------------------------------- processing

def process(report: str, paths: list[Path], mapping: dict, ctx: Ctx, aux: dict, done: set[str]) -> dict:
    rep = mapping["reports"][report]
    fields = rep["fields"]
    files: list[dict] = []
    kept: list[dict] = []
    seen: set[str] = set()
    for fidx, path in enumerate(paths):
        data = read_csv(path)
        ctx.file = path.name
        summ = {"file": path.name, "sha256": data["sha256"], "encoding": data["encoding"],
                "delimiter": data["delimiter"], "rows_in": 0, "rows_kept": 0, "rejected": 0,
                "excluded": {}, "skipped": None}
        files.append(summ)
        if data["sha256"] in seen:
            summ["skipped"] = "duplicate_file_in_this_run"
            continue
        if data["sha256"] in done:
            summ["skipped"] = "already_imported"
            continue
        seen.add(data["sha256"])
        if data["nul_removed"]:
            ctx.flags["nul_removed"] += data["nul_removed"]
        if not data["header"]:
            continue
        colmap, mapped_headers, unmapped, dupes = map_headers(report, rep, data["header"])
        summ["headers"] = {"mapped": mapped_headers, "unmapped": unmapped, "duplicate": dupes}
        width = len(data["header"])
        for line, cells in data["rows"]:
            ctx.line = line
            summ["rows_in"] += 1
            if len(cells) > width and not any(c.strip() for c in cells[width:]):
                cells = cells[:width]
            if len(cells) != width:
                ctx.rejects.append({"file": path.name, "row": line, "column": None, "reason": "ragged_row",
                                    "evidence": f"{len(cells)} cells, expected {width}"})
                summ["rejected"] += 1
                continue
            try:
                values = {}
                for fname, idx in colmap.items():
                    values[fname] = convert(fname, fields[fname], cells[idx], ctx)
                    if fields[fname].get("required") and values[fname] is None:
                        raise RowReject("missing_required", fname, "")
                rec = build(report, rep, values, ctx, aux)
            except RowReject as r:
                ctx.rejects.append({"file": path.name, "row": line, "column": r.column, "reason": r.reason,
                                    "evidence": (r.evidence or "")[:40]})
                summ["rejected"] += 1
                continue
            except RowExclude as x:
                summ["excluded"][x.reason] = summ["excluded"].get(x.reason, 0) + 1
                continue
            rec["_file"], rec["_line"], rec["_file_idx"] = path.name, line, fidx
            kept.append(rec)
            summ["rows_kept"] += 1
    records, collapsed = collapse(kept, ctx)
    if report == "recruiters":
        by_norm: dict[str, dict] = {}
        for r in records:
            prev = by_norm.get(r["name_norm"])
            if prev:
                ctx.warnings.append({"file": r["_file"], "row": r["_line"], "column": "name",
                                     "reason": "duplicate_name_norm", "evidence": f"same as {prev['_file']}:{prev['_line']}"[:40]})
            else:
                by_norm[r["name_norm"]] = r
    return {"files": files, "records": records, "collapsed": collapsed}


# --------------------------------------------------------------------------- SQL

def sql_lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, Raw):
        return v.sql
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if "\x00" in s:
        raise ValueError("NUL in SQL literal")
    return "'" + s.replace("'", "''") + "'"


def load_upserts(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise UsageError(f"upserts.sql unreadable: {e}") from e
    body = re.sub(r"--[^\n]*", "", text)
    stmts = [re.sub(r"\s+", " ", s).strip() for s in body.split(";") if s.strip()]
    want = {"employers": "INSERT INTO employers ", "jobs": "INSERT INTO jobs ", "candidates": "INSERT INTO candidates ",
            "applications": "INSERT INTO applications ", "import_batches": "INSERT OR IGNORE INTO import_batches "}
    out: dict[str, str] = {}
    for key, prefix in want.items():
        hits = [s for s in stmts if s.startswith(prefix)]
        if len(hits) != 1:
            raise UsageError(f"upserts.sql: expected one '{prefix.strip()}' statement, found {len(hits)}")
        out[key] = hits[0]
    return out


def render(template: str, params: list) -> str:
    n = max(int(x) for x in re.findall(r"\?(\d+)", template))
    if n != len(params):
        raise UsageError(f"upsert shape changed: needs {n} params, emitter has {len(params)}")
    return re.sub(r"\?(\d+)", lambda m: sql_lit(params[int(m.group(1)) - 1]), template) + ";"


def params_for(report: str, site: str, r: dict, now: str) -> tuple[str, list]:
    if report == "recruiters":
        return "employers", [r["id"], site, "strategies", r["source_id"], r["name"], r["name_norm"], r["contact_name"],
                             r["contact_email"], r["phone"], r["website"], r["logo_key"], r["last_active_at"], now]
    if report in ("candidates", "profiles"):
        return "candidates", [r["id"], site, "strategies", r["source_id"], r["email_norm"], r["first_name"],
                              r["last_name"], r["phone"], r["location"], r["headline"], r["sectors_json"],
                              r["consent_marketing"], r["consent_at"], r["registered_at"], r["last_active_at"], now]
    if report == "jobs":
        return "jobs", [r["id"], site, "strategies", r["source_id"], r["employer_id"], r["title"], r["location"],
                        r["region"], r["job_type"], r["sal_min"], r["sal_max"], r["currency"], r["period"],
                        r["sal_text"], r["sectors_json"], r["summary"], r["description"], r["apply_mode"],
                        r["apply_email"], r["apply_url"], r["status"], r["posted_at"], r["closing_at"], "import", now]
    return "applications", [r["id"], site, "strategies", r["source_id"], r["job_id"], r["candidate_id"],
                            r["applicant_name"], r["applicant_email"], r["phone"], r["cover_note"], r["cv_key"],
                            r["routed_to"], r["delivery_status"], r["dedupe_key"], r["submitted_at"], now]


def emit_sql(report: str, site: str, result: dict, templates: dict, now: str) -> str:
    lines = [f"-- GreenJobs Strategies import: site={site} report={report} generated={now}",
             "-- Idempotent: canonical upserts from d1/upserts.sql; re-running converges. Contains PII: never commit.",
             "-- Apply: npx wrangler@4 d1 execute greenjobs --file=THIS_FILE   (order: recruiters, jobs, candidates, profiles, applications)"]
    for r in result["records"]:
        table, params = params_for(report, site, r, now)
        lines.append(render(templates[table], params))
    for f in result["files"]:
        if f["skipped"]:
            continue
        lines.append(render(templates["import_batches"], [f["sha256"], site, report, f["rows_in"], f["rows_kept"], now]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- paths

def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def check_input(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    if not p.is_file():
        raise UsageError(f"input not found or not a file: {Path(raw).name}")
    if _within(p, REPO_ROOT):
        parts = p.relative_to(REPO_ROOT).parts
        if not (parts and parts[0] == "tests" and "fixtures" in parts[1:-1]):
            raise UsageError("refused: input CSVs hold PII and must live outside the git repo "
                             "(only tests/**/fixtures/ is allowed inside it)")
    return p


def check_output(raw: str, allow_repo_tmp: bool, inputs: list[Path]) -> Path:
    p = Path(raw).expanduser().resolve()
    if p.is_dir():
        raise UsageError(f"output is a directory: {raw}")
    if not p.parent.is_dir():
        raise UsageError(f"output directory does not exist: {p.parent}")
    if p in inputs:
        raise UsageError("output path equals an input path")
    if _within(p, REPO_ROOT) and not (allow_repo_tmp and _within(p, REPO_ROOT / ".tmp")):
        where = "outside the repo or under <repo>/.tmp/" if allow_repo_tmp else "outside the git repo"
        raise UsageError(f"refused: this output must resolve {where}")
    return p


def atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".strat_import_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------- CLI

def months_before(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + (d.month - 1) - n, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ratio(lo: float, hi: float, name: str):
    def parse(s: str) -> float:
        try:
            v = float(s)
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"{name} must be a number") from e
        if not lo <= v <= hi:
            raise argparse.ArgumentTypeError(f"{name} must be within {lo}..{hi}")
        return v
    return parse


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Strategies CSV -> GreenJobs D1 (offline; dry run by default)")
    ap.add_argument("--site", required=True, choices=["ie", "uk"])
    ap.add_argument("--report", required=True, choices=list(REPORTS))
    ap.add_argument("--csv", required=True, action="append", help="report CSV (repeat for date batches)")
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--retention-months", type=int, default=24, help=f"{RETENTION_MIN}..{RETENTION_MAX}")
    ap.add_argument("--min-yield", type=ratio(0.0, 1.0, "--min-yield"), default=0.05)
    ap.add_argument("--max-reject-rate", type=ratio(0.0, 1.0, "--max-reject-rate"), default=0.20)
    ap.add_argument("--allow-low-yield", action="store_true")
    ap.add_argument("--candidates-csv", action="append", default=[], help="profiles: candidate id -> email source")
    ap.add_argument("--jobs-csv", action="append", default=[], help="applications: kept-jobs source (orphan check)")
    ap.add_argument("--known-job-ids", help="applications: text file, one Strategies job id per line")
    ap.add_argument("--done-sha256", help="text file of sha256 already in import_batches (skip those files)")
    ap.add_argument("--report-out")
    ap.add_argument("--emit-sql")
    ap.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    ap.add_argument("--upserts", default=str(DEFAULT_UPSERTS))
    return ap


def read_id_list(path: Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            out.add(s)
    return out


def run(args: argparse.Namespace) -> tuple[int, dict]:
    if not RETENTION_MIN <= args.retention_months <= RETENTION_MAX:
        raise UsageError(f"--retention-months must be {RETENTION_MIN}..{RETENTION_MAX}, got {args.retention_months}")
    today = datetime.now(timezone.utc).date()
    if args.as_of:
        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError as e:
            raise UsageError(f"--as-of must be YYYY-MM-DD: {e}") from e
        if not date(2000, 1, 1) <= as_of <= today + timedelta(days=366):
            raise UsageError("--as-of out of range (2000-01-01 .. today+1y)")
    else:
        as_of = today
    mapping = load_mapping(Path(args.mapping))
    inputs = [check_input(c) for c in args.csv]
    aux_inputs = [check_input(c) for c in args.candidates_csv + args.jobs_csv]
    known_path = check_input(args.known_job_ids) if args.known_job_ids else None
    done = read_id_list(check_input(args.done_sha256)) if args.done_sha256 else set()
    all_in = inputs + aux_inputs + ([known_path] if known_path else [])
    report_out = check_output(args.report_out, True, all_in) if args.report_out else None
    sql_out = check_output(args.emit_sql, False, all_in) if args.emit_sql else None
    templates = load_upserts(Path(args.upserts)) if sql_out else None
    if args.report != "applications" and (args.jobs_csv or args.known_job_ids):
        raise UsageError("--jobs-csv / --known-job-ids apply to --report applications only")
    if args.report != "profiles" and args.candidates_csv:
        raise UsageError("--candidates-csv applies to --report profiles only")

    cutoff = months_before(as_of, args.retention_months)
    ctx = Ctx(site=args.site, report=args.report, as_of=as_of, cutoff_iso=f"{cutoff.isoformat()}T00:00:00Z",
              date_formats=mapping["date_formats"])
    aux: dict = {}
    reference: dict = {}
    if args.report == "profiles":
        has_email_alias = True
        if args.candidates_csv:
            sub = Ctx(site=args.site, report="candidates", as_of=as_of, cutoff_iso=ctx.cutoff_iso,
                      date_formats=mapping["date_formats"])
            res = process("candidates", [check_input(c) for c in args.candidates_csv], mapping, sub, {}, set())
            aux["candidate_emails"] = {r["source_id"]: r["email_norm"] for r in res["records"]}
            reference["candidates"] = {"kept": len(res["records"]), "rejected": len(sub.rejects)}
        else:
            has_email_alias = False
        if not has_email_alias:
            for p in inputs:
                hdr = read_csv(p)["header"]
                aliases = {norm_header(a) for a in mapping["reports"]["profiles"]["fields"]["email"]["aliases"]}
                if not aliases & {norm_header(h) for h in hdr}:
                    raise UsageError(f"profiles: {p.name} has no email column; pass --candidates-csv to map candidate id -> email")
    if args.report == "applications":
        ids: set[str] | None = None
        if args.jobs_csv:
            sub = Ctx(site=args.site, report="jobs", as_of=as_of, cutoff_iso=ctx.cutoff_iso,
                      date_formats=mapping["date_formats"])
            res = process("jobs", [check_input(c) for c in args.jobs_csv], mapping, sub, {}, set())
            ids = {r["source_id"] for r in res["records"]}
            reference["jobs"] = {"kept": len(ids), "rejected": len(sub.rejects)}
        if known_path:
            ids = (ids or set()) | read_id_list(known_path)
            reference["known_job_ids"] = len(read_id_list(known_path))
        aux["job_ids"] = ids
        if ids is None:
            if sql_out:
                raise UsageError("applications --emit-sql needs --jobs-csv or --known-job-ids "
                                 "(applications.job_id is a NOT NULL foreign key)")
            ctx.warnings.append({"file": None, "row": None, "column": "job_id", "reason": "orphan_check_skipped",
                                 "evidence": "no --jobs-csv/--known-job-ids"})

    result = process(args.report, inputs, mapping, ctx, aux, done)
    rows_in = sum(f["rows_in"] for f in result["files"])
    gate_failures = []
    for f in result["files"]:
        if f["skipped"] or f["rows_in"] == 0:
            continue
        f["yield"] = round(f["rows_kept"] / f["rows_in"], 4)
        f["reject_rate"] = round(f["rejected"] / f["rows_in"], 4)
        ev = [f"{r['row']}:{r['column']}:{r['reason']}" for r in ctx.rejects if r["file"] == f["file"]][:5]
        if f["yield"] < args.min_yield and not args.allow_low_yield:
            gate_failures.append({"file": f["file"], "gate": "min_yield", "value": f["yield"],
                                  "threshold": args.min_yield, "excluded": f["excluded"], "evidence": ev})
        if f["reject_rate"] > args.max_reject_rate:
            gate_failures.append({"file": f["file"], "gate": "max_reject_rate", "value": f["reject_rate"],
                                  "threshold": args.max_reject_rate, "evidence": ev})
    reasons: dict[str, int] = {}
    for r in ctx.rejects:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    status = "noop" if rows_in == 0 else ("gate_failed" if gate_failures else "ok")
    code = EXIT_GATE if gate_failures else EXIT_OK
    summary = {
        "tool": "strategies_import", "site": args.site, "report": args.report,
        "target_table": mapping["reports"][args.report]["target_table"],
        "mode": "emit_sql" if sql_out else "dry_run", "status": status, "exit_code": code,
        "as_of": as_of.isoformat(), "retention_months": args.retention_months, "cutoff": cutoff.isoformat(),
        "files": result["files"], "reference_inputs": reference,
        "totals": {"rows_in": rows_in, "rows_kept": sum(f["rows_kept"] for f in result["files"]),
                   "rejected": len(ctx.rejects), "duplicates_collapsed": result["collapsed"],
                   "records_out": len(result["records"]),
                   "live_jobs": sum(1 for r in result["records"] if r.get("status") == "live")},
        "reject_reasons": reasons, "flags": ctx.flags,
        "gates": {"min_yield": args.min_yield, "max_reject_rate": args.max_reject_rate,
                  "allow_low_yield": args.allow_low_yield, "failures": gate_failures},
        "rejects": ctx.rejects, "warnings": ctx.warnings, "sql_written": False,
    }
    if sql_out and status == "ok":
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        atomic_write(sql_out, emit_sql(args.report, args.site, result, templates, now))
        summary["sql_written"] = True
        summary["sql_statements"] = len(result["records"]) + sum(1 for f in result["files"] if not f["skipped"])
    if report_out:
        atomic_write(report_out, json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return code, summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, summary = run(args)
    except UsageError as e:
        print(json.dumps({"tool": "strategies_import", "status": "error", "exit_code": EXIT_USAGE, "error": str(e)}))
        print(f"error: {e}", file=sys.stderr)
        return EXIT_USAGE
    out = dict(summary)
    for k in ("rejects", "warnings"):
        if len(out[k]) > STDOUT_ISSUE_CAP:
            out[k + "_truncated"] = len(out[k]) - STDOUT_ISSUE_CAP
            out[k] = out[k][:STDOUT_ISSUE_CAP]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
