"""
Shortlist Check -- the Keith-facing render (deliverables/gaia_poc_check/PLAN.md
step 4; copy source of truth is deliverables/gaia_poc_check/keith_copy.md).

`render_check_page(results)` turns a `check_results.json` document (contract
in PLAN.md) into one self-contained HTML string: no network call, no
external image, no library. `write_check_page(results_path, out_path)` reads
the JSON off disk and writes the rendered page.

Every sentence in keith_copy.md is final copy; this module never rewords it.
Only the values marked {computed} in that file are substituted in, straight
from the JSON -- nothing here invents a number. Every string pulled from the
JSON (names, employers, quotes, URLs) is passed through `e()` --
`html.escape` -- before it reaches the page.

Banned words (keith_copy.md's own rule): AI, LLM, model, platform, pipeline,
automated, system, agent, algorithm. The static copy in this module is
guaranteed never to contain one of those words -- `render_check_page` checks
it on every call by re-rendering with every field the caller's data can
reach (`rows`, `pool`, `brief`, `summary`, `campaign`, `input`) emptied out
and running `banned_words_in` over that static-only render, raising
`ValueError` if the check fails (a firm name in the caller's data is allowed
to contain one of these words, e.g. "... Systems Ltd" -- only the copy this
module authored is ever checked).
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["render_check_page", "write_check_page", "banned_words_in", "BANNED_WORDS"]

# ---------------------------------------------------------------------------
# Banned words
# ---------------------------------------------------------------------------

BANNED_WORDS = [
    "AI", "LLM", "model", "platform", "pipeline", "automated", "system",
    "agent", "algorithm",
]

_BANNED_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")\b",
    re.IGNORECASE,
)


def banned_words_in(page_html: str) -> list[str]:
    """Every banned word (lower-cased, deduped) found as a whole word in
    `page_html`, case-insensitive. Empty list means clean."""
    return sorted({m.group(0).lower() for m in _BANNED_RE.finditer(page_html)})


def e(value: Any) -> str:
    """html.escape, tolerant of None and non-strings."""
    return html.escape("" if value is None else str(value))


# ---------------------------------------------------------------------------
# Row ordering (PLAN.md / keith_copy.md "The ledger"):
# PASS, then NEAR MISS, then OUT ordered by first failed gate --
# seniority_ceiling, located_ie, chartered, then any other gate in the order
# it first appears -- then NOT CHECKED last.
# ---------------------------------------------------------------------------

_STATUS_ORDER = {"PASS": 0, "NEAR_MISS": 1, "OUT": 2, "NOT_CHECKED": 3}
_GATE_PRIORITY = {"seniority_ceiling": 0, "located_ie": 1, "chartered": 2}

STAMP_TEXT = {"PASS": "PASS", "NEAR_MISS": "NEAR MISS", "OUT": "OUT", "NOT_CHECKED": "NOT CHECKED"}
STAMP_CLASS = {"PASS": "pass", "NEAR_MISS": "near", "OUT": "out", "NOT_CHECKED": "notchecked"}

CONTACT_LABELS = {
    "verified": "email verified",
    "catch_all": "catch-all domain",
    "guess": "email was a guess",
    "none": "no email found",
    "unknown": "not looked up",
}


def _gate_rank(gate_id: str) -> int:
    return _GATE_PRIORITY.get(gate_id, 99)


def _out_rank(row: dict) -> int:
    failed = row.get("failed") or []
    ranks = [_gate_rank(f.get("gate_id", "")) for f in failed if isinstance(f, dict)]
    return min(ranks) if ranks else 99


def sort_rows(rows: list[dict]) -> list[dict]:
    """Stable sort into ledger order. Index is part of the key so ties
    (same status/gate) keep the caller's original order rather than
    depending on Python's dict comparison, which would raise."""
    def key(pair):
        idx, row = pair
        status = row.get("status", "NOT_CHECKED")
        status_rank = _STATUS_ORDER.get(status, 4)
        gate_rank = _out_rank(row) if status == "OUT" else 0
        return (status_rank, gate_rank, idx)

    indexed = sorted(enumerate(rows or []), key=key)
    return [row for _, row in indexed]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_date(iso: str | None) -> str:
    """"11 September 2026" from an ISO timestamp. Returns the RAW string --
    callers escape it with e() themselves; escaping here too double-escapes
    the ValueError fallback path. "%-d" (no leading zero) is a glibc
    extension strftime does not support on Windows, so the day number is
    built by hand instead."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return f"{dt.day} {dt.strftime('%B %Y')}"


def _num(x: float) -> str:
    """A whole number renders without a decimal point (15.0 -> "15");
    anything else keeps at most 2 decimals with no forced trailing zero
    (3.25 stays "3.25", 3.20 becomes "3.2")."""
    x = float(x)
    if x == int(x):
        return str(int(x))
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s


def _eur(x: float) -> str:
    """Euro amounts render as a rounded integer with a comma thousands
    separator: 1950 -> "1,950". Rounds HALF UP (int(x + 0.5) for the
    non-negative euro amounts this page ever shows) rather than Python's
    builtin round() (banker's/half-to-even) -- the JS side rounds with
    Math.round, which is always half-up, and the two must land on the same
    integer for the same input."""
    x = float(x)
    rounded = int(x + 0.5) if x >= 0 else -int(-x + 0.5)
    return f"{rounded:,}"


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


_SAFE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _render_evidence(evidence: list[dict] | None) -> str:
    parts = []
    for ev in evidence or []:
        quote = e(ev.get("quote"))
        raw_url = ev.get("source_url") or ""
        if _SAFE_URL_RE.match(raw_url):
            source_html = f'<a href="{e(raw_url)}" target="_blank" rel="noopener">source</a>'
        else:
            # Anything that is not http(s) -- javascript:, data:, a bare
            # string, an empty value -- is never turned into a clickable
            # link; it is printed as inert text so a malicious or malformed
            # source_url in the data can never become an href.
            source_html = f'<span class="src-plain">{e(raw_url)}</span>' if raw_url else ""
        parts.append(
            f'<div class="claim"><blockquote>&ldquo;{quote}&rdquo;</blockquote> '
            f'{source_html}</div>'
        )
    return "".join(parts)


def _render_ledger_row(row: dict, idx: int) -> str:
    status = row.get("status", "NOT_CHECKED")
    stamp_text = STAMP_TEXT.get(status, "NOT CHECKED")
    stamp_class = STAMP_CLASS.get(status, "notchecked")
    proof_id = f"proof-{idx}"
    name = e(row.get("name"))
    employer = e(row.get("employer"))
    one_line = e(row.get("one_line"))
    contact_label = CONTACT_LABELS.get(row.get("contact") or "unknown", CONTACT_LABELS["unknown"])
    evidence_html = _render_evidence(row.get("evidence"))
    if not evidence_html:
        evidence_html = '<p class="noproof">No proof lines on file.</p>'
    proof_body = (
        f'<div class="proof-in">{evidence_html}'
        f'<p class="contact-line">Contact: {e(contact_label)}.</p></div>'
    )
    main = (
        '<tr class="ledger-row">'
        f'<td class="c-name">{name}</td>'
        f'<td class="c-firm">{employer}</td>'
        f'<td class="c-stamp"><span class="stamp stamp-{stamp_class}">{stamp_text}</span></td>'
        f'<td class="c-line">{one_line}</td>'
        '<td class="c-proof">'
        f'<button class="proof-btn" type="button" aria-expanded="false" aria-controls="{proof_id}">Proof</button>'
        '</td>'
        '</tr>'
    )
    detail = f'<tr class="proof-row" id="{proof_id}" hidden><td colspan="5">{proof_body}</td></tr>'
    return main + detail


def _render_ledger(rows: list[dict]) -> str:
    body = "".join(_render_ledger_row(row, i) for i, row in enumerate(sort_rows(rows)))
    return (
        '<table class="ledger">'
        '<colgroup><col class="col-name"><col class="col-firm"><col class="col-stamp">'
        '<col class="col-line"><col class="col-proof"></colgroup>'
        '<thead><tr><th>Name</th><th>Firm</th><th>Stamp</th><th>The one line</th><th>Proof</th></tr></thead>'
        f'<tbody>{body}</tbody>'
        '</table>'
    )


def _render_rules(rules: list[dict] | None) -> str:
    items = [
        f'<li><strong>{e(r.get("label"))}</strong> &mdash; {e(r.get("rule_text"))}</li>'
        for r in (rules or [])
    ]
    return "".join(items)


def _render_brief_rules_block(briefs: list[dict] | None) -> str:
    """`check_results.json`'s `brief` is a LIST -- one entry per role_id
    actually applied to a matched row (coordinator fix 2026-09-11 item 1: a
    mixed-role submission is gated one brief per role, never a single
    brief forced onto everyone). A single-brief list (the common case, and
    every existing fixture/test) renders exactly as before -- one rules
    list, no extra heading. More than one brief gets its own heading per
    role so a reader can tell which rules applied to which names."""
    briefs = briefs or []
    if len(briefs) <= 1:
        rules = briefs[0].get("rules") if briefs else []
        return f'<ul class="rules-list">{_render_rules(rules)}</ul>'
    parts = []
    for b in briefs:
        parts.append(
            f'<p class="rules-role"><strong>{e(b.get("title"))}</strong></p>'
            f'<ul class="rules-list">{_render_rules(b.get("rules"))}</ul>'
        )
    return "".join(parts)


_GRADE_LABELS = {
    "senior_engineer": "Senior Engineer",
    "principal_engineer": "Principal Engineer",
    "associate": "Associate",
    "associate_director": "Associate Director",
    "director": "Director",
}


def _grade_label(raw: str | None) -> str | None:
    if not raw:
        return None
    return _GRADE_LABELS.get(raw, str(raw).replace("_", " ").title())


def _override_value(overrides: dict, key: str):
    """`brief[].overrides[key]` -- run.py (code-review fix 2026-09-11 item
    a) now stores `{"value": ..., "source": "cli"|"check_default"|
    "brief_default"}` per param so the page could show provenance later;
    this page only needs the value today, unwrapped here so a plain
    scalar (an older/fixture shape) still works too."""
    v = overrides.get(key)
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v


def _brief_role_summary(brief: dict) -> str:
    """One role's ceiling and residence rule, in plain words, built only
    from that role's own `overrides`/`rules` -- never a hardcoded grade or
    county (coordinator fix 2026-09-11 item 4)."""
    overrides = brief.get("overrides") or {}
    rules = brief.get("rules") or []
    parts = []
    grade = _grade_label(_override_value(overrides, "max_grade"))
    if grade:
        parts.append(f"no higher than {grade} grade")
    residence_rule = next((r for r in rules if r.get("gate_id") == "located_ie"), None)
    if residence_rule:
        counties = _override_value(overrides, "counties") or []
        where = ", ".join(str(c) for c in counties) if counties else "the Republic of Ireland"
        evidence = " with direct evidence" if _override_value(overrides, "require_direct_evidence") else ""
        parts.append(f"{where} residence{evidence}")
    chartered_rule = next((r for r in rules if r.get("gate_id") == "chartered"), None)
    if chartered_rule and chartered_rule.get("label"):
        parts.append(str(chartered_rule["label"]))
    return ", ".join(parts)


def _project_and_brief_lines(briefs: list[dict] | None) -> tuple[str, str]:
    """The title block's Project and Brief values, built from
    `results["brief"]` (a list, one entry per role) rather than a literal
    role name and rule summary -- a second role, a renamed role, or a
    changed ceiling/county all show up here with no code change."""
    briefs = briefs or []
    titles = [str(b.get("title") or "").strip() for b in briefs if b.get("title")]
    titles = [t for t in titles if t]
    if not titles:
        project = ""
    elif len(titles) == 1:
        project = titles[0]
    elif len(titles) == 2:
        project = f"{titles[0]} and {titles[1]}"
    else:
        project = ", ".join(titles[:-1]) + f", and {titles[-1]}"

    if not briefs:
        brief_line = ""
    elif len(briefs) == 1:
        brief_line = _brief_role_summary(briefs[0])
    else:
        brief_line = "; ".join(
            f"{b.get('title') or 'role'}: {_brief_role_summary(b)}" for b in briefs
        )
    return project, brief_line


def _render_residence_note(residence: dict | None) -> str:
    """Coordinator fix 2026-09-11 item 3: absence of a residence statement
    and evidence of one outside the Republic are different facts: this
    prints the split rather than folding both into one 'failed residence'
    count."""
    residence = residence or {}
    outside = residence.get("outside_republic", 0)
    absent = residence.get("no_evidence", 0)
    if not outside and not absent:
        return ""
    return (
        '<p class="footnote">Of the names that failed on residence: '
        f'{e(outside)} are evidenced living outside the Republic of Ireland; '
        f'{e(absent)} have no public statement of where they live at all.</p>'
    )


# ---------------------------------------------------------------------------
# Pool JSON for the "try a name" box -- guard against </script> in the data
# breaking out of the embedding script tag.
# ---------------------------------------------------------------------------


def _pool_json(pool: list[dict] | None) -> str:
    return json.dumps(pool or [], ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
:root{
  --ink:#16211C; --muted:#5C6B63; --line:#DFE5E0; --panel:#F6F8F6; --paper:#F7F8F6;
  --accent:#1D6F4F; --warn:#8A5A00; --warnbg:#FFF6E5; --stamp:#9B2C1F; --stampbg:#FBEFEC;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ink:#E8EDE9; --muted:#9AA79F; --line:#2A3630; --panel:#1A231E; --paper:#121815;
    --accent:#4FBF8E; --warn:#E0B46A; --warnbg:#26200f; --stamp:#E07A6B; --stampbg:#2b1815;
  }
}
:root[data-theme="dark"]{
  --ink:#E8EDE9; --muted:#9AA79F; --line:#2A3630; --panel:#1A231E; --paper:#121815;
  --accent:#4FBF8E; --warn:#E0B46A; --warnbg:#26200f; --stamp:#E07A6B; --stampbg:#2b1815;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font:400 16px/1.55 "IBM Plex Sans","Segoe UI",Helvetica,Arial,sans-serif;
  padding:0 20px; padding-block:28px 72px;
}
.wrap{max-width:1100px;margin:0 auto}
h1,h2{font-family:"IBM Plex Sans","Segoe UI",Helvetica,Arial,sans-serif;font-weight:700;letter-spacing:-.01em;color:var(--ink)}
.eyebrow{
  font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  font-weight:600;margin:0 0 8px;
}
h1{font-size:30px;margin:0 0 18px;border-bottom:3px solid var(--accent);padding-bottom:14px}
h2{font-size:20px;margin:38px 0 10px}
p{margin:0 0 12px;max-width:65ch}
.mono,.stamp,.tabular{font-family:"IBM Plex Mono","Consolas",monospace;font-variant-numeric:tabular-nums}

.titleblock{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px 24px;
  margin:0 0 26px;padding:16px 0 0;border-top:1px solid var(--line);
}
.titleblock div{min-width:0}
.titleblock dt{
  font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600;margin:0 0 3px;
}
.titleblock dd{margin:0;font-size:14.5px}

.verdict{font-size:22px;line-height:1.45;font-weight:600;max-width:44ch;margin:26px 0 6px}
.subline{color:var(--muted);font-size:14.5px;max-width:70ch}

.ledger-wrap{overflow-x:auto}
table.ledger{width:100%;border-collapse:collapse;margin:14px 0 8px;font-size:14px}
table.ledger th{
  text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  font-weight:600;padding:0 12px 7px;border-bottom:2px solid var(--accent);
}
table.ledger td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
table.ledger td.c-name{font-weight:600}
table.ledger td.c-firm{color:var(--muted)}
.stamp{
  display:inline-block;font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;
  padding:3px 8px;border-radius:4px;border:1px solid transparent;
}
.stamp-pass{color:#fff;background:var(--accent)}
.stamp-near{color:var(--warn);background:var(--warnbg);border-color:#e0b46a}
.stamp-out{color:#fff;background:var(--stamp)}
.stamp-notchecked{color:var(--muted);background:transparent;border:1px dashed var(--line)}

button.proof-btn{
  font:600 12.5px/1 "IBM Plex Sans",inherit;color:var(--accent);background:none;
  border:1px solid var(--line);border-radius:5px;padding:6px 10px;cursor:pointer;
}
button.proof-btn:hover,button.proof-btn:focus-visible{border-color:var(--accent);background:var(--panel)}
tr.proof-row>td{background:var(--panel);padding:14px 16px 16px}
.proof-in{font-size:13.5px;line-height:1.55;max-width:78ch}
.proof-in .claim{margin:0 0 8px;padding-left:11px;border-left:3px solid var(--line)}
.proof-in blockquote{margin:0;padding:0;border:0;display:inline;color:var(--ink)}
.proof-in a{color:var(--accent)}
.proof-in .contact-line{margin:8px 0 0;color:var(--muted)}
.proof-in .noproof{color:var(--muted);font-style:italic}

.rules-note{font-size:12.5px;font-weight:600;color:var(--muted);margin:16px 0 4px}
.rules-list{margin:0 0 8px;padding-left:18px;font-size:13.5px;color:var(--muted)}
.rules-list li{margin:0 0 4px}

.trybox{border:1px solid var(--line);border-radius:8px;padding:16px;background:var(--panel);margin:12px 0}
textarea#try-names{
  width:100%;min-height:96px;font:14px/1.5 "IBM Plex Mono",monospace;padding:10px;
  border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink);resize:vertical;
}
button#try-check{
  margin-top:10px;font:600 13.5px/1 "IBM Plex Sans",inherit;color:#fff;background:var(--accent);
  border:1px solid var(--accent);border-radius:6px;padding:9px 16px;cursor:pointer;
}
button#try-check:hover,button#try-check:focus-visible{background:#17583f}
#try-out{margin-top:14px}
#try-out table.ledger{margin:0}
.footnote{color:var(--muted);font-size:13px}

.arith-inputs{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:14px 0}
.arith-inputs label{display:block;font-size:12.5px;color:var(--muted);margin:0 0 5px}
.arith-inputs input{
  width:100%;font:600 16px/1 "IBM Plex Mono",monospace;padding:9px 10px;
  border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink);
}
.arith-outputs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:16px 0}
.arith-out{border-top:2px solid var(--accent);padding-top:8px}
.arith-out .num{font-size:26px;font-weight:700;display:block}
.arith-out .lbl{font-size:12.5px;color:var(--muted)}
.small-print{color:var(--muted);font-size:12.5px;max-width:70ch}

.fit-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:14px 0}
.fit-grid div{border:1px solid var(--line);border-radius:8px;padding:14px;font-size:14px}
.fit-grid .num{
  display:inline-block;font:700 12px "IBM Plex Mono",monospace;color:var(--accent);
  border:1px solid var(--accent);border-radius:50%;width:22px;height:22px;line-height:20px;
  text-align:center;margin:0 0 8px;
}

ul.plain{margin:8px 0;padding-left:18px}
ul.plain li{margin:0 0 8px}

footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}

@media (max-width:760px){
  table.ledger,table.ledger thead,table.ledger tbody,table.ledger tr,table.ledger td{display:block;width:100%}
  table.ledger tr.proof-row[hidden]{display:none}
  table.ledger thead{display:none}
  table.ledger td{border:0;padding:4px 0}
  tr.ledger-row{display:block;border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0}
  tr.proof-row>td{border:1px solid var(--line);border-top:0;border-radius:0 0 8px 8px;margin:-12px 0 12px}
}
@media (max-width:640px){
  .fit-grid{grid-template-columns:1fr}
  .titleblock{grid-template-columns:1fr}
}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
@media print{
  button.proof-btn{display:none}
  .trybox button#try-check{display:none}
  tr.proof-row{display:table-row!important}
  tr.proof-row[hidden]{display:table-row!important}
}
"""

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&'
    'family=IBM+Plex+Sans:wght@400;600;700&display=swap" rel="stylesheet">'
)

