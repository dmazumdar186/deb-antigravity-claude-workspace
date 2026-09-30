#!/usr/bin/env python3
"""
Local proposal builder. No APIs, no accounts.
Reads config.json, fills {{PLACEHOLDERS}} in template.html, writes to public/<slug>/index.html.

Usage:
    python3 build.py                  # uses config.json
    python3 build.py my_config.json   # custom config
    python3 build.py --open           # also opens in browser
"""
import json
import os
import sys
import re
import secrets
import string
import webbrowser
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).parent


def base_url():
    """Public site root from settings.json, used only for the URL printed after a build."""
    path = SCRIPT_DIR / "settings.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("base_url", "").rstrip("/")
    return "https://<your-domain>"

TEMPLATE_PATH = SCRIPT_DIR / "template.html"
PUBLIC_DIR = SCRIPT_DIR / "public"


def flatten(cfg):
    """Flatten config into a dict of {PLACEHOLDER: value}."""
    m = {}
    c = cfg["client"]
    s = cfg["sender"]
    p = cfg["project"]
    sit = cfg["situation"]
    scope = cfg["scope"]
    inv = cfg["investment"]
    agr = cfg["agreement"]
    pay = cfg.get("payment", {})

    m["CLIENT_NAME"] = c["name"]
    m["CLIENT_TITLE"] = c["title"]
    m["CLIENT_COMPANY"] = c["company"]
    # Base slug from company name
    base_slug = c.get("company_slug_base") or re.sub(r"[^a-z0-9]+", "-", c["company"].lower()).strip("-")
    # Append 6-char random suffix so the URL is unguessable even if the company name is known
    existing_slug = c.get("company_slug")
    if existing_slug:
        slug = existing_slug
    else:
        alphabet = string.ascii_lowercase + string.digits
        suffix = ''.join(secrets.choice(alphabet) for _ in range(6))
        slug = f"{base_slug}-{suffix}"
    m["CLIENT_COMPANY_SLUG"] = slug

    m["SENDER_NAME"] = s["name"]
    m["SENDER_NAME_FIRST"] = s.get("name_first", s["name"].split()[0])
    m["SENDER_TITLE"] = s["title"]
    m["SENDER_COMPANY"] = s["company"]
    m["SENDER_EMAIL"] = s["email"]
    m["LOGO_URL"] = s.get("logo_url", "/assets/logo.png")
    # Split company name: last word gets accent color (e.g. "Acme Studio" -> "Acme" + accent "Studio")
    company_parts = s["company"].rsplit(" ", 1)
    if len(company_parts) == 2:
        m["SENDER_COMPANY_WORDMARK"] = f'{company_parts[0]} <span class="accent">{company_parts[1]}</span>'
    else:
        m["SENDER_COMPANY_WORDMARK"] = s["company"]

    m["PROJECT_TITLE"] = p["title"]
    m["COVER_BRAND_LABEL"] = p["cover_brand_label"]
    m["COVER_SUBTITLE"] = p["cover_subtitle"]
    m["CREATED_DATE"] = p.get("created_date") or date.today().isoformat()

    m["SITUATION_HEADLINE"] = sit["headline"]
    m["SITUATION_LEDE"] = sit["lede"]
    m["SITUATION_CALLOUT_TITLE"] = sit["callout_title"]
    m["SITUATION_CALLOUT_BODY"] = sit["callout_body"]
    m["SITUATION_CLOSE"] = sit["close"]

    for i, prob in enumerate(cfg["problems"][:4], start=1):
        m[f"PROBLEM_0{i}_TITLE"] = prob["title"]
        m[f"PROBLEM_0{i}_BODY"] = prob["body"]
    for i, ben in enumerate(cfg["benefits"][:4], start=1):
        m[f"BENEFIT_0{i}_TITLE"] = ben["title"]
        m[f"BENEFIT_0{i}_BODY"] = ben["body"]

    m["SCOPE_M1_TITLE"] = scope["m1_title"]
    m["SCOPE_M1_BODY"] = scope["m1_body"]
    m["SCOPE_M2_TITLE"] = scope["m2_title"]
    m["SCOPE_M2_BODY"] = scope["m2_body"]
    m["SCOPE_M3_TITLE"] = scope["m3_title"]
    m["SCOPE_M3_BODY"] = scope["m3_body"]
    m["SCOPE_THROUGHOUT"] = scope["throughout"]
    m["OUT_OF_SCOPE"] = scope["out_of_scope"]

    m["M1_DELIVERABLE"] = inv["m1_deliverable"]
    m["M1_AMOUNT"] = str(inv["m1_amount"])
    m["M2_DELIVERABLE"] = inv["m2_deliverable"]
    m["M2_AMOUNT"] = str(inv["m2_amount"])
    m["M3_DELIVERABLE"] = inv["m3_deliverable"]
    m["M3_AMOUNT"] = str(inv["m3_amount"])
    m["TOTAL_AMOUNT"] = str(inv["total_amount"])
    m["ROI_TITLE"] = inv["roi_title"]
    m["ROI_BODY"] = inv["roi_body"]

    m["AGREEMENT_BODY"] = agr["body"]
    m["SENDER_SIGNATURE_TEXT"] = agr.get("sender_signature_text", s["name"])

    m["STRIPE_PAYMENT_URL"] = pay.get("stripe_url", "#")

    return m


def fill(template, mapping):
    missing = []
    def repl(match):
        key = match.group(1)
        if key not in mapping:
            missing.append(key)
            return match.group(0)
        return str(mapping[key])
    output = re.sub(r"\{\{([A-Z0-9_]+)\}\}", repl, template)
    return output, missing


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.startswith("-")]
    config_path = SCRIPT_DIR / (args[0] if args else "config.json")
    if not config_path.exists():
        config_path = SCRIPT_DIR / "config.example.json"
        print(f"⚠️  No config.json found — using {config_path.name}")

    with open(config_path) as f:
        cfg = json.load(f)

    template = TEMPLATE_PATH.read_text()
    mapping = flatten(cfg)

    # Persist generated slug back to config so re-builds reuse the same URL
    if cfg["client"].get("company_slug") != mapping["CLIENT_COMPANY_SLUG"]:
        cfg["client"]["company_slug"] = mapping["CLIENT_COMPANY_SLUG"]
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    output, missing = fill(template, mapping)

    if missing:
        print(f"⚠️  Unfilled placeholders: {', '.join(set(missing))}")

    slug = mapping["CLIENT_COMPANY_SLUG"]
    out_dir = PUBLIC_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(output)

    print(f"✅ Wrote {out_path}")
    print(f"   Slug:   {slug}")
    print(f"   Client: {mapping['CLIENT_COMPANY']}")
    print(f"   Total:  ${mapping['TOTAL_AMOUNT']}")
    print(f"   Local:  file://{out_path.resolve()}")
    print(f"   URL:    (after deploy) {base_url()}/{slug}")

    if "--open" in sys.argv or "-o" in sys.argv:
        webbrowser.open(f"file://{out_path.resolve()}")

    return out_path


if __name__ == "__main__":
    main()
