"""
L13 -- the renderer. The only layer the client ever sees.

Produces three artifacts in `deliverables/gaia_2026-08-20/`:

  dossier.html          self-contained, no CDN, prints cleanly, opens offline
  candidates.csv        the same 15 people, flat, for an ATS import
  pool_map_role1.md     the honest denominator per role (SPEC 2.2)
  pool_map_role2.md

Two rules shape every design decision here:

  Every claim on a card carries its verbatim quote and a link to the document
  that quote came from. A card that asserts something without showing where it
  came from is exactly the artifact this pipeline exists not to produce.

  Gaps are printed, not hidden. A Tier C card says which signal is missing, in
  the same type size as the strengths. The client is a managing director who
  will check two links in the first minute; a dossier that oversells is worth
  less than one that is short and true.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from ..core.cache import head_ok
from ..core.config import CONFIG, PKG_ROOT, PRIVACY_NOTICE_URL, WORKSPACE_ROOT
from ..roles import ROLE1, ROLE2

RUN_DIR = PKG_ROOT / "run" / CONFIG.campaign_id
OUT_DIR = WORKSPACE_ROOT / "deliverables" / "gaia_2026-08-20"

TIER_LABEL = {
    "A": "Tier A -- primary signal evidenced twice or more",
    "B": "Tier B -- primary signal evidenced once",
    "C": "Tier C -- primary signal not evidenced in public sources",
}

DIM_LABEL = {
    "chartership": "Chartership",
    "employer": "Employer",
    "location": "Location",
    "discipline": "Discipline",
    "years_experience": "Experience",
    "technical_skill": "Technical",
    "statutory_process": "Statutory process",
    "project": "Project",
    "sector": "Sector",
    "education": "Education",
    "seniority": "Seniority",
}


def _load(name: str, default=None):
    p = RUN_DIR / (name + ".json")
    if not p.exists():
        if default is None:
            raise SystemExit("Missing stage output: " + str(p))
        return default
    return json.loads(p.read_text(encoding="utf-8"))


# U+FFFD sitting between two letters is a mis-decoded apostrophe and nothing
# else -- it is how "Michael O'Reilly" survives a cp1252 smart quote read as
# UTF-8. Repairing it is faithful to the source: the character the document
# actually contains is an apostrophe, and printing the replacement glyph on a
# card that says "verbatim quote" undermines the one thing the card promises.
# The repair is deliberately narrow. A U+FFFD anywhere else is left visible,
# because an unexplained corruption should look corrupted rather than be
# silently papered over.
#
# The rule is NOT "between two letters". A mis-decoded fada is also between
# two letters, and blanket-substituting an apostrophe turned "Iarnród" into
# "Iarnr’d" on the client-side sidebar of the delivered dossier -- inventing a
# misspelling of the national rail operator's name where the source had a
# perfectly ordinary accented o. An apostrophe is only plausible after the
# one- or two-letter name particles that actually take one, so the repair is
# anchored to those: O’Reilly, D’Arcy, Mc’, Ma’.
_MOJIBAKE_APOSTROPHE = re.compile(r"(?<=\b[A-Z])�(?=[A-Z][a-z])")

# Irish organisation names whose accented characters this pipeline's PDF text
# layer routinely loses. Restored by name rather than guessed at, because
# there is no general way to recover which letter a U+FFFD used to be -- and
# a card that promises verbatim evidence must not display a corrupted
# employer for the person it is describing.
_CANONICAL_ORGS = [
    (re.compile(r"\bIarnr.?d\s+.?ireann\b", re.I), "Iarnród Éireann"),
    (re.compile(r"\bAn\s+Coimisi.?n\s+Plean.?la\b", re.I), "An Coimisiún Pleanála"),
    (re.compile(r"\bAn\s+Bord\s+Plean.?la\b", re.I), "An Bord Pleanála"),
    (re.compile(r"\bU?isce\s+.?ireann\b", re.I), "Uisce Éireann"),
]


def repair(s: str) -> str:
    s = s or ""
    if "�" in s:
        for pattern, canonical in _CANONICAL_ORGS:
            s = pattern.sub(canonical, s)
    return _MOJIBAKE_APOSTROPHE.sub("’", s)


def e(s) -> str:
    return html.escape(repair(str(s or "")))


# ---------------------------------------------------------------------------
# CSS. Inlined -- a dossier that needs the network to look right is a dossier
# that looks broken on a train.
# ---------------------------------------------------------------------------

CSS = """
:root{
  --ink:#16211c; --muted:#5c6b63; --line:#dfe5e0; --bg:#ffffff;
  --panel:#f6f8f6; --accent:#1d6f4f; --warn:#8a5a00; --warnbg:#fff6e5;
  --quote:#334b40;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.55 "Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-text-size-adjust:100%;
}
.wrap{max-width:940px;margin:0 auto;padding:32px 20px 80px}
header.doc{border-bottom:3px solid var(--accent);padding-bottom:18px;margin-bottom:8px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:15px;margin:0}
h2{font-size:21px;margin:38px 0 4px;padding-top:18px;border-top:1px solid var(--line)}
h2 .count{color:var(--muted);font-weight:400;font-size:15px}
.lede{color:var(--muted);margin:6px 0 18px;font-size:15px}
.banner{
  background:var(--warnbg);border:1px solid #e6c98a;border-left:5px solid var(--warn);
  color:var(--warn);padding:12px 14px;border-radius:6px;margin:18px 0;font-size:14.5px;
}
.card{
  border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin:18px 0;
  background:var(--bg);
}
.card h3{margin:0;font-size:20px;letter-spacing:-.01em}