# ---------------------------------------------------------------------------
# JS -- proof-drawer toggle, the try-a-name box (name normalisation mirrors
# layers/intake.py::normalise_name exactly), and the live arithmetic.
# ---------------------------------------------------------------------------

_JS = r"""
(function(){
  "use strict";

  // -- proof drawer -------------------------------------------------------
  document.addEventListener("click", function(ev){
    var btn = ev.target.closest && ev.target.closest(".proof-btn");
    if (!btn) { return; }
    var row = document.getElementById(btn.getAttribute("aria-controls"));
    if (!row) { return; }
    var open = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", open ? "false" : "true");
    row.hidden = open;
  });

  // -- name normalisation, mirrors layers/intake.py::normalise_name -------
  var POST_NOMINALS = ["bsc","msc","beng","meng","ceng","miei","fiei","mistructe","mice","phd","pe"];
  function stripAccents(s){
    return s.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }
  // Coordinator fix 2026-09-11 item 6: a comma can introduce post-nominals
  // ("Kate FitzGerald, CEng MIEI" -> drop the tail) or a reversed name
  // ("Smith, John" -> the tail IS the given name, so folding it to a space
  // keeps "john" in the normalised string instead of losing it). The tail
  // is dropped only when EVERY token in it is a known post-nominal;
  // otherwise the comma becomes a space, same as a hyphen.
  function splitComma(s){
    var idx = s.indexOf(",");
    if (idx === -1) { return s; }
    var head = s.slice(0, idx);
    var tail = s.slice(idx + 1);
    var tailTokens = tail.toLowerCase().replace(/[^a-z ]+/g, " ").split(/\s+/).filter(Boolean);
    var allPostNominal = tailTokens.length > 0 && tailTokens.every(function(t){
      return POST_NOMINALS.indexOf(t) !== -1;
    });
    return allPostNominal ? head : head + " " + tail;
  }
  function normaliseName(s){
    if (!s) { return ""; }
    s = String(s).replace(/’|‘/g, "'");
    s = s.replace(/\([^)]*\)/g, " ");
    s = splitComma(s);
    s = s.replace(/-/g, " ");
    s = stripAccents(s).toLowerCase();
    s = s.replace(/'/g, "");
    s = s.replace(/[^a-z0-9 ]+/g, " ");
    var tokens = s.split(/\s+/).filter(function(t){
      return t && POST_NOMINALS.indexOf(t) === -1;
    });
    return tokens.join(" ");
  }

  var STAMP_TEXT = {PASS:"PASS", NEAR_MISS:"NEAR MISS", OUT:"OUT", NOT_CHECKED:"NOT CHECKED"};
  var STAMP_CLASS = {PASS:"pass", NEAR_MISS:"near", OUT:"out", NOT_CHECKED:"notchecked"};
  var NOT_CHECKED_LINE = "Not checked yet. A new name takes one working day and comes back with the same proof lines.";

  function poolOneLine(entry){
    var labels = entry.failed_labels || [];
    if (entry.status === "PASS") { return "Meets every rule."; }
    if (entry.status === "NEAR_MISS") { return "Misses one rule: " + labels.join(", ") + "."; }
    if (entry.status === "OUT") { return "Fails: " + labels.join(", ") + "."; }
    return NOT_CHECKED_LINE;
  }

  function escapeHtml(s){
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function buildIndex(pool){
    var idx = {};
    (pool || []).forEach(function(entry){
      var key = normaliseName(entry.name);
      if (key) { idx[key] = entry; }
    });
    return idx;
  }

  function renderTryResults(names, pool){
    var idx = buildIndex(pool);
    var rows = names.map(function(raw){
      raw = raw.trim();
      if (!raw) { return null; }
      var key = normaliseName(raw);
      var entry = idx[key];
      var status = entry ? entry.status : "NOT_CHECKED";
      var line = entry ? poolOneLine(entry) : NOT_CHECKED_LINE;
      var firm = entry ? entry.employer : "";
      var stampText = STAMP_TEXT[status] || "NOT CHECKED";
      var stampClass = STAMP_CLASS[status] || "notchecked";
      return (
        '<tr class="ledger-row">' +
        '<td class="c-name">' + escapeHtml(raw) + '</td>' +
        '<td class="c-firm">' + escapeHtml(firm) + '</td>' +
        '<td class="c-stamp"><span class="stamp stamp-' + stampClass + '">' + stampText + '</span></td>' +
        '<td class="c-line">' + escapeHtml(line) + '</td>' +
        '<td class="c-proof"></td>' +
        '</tr>'
      );
    }).filter(Boolean);
    var out = document.getElementById("try-out");
    if (!out) { return; }
    if (!rows.length) { out.innerHTML = ""; return; }
    out.innerHTML =
      '<table class="ledger"><thead><tr><th>Name</th><th>Firm</th><th>Stamp</th>' +
      '<th>The one line</th><th>Proof</th></tr></thead><tbody>' + rows.join("") + '</tbody></table>';
  }

  var poolTag = document.getElementById("pool-data");
  var pool = [];
  try { pool = poolTag ? JSON.parse(poolTag.textContent) : []; } catch (err) { pool = []; }

  var checkBtn = document.getElementById("try-check");
  if (checkBtn) {
    checkBtn.addEventListener("click", function(){
      var ta = document.getElementById("try-names");
      var names = ta ? ta.value.split(/\r?\n/) : [];
      renderTryResults(names, pool);
    });
  }

  // -- arithmetic, formulas match eval/time_value.py -----------------------
  var minutesEl = document.getElementById("tv-minutes");
  var namesEl = document.getElementById("tv-names");
  var rateEl = document.getElementById("tv-rate");
  var emailsEl = document.getElementById("tv-emails");
  var hoursOut = document.getElementById("tv-hours-week");
  var monthOut = document.getElementById("tv-eur-month");
  var augOut = document.getElementById("tv-aug-hours");
  var emailsOut = document.getElementById("tv-aug-emails");

  var augustNames = augOut ? parseFloat(augOut.getAttribute("data-august-names")) || 0 : 0;

  function num(el, fallback){
    var v = el ? parseFloat(el.value) : NaN;
    return isNaN(v) ? fallback : v;
  }

  // A whole number shows without a decimal point; anything else keeps at
  // most 2 decimals with no forced trailing zero -- mirrors _num() in
  // render/check_page.py.
  function formatNum(x){
    if (Math.round(x) === x) { return String(Math.round(x)); }
    var s = x.toFixed(2);
    s = s.replace(/0+$/, "").replace(/\.$/, "");
    return s;
  }

  // Euro amounts always show as a rounded integer with a thousands
  // separator -- mirrors _eur() in render/check_page.py EXACTLY, including
  // rounding mode: Math.round (JS) and int(x + 0.5) (Python's _eur) are
  // both round-half-up, unlike Python's builtin round() (round-half-to-
  // even/banker's), so the two languages land on the same integer for
  // every input, not just most of them.
  function formatEur(x){
    return Math.round(x).toLocaleString("en-US");
  }

  // 2-decimal round-half-up, applied at each step eval/time_value.py
  // applies it at (hours_for, then weekly's eur_per_week, then its
  // eur_per_month) -- the ORDER matters: hours must be rounded to 2dp
  // BEFORE being multiplied by the rate, not after, or a rate that isn't a
  // round number can drift a cent or more from the server-rendered value.
  function round2(x){
    return Math.round(x * 100) / 100;
  }

  function recompute(){
    var minutes = num(minutesEl, 15);
    var names = num(namesEl, 40);
    var rate = num(rateEl, 45);
    var emails = num(emailsEl, 4);
    var hoursPerWeek = round2(names * minutes / 60);
    var eurPerWeek = round2(hoursPerWeek * rate);
    var eurPerMonth = round2(eurPerWeek * 52 / 12);
    var augHours = round2(augustNames * minutes / 60);
    if (hoursOut) { hoursOut.textContent = formatNum(hoursPerWeek); }
    if (monthOut) { monthOut.textContent = formatEur(eurPerMonth); }
    if (augOut) { augOut.textContent = formatNum(augHours); }
    if (emailsOut) { emailsOut.textContent = formatNum(emails); }
  }

  [minutesEl, namesEl, rateEl, emailsEl].forEach(function(el){
    if (el) { el.addEventListener("input", recompute); }
  });
  recompute();

  // Test-only hook: exposes the pure functions above to the offline node
  // harness in tests/test_check_page.py so the arithmetic-rounding and
  // name-normalisation rules can be asserted against a real JS engine
  // rather than by inspecting this source as text. globalThis.
  // __CHECK_PAGE_TEST_HOOKS__ is never defined outside that harness, so
  // this is a no-op in every real render of the page.
  if (typeof globalThis !== "undefined" && globalThis.__CHECK_PAGE_TEST_HOOKS__) {
    globalThis.__CHECK_PAGE_TEST_HOOKS__({
      normaliseName: normaliseName,
      splitComma: splitComma,
      formatNum: formatNum,
      formatEur: formatEur,
      round2: round2
    });
  }
})();
"""


