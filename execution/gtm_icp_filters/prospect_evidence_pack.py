"""
prospect_evidence_pack.py
description: Build a two-check prospect evidence pack (pack.html + pack.csv) from finder/verifier row files.
             A row is QUALIFIED only if the finder AND an independent blind verifier both PASS and the
             screenshot verdict is not MODERN. Pure local file work: no network, no spend.
inputs:  --dir <pack dir> containing rows/*.json (schema below); screenshots referenced by absolute path
outputs: <dir>/pack.csv, <dir>/pack.html, <dir>/img/*.png (copied); summary line on stdout
usage:   python3 execution/gtm_icp_filters/prospect_evidence_pack.py --dir .tmp/<client>/pack
Directive: directives/gtm_icp_filters/prospect_evidence_pack.md
Input: .tmp/les/pack/rows/*.json, each a list of rows:
{company,url,vertical,hq,size,size_source,trigger_quote,trigger_url,trigger_date,
 markers:[str], visual_verdict, visual_notes, desk_png, mob_png,
 finder_status, verifier_status, verifier_notes, jev_score}
A row is QUALIFIED only if finder_status==verifier_status=="PASS" and visual_verdict!="MODERN".
"""
import csv, glob, html, json, os, shutil, sys
import argparse
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True)
base = os.path.abspath(ap.parse_args().dir)
if not os.path.isdir(os.path.join(base, "rows")):
    sys.exit(f"no rows/ folder under {base}")
os.makedirs(os.path.join(base, "img"), exist_ok=True)
rows = []
for f in sorted(glob.glob(os.path.join(base, "rows", "*.json"))):
    try:
        rows += json.load(open(f, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"bad row file {f}: {exc}")
def qualified(r):
    return r.get("finder_status") == "PASS" and r.get("verifier_status") == "PASS" and r.get("visual_verdict") != "MODERN"
for r in rows:
    r["qualified"] = qualified(r)
    for k in ("desk_png", "mob_png"):
        p = r.get(k) or ""
        if p and os.path.exists(p):
            dst = os.path.join(base, "img", os.path.basename(p))
            shutil.copyfile(p, dst); r[k + "_rel"] = "img/" + os.path.basename(p)
rows.sort(key=lambda r: (not r["qualified"], -(r.get("jev_score") or 0)))
cols = ["qualified","company","url","vertical","hq","size","size_source","trigger_date","trigger_quote","trigger_url","markers","visual_verdict","visual_notes","verifier_status","verifier_notes","jev_score"]
with open(os.path.join(base, "pack.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(cols)
    for r in rows: w.writerow([("; ".join(r.get(c) or []) if c == "markers" else r.get(c, "")) for c in cols])
e = lambda s: html.escape(str(s or ""))
out = ["<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Evidence pack: Jacob Tyler prospects</title>",
       "<style>body{font:15px/1.5 system-ui;margin:24px;max-width:1200px}.card{border:1px solid #ccc;border-radius:8px;padding:16px;margin:16px 0}.no{opacity:.55}"
       ".shots{display:flex;gap:12px;align-items:flex-start}.shots img{border:1px solid #999}.d{width:560px}.m{width:180px}code{background:#f3f3f3;padding:1px 4px}"
       ".tag{display:inline-block;padding:2px 8px;border-radius:4px;font-weight:600}.ok{background:#d7f5dd}.bad{background:#f8d7d7}</style>",
       f"<h1>Evidence pack: Jacob Tyler prospects</h1><p>{sum(r['qualified'] for r in rows)} qualified of {len(rows)} checked. Qualified = finder PASS + independent verifier PASS + screenshot not MODERN.</p>"]
for r in rows:
    ok = r["qualified"]
    out.append(f"<div class='card {'' if ok else 'no'}'><h2>{e(r.get('company'))} <span class='tag {'ok' if ok else 'bad'}'>{'QUALIFIED' if ok else 'REJECTED'}</span></h2>")
    out.append(f"<p><a href='{e(r.get('url'))}'>{e(r.get('url'))}</a> · {e(r.get('vertical'))} · {e(r.get('hq'))} · size {e(r.get('size'))} ({e(r.get('size_source'))}) · Jev evidence {e(r.get('jev_score'))}/4</p>")
    out.append(f"<p><b>Trigger ({e(r.get('trigger_date'))}):</b> “{e(r.get('trigger_quote'))}” <a href='{e(r.get('trigger_url'))}'>source</a></p>")
    out.append("<p><b>Page-source markers:</b> " + " ".join(f"<code>{e(m)}</code>" for m in r.get("markers") or []) + "</p>")
    out.append(f"<p><b>Screenshot verdict:</b> {e(r.get('visual_verdict'))}: {e(r.get('visual_notes'))}</p>")
    out.append(f"<p><b>Independent verifier:</b> {e(r.get('verifier_status'))}: {e(r.get('verifier_notes'))}</p>")
    imgs = "".join(f"<img class='{c}' src='{e(r.get(k))}'>" for k, c in (("desk_png_rel","d"),("mob_png_rel","m")) if r.get(k))
    out.append(f"<div class='shots'>{imgs}</div></div>")
open(os.path.join(base, "pack.html"), "w", encoding="utf-8").write("\n".join(out))
print(f"rows={len(rows)} qualified={sum(r['qualified'] for r in rows)}")
