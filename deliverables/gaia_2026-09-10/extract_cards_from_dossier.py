"""
description: Parse the Gaia sourcing dossier HTML (a rendered CandidateCard
  table -- see execution/gtm_client_workflows/gaia_sourcing/render/render.py)
  into structured JSON, plus derive seniority_grade / years_experience /
  location_country / location_evidence with documented deterministic rules.
inputs: $S/live.html (positional arg 1, default "live.html" next to this
  script); deliverables/gaia_2026-08-20/pool_map_role1.md and
  pool_map_role2.md (read-only, for pool_map.json).
outputs: $S/candidates.json, $S/pool_map.json (written next to this script
  unless overridden); a summary table printed to stdout.

CAVEATS (see also the printed caveats block at the end of a run):
  - The live table render (row_html / _detail_cell in render.py) does not
    reproduce the full CandidateCard model 1:1. Several contract fields are
    not present in the HTML at all and are reconstructed/approximated here:
      * gates: individual GateResult objects are never rendered. Because
        only candidates who passed every hard gate ever reach the page,
        each delivered candidate is given one synthetic GateResult per known
        gate_id (chartered, located_ie, discipline, seniority_years,
        not_client) with passed=True and an explanatory note -- this is NOT
        sourced from the pipeline's real evaluation.gates list.
      * claims: the "why" column shows reviewer strengths (not 1:1 with a
        quote), and the detail pane shows verbatim quotes without their
        paired `assertion`/`dimension`. Each blockquote becomes one claim
        with assertion == evidence_quote (best available), and `dimension`
        is guessed with a keyword heuristic (classify_claim_dimension) --
        "unclassified" when no keyword matches. Inferred (non-quote) facts
        become separate claims: confidence="inferred", evidence_quote=None.
      * movability_signals: the render only ever shows one rationale
        sentence, never a discrete signals list -- movability_signals is
        therefore always [] here; the sentence is on movability_rationale.
      * tenure_months_current: never rendered in the table view -> None.
      * location: not shown per-candidate (only a role-level list of target
        counties in the section lede). Reconstructed by scanning the
        candidate's own text (title/employer/why/quotes/facts) for a place
        name; falls back to "Unknown".
      * text_source: "ocr" only when render.py's OCR-provenance string sits
        next to that quote's source link; else "text_layer".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

SCRIPT_DIR = Path(__file__).resolve().parent
DELIVERABLES = Path(
    "/home/user/deb-antigravity-claude-workspace/deliverables/gaia_2026-08-20"
)

GATE_IDS = ["chartered", "located_ie", "discipline", "seniority_years", "not_client"]

EMAIL_STATUS_RULES = [
    (re.compile(r"SMTP-verified", re.I), "verified"),
    (re.compile(r"accepts all mail", re.I), "catch_all"),
    (re.compile(r"naming pattern", re.I), "pattern_guess"),
    (re.compile(r"No email address found", re.I), "none"),
]

# --------------------------------------------------------------------------
# Derived-field rules (kept as standalone functions so they're reusable /
# testable independent of the HTML parsing above them).
# --------------------------------------------------------------------------


def classify_seniority(title: str) -> str:
    """Keyword rule -> one of the seniority_grade enum values.

    Checked most-specific-first so "Associate Director" doesn't fall into
    the generic "Associate" bucket, and "Director" doesn't shadow it either.
    """
    t = (title or "").lower()
    if "graduate" in t:
        return "graduate"
    if "associate director" in t:
        return "associate_director"
    if any(k in t for k in ("director", "managing", "partner", "head of")):
        return "director_or_above"
    if any(k in t for k in ("principal", "associate")):
        return "principal_or_associate"
    if "chartered engineer" in t or "senior" in t:
        return "senior_engineer"
    if "engineer" in t:
        return "engineer"
    return "unknown"


YEARS_RE = re.compile(r"(?:over\s+)?(\d{1,3})\+?\s*years", re.I)


def extract_years_experience(text_blobs: list[str]) -> int | None:
    """First "N years" figure found across the candidate's claim text."""
    for blob in text_blobs:
        m = YEARS_RE.search(blob or "")
        if m:
            return int(m.group(1))
    return None


