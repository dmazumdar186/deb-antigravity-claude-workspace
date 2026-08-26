"""
instantly_guard -- cron-able bounce/deliverability guard for one Instantly campaign.

purpose: keep a campaign's bounce rate down without manual babysitting. Each run
         (a) finds bounces new since the last run, (b) blocklists their domains
         workspace-wide, (c) MX-screens leads that have NOT been contacted yet,
         (d) deletes leads whose domain cannot receive mail, (e) writes a dated log.

inputs:  CLI: campaign_id (positional); --no-dry-run (default is DRY RUN),
              --api-key-env (default INSTANTLY_NOTIFIER_API_KEY), --state-file,
              --log-dir (default ./logs), --dns-timeout, --workers, --env-file
         env: the API key named by --api-key-env, read from environment or --env-file

outputs: JSON summary on stdout; dated log at
         <log-dir>/instantly_guard_<campaign8>_<date>.log; state at <state-file>
         (per-campaign last_run + seen bounce ids + blocklisted domains)

notes:   NEVER activates or resumes a campaign, and never edits campaign settings.
         Deletion is restricted to not-yet-contacted leads on provably dead domains.
         Resolver errors (timeout/SERVFAIL) are NEVER treated as dead.

deps:    none required. dnspython is used when importable AND port 53 works;
         otherwise the script falls back to DNS-over-HTTPS automatically.
         NOTE: on Windows the `py` launcher honours this file's shebang, so
         `py instantly_guard.py` may run a DIFFERENT interpreter than `py -m pip`
         installed into. `py -3.14 instantly_guard.py` pins it explicitly.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

try:
    import dns.exception
    import dns.resolver
    HAVE_DNSPYTHON = True
except ImportError:
    # Not fatal: the DoH backend below needs no third-party package. Two real
    # traps on this machine made the hard dependency a liability --
    #   1. the Windows `py` launcher honours a script's shebang, so `py foo.py`
    #      and `py -c` can run DIFFERENT interpreters, and `pip install` may
    #      have landed in the other one;
    #   2. some networks block outbound port 53 entirely, which makes dnspython
    #      time out on every domain and look like "every domain is dead".
    HAVE_DNSPYTHON = False

BASE_URL = "https://api.instantly.ai/api/v2"
# Instantly fronts the API with Cloudflare, which 403s (error 1010) on urllib's
# default User-Agent. A real UA string is required, not optional.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) instantly-guard/1.0"

LEAD_STATUS = {1: "Active", 2: "Paused", 3: "Completed",
               -1: "Bounced", -2: "Unsubscribed", -3: "Skipped"}

CAMPAIGN_STATUS = {0: "Draft", 1: "Active", 2: "Paused", 3: "Completed",
                   4: "Running Subsequences", -1: "Accounts Unhealthy",
                   -2: "Bounce Protect", -99: "Account Suspended"}

# Verdicts that prove the domain cannot accept mail. Anything else is left alone.
DEAD_VERDICTS = ("NXDOMAIN", "NO_MX", "NULL_MX")

BULK_BLOCKLIST_MAX = 1000   # documented API cap
BULK_DELETE_MAX = 10000     # documented API cap

_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)


# --------------------------------------------------------------------------- env


def load_env_file(path: Path) -> dict:
    """Parse a .env file into a plain dict. Returns {} if the file is absent.

    python-dotenv is used when available (workspace convention), but this script
    deliberately keeps a dependency-free fallback: see the shebang/interpreter
    note in the module docstring -- a package installed for one interpreter is
    not necessarily importable by the one that ends up running this file.
    """
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(path).items() if v is not None}
    except ImportError:
        pass  # fall through to the built-in parser below
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def resolve_api_key(env_var: str, env_file: Path | None) -> str:
    key = os.environ.get(env_var, "").strip()
    if not key and env_file:
        key = load_env_file(env_file).get(env_var, "").strip()
    if not key:
        raise SystemExit(f"FATAL: {env_var} not set in environment or env file.")
    return key


# --------------------------------------------------------------------------- api


class Instantly:
    """Thin Instantly v2 client. Retries transient failures; never logs the key."""

    def __init__(self, api_key: str, timeout: int = 45, retries: int = 3):
        self._key = api_key
        self.timeout = timeout
        self.retries = retries
        self.calls = 0

    def call(self, method: str, path: str, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": f"Bearer {self._key}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if data is not None:
            # Only declare a JSON body when one exists. Instantly runs Fastify,
            # which rejects Content-Type: application/json with an empty body as
            # 400 FST_ERR_CTP_EMPTY_JSON_BODY -- this silently breaks every
            # bodyless DELETE /leads/{id}.
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{BASE_URL}{path}", data=data,
                                     method=method, headers=headers)
        for attempt in range(self.retries):
            try:
                self.calls += 1
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                    return resp.status, (json.loads(raw) if raw.strip() else {})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return exc.code, detail
            except OSError as exc:
                # Transient socket/DNS failure. Retried with backoff, then surfaced
                # to the caller as a None status -- never swallowed.
                if attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None, f"{type(exc).__name__}: {exc}"
        return None, "exhausted retries"

    def expect(self, method: str, path: str, body=None):
        status, payload = self.call(method, path, body)
        if status != 200:
            raise SystemExit(f"FATAL: {method} {path} -> HTTP {status}: {str(payload)[:300]}")
        return payload

    def list_leads(self, campaign_id: str, lead_filter: str | None = None) -> list[dict]:
        leads: list[dict] = []
        cursor, pages = None, 0
        while True:
            body = {"campaign": campaign_id, "limit": 100}
            if lead_filter:
                body["filter"] = lead_filter
            if cursor:
                body["starting_after"] = cursor
            payload = self.expect("POST", "/leads/list", body)
            items = payload.get("items", [])
            leads.extend(items)
            cursor = payload.get("next_starting_after")
            pages += 1
            if not cursor or not items:
                break
            if pages > 500:
                raise SystemExit("FATAL: pagination guard tripped at 500 pages")
        return leads

    def already_blocklisted(self, candidates: list[str]) -> set[str]:
        """Return the subset of candidates already present on the blocklist."""
        present = set()
        for domain in candidates:
            query = urllib.parse.quote(domain, safe="")
            status, payload = self.call(
                "GET", f"/block-lists-entries?domains_only=true&search={query}")
            if status == 200 and isinstance(payload, dict):
                for item in payload.get("items", []):
                    if (item.get("bl_value") or "").lower() == domain:
                        present.add(domain)
        return present


# --------------------------------------------------------------------------- dns


DOH_ENDPOINTS = ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve")
DNS_RCODE_NOERROR = 0
DNS_RCODE_NXDOMAIN = 3
DNS_TYPE_A = 1
DNS_TYPE_MX = 15


class MxScreen:
    """Thread-safe, cached MX classifier with two interchangeable backends.

    backend "system": dnspython over UDP/TCP port 53.
    backend "doh":    DNS-over-HTTPS (no third-party dep, works where 53 is blocked).
    backend "auto":   probe a known-good domain over port 53; fall back to DoH.

    A resolver failure is NEVER reported as a dead domain -- it gets an ERROR_*
    verdict so the caller can exclude it from deletion.
    """

    PROBE_DOMAIN = "cloudflare.com"

    def __init__(self, timeout: float = 10.0, backend: str = "auto"):
        self._cache: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()
        self.timeout = timeout
        self._resolver = None
        self.backend = self._select_backend(backend)

    def _select_backend(self, requested: str) -> str:
        if requested == "doh":
            return "doh"
        if requested == "system":
            if not HAVE_DNSPYTHON:
                raise SystemExit("FATAL: --resolver system needs dnspython. "
                                 "Run: pip install dnspython (into the interpreter "
                                 "that will RUN this script -- see module docstring).")
            self._init_resolver()
            return "system"
        # auto: only trust port 53 if it actually answers a known-good query
        if HAVE_DNSPYTHON:
            self._init_resolver()
            try:
                self._resolver.resolve(self.PROBE_DOMAIN, "MX")
                return "system"
            except dns.exception.DNSException:
                pass  # port 53 unusable here; DoH below
        return "doh"

    def _init_resolver(self) -> None:
        self._resolver = dns.resolver.Resolver()
        self._resolver.timeout = self.timeout
        self._resolver.lifetime = self.timeout

    # -- backends ----------------------------------------------------------

    def _classify_system(self, domain: str) -> tuple[str, str]:
        try:
            answer = self._resolver.resolve(domain, "MX")
            hosts = sorted(str(r.exchange).rstrip(".") or "." for r in answer)
            if hosts == ["."]:
                return ("NULL_MX", ".")            # RFC 7505: refuses all mail
            if not hosts:
                return ("NO_MX", "")
            return ("OK", ";".join(hosts))
        except dns.resolver.NXDOMAIN:
            return ("NXDOMAIN", "")
        except dns.resolver.NoAnswer:
            return ("NO_MX", "")
        except dns.resolver.NoNameservers as exc:
            # SERVFAIL / broken delegation. Not proof the domain refuses mail.
            return ("ERROR_SERVFAIL", str(exc)[:100])
        except dns.resolver.LifetimeTimeout:
            return ("ERROR_TIMEOUT", "")
        except dns.exception.DNSException as exc:
            return ("ERROR_OTHER", f"{type(exc).__name__}: {exc}"[:100])
        except OSError as exc:
            # dnspython does not wrap every socket-layer failure. Unwrapped, this
            # propagates through ThreadPoolExecutor.map and kills the whole run.
            # Downgraded to a non-deletable verdict so one bad domain cannot take
            # out the screen.
            return ("ERROR_OTHER", f"{type(exc).__name__}: {exc}"[:100])

    def _doh_query(self, domain: str, rrtype: str) -> tuple[int, list[str]]:
        want = DNS_TYPE_MX if rrtype == "MX" else DNS_TYPE_A
        last = "no endpoint tried"
        for base in DOH_ENDPOINTS:
            url = f"{base}?{urllib.parse.urlencode({'name': domain, 'type': rrtype})}"
            req = urllib.request.Request(
                url, headers={"accept": "application/dns-json", "User-Agent": USER_AGENT})
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        payload = json.loads(resp.read().decode("utf-8", "replace"))
                    return payload.get("Status"), [
                        a.get("data", "") for a in payload.get("Answer", [])
                        if a.get("type") == want
                    ]
                except (urllib.error.HTTPError, OSError, json.JSONDecodeError) as exc:
                    last = f"{type(exc).__name__}: {exc}"
                    if attempt == 0:
                        time.sleep(1)
        raise OSError(f"all DoH endpoints failed ({last})")

    def _classify_doh(self, domain: str) -> tuple[str, str]:
        try:
            status, answers = self._doh_query(domain, "MX")
            if status == DNS_RCODE_NXDOMAIN:
                return ("NXDOMAIN", "")
            if status != DNS_RCODE_NOERROR:
                return (f"ERROR_RCODE_{status}", "")
            if not answers:
                # NOERROR + no MX. Confirm the domain exists before judging it.
                a_status, _ = self._doh_query(domain, "A")
                return ("NXDOMAIN", "") if a_status == DNS_RCODE_NXDOMAIN else ("NO_MX", "")
            hosts = sorted(a.split(" ", 1)[-1].rstrip(".") or "." for a in answers)
            return ("NULL_MX", ".") if hosts == ["."] else ("OK", ";".join(hosts))
        except OSError as exc:
            return ("ERROR_RESOLVER", str(exc)[:100])

    # -- public ------------------------------------------------------------

    def classify(self, domain: str) -> tuple[str, str]:
        with self._lock:
            hit = self._cache.get(domain)
        if hit is not None:
            return hit
        result = (self._classify_system(domain) if self.backend == "system"
                  else self._classify_doh(domain))
        with self._lock:
            self._cache[domain] = result
        return result

    def screen(self, domains: list[str], workers: int = 10) -> dict[str, tuple[str, str]]:
        if not domains:
            return {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            verdicts = list(pool.map(self.classify, domains))
        return dict(zip(domains, verdicts))


# ------------------------------------------------------------------------- state


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {"campaigns": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARN: state file unreadable ({exc}); starting fresh.", file=sys.stderr)
        return {"campaigns": {}}


def save_state(path: Path, state: dict) -> None:
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic swap; a killed run never leaves a half-written state


# ------------------------------------------------------------------------- utils


def domain_of(email: str) -> str | None:
    """Extract a validated domain, or None if the address is not usable.

    An empty local part ("@example.com") is malformed and must NOT yield a
    domain: a single garbage address would otherwise blocklist a real company
    across every campaign in the workspace.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return None
    local, domain = email.rsplit("@", 1)
    if not local.strip():
        return None
    domain = domain.strip()
    return domain if _DOMAIN_RE.match(domain) else None


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# --------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> dict:
    started = datetime.now(timezone.utc)
    api = Instantly(resolve_api_key(args.api_key_env, args.env_file))

    campaign = api.expect("GET", f"/campaigns/{args.campaign_id}")
    state = load_state(args.state_file)
    cstate = state.setdefault("campaigns", {}).setdefault(args.campaign_id, {})
    seen_bounces = set(cstate.get("seen_bounce_ids", []))
    known_blocked = {d.lower() for d in cstate.get("blocklisted_domains", [])}

    summary = {
        "run_at": started.isoformat(),
        "campaign_id": args.campaign_id,
        "campaign_name": campaign.get("name"),
        "campaign_status": campaign.get("status"),
        "campaign_status_label": CAMPAIGN_STATUS.get(campaign.get("status"), "Unknown"),
        "dry_run": args.dry_run,
        "previous_run": cstate.get("last_run"),
    }

    # (a) bounces new since the last run -------------------------------------
    bounced = api.list_leads(args.campaign_id, "FILTER_VAL_BOUNCED")
    new_bounces = [lead for lead in bounced if lead.get("id") not in seen_bounces]
    summary["bounced_total"] = len(bounced)
    summary["bounced_new"] = len(new_bounces)

    # (b) blocklist their domains --------------------------------------------
    new_domains = sorted({d for d in (domain_of(l.get("email", "")) for l in new_bounces) if d})
    to_block = [d for d in new_domains if d not in known_blocked]
    if to_block:
        already = api.already_blocklisted(to_block)
        to_block = [d for d in to_block if d not in already]
        known_blocked |= already
    summary["bounced_domains_new"] = new_domains
    summary["domains_to_blocklist"] = to_block

    blocked_ok: list[str] = []
    if to_block and not args.dry_run:
        for batch in chunked(to_block, BULK_BLOCKLIST_MAX):
            payload = api.expect("POST", "/block-lists-entries/bulk-create",
                                 {"bl_values": batch})
            blocked_ok.extend(item.get("bl_value") for item in payload.get("items", []))
        known_blocked |= {d.lower() for d in blocked_ok if d}
    summary["blocklisted"] = blocked_ok
    summary["would_blocklist"] = len(to_block) if args.dry_run else 0

    # (c) MX-screen leads not yet contacted ----------------------------------
    pending = api.list_leads(args.campaign_id, "FILTER_VAL_NOT_CONTACTED")
    # Defence in depth: do NOT trust the upstream filter's name. Independently
    # exclude anything showing evidence of having been contacted -- status
    # Completed/Bounced, or any populated last-contact timestamp (an "Active"
    # lead can still be mid-sequence and already emailed). A contacted lead
    # cannot bounce again, so deleting it destroys send history for zero
    # deliverability gain. Added 2026-08-26 after an audit found the live
    # cleanup had removed 4 already-contacted leads via an ad-hoc script.
    pre_filter = len(pending)
    pending = [lead for lead in pending
               if lead.get("status") not in (-1, 3)
               and not lead.get("timestamp_last_contact")]
    summary["pending_excluded_as_contacted"] = pre_filter - len(pending)
    by_domain: dict[str, list[dict]] = collections.defaultdict(list)
    unparseable = 0
    for lead in pending:
        domain = domain_of(lead.get("email", ""))
        if domain:
            by_domain[domain].append(lead)
        else:
            unparseable += 1

    screen = MxScreen(args.dns_timeout, args.resolver)
    verdicts = screen.screen(sorted(by_domain), args.workers)
    tally = collections.Counter(verdict for verdict, _ in verdicts.values())
    summary["resolver_backend"] = screen.backend
    summary["not_contacted"] = len(pending)
    summary["unparseable_emails"] = unparseable
    summary["domains_screened"] = len(verdicts)
    summary["dns_verdicts"] = dict(tally)

    # (d) delete leads on provably-dead domains ------------------------------
    dead_domains = sorted(d for d, (verdict, _) in verdicts.items() if verdict in DEAD_VERDICTS)
    dead_leads = [lead for domain in dead_domains for lead in by_domain[domain]]
    summary["dead_domains"] = [
        {"domain": d, "verdict": verdicts[d][0], "leads": len(by_domain[d])}
        for d in dead_domains
    ]
    summary["dead_leads"] = len(dead_leads)

    deleted = 0
    if dead_leads and not args.dry_run:
        ids = [lead["id"] for lead in dead_leads if lead.get("id")]
        for batch in chunked(ids, BULK_DELETE_MAX):
            payload = api.expect("DELETE", "/leads",
                                 {"campaign_id": args.campaign_id, "ids": batch})
            deleted += int(payload.get("count") or 0)
    summary["deleted"] = deleted
    summary["would_delete"] = len(dead_leads) if args.dry_run else 0

    remaining = api.list_leads(args.campaign_id)
    distribution = collections.Counter(lead.get("status") for lead in remaining)
    summary["remaining_leads"] = len(remaining)
    summary["remaining_status_distribution"] = {
        LEAD_STATUS.get(code, str(code)): count for code, count in distribution.items()
    }
    summary["api_calls"] = api.calls
    summary["elapsed_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)

    # (e) dated log + state ---------------------------------------------------
    args.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.log_dir / (
        f"instantly_guard_{args.campaign_id[:8]}_{started.strftime('%Y-%m-%d')}.log"
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary) + "\n")
    summary["log_file"] = str(log_path)

    if args.dry_run:
        summary["state_file"] = "(not written -- dry run)"
    else:
        cstate["last_run"] = started.isoformat()
        cstate["seen_bounce_ids"] = sorted(
            seen_bounces | {lead["id"] for lead in bounced if lead.get("id")})
        cstate["blocklisted_domains"] = sorted(known_blocked)
        save_state(args.state_file, state)
        summary["state_file"] = str(args.state_file)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounce/deliverability guard for one Instantly campaign. "
                    "Defaults to DRY RUN -- pass --no-dry-run to apply changes.")
    parser.add_argument("campaign_id", help="Instantly campaign UUID")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                        help="actually blocklist and delete (default: dry run only)")
    parser.set_defaults(dry_run=True)
    parser.add_argument("--api-key-env", default="INSTANTLY_NOTIFIER_API_KEY",
                        help="env var holding the API key "
                             "(default: INSTANTLY_NOTIFIER_API_KEY)")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="fallback .env file to read the key from (default: ./.env)")
    parser.add_argument("--state-file", type=Path,
                        default=Path(".instantly_guard_state.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--dns-timeout", type=float, default=10.0)
    parser.add_argument("--resolver", choices=("auto", "system", "doh"), default="auto",
                        help="MX lookup backend. auto (default) probes port 53 and "
                             "falls back to DNS-over-HTTPS when it is blocked.")
    parser.add_argument("--workers", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2))
    if args.dry_run and (summary["would_blocklist"] or summary["would_delete"]):
        print(
            f"WARNING: DRY RUN -- {summary['would_blocklist']} domain(s) and "
            f"{summary['would_delete']} lead(s) were identified but NOTHING WAS "
            f"CHANGED and no state was saved. If this is a cron, it is a no-op "
            f"loop: add --no-dry-run.",
            file=sys.stderr,
        )
    mode = "DRY RUN -- nothing changed" if args.dry_run else "APPLIED"
    print(
        f"\n[{mode}] campaign={summary['campaign_name']!r} "
        f"status={summary['campaign_status_label']} "
        f"new_bounces={summary['bounced_new']} "
        f"blocklist={summary['would_blocklist'] or len(summary['blocklisted'])} "
        f"dead_leads={summary['dead_leads']} "
        f"deleted={summary['would_delete'] or summary['deleted']} "
        f"remaining={summary['remaining_leads']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
