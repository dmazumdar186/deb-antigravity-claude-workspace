"""Shared constants and helpers for the GreenJobs ops scripts (redirects, DNS watcher, probe, metrics).

description: One place for the 10 domains, canonical hosts, the sector-domain
  forwards, the zone-inventory baseline (MX + SPF), a DNS-over-HTTPS resolver
  with an injectable transport, atomic JSON/JSONL writes and the site route set
  (built from build_site.py's own vocabulary, never copied).
inputs: none (library)
outputs: none (library)
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REDESIGN = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REDESIGN))

import build_site  # noqa: E402  (vocabulary source: TAXONOMY, slugify, LANDINGS, PAGES_FOR_SITEMAP, CONTRACT_LABEL)

MIGRATION = REPO / "deliverables" / "greenjobs_migration_2026-11-06" / "build"
INVENTORY_JSON = MIGRATION / "dns" / "zone_inventory_2026-11-20.json"
REDIRECT_MAP = MIGRATION / "live_snapshot_2026-11-20" / "redirect_map.json"
SITE_SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
GENERATED = HERE / "generated"
STATE_DIR = (
    REPO / ".tmp" / "greenjobs_ops"
)  # scratch: state, outbox, ledger, probe log (never committed)

BOARDS = {"ie": "greenjobs.ie", "uk": "greenjobs.co.uk"}
CANONICAL = {"ie": "https://www.greenjobs.ie", "uk": "https://www.greenjobs.co.uk"}
# Sector domain -> the canonical sector it forwards to on greenjobs.co.uk (/sectors/<slug>/).
# The sector NAME is checked against build_site.TAXONOMY at import (build-time assertion).
SECTOR_DOMAINS = {
    "conservationjobsuk.com": "Ecology, nature recovery & biodiversity",
    "ecologyjobsuk.com": "Ecology, nature recovery & biodiversity",
    "environmentaljobsuk.com": "Environmental science & consulting",
    "renewableenergyjobsuk.com": "Renewable energy & storage",
    "windjobsuk.com": "Wind energy",
    "solarjobsuk.com": "Solar energy",
    "wastejobsuk.com": "Waste & circular economy",
    "waterjobsuk.com": "Water & flood",
}
NOT_A_DOMAIN = "renewablejobsuk.com"  # NXDOMAIN (ZONE_INVENTORY §4.1); never watched, never redirected
DOMAINS = list(BOARDS.values()) + list(SECTOR_DOMAINS)
# Sold scope (engagement record 2026-11-20 §2 P11): the two boards. The 8 network domains are "quoted
# separately": their forwards are prepared config only and never part of the go/no-go gate.
CORE_DOMAINS = list(BOARDS.values())


def scope_of(host_or_domain: str) -> str:
    d = host_or_domain.lower().removeprefix("www.")
    return "core" if d in CORE_DOMAINS else "optional"
_TAX_NAMES = [t[0] for t in build_site.TAXONOMY]
assert len(DOMAINS) == 10 and NOT_A_DOMAIN not in DOMAINS
assert all(
    s in _TAX_NAMES for s in SECTOR_DOMAINS.values()
), "SECTOR_DOMAINS names a sector build_site.TAXONOMY lacks"

FILTER_KEYS = ("sector", "region", "type", "employer")


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_iso(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def sector_slug(name: str) -> str:
    return build_site.slugify(name)


def expected_host(domain: str) -> str:
    """Host a domain (apex or www) must finally answer 200 on."""
    if domain == BOARDS["ie"]:
        return urllib.parse.urlsplit(CANONICAL["ie"]).hostname or ""
    return urllib.parse.urlsplit(CANONICAL["uk"]).hostname or ""


def sector_forward_path(domain: str) -> str:
    return f"/sectors/{sector_slug(SECTOR_DOMAINS[domain])}/"


# ---------------------------------------------------------------- files


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomic write: a crash never leaves a half state file (idempotent re-runs read a whole file or none)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for ln in lines:
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue  # a torn last line from a killed run is skipped, not fatal
    return out


# ---------------------------------------------------------------- DNS

Fetch = Callable[[str, dict[str, str], float], tuple[int, bytes]]
DOH_URL = "https://cloudflare-dns.com/dns-query"


def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "GreenJobsOps/1.0", **headers}
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout
        ) as r:  # noqa: S310 (https only, fixed host)
            return r.status, r.read(1_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""


def doh(
    name: str, rtype: str, fetch: Fetch = http_get, timeout: float = 8.0
) -> dict[str, Any]:
    """{'ok': bool, 'status': rcode|None, 'data': [answer strings of rtype]}; never raises."""
    url = f"{DOH_URL}?name={urllib.parse.quote(name)}&type={rtype}"
    try:
        code, body = fetch(url, {"Accept": "application/dns-json"}, timeout)
        if code != 200:
            return {"ok": False, "status": None, "data": [], "error": f"HTTP {code}"}
        js = json.loads(body.decode("utf-8"))
    except (
        Exception
    ) as e:  # timeout, DNS, TLS, bad JSON: the caller marks the domain "unknown", never "changed"
        return {"ok": False, "status": None, "data": [], "error": type(e).__name__}
    status = js.get("Status")
    if status not in (0, 3):  # SERVFAIL / REFUSED: unknown, not empty
        return {"ok": False, "status": status, "data": [], "error": f"rcode {status}"}
    want = {"NS": 2, "MX": 15, "TXT": 16, "A": 1, "AAAA": 28, "CNAME": 5}.get(rtype)
    data = [
        a.get("data", "")
        for a in js.get("Answer") or []
        if want is None or a.get("type") == want
    ]
    return {"ok": True, "status": status, "data": data}


def norm_host(h: str) -> str:
    return h.strip().lower().rstrip(".")


def norm_mx(values: list[str]) -> list[str]:
    out = []
    for v in values:
        parts = v.split()
        if len(parts) == 2:
            out.append(f"{int(parts[0])} {norm_host(parts[1])}")
    return sorted(set(out))


def txt_join(v: str) -> str:
    """'"v=spf1 a" "b"' -> 'v=spf1 ab' (DNS splits long TXT into quoted 255-byte strings)."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', v)
    return "".join(parts) if parts else v.strip()


