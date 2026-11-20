"""Monthly Cloudflare compatibility_date check (offline: reads wrangler.toml only).

description: reports when compatibility_date is more than --max-age-days (default 90) old and lists the
  compatibility_flags in use (all envs) to review against the Cloudflare compatibility-date changelog.
  Never edits wrangler.toml: bumping it is a normal change through CI -> staging smoke -> gated promote.
inputs: --toml PATH --today YYYY-MM-DD (default: now) --max-age-days N --write-json PATH
outputs: report on stdout; exit 0 current, 1 stale (the workflow turns this into an issue); 2 unreadable
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch_state  # noqa: E402

TOML = Path(__file__).resolve().parents[1] / "platform_worker" / "wrangler.toml"
CHANGELOG = (
    "https://developers.cloudflare.com/workers/configuration/compatibility-flags/"
)


def check(toml_text: str, today: date, max_age_days: int = 90) -> dict:
    data = tomllib.loads(toml_text)
    raw = data.get("compatibility_date")
    flags: set[str] = set(data.get("compatibility_flags", []))
    for env in (data.get("env") or {}).values():
        flags.update(env.get("compatibility_flags", []))
        raw = raw or env.get("compatibility_date")
    if not raw:
        raise ValueError("compatibility_date not found")
    d = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
    age = (today - d).days
    return {
        "at": today.isoformat(),
        "compatibility_date": d.isoformat(),
        "age_days": age,
        "max_age_days": max_age_days,
        "stale": age > max_age_days,
        "flags_to_review": sorted(flags),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--toml", type=Path, default=TOML)
    ap.add_argument(
        "--today", type=date.fromisoformat, default=datetime.now(timezone.utc).date()
    )
    ap.add_argument("--max-age-days", type=int, default=90)
    ap.add_argument("--write-json", type=Path)
    a = ap.parse_args(argv)
    try:
        r = check(a.toml.read_text(encoding="utf-8"), a.today, a.max_age_days)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        print(f"compat_check: cannot read compatibility_date: {e}", file=sys.stderr)
        return 2
    if a.write_json:
        patch_state.merge_write(a.write_json, "compat", r)
    state = "STALE" if r["stale"] else "ok"
    print(
        f"compatibility_date {r['compatibility_date']} is {r['age_days']} days old (limit {r['max_age_days']}): {state}"
    )
    print(
        "flags to review: "
        + (
            ", ".join(r["flags_to_review"])
            or "none set (review the date's changelog only)"
        )
    )
    if r["stale"]:
        print(
            f"Review {CHANGELOG}, bump compatibility_date in a normal change (CI -> staging smoke -> promote)."
        )
    return 1 if r["stale"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
