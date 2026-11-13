"""Add the operator's opt-out P.S. (with spintax) to every email of the Instantly campaigns sent from Debanjan's accounts.

description: Idempotently append (or swap in) the "if this isn't interesting, let me know and i'll stop following up" P.S. on every step/variant of Debanjan's sending campaigns; dry run by default
inputs: --apply (PATCH; default dry run); --statuses (default 1,2,4,-1,-2: active, paused, running subsequences, unhealthy, bounce-protected); --backup-dir; env INSTANTLY_API_KEY
outputs: stdout one line per campaign (would add / already has / updated / VERIFY FAIL / skipped); with --apply a JSON backup of each campaign's sequences before its PATCH

Usage:
    python3 execution/infrastructure/instantly_add_ps.py            # dry run: what would change
    python3 execution/infrastructure/instantly_add_ps.py --apply    # backup, PATCH, re-GET verify

Rules (operator order 2026-11-13: "always keep a ps"):
    - A campaign is Debanjan's when any account it sends from (email_list or email_tag_list -> tag mappings) has
      first name "Debanjan" or an address starting "deb". Drafts and completed campaigns are not touched.
    - Body already contains "stop following up" -> left alone (idempotent).
    - Body has the old opt-out "if you'd rather not hear from me" -> that paragraph is replaced by the new line,
      labelled "pps." (the body's existing "ps." stays).
    - Otherwise the line is appended as the last paragraph, "ps." in all-lowercase copy, "P.S." otherwise.
    - French bodies are skipped and reported (the line is English).

Writes:
    - Instantly campaign sequences (only with --apply); backups under --backup-dir (gitignored .tmp by default)
    - exit 0 nothing to do / all verified; 1 a verify failure; 2 API failure

Env vars used:
    - INSTANTLY_API_KEY -- Instantly v2 bearer key

Modes:
    No LLM call. Keep instantly_copy_variants.json in step (A/B new-copy slots) or instantly_copy_sync reverts them.

See also: directives/infrastructure/instantly_copy_monitor.md
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from execution.infrastructure.instantly_copy_monitor import (
    ApiError,
    instantly_client,
)  # noqa: E402

SPIN_BODY = (
    "if this isn't {{RANDOM|interesting|interesting to you|of interest}}, "
    "{{RANDOM|please let me know|please just let me know|just let me know}} and i'll stop following up."
)
LINE_LOWER = "{{RANDOM|ps.|p.s.}} " + SPIN_BODY
LINE_PROPER = (
    "{{RANDOM|P.S.|PS.}} "
    + SPIN_BODY.replace(" i'll ", " I'll ")  # operator's exact lowercase "if"; only the pronoun follows casing
)
LINE_PPS = "{{RANDOM|pps.|p.p.s.}} " + SPIN_BODY
MARKER = "stop following up"
OLD_OPTOUT = re.compile(r"<div>[^<]*rather not hear from me[^<]*</div>", re.I)
FRENCH = re.compile(r"\b(vous|votre|bonjour|je peux|chiffre d)\b", re.I)
DEFAULT_STATUSES = "1,2,4,-1,-2"


def plain(body: str) -> str:
    return re.sub(r"<[^>]+>", "\n", body or "")


def is_lowercase_style(body: str) -> bool:
    """True when the copy is written all-lowercase (first-person 'i', lowercase sentence starts)."""
    # Spintax options carry most of the copy's own words: keep them, drop only the delimiters and merge tags.
    txt = re.sub(r"\{\{\s*RANDOM\s*\|", " ", plain(body))
    txt = re.sub(r"\{\{[^}]*\}\}", " ", txt).replace("|", " ").replace("}}", " ")
    lower_i = len(re.findall(r"(?:^|\s)i(?:'|\s)", txt))
    upper_i = len(re.findall(r"(?:^|\s)I(?:'|\s)", txt))
    if lower_i or upper_i:
        return lower_i > upper_i
    starts = re.findall(r"(?:^|[.?!]\s+|\n)([A-Za-z])", txt)
    return bool(starts) and sum(c.islower() for c in starts) > len(starts) / 2


def add_ps(body: str) -> tuple[str, str]:
    """(new body, action) for one variant body. action: kept | swapped | added | french."""
    if MARKER in plain(body).lower():
        return body, "kept"
    if FRENCH.search(plain(body)):
        return body, "french"
    if OLD_OPTOUT.search(body):
        return (
            OLD_OPTOUT.sub(lambda _m: f"<div>{LINE_PPS}</div>", body, count=1),
            "swapped",
        )
    line = LINE_LOWER if is_lowercase_style(body) else LINE_PROPER
    base = body.rstrip()
    if base and not base.lstrip().startswith("<"):
        # Instantly drops bare text outside <div> on PATCH (2026-11-13: a draft's placeholder vanished), so wrap it.
        base = "".join(f"<div>{ln}</div>" for ln in base.split("\n") if ln.strip())
    return f"{base}<div><br /></div><div>{line}</div>", "added"


def new_sequences(camp: dict[str, Any]) -> tuple[list[Any], dict[str, int]]:
    seqs = copy.deepcopy(camp.get("sequences") or [])
    counts = {"kept": 0, "swapped": 0, "added": 0, "french": 0}
    for seq in seqs:
        for step in seq.get("steps", []):
            for v in step.get("variants", []):
                v["body"], act = add_ps(v.get("body", ""))
                counts[act] += 1
    return seqs, counts


def pages(c: Any, path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    after = None
    while True:
        params: dict[str, Any] = {"limit": 100}
        if after:
            params["starting_after"] = after
        r = c.get(path, params)
        items = r.get("items", [])
        out += items
        after = r.get("next_starting_after")
        if not after or not items:
            return out


def debanjan_campaigns(c: Any, statuses: set[int]) -> list[dict[str, Any]]:
    accts = pages(c, "/accounts")
    deb = {
        a["email"]
        for a in accts
        if str(a.get("first_name", "")).strip().lower() == "debanjan"
        or a["email"].lower().startswith("deb")
    }
    by_id = {a.get("id"): a["email"] for a in accts}
    tag_accts: dict[str, set[str]] = {}
    for m in pages(c, "/custom-tag-mappings"):
        tag_accts.setdefault(m["tag_id"], set()).add(
            by_id.get(m.get("resource_id"), m.get("resource_id"))
        )
    out = []
    for s in pages(c, "/campaigns"):
        if s.get("status") not in statuses:
            continue
        senders = set(s.get("email_list") or [])
        for t in s.get("email_tag_list") or []:
            senders |= tag_accts.get(t, set())
        if senders & deb:
            out.append(s)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--apply", action="store_true", help="PATCH campaigns (default: dry run)"
    )
    ap.add_argument(
        "--statuses", default=DEFAULT_STATUSES, help="campaign status codes to touch"
    )
    ap.add_argument("--backup-dir", default=str(ROOT / ".tmp" / "instantly_ps_backup"))
    a = ap.parse_args(argv)
    try:
        c = instantly_client()
        camps = debanjan_campaigns(c, {int(x) for x in a.statuses.split(",")})
    except ApiError as exc:
        print(f"API error: {exc}")
        return 2
    failures = changed = 0
    for s in sorted(camps, key=lambda x: x["name"]):
        try:
            fresh = c.campaign(
                s["id"]
            )  # fresh GET right before any PATCH: never revert concurrent edits
        except ApiError as exc:
            print(f"error      {s['name']}: {exc}")
            failures += 1
            continue
        seqs, n = new_sequences(fresh)
        tag = f"{s['name']} (added {n['added']}, swapped {n['swapped']}, kept {n['kept']}, french {n['french']})"
        if not n["added"] and not n["swapped"]:
            print(f"in place   {tag}")
            continue
        changed += 1
        if not a.apply:
            print(f"would edit {tag}")
            continue
        bdir = Path(a.backup_dir)
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / f"{s['id']}.json").write_text(
            json.dumps(fresh.get("sequences"), ensure_ascii=False), encoding="utf-8"
        )
        try:
            c.patch_sequences(s["id"], seqs)
            after = c.campaign(s["id"])
        except ApiError as exc:
            print(f"error      {tag}: {exc}")
            failures += 1
            continue
        _, n2 = new_sequences(after)
        if n2["added"] or n2["swapped"]:
            print(f"VERIFY FAIL {tag}")
            failures += 1
        else:
            print(f"updated    {tag}")
    print(
        f"{len(camps)} Debanjan campaigns, {changed} {'updated' if a.apply else 'to edit'}, {failures} failures"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
