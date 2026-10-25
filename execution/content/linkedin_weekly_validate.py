"""
description: Validation gate for the ProdCraft weekly LinkedIn cards: numeric-claim check against the claim registry, Playwright text-overflow check on rendered HTML, and a Jev-scored six-part 30-point review (>=24 + claims pass = PUBLISHABLE). A v2 dir (messages_v2.json, from linkedin_weekly_cards_v2.py) is detected automatically: the claim gate then runs over headline, card_fact, annotation, caption, cta line and every carousel slide's title/body (verbatim code panes and fixed kicker labels are exempt), and the overflow check covers every slide plus a two-line headline check.
inputs: --out <render dir with messages.json or messages_v2.json + html/> (default latest deliverables/linkedin_weekly_cards/prodcraft/<date>); --weeks 1-10 (optional subset); --claims execution/content/prodcraft_claim_registry.json; --scores <json {week: {criterion: 0-5}}> manual fallback; --no-jev; env OPENROUTER_API_KEY or OPENROUTER_API_TOEKN; env PW_CHROME (optional)
outputs: <out>/validation_report.md, <out>/validation_report.json, one ledger row in .tmp/jev_ledger.jsonl (caller linkedin_weekly_validate); exit 1 if any week fails claims or overflows
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from execution.content.linkedin_weekly_cards import SAFE, H, W, chromium_path, parse_weeks  # noqa: E402

LEDGER = ROOT / ".tmp" / "jev_ledger.jsonl"
NUM_RE = re.compile(r"[$€£]?\d(?:[\d,.]*\d)?\s*(?:%|[kKmM](?![a-zA-Z])\+?|\+)?|[²³¹¼½¾]")
WORD_NUM_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
                         r"sixty|seventy|eighty|ninety|dozen|hundred|thousand|million|billion|double|triple|half|quarter)\b", re.I)
NORM_RE = re.compile(r"[$,+\u2212\-%\s]")
GATE = 24
LEVELS = ["0 absent", "1 weak", "2 partial", "3 adequate", "4 strong", "5 excellent"]
CRITERIA = {
    "reader": "Does this post speak to ONE identifiable reader (a founder, a product/ops leader, or a sales/revenue operator) rather than everyone? 0 = no reader, 5 = one unmistakable reader.",
    "situation": "Does it name ONE specific situation the reader recognises (a concrete workflow, moment or failure), not a generic topic? 0 = abstract, 5 = vivid specific situation.",
    "point_of_view": "Does the headline take a clear, arguable point of view? 0 = platitude, 5 = sharp stance someone could disagree with.",
    "useful": "Does the card plus companion angle give a useful lesson, test or checklist the reader can apply? 0 = nothing to apply, 5 = directly applicable.",
    "voice": "Does the copy sound like a natural human practitioner, not AI-consultant marketing or engagement bait? 0 = salesy/generic, 5 = natural, plain voice.",
    "visual_clarity": "Given the visual direction, will the image carry one idea clearly with only a headline, one supporting line and at most one diagram? 0 = cluttered, 5 = one clear idea.",
}


def numeric_tokens(text: str) -> list[str]:
    return [m.group(0).strip() for m in NUM_RE.finditer(text)]


def norm(s: str) -> str:
    return NORM_RE.sub("", s).lower()


def token_ok(tok: str, text: str, week: int, claims: list[dict]) -> bool:
    """Exact normalised match: tok equals the numeric core of an approved match phrase for this week that appears in full in text."""
    low, word = text.lower(), tok.isalpha()
    for c in claims:
        if c["status"] != "approved" or week not in c["weeks"]:
            continue
        for m in c.get("match", []):
            if m.lower() not in low:
                continue
            if word and tok.lower() in re.findall(r"[a-z]+", m.lower()):
                return True
            core = NUM_RE.search(m)
            if not word and core and norm(tok) == norm(core.group(0)):
                return True
    return False


def gated_texts(row: dict) -> dict[str, str]:
    """Every copy field that reaches the image (v2 rows: plus caption, card fact, note, CTA line and slide text)."""
    if row.get("format"):
        t = {"headline": row["headline"], "card_fact": row["card_fact"], "caption": row.get("caption", ""),
             "annotation": row.get("annotation", ""), "cta_line": row.get("cta_line", ""), "alt_text": row.get("alt_text", "")}
        for i, sl in enumerate(row.get("slides", [])):  # kicker ("case 1 · ...") is a fixed label; code is a verbatim quoted artefact
            t[f"slide_{i + 1}_title"] = sl.get("title", "")
            t[f"slide_{i + 1}_body"] = sl.get("body", "")
        return {k: v for k, v in t.items() if v}
    t = {"headline": row["headline"], "supporting_line": row.get("rendered_supporting_line", row["supporting_line"]),
         "theme": row.get("theme", ""), "cta": row.get("cta_text", "")}
    for i, (_k, v) in enumerate(row.get("receipt_rows", [])):
        t[f"receipt_{i}"] = v  # labels (case/note NN) are fixed template text; values carry the copy
    for i, v in enumerate(row.get("visual_words", [])):
        t[f"visual_{i}"] = v  # words drawn on the diagram; list numerals 01/02/03 and "wk NN" are fixed labels, not gated
    return t


def check_claims(row: dict, claims: list[dict]) -> list[str]:
    """Return failure reasons for the copy that actually rendered (headline + rendered supporting line)."""
    if row.get("verdict") == "blocked":
        return [f"blocked: {row.get('blocked_reason', 'not rendered')}"]
    reasons = []
    for field, text in gated_texts(row).items():
        for c in claims:
            if c["status"] == "retired" and any(m.lower() in text.lower() for m in c.get("match", [])):
                reasons.append(f"{field}: retired value '{c['claim_text']}'")
        for tok in numeric_tokens(text) + WORD_NUM_RE.findall(text):
            if not token_ok(tok, text, row["week"], claims):
                reasons.append(f"{field}: number '{tok}' has no approved claim for week {row['week']}")
    return reasons


def check_overflow(out: Path, rows: list[dict]) -> dict[int, list[str]]:
    from playwright.sync_api import sync_playwright
    js = """([W,H,S]) => { const bad=[]; const h1=document.querySelector('h1'); if (h1 && h1.dataset.lines && +h1.dataset.lines>2) bad.push('h1 '+h1.dataset.lines+' lines');
      document.querySelectorAll('.t, .vis, .main, .pane').forEach((el,i)=>{
      const r=el.getBoundingClientRect(); const tag=(el.className||el.tagName)+'#'+i;
      if (el.scrollHeight>el.clientHeight+2 || el.scrollWidth>el.clientWidth+2) bad.push(tag+' scroll '+el.scrollHeight+'>'+el.clientHeight);
      if (el.classList.contains('t') && (r.left<S-1||r.top<S-1||r.right>W-S+1||r.bottom>H-S+1)) bad.push(tag+' outside safe box '+[r.left,r.top,r.right,r.bottom].map(Math.round));
      if (el.classList.contains('t') && el.offsetParent && (r.bottom>H||r.right>W)) bad.push(tag+' off artboard'); });
      return bad; }"""
    res: dict[int, list[str]] = {}
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium_path())
        pg = br.new_page(viewport={"width": W, "height": H})
        base = out.resolve()
        for r in rows:
            if not r.get("html"):
                continue  # blocked week; reported as a claims FAIL
            found: list[str] = []
            for rel in [r["html"], *r.get("slides_html", [])[1:]]:
                f = (out / rel).resolve()
                if not f.is_relative_to(base):
                    raise ValueError(f"html path escapes out dir: {rel}")
                if not f.exists():
                    print(f"note: week {r['week']:02d} {rel} absent (not in --weeks subset); overflow skipped", file=sys.stderr)
                    continue
                pg.goto(f.as_uri())
                pg.wait_for_timeout(150)
                pg.evaluate("window.fitHead && window.fitHead()")
                found += [f"{Path(rel).stem}: {x}" for x in pg.evaluate(js, [W, H, SAFE])]
            res[r["week"]] = found
        br.close()
    return res


def jev_scores(rows: list[dict]) -> tuple[dict[int, dict[str, float] | None], float, str | None]:
    from execution.modules import jev_client as jev
    qs = {k: jev.score(v, LEVELS) for k, v in CRITERIA.items()}
    states = [{k: r[k] for k in ("headline", "companion_post", "theme", "visual_direction")} | {"supporting_line": r.get("rendered_supporting_line", r["supporting_line"])}
              | ({"caption": r["caption"], "card_fact": r["card_fact"]} if r.get("format") else {}) for r in rows]  # v2: the finished caption is scored, not the angle
    results = jev.decide_many(states, qs, workers=8)
    cost, err, out = 0.0, None, {}
    for r, res in zip(rows, results):
        cost += res.cost_usd
        if res.error or not res.answers:
            out[r["week"]] = None
            err = res.error or "empty answers"
        else:
            out[r["week"]] = {k: round(res.score(k), 2) for k in CRITERIA}
    jev.append_ledger({"caller": "linkedin_weekly_validate", "cost_usd": round(cost, 6), "items": len(rows), "error": err}, LEDGER)
    return out, cost, err


def latest_out() -> Path:
    base = ROOT / "deliverables/linkedin_weekly_cards/prodcraft"
    dirs = sorted(d for d in base.glob("*") if (d / "messages.json").exists() or (d / "messages_v2.json").exists())
    if not dirs:
        raise SystemExit(f"no rendered output under {base}; run linkedin_weekly_cards.py first")
    return dirs[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="")
    ap.add_argument("--claims", default=str(ROOT / "execution/content/prodcraft_claim_registry.json"))
    ap.add_argument("--scores", default="", help="manual scores JSON {week: {criterion: 0-5}} used when Jev fails")
    ap.add_argument("--no-jev", action="store_true")
    ap.add_argument("--weeks", default="", help="validate only these weeks, ranges and lists: 1-10,15 (default all)")
    a = ap.parse_args()
    out = Path(a.out).resolve() if a.out else latest_out()
    msg = out / "messages_v2.json" if (out / "messages_v2.json").exists() else out / "messages.json"
    rows = json.loads(msg.read_text(encoding="utf-8"))["weeks"]
    only = parse_weeks(a.weeks)
    if only:
        rows = [r for r in rows if r["week"] in only]
    claims = json.loads(Path(a.claims).read_text(encoding="utf-8"))["claims"]
    manual = json.loads(Path(a.scores).read_text(encoding="utf-8")) if a.scores else {}

    overflow = check_overflow(out, rows)
    live = [r for r in rows if r.get("verdict") != "blocked"]
    scores, cost, jerr = ({}, 0.0, "skipped (--no-jev)") if a.no_jev else jev_scores(live)

    report, hard_fail = [], False
    for r in rows:
        wk = r["week"]
        claim_fail = check_claims(r, claims)
        s = scores.get(wk) or manual.get(str(wk))
        total = round(sum(s.values()), 1) if s else None
        reasons = claim_fail + [f"overflow: {x}" for x in overflow.get(wk, [])]
        if total is None:
            reasons.append("unscored (Jev unavailable, no manual score)")
        elif total < GATE:
            reasons.append(f"score {total}/30 < {GATE}")
        pending = [c["id"] + ":" + c["status"] for c in claims if wk in c["weeks"] and c["status"] not in {"approved", "retired"}]
        verdict = "PUBLISHABLE" if not reasons else "FAIL" if claim_fail or overflow.get(wk) else "HOLD"
        hard_fail |= bool(claim_fail or overflow.get(wk))
        report.append({"week": wk, "layout": r["layout"], "verdict": verdict, "score": total, "scores": s,
                       "score_source": "jev" if scores.get(wk) else "manual" if s else "unscored",
                       "claims_pass": not claim_fail, "overflow": overflow.get(wk, []), "reasons": reasons,
                       "pending_claims": pending, "used_fallback": r.get("used_fallback", False)})

    tot = [x["score"] for x in report if x["score"] is not None]
    summary = {"weeks": len(report), "publishable": sum(x["verdict"] == "PUBLISHABLE" for x in report),
               "claims_fail": [x["week"] for x in report if not x["claims_pass"]],
               "overflow_fail": [x["week"] for x in report if x["overflow"]],
               "score_ge_24": sum(t >= GATE for t in tot), "unscored": len(report) - len(tot),
               "score_min": min(tot) if tot else None, "score_median": sorted(tot)[len(tot) // 2] if tot else None,
               "score_max": max(tot) if tot else None, "jev_cost_usd": round(cost, 6), "jev_error": jerr}
    (out / "validation_report.json").write_text(json.dumps({"summary": summary, "weeks": report}, indent=2) + "\n", encoding="utf-8")
    md = ["# Validation report\n", "```", json.dumps(summary, indent=2), "```\n",
          "| wk | layout | verdict | score | claims | overflow | notes |", "|---|---|---|---|---|---|---|"]
    for x in report:
        md.append(f"| {x['week']:02d} | {x['layout']} | {x['verdict']} | {x['score']} | {'ok' if x['claims_pass'] else 'FAIL'} | "
                  f"{len(x['overflow'])} | {'; '.join(x['reasons'] + x['pending_claims'])} |")
    (out / "validation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