def spf_of(txts: list[str]) -> list[str]:
    return sorted(
        {
            re.sub(r"\s+", " ", txt_join(t)).strip()
            for t in txts
            if txt_join(t).lower().startswith("v=spf1")
        }
    )


def inventory_baseline(path: Path = INVENTORY_JSON) -> dict[str, dict[str, list[str]]]:
    """{domain: {'mx': [...], 'spf': [...], 'ns': [...]}} from the 2026-11-20 public zone inventory."""
    inv = read_json(path)
    by = {d["domain"]: d.get("dns", {}) for d in inv["domains"]}
    out = {}
    for dom in DOMAINS:
        dns = by.get(dom, {})

        def ans(key: str, rtype: str) -> list[str]:
            return [
                a["data"]
                for a in dns.get(key, {}).get("answers", [])
                if a.get("type") == rtype
            ]

        out[dom] = {
            "mx": norm_mx(ans(f"{dom}|MX", "MX")),
            "spf": spf_of(ans(f"{dom}|TXT", "TXT")),
            "ns": sorted(norm_host(x) for x in ans(f"{dom}|NS", "NS")),
        }
    return out


# ---------------------------------------------------------------- the new site's route set


def region_table(ed: str) -> dict[str, Any]:
    return build_site.load_region_table(SITE_SRC, ed)


def region_slugs(ed: str) -> dict[str, str]:
    """slug of a region name or alias -> slug of the canonical region (Worker lstRegion lookup)."""
    out: dict[str, str] = {}
    for name, aliases in region_table(ed)["regions"].items():
        canon = build_site.slugify(name)
        for a in [name, *aliases]:
            out.setdefault(build_site.slugify(a), canon)
    return out


def employer_slugs(ed: str, extra: list[str] | None = None) -> set[str]:
    names = [
        c["name"] for c in read_json(SITE_SRC / "data" / f"clients_{ed}.json", [])
    ] + list(extra or [])
    return {build_site.slugify(n) for n in names if n}


def vocab(ed: str, employers: list[str] | None = None) -> dict[str, set[str]]:
    return {
        "sector": {sector_slug(n) for n in _TAX_NAMES},
        "region": {build_site.slugify(r) for r in region_table(ed)["regions"]},
        "type": set(build_site.CONTRACT_LABEL),
        "employer": employer_slugs(ed, employers),
    }


def static_routes(ed: str) -> set[str]:
    paths = {"/"} | {
        "/" + p[: -len("index.html")] for p in build_site.PAGES_FOR_SITEMAP
    }
    paths |= {f"/{spec['slug']}/" for spec in build_site.LANDINGS[ed]}
    paths |= {f"/sectors/{sector_slug(n)}/" for n in _TAX_NAMES}
    return paths


class Routes:
    """Paths the new site serves on one board. Static set from build_site (override with a published
    route list), /jobs/<id>/ only for live ids, /jobs/?k=v only for keys in FILTER_KEYS and values in vocab.
    """

    def __init__(
        self,
        ed: str,
        live_ids: set[str],
        static: set[str] | None = None,
        employers: list[str] | None = None,
    ):
        self.ed = ed
        self.static = set(static) if static is not None else static_routes(ed)
        self.live_ids = {str(i) for i in live_ids}
        self.vocab = vocab(ed, employers)

    def serves(self, url: str) -> bool:
        u = urllib.parse.urlsplit(url)
        if u.scheme or u.netloc:
            if f"{u.scheme}://{u.netloc}" != CANONICAL[self.ed]:
                return False
        path, query = u.path, u.query
        if not query:
            if path in self.static:
                return True
            m = re.fullmatch(r"/jobs/([A-Za-z0-9_-]+)/", path)
            return bool(m and m.group(1) in self.live_ids)
        if path != "/jobs/":
            return False
        q = urllib.parse.parse_qs(query, keep_blank_values=True)
        if not q or any(k not in FILTER_KEYS or len(v) != 1 for k, v in q.items()):
            return False
        return all(v[0] in self.vocab[k] for k, v in q.items())
