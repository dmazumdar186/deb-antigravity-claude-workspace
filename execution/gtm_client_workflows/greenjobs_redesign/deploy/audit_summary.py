"""Summarise `npm audit --json` and `pip-audit -f json` output (offline parser).

description: counts HIGH/CRITICAL findings per ecosystem (pip-audit JSON has no severity, so every
  advisory counts); a missing or unparseable input is null (not measured), never 0.
  Exit 1 when any finding exists or an input is missing/unreadable.
inputs: --npm FILE --pip FILE --write-json PATH --out-md FILE (issue body)
outputs: summary on stdout, optional JSON section "audit", optional markdown
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch_state  # noqa: E402

BAD = {"high", "critical"}


def load(p: Path | None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")) if p else None
    except (OSError, ValueError):
        return None


def npm_findings(d) -> list[str] | None:
    if not isinstance(d, dict) or not isinstance(d.get("vulnerabilities"), dict):
        return None
    return sorted(
        f"{n} ({v.get('severity')})"
        for n, v in d["vulnerabilities"].items()
        if str(v.get("severity")).lower() in BAD
    )


def pip_findings(d) -> list[str] | None:
    deps = d.get("dependencies") if isinstance(d, dict) else d
    if not isinstance(deps, list):
        return None
    return sorted(
        f"{dep.get('name')}=={dep.get('version')} {v.get('id')}"
        for dep in deps
        for v in dep.get("vulns", [])
    )


def summarise(npm, pip) -> dict:
    n, p = npm_findings(npm), pip_findings(pip)
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "npm_high_critical": None if n is None else len(n),
        "pip_advisories": None if p is None else len(p),
        "findings": (n or []) + (p or []),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--npm", type=Path)
    ap.add_argument("--pip", type=Path)
    ap.add_argument("--write-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    a = ap.parse_args(argv)
    s = summarise(load(a.npm), load(a.pip))
    if a.write_json:
        patch_state.merge_write(a.write_json, "audit", s)
    unmeasured = s["npm_high_critical"] is None or s["pip_advisories"] is None
    md = [f"GreenJobs weekly dependency audit {s['at']}", ""]
    md += [f"- {f}" for f in s["findings"]] or ["- no HIGH/CRITICAL findings"]
    if unmeasured:
        md.append(
            "- an audit output was missing or unreadable (not measured): check the job log"
        )
    print("\n".join(md))
    if a.out_md:
        a.out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    return 1 if (s["findings"] or unmeasured) else 0


if __name__ == "__main__":
    raise SystemExit(main())
