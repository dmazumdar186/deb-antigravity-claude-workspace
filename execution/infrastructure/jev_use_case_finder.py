"""Jev use case finder (Jev use case 19) -- which Jev use cases fit this operator, and where past work had Jev steps.

description: Three subcommands. `catalog` loads Jev use cases (--catalog file, else a live
             shipwithjev.com scrape, else the bundled catalog). `rank` scores each use case against an
             operator profile with one Jev call each (fit / data_ready / already_built / impact) and writes
             a ranked markdown report. `sessions` splits past-work artefacts (handoffs, notes, audits) into
             steps and asks Jev, in batches of 20, which steps a sub-second typed decision could replace.
inputs: env OPENROUTER_API_KEY (cloud alias OPENROUTER_API_TOEKN); profile markdown files; the
        directive table in directives/infrastructure/jev.md (built flags); artefact markdown files.
outputs: .tmp/jev_use_cases_for_me.md (rank), .tmp/jev_steps_found.md (sessions),
         .tmp/shipwithjev_raw.json (live scrape), ledger rows caller=jev_use_case_finder.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

CALLER = "jev_use_case_finder"
BUNDLED = _ROOT / "execution/infrastructure/jev_specs/jev_use_case_catalog.json"
JEV_MD = _ROOT / "directives/infrastructure/jev.md"
RAW_OUT = _ROOT / ".tmp/shipwithjev_raw.json"
SITE_URLS = ["https://shipwithjev.com", "https://shipwithjev.com/use-cases", "https://shipwithjev.com/sitemap.xml"]
UA = "Mozilla/5.0 (X11; Linux x86_64) jev-use-case-finder/1.0"
DEFAULT_PROFILES = [".claude/notes/general.md", "directives/README.md", "HANDOFF.md"]
PROFILE_CHARS = 6000
STEP_BATCH = 20
MAX_QUESTIONS = 40
PRIMITIVES = {"classify": "Sort into a fixed set of categories", "pick_from_menu": "Pick one item from a list",
              "score": "Rate on an ordered scale", "gate": "Yes/no go-no-go decision",
              "not_a_jev_step": "Needs generation or reasoning, not a typed decision"}
IMPACTS = {"saves_tokens": "Replaces LLM calls, cutting token spend", "saves_time": "Saves operator time",
           "new_revenue": "Enables something sellable to clients", "new_capability": "Adds a capability not possible today",
           "none": "No meaningful impact"}
FIT_LEVELS = ["irrelevant to this operator", "occasionally useful", "useful for regular work",
              "core to this operator's daily work"]


def _safe_path(p: str | Path) -> Path:
    path = (_ROOT / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    if _ROOT not in path.parents and path != _ROOT:
        raise SystemExit(f"path outside repo refused: {p}")
    return path


# ---- catalog -----------------------------------------------------------------------------

class _CardParser(HTMLParser):
    """Collect heading text followed by the next paragraph as (title, description)."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._tag = ""
        self._buf: list[str] = []
        self._pending: str | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("h2", "h3", "h4", "p", "loc"):
            self._tag, self._buf = tag, []

    def handle_endtag(self, tag: str) -> None:
        if tag != self._tag:
            return
        text = " ".join("".join(self._buf).split())
        self._tag = ""
        if not text:
            return
        if tag in ("h2", "h3", "h4"):
            self._pending = text
        elif tag == "p" and self._pending:
            self.items.append({"title": self._pending, "description": text[:200]})
            self._pending = None
        elif tag == "loc":
            self.items.append({"title": text.rstrip("/").rsplit("/", 1)[-1].replace("-", " "), "description": text})

    def handle_data(self, data: str) -> None:
        if self._tag:
            self._buf.append(data)


def fetch_live(timeout: float = 20.0) -> list[dict[str, Any]]:
    """Best-effort scrape of shipwithjev.com. Returns [] when blocked or empty."""
    raw: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    for url in SITE_URLS:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        except requests.RequestException as exc:
            raw[url] = {"error": f"{exc.__class__.__name__}: {exc}"[:300]}
            continue
        raw[url] = {"status": r.status_code, "chars": len(r.text)}
        if r.status_code != 200:
            continue
        p = _CardParser()
        p.feed(r.text)
        raw[url]["items"] = p.items
        items.extend(p.items)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUT.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    seen: set[str] = set()
    out = []
    for it in items:
        key = it["title"].lower()
        if key in seen or len(key) < 3 or key.startswith(("visit ", "learn", "page ")) or "://" in it["title"]:
            continue
        seen.add(key)
        out.append({"id": "web_" + re.sub(r"\W+", "_", key)[:40], "title": it["title"], "category": "shipwithjev",
                    "description": it["description"], "inputs": [], "effort": 2})
    return out


