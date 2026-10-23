#!/usr/bin/env python3
"""Eval set for linkedin_connect_queue.py — 20 deterministic cases through the real CLI.

Every case runs the same command line Cowork runs, on a throwaway data dir, and asserts one
property (gap, vulnerability or contract). Output is a fixed-order markdown table plus a pass
rate, so two runs on the same code produce the same report.

Usage: python3 execution/personal_workflows/tests/linkedin_connect_eval.py [--data path/to/master.csv]
Exit 0 all pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
SCRIPT = WS / "execution" / "personal_workflows" / "linkedin_connect_queue.py"
TODAY = dt.date.today().isoformat()
YESTERDAY = (dt.date.today() - dt.timedelta(days=1)).isoformat()


def run(data_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), "--data-dir", str(data_dir), *args],
                          capture_output=True, text=True)


def write(path: Path, text: str, enc: str = "utf-8") -> Path:
    path.write_text(text, encoding=enc)
    return path


def ledger(data_dir: Path, rows: list[tuple[str, str, str]]) -> None:
    """rows: (date, slug, status)"""
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / "ledger.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "date", "slug", "name", "status", "note"])
        for d, s, st in rows:
            w.writerow([f"{d}T10:00:00", d, s, s, st, ""])


def master_rows(data_dir: Path) -> list[dict]:
    return list(csv.DictReader((data_dir / "master.csv").open(encoding="utf-8")))


def ledger_rows(data_dir: Path) -> list[dict]:
    p = data_dir / "ledger.csv"
    return list(csv.DictReader(p.open(encoding="utf-8"))) if p.exists() else []


A_CSV = ("Full Name,Company,Title,LinkedIn URL\n"
         "Ada Lovelace,Analytical Engines,CTO,https://www.linkedin.com/in/ada-lovelace/\n"
         "Alan Turing,Bletchley,Lead,linkedin.com/in/aturing?x=1\n"
         "No Url,Acme,CEO,\n")
B_CSV = ("first_name,last_name,Organization,Headline,Profile\n"
         "Grace,Hopper,US Navy,Rear Admiral,https://linkedin.com/in/ghopper\n"
         "Ada,Lovelace,Analytical Engines,CTO,https://www.linkedin.com/in/ADA-LOVELACE\n")


def seed_master(d: Path, n: int) -> None:
    rows = "\n".join(f"P{i},Co{i},Role{i},https://www.linkedin.com/in/p{i}/" for i in range(n))
    write(d / "in.csv", "Name,Company,Title,LinkedIn\n" + rows + "\n")
    assert run(d, "consolidate", "--in", str(d / "in.csv")).returncode == 0


# ---- cases: each returns (ok: bool, evidence: str) ----

def c01_merge_aliases(d):
    write(d / "a.csv", A_CSV); write(d / "b.csv", B_CSV)
    r = run(d, "consolidate", "--in", str(d / "a.csv"), str(d / "b.csv"))
    n = len(master_rows(d))
    return r.returncode == 0 and n == 3, f"exit {r.returncode}, {n} people"


def c02_case_insensitive_dupe(d):
    c01_merge_aliases(d)
    slugs = [r["slug"] for r in master_rows(d)]
    return slugs.count("ada-lovelace") == 1 and "ada-lovelace" in slugs, f"slugs={slugs}"


def c03_no_url_counted(d):
    write(d / "a.csv", A_CSV)
    r = run(d, "consolidate", "--in", str(d / "a.csv"))
    return "1 rows without a LinkedIn URL skipped" in r.stdout, r.stdout.strip()


def c04_url_decoded(d):
    write(d / "a.csv", "Name,Company,Title,LinkedIn\nJosé,Co,CEO,https://www.linkedin.com/in/jos%C3%A9-garc%C3%ADa/\n")
    run(d, "consolidate", "--in", str(d / "a.csv"))
    s = master_rows(d)[0]["slug"]
    return s == "josé-garcía", f"slug={s!r}"


def c05_non_profile_urls_rejected(d):
    write(d / "a.csv", "Name,Company,Title,LinkedIn\nA,Co,X,https://www.linkedin.com/company/acme/\n"
                       "B,Co,X,https://www.linkedin.com/pub/bob/1/2/3\nC,Co,X,https://www.linkedin.com/sales/lead/123\n"
                       "D,Co,X,https://www.linkedin.com/in/real-one/\n")
    r = run(d, "consolidate", "--in", str(d / "a.csv"))
    n = len(master_rows(d))
    return n == 1 and "3 rows without" in r.stdout, f"{n} people; {r.stdout.strip()}"


def c06_decoy_url_column(d):
    write(d / "a.csv", "Name,Company,URL,Company Linkedin,LinkedIn\n"
                       "A,Co,https://acme.com,https://www.linkedin.com/company/acme,https://www.linkedin.com/in/a-person/\n")
    run(d, "consolidate", "--in", str(d / "a.csv"))
    rows = master_rows(d)
    return len(rows) == 1 and rows[0]["slug"] == "a-person", f"rows={rows}"


def c07_cp1252(d):
    write(d / "a.csv", "Name,Company,Title,LinkedIn\nRenée Café,Société,CEO,https://www.linkedin.com/in/renee/\n", enc="cp1252")
    r = run(d, "consolidate", "--in", str(d / "a.csv"))
    rows = master_rows(d)
    return r.returncode == 0 and rows and rows[0]["name"] == "Renée Café", f"exit {r.returncode} rows={rows}"


def c08_idempotent(d):
    write(d / "a.csv", A_CSV)
    run(d, "consolidate", "--in", str(d / "a.csv")); n1 = len(master_rows(d))
    run(d, "consolidate", "--in", str(d / "a.csv")); n2 = len(master_rows(d))
    return n1 == n2 == 2, f"{n1} then {n2}"


def c09_cap_25(d):
    seed_master(d, 40)
    r = run(d, "plan", "--limit", "30")
    n = len(list(csv.DictReader((d / f"queue_{TODAY}.csv").open())))
    return n == 25, f"queued {n}"


def c10_limit_zero(d):
    seed_master(d, 5)
    r = run(d, "plan", "--limit", "0")
    return r.returncode == 2, f"exit {r.returncode}"


def c11_26th_refused(d):
    seed_master(d, 30)
    ledger(d, [(TODAY, f"p{i}", "sent") for i in range(25)])
    r = run(d, "mark", "p25", "--status", "sent")
    return r.returncode == 3 and len(ledger_rows(d)) == 25, f"exit {r.returncode}, ledger {len(ledger_rows(d))}"


def c12_duplicate_mark(d):
    seed_master(d, 3)
    run(d, "mark", "p0", "--status", "sent")
    r = run(d, "mark", "p0", "--status", "skipped")
    return r.returncode == 0 and len(ledger_rows(d)) == 1 and "not marking again" in r.stdout, r.stdout.strip()


def c13_retry_semantics(d):
    seed_master(d, 2)
    ledger(d, [(TODAY, "p0", "retry"), (YESTERDAY, "p1", "retry")])
    run(d, "plan")
    q = [r["slug"] for r in csv.DictReader((d / f"queue_{TODAY}.csv").open())]
    return q == ["p1"], f"queue={q}"


def c14_topup_after_skips(d):
    seed_master(d, 60)
    run(d, "plan")
    for i in range(10):
        run(d, "mark", f"p{i}", "--status", "skipped")
    run(d, "plan")
    q = [r["slug"] for r in csv.DictReader((d / f"queue_{TODAY}.csv").open())]
    return len(q) == 25 and not any(s in q for s in [f"p{i}" for i in range(10)]), f"{len(q)} queued, first={q[:3]}"


def c15_weekly_trim(d):
    seed_master(d, 200)
    ledger(d, [((dt.date.today() - dt.timedelta(days=1 + i % 6)).isoformat(), f"p{i}", "sent") for i in range(95)])
    r = run(d, "plan")
    n = len(list(csv.DictReader((d / f"queue_{TODAY}.csv").open())))
    return n == 5 and "weekly soft cap" in r.stderr, f"queued {n}; {r.stderr.strip()}"


def c16_report_four_fields(d):
    seed_master(d, 4)
    ledger(d, [(TODAY, "p0", "sent"), (TODAY, "p1", "skipped"), (YESTERDAY, "p2", "sent")])
    r = run(d, "report")
    lines = [l for l in r.stdout.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    cols = lines[0].count("|") - 1 if lines else 0
    return len(lines) == 1 and cols == 5 and "p0" in lines[0] and "1 request(s)" in r.stdout, f"{len(lines)} rows, {cols} cols"


def c17_orphan_warning(d):
    seed_master(d, 2)
    ledger(d, [(TODAY, "ghost", "sent")])
    r = run(d, "status")
    return "1 orphan slug" in r.stderr, r.stderr.strip()


def c18_shuffle_deterministic(d):
    seed_master(d, 100)
    run(d, "plan", "--shuffle"); q1 = [r["slug"] for r in csv.DictReader((d / f"queue_{TODAY}.csv").open())]
    (d / f"queue_{TODAY}.csv").unlink()
    run(d, "plan", "--shuffle"); q2 = [r["slug"] for r in csv.DictReader((d / f"queue_{TODAY}.csv").open())]
    return q1 == q2 and q1 != [f"p{i}" for i in range(25)], f"same={q1 == q2}, shuffled={q1 != [f'p{i}' for i in range(25)]}"


def c19_empty_master(d):
    r = run(d, "plan")
    return r.returncode == 2, f"exit {r.returncode}"


def make_c20(master: Path | None):
    def c20_real_master(d):
        if not master or not master.exists():
            return None, "no --data master given"
        rows = list(csv.DictReader(master.open(encoding="utf-8")))
        slugs = [r["slug"] for r in rows]
        blanks = sum(1 for r in rows for k in ("name", "company", "position", "linkedin_url") if not r[k])
        ok = len(set(slugs)) == len(slugs) and blanks == 0 and all(r["linkedin_url"].endswith(f"/in/{r['slug']}/") for r in rows)
        return ok, f"{len(rows)} rows, {len(set(slugs))} unique slugs, {blanks} blank fields"
    return c20_real_master


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="real master.csv to check (case 20)")
    ap.add_argument("--out", help="write the table here as well")
    a = ap.parse_args()
    cases = [c01_merge_aliases, c02_case_insensitive_dupe, c03_no_url_counted, c04_url_decoded,
             c05_non_profile_urls_rejected, c06_decoy_url_column, c07_cp1252, c08_idempotent, c09_cap_25,
             c10_limit_zero, c11_26th_refused, c12_duplicate_mark, c13_retry_semantics, c14_topup_after_skips,
             c15_weekly_trim, c16_report_four_fields, c17_orphan_warning, c18_shuffle_deterministic,
             c19_empty_master, make_c20(Path(a.data) if a.data else None)]
    lines = ["| # | Case | Result | Evidence |", "|---|---|---|---|"]
    passed = total = 0
    for i, fn in enumerate(cases, 1):
        tmp = Path(tempfile.mkdtemp(prefix="lc_eval_"))
        try:
            d = tmp / "state"; d.mkdir(parents=True, exist_ok=True)
            ok, ev = fn(d)
        except Exception as e:  # a crash is a failure with evidence
            ok, ev = False, f"exception: {e!r}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if ok is None:
            res = "SKIP"
        else:
            total += 1; passed += ok; res = "PASS" if ok else "FAIL"
        lines.append(f"| {i} | {fn.__name__[4:]} | {res} | {ev.replace('|', '/')[:110]} |")
    rate = passed / total if total else 0
    lines += ["", f"**{passed}/{total} passed ({rate:.0%})**"]
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
