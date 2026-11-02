"""Idempotent sync of the A/B test's new-copy variants in live Instantly campaigns from the committed copy file.

description: Idempotent sync of Instantly A/B new-copy variants (step 1 roles B/C, steps 2-3 role new) from instantly_copy_variants.json; controls untouched; dry run by default
inputs: --apply (PATCH; default dry run); --config (default execution/infrastructure/instantly_copy_tests.json); --copy (default execution/infrastructure/instantly_copy_variants.json); env INSTANTLY_API_KEY
outputs: stdout per campaign "in sync" / "differs" / "updated" / "VERIFY FAIL"; with --apply PATCHes /api/v2/campaigns/{id} sequences

Usage:
    python3 execution/infrastructure/instantly_copy_sync.py            # dry run: report drift only
    python3 execution/infrastructure/instantly_copy_sync.py --apply    # PATCH drifted campaigns, re-GET verify

Arguments:
    - --apply: PATCH campaigns whose new-copy variants differ from the copy file
    - --config: tests config (campaign_id, family, roles per step)
    - --copy: JSON list of {"id": "<family>_s1_B|_s1_C|_s2|_s3", "subject", "body"}; body is plain text,
      paragraphs separated by a blank line

Writes:
    - Instantly campaign sequences (only with --apply); nothing on disk
    - exit 0 all in sync / all verified; exit 1 drift found (dry run) or verify failure; exit 2 API failure

Env vars used:
    - INSTANTLY_API_KEY -- Instantly v2 bearer key

Modes:
    No LLM call.

See also: directives/infrastructure/instantly_copy_monitor.md
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from execution.infrastructure.instantly_copy_monitor import (
    DEFAULT_CONFIG,
    DEFAULT_COPY,
    ApiError,
    campaign_roles,
    instantly_client,
)

# (step, role, copy-id suffix): which variant slot receives which copy.
SLOTS = ((0, "B", "s1_B"), (0, "C", "s1_C"), (1, "new", "s2"), (2, "new", "s3"))


def to_html(body: str) -> str:
    """Plain text with blank-line paragraphs -> Instantly HTML, byte-identical to the copy lab's html()."""
    paras = body.split("\n\n")
    return "".join(f"<div>{p}</div><div><br /></div>" for p in paras[:-1]) + f"<div>{paras[-1]}</div>"


def wanted(test: dict[str, Any], copies: dict[str, dict[str, Any]]) -> dict[tuple[int, int], tuple[str, str]]:
    """{(step, variant): (subject, html body)} for one campaign. Raises KeyError on a missing role or copy id."""
    roles = campaign_roles(test)
    out = {}
    for step, role, suffix in SLOTS:
        c = copies[f"{test['family']}_{suffix}"]
        out[(step, roles[step][role])] = (c.get("subject") or "", to_html(c.get("body") or ""))
    return out


def drift(sequences: list[dict[str, Any]], want: dict[tuple[int, int], tuple[str, str]]) -> list[tuple[int, int]]:
    steps = sequences[0]["steps"]
    return [(s, v) for (s, v), (subj, body) in sorted(want.items())
            if steps[s]["variants"][v].get("subject") != subj or steps[s]["variants"][v].get("body") != body]


def patched(sequences: list[dict[str, Any]], want: dict[tuple[int, int], tuple[str, str]]) -> list[dict[str, Any]]:
    new = copy.deepcopy(sequences)
    for (s, v), (subj, body) in want.items():
        var = new[0]["steps"][s]["variants"][v]
        var["subject"], var["body"] = subj, body
    return new


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync A/B new-copy variants into live Instantly campaigns.")
    p.add_argument("--apply", action="store_true", help="PATCH drifted campaigns (default: dry run).")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--copy", default=str(DEFAULT_COPY))
    args = p.parse_args(argv)
    tests = json.loads(Path(args.config).read_text(encoding="utf-8")).get("tests") or []
    copies = {c["id"]: c for c in json.loads(Path(args.copy).read_text(encoding="utf-8"))}
    bad = 0
    try:
        api = instantly_client()
        for t in tests:
            want = wanted(t, copies)
            cur = api.campaign(t["campaign_id"]).get("sequences") or []
            diff = drift(cur, want)
            if not diff:
                print(f"in sync  {t['name']}")
                continue
            if not args.apply:
                bad += 1
                print(f"differs  {t['name']} slots {diff}")
                continue
            new = patched(cur, want)
            api.patch_sequences(t["campaign_id"], new)
            after = api.campaign(t["campaign_id"]).get("sequences") or []
            untouched = all(after[0]["steps"][s]["variants"][v] == cur[0]["steps"][s]["variants"][v]
                            for s, st in enumerate(cur[0]["steps"]) for v in range(len(st["variants"])) if (s, v) not in want)
            if drift(after, want) or not untouched:
                bad += 1
                print(f"VERIFY FAIL {t['name']}")
            else:
                print(f"updated  {t['name']} slots {diff}")
    except ApiError as exc:
        print(f"API failure: {exc}", file=sys.stderr)
        return 2
    print(f"{len(tests)} campaigns, {bad} {'verify failures' if args.apply else 'out of sync'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