# ---------------------------------------------------------------------------
# Full page assembly
# ---------------------------------------------------------------------------


def _build(results: dict) -> str:
    summary = results.get("summary") or {}
    brief = results.get("brief") or []
    time_value = results.get("time_value") or {}
    assumptions = time_value.get("assumptions") or {}
    weekly = time_value.get("weekly") or {}
    august = time_value.get("august_list") or {}
    rows = results.get("rows") or []
    pool = results.get("pool") or []

    submitted = summary.get("submitted", 0)
    n_pass = summary.get("pass", 0)
    n_out = summary.get("out", 0)
    n_near = summary.get("near_miss", 0)
    checked_date = _format_date(results.get("generated_at"))
    campaign = e(results.get("campaign"))
    minutes = assumptions.get("minutes_per_manual_check", 15)
    names_wk = assumptions.get("names_per_week", 40)
    rate = assumptions.get("hourly_cost_eur", 45.0)
    hours_wk = weekly.get("hours_per_week", 0)
    eur_month = weekly.get("eur_per_month", 0)
    aug_hours = august.get("consultant_hours_spent", 0)
    aug_emails = august.get("emails_to_unplaceable", 0)
    aug_names = august.get("calls_that_would_have_been_wrong", submitted)
    # Coordinator fix 2026-09-11 item 7: the calculator's "messages sent"
    # default is Keith's own stated count when the JSON carries one
    # (time_value.assumptions.emails_written), falling back to the fixed
    # august_list count derived at check time.
    emails_default = assumptions.get("emails_written", aug_emails)

    project_line, brief_line = _project_and_brief_lines(brief)

    title_block = (
        '<dl class="titleblock">'
        f'<div><dt>Project</dt><dd>{e(project_line)}</dd></div>'
        f'<div><dt>Brief</dt><dd>{e(brief_line)}</dd></div>'
        f'<div><dt>Names in</dt><dd>{e(submitted)}</dd></div>'
        f'<div><dt>Checked on</dt><dd>{e(checked_date)}</dd></div>'
        '<div><dt>Checked against</dt><dd>the brief as agreed on 10 September</dd></div>'
        '</dl>'
    )

    verdict = (
        f'<p class="verdict">{e(submitted)} names went in. {e(n_pass)} pass the brief. '
        f'{e(n_out)} are out and {e(n_near)} miss by one rule. Every name below says which rule '
        'it failed, in one line, with the proof underneath.</p>'
        '<p class="subline">You said this list was too senior and that some were not in Ireland. '
        'You were right on both. This is the list you were sent on 20 August. The check was run '
        f'again on {e(checked_date)} against the brief you set on the call. Nothing here was '
        'typed by hand; every line is a quote from a public page, checked character by character '
        'against that page.</p>'
    )

    ledger_section = (
        '<h2>The ledger</h2>'
        f'<div class="ledger-wrap">{_render_ledger(rows)}</div>'
        f'{_render_residence_note(summary.get("residence"))}'
        '<p class="rules-note">Rules applied, in plain words:</p>'
        f'{_render_brief_rules_block(brief)}'
    )

    try_section = (
        '<h2>Try any name from your own lists.</h2>'
        '<div class="trybox">'
        '<textarea id="try-names" placeholder="Type or paste names, one per line"></textarea>'
        '<button id="try-check" type="button">Check</button>'
        '<div id="try-out"></div>'
        '</div>'
        f'<p class="footnote">{e(len(pool))} engineers are already checked for this brief. '
        'The box looks them up by name; it does not search the internet.</p>'
        f'<script type="application/json" id="pool-data">{_pool_json(pool)}</script>'
    )

    arithmetic_section = (
        '<h2>What a wrong list costs</h2>'
        '<p>Checking one name by hand means opening the profile, the firm&rsquo;s page and the '
        'Engineers Ireland register, confirming where the person lives, and finding an address '
        'that is not a guess. Set your own minutes below; the figures update.</p>'
        '<div class="arith-inputs">'
        '<div><label for="tv-minutes">Minutes per name checked by hand</label>'
        f'<input id="tv-minutes" type="number" min="0" step="1" value="{_num(minutes)}"></div>'
        '<div><label for="tv-names">Names your team checks in a week</label>'
        f'<input id="tv-names" type="number" min="0" step="1" value="{_num(names_wk)}"></div>'
        '<div><label for="tv-rate">Cost of a consultant hour, &euro;</label>'
        f'<input id="tv-rate" type="number" min="0" step="1" value="{_num(rate)}"></div>'
        '<div><label for="tv-emails">Messages your team sent to this list</label>'
        f'<input id="tv-emails" type="number" min="0" step="1" value="{_num(emails_default)}"></div>'
        '</div>'
        '<div class="arith-outputs">'
        '<div class="arith-out"><span class="num tabular" id="tv-hours-week">'
        f'{_num(hours_wk)}</span><span class="lbl">Hours a week spent checking</span></div>'
        '<div class="arith-out"><span class="num tabular">&euro;<span id="tv-eur-month">'
        f'{_eur(eur_month)}</span></span><span class="lbl">Per month</span></div>'
        '<div class="arith-out"><span class="num tabular" id="tv-aug-hours" '
        f'data-august-names="{e(aug_names)}">{_num(aug_hours)}</span>'
        f'<span class="lbl">consultant hours on the 20 August list alone &mdash; a list where '
        f'{e(n_pass)} of {e(submitted)} qualified, and <span id="tv-aug-emails">'
        f'{_num(emails_default)}</span> emails were written to people the brief could never '
        'place</span></div>'
        '</div>'
        '<p class="small-print">You said Isadora and you could take on 50 to 100 jobs with '
        'Maddie&rsquo;s screener doing the first pass. The messages figure is from your own note '
        'that you contacted a handful; set the real number. The names per week above is where '
        'that ambition meets a consultant&rsquo;s hours; set it to your number. The 15 minutes is '
        'my estimate. Replace it with yours and the page recomputes. The cost of a wrong CV '
        'reaching TOBIN or AtkinsR&eacute;alis is not on this page; you know that number better '
        'than I '
        'do.</p>'
    )

    fits_section = (
        '<h2>How it fits with what you have</h2>'
        '<div class="fit-grid">'
        '<div><span class="num">1</span><p>Recruit CRM and LinkedIn Recruiter find names. '
        'They keep doing that.</p></div>'
        '<div><span class="num">2</span><p>Shortlist Check proves the names before anyone calls: '
        'chartered, resident, right grade, real contact, with the quote. Names that fail come '
        'back with the reason, so nobody spends an hour on them.</p></div>'
        '<div><span class="num">3</span><p>Maddie&rsquo;s screener takes over exactly where it '
        'does today. A checked name lands in Recruit CRM as a candidate on the job, with the '
        'proof as a note, and can show in the dashboard Maddie built as one more column beside '
        'her score: checked, with the proof. Nothing sends on its own; a consultant always makes '
        'the call.</p></div>'
        '</div>'
    )

    not_section = (
        '<h2>What it is not</h2>'
        '<ul class="plain">'
        '<li>Not a database. It checks names you already have.</li>'
        '<li>Not a replacement for Recruit CRM, LinkedIn Recruiter or what Maddie built.</li>'
        '<li>Not something that contacts candidates. Your consultants do, from their own '
        'seats.</li>'
        '<li>Not a score. A name passes the brief or it does not, and the page says why.</li>'
        '<li>Not another thing to learn. One list in, one page back. Isadora can run it without '
        'you.</li>'
        '</ul>'
    )

    why_section = (
        '<h2>Why this cannot come from the tools you already pay for</h2>'
        '<p>You read me their upgrade note on Thursday: job change alerts, backdoor hire '
        'detection, sourcing across 800 million profiles with a 0 to 100 match score, cheaper '
        'enrichment. Keep all of it; none of it is touched here. The difference is one line: a '
        'score says how similar a person looks to the job. A check says whether they meet the '
        f'brief, and shows why. Read from Recruit CRM&rsquo;s own pages on {e(checked_date)}:</p>'
        '<ul class="plain">'
        '<li>Their sourcing returns profiles with no quote and no source link, so a consultant '
        'still has to check each one.</li>'
        '<li>Their matching is a single 0 to 100 score. A rule like &ldquo;must be '
        'chartered&rdquo; or &ldquo;must live in the Republic&rdquo; lowers a score; it does not '
        'remove the name.</li>'
        '<li>No credential check exists in the product. Their own blog treats it as something '
        'you buy elsewhere.</li>'
        '<li>Their sequences send and pause; they do not read the reply, and &ldquo;not '
        'now&rdquo; is not remembered for 90 days.</li>'
        '<li>&ldquo;Verified emails&rdquo; is claimed with no method stated. Here every address '
        'carries its label: verified, catch-all, guess, or none.</li>'
        '</ul>'
        '<p>And why from me: this is built around Gaia&rsquo;s brief and Irish public records '
        '(planning oral hearings, Engineers Ireland post-nominals, the firms&rsquo; own people '
        'pages), with one rule that no product sells: no quote, no claim. You own every output. '
        'There is no per-seat fee. And you have already seen the wrong version of this list and '
        'the corrected one, with the count told straight both times.</p>'
    )

    footer = (
        '<footer><p>Prepared for Keith Molony, Gaia Talent Ltd, by Debanjan Mazumdar, Prodcraft, '
        f'{e(checked_date)}. Campaign {campaign}. Public sources only; every candidate receives '
        'the Article 14 notice with the source cited.</p></footer>'
    )

    body = (
        '<div class="wrap">'
        '<p class="eyebrow">Gaia Talent Ltd &middot; prepared by Prodcraft</p>'
        '<h1>Your 20 August list, checked.</h1>'
        f'{title_block}{verdict}{ledger_section}{try_section}{arithmetic_section}'
        f'{fits_section}{not_section}{why_section}{footer}'
        '</div>'
    )

    return (
        '<title>Shortlist Check</title>'
        f'{_FONTS_LINK}'
        f'<style>{_CSS}</style>'
        f'{body}'
        f'<script>{_JS}</script>'
    )


def render_check_page(results: dict) -> str:
    """Render `results` (the check_results.json contract) into one
    self-contained HTML string. Checks that the module's own static copy
    stays free of the banned words (see the module docstring) -- a caller's
    data (a firm name, a brief title, a campaign id, say) is never checked,
    only the copy this module wrote, so every field this render pulls text
    from is blanked out before that check runs."""
    page = _build(results)

    static_only = dict(results)
    static_only["rows"] = []
    static_only["pool"] = []
    static_only["brief"] = []
    static_only["summary"] = {}
    static_only["campaign"] = ""
    static_only["input"] = {}
    bad = banned_words_in(_build(static_only))
    if bad:
        raise ValueError(f"banned word(s) found in static copy: {bad}")

    return page


def write_check_page(results_path: str | Path, out_path: str | Path) -> Path:
    """Read `results_path` (check_results.json) and write the rendered page
    to `out_path`. Returns `out_path` as a Path."""
    results_path = Path(results_path)
    out_path = Path(out_path)
    results = json.loads(results_path.read_text(encoding="utf-8"))
    page = render_check_page(results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
