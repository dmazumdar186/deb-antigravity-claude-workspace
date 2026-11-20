"""GreenJobs release pipeline: stage, promote, rollback, deploy ledger (dry-run by default).

description: Plans and (only with --execute) runs the GreenJobs Cloudflare release steps for the
    `staging` and `production` environments in environments.json: D1 schema + migrations, Worker
    deploy, both static boards to Pages, a pre-promote D1 backup and previous-version record, and
    rollback to the recorded previous Worker version + Pages deployments. Every run writes a deploy
    record (deploy_record.json) and appends to an append-only ledger (ledger.jsonl). Without
    --execute it prints the exact wrangler / API commands and touches nothing.
inputs: subcommand (stage | promote | rollback | record-smoke | verify-promotable | seed-sql |
    check-config | scan-secrets); --sha; --ledger-dir; --execute; env GREENJOBS_RELEASE_TARGET must
    equal the environment name for --execute; Cloudflare token/account read from the env var names
    in environments.json (never printed).
outputs: {ledger-dir}/deploy_record.json, {ledger-dir}/ledger.jsonl, {ledger-dir}/summary.md;
    stdout plan. Exit 0 ok, 1 step failed, 2 usage/config, 3 gate refused (promote without a passing
    staging record, destructive migration without backup + --allow-destructive, missing rollback target).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import tomllib

try:  # optional: local terminal runs read .env; CI passes secrets as env vars
    from dotenv import load_dotenv

    load_dotenv()
except (
    ImportError
):  # dotenv absent in a bare runner: env vars alone are the documented path
    pass

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "environments.json"
WRANGLER = ["npx", "-y", "wrangler@4"]
CF_API = "https://api.cloudflare.com/client/v4"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
DRY = "<dry-run>"


class GateError(RuntimeError):
    """A release gate refused to continue (exit 3)."""


class StepError(RuntimeError):
    """A command failed (exit 1)."""


# ── config ──────────────────────────────────────────────────────────────────


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def env_cfg(cfg: dict[str, Any], env: str) -> dict[str, Any]:
    if env not in cfg["envs"]:
        raise GateError(
            f"unknown environment {env!r} (known: {', '.join(cfg['envs'])})"
        )
    return cfg["envs"][env]


def placeholders(ec: dict[str, Any]) -> list[str]:
    """Every URL in the env that still holds a REPLACE_ placeholder."""
    out = []
    for group in ("board_urls", "worker_urls"):
        for site, url in ec[group].items():
            if "REPLACE_" in url:
                out.append(f"{group}.{site}={url}")
    return out


def check_wrangler_toml(
    cfg: dict[str, Any], env: str, toml_path: Path | None = None
) -> list[str]:
    """Problems with the [env.<env>] section of wrangler.toml against environments.json (empty = ok)."""
    ec = env_cfg(cfg, env)
    p = toml_path or (ROOT / cfg["worker_dir"] / "wrangler.toml")
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    sec = data.get("env", {}).get(ec["wrangler_env"])
    if sec is None:
        return [f"wrangler.toml has no [env.{ec['wrangler_env']}] section"]
    problems = []
    if sec.get("name") != ec["worker"]:
        problems.append(
            f"env.{env}.name is {sec.get('name')!r}, expected {ec['worker']!r}"
        )
    d1 = sec.get("d1_databases") or []
    if [d.get("database_name") for d in d1] != [ec["d1"]]:
        problems.append(f"env.{env}.d1_databases must be exactly [{ec['d1']!r}]")
    elif not d1[0].get("migrations_dir"):
        problems.append(f"env.{env}.d1_databases[0].migrations_dir is missing")
    r2 = sec.get("r2_buckets") or []
    want_r2 = [ec["r2"]] if ec.get("r2") else []  # "" = no CV bucket (staging until R2 is enabled on the account)
    if [b.get("bucket_name") for b in r2] != want_r2:
        problems.append(f"env.{env}.r2_buckets must be exactly {want_r2!r}")
    vars_ = sec.get("vars") or {}
    if ec.get("require_dry_run") and (
        vars_.get("DRY_RUN") != "1" or vars_.get("LIVE_CONFIRM")
    ):
        problems.append(
            f'env.{env}.vars must pin DRY_RUN="1" and an empty LIVE_CONFIRM'
        )
    if ec.get("require_dry_run") and vars_.get("MAIL_PROVIDER", "none") != "none":
        problems.append(f'env.{env}.vars.MAIL_PROVIDER must be "none"')
    top_vars = set((data.get("vars") or {}).keys())
    missing = sorted(top_vars - set(vars_))
    if (
        missing
    ):  # vars are not inherited by wrangler envs: a missing one silently becomes undefined
        problems.append(f"env.{env}.vars is missing {', '.join(missing)}")
    return problems


# ── SQL and migrations ─────────────────────────────────────────────────────

_DESTRUCTIVE = re.compile(
    r"\b(DROP\s+(TABLE|INDEX|VIEW|TRIGGER)|DELETE\s+FROM|TRUNCATE|ALTER\s+TABLE\s+\S+\s+(DROP|RENAME))\b",
    re.IGNORECASE,
)


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def destructive_statements(sql: str) -> list[str]:
    """Statements that can lose data (drop, delete, truncate, rename). Comments are ignored."""
    stmts = [s.strip() for s in strip_sql_comments(sql).split(";") if s.strip()]
    return [" ".join(s.split())[:120] for s in stmts if _DESTRUCTIVE.search(s)]


def migration_files(mdir: Path) -> list[str]:
    return sorted(p.name for p in Path(mdir).glob("*.sql"))


def migration_level(mdir: Path) -> str:
    files = migration_files(mdir)
    return files[-1] if files else "none"


def pending_from_list_output(output: str, files: list[str]) -> list[str]:
    """`wrangler d1 migrations list` prints only unapplied migrations; match them to repo files."""
    if re.search(r"no migrations to apply", output, re.IGNORECASE):
        return []
    return [f for f in files if f in output]


# ── wrangler output parsing ─────────────────────────────────────────────────


def parse_worker_version(output: str) -> str | None:
    m = re.search(r"Version ID:\s*(" + UUID + ")", output, re.IGNORECASE)
    return m.group(1) if m else None


def parse_deployment_status(output: str) -> str | None:
    """Version serving 100% from `wrangler deployments status`."""
    m = re.search(r"\(100%\)\s*(" + UUID + ")", output)
    if m:
        return m.group(1)
    ids = re.findall(UUID, output)
    return ids[0] if len(set(ids)) == 1 else None


def parse_time_travel_bookmark(output: str) -> str | None:
    try:
        b = json.loads(output).get("bookmark")
        return b if isinstance(b, str) and b else None
    except (ValueError, AttributeError):
        m = re.search(r"bookmark[\"':\s]+([0-9a-f-]{20,})", output, re.IGNORECASE)
        return m.group(1) if m else None


# ── staging seed (public job data only) ────────────────────────────────────

SEED_TABLES = ("employers", "jobs", "job_facets")
_TAG = re.compile(r"<[^>]+>")


def _q(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    # One statement per line is a seed invariant (assert_seed_safe parses by line): fold newlines.
    return "'" + " ".join(str(v).split()).replace("'", "''") + "'"


def _text(raw: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", raw or "")).split())


def _norm(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    s = re.sub(r"\b(ltd|limited|plc)\b", " ", s)
    return " ".join(s.split())


def build_seed_sql(env: str, sources: dict[str, Path], as_of: str) -> tuple[str, int]:
    """INSERT OR IGNORE rows for public jobs + employer names. Staging only; no contact or candidate fields.

    Every job is link-mode to its public listing URL, so no apply email is ever stored; timestamps are
    the fixed --as-of so a re-run produces byte-identical SQL (idempotent). Ids are the Strategies ids an
    import would write ('{site}:strat:<id>'), so the Worker serves them at /{site}/jobs/<id>/ like the static
    board; the advert's closing date is kept, so a closed advert is not live. Each job gets its job_facets row
    from job_classifier (taxonomy.json), exactly as strategies_import.py writes it (set_by 'import')."""
    if env != "staging":
        raise GateError(
            "seed-sql is staging-only: production data never comes from a seed"
        )
    lines = [
        "-- GreenJobs staging seed: public job data only (no candidates, applications or contacts)."
    ]
    pkg = str(Path(__file__).resolve().parents[1])
    if pkg not in sys.path:
        sys.path.insert(0, pkg)
    import job_classifier as jc  # noqa: PLC0415  (build_site + taxonomy.json; staging seed only)

    tax = jc.canonical_taxonomy()
    jc.assert_canonical(tax)
    n = 0
    for site, path in sorted(sources.items()):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        fetched = jc.bs.parse_date(data.get("fetched")) or as_of[:10]
        cur_ok = {"ie": "EUR", "uk": "GBP"}[site]
        for j in data.get("jobs", []):
            title, loc = (
                str(j.get("title") or "").strip(),
                str(j.get("location") or "").strip(),
            )
            desc = _text(j.get("description_html") or j.get("summary") or "")[:20000]
            url = str(j.get("url") or "")
            jid = re.sub(r"[^A-Za-z0-9_-]", "", str(j.get("id") or ""))
            if not (
                jid
                and 3 <= len(title) <= 160
                and 1 <= len(loc) <= 120
                and len(desc) >= 20
                and url.startswith("https://")
            ):
                continue
            emp = str(j.get("employer") or "").strip()[:200]
            emp_id = (
                f"{site}:seed-emp-{_norm(emp).replace(' ', '-')[:80]}" if emp else None
            )
            if emp_id:
                lines.append(
                    "INSERT OR IGNORE INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) "
                    f"VALUES ({_q(emp_id)}, {_q(site)}, 'feed', {_q('seed-emp:' + _norm(emp))}, {_q(emp)}, {_q(_norm(emp))}, {_q(as_of)}, {_q(as_of)});"
                )
            smin, smax = j.get("salary_min"), j.get("salary_max")
            smin = smin if isinstance(smin, int) and smin >= 0 else None
            smax = smax if isinstance(smax, int) and smax >= 0 else None
            if smin is not None and smax is not None and smin > smax:
                smin = smax = None
            period = (
                j.get("period")
                if j.get("period") in ("year", "day", "hour", "month")
                else None
            )
            # The seed is the static board's snapshot (build_site normalise() today = the dataset's fetched date):
            # an advert already closed at the snapshot is not seeded; the rest stay open on staging, exactly as the
            # static board shows them (closing_at NULL; the snapshot's real closing dates are all in the past now).
            closing = jc.bs.parse_date(j.get("closing"))  # the data says dd/mm/yyyy; build_site's own parser
            if closing and closing < fetched:
                continue
            closing_at = None
            job_id = f"{site}:strat:{jid}" if jid.isdigit() else f"{site}:seed:{jid}"
            lines.append(
                "INSERT OR IGNORE INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, "
                "sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, "
                "apply_url, status, posted_at, closing_at, created_by, created_at, updated_at) VALUES ("
                f"{_q(job_id)}, {_q(site)}, 'feed', {_q('seed:' + jid)}, {_q(emp_id)}, {_q(title)}, {_q(loc)}, "
                f"{_q(j.get('region') or None)}, {_q(j.get('type') or None)}, {_q(smin)}, {_q(smax)}, "
                f"{_q(cur_ok if j.get('currency') == cur_ok else None)}, {_q(period)}, {_q(j.get('salary_text') or None)}, "
                f"{_q(json.dumps(j.get('sectors') or [], ensure_ascii=False))}, {_q(_text(j.get('summary') or '')[:300] or None)}, "
                f"{_q(desc)}, 'link', NULL, {_q(url[:2000])}, 'live', {_q(as_of)}, {_q(closing_at)}, 'staging-seed', {_q(as_of)}, {_q(as_of)});"
            )
            cls_in = {"title": title, "employer": emp, "location": loc, "region": j.get("region") or "",
                      "country": j.get("country") or "", "summary": j.get("summary") or "",
                      "description_html": j.get("description_html") or "", "job_type": j.get("type") or "",
                      "source_sectors": [str(x) for x in (j.get("sectors") or [])]}
            labels = [tax.canon(x) for x in cls_in["source_sectors"] if tax.canon(x)]
            hint = {"sectors": labels, "confidence": 1.0, "method": "source"} if labels else None
            c = jc.classify(cls_in, site, tax, hint=hint, require_frozen=False)
            f = jc.facet_row({**cls_in, "sal_min": smin, "sal_max": smax, "currency": cur_ok if j.get("currency") == cur_ok else None,
                              "period": period, "sal_text": j.get("salary_text") or ""}, site, c, "import")
            cols = ("job_id, sectors_json, regions_json, job_type, workplace, contract_json, loc_class, level, is_agency, "
                    "salary_display, unverified_cur, taxonomy_version, set_by, updated_at, search_text, source_sectors_json, "
                    "sector_confidence, sector_method")
            vals = ", ".join(_q(v) if not isinstance(v, float) else repr(v) for v in jc.facet_params(job_id, f, as_of))
            lines.append(f"INSERT OR IGNORE INTO job_facets ({cols}) VALUES ({vals});")
            n += 1
    sql = "\n".join(lines) + "\n"
    assert_seed_safe(sql)
    return sql, n


def assert_seed_safe(sql: str) -> None:
    """Fail closed: the seed may only INSERT OR IGNORE into the public tables."""
    # One statement per line (descriptions are whitespace-collapsed); "--" lines are the header comment.
    for stmt in (
        s.strip() for s in sql.splitlines() if s.strip() and not s.startswith("--")
    ):
        m = re.match(r"INSERT OR IGNORE INTO (\w+) \(([^)]*)\) VALUES \(", stmt)
        if not m or m.group(1) not in SEED_TABLES or not stmt.endswith(");"):
            raise GateError(f"seed statement not allowed: {stmt[:80]}")
        if re.search(
            r"\b(contact_email|contact_name|phone|candidate\w*|application\w*)\b",
            m.group(2),
        ):
            raise GateError("seed touches a personal-data column")
        if m.group(1) == "jobs" and ", 'link', NULL, 'https://" not in stmt:
            raise GateError("seed job must be link-mode with no apply_email")


# ── ledger ───────────────────────────────────────────────────────────────────


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_record(env: str, sha: str, executed: bool) -> dict[str, Any]:
    return {
        "env": env,
        "sha": sha,
        "executed": executed,
        "started_at": utc_now(),
        "finished_at": None,
        "worker_version_id": None,
        "pages_deployments": {},
        "d1_migration_level": None,
        "previous": {
            "worker_version_id": None,
            "pages_deployments": {},
            "d1_bookmark": None,
        },
        "backup": None,
        "pending_migrations": [],
        "destructive_migrations": [],
        "smoke": {"status": "not_run"},
        "rollback": None,
        "status": "started",
        "run_url": os.environ.get("GITHUB_RUN_URL") or "",
    }


def append_ledger(ledger_dir: Path, event: str, record: dict[str, Any]) -> None:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    row = {"event": event, "at": utc_now(), **record}
    with (ledger_dir / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    tmp = ledger_dir / "deploy_record.json.tmp"
    tmp.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(ledger_dir / "deploy_record.json")
    (ledger_dir / "summary.md").write_text(summary_md(record), encoding="utf-8")


def read_ledger(ledger_dir: Path) -> list[dict[str, Any]]:
    p = ledger_dir / "ledger.jsonl"
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def last_good(rows: list[dict[str, Any]], env: str) -> dict[str, Any] | None:
    """Most recent executed deploy on env whose smoke passed and that was not rolled back."""
    for r in reversed(rows):
        if (
            r.get("env") == env
            and r.get("executed")
            and r.get("smoke", {}).get("status") == "pass"
            and not r.get("rollback")
        ):
            return r
    return None


def summary_md(r: dict[str, Any]) -> str:
    pages = (
        ", ".join(f"{k}={v}" for k, v in sorted(r.get("pages_deployments", {}).items()))
        or "-"
    )
    prev = r.get("previous") or {}
    prev_pages = (
        ", ".join(
            f"{k}={v}" for k, v in sorted((prev.get("pages_deployments") or {}).items())
        )
        or "-"
    )
    return (
        f"### GreenJobs deploy: {r['env']}\n\n| field | value |\n|---|---|\n"
        f"| sha | `{r['sha']}` |\n| executed | {r['executed']} |\n| status | {r['status']} |\n"
        f"| Worker version | {r.get('worker_version_id') or '-'} |\n| Pages deployments | {pages} |\n"
        f"| D1 migration level | {r.get('d1_migration_level') or '-'} |\n| smoke | {r['smoke'].get('status')} |\n"
        f"| previous Worker | {prev.get('worker_version_id') or '-'} |\n| previous Pages | {prev_pages} |\n"
        f"| backup | {(r.get('backup') or {}).get('object') or '-'} |\n| rollback | {(r.get('rollback') or {}).get('status') or '-'} |\n"
        f"| started / finished | {r['started_at']} / {r.get('finished_at') or '-'} |\n"
    )


def verify_promotable(staging_record: dict[str, Any], sha: str) -> None:
    """The exact sha must have been executed on staging with a passing smoke run."""
    if staging_record.get("env") != "staging":
        raise GateError("record is not a staging record")
    if staging_record.get("sha") != sha:
        raise GateError(f"staging record is for {staging_record.get('sha')}, not {sha}")
    if not staging_record.get("executed"):
        raise GateError("staging record is a dry run")
    smoke = staging_record.get("smoke") or {}
    if smoke.get("status") != "pass" or smoke.get("mode") != "full":
        raise GateError(
            f"staging smoke for {sha} is {smoke.get('status')!r} (mode {smoke.get('mode')!r}); a full pass is required"
        )


# ── runner ──────────────────────────────────────────────────────────────────

Runner = Callable[[list[str], dict[str, str]], tuple[int, str]]


def subprocess_runner(argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    p = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    out = (p.stdout or "") + (p.stderr or "")
    for secret in (env.get("CLOUDFLARE_API_TOKEN"),):
        if secret:
            out = out.replace(secret, "***")
    sys.stdout.write(out[-4000:])
    return p.returncode, out


ApiCall = Callable[[str, str, str, str], dict[str, Any]]


def urllib_api(method: str, path: str, token: str, account: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{CF_API}/accounts/{account}{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(
            req, timeout=30
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # surfaced as a step failure, never swallowed
        raise StepError(
            f"Cloudflare API {method} {path} failed: {type(e).__name__}"
        ) from e


class Release:
    """One release run. dry-run prints every command; --execute runs them in order and stops at the first failure."""

    def __init__(
        self,
        cfg: dict[str, Any],
        env: str,
        sha: str,
        ledger_dir: Path,
        execute: bool,
        runner: Runner = subprocess_runner,
        api: ApiCall = urllib_api,
        workdir: Path | None = None,
        environ: dict[str, str] | None = None,
    ) -> None:
        self.cfg, self.env, self.sha, self.execute = cfg, env, sha, execute
        self.ec = env_cfg(cfg, env)
        self.ledger_dir = ledger_dir
        self.runner, self.api = runner, api
        self.workdir = workdir or (ROOT / ".tmp" / "greenjobs_release" / env)
        self.environ = dict(os.environ) if environ is None else dict(environ)
        self.record = new_record(env, sha, execute)
        self.log: list[str] = []

    # -- plumbing
    def _child_env(self) -> dict[str, str]:
        e = dict(self.environ)
        token = e.get(self.ec["api_token_env"], "")
        account = e.get(self.ec["account_id_env"], "")
        if token:
            e["CLOUDFLARE_API_TOKEN"] = token
        if account:
            e["CLOUDFLARE_ACCOUNT_ID"] = account
        return e

    def preflight(self) -> None:
        problems = check_wrangler_toml(self.cfg, self.env)
        if problems:
            raise GateError("wrangler.toml: " + "; ".join(problems))
        if not self.execute:
            return
        if self.environ.get("GREENJOBS_RELEASE_TARGET") != self.env:
            raise GateError(
                f"--execute needs GREENJOBS_RELEASE_TARGET={self.env} (guard against a live run by accident)"
            )
        ph = placeholders(self.ec)
        toml = tomllib.loads(
            (ROOT / self.cfg["worker_dir"] / "wrangler.toml").read_text(
                encoding="utf-8"
            )
        )
        for d in toml["env"][self.ec["wrangler_env"]].get("d1_databases", []):
            if "REPLACE_" in str(d.get("database_id", "")):
                ph.append(
                    f"wrangler.toml env.{self.env} database_id={d.get('database_id')}"
                )
        if ph:
            raise GateError("unresolved placeholders: " + ", ".join(ph))
        for var in (self.ec["api_token_env"], self.ec["account_id_env"]):
            if not self.environ.get(var):
                raise GateError(f"{var} is not set")

    def run(self, desc: str, argv: list[str]) -> str:
        line = " ".join(shlex.quote(a) for a in argv)
        self.log.append(line)
        print(f"[{self.env}] {desc}\n  $ {line}")
        if not self.execute:
            return DRY
        code, out = self.runner(argv, self._child_env())
        if code != 0:
            raise StepError(f"{desc} failed (exit {code})")
        return out

    def call_api(self, desc: str, method: str, path: str) -> dict[str, Any]:
        tok, acct = f"${self.ec['api_token_env']}", f"${self.ec['account_id_env']}"
        line = f'curl -fsS -X {method} -H "Authorization: Bearer {tok}" {CF_API}/accounts/{acct}{path}'
        self.log.append(line)
        print(f"[{self.env}] {desc}\n  $ {line}")
        if not self.execute:
            return {
                "success": True,
                "result": [{"id": DRY}] if method == "GET" else {"id": DRY},
            }
        res = self.api(
            method,
            path,
            self.environ.get(self.ec["api_token_env"], ""),
            self.environ.get(self.ec["account_id_env"], ""),
        )
        if not res.get("success"):
            raise StepError(f"{desc}: API answered success=false")
        return res

    def wr(self, *args: str) -> list[str]:
        return [
            *WRANGLER,
            *args,
            "--config",
            f"{self.cfg['worker_dir']}/wrangler.toml",
            "--env",
            self.ec["wrangler_env"],
        ]

    def latest_pages_deployment(self, project: str) -> str | None:
        res = self.call_api(
            f"latest production deployment of {project}",
            "GET",
            f"/pages/projects/{project}/deployments?env=production&per_page=1",
        )
        items = res.get("result") or []
        return items[0].get("id") if items else None

    # -- steps
    def apply_schema_and_migrations(self) -> None:
        mdir = ROOT / self.cfg["migrations_dir"]
        self.run(
            "D1 schema (idempotent CREATE IF NOT EXISTS)",
            self.wr(
                "d1", "execute", self.ec["d1"], "--remote", "--file", self.cfg["schema"]
            ),
        )
        self.run(
            "D1 migrations (wrangler tracks applied files; each file is idempotent)",
            self.wr("d1", "migrations", "apply", self.ec["d1"], "--remote"),
        )
        self.record["d1_migration_level"] = migration_level(mdir)

    def seed(self) -> None:
        if not self.ec.get("seed_public_jobs"):
            return
        srcs = {k: ROOT / v for k, v in self.cfg["seed_sources"].items()}
        sql, n = build_seed_sql(self.env, srcs, as_of="2026-11-20T00:00:00Z")
        self.workdir.mkdir(parents=True, exist_ok=True)
        f = self.workdir / "seed_staging.sql"
        f.write_text(sql, encoding="utf-8")
        self.run(
            f"D1 staging seed: {n} public jobs (INSERT OR IGNORE)",
            self.wr(
                "d1",
                "execute",
                self.ec["d1"],
                "--remote",
                "--file",
                str(f.relative_to(ROOT) if f.is_relative_to(ROOT) else f),
            ),
        )

    def deploy_worker(self) -> None:
        # RELEASE_SHA: GET /api/health reports which commit is serving (smoke and humans compare it to the sha)
        out = self.run(f"Worker deploy -> {self.ec['worker']}", self.wr("deploy", "--var", f"RELEASE_SHA:{self.sha}"))
        vid = DRY if not self.execute else parse_worker_version(out)
        if not vid:
            raise StepError(
                "could not read the new Worker version id from wrangler output"
            )
        self.record["worker_version_id"] = vid

    def deploy_boards(self) -> None:
        build = "execution/gtm_client_workflows/greenjobs_redesign/build_site.py"
        deploy = (
            "execution/gtm_client_workflows/greenjobs_redesign/deploy_cloudflare.sh"
        )
        for site, project in sorted(self.ec["pages"].items()):
            out_dir = self.workdir / f"site-{site}"
            rel = (
                str(out_dir.relative_to(ROOT))
                if out_dir.is_relative_to(ROOT)
                else str(out_dir)
            )
            self.run(
                f"build board {site} (both editions, canonical {self.ec['board_urls'][site]})",
                [
                    "python3",
                    build,
                    "--edition",
                    "both",
                    "--out",
                    rel,
                    "--site-base",
                    self.ec["board_urls"][site].rstrip("/") + "/",
                    "--board-site",
                    site,
                    *(["--robots-index"] if self.ec.get("robots_index") else []),
                    *(["--live-api"] if self.ec.get("live_api") else []),
                    # staging: the Worker is on its own origin (workers.dev); production: same host, no flag
                    *(["--api-base", self.ec["api_base"][site]] if (self.ec.get("api_base") or {}).get(site) else []),
                    # GA4 only in production builds; staging stays analytics-free
                    "--analytics",
                    "production" if self.ec.get("analytics") == "production" else "off",
                ],
            )
            self.run(
                f"Pages deploy {site} -> {project}", ["bash", deploy, rel, project]
            )
            self.record["pages_deployments"][site] = self.latest_pages_deployment(
                project
            )

    def record_previous(self) -> None:
        out = self.run(
            "record previous Worker version", self.wr("deployments", "status")
        )
        prev = DRY if not self.execute else parse_deployment_status(out)
        self.record["previous"]["worker_version_id"] = prev
        for site, project in sorted(self.ec["pages"].items()):
            self.record["previous"]["pages_deployments"][site] = (
                self.latest_pages_deployment(project)
            )
        out = self.run(
            "record D1 Time Travel bookmark",
            self.wr("d1", "time-travel", "info", self.ec["d1"], "--json"),
        )
        self.record["previous"]["d1_bookmark"] = (
            DRY if not self.execute else parse_time_travel_bookmark(out)
        )

    def backup_d1(self) -> None:
        if not self.ec.get("backup_bucket"):
            raise GateError(
                f"{self.env} has no backup_bucket; a promote never runs without a backup"
            )
        self.workdir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "").replace("-", "")
        name = f"d1_{self.ec['d1']}_{self.sha[:12]}_{stamp}.sql"
        local = self.workdir / name
        rel = str(local.relative_to(ROOT)) if local.is_relative_to(ROOT) else str(local)
        obj = f"{self.ec['backup_bucket']}/d1/{name}"
        try:
            self.run(
                "D1 backup (export)",
                self.wr("d1", "export", self.ec["d1"], "--remote", "--output", rel),
            )
            if self.execute:
                body = (
                    local.read_text(encoding="utf-8", errors="replace")
                    if local.exists()
                    else ""
                )
                if not re.search(r"CREATE TABLE", body, re.IGNORECASE):
                    raise GateError(
                        "D1 backup is empty or has no CREATE TABLE; refusing to migrate"
                    )
            self.run(
                "store backup in the client's R2 (holds personal data: never a CI artifact)",
                self.wr("r2", "object", "put", obj, "--file", rel, "--remote"),
            )
        finally:
            if (
                self.execute
            ):  # personal data: the R2 copy is the backup, the runner keeps nothing
                local.unlink(missing_ok=True)
        self.record["backup"] = {"object": obj, "verified": self.execute}

    def gate_migrations(self, allow_destructive: bool) -> None:
        mdir = ROOT / self.cfg["migrations_dir"]
        files = migration_files(mdir)
        out = self.run(
            "list pending D1 migrations",
            self.wr("d1", "migrations", "list", self.ec["d1"], "--remote"),
        )
        pending = files if out == DRY else pending_from_list_output(out, files)
        destructive = {
            f: destructive_statements((mdir / f).read_text(encoding="utf-8"))
            for f in pending
        }
        destructive = {f: s for f, s in destructive.items() if s}
        self.record["pending_migrations"] = pending
        self.record["destructive_migrations"] = sorted(destructive)
        if destructive and not (self.record.get("backup") or {}).get("object"):
            raise GateError("destructive migration pending and no backup recorded")
        if destructive and not allow_destructive:
            msg = "; ".join(f"{f}: {s[0]}" for f, s in destructive.items())
            if self.execute:
                raise GateError(
                    f"destructive migration(s) pending ({msg}); re-run with --allow-destructive after reading the backup line"
                )
            print(
                f"[{self.env}] GATE (would refuse on --execute): destructive migration(s) pending: {msg}"
            )

    # -- flows
    def finish(self, event: str, status: str) -> dict[str, Any]:
        self.record["status"] = status
        self.record["finished_at"] = utc_now()
        append_ledger(self.ledger_dir, event, self.record)
        return self.record

    def stage(self) -> dict[str, Any]:
        if self.env != "staging":
            raise GateError(
                "stage targets staging only; production goes through promote"
            )
        self.preflight()
        try:
            self.apply_schema_and_migrations()
            self.seed()
            self.deploy_worker()
            self.deploy_boards()
        except (StepError, GateError):
            self.finish("deploy", "failed")
            raise
        return self.finish("deploy", "deployed" if self.execute else "planned")

    def promote(
        self, staging_record: dict[str, Any] | None, allow_destructive: bool
    ) -> dict[str, Any]:
        if self.env != "production":
            raise GateError("promote targets production only")
        if staging_record is None:
            if self.execute:
                raise GateError(
                    "promote needs --staging-record (the staging deploy_record.json for this sha)"
                )
            print(
                "[production] GATE (would refuse on --execute): no --staging-record given"
            )
        else:
            verify_promotable(staging_record, self.sha)
        self.preflight()
        try:
            self.record_previous()
            self.backup_d1()
            self.gate_migrations(allow_destructive)
            self.apply_schema_and_migrations()
            self.deploy_worker()
            self.deploy_boards()
        except (StepError, GateError):
            self.finish("deploy", "failed")
            raise
        return self.finish("deploy", "deployed" if self.execute else "planned")

    def rollback(self, record: dict[str, Any]) -> dict[str, Any]:
        """Restore the recorded previous Worker version and Pages deployments of `record`."""
        self.record = record
        prev = record.get("previous") or {}
        wv, pages = prev.get("worker_version_id"), prev.get("pages_deployments") or {}
        if (
            not wv
            or wv == DRY
            or not pages
            or any(not v or v == DRY for v in pages.values())
        ):
            record["rollback"] = {
                "status": "impossible",
                "reason": "no recorded previous Worker version / Pages deployment",
            }
            self.finish("rollback", "rollback_impossible")
            raise GateError(
                "rollback target missing from the record (first deploy?); restore by hand"
            )
        self.preflight()
        done = []
        try:
            self.run(
                f"Worker rollback -> {wv}",
                self.wr(
                    "rollback",
                    wv,
                    "--message",
                    f"auto-rollback of {record['sha'][:12]}",
                    "--yes",
                ),
            )
            done.append("worker")
            for site, dep in sorted(pages.items()):
                self.call_api(
                    f"Pages rollback {site} -> {dep}",
                    "POST",
                    f"/pages/projects/{self.ec['pages'][site]}/deployments/{dep}/rollback",
                )
                done.append(f"pages:{site}")
        except (StepError, GateError):
            record["rollback"] = {"status": "partial", "done": done}
            self.finish("rollback", "rollback_failed")
            raise
        bm = prev.get("d1_bookmark")
        manual = None
        if bm:
            manual = " ".join(
                self.wr("d1", "time-travel", "restore", self.ec["d1"], "--bookmark", bm)
            )
            print(
                f"[{self.env}] D1 is NOT restored automatically (it would discard writes since the deploy). If the schema change caused the failure:\n  $ {manual}"
            )
        record["rollback"] = {
            "status": "done" if self.execute else "planned",
            "done": done,
            "d1_manual_restore": manual,
        }
        return self.finish(
            "rollback", "rolled_back" if self.execute else "rollback_planned"
        )


# ── secret scan (CI, changed files) ────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"\b(CLOUDFLARE_API_TOKEN|RESEND_API_KEY|BUILD_TOKEN|CLIENT_SECRET)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{20,}"
    ),
    re.compile(r"\bre_[A-Za-z0-9]{24,}\b"),  # Resend key shape
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),  # GitHub token shape
    re.compile(r"\bsk-[A-Za-z0-9_-]{30,}\b"),  # generic sk- API key shape
]


_DUMMY_WORDS = ("dummy", "test", "example", "fake", "placeholder", "replace")


def scan_secrets(paths: list[Path]) -> list[str]:
    hits = []
    for p in paths:
        if not p.is_file() or p.suffix in {
            ".png",
            ".jpg",
            ".webp",
            ".mp4",
            ".woff2",
            ".pdf",
        }:
            continue
        for i, line in enumerate(
            p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for rx in _SECRET_PATTERNS:
                m = rx.search(line)
                # obvious test values ("dummy-not-a-real-key", "build-token-for-tests-only") are not secrets
                if m and not any(w in m.group(0).lower() for w in _DUMMY_WORDS):
                    hits.append(f"{p}:{i}")
                    break
    return hits


# ── CLI ─────────────────────────────────────────────────────────────────────


def git_sha() -> str:
    p = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return p.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="GreenJobs release pipeline (dry-run unless --execute)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser, env_default: str | None) -> None:
        p.add_argument(
            "--env",
            default=env_default,
            choices=["staging", "production"],
            required=env_default is None,
        )
        p.add_argument(
            "--sha", default=None, help="git sha being released (default: HEAD)"
        )
        p.add_argument("--ledger-dir", type=Path, default=None)
        p.add_argument(
            "--execute",
            action="store_true",
            help="run the commands (needs GREENJOBS_RELEASE_TARGET=<env>)",
        )

    common(sub.add_parser("stage"), "staging")
    pp = sub.add_parser("promote")
    common(pp, "production")
    pp.add_argument(
        "--staging-record",
        type=Path,
        help="deploy_record.json from the staging run of this sha",
    )
    pp.add_argument("--allow-destructive", action="store_true")
    rp = sub.add_parser("rollback")
    common(rp, "production")
    rp.add_argument(
        "--record",
        type=Path,
        required=True,
        help="deploy_record.json of the deploy to undo",
    )
    sp = sub.add_parser("record-smoke")
    sp.add_argument("--ledger-dir", type=Path, required=True)
    sp.add_argument("--smoke", type=Path, required=True)
    vp = sub.add_parser("verify-promotable")
    vp.add_argument("--record", type=Path, required=True)
    vp.add_argument("--sha", required=True)
    sq = sub.add_parser("seed-sql")
    sq.add_argument("--out", type=Path, required=True)
    sq.add_argument("--as-of", default="2026-11-20T00:00:00Z")
    cc = sub.add_parser("check-config")
    cc.add_argument("--env", choices=["staging", "production"], default=None)
    ss = sub.add_parser("scan-secrets")
    ss.add_argument("files", nargs="*", type=Path)
    args = ap.parse_args(argv)
    cfg = load_config()

    try:
        if args.cmd == "check-config":
            bad = {
                e: check_wrangler_toml(cfg, e)
                for e in ([args.env] if args.env else cfg["envs"])
            }
            for e, probs in bad.items():
                print(f"{e}: {'ok' if not probs else '; '.join(probs)}")
                for ph in placeholders(env_cfg(cfg, e)):
                    print(f"{e}: placeholder (blocks --execute) {ph}")
            return 2 if any(bad.values()) else 0
        if args.cmd == "scan-secrets":
            hits = scan_secrets(args.files)
            for h in hits:
                print(f"possible secret: {h}")
            return 1 if hits else 0
        if args.cmd == "seed-sql":
            sql, n = build_seed_sql(
                "staging",
                {k: ROOT / v for k, v in cfg["seed_sources"].items()},
                args.as_of,
            )
            args.out.write_text(sql, encoding="utf-8")
            print(f"{n} public jobs -> {args.out}")
            return 0
        if args.cmd == "verify-promotable":
            verify_promotable(
                json.loads(args.record.read_text(encoding="utf-8")), args.sha
            )
            print(f"promotable: {args.sha}")
            return 0
        if args.cmd == "record-smoke":
            rec = json.loads(
                (args.ledger_dir / "deploy_record.json").read_text(encoding="utf-8")
            )
            sm = json.loads(args.smoke.read_text(encoding="utf-8"))
            rec["smoke"] = {
                "status": sm.get("status"),
                "mode": sm.get("mode"),
                "failed": [
                    c["name"] for c in sm.get("checks", []) if c.get("status") == "fail"
                ],
                "at": utc_now(),
            }
            append_ledger(args.ledger_dir, "smoke", rec)
            print(f"smoke {rec['smoke']['status']} recorded for {rec['sha']}")
            return 0

        sha = args.sha or git_sha()
        ledger_dir = args.ledger_dir or (ROOT / ".tmp" / "greenjobs_release" / args.env)
        rel = Release(cfg, args.env, sha, ledger_dir, args.execute)
        if not args.execute:
            print(
                "DRY RUN: nothing is called. Add --execute (and GREENJOBS_RELEASE_TARGET) to run.\n"
            )
        if args.cmd == "stage":
            if args.execute and git_sha() != sha:
                raise GateError(
                    f"checked-out HEAD {git_sha()} is not the staged sha {sha}"
                )
            rel.stage()
        elif args.cmd == "promote":
            srec = (
                json.loads(args.staging_record.read_text(encoding="utf-8"))
                if args.staging_record
                else None
            )
            if args.execute and git_sha() != sha:
                raise GateError(
                    f"checked-out HEAD {git_sha()} is not the promoted sha {sha}"
                )
            rel.promote(srec, args.allow_destructive)
        elif args.cmd == "rollback":
            rel.rollback(json.loads(args.record.read_text(encoding="utf-8")))
        print(f"\nrecord: {ledger_dir / 'deploy_record.json'}")
        return 0
    except GateError as e:
        print(f"GATE: {e}", file=sys.stderr)
        return 3
    except StepError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
