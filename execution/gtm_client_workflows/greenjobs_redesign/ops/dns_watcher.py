"""GreenJobs DNS watcher: nameserver move to Cloudflare, with mail records held to the inventory.

description: Each run reads NS, MX and TXT for the 10 domains over public
  DNS-over-HTTPS and compares them with the target state: nameservers on
  Cloudflare (*.ns.cloudflare.com) and MX + SPF identical to the 2026-11-20
  zone inventory. When a domain first reaches the target it drafts one short
  "done, checked" email to Diana (outbox; live only with --send). Any MX or
  SPF difference from the inventory drafts an operator alert and exits 2
  (fail loud); a lookup that fails 6 runs in a row also alerts. Idempotent:
  a domain is announced to Diana once, a given drift once (a new drift alerts
  again), and an unchanged run rewrites nothing but the timestamps.
inputs: [--state-dir DIR] [--send] [--baseline JSON] [--domains d1,d2]
  env (only with --send): RESEND_API_KEY, OPS_MAIL_FROM, DIANA_EMAIL, OPS_ALERT_EMAIL
outputs: <state>/dns_state.json, <state>/outbox.jsonl, <state>/cost_ledger.jsonl (live only);
  stdout one line per domain; exit 0 ok, 2 mail drift or persistent lookup failure
Schedule: every 10 minutes (SYNTHESIS §3), e.g. a GitHub Actions cron or the operator's machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from notify import Notifier  # noqa: E402

CF_NS_SUFFIX = ".ns.cloudflare.com"
LOOKUP_FAIL_ALERT_AFTER = 6  # consecutive failed runs (1 h at a 10-minute cadence)

DIANA_SUBJECT = "{domain}: move done and checked"
DIANA_BODY = """Hi Diana,

{domain} now points to Cloudflare. I checked it from public DNS at {checked} UTC: the email settings (MX and SPF) are the same as before, so mail is unaffected.

Nothing else is needed for this domain.

Debanjan
Founder, ProdCraft
debanjan@prodcraft.fyi
"""
ALERT_SUBJECT = "GreenJobs ALERT: mail records differ on {domain}"
ALERT_BODY = """Mail DNS on {domain} differs from the 2026-11-20 inventory.

MX expected: {mx_want}
MX observed: {mx_got}
SPF expected: {spf_want}
SPF observed: {spf_got}
Nameservers: {ns}
Checked: {checked} UTC

