"""Idempotent sync of the A/B test's new-copy variants in live Instantly campaigns from the committed copy file.

description: Idempotent sync of Instantly A/B new-copy variants (step 1 roles B/C, steps 2-3 role new) from instantly_copy_variants.json; controls untouched; dry run by default
inputs: --apply (PATCH; default dry run); --config (default execution/infrastructure/instantly_copy_tests.json); --copy (default execution/infrastructure/instantly_copy_variants.json); env INSTANTLY_API_KEY
outputs: stdout per campaign "in sync" / "differs" / "updated" / "skipped" / "error" / "VERIFY FAIL"; with --apply PATCHes /api/v2/campaigns/{id} sequences

Usage:
    python3 execution/infrastructure/instantly_copy_sync.py            # dry run: report drift only
    python3 execution/infrastructure/instantly_copy_sync.py --apply    # PATCH drifted campaigns, re-GET verify

Arguments:
    - --apply: PATCH campaigns whose new-copy variants differ from the copy file
    - --config: tests config (campaign_id, family, roles per step)
    - --copy: JSON list of {"id": "<family>_s1_B|_s1_C|_s2|_s3", "subject", "body"}; body is plain text,
      paragraphs separated by a blank line, a single newline is a line break; & < > are HTML-escaped

Writes:
    - Instantly campaign sequences (only with --apply); nothing on disk
    - exit 0 all in sync / all verified; exit 1 drift, config/shape error or verify failure; exit 2 API failure
      or malformed config/copy JSON. Campaigns with status != 1 are skipped (as the monitor does).

Env vars used:
    - INSTANTLY_API_KEY -- Instantly v2 bearer key

Modes:
    No LLM call.

See also: directives/infrastructure/instantly_copy_monitor.md
"""
from __future__ import annotations

import argparse
import copy
import html
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from execution.infrastructure.instantly_copy_monitor import (  # noqa: E402, RUF100
    DEFAULT_CONFIG,
    DEFAULT_COPY,
    ApiError,
    ConfigError,
    campaign_roles,
    instantly_client,
    load_config,
    load_json,
)

# (step, role, copy-id suffix): which variant slot receives which copy.
SLOTS = ((0, "B", "s1_B"), (0, "C", "s1_C"), (1, "new", "s2"), (2, "new", "s3"))


class SyncError(ValueError):
    """A config entry or live campaign that cannot be synced; reported per campaign, never a traceback."""


def to_html(body: str) -> str:
    """Plain text -> Instantly HTML, byte-identical to the copy lab's html() for plain copy.

    Blank line = paragraph (`<div>p</div><div><br /></div>`, last paragraph `<div>p</div>`), a single
    newline inside a paragraph = `<br />`, and & < > are escaped (quotes, accents and « » are not).
    """
    paras = [html.escape(p, quote=False).replace("\n", "<br />") for p in body.strip().split("\n\n")]
    return "".join(f"<div>{p}</div><div><br /></div>" for p in paras[:-1]) + f"<div>{paras[-1]}</div>"


def wanted(test: dict[str, Any], copies: dict[str, dict[str, Any]]) -> dict[tuple[int, int], tuple[str, str]]:
    """{(step, variant): (subject, html body)} for one campaign. Raises SyncError on a missing role or copy id."""
    name = test.get("name") or test.get("campaign_id")
    if not test.get("roles"):
        raise SyncError(f"{name}: config entry has no `roles`")
    if not test.get("family"):
        raise SyncError(f"{name}: config entry has no `family`")
    roles = campaign_roles(test)
    out = {}
    for step, role, suffix in SLOTS:
        v = roles.get(step, {}).get(role)
        if v is None:
            raise SyncError(f"{name}: `roles` has no role {role!r} for step {step + 1}")
        cid = f"{test['family']}_{suffix}"
        if cid not in copies:
            raise SyncError(f"{name}: copy file has no id {cid!r}")
        c = copies[cid]
        out[(step, v)] = (c.get("subject") or "", to_html(c.get("body") or ""))
    return out


def check_shape(sequences: list[dict[str, Any]], want: dict[tuple[int, int], tuple[str, str]], name: str) -> None:
    """SyncError unless every wanted (step, variant) slot exists in the live sequence."""
    try:
        steps = sequences[0]["steps"]
        for s, v in want:
            if not isinstance(steps[s]["variants"][v], dict):
                raise TypeError("variant is not an object")
    except (KeyError, IndexError, TypeError) as exc:
        raise SyncError(f"{name}: live sequence lacks a wanted slot ({exc.__class__.__name__}: {exc})") from exc


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


def without_slots(sequences: list[dict[str, Any]], want: dict[tuple[int, int], Any]) -> list[dict[str, Any]]:
    """Deep copy with the wanted variant slots blanked: everything else (other variants, step-level
    fields such as delay, sequence-level fields) must survive a sync unchanged."""
    out = copy.deepcopy(sequences)
    for s, v in want:
        out[0]["steps"][s]["variants"][v] = None
    return out


def untouched(before: list[dict[str, Any]], after: list[dict[str, Any]], want: dict[tuple[int, int], Any]) -> bool:
    try:
        return without_slots(before, want) == without_slots(after, want)
    except (KeyError, IndexError, TypeError):
        return False


def load_copies(path: str | Path) -> dict[str, dict[str, Any]]:
    raw = load_json(path, "copy file")
    if not isinstance(raw, list) or not all(isinstance(c, dict) and "id" in c for c in raw):
        raise ConfigError(f"copy file must be a JSON list of {{id, subject, body}}: {path}")
    return {c["id"]: c for c in raw}


def sync_one(api: Any, t: dict[str, Any], copies: dict[str, dict[str, Any]], apply: bool) -> tuple[str, bool]:
    """-> (stdout line, ok). Skips non-active campaigns; SyncError -> an `error` line."""
    name = t.get("name") or t.get("campaign_id")
    try:
        if not t.get("campaign_id"):
            raise SyncError(f"{name}: config entry has no `campaign_id`")
        want = wanted(t, copies)
        camp = api.campaign(t["campaign_id"])
        if camp.get("status") != 1:
            return f"skipped  {name} (status {camp.get('status')})", True
        cur = camp.get("sequences") or []
        check_shape(cur, want, name)
        diff = drift(cur, want)
        if not diff:
            return f"in sync  {name}", True
        if not apply:
            return f"differs  {name} slots {diff}", False
        api.patch_sequences(t["campaign_id"], patched(cur, want))
        after = api.campaign(t["campaign_id"]).get("sequences") or []
        check_shape(after, want, name)
        if drift(after, want) or not untouched(cur, after, want):
            return f"VERIFY FAIL {name}", False
        return f"updated  {name} slots {diff}", True
    except SyncError as exc:
        return f"error    {exc}", False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync A/B new-copy variants into live Instantly campaigns.")
    p.add_argument("--apply", action="store_true", help="PATCH drifted campaigns (default: dry run).")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--copy", default=str(DEFAULT_COPY))
    args = p.parse_args(argv)
    try:
        tests = load_config(args.config).get("tests") or []
        copies = load_copies(args.copy)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    bad = 0
    try:
        api = instantly_client()
        for t in tests:
            line, ok = sync_one(api, t, copies, args.apply)
            print(line)
            bad += 0 if ok else 1
    except ApiError as exc:
        print(f"API failure: {exc}", file=sys.stderr)
        return 2
    print(f"{len(tests)} campaigns, {bad} {'failures' if args.apply else 'out of sync or in error'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
