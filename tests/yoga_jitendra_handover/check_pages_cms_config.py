"""Validate .pages.yml against Pages CMS schema rules and the JSON content it edits.
Usage: python3 check_pages_cms_config.py [/tmp/handover]  -> exit 1 on any ERROR."""
import json, sys, os, yaml
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/handover"
TYPES = {"boolean","code","date","file","image","number","object","rich-text","select","string","text","uuid","reference","block"}
INTERNAL = {"_comment","_note","$schema"}
errs, warns = [], []
cfg = yaml.safe_load(open(os.path.join(ROOT, ".pages.yml")))
m = cfg.get("media")
if not isinstance(m, (dict, list)) and not isinstance(m, str): errs.append("media missing")
if isinstance(m, dict) and not {"input","output"} <= set(m): errs.append("media needs input+output")
def pytype(v):
    return {bool:"bool",int:"number",float:"number",str:"string",list:"list",dict:"object",type(None):"null"}[type(v)]
def check(fields, data, where):
    if not isinstance(data, dict):
        errs.append(f"{where}: expected object, JSON has {pytype(data)}"); return
    names = {f["name"] for f in fields}
    for k in data:
        if k not in names and k not in INTERNAL and not k.startswith("_"):
            warns.append(f"{where}: JSON key '{k}' not in config (may be dropped on save)")
    for f in fields:
        t, n, p = f.get("type"), f["name"], f"{where}.{f['name']}"
        if t not in TYPES: errs.append(f"{p}: unknown type {t}")
        if n not in data: warns.append(f"{p}: field not in JSON"); continue
        v, lst = data[n], f.get("list")
        if lst:
            if not isinstance(v, list): errs.append(f"{p}: list:true but JSON is {pytype(v)}"); continue
            items = v
        else:
            if isinstance(v, list): errs.append(f"{p}: JSON is list but list not set"); continue
            items = [v]
        for i, it in enumerate(items):
            q = f"{p}[{i}]" if lst else p
            if t == "object": check(f.get("fields", []), it, q)
            elif t == "boolean" and not isinstance(it, bool): errs.append(f"{q}: boolean vs {pytype(it)}")
            elif t == "number" and (isinstance(it, bool) or not isinstance(it, (int, float))): errs.append(f"{q}: number vs {pytype(it)}")
            elif t in ("string","text","rich-text","image","file","select","date","code") and not isinstance(it, str):
                errs.append(f"{q}: {t} vs {pytype(it)}")
            if t == "select":
                vals = [o["value"] if isinstance(o, dict) else o for o in (f.get("options", {}) or {}).get("values", [])]
                if vals and it not in vals: errs.append(f"{q}: '{it}' not in select values {vals}")
for e in cfg.get("content", []):
    path = os.path.join(ROOT, e.get("path", ""))
    if e.get("type") != "file": warns.append(f"{e['name']}: type {e.get('type')} not checked"); continue
    if e.get("format") != "json": errs.append(f"{e['name']}: format not json")
    if not os.path.exists(path): errs.append(f"{e['name']}: path missing {e.get('path')}"); continue
    data = json.load(open(path))
    if e.get("list"):
        if not isinstance(data, list): errs.append(f"{e['name']}: entry list:true but JSON {pytype(data)}"); continue
        for i, d in enumerate(data): check(e.get("fields", []), d, f"{e['name']}[{i}]")
    else: check(e.get("fields", []), data, e["name"])
for w in warns: print("WARN ", w)
for x in errs: print("ERROR", x)
print(f"{len(errs)} errors, {len(warns)} warnings"); sys.exit(1 if errs else 0)