IE_PLACES = [
    "Dublin", "Cork", "Limerick", "Galway", "Waterford", "Kildare", "Meath",
    "Wicklow", "Louth", "Kilkenny", "Clare", "Tipperary", "Kerry", "Mayo",
    "Sligo", "Donegal", "Wexford", "Laois", "Offaly", "Westmeath",
    "Longford", "Roscommon", "Leitrim", "Cavan", "Monaghan", "Carlow",
    "Ireland",
]
NI_PLACES = ["Belfast", "Northern Ireland", "Derry", "Antrim", "Armagh", "Down",
             "Tyrone", "Fermanagh"]
UK_PLACES = ["London", "Manchester", "Birmingham", "Glasgow", "Edinburgh",
             "Cardiff", "Bristol", "Leeds", "England", "Scotland", "Wales",
             "United Kingdom", "UK"]

_PLACE_TO_COUNTRY = (
    [(p, "NI") for p in NI_PLACES]      # NI checked before IE/UK so
    + [(p, "UK") for p in UK_PLACES]    # "Northern Ireland" etc. win first
    + [(p, "IE") for p in IE_PLACES]
)


def _place_pattern(place: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(place) + r"\b", re.I)


def find_location(text_blobs: list[str]) -> tuple[str, str]:
    """Return (location, evidence_snippet). "Unknown" if nothing matches.

    Scans NI place names first, then UK, then IE (longest/most specific
    names like "Northern Ireland" are listed before generic ones like "UK"
    within their own tier via _PLACE_TO_COUNTRY's construction order).
    """
    for blob in text_blobs:
        if not blob:
            continue
        for place, _country in _PLACE_TO_COUNTRY:
            m = _place_pattern(place).search(blob)
            if m:
                start = max(0, m.start() - 40)
                end = min(len(blob), m.end() + 40)
                snippet = blob[start:end].strip()
                return place, snippet
    return "Unknown", ""


def location_country_from_text(location: str, text_blobs: list[str]) -> tuple[str, str]:
    """IE / NI / UK / unknown, per the task's county+city keyword lists."""
    blobs = [location] + list(text_blobs)
    for blob in blobs:
        if not blob:
            continue
        for place, country in _PLACE_TO_COUNTRY:
            m = _place_pattern(place).search(blob)
            if m:
                start = max(0, m.start() - 40)
                end = min(len(blob), m.end() + 40)
                return country, blob[start:end].strip()
    return "unknown", ""


CLAIM_DIMENSION_RULES = [
    ("chartership", re.compile(
        r"charter|CEng|MIStructE|MIEI|RConsEI|professional body|Fellow member", re.I)),
    ("years_experience", re.compile(r"\byears\b", re.I)),
    ("statutory_process", re.compile(
        r"An Bord Pleanála|Railway Order|Oral Hearing|statutory|inspector report|witness statement", re.I)),
    ("technical_skill", re.compile(
        r"design|assessment|engineering|structural|transport|infrastructure|project", re.I)),
    ("employer", re.compile(r"director|associate|consulting|engineers|ltd|limited", re.I)),
    ("education", re.compile(r"\bBE\b|\bBEng\b|\bMEng\b|degree|graduate", re.I)),
    ("location", re.compile(r"|".join(re.escape(p) for p in IE_PLACES + NI_PLACES + UK_PLACES), re.I)),
]


def classify_claim_dimension(text: str) -> str:
    for dimension, pattern in CLAIM_DIMENSION_RULES:
        if pattern.search(text or ""):
            return dimension
    return "unclassified"


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------