Runbook: deliverables/greenjobs_migration_2026-11-06/build/CUTOVER_RUNBOOK.md (rollback section).
"""
LOOKUP_SUBJECT = "GreenJobs ALERT: DNS lookups failing for {domain}"
LOOKUP_BODY = "Public DNS lookups for {domain} have failed {n} runs in a row (last error: {err}). Checked: {checked} UTC.\n"


def check_domain(
    dom: str, base: dict[str, list[str]], fetch: C.Fetch
) -> dict[str, Any]:
    ns, mx, txt = (C.doh(dom, t, fetch) for t in ("NS", "MX", "TXT"))
    if not (ns["ok"] and mx["ok"] and txt["ok"]):
        err = next(r.get("error") for r in (ns, mx, txt) if not r["ok"])
        return {"lookup_ok": False, "error": err}
    got_ns = sorted(C.norm_host(x) for x in ns["data"])
    got_mx, got_spf = C.norm_mx(mx["data"]), C.spf_of(txt["data"])
    return {
        "lookup_ok": True,
        "ns": got_ns,
        "mx": got_mx,
        "spf": got_spf,
        "on_cloudflare": bool(got_ns) and all(n.endswith(CF_NS_SUFFIX) for n in got_ns),
        "mx_ok": got_mx == base["mx"],
        "spf_ok": got_spf == base["spf"],
    }


def run(
    state_dir: Path,
    fetch: C.Fetch | None = None,
    send: bool = False,
    baseline: dict[str, Any] | None = None,
    domains: list[str] | None = None,
    notifier: Notifier | None = None,
) -> dict[str, Any]:
    base = baseline or C.inventory_baseline()
    nt = notifier or Notifier(state_dir, send=send)
    path = Path(state_dir) / "dns_state.json"
    state = C.read_json(path, {}) or {}
    doms = state.setdefault("domains", {})
    checked = C.now_iso()
    events: list[str] = []
    loud = False
    for dom in domains or C.DOMAINS:
        st = doms.setdefault(
            dom,
            {
                "status": "pending",
                "notified_at": None,
                "fail_streak": 0,
                "last_drift": None,
            },
        )
        r = check_domain(dom, base[dom], fetch or C.http_get)
        st["last_checked"] = checked
        if not r["lookup_ok"]:
            st["fail_streak"] = st.get("fail_streak", 0) + 1
            st["last_error"] = r["error"]
            if st["fail_streak"] >= LOOKUP_FAIL_ALERT_AFTER:
                loud = True
                st["fail_since"] = st.get("fail_since") or checked
                key = f"lookup-fail:{dom}:{st['fail_since']}"
                nt.queue(
                    key,
                    "OPS_ALERT_EMAIL",
                    LOOKUP_SUBJECT.format(domain=dom),
                    LOOKUP_BODY.format(
                        domain=dom, n=st["fail_streak"], err=r["error"], checked=checked
                    ),
                    "ops_alert",
                    LOOKUP_BODY,
                )
            events.append(
                f"{dom}: lookup failed ({r['error']}), streak {st['fail_streak']}"
            )
            continue
        st.update(
            {
                "fail_streak": 0,
                "fail_since": None,
                "ns": r["ns"],
                "mx_ok": r["mx_ok"],
                "spf_ok": r["spf_ok"],
                "on_cloudflare": r["on_cloudflare"],
            }
        )
        if not (r["mx_ok"] and r["spf_ok"]):
            loud = True
            fp = hashlib.sha256(json.dumps([r["mx"], r["spf"]]).encode()).hexdigest()[
                :16
            ]
            res = nt.queue(
                f"mail-drift:{dom}:{fp}",
                "OPS_ALERT_EMAIL",
                ALERT_SUBJECT.format(domain=dom),
                ALERT_BODY.format(
                    domain=dom,
                    mx_want=base[dom]["mx"],
                    mx_got=r["mx"],
                    spf_want=base[dom]["spf"],
                    spf_got=r["spf"],
                    ns=r["ns"],
                    checked=checked,
                ),
                "ops_alert",
                ALERT_BODY,
            )
            st["last_drift"] = fp
            events.append(
                f"{dom}: MAIL DRIFT mx_ok={r['mx_ok']} spf_ok={r['spf_ok']} (alert {res})"
            )
            continue
        st["last_drift"] = None
        if r["on_cloudflare"]:
            if st["status"] != "moved":
                st["status"], st["moved_at"] = "moved", checked
            done = st.get("notified_mode") == "sent" or (not nt.send and st.get("notified_at"))
            if not done:
                res = nt.queue(
                    f"dns-done:{dom}",
                    "DIANA_EMAIL",
                    DIANA_SUBJECT.format(domain=dom),
                    DIANA_BODY.format(
                        domain=dom, checked=checked.replace("T", " ").rstrip("Z")
                    ),
                    "diana_dns_done",
                    DIANA_BODY,
                )
                if res in ("drafted", "sent", "duplicate"):
                    st["notified_at"] = checked
                    st["notified_mode"] = "sent" if (nt.send and res == "duplicate") else (res if res != "duplicate" else st.get("notified_mode") or "drafted")
                events.append(f"{dom}: moved, mail intact (Diana email {res})")
            else:
                events.append(f"{dom}: moved, mail intact (already notified)")
        else:
            events.append(f"{dom}: pending (ns {', '.join(r['ns'])})")
    state["last_run"] = checked
    C.write_json(path, state)
    return {"events": events, "loud": loud, "state": state}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    ap.add_argument(
        "--send",
        action="store_true",
        help="live email via Resend (needs keys + red-team-approved template)",
    )
    ap.add_argument(
        "--baseline",
        type=Path,
        help="JSON {domain: {mx, spf}} replacing the inventory (an approved mail change)",
    )
    ap.add_argument("--domains", help="comma list (default: all 10)")
    a = ap.parse_args(argv)
    base = C.read_json(a.baseline) if a.baseline else None
    out = run(
        a.state_dir,
        send=a.send,
        baseline=base,
        domains=a.domains.split(",") if a.domains else None,
    )
    print("\n".join(out["events"]))
    return 2 if out["loud"] else 0


if __name__ == "__main__":
    sys.exit(main())