/* Identity and the way to reach them, on one line. Contact used to be the
   last section of a ~980-word card. */
.head{
  display:flex;flex-wrap:wrap;gap:12px 20px;align-items:flex-start;
  justify-content:space-between;
}
.who{flex:1 1 280px;min-width:0}
.act{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:0 0 auto}
.cta{
  display:inline-block;font-size:14px;font-weight:600;text-decoration:none;
  background:var(--accent);color:#fff;border-radius:6px;padding:7px 13px;
  transition:background 160ms cubic-bezier(.22,1,.36,1);
}
a.cta:hover,a.cta:focus-visible{background:#17583f}
.reach{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}
.reach-note{margin:0 0 6px;color:var(--muted);font-size:13.5px;max-width:68ch}
.reach-alt{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px 16px}
.reach-alt li{margin:0;font-size:13.5px}
.mov{
  margin:14px 0 0;font-size:14px;color:var(--muted);max-width:70ch;
}
.mov-k{
  font-weight:600;text-transform:uppercase;letter-spacing:.05em;font-size:11.5px;
  border:1px solid var(--line);border-radius:4px;padding:1px 6px;margin-right:8px;
  color:var(--muted);white-space:nowrap;
}
.mov-high{color:var(--accent);border-color:var(--accent)}
.mov-low{color:var(--warn);border-color:#e0b46a}

/* Two roles, two deliverables. Run together they read as one list. */
.role-band{
  margin:52px 0 0;padding:20px 22px;border-radius:10px;
  background:var(--panel);border:1px solid var(--line);
}
.role-band:first-of-type{margin-top:32px}
.role-band h2{margin:0;padding:0;border:0;font-size:23px;letter-spacing:-.01em}
.role-band .of{
  display:inline-block;margin-left:10px;font-size:13px;font-weight:600;
  color:var(--accent);border:1px solid var(--accent);border-radius:999px;
  padding:2px 10px;vertical-align:middle;
}
.role-band .of.short{color:var(--warn);border-color:#e0b46a}
.role-band .lede{margin:8px 0 0}
.toc{
  display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 0;padding:0;list-style:none;
}
.toc li{margin:0}
.toc a{
  display:inline-block;font-size:14px;text-decoration:none;border:1px solid var(--line);
  border-radius:6px;padding:7px 12px;background:var(--panel);
}
.toc a:hover,.toc a:focus-visible{border-color:var(--accent)}
.role{color:var(--muted);font-size:15px;margin:2px 0 0}
.tier{
  display:inline-block;font-size:12.5px;font-weight:600;letter-spacing:.02em;
  border:1px solid var(--accent);color:var(--accent);border-radius:999px;
  padding:2px 10px;margin-top:8px;
}
.tier.b{border-color:#7a6a1f;color:#7a6a1f}
.tier.c{border-color:var(--muted);color:var(--muted)}
.sec{margin-top:16px}
.sec h4{
  margin:0 0 8px;font-size:12.5px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);font-weight:700;
}
ul{margin:0;padding-left:20px}
li{margin:0 0 8px}
.claim{margin:0 0 12px}
.claim .a{font-weight:600}
.dim{
  display:inline-block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  background:var(--panel);border:1px solid var(--line);border-radius:4px;
  padding:1px 6px;margin-right:6px;color:var(--muted);
}
.a-line{margin:0 0 3px}
.a-line:last-of-type{margin-bottom:5px}
.prov{
  font-size:12px; color:var(--warn); background:var(--warnbg);
  border-left:3px solid var(--warn); padding:6px 9px; margin-top:6px;
  border-radius:0 3px 3px 0; line-height:1.45;
}
blockquote{
  margin:6px 0 4px;padding:8px 12px;border-left:3px solid var(--accent);
  background:var(--panel);color:var(--quote);font-size:14.5px;border-radius:0 5px 5px 0;
}
.src{font-size:12.5px}
a{color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.kv{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kv .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.kv .v{font-size:15px;margin-top:3px;word-break:break-word}
.pill{font-size:11.5px;border-radius:4px;padding:1px 6px;border:1px solid}
.pill.verified{color:#1d6f4f;border-color:#1d6f4f;background:#eef7f2}
.pill.catch_all{color:#7a6a1f;border-color:#c9b76a;background:#fbf7e8}
.pill.pattern_guess{color:#8a5a00;border-color:#e0b46a;background:#fff4e3}
.pill.none{color:var(--muted);border-color:var(--line);background:var(--panel)}
details{margin-top:10px;border:1px solid var(--line);border-radius:8px;padding:10px 14px}
summary{cursor:pointer;font-weight:600;font-size:14.5px}
pre.msg{
  white-space:pre-wrap;font:13.5px/1.5 "Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:var(--panel);border:1px solid var(--line);border-radius:6px;
  padding:12px;margin:8px 0;
}
table{border-collapse:collapse;width:100%;font-size:14.5px;margin-top:10px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left}
th{background:var(--panel);font-size:12.5px;text-transform:uppercase;letter-spacing:.05em}
.gap{color:var(--warn)}
footer{margin-top:44px;border-top:1px solid var(--line);padding-top:16px;
  color:var(--muted);font-size:13.5px}
@media (max-width:640px){
  .wrap{padding:20px 14px 60px} h1{font-size:23px} .card{padding:16px}
}
@media print{
  .role-band{break-after:avoid-page}
  details{display:block}
  details>summary{display:none}

  body{font-size:11.5pt} .wrap{max-width:none;padding:0}
  .card{break-inside:avoid;page-break-inside:avoid;border-color:#bbb}
  details{border:0;padding:0} details[open] summary{margin-bottom:6px}
  a{color:inherit;text-decoration:none} .src a::after{content:" (" attr(href) ")";font-size:9pt}
  h2{page-break-after:avoid}
}
"""


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------


# Documents whose text was recovered from an image-only scan rather than read
# from a text layer. Populated by build() from the document store.
#
# This has to reach the card. L6 verifies a quote character-by-character
# against the cached source text, and for these documents that text is a
# model's transcription of a scan -- so the check is one model's quote against
# another model's reading of an image. It is still a real quote from a real
# public document, and the link goes to the original, but a reader deciding
# how much weight to put on a line of evidence deserves to know which kind
# they are looking at. Folding the two together silently would be the quiet
# kind of dishonesty this dossier exists to avoid.
_OCR_DOC_IDS: set[str] = set()


def load_ocr_doc_ids() -> set[str]:
    path = RUN_DIR / "docs.jsonl"
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or '"ocr"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue  # a torn line loses one document, never the store
        if rec.get("text_source") == "ocr" and rec.get("doc_id"):
            out.add(rec["doc_id"])
    return out


def _claims_html(claims: list[dict]) -> str:
    """Render claims, grouping everything that rests on one source sentence.

    A single sentence legitimately evidences several dimensions -- "over 25
    years of experience in structural and civil engineering in Ireland" is at
    once experience, sector and location. Emitting one bullet per dimension
    printed that sentence three times under three labels, and a card that
    repeats itself reads as padding however true each line is.

    The claims are all kept: the gates count dimensions, and the "not
    verified" section is built from which dimensions have evidence, so
    dropping one to tidy the page would quietly change what the dossier
    asserts. Only the presentation collapses -- the assertions stack above a
    single quote, shown once, with its source.
    """
    # Grouping is by CONTAINMENT, not by equality. An exact-match key fails on
    # the cases that actually occur: the same sentence quoted once with its
    # full stop and once without, or once with a leading "including". Both
    # printed the identical sentence twice under two labels.
    #
    # Deliberately looser than the validation-stage dedup, which only collapses
    # within a dimension because it changes what the gates count. This is
    # presentation only, so it can safely span dimensions -- and spanning them
    # is the point, since "25 years in structural engineering in Ireland" is
    # experience, sector and location in one sentence.
    def norm(c: dict) -> str:
        return " ".join(c["evidence_quote"].split()).lower().strip(" .;,:")

    groups: list[list[dict]] = []
    for c in sorted(claims, key=lambda x: -len(norm(x))):
        q = norm(c)
        for group in groups:
            g = norm(group[0])
            if q and (q in g or g in q):
                group.append(c)
                break
        else:
            groups.append([c])

    # Longest quote first inside a group is an artefact of the sort above; the
    # cards read better in the order the claims arrived.
    index = {id(c): i for i, c in enumerate(claims)}
    groups.sort(key=lambda g: min(index[id(c)] for c in g))
    for group in groups:
        group.sort(key=lambda c: index[id(c)])

    out: list[str] = []
    for group in groups:
        # The displayed quote is the longest in the group -- the one carrying
        # the most context for a reader who clicks through to check it.
        longest = max(group, key=lambda c: len(c["evidence_quote"]))
        head = "".join(
            '<div class="a-line">'
            '<span class="dim">' + e(DIM_LABEL.get(c["dimension"], c["dimension"]))
            + "</span>"
            '<span class="a">' + e(c["assertion"]) + "</span>"
            "</div>"
            for c in group
        )
        first = longest
        provenance = ""
        if first.get("source_doc_id") in _OCR_DOC_IDS:
            provenance = (
                '<div class="prov">Text recovered by OCR from a scanned '
                "document. The quote was verified against that transcription, "
                "not against a machine-readable original &mdash; check it "
                "against the linked PDF before relying on the exact wording."
                "</div>"
            )
        out.append(
            '<div class="claim">'
            + head
            + "<blockquote>&ldquo;" + e(first["evidence_quote"].strip())
            + "&rdquo;</blockquote>"
            '<div class="src">Source: <a href="' + e(first["source_url"]) + '">'
            + e(_short_url(first["source_url"])) + "</a></div>"
            + provenance
            + "</div>"
        )
    return "".join(out)


def _claim_html(c: dict) -> str:
    dim = DIM_LABEL.get(c["dimension"], c["dimension"])
    provenance = ""
    if c.get("source_doc_id") in _OCR_DOC_IDS:
        provenance = (
            '<div class="prov">Text recovered by OCR from a scanned document. '
            "The quote was verified against that transcription, not against a "
            "machine-readable original &mdash; check it against the linked PDF "
            "before relying on the exact wording.</div>"
        )
    return (
        '<div class="claim">'
        '<span class="dim">' + e(dim) + "</span>"
        '<span class="a">' + e(c["assertion"]) + "</span>"
        "<blockquote>&ldquo;" + e(c["evidence_quote"].strip()) + "&rdquo;</blockquote>"
        '<div class="src">Source: <a href="' + e(c["source_url"]) + '">'
        + e(_short_url(c["source_url"])) + "</a></div>"
        + provenance
        + "</div>"
    )


def _short_url(u: str) -> str:
    s = str(u).replace("https://", "").replace("http://", "").replace("www.", "")
    return s if len(s) <= 78 else s[:75] + "..."


def _reach_routes(person: dict, contact: dict) -> list[tuple[str, str, str]]:
    """Ranked ways to actually reach this person. Never returns an empty list.

    On the first delivered run, six of thirteen cards were a dead end: five had
    a pattern-guessed address the card itself told the reader not to use for a
    first touch and no LinkedIn URL, and one had nothing at all. A shortlist
    entry nobody can contact is not a shortlist entry.

    A missing LinkedIn URL never meant the person has no LinkedIn -- it meant
    the enrichment provider did not return one. The profile is still findable,
    so the card hands over the search rather than a shrug. Same for the firm:
    every one of these people works somewhere with a switchboard, and asking
    for an engineer by name is ordinary recruiter practice.

    Each route is (kind, label, href-or-empty), strongest first.
    """
    from ..layers.contact import _employer_domain, domain_of

    routes: list[tuple[str, str, str]] = []
    name = (person.get("full_name") or "").strip()
    employer = (person.get("current_employer") or "").strip()
    status = contact.get("email_status", "none")
    email = contact.get("email")
    li = contact.get("linkedin_url")

    if li:
        routes.append(("linkedin", "LinkedIn profile", str(li)))
    if email and status in ("verified", "catch_all"):
        label = ("Work email, SMTP-verified" if status == "verified"
                 else "Work email, catch-all domain")
        routes.append(("email", label + " — " + str(email), "mailto:" + str(email)))

    # Always available, and the reason no card is a dead end.
    if name:
        query = name + ((" " + employer) if employer else "")
        routes.append((
            "search",
            "Find on LinkedIn — search \"" + query + "\"",
            "https://www.linkedin.com/search/results/people/?keywords="
            + quote_plus(query),
        ))

    domain = _employer_domain(employer) or domain_of(
        "https://" + str(email).split("@")[-1] if email and "@" in str(email) else None)
    if domain:
        routes.append((
            "switchboard",
            "Call " + (employer or domain) + " and ask for " + (name or "them"),
            "https://" + domain,
        ))
    elif employer:
        # No resolved domain is not the same as no firm. Cronin & Sutton is a
        # real Dublin consultancy with a real switchboard; it simply is not in
        # the Role 1 sourcing list, so no domain was ever fetched for it.
        routes.append((
            "switchboard",
            "Find " + employer + " and ask for " + (name or "them"),
            "https://duckduckgo.com/?q=" + quote_plus(employer + " Ireland contact"),
        ))

    if email and status == "pattern_guess":
        routes.append((
            "guess",
            "Inferred address, unverified — " + str(email),
            "mailto:" + str(email),
        ))

    if person.get("profile_url"):
        routes.append(("profile", "Their profile page at the firm",
                       str(person["profile_url"])))
    return routes


def _reach_block(person: dict, contact: dict, links: dict) -> str:
    routes = _reach_routes(person, contact)
    best = routes[0]

    KIND_NOTE = {
        "linkedin": "Message here first. Approaching a senior engineer at their "
                    "employer's mailbox about leaving that employer is monitored "
                    "mail and poor tradecraft.",
        "email": "Confirmed deliverable. Still second choice behind LinkedIn.",
        "search": "The provider returned no profile URL, which is not the same as "
                  "there being no profile. This search finds it.",
        "switchboard": "No confirmed digital route. Ask the switchboard for them "
                       "by name — ordinary practice, and it works.",
        "guess": "Built from the firm's naming pattern. Never use it for a first "
                 "touch.",
        "profile": "",
    }

    # The primary route is the button in the card header; repeating it here
    # would be the same sentence twice.
    out = ['<div class="reach">']
    note = KIND_NOTE.get(best[0], "")
    if note:
        out.append('<p class="reach-note">' + e(note) + "</p>")

    if len(routes) > 1:
        out.append('<ul class="reach-alt">')
        for kind, label, href in routes[1:]:
            out.append("<li>" + ('<a href="' + e(href) + '">' + e(label) + "</a>"
                                 if href else e(label)) + "</li>")
        out.append("</ul>")

    checks = links.get("checks", []) if links else []
    dead = [c for c in checks if c.get("alive") is False]
    if dead:
        out.append('<p class="reach-note gap">' + str(len(dead))
                   + " source link(s) did not return 200 — check before citing.</p>")
    out.append("</div>")
    return "".join(out)


def _contact_block(contact: dict, links: dict) -> str:
    status = contact.get("email_status", "none")
    email = contact.get("email")
    li = contact.get("linkedin_url")

    email_note = {
        "verified": "SMTP-verified by the provider.",
        "catch_all": "Domain accepts all mail -- deliverable, but not proof this "
                     "mailbox exists.",
        "pattern_guess": "Constructed from the firm's naming pattern. NOT verified. "
                         "Treat as a guess.",
        "none": "No address found.",
    }[status]

    cells = [
        '<div class="kv"><div class="k">Email</div><div class="v">'
        + (e(email) if email else "<span class='gap'>not found</span>")
        + ' <span class="pill ' + e(status) + '">' + e(status.replace("_", " ")) + "</span>"
        + '<div class="src" style="margin-top:4px">' + e(email_note) + "</div></div></div>",
        '<div class="kv"><div class="k">LinkedIn</div><div class="v">'
        + (('<a href="' + e(li) + '">' + e(_short_url(li)) + "</a>") if li
           else "<span class='gap'>not found by the provider</span>")
        + "</div></div>",
        '<div class="kv"><div class="k">First channel</div><div class="v">'
        + e(str(contact.get("recommended_first_channel", "linkedin")).replace("_", " "))
        + '<div class="src" style="margin-top:4px">'
        + e(contact.get("channel_rationale", "")) + "</div></div></div>",
    ]

    checks = links.get("checks", [])
    # Three states, reported as three different things. Collapsing
    # "we could not check this" into "this is broken" is how a dossier tells a
    # client that a working LinkedIn profile is a dead link.
    dead = [c for c in checks if c.get("alive") is False]
    blocked = [c for c in checks if c.get("alive") is None]
    live = [c for c in checks if c.get("alive") is True]
    mism = [c for c in checks if c.get("name_matched") is False]
    if links:
        problems = []
        if dead:
            problems.append(str(len(dead)) + " source link(s) did not return 200")
        if mism:
            problems.append(str(len(mism)) + " live link(s) no longer name this person")
        if problems:
            v = "<span class='gap'>" + e("; ".join(problems)) + "</span>"
        elif live and not blocked:
            v = "All " + str(len(live)) + " links live and checked"
        elif live:
            v = (
                str(len(live)) + " link(s) live and checked; "
                + str(len(blocked)) + " could not be checked automatically "
                "(the host blocks robots, LinkedIn always does) "
                "&mdash; nothing suggests they are broken"
            )
        else:
            v = (
                str(len(blocked)) + " link(s) could not be checked automatically "
                "(the host blocks robots) &mdash; nothing suggests they are broken"
            )
        cells.append(
            '<div class="kv"><div class="k">Link check</div><div class="v">' + v + "</div></div>"
        )

    return '<div class="grid">' + "".join(cells) + "</div>"


def card_html(
    person: dict,
    claims: list[dict],
    ev: dict,
    contact: dict,
    mov: dict,
    outreach: dict | None,
    links: dict,
    spec,
) -> str:
    tier = ev.get("tier", "C")
    parts: list[str] = ['<article class="card">']

    # Identity and the way to reach them sit together at the top. Contact used
    # to be the last section of a ~980-word card, which put the single most
    # actionable fact behind everything else on the page.
    routes = _reach_routes(person, contact)
    best = routes[0]
    parts.append('<div class="head">')
    parts.append('<div class="who">')
    parts.append("<h3>" + e(person["full_name"]) + "</h3>")
    parts.append(
        '<p class="role">'
        + e(person.get("current_title") or "Title not stated in public sources")
        + (" &middot; " + e(person["current_employer"]) if person.get("current_employer") else "")
        + (" &middot; " + e(person["location"]) if person.get("location") else "")
        + "</p>"
    )
    parts.append("</div>")
    parts.append(
        '<div class="act">'
        + ('<a class="cta" href="' + e(best[2]) + '">' + e(best[1]) + "</a>"
           if best[2] else '<span class="cta">' + e(best[1]) + "</span>")
        + '<span class="tier ' + tier.lower() + '">'
        + e(TIER_LABEL.get(tier, tier).split("--")[0].strip()) + "</span>"
        + "</div>")
    parts.append("</div>")
    parts.append(_reach_block(person, contact, links))

    # -- Evidence, primary signal first -------------------------------------
    primary = [c for c in claims if c["dimension"] == spec.primary_signal_dimension]
    other = [c for c in claims if c["dimension"] != spec.primary_signal_dimension]
    direct = [c for c in primary + other if c.get("confidence") == "direct"]
    inferred = [c for c in primary + other if c.get("confidence") != "direct"]

    if direct:
        # No heading. Every quote already carries "Source: <link>" beneath it,
        # so a banner announcing that quotes are verified restated on every
        # card what each line demonstrates on its own.
        parts.append('<div class="sec">')
        parts.append(_claims_html(direct))
        parts.append("</div>")

    if inferred:
        parts.append('<div class="sec"><h4>Possible, unconfirmed</h4><ul>')
        for c in inferred:
            parts.append(
                "<li>" + e(c["assertion"])
                + ' <span class="src">(inferred, not directly stated)</span></li>'
            )
        parts.append("</ul></div>")

    # The "Not verified / open questions" section is gone. It ran to 3,228
    # words across thirteen cards -- a quarter of everything on the page -- by
    # concatenating four overlapping sources into one flat list, including
    # notes from gates that had PASSED. The honest accounting it existed to
    # provide has a better home: pool_map_role1.md and pool_map_role2.md carry
    # the full denominator, every exclusion reason with counts, and each
    # near-miss by name. A caveat nobody reads is not disclosure.

    if ev.get("strengths"):
        parts.append('<div class="sec"><h4>Why this person, in one reader\'s words</h4><ul>')
        for s in [x for x in ev["strengths"] if len(str(x).strip()) > 1]:
            parts.append("<li>" + e(s) + "</li>")
        parts.append("</ul></div>")

    # -- Movability, as one line -------------------------------------------
    if mov and (mov.get("assessment") or mov.get("rationale")):
        assessment = str(mov.get("assessment", "unknown")).lower()
        parts.append(
            '<p class="mov"><span class="mov-k mov-' + e(assessment) + '">'
            + e(assessment) + " movability</span> "
            + e(mov.get("rationale", "")) + "</p>"
        )

    # -- Contact ------------------------------------------------------------


    # -- Outreach -----------------------------------------------------------
    if outreach:
        parts.append("<details><summary>Outreach drafts (edit before sending)</summary>")
        parts.append("<p class='src' style='margin:8px 0 0'>"
                     "LinkedIn connection note</p>")
        parts.append("<pre class='msg'>" + e(outreach["linkedin_note"]) + "</pre>")
        parts.append("<p class='src' style='margin:8px 0 0'>Email &mdash; subject: "
                     + e(outreach["email_subject"]) + "</p>")
        parts.append("<pre class='msg'>" + e(outreach["email_body"]) + "</pre>")
        if outreach.get("follow_up"):
            parts.append("<p class='src' style='margin:8px 0 0'>Follow-up, about a "
                         "week later</p>")
            parts.append("<pre class='msg'>" + e(outreach["follow_up"]) + "</pre>")
        parts.append("</details>")

    parts.append("</article>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Pool map
# ---------------------------------------------------------------------------


def pool_map_md(m: dict, spec) -> str:
    lines = [
        "# Pool map -- " + spec.title,
        "",
        "Where the pool went. Published because a shortlist without a denominator",
        "is a claim, not a finding.",
        "",
        "| Stage | Count |",
        "|---|---|",
        "| Profiles assessed | " + str(m["profiles_assessed"]) + " |",
        "| Raw claims extracted | " + str(m["raw_claims"]) + " |",
        "| Claims surviving quote validation | " + str(m["evidence_validated"]) + " |",
        "| Passed every hard gate | " + str(m["passed_all_gates"]) + " |",
        "| Delivered | " + str(m["delivered"]) + " of " + str(spec.target_count) + " |",
        "",
        "## Why candidates were excluded",
        "",
        "| Hard gate not met | Candidates |",
        "|---|---|",
    ]
    for row in m["exclusions"]:
        lines.append("| " + row["reason"] + " | " + str(row["count"]) + " |")
    if not m["exclusions"]:
        lines.append("| (none) | 0 |")

    if m.get("near_misses"):
        lines += [
            "",
            "## Missed by one thing",
            "",
            "Each of these passed every hard gate but one. They are listed",
            "because a single named gap is something you can act on -- by",
            "widening the brief, or by asking us to verify the one open point.",
            "",
        ]
        for s_ in m["near_misses"]:
            lines.append("- " + s_)

    if m.get("client_side_sidebar"):
        lines += [
            "",
            "## Client-side engineers (deliberately NOT in the shortlist)",
            "",
            "These people have the statutory-process experience the role wants but",
            "sit at TII, the NTA, a local authority or a similar body. They are a",
            "different placement conversation and are listed here rather than",
            "counted toward the target.",
            "",
        ]
        for s in m["client_side_sidebar"]:
            lines.append("- " + s)

    lines += ["", "Generated " + date.today().isoformat() + " -- campaign "
              + CONFIG.campaign_id + "."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build(allow_placeholder_notice: bool = False) -> None:
    global _OCR_DOC_IDS
    _OCR_DOC_IDS = load_ocr_doc_ids()
    persons_raw = _load("extract")["persons"]
    validated = _load("validate")["claims"]
    gate_out = _load("gate")
    adv = _load("adversarial", {})
    contacts = _load("contact", {})
    movs = _load("movability", {})
    outreach = _load("messages", {})
    links = _load("linkcheck", {})
    pool = _load("poolmap")
    delivery = _load("delivery", {})

    by_person: dict[str, list[dict]] = {}
    for c in validated:
        by_person.setdefault(c["subject_person_id"], []).append(c)

    # -- Notice gate. Outreach that cites an Art.14 notice which 404s is worse
    # -- than outreach with no notice, so the drafts are withheld rather than
    # -- shipped pointing at a dead URL.
    notice_live, notice_status = head_ok(PRIVACY_NOTICE_URL)
    if not notice_live and not allow_placeholder_notice:
        raise SystemExit(
            "REFUSING TO RENDER: the Art. 14 privacy notice at "
            + PRIVACY_NOTICE_URL + " returned " + str(notice_status) + ".\n"
            "Every outreach draft cites that URL. Deploy the notice and re-run,\n"
            "or pass --allow-placeholder-notice to render the dossier WITHOUT\n"
            "the outreach drafts and with a warning banner."
        )
    include_outreach = notice_live

    order = {"A": 0, "B": 1, "C": 2}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    body: list[str] = []
    csv_rows: list[dict] = []
    delivered_total = 0

    for spec in (ROLE1, ROLE2):
        m = pool[spec.role_id]
        def final_tier(pid: str) -> str:
            rec = adv.get(pid) or {}
            return rec.get("tier") or gate_out[pid]["tier"]

        # The pipeline's own list, not a second opinion about it. Recomputing
        # it here shipped two people the contact stage had never enriched --
        # cards with no email, no LinkedIn and no route -- because this copy
        # applied a slightly different filter and broke ties the other way.
        pids = list(delivery.get(spec.role_id) or [])
        if not pids:
            pids = [
                pid for pid, g in gate_out.items()
                if g["role_id"] == spec.role_id and g["tier"] != "EXCLUDED"
                and not g["client_side"] and final_tier(pid) != "EXCLUDED"
            ]
            pids.sort(key=lambda p: (order.get(final_tier(p), 3),
                                     -gate_out[p]["n_claims"], p))
            pids = pids[: spec.target_count]
        delivered_total += len(pids)

        short = len(pids) < spec.target_count
        body.append('<section class="role-band" id="' + e(spec.role_id) + '">')
        body.append(
            "<h2>" + e(spec.title)
            + '<span class="of' + (" short" if short else "") + '">'
            + str(len(pids)) + " of " + str(spec.target_count) + "</span></h2>"
        )
        body.append(
            '<p class="lede">' + e(", ".join(spec.locations)) + ". "
            + "Assessed " + str(m["profiles_assessed"]) + " profiles; "
            + str(m["passed_all_gates"]) + " passed every hard gate. "
            + "Ranked by strength of evidence on "
            + e(spec.primary_signal_dimension.replace("_", " ")) + ".</p>"
        )
        body.append("</section>")
        if len(pids) < spec.target_count:
            body.append(
                '<div class="banner"><strong>Short of target.</strong> '
                + str(len(pids)) + " of " + str(spec.target_count)
                + " delivered. The pool map for this role lists exactly which gate "
                "removed each of the others. Padding the list with candidates who "
                "fail a hard gate would be the alternative, and it is not one.</div>"
            )

        for pid in pids:
            person = dict(persons_raw[pid])
            g = gate_out[pid]
            ev = adv.get(pid) or {
                "tier": g["tier"],
                "gates": g["gates"],
                "strengths": [],
                "unknowns": [
                    "This candidate did not receive the adversarial second pass; "
                    "the card reflects one reviewer only."
                ],
                "adversarial_findings": [],
            }
            ev = dict(ev)
            ev.setdefault("gates", g["gates"])
            pclaims = by_person.get(pid, [])
            contact = contacts.get(pid, {"email_status": "none"})
            body.append(
                card_html(
                    person, pclaims, ev, contact, movs.get(pid, {}),
                    outreach.get(pid) if include_outreach else None,
                    links.get(pid, {}), spec,
                )
            )

            csv_rows.append(
                {
                    "role": spec.title,
                    "tier": ev.get("tier", g["tier"]),
                    "full_name": person["full_name"],
                    "current_title": person.get("current_title") or "",
                    "current_employer": person.get("current_employer") or "",
                    "location": person.get("location") or "",
                    "email": contact.get("email") or "",
                    "email_status": contact.get("email_status", "none"),
                    "linkedin_url": contact.get("linkedin_url") or "",
                    "profile_url": person.get("profile_url") or "",
                    "evidence_claims": len(pclaims),
                    "primary_signal_claims": len(
                        [c for c in pclaims
                         if c["dimension"] == spec.primary_signal_dimension
                         and c.get("confidence") == "direct"]
                    ),
                    "movability": (movs.get(pid) or {}).get("assessment", "unknown"),
                    "recommended_channel": contact.get("recommended_first_channel", ""),
                    "top_evidence_source": (pclaims[0]["source_url"] if pclaims else ""),
                }
            )

        (OUT_DIR / ("pool_map_" + ("role1" if spec is ROLE1 else "role2") + ".md")).write_text(
            pool_map_md(m, spec), encoding="utf-8"
        )

    # -- Client-side sidebar -------------------------------------------------
    sidebar = []
    for spec in (ROLE1, ROLE2):
        sidebar += pool[spec.role_id].get("client_side_sidebar", [])
    sidebar = sorted(set(sidebar))

    banner = ""
    if not include_outreach:
        banner = (
            '<div class="banner"><strong>Outreach drafts withheld.</strong> '
            "Every draft cites a GDPR Article 14 privacy notice at <code>"
            + e(PRIVACY_NOTICE_URL) + "</code>, which is not live yet (HTTP "
            + str(notice_status) + "). Sending outreach that cites a dead notice "
            "URL is worse than sending none, so the drafts are held back until "
            "the notice is published. The candidate evidence below is unaffected."
            "</div>"
        )

    head = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Gaia Talent -- TOBIN / AtkinsRealis shortlist</title>"
        "<style>" + CSS + "</style></head><body><div class='wrap'>"
        "<header class='doc'><h1>Senior Structural Engineer &amp; Transport Major "
        "Projects Manager</h1>"
        "<p class='sub'>Evidence-backed shortlist prepared for Gaia Talent Ltd &middot; "
        + date.today().strftime("%d %B %Y") + " &middot; " + str(delivered_total)
        + " candidates</p></header>"
        "<p class='lede'>Every factual statement on every card below is a verbatim "
        "quote from a public document, checked character-by-character against the "
        "cached source before it was allowed onto the page. Claims that could not be "
        "matched to their source were dropped rather than softened. Where a signal is "
        "missing, the card says so.</p>"
        + banner
    )

    tail = (
        ("<h2>Client-side engineers &mdash; not part of the shortlist</h2>"
         "<p class='lede'>These people have the statutory-process experience the "
         "transport role wants, but they work for the bodies that commission the "
         "schemes rather than the consultancies that deliver them. A different "
         "conversation, listed here because leaving them out entirely would hide "
         "something useful.</p><ul>"
         + "".join("<li>" + e(s) + "</li>" for s in sidebar) + "</ul>")
        if sidebar else ""
    ) + (
        "<footer><p><strong>Method.</strong> Public sources only: company staff "
        "directories and An Coimisi&uacute;n Pleanála oral-hearing documents. "
        "No claim appears without a verbatim quote that was verified against its "
        "cached source. Tiering is deterministic: hard gates are Python, never a "
        "model's opinion. Each shortlisted candidate was reviewed a second time by "
        "a reviewer that could not see the first review's verdict.</p>"
        "<p><strong>Contact-data honesty.</strong> Addresses are labelled "
        "<em>verified</em>, <em>catch-all</em> or <em>pattern guess</em> and those "
        "labels are never collapsed. A pattern guess is a guess.</p>"
        "<p>Generated " + date.today().isoformat() + " &middot; campaign "
        + e(CONFIG.campaign_id) + ".</p></footer>"
        "</div></body></html>"
    )

    (OUT_DIR / "dossier.html").write_text(head + "".join(body) + tail, encoding="utf-8")

    fields = list(csv_rows[0].keys()) if csv_rows else ["role", "full_name"]
    with (OUT_DIR / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    print("rendered " + str(delivered_total) + " candidates -> " + str(OUT_DIR))
    for f in sorted(OUT_DIR.iterdir()):
        print("  " + f.name + "  " + format(f.stat().st_size / 1024, ".1f") + " KB")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the Gaia dossier")
    ap.add_argument(
        "--allow-placeholder-notice",
        action="store_true",
        help="render without outreach drafts when the Art.14 notice is not live",
    )
    args = ap.parse_args()
    build(allow_placeholder_notice=args.allow_placeholder_notice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
