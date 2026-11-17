"""Safeguard tests for execution/infrastructure/openmausbot/client_bots.py.

description: Proves each client_bots.py gate fires on input it must catch, and the happy path is idempotent.
inputs: none (builds fixture rosters in a temp dir).
outputs: stdout PASS/FAIL lines; exit 1 on any failure. Run: python3 tests/test_openmausbot_client_bots.py
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "client_bots", ROOT / "execution/infrastructure/openmausbot/client_bots.py"
)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

RULES = (
    "\n## Rules\n- Only facts in this brief.\n- "
    + cb.RULES_MARKER
    + "\n- Draft only.\n"
)
BODY = "You are the account assistant for {name}. " + "They run a small business. " * 15


def make(tmp: Path, clients: list[dict], souls: dict[str, str]) -> Path:
    (tmp / "clients").mkdir(exist_ok=True)
    for slug, text in souls.items():
        (tmp / "clients" / f"{slug}.md").write_text(text, encoding="utf-8")
    roster = tmp / "clients.json"
    roster.write_text(json.dumps(clients), encoding="utf-8")
    return roster


def row(slug, name, status="client", soul=None):
    return {
        "slug": slug,
        "name": name,
        "status": status,
        "sector": "retail",
        "scope": "website",
        "evidence": [{"quote": "x", "source": "a.md:1"}],
        "soul_file": soul or f"clients/{slug}.md",
    }


def run(roster: Path, *extra) -> int:
    return cb.main(
        [
            "--roster",
            str(roster),
            "--out",
            str(roster.parent / "client_team.json"),
            *extra,
        ]
    )


results = []


def case(label, expect_code, clients, souls, *extra):
    with tempfile.TemporaryDirectory() as d:
        roster = make(Path(d), clients, souls)
        code = run(roster, *extra)
        ok = code == expect_code
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}: {label} (exit {code}, want {expect_code})")
        return Path(d), code


good = {
    "acme": BODY.format(name="Acme") + RULES,
    "zen": BODY.format(name="Zen Yoga") + RULES,
}

# Happy path + idempotency
with tempfile.TemporaryDirectory() as d:
    roster = make(
        Path(d),
        [
            row("acme", "Acme"),
            row("zen", "Zen Yoga"),
            row("p", "Prospect Co", "prospect"),
        ],
        good,
    )
    c1 = run(roster)
    out = Path(d) / "client_team.json"
    first = out.read_text()
    team = json.loads(first)
    c2 = run(roster)
    ok = (
        c1 == 0
        and c2 == 0
        and out.read_text() == first
        and len(team["bots"]) == 2
        and team["defaults"]["computer"] == "off"
        and team["defaults"]["approval"] == "ask"
        and {b["team"] for b in team["bots"]} == {"Client: Acme", "Client: Zen Yoga"}
    )
    results.append(ok)
    print(
        f"{'PASS' if ok else 'FAIL'}: happy path, prospects excluded, one team per client, re-run identical"
    )

case("prospects included only with flag", 2, [row("p", "Prospect Co", "prospect")], {})
case(
    "soul naming another client is refused",
    2,
    [row("acme", "Acme"), row("zen", "Zen Yoga")],
    {
        "acme": BODY.format(name="Acme") + " Unlike Zen Yoga, they..." + RULES,
        "zen": good["zen"],
    },
)
case(
    "third-party email in soul is refused",
    2,
    [row("acme", "Acme")],
    {"acme": BODY.format(name="Acme") + " Owner: priya@acme.in" + RULES},
)
case(
    "missing Rules block is refused",
    2,
    [row("acme", "Acme")],
    {"acme": BODY.format(name="Acme") * 2},
)
case(
    "secret-like token is refused",
    2,
    [row("acme", "Acme")],
    {"acme": BODY.format(name="Acme") + " key sk-abcdefghijklmnopqrstuv" + RULES},
)
case("too-short soul is refused", 2, [row("acme", "Acme")], {"acme": "Hi." + RULES})
case("missing soul file is refused", 2, [row("acme", "Acme")], {})
case(
    "path traversal in soul_file is refused",
    2,
    [row("acme", "Acme", soul="../../etc/passwd")],
    {},
)
case(
    "duplicate client is refused",
    2,
    [row("acme", "Acme"), row("acme2", "ACME")],
    {"acme": good["acme"], "acme2": good["acme"]},
)
case(
    "row without evidence is refused",
    2,
    [dict(row("acme", "Acme"), evidence=[])],
    {"acme": good["acme"]},
)
case(
    "partial name of another client (bracketed form) is refused",
    2,
    [row("acme", "Acme"), row("am", "Accessory Masters (Elite Broker Group)")],
    {
        "acme": BODY.format(name="Acme") + " Like Accessory Masters did." + RULES,
        "am": BODY.format(name="Accessory Masters") + RULES,
    },
)
case(
    "contact person of another client is refused",
    2,
    [row("acme", "Acme"), row("g", "Gaia Talent (Keith Molony)")],
    {
        "acme": BODY.format(name="Acme") + " Ask Keith about it." + RULES,
        "g": BODY.format(name="Gaia") + RULES,
    },
)
case(
    "allowed signature email passes",
    0,
    [row("acme", "Acme")],
    {"acme": BODY.format(name="Acme") + " Sign as debanjan@prodcraft.fyi" + RULES},
)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