def load_catalog(path: str | None = None, live: bool = True) -> tuple[list[dict[str, Any]], str]:
    """--catalog file > live shipwithjev.com scrape (if `live`) > bundled catalog."""
    if path:
        data = json.loads(_safe_path(path).read_text(encoding="utf-8"))
        return (data.get("use_cases", data) if isinstance(data, dict) else data), "file"
    if live:
        got = fetch_live()
        if len(got) >= 5:
            return got, "live"
    data = json.loads(BUNDLED.read_text(encoding="utf-8"))
    return data["use_cases"], "bundled"


def built_numbers(jev_md: Path = JEV_MD) -> set[int]:
    """Use-case numbers marked ✅ in the directive table."""
    if not jev_md.exists():
        return set()
    out = set()
    for line in jev_md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|[^|]*\|\s*✅", line)
        if m:
            out.add(int(m.group(1)))
    return out


def is_built(uc: dict[str, Any], built: set[int]) -> bool:
    m = re.match(r"rn(\d+)_", str(uc.get("id", "")))
    return bool(m and int(m.group(1)) in built)


# ---- rank --------------------------------------------------------------------------------

def load_profile(paths: list[str]) -> str:
    parts = []
    for p in paths:
        fp = _safe_path(p)
        if fp.exists():
            parts.append(f"## {p}\n" + fp.read_text(encoding="utf-8", errors="replace")[:PROFILE_CHARS])
    return "\n\n".join(parts)


RANK_QUESTIONS = {
    "fit": jev_client.score("How useful is this Jev use case for the operator described in profile_excerpt?", FIT_LEVELS),
    "data_ready": jev_client.noul("Judging from the profile, does the operator already have the inputs this use case needs?",
                                  "The operator already has these inputs", "The operator would need to collect new data"),
    "already_built": jev_client.noul("Is this use case already implemented here? `built` in state is authoritative when true.",
                                     "Already implemented in this workspace", "Not implemented yet"),
    "impact": jev_client.choice("What is the main impact of building this for the operator?", IMPACTS),
}


def rank_value(fit: float, data_ready: float) -> float:
    return round(fit * (1 + data_ready), 3)


def is_quick_win(row: dict[str, Any]) -> bool:
    return row["fit"] >= 2 and row["data_ready"] >= 0.6 and int(row.get("effort", 3)) == 1


def rank(catalog: list[dict[str, Any]], profile: str, built: set[int], include_built: bool = False) -> list[dict[str, Any]]:
    excerpt = profile[:20000]
    states = []
    for uc in catalog:
        b = is_built(uc, built)
        states.append({"profile_excerpt": excerpt, "use_case": {**uc, "built": b}})
    results = jev_client.decide_many(states, RANK_QUESTIONS, timeout_s=20.0)
    rows = []
    cost = 0.0
    errors = 0
    for st, r in zip(states, results):
        uc = st["use_case"]
        cost += r.cost_usd
        errors += 0 if r.ok else 1
        fit, dr = r.score("fit"), r.noul("data_ready")
        built_flag = uc["built"]
        rows.append({**uc, "fit": fit, "data_ready": dr, "already_built_p": r.noul("already_built"),
                     "impact": r.choice("impact", "none"), "rank": rank_value(fit, dr), "built": built_flag,
                     "error": r.error})
    jev_client.append_ledger({"caller": CALLER, "mode": "rank", "n": len(rows), "errors": errors, "cost_usd": cost})
    if not include_built:
        rows = [r for r in rows if not r["built"]]
    rows.sort(key=lambda r: r["rank"], reverse=True)
    return rows


