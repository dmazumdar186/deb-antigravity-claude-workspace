"""
inline_manifest.py
description: Reads manifest.json and inlines it into wrangler.toml's MANIFEST_JSON var so the Worker sees the current project list at deploy time. Idempotent; safe to run repeatedly. No network calls; no LLM calls.
inputs: manifest.json (adjacent to this script), wrangler.toml (adjacent).
outputs: Rewrites wrangler.toml with the MANIFEST_JSON var updated to the stringified manifest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "manifest.json"
WRANGLER_PATH = HERE / "wrangler.toml"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest.json not found at {MANIFEST_PATH}")
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _quote_for_toml(payload: str) -> str:
    # TOML basic strings escape backslash and double-quote.  Manifest JSON is
    # ASCII-safe (or at least should be), but be defensive about \ and ".
    escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
    # Newlines inside a TOML basic string are forbidden; JSON.dumps with the
    # default separators produces a single-line string, so this is a safety
    # assertion rather than a transformation.
    if "\n" in escaped or "\r" in escaped:
        raise ValueError("manifest JSON contained a newline; cannot inline into TOML basic string")
    return f'"{escaped}"'


def _replace_var(toml_body: str, var_name: str, new_value_literal: str) -> str:
    """Replace `VAR = "..."` inside the [vars] block. Preserves everything else byte-for-byte where possible.

    We do a linewise pass rather than a full TOML parse to avoid a dependency and to preserve comments/formatting.
    """
    lines = toml_body.splitlines(keepends=False)
    out: list[str] = []
    in_vars = False
    replaced = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("["):
            in_vars = stripped.startswith("[vars]")
            out.append(line)
            continue
        if in_vars and stripped.startswith(f"{var_name} ") and "=" in stripped:
            leading = line[: len(line) - len(stripped)]
            out.append(f"{leading}{var_name} = {new_value_literal}")
            replaced = True
            continue
        out.append(line)
    if not replaced:
        raise ValueError(f"[vars] {var_name} = ... line not found in wrangler.toml")
    return "\n".join(out) + ("\n" if toml_body.endswith("\n") else "")


def main() -> int:
    manifest = _load_manifest()
    payload = json.dumps(manifest, separators=(",", ":"), ensure_ascii=True)
    literal = _quote_for_toml(payload)

    toml_body = WRANGLER_PATH.read_text(encoding="utf-8")
    new_body = _replace_var(toml_body, "MANIFEST_JSON", literal)

    if new_body == toml_body:
        print(f"inline_manifest: no change (already up to date; {len(payload)} bytes)")
        return 0

    WRANGLER_PATH.write_text(new_body, encoding="utf-8")
    project_count = len(manifest.get("projects", []))
    print(
        f"inline_manifest: wrote {len(payload)} bytes of manifest ({project_count} projects) into wrangler.toml",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
