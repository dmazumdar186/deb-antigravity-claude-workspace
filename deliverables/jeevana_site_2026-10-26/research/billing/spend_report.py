"""Jeevana site — billable spend report (paid APIs only), rebuilt from the per-call ledgers.

description: Sums every paid call recorded for this project and writes research/billing/SPEND.md.
  Sources: research/film*/ledger.jsonl (Higgsfield / Kling video legs, `usd` per leg, status ok vs other),
  research/glm_log.md (GLM backdrop calls), research/warroom/ledger.md (OpenRouter war-room calls: Sol, Claude, GLM, Fable),
  research/billing/manual.jsonl (anything not logged by a script: one JSON object per line {date, vendor, item, usd, note}).
  `snapshot` appends the OpenRouter account balance to research/billing/openrouter_snapshots.jsonl as a cross-check
  (account-wide, so it is NOT the billable figure; the per-call ledgers are).
usage: python3 research/billing/spend_report.py [snapshot]
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "research/billing"

def film() -> list[tuple]:
    rows = []
    for f in sorted(ROOT.glob("research/film*/ledger.jsonl")):
        recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        ok = sum(float(r.get("usd") or 0) for r in recs if r.get("status") == "ok")
        other = sum(float(r.get("usd") or 0) for r in recs if r.get("status") != "ok")
        rows.append(("2026-10-26", "Higgsfield (Kling 3.0)", f"{f.parent.name}: {len(recs)} video legs", round(ok + other, 3),
                     f"ok {ok:.3f} + non-ok {other:.3f}"))
    return rows

def md_table(path: Path, model_col: int, cost_col: int, when_col: int = 0, step_col: int | None = None) -> list[tuple]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*20\d\d-", line):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        try:
            usd = float(c[cost_col].lstrip("$") or 0)
        except (ValueError, IndexError):
            continue
        step = c[step_col] if step_col is not None else ""
        rows.append((c[when_col][:10], "OpenRouter", f"{c[model_col]} {step}".strip(), usd, path.name))
    return rows

def manual() -> list[tuple]:
    f = B / "manual.jsonl"
    if not f.exists():
        return []
    out = []
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l); out.append((r["date"], r["vendor"], r["item"], float(r["usd"]), r.get("note", "")))
    return out

def snapshot() -> None:
    k = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_TOEKN")
    req = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {k}"})
    d = json.load(urllib.request.urlopen(req, timeout=20))["data"]
    with (B / "openrouter_snapshots.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **d}) + "\n")
    print("snapshot", d)

def main() -> None:
    if sys.argv[1:] == ["snapshot"]:
        snapshot()
    rows = film() + md_table(ROOT / "research/glm_log.md", 1, 5, 0, 2) + md_table(ROOT / "research/warroom/ledger.md", 2, 5, 0, 1) + manual()
    rows.sort(key=lambda r: (r[0], r[1]))
    by_vendor: dict[str, float] = {}
    for r in rows:
        by_vendor[r[1]] = by_vendor.get(r[1], 0) + r[3]
    total = sum(by_vendor.values())
    snaps = [json.loads(l) for l in (B / "openrouter_snapshots.jsonl").read_text(encoding="utf-8").splitlines()] if (B / "openrouter_snapshots.jsonl").exists() else []
    out = ["# Jeevana site — paid spend (billable third-party costs)", "",
           f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `research/billing/spend_report.py` from the per-call ledgers.", "",
           "| Vendor | USD |", "|---|---|"] + [f"| {v} | {u:.2f} |" for v, u in sorted(by_vendor.items())] + [f"| **Total** | **{total:.2f}** |", "",
           "## Line items", "", "| Date | Vendor | Item | USD | Source / note |", "|---|---|---|---|---|"]
    out += [f"| {d} | {v} | {i} | {u:.4f} | {n} |" for d, v, i, u, n in rows]
    out += ["", "## Not itemised", "- Claude subscription (Max plan) usage for this session and its sub-agents: flat-fee plan, not metered per project.",
            "- Cloudflare Pages, Functions, KV, Web Analytics: free tier.",
            "- Labour / design time: outside this ledger.", "",
            "## Reconciliation to check", "",
            "- Higgsfield: the per-leg ledgers sum to $13.62, but the 2026-10-26 handoff states \"Higgsfield $16.19\". The ~$2.57 gap is",
            "  likely identity-reference / still-image calls that were not ledgered. Confirm against the Higgsfield billing page and add",
            "  the missing line to `research/billing/manual.jsonl` if real.", ""]
    if snaps:
        out += ["## OpenRouter account snapshots (cross-check only; account-wide)", "", "| When | Credits bought | Usage to date |", "|---|---|---|"]
        out += [f"| {s['ts']} | {s['total_credits']} | {s['total_usage']:.4f} |" for s in snaps]
    (B / "SPEND.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"total ${total:.2f}", {k: round(v, 2) for k, v in by_vendor.items()})

if __name__ == "__main__":
    main()