def render_rank(rows: list[dict[str, Any]], top: int, source: str) -> str:
    lines = [f"# Jev use cases for me\n\nCatalog source: {source}. Ranked by fit x (1 + data_ready).\n",
             "| # | Use case | Category | Fit (0-3) | Data ready | Impact | Effort | Rank |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:top], 1):
        lines.append(f"| {i} | {r['title']} | {r['category']} | {r['fit']:.2f} | {r['data_ready']:.2f} | "
                     f"{r['impact']} | {r.get('effort', '?')} | {r['rank']:.2f} |")
    qw = [r for r in rows if is_quick_win(r)]
    lines.append("\n## Quick wins (fit >= 2, data ready >= 0.6, effort 1)\n")
    lines += [f"- **{r['title']}** — {r['description']}" for r in qw] or ["- none"]
    nd = [r for r in rows if r["fit"] >= 2 and r["data_ready"] < 0.6]
    lines.append("\n## Needs data first\n")
    lines += [f"- **{r['title']}** — needs: {', '.join(r.get('inputs') or []) or 'see description'}" for r in nd] or ["- none"]
    return "\n".join(lines) + "\n"


# ---- sessions ----------------------------------------------------------------------------

def default_sources() -> list[Path]:
    out = sorted(_ROOT.glob("HANDOFF*.md"))
    for pat in (".claude/handoffs/*.md", ".claude/notes/**/*.md", "docs/audits/*.md"):
        out += sorted(_ROOT.glob(pat))
    return out


def split_steps(text: str, min_words: int = 8) -> list[str]:
    steps = []
    for block in re.split(r"\n\s*\n", text):
        bullets = re.split(r"\n\s*(?:[-*+]|\d+[.)])\s+", "\n" + block)
        for b in bullets:
            s = " ".join(b.split()).lstrip("-*+ ")
            if s.startswith("#") or s.startswith("|") or s.startswith("```"):
                continue
            if len(s.split()) >= min_words:
                steps.append(s[:600])
    return steps


def step_questions(n: int) -> dict[str, dict[str, Any]]:
    q: dict[str, dict[str, Any]] = {}
    for i in range(n):
        q[f"s{i}_jev"] = jev_client.noul(
            f"Step i={i}: Could a sub-second typed decision (classify / pick / score) have replaced an LLM call or manual step here?",
            "Yes, a typed decision would have done the job", "No, it needs generation, reasoning or real work")
        q[f"s{i}_prim"] = jev_client.choice(f"Step i={i}: which Jev primitive fits?", PRIMITIVES)
    assert len(q) <= MAX_QUESTIONS
    return q


def batches(items: list[Any], size: int = STEP_BATCH) -> list[list[Any]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def find_steps(steps: list[dict[str, str]], min_prob: float = 0.7) -> list[dict[str, Any]]:
    found = []
    cost = 0.0
    for batch in batches(steps):
        state = {"steps": [{"i": i, "text": s["text"]} for i, s in enumerate(batch)]}
        r = jev_client.decide(state, step_questions(len(batch)), timeout_s=30.0)
        cost += r.cost_usd
        for i, s in enumerate(batch):
            p = r.noul(f"s{i}_jev")
            prim = r.choice(f"s{i}_prim", "not_a_jev_step")
            if p >= min_prob and prim != "not_a_jev_step":
                found.append({**s, "prob": p, "primitive": prim})
    jev_client.append_ledger({"caller": CALLER, "mode": "sessions", "n": len(steps), "found": len(found), "cost_usd": cost})
    return found


def render_steps(found: list[dict[str, Any]], scanned: int) -> str:
    lines = [f"# Jev steps found in past work\n\n{len(found)} of {scanned} steps could have been a Jev call.\n"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in found:
        groups[f["source"]].append(f)
    for src, items in groups.items():
        lines.append(f"\n## {src}\n")
        for f in items:
            lines.append(f"- [{f['primitive']}, p={f['prob']:.2f}] {f['text']}")
    return "\n".join(lines) + "\n"


# ---- CLI ---------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog")
    c.add_argument("--catalog")
    c.add_argument("--no-live", action="store_true")
    r = sub.add_parser("rank")
    r.add_argument("--profile", action="append")
    r.add_argument("--catalog")
    r.add_argument("--live", action="store_true", help="rank the live shipwithjev.com gallery (hundreds of builds)")
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--include-built", action="store_true")
    r.add_argument("--out", default=".tmp/jev_use_cases_for_me.md")
    s = sub.add_parser("sessions")
    s.add_argument("--dir")
    s.add_argument("--glob", default="*.md")
    s.add_argument("--min-prob", type=float, default=0.7)
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--out", default=".tmp/jev_steps_found.md")
    a = ap.parse_args(argv)

    if a.cmd == "catalog":
        cat, src = load_catalog(a.catalog, live=not a.no_live)
        print(f"source: {src}  total: {len(cat)}")
        for k, v in Counter(u.get("category", "?") for u in cat).most_common():
            print(f"  {k}: {v}")
        return 0
    if a.cmd == "rank":
        cat, src = load_catalog(a.catalog, live=a.live)
        profile = load_profile(a.profile or DEFAULT_PROFILES)
        rows = rank(cat, profile, built_numbers(), a.include_built)
        out = _safe_path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        md = render_rank(rows, a.top, src)
        out.write_text(md, encoding="utf-8")
        print(md)
        return 0
    files = sorted(_safe_path(a.dir).rglob(a.glob)) if a.dir else default_sources()
    steps = []
    for f in files:
        rel = str(f.relative_to(_ROOT))
        steps += [{"source": rel, "text": t} for t in split_steps(f.read_text(encoding="utf-8", errors="replace"))]
    if a.limit:
        steps = steps[:a.limit]
    found = find_steps(steps, a.min_prob)
    out = _safe_path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md = render_steps(found, len(steps))
    out.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
