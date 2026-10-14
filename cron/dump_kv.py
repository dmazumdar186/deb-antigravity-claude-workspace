#!/usr/bin/env python3
"""Dump every key of the yoga-jitendra DASHBOARD_KV namespace to JSON files.

Writes <out>/<prefix>.json  (prefix = first key segment, e.g. review, event,
dashboard, newsletter, self_report). OAuth caches (oauth:*) are never dumped.
Env: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID.  Usage: dump_kv.py <out_dir> [key_prefix]  (prefix limits the dump, e.g. review:approved:)
"""
import json, os, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

NS = "4cdf5cdb6fc14db3b29edcab6c464714"
TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
ACCT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/storage/kv/namespaces/{NS}"
HDR = {"Authorization": f"Bearer {TOKEN}"}


def get(url, raw=False):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30)
    b = r.read()
    return b.decode() if raw else json.loads(b)


def list_keys():
    keys, cursor = [], ""
    while True:
        d = get(f"{BASE}/keys?limit=1000" + (f"&cursor={cursor}" if cursor else ""))
        keys += [k["name"] for k in d["result"]]
        cursor = (d.get("result_info") or {}).get("cursor") or ""
        if not cursor:
            return keys


def fetch(k):
    v = get(f"{BASE}/values/{urllib.parse.quote(k, safe='')}", raw=True)
    try:
        return k, json.loads(v)
    except ValueError:
        return k, v


def main(out, prefix=""):
    os.makedirs(out, exist_ok=True)
    keys = [k for k in list_keys() if not k.startswith("oauth:") and k.startswith(prefix)]
    print(f"{len(keys)} keys")
    with ThreadPoolExecutor(16) as ex:
        items = list(ex.map(fetch, keys))
    by = {}
    for k, v in items:
        by.setdefault(k.split(":")[0], {})[k] = v
    for p, d in by.items():
        with open(os.path.join(out, f"{p}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"{p}: {len(d)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "kv_dump", sys.argv[2] if len(sys.argv) > 2 else "")
