"""Build an OpenMausBot team file with one bot per ProdCraft client.

description: One OpenMausBot bot (and team) per evidenced client, from clients.json + per-client souls.
inputs: --roster, --out, --include-prospects, --model, --plan | --apply, --cli; no env vars or keys.
outputs: client_team.json beside the roster; with --plan/--apply, runs `openmausbot team apply` locally.

Reads clients.json (roster with evidence) + clients/<slug>.md (each bot's soul),
validates every soul, writes client_team.json (OpenMausBot team-file format, JSON),
then optionally runs `openmausbot team apply` against a local server.

Default is offline: generate + validate only. `--plan` runs `team apply --dry-run`;
`--apply` applies (idempotent: a second apply prints "No changes.").
Directive: directives/infrastructure/openmausbot.md
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROSTER = HERE / "clients.json"
OUT = HERE / "client_team.json"

MAX_SOUL_BYTES = 24_000  # OpenMausBot limit
MIN_SOUL_CHARS = 300  # floor: a soul shorter than this has no real brief
MAX_BOTS = 50  # ceiling: more than this means the roster is wrong
RULES_MARKER = (
    "Never mention, name or compare to any other ProdCraft client or prospect."
)
ALLOWED_EMAILS = {"debanjan@prodcraft.fyi"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|xox[bp]-[A-Za-z0-9-]{10,})"
)

DEFAULTS = {
    "model": "claude/claude-opus-5-5",  # standard tier: writing from a brief
    "effort": "low",
    "approval": "ask",  # any tool use asks Debanjan first
    "computer": "off",  # no files/browser: a bot sees only its own brief
}


class RosterError(Exception):
    pass


def load_roster(path: Path, include_prospects: bool) -> list[dict]:
    if not path.exists():
        raise RosterError(f"roster missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RosterError("clients.json must be a JSON list")
    wanted = {"client"} | ({"prospect"} if include_prospects else set())
    picked, seen_slugs, seen_names = [], set(), set()
    for row in data:
        for key in ("slug", "name", "status", "soul_file", "evidence"):
            if key not in row:
                raise RosterError(
                    f"roster row missing {key!r}: {row.get('slug') or row}"
                )
        if row["status"] not in wanted:
            continue
        if not row["evidence"]:
            raise RosterError(f"{row['slug']}: no evidence; refusing to make a bot")
        slug, name = row["slug"], row["name"].strip()
        if slug in seen_slugs or name.lower() in seen_names:
            raise RosterError(f"duplicate client: {slug} / {name}")
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            raise RosterError(f"{slug}: slug must be snake_case")
        if not 1 <= len(name) <= 60 or "\n" in name:
            raise RosterError(f"{slug}: name must be 1-60 chars on one line")
        seen_slugs.add(slug)
        seen_names.add(name.lower())
        picked.append(row)
    if not picked:
        raise RosterError("no clients selected: refusing to write an empty team file")
    if len(picked) > MAX_BOTS:
        raise RosterError(f"{len(picked)} clients exceeds ceiling {MAX_BOTS}")
    return picked


def check_soul(slug: str, text: str) -> list[str]:
    """Return a list of problems; empty means the soul may ship."""
    problems = []
    size = len(text.encode("utf-8"))
    if size > MAX_SOUL_BYTES:
        problems.append(f"soul is {size} bytes > {MAX_SOUL_BYTES}")
    if len(text.strip()) < MIN_SOUL_CHARS:
        problems.append(f"soul under {MIN_SOUL_CHARS} chars")
    if RULES_MARKER not in text:
        problems.append("missing the confidentiality Rules block")
    for email in sorted(set(EMAIL_RE.findall(text)) - ALLOWED_EMAILS):
        problems.append(f"email address in soul: {email!r}")
    for hit in SECRET_RE.findall(text):
        problems.append(f"secret-like token in soul: {hit[:6]}…")
    return problems


def check_isolation(rows: list[dict], souls: dict[str, str]) -> list[str]:
    """A client's soul must not name another client (confidentiality)."""
    problems = []
    for row in rows:
        for other in rows:
            if other is row:
                continue
            if re.search(
                rf"\b{re.escape(other['name'])}\b", souls[row["slug"]], re.IGNORECASE
            ):
                problems.append(
                    f"{row['slug']}: soul names another client {other['name']!r}"
                )
    return problems


def build_team(rows: list[dict]) -> dict:
    teams, bots = [], []
    for row in rows:
        team = f"Client: {row['name']}"
        teams.append(
            {
                "name": team,
                "brief": (
                    f"Account workspace for {row['name']} ({row.get('sector', 'client')}). "
                    "Confidential: nothing here is shared with other clients."
                ),
            }
        )
        bots.append(
            {
                "name": row["name"],
                "team": team,
                "title": f"{row['name']} account assistant"[:200],
                "description": (row.get("scope") or "")[:200],
                "soul": {"file": row["soul_file"]},
            }
        )
    return {"version": 1, "defaults": dict(DEFAULTS), "teams": teams, "bots": bots}


def find_cli() -> list[str] | None:
    exe = shutil.which("openmausbot")
    return [exe] if exe else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--roster", type=Path, default=ROSTER)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--include-prospects", action="store_true", help="also make bots for prospects"
    )
    ap.add_argument(
        "--model", default=DEFAULTS["model"], help="INSTANCE/MODEL for every bot"
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--plan", action="store_true", help="run `openmausbot team apply --dry-run`"
    )
    mode.add_argument(
        "--apply", action="store_true", help="apply to the local OpenMausBot server"
    )
    ap.add_argument("--cli", nargs="+", help="openmausbot command (default: on PATH)")
    args = ap.parse_args(argv)

    try:
        rows = load_roster(args.roster, args.include_prospects)
    except (RosterError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    base = args.roster.parent
    souls, problems = {}, []
    for row in rows:
        path = (base / row["soul_file"]).resolve()
        if not path.is_relative_to(base.resolve()):
            problems.append(f"{row['slug']}: soul_file escapes the roster folder")
            continue
        if not path.exists():
            problems.append(f"{row['slug']}: soul file missing ({row['soul_file']})")
            continue
        souls[row["slug"]] = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        problems += [
            f"{row['slug']}: {p}" for p in check_soul(row["slug"], souls[row["slug"]])
        ]
    if not problems:
        problems += check_isolation(rows, souls)
    if problems:
        print("REFUSED: souls failed validation:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    team = build_team(rows)
    team["defaults"]["model"] = args.model
    # Soul paths are relative to the team file, so it must sit beside the roster.
    if args.out.resolve().parent != base.resolve():
        print(
            "ERROR: --out must be in the roster's folder (soul paths are relative)",
            file=sys.stderr,
        )
        return 2
    new = json.dumps(team, indent=2, ensure_ascii=False) + "\n"
    old = args.out.read_text(encoding="utf-8") if args.out.exists() else None
    if new != old:
        args.out.write_text(new, encoding="utf-8")
    print(
        f"{'wrote' if new != old else 'unchanged'} {args.out.name}: {len(rows)} client bot(s): "
        + ", ".join(r["name"] for r in rows)
    )

    if not (args.plan or args.apply):
        return 0
    cli = args.cli or find_cli()
    if not cli:
        print(
            "ERROR: openmausbot CLI not found; pass --cli or `npm i -g openmausbot`",
            file=sys.stderr,
        )
        return 3
    cmd = [*cli, "team", "apply", str(args.out)] + (["--dry-run"] if args.plan else [])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(f"ERROR: team apply exited {proc.returncode}", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