def text_of(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def parse_role_tables(soup: BeautifulSoup):
    """Yield (role_id, role_title, table_tag) for each role band, in order.

    The <section class="role-band"> only holds the header; the following
    sibling <table class="sl"> holds that role's rows. Walk the wrap div's
    children in document order to pair them correctly rather than assuming
    a fixed count.
    """
    wrap = soup.select_one("div.wrap")
    current_role_id = None
    current_role_title = None
    for child in wrap.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "section" and "role-band" in (child.get("class") or []):
            current_role_id = child.get("id")
            h2 = child.find("h2")
            # h2 text includes the trailing "<span class='of'>10 of 10</span>"
            # counter; strip it back out so role_title is just the title.
            span = h2.find("span") if h2 else None
            span_text = text_of(span)
            full = text_of(h2)
            current_role_title = full[: len(full) - len(span_text)].strip() if span_text else full
        elif child.name == "table" and "sl" in (child.get("class") or []):
            yield current_role_id, current_role_title, child


def parse_claims(det_in: Tag) -> list[dict]:
    claims = []
    for claim_div in det_in.select("div.claim"):
        bq = claim_div.find("blockquote")
        quote = text_of(bq)
        src_div = claim_div.find("div", class_="src")
        source_url = None
        link = src_div.find("a") if src_div else None
        if link and link.get("href"):
            source_url = link["href"]
        src_text = text_of(src_div)
        text_source = "ocr" if "OCR" in src_text or "scanned document" in src_text.lower() else "text_layer"
        dimension = classify_claim_dimension(quote)
        claims.append({
            "dimension": dimension,
            "assertion": quote,  # not separately rendered in this view; see module caveat
            "evidence_quote": quote,
            "source_url": source_url,
            "text_source": text_source,
            "confidence": "direct",
        })

    # "Inferred, not directly stated: a; b; c" -- render.py _detail_cell block 2.
    facts_div = det_in.select_one("div.facts")
    if facts_div:
        for p in facts_div.find_all("p", class_="src"):
            t = text_of(p)
            if t.startswith("Inferred, not directly stated:"):
                body = t.split(":", 1)[1].strip()
                for piece in re.split(r";\s*", body):
                    piece = piece.strip().rstrip(".")
                    if not piece:
                        continue
                    claims.append({
                        "dimension": classify_claim_dimension(piece),
                        "assertion": piece,
                        "evidence_quote": None,
                        "source_url": None,
                        "text_source": "text_layer",
                        "confidence": "inferred",
                    })
    return claims


def parse_email(det_in: Tag, row_td) -> tuple[str | None, str]:
    email = None
    cta_em = row_td.select_one("a.cta-em")
    if cta_em:
        email = cta_em.get("data-email") or (
            cta_em["href"][7:] if cta_em.get("href", "").lower().startswith("mailto:") else None
        )
    status = "none"
    facts_div = det_in.select_one("div.facts")
    if facts_div:
        for p in facts_div.find_all("p", class_="src"):
            t = text_of(p)
            for pattern, s in EMAIL_STATUS_RULES:
                if pattern.search(t):
                    status = s
                    break
    elif email:
        status = "pattern_guess" if (cta_em and "weak" in (cta_em.get("class") or [])) else "verified"
    return email, status


def parse_movability(det_in: Tag) -> tuple[str, str]:
    facts_div = det_in.select_one("div.facts")
    if not facts_div:
        return "unknown", ""
    strong = facts_div.find("strong", class_=lambda c: c and c.startswith("mov-"))
    if not strong:
        return "unknown", ""
    assessment = strong["class"][0].replace("mov-", "")
    parent_p = strong.find_parent("p")
    full = text_of(parent_p)
    strong_text = text_of(strong)
    rationale = full[len(strong_text):].strip()
    return assessment, rationale


def parse_recommended_channel(row_td) -> str:
    """Heuristic: the first non-"weak" (i.e. real, not a fallback search
    link) button in the candidate's button stack, in the order render.py
    emits them (LinkedIn, then email, then switchboard/profile fallback).
    Not directly rendered as a labelled field in the table view.
    """
    btns = row_td.select("div.btns > a.cta")
    for b in btns:
        classes = b.get("class") or []
        if "weak" in classes:
            continue
        if "cta-li" in classes:
            return "linkedin"
        if "cta-em" in classes:
            return "personal_email"
    for b in btns:
        classes = b.get("class") or []
        if "cta-alt" in classes:
            return "phone"
    if btns:
        classes = btns[0].get("class") or []
        if "cta-li" in classes:
            return "linkedin"
        if "cta-em" in classes:
            return "personal_email"
    return "linkedin"


def parse_card(role_id: str, role_title: str, row: Tag, det: Tag) -> dict:
    who_td = row.find("td")
    name = text_of(who_td.find("p", class_="nm"))
    ro_text = text_of(who_td.find("p", class_="ro"))
    if " · " in ro_text:
        title, employer = ro_text.split(" · ", 1)
    else:
        title, employer = ro_text, ""
    if title == "Title not stated":
        title = ""

    tier_span = row.select_one("span.tier")
    tier = text_of(tier_span).replace("Tier", "").strip() or "?"

    person_id = det["id"]
    prefix = f"d-{role_id}-"
    if person_id.startswith(prefix):
        person_id = person_id[len(prefix):]

    why_lis = [text_of(li) for li in row.select("td ul.why li")]
    strengths = why_lis

    li_a = who_td.select_one("a.cta-li")
    linkedin_url = None
    if li_a and "weak" not in (li_a.get("class") or []):
        linkedin_url = li_a.get("href")

    det_in = det.select_one("div.det-in")
    claims = parse_claims(det_in) if det_in else []
    email, email_status = parse_email(det_in, who_td) if det_in else (None, "none")
    movability_assessment, movability_rationale = parse_movability(det_in) if det_in else ("unknown", "")
    recommended_first_channel = parse_recommended_channel(who_td)

    tds = row.find_all("td")
    outreach = None
    if len(tds) >= 3:
        msg_td = tds[2]
        buttons = msg_td.select("button.cp")
        labels = [text_of(lbl) for lbl in msg_td.select("p.msg-k span.lbl")]
        li_note = buttons[0].get("data-copy") if len(buttons) >= 1 else None
        email_body = buttons[1].get("data-copy") if len(buttons) >= 2 else None
        email_subject = None
        for lbl in labels:
            if lbl.startswith("Email"):
                # label is "Email — <subject>" (em dash); strip the prefix.
                email_subject = re.sub(r"^Email\s*[—\-–]\s*", "", lbl).strip()
        if li_note or email_body:
            outreach = {
                "linkedin_note": li_note,
                "email_subject": email_subject,
                "email_body": email_body,
            }

    gap_span = who_td.select_one("span.none")
    if gap_span:
        pass  # "No email address found" -- already reflected via email_status/email=None

    # ---- text pool for the derived fields ----
    quote_texts = [c["evidence_quote"] for c in claims if c.get("evidence_quote")]
    assertion_texts = [c["assertion"] for c in claims if c.get("assertion")]
    text_blobs = [title, employer, *why_lis, *quote_texts, *assertion_texts, movability_rationale]

    location, location_snip = find_location(text_blobs)
    location_country, location_country_snip = location_country_from_text(location, text_blobs)
    location_evidence = location_country_snip or location_snip
    years_experience = extract_years_experience([*quote_texts, *assertion_texts, *why_lis])
    seniority_grade = classify_seniority(title)

    gates = [
        {
            "gate_id": gid,
            "passed": True,
            "note": (
                "Not individually rendered in the HTML; inferred True because only "
                "candidates who passed every hard gate for this role are ever shown."
            ),
        }
        for gid in GATE_IDS
    ]

    return {
        "person_id": person_id,
        "full_name": name,
        "current_title": title,
        "current_employer": employer,
        "location": location,
        "role_id": role_id,
        "role_title": role_title,
        "tier": tier,
        "gates": gates,
        "claims": claims,
        "strengths": strengths,
        "unknowns": [],
        "adversarial_findings": [],
        "email_status": email_status,
        "email": email,
        "linkedin_url": linkedin_url,
        "movability_assessment": movability_assessment,
        "movability_rationale": movability_rationale,
        "movability_signals": [],
        "tenure_months_current": None,
        "recommended_first_channel": recommended_first_channel,
        "outreach": outreach,
        # derived fields
        "seniority_grade": seniority_grade,
        "seniority_grade_rule": "classify_seniority(current_title) keyword rule; see docstring",
        "years_experience": years_experience,
        "years_experience_rule": r'regex (?:over\s+)?(\d{1,3})\+?\s*years over claim quotes/assertions/why-bullets, first match',
        "location_country": location_country,
        "location_evidence": location_evidence,
    }


def extract(html_path: Path) -> list[dict]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    cards = []
    for role_id, role_title, table in parse_role_tables(soup):
        rows = table.select("tr.r")
        for row in rows:
            det = row.find_next_sibling("tr")
            if det is None or "det" not in (det.get("class") or []):
                continue
            cards.append(parse_card(role_id, role_title, row, det))
    return cards


# --------------------------------------------------------------------------
# pool_map.json, from the two markdown files under deliverables/ (read-only)
# --------------------------------------------------------------------------


def _parse_md_table(md: str, heading: str) -> list[tuple[str, str]]:
    """Return [(col1, col2), ...] rows of the first '| ... |' table after
    a '## heading' (or from the top of the doc if heading is None)."""
    lines = md.splitlines()
    start = 0
    if heading:
        for i, line in enumerate(lines):
            if line.strip().lstrip("#").strip().lower() == heading.lower():
                start = i
                break
    rows = []
    in_table = False
    for line in lines[start:]:
        line = line.strip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set(cells[0]) <= {"-"}:  # separator row "---|---"
                in_table = True
                continue
            if not in_table and rows == [] and cells[0].lower() in ("stage", "hard gate not met"):
                in_table = True
                continue
            rows.append(tuple(cells))
        elif rows and not line.startswith("|"):
            break
    return rows


def _parse_md_bullets(md: str, heading: str, stop_heading: str | None = None) -> list[str]:
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lstrip("#").strip().lower() == heading.lower():
            start = i + 1
            break
    if start is None:
        return []
    out = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("##"):
            break
        if s.startswith("- "):
            out.append(s[2:].strip())
    return out


def build_pool_map(md_path: Path, role_id: str) -> dict:
    md = md_path.read_text(encoding="utf-8")
    # The stage-counts table has no preceding "##" heading of its own -- it
    # sits right after the intro paragraph, so heading=None grabs it as the
    # first "| ... |" table on the page.
    stages = dict(_parse_md_table(md, None))

    exclusion_rows = _parse_md_table(md, "Why candidates were excluded")
    exclusions = [{"gate": g, "count": int(c)} for g, c in exclusion_rows]

    missed = []
    for b in _parse_md_bullets(md, "Missed by one thing"):
        # "Name -- Employer -- missing only: gate"
        parts = [p.strip() for p in b.split(" -- ")]
        if len(parts) >= 3:
            missed.append({
                "name": parts[0],
                "employer": " -- ".join(parts[1:-1]),
                "missing_gate": parts[-1].replace("missing only:", "").strip(),
            })
        else:
            missed.append({"raw": b})

    client_side = []
    for b in _parse_md_bullets(md, "Client-side engineers (deliberately NOT in the shortlist)"):
        parts = [p.strip() for p in b.split(" -- ", 1)]
        client_side.append({"name": parts[0], "note": parts[1] if len(parts) > 1 else ""})

    def to_int(s):
        try:
            return int(s)
        except (TypeError, ValueError):
            return s

    return {
        "role_id": role_id,
        "profiles_assessed": to_int(stages.get("Profiles assessed")),
        "raw_claims_extracted": to_int(stages.get("Raw claims extracted")),
        "claims_surviving_quote_validation": to_int(stages.get("Claims surviving quote validation")),
        "passed_every_hard_gate": to_int(stages.get("Passed every hard gate")),
        "delivered": stages.get("Delivered"),
        "exclusions": exclusions,
        "missed_by_one": missed,
        "client_side_sidebar": client_side,
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main():
    html_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT_DIR / "live.html"
    out_candidates = SCRIPT_DIR / "candidates.json"
    out_pool_map = SCRIPT_DIR / "pool_map.json"

    cards = extract(html_path)
    out_candidates.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")

    pool_map = {
        "role1_senior_structural_engineer": build_pool_map(
            DELIVERABLES / "pool_map_role1.md", "role1_senior_structural_engineer"
        ),
        "role2_transport_major_projects_manager": build_pool_map(
            DELIVERABLES / "pool_map_role2.md", "role2_transport_major_projects_manager"
        ),
    }
    out_pool_map.write_text(json.dumps(pool_map, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- validation: count per role/tier against the HTML's own counters ----
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    print(f"Extracted {len(cards)} candidate cards -> {out_candidates}")
    print(f"Pool map written -> {out_pool_map}\n")

    for section in soup.select("section.role-band"):
        role_id = section.get("id")
        h2 = section.find("h2")
        of_span = h2.find("span")
        counter = text_of(of_span)  # e.g. "10 of 10"
        n = sum(1 for c in cards if c["role_id"] == role_id)
        print(f"validation: {role_id}: HTML header says '{counter}', extracted {n} cards")

    print()
    for role_id in sorted({c["role_id"] for c in cards}):
        tiers = {}
        for c in cards:
            if c["role_id"] == role_id:
                tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
        print(f"validation: {role_id} tier counts: {dict(sorted(tiers.items()))}")

    # ---- summary table ----
    print()
    headers = ["name", "title", "employer", "location", "country", "grade", "years", "tier", "role", "email_status"]
    rows = []
    for c in cards:
        rows.append([
            c["full_name"],
            (c["current_title"] or "")[:28],
            (c["current_employer"] or "")[:26],
            c["location"],
            c["location_country"],
            c["seniority_grade"],
            str(c["years_experience"]) if c["years_experience"] is not None else "-",
            c["tier"],
            "R1" if "role1" in c["role_id"] else "R2",
            c["email_status"],
        ])
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = " | ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))


if __name__ == "__main__":
    main()
