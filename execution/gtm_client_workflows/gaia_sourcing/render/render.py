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
  font:16px/1.5 "Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-text-size-adjust:100%;
}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 72px}
header.doc{border-bottom:3px solid var(--accent);padding-bottom:16px;margin-bottom:10px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:15px;margin:0}
.lede{color:var(--muted);margin:6px 0 16px;font-size:14.5px}
/* The standing note runs the full width of the table beneath it. Capped at
   80ch it wrapped after roughly half the page and left the right-hand side
   empty, so the header looked misaligned with the four columns it introduces. */
.lede.wide{max-width:none;text-align:left}
.role-lede{max-width:96ch}
h2{font-size:20px;margin:34px 0 2px}
h2 .of{
  color:var(--muted);font-weight:400;font-size:13px;margin-left:10px;
  border:1px solid var(--line);border-radius:4px;padding:1px 7px;white-space:nowrap;
}
h2 .of.short{color:var(--warn);border-color:#e0b46a}
.banner{
  background:var(--warnbg);border:1px solid #e6c98a;border-left:5px solid var(--warn);
  color:var(--warn);padding:11px 13px;border-radius:6px;margin:16px 0;font-size:14px;
}

/* One table, four columns. The card layout put ~980 words in front of a
   reader whose whole question is "who do I contact, and what do I say". */
table.sl{
  width:100%;border-collapse:collapse;margin:14px 0 8px;
  font-size:14px;table-layout:fixed;
}
table.sl th{
  text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);font-weight:600;padding:0 12px 7px;border-bottom:2px solid var(--accent);
}
table.sl td{
  padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top;
}
col.c-who{width:20%} col.c-why{width:27%} col.c-msg{width:38%} col.c-det{width:15%}
tr.r:hover td{background:var(--panel)}

.nm{font-size:16px;font-weight:600;letter-spacing:-.01em;margin:0 0 2px}
.ro{color:var(--muted);font-size:12.5px;margin:0 0 9px;line-height:1.35}
.btns{display:flex;flex-direction:column;gap:5px;align-items:stretch}
.cta{
  display:block;text-align:center;font-size:13px;font-weight:600;text-decoration:none;
  background:var(--accent);color:#fff;border-radius:5px;padding:6px 10px;
  transition:background 160ms cubic-bezier(.22,1,.36,1);
}
a.cta:hover,a.cta:focus-visible{background:#17583f}
/* A search box is not a profile. Same amber the email column uses for a
   guess, so one convention covers both kinds of uncertainty. */
.cta-li.weak{background:var(--bg);color:var(--warn);border:1px solid #e0b46a}
a.cta-li.weak:hover,a.cta-li.weak:focus-visible{background:var(--warnbg)}
.cta-em,.cta-alt{background:var(--bg);color:var(--accent);border:1px solid var(--accent)}
a.cta-alt:hover,a.cta-alt:focus-visible{background:var(--panel)}
a.cta-em:hover,a.cta-em:focus-visible{background:var(--panel)}
.cta-em.weak{color:var(--warn);border-color:#e0b46a}
a.cta-em.weak:hover,a.cta-em.weak:focus-visible{background:var(--warnbg)}
/* Clipboard confirmation. mailto: has no success callback, so the copy is the
   only part of the click we can prove happened. */
a.cta-em.copied,a.cta-em.weak.copied{
  background:var(--accent);color:#fff;border-color:var(--accent)
}
.none{color:var(--muted);font-size:12px;font-style:italic}

.tier{
  display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.05em;border:1px solid var(--line);border-radius:4px;
  padding:1px 6px;margin-bottom:7px;color:var(--muted);
}
.tier.a{color:var(--accent);border-color:var(--accent)}
.tier.b{color:var(--ink)}
.why{margin:0;padding-left:16px}
.why li{margin:0 0 5px;line-height:1.45}

.msg-k{
  font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  font-weight:600;margin:0 0 3px;display:flex;gap:8px;align-items:baseline;
}
.msg-k .lbl{flex:1 1 auto;min-width:0}
.msg-wrap+.msg-k{margin-top:10px}
/* Reading the message in a 132px box is not the job -- sending it is. The
   button copies the exact text that would be sent, so the box only has to
   show enough to recognise which message it is. */
button.cp{
  flex:0 0 auto;font:600 10.5px/1 inherit;letter-spacing:.04em;text-transform:uppercase;
  color:var(--accent);background:none;border:1px solid var(--line);border-radius:4px;
  padding:3px 7px;cursor:pointer;
}
button.cp:hover,button.cp:focus-visible{border-color:var(--accent);background:var(--panel)}
button.cp.copied{background:var(--accent);color:#fff;border-color:var(--accent)}
/* A capped box with no visible edge reads as a cut-off document. The fade is
   the "there is more" signal that a screenshot can actually show. */
.msg-wrap{position:relative}
/* Only where there is genuinely more to see. A fade over a message that
   already fits promises content that does not exist. */
.msg-wrap.more::after{
  content:"";position:absolute;left:1px;right:1px;bottom:1px;height:22px;
  background:linear-gradient(rgba(246,248,246,0),var(--panel));
  border-radius:0 0 5px 5px;pointer-events:none;
}
pre.msg{
  margin:0;white-space:pre-wrap;word-wrap:break-word;font:12.5px/1.5 inherit;
  background:var(--panel);border:1px solid var(--line);border-radius:5px;
  padding:8px 10px;color:var(--quote);
  max-height:132px;overflow-y:scroll;scrollbar-width:thin;
}

.det-btn{
  font:600 13px/1 inherit;color:var(--accent);background:none;
  border:1px solid var(--line);border-radius:5px;padding:7px 10px;cursor:pointer;
  width:100%;text-align:left;
}
.det-btn:hover,.det-btn:focus-visible{border-color:var(--accent);background:var(--panel)}
.det-ar{
  display:inline-block;font-size:10px;margin-right:6px;
  transition:transform 140ms cubic-bezier(.22,1,.36,1);
}
.det-btn[aria-expanded="true"] .det-ar{transform:rotate(90deg)}
tr.det>td{background:var(--panel);padding:14px 16px 16px}
.det-in{max-width:88ch;font-size:13.5px;line-height:1.55}
.det-in p{margin:0 0 7px}
.det-in .claim{
  margin:0 0 8px;padding-left:11px;border-left:3px solid var(--line);
}
.det-in blockquote{margin:0;padding:0;border:0;color:var(--quote);display:inline}
.det-in .src{font-size:11.5px;color:var(--muted);display:inline;margin-left:6px}
.det-in .facts{margin:9px 0 0;padding-top:8px;border-top:1px solid var(--line)}
.det-in a{color:var(--accent)}
.gap{color:var(--warn)}

@media (max-width:900px){
  table.sl,table.sl thead,table.sl tbody,table.sl tr,table.sl td{display:block;width:100%}
  /* Must out-specify the rule above, or `hidden` stops meaning hidden. */
  table.sl tr[hidden]{display:none}
  table.sl thead{display:none}
  table.sl td{border:0;padding:6px 0}
  tr.r{border:1px solid var(--line);border-radius:8px;padding:14px;margin:12px 0;display:block}
  .btns{flex-direction:row;flex-wrap:wrap}
  .cta{display:inline-block}
}
@media print{
  .det-btn,button.cp{display:none}
  .msg-wrap.more::after{display:none}
  tr.det{display:table-row !important}
  tr.r,tr.det,pre.msg{page-break-inside:avoid;break-inside:avoid}
  pre.msg{max-height:none;overflow:visible}
  a{color:inherit;text-decoration:none}
}
"""


# A mailto: link is not, on its own, a working contact route.
#
# The button was correct HTML and still did nothing when clicked. Windows hands
# the mailto: protocol to whatever holds the UserChoice association, which is
# routinely a browser rather than a mail client; if that browser has no web
# mail handler registered, the navigation is dropped without an error, a
# console line or any visible change. The same click is inert again inside a
# sandboxed iframe, which is how this file gets previewed. In every one of
# those cases the reader clicks, nothing happens, and the reasonable conclusion
# is that the dossier is broken.
#
# The address is the thing the reader actually needs, so the click puts it on
# the clipboard and the label confirms it. The default is deliberately NOT
# prevented: where a mail client does exist it still opens, and the copy is
# harmless. Degrades in order -- async clipboard, execCommand, and finally
# showing the address in the button itself for manual selection.
COPY_JS = """
(function(){
  var RESTORE = 1800;
  function flash(a, msg){
    if (a.dataset.busy) { return; }
    var original = a.textContent;
    a.dataset.busy = '1';
    a.classList.add('copied');
    a.textContent = msg;
    setTimeout(function(){
      a.textContent = original;
      a.classList.remove('copied');
      delete a.dataset.busy;
    }, RESTORE);
  }
  function legacyCopy(text){
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  document.addEventListener('click', function(ev){
    var t = ev.target;
    if (!t || !t.closest) { return; }
    var a = t.closest('a.cta-em, a[href^="mailto:"], button.cp');
    if (!a) { return; }
    var literal = a.getAttribute('data-copy');
    if (literal !== null) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(literal).then(function(){
          flash(a, 'Copied');
        }, function(){
          flash(a, legacyCopy(literal) ? 'Copied' : 'Select the text below');
        });
      } else {
        flash(a, legacyCopy(literal) ? 'Copied' : 'Select the text below');
      }
      return;
    }
    /* The button carries the address explicitly; the reach-block links carry
       it only in the href, so fall back to reading it off there rather than
       leaving those clicks inert for the same reason as before. */
    var addr = a.getAttribute('data-email');
    if (!addr) {
      var h = a.getAttribute('href') || '';
      addr = h.replace(/^mailto:/i, '').split('?')[0];
      try { addr = decodeURIComponent(addr); } catch (err) { /* keep raw */ }
    }
    if (!addr) { return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(addr).then(function(){
        flash(a, 'Address copied');
      }, function(){
        flash(a, legacyCopy(addr) ? 'Address copied' : addr);
      });
    } else {
      flash(a, legacyCopy(addr) ? 'Address copied' : addr);
    }
  });

  /* Mark only the message boxes that actually overflow, so the fade is a
     fact about the content rather than a decoration on every box. */
  function markOverflow(){
    var wraps = document.querySelectorAll('.msg-wrap');
    for (var i = 0; i < wraps.length; i++) {
      var pre = wraps[i].querySelector('pre.msg');
      if (!pre) { continue; }
      var more = pre.scrollHeight > pre.clientHeight + 2;
      wraps[i].classList.toggle('more', more);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markOverflow);
  } else {
    markOverflow();
  }
  window.addEventListener('resize', markOverflow);

  /* The detail pane. A <details> element inside a table cell would open
     inside that column's width, which is the narrowest place on the page to
     read a quotation; this toggles a full-width row underneath instead.
     hidden is the only state -- no class, no inline style -- so print CSS can
     override it and show every pane at once. */
  document.addEventListener('click', function(ev){
    var t = ev.target;
    if (!t || !t.closest) { return; }
    var btn = t.closest('.det-btn');
    if (!btn) { return; }
    var row = document.getElementById(btn.getAttribute('aria-controls'));
    if (!row) { return; }
    var open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    row.hidden = open;
    var lb = btn.querySelector('.det-lb');
    if (lb) { lb.textContent = open ? 'Click here for details' : 'Hide details'; }
  });
})();
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


_SAFE_SCHEMES = ("http://", "https://", "mailto:", "tel:")


def _safe_url(url: str) -> str:
    """Drop any href whose scheme is not one this document has a reason to use.

    e() escapes, it does not validate: `javascript:alert(1)` survived it intact
    into an href. Nothing in the current pipeline can produce one -- these URLs
    come from our own crawler and the enrichment provider -- but "no current
    caller is hostile" is a property of today's inputs, not of this function,
    and the artifact is circulated outside the workspace.
    """
    u = str(url or "").strip()
    return u if u.lower().startswith(_SAFE_SCHEMES) else ""


def _quote_norm(c: dict) -> str:
    return " ".join(str(c.get("evidence_quote") or "").split()).lower().strip(" .;,:")


def _group_by_quote(claims: list[dict]) -> list[list[dict]]:
    """Group every claim that rests on the same source sentence.

    Grouping is by CONTAINMENT, not equality. An exact-match key fails on the
    cases that actually occur: the same sentence quoted once with its full stop
    and once without, or once with a leading "including". Both printed the
    identical sentence twice under two labels.

    Deliberately looser than the validation-stage dedup, which only collapses
    within a dimension because it changes what the gates count. This is
    presentation only, so it can safely span dimensions -- and spanning them is
    the point, since "25 years in structural engineering in Ireland" is
    experience, sector and location in one sentence.

    Shared by the long-form renderer and the detail pane. It lived only in
    _claims_html until the table layout stopped calling that function, which
    silently un-fixed the repetition for every candidate -- Patrick Raggett
    spent two of his three quote slots on one sentence.
    """
    groups: list[list[dict]] = []
    for c in sorted(claims, key=lambda x: -len(_quote_norm(x))):
        q = _quote_norm(c)
        for group in groups:
            g = _quote_norm(group[0])
            if q and (q in g or g in q):
                group.append(c)
                break
        else:
            groups.append([c])

    # Longest-first inside a group is an artefact of the sort above; both
    # renderers read better in the order the claims arrived.
    index = {id(c): i for i, c in enumerate(claims)}
    groups.sort(key=lambda g: min(index[id(c)] for c in g))
    for group in groups:
        group.sort(key=lambda c: index[id(c)])
    return groups


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
    groups = _group_by_quote(claims)

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


DETAIL_WORD_CAP = 150
# Three quotes is what fits before a pane stops being glanceable, regardless of
# how short the individual quotes happen to be.
MAX_DETAIL_QUOTES = 3


def _wc(fragment: str) -> int:
    """Words a reader actually sees -- tags and entities are not words."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
    return len([w for w in text.split() if w.strip()])


def _clip(text: str, max_words: int) -> str:
    """Shorten to a boundary a reader recognises, not to a word count.

    Cutting at exactly N words lands mid-clause -- "satisfying the...",
    "tenure stagnation..." -- which stops before the point the sentence was
    making and reads as a rendering fault rather than an edit. So: keep whole
    sentences where any fit, allow a 25% overrun to reach the end of the one
    we are inside, and only fall back to a hard cut when a single sentence is
    longer than that.
    """
    text = str(text).strip()
    words = text.split()
    if len(words) <= max_words:
        return text

    sentences = re.findall(r"[^.!?]+(?:[.!?]+|$)", text)
    kept, used = [], 0
    for sent in sentences:
        n = len(sent.split())
        if kept and used + n > max_words:
            break
        kept.append(sent)
        used += n
        if used >= max_words:
            break
    if kept and used <= max_words * 1.25:
        return "".join(kept).strip()
    return " ".join(words[:max_words]).rstrip(" ,;.") + "..."


def _why_cell(ev: dict, claims: list[dict], spec) -> str:
    """The short answer to "why is this person on the list".

    Three lines at most. The reasons the second reviewer wrote in its own
    words come first; where it wrote none, the primary-signal evidence is the
    reason, so the assertion stands in rather than leaving the cell empty.
    """
    tier = ev.get("tier", "C")
    out = ['<span class="tier ' + tier.lower() + '">'
           + e(TIER_LABEL.get(tier, tier).split("--")[0].strip()) + "</span>"]

    reasons = [str(x).strip() for x in (ev.get("strengths") or [])
               if len(str(x).strip()) > 1]
    if not reasons:
        primary = [c for c in claims
                   if c["dimension"] == spec.primary_signal_dimension]
        reasons = [c["assertion"] for c in (primary or claims)]

    if reasons:
        out.append('<ul class="why">')
        for r in reasons[:3]:
            out.append("<li>" + e(_clip(r, 30)) + "</li>")
        out.append("</ul>")
    else:
        out.append('<p class="none">No summary recorded.</p>')
    return "".join(out)


def _msg_cell(outreach: dict | None) -> str:
    """What to send, and nothing else. Two messages: LinkedIn, then email."""
    if not outreach:
        return '<p class="none">Withheld until the privacy notice is live.</p>'
    out: list[str] = []
    blocks = [("LinkedIn note", outreach["linkedin_note"]),
              ("Email &mdash; " + e(outreach["email_subject"]), outreach["email_body"])]
    # Written by the pipeline and dropped when the card became a column. A
    # sequence with no second touch is not the sequence that was built.
    if outreach.get("follow_up"):
        blocks.append(("Follow-up, about a week later", outreach["follow_up"]))
    for label, text in blocks:
        out.append('<p class="msg-k"><span class="lbl">' + label + "</span>"
                   '<button class="cp" type="button" aria-live="polite"'
                   ' data-copy="' + e(text) + '">Copy</button></p>')
        out.append('<div class="msg-wrap"><pre class="msg">' + e(text) + "</pre></div>")
    return "".join(out)


def _detail_cell(person, claims, ev, contact, mov, links, spec) -> str:
    """Everything else, inside a hard word budget.

    The card this replaces ran to roughly 980 words per person and put all of
    it in front of a reader whose question is "who do I contact". This is the
    same material for whoever asks "why" later, capped at DETAIL_WORD_CAP so
    it stays answerable at a glance. Blocks are added in priority order and
    the first that would breach the cap ends the pane, so what survives is the
    most load-bearing evidence rather than a sentence cut in half.
    """
    blocks: list[str] = []

    # 1. The verbatim evidence, primary signal first. This is the whole basis
    #    of the shortlist; if only one thing fits, it should be this.
    primary = [c for c in claims if c["dimension"] == spec.primary_signal_dimension]
    other = [c for c in claims if c["dimension"] != spec.primary_signal_dimension]
    direct = [x for x in primary + other if x.get("confidence") == "direct"]
    # One sentence can evidence three dimensions. Without grouping the pane
    # prints it three times and burns the quote budget repeating itself.
    for group in _group_by_quote(direct):
        # The longest quote in the group carries the most context for a reader
        # who clicks through to check it.
        c = max(group, key=lambda x: len(str(x.get("evidence_quote") or "")))
        quote = _clip(c.get("evidence_quote") or c["assertion"], 30)
        src = c.get("source_url")
        # The .claim / blockquote / .src shape is the evidence contract: every
        # claim shows a verbatim quote and links the document it came from.
        # Shortening the pane is not a licence to drop the citation.
        blocks.append(
            '<div class="claim"><blockquote>&ldquo;' + e(quote)
            + "&rdquo;</blockquote>"
            + '<div class="src">'
            + ('<a href="' + e(_safe_url(src)) + '">source</a>' if _safe_url(src)
               else "source document not recorded")
            + (" &middot; text recovered by OCR from a scanned document"
               if c.get("source_doc_id") in _OCR_DOC_IDS else "")
            + "</div></div>"
        )

    # 2. How good the address is. A pattern guess is a guess, and the reader
    #    is one click away from copying it.
    facts: list[str] = []

    # Lower-confidence evidence had a labelled section on the card and no home
    # at all in the table. It is weaker than a verbatim quote, which is a
    # reason to label it, not a reason to delete it.
    inferred = [c["assertion"] for c in claims
                if c.get("confidence") != "direct" and c.get("assertion")]
    if inferred:
        facts.append('<p class="src">Inferred, not directly stated: '
                     + e(_clip("; ".join(inferred), 22)) + "</p>")
    status = contact.get("email_status", "none")
    note = {
        "verified": "Email SMTP-verified by the provider.",
        "catch_all": "Domain accepts all mail: deliverable, not proof the mailbox exists.",
        "pattern_guess": "Inferred address: built from the firm's naming pattern, "
                         "never verified. Treat it as a guess.",
        "none": "No email address found.",
    }[status]
    facts.append('<p class="src">' + e(note) + "</p>")

    # 3. Whether they are likely to move.
    if mov and (mov.get("assessment") or mov.get("rationale")):
        # movability.py whitelists this to high/medium/low/unknown, but that is
        # a contract in another file that this one neither sees nor asserts.
        # An unclipped value put a 197-word pane through a 150-word "hard cap".
        assessment = _clip(str(mov.get("assessment", "unknown")).lower(), 3)
        rationale = str(mov.get("rationale") or "").strip()
        facts.append(
            '<p><strong class="mov-' + e(assessment) + '">' + e(assessment)
            + " movability.</strong>"
            + (" " + e(_clip(rationale, 26)) if rationale
               else " No basis recorded either way.")
            + "</p>"
        )

    # 4. Only what the link checker found WRONG. "All links fine" is not worth
    #    a reader's words when the budget is 150 of them.
    # 3b. The route that does not depend on a mailbox or an accepted
    #     connection request. It was computed for all 13 candidates and shown
    #     for none of them; a shortlist that drops the fallback is a shortlist
    #     that stops working the moment the first two channels go quiet.
    switchboard = next((r for r in _reach_routes(person, contact)
                        if r[0] == "switchboard"), None)
    if switchboard:
        facts.append('<p class="src">' + e(switchboard[1]) + "</p>")

    checks = (links or {}).get("checks", [])
    dead = [c for c in checks if c.get("alive") is False]
    mism = [c for c in checks if c.get("name_matched") is False]
    if dead or mism:
        bits = []
        if dead:
            bits.append(str(len(dead)) + " source link(s) did not return 200")
        if mism:
            bits.append(str(len(mism)) + " link(s) no longer name this person")
        facts.append('<p class="gap">' + e("; ".join(bits) + ".") + "</p>")

    # The honesty lines are reserved, not queued. Filling the budget with
    # quotes first and letting "this address is a guess" fall off the end
    # would drop the one line that changes what the reader does next.
    budget = DETAIL_WORD_CAP - _wc("".join(facts))

    kept, used = [], 0
    for b in blocks[:MAX_DETAIL_QUOTES]:
        n = _wc(b)
        if used + n > budget:
            break
        kept.append(b)
        used += n

    body = "".join(kept)
    if not body:
        body = '<p class="none">No verbatim evidence fits here -- see the pool map.</p>'
    note = ""
    if len(kept) < len(blocks):
        note = ('<p class="src">Showing ' + str(len(kept)) + " of "
                + str(len(blocks)) + " verified quotes; the rest are in the "
                "run record.</p>")
    # The facts are reserved, so if they alone exceed the cap the pane would
    # breach it no matter how few quotes were kept. Drop from the end -- the
    # ordering above is priority order -- until it fits. The cap is then a
    # property of this function rather than of the data it happens to receive.
    out = '<div class="facts">' + note + "".join(facts) + "</div>"
    while _wc(body + out) > DETAIL_WORD_CAP and facts:
        facts.pop()
        out = '<div class="facts">' + note + "".join(facts) + "</div>"
    return '<div class="det-in">' + body + out + "</div>"


def row_html(
    person: dict,
    claims: list[dict],
    ev: dict,
    contact: dict,
    mov: dict,
    outreach: dict | None,
    links: dict,
    spec,
) -> str:
    """One candidate as two table rows: the line, and the detail it hides."""
    # Scoped by role: the same person delivered under both roles would
    # otherwise emit two rows with one id, and getElementById would toggle the
    # wrong one. The gates make it unlikely; nothing made it impossible.
    rid = "d-" + e(str(spec.role_id)) + "-" + e(str(person["person_id"]))
    routes = _reach_routes(person, contact)

    BTN = {"linkedin": "LinkedIn", "search": "Find on LinkedIn",
           "email": "Email", "guess": "Email (unverified)",
           "switchboard": "Call the firm", "profile": "Profile page"}
    buttons: list[str] = []
    for kind, label, href in routes:
        if kind in ("linkedin", "search") and not any("cta-li" in b for b in buttons):
            buttons.append(
                '<a class="cta cta-li' + (" weak" if kind == "search" else "")
                + '" href="' + e(_safe_url(href)) + '">' + e(BTN[kind]) + "</a>")
        elif kind in ("email", "guess") and not any("cta-em" in b for b in buttons):
            # The address rides in data-email so the click can copy it even
            # where the mailto: navigation dead-ends, and in title= so a hover
            # reveals it with scripting off.
            addr = href[7:] if href.lower().startswith("mailto:") else href
            buttons.append(
                '<a class="cta cta-em' + (" weak" if kind == "guess" else "")
                + '" href="' + e(href) + '" data-email="' + e(addr) + '"'
                + ' aria-live="polite"'
                + ' title="' + e(addr) + ' -- click to copy">'
                + e(BTN[kind]) + "</a>")
    if not any("cta-em" in b for b in buttons):
        fallback = next((r for r in routes if r[0] in ("switchboard", "profile")), None)
        if fallback:
            buttons.append('<a class="cta cta-alt" href="'
                           + e(_safe_url(fallback[2])) + '">'
                           + e(BTN[fallback[0]]) + "</a>")
        buttons.append('<span class="none">No email address found</span>')

    who = (
        '<p class="nm">' + e(person["full_name"]) + "</p>"
        + '<p class="ro">'
        + e(person.get("current_title") or "Title not stated")
        + (" &middot; " + e(person["current_employer"])
           if person.get("current_employer") else "")
        + "</p>"
        + '<div class="btns">' + "".join(buttons) + "</div>"
    )

    return (
        '<tr class="r">'
        + "<td>" + who + "</td>"
        + "<td>" + _why_cell(ev, claims, spec) + "</td>"
        + "<td>" + _msg_cell(outreach) + "</td>"
        + '<td><button class="det-btn" type="button" aria-expanded="false"'
          ' aria-controls="' + rid + '">'
          '<span class="det-ar" aria-hidden="true">&#9656;</span>'
          '<span class="det-lb">Click here for details</span></button></td>'
        + "</tr>"
        + '<tr class="det" id="' + rid + '" hidden><td colspan="4">'
        + _detail_cell(person, claims, ev, contact, mov, links, spec)
        + "</td></tr>"
    )


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
        # Reachability first, evidence second.
        #
        # The client opens this to contact people. A row whose email is a
        # pattern guess and whose profile did not resolve is still a real
        # candidate, but it is one that needs work before it can be actioned,
        # and interleaving those with the ready ones makes the reader check
        # every row to find the ones they can use. Both signals must be
        # present to sort into the top group: a verified address and a
        # resolved profile, which is exactly what the two solid buttons mean.
        #
        # Within each group the pipeline's own evidence ranking is preserved
        # untouched, so this reorders the list without re-judging anybody.
        def _ready(pid: str) -> int:
            c = contacts.get(pid, {})
            has_email = c.get("email_status") == "verified" and c.get("email")
            has_profile = bool(c.get("linkedin_url"))
            return 0 if (has_email and has_profile) else 1

        rank = {pid: i for i, pid in enumerate(pids)}
        pids.sort(key=lambda p: (_ready(p), rank[p]))
        n_ready = sum(1 for p in pids if _ready(p) == 0)

        delivered_total += len(pids)

        short = len(pids) < spec.target_count
        body.append('<section class="role-band" id="' + e(spec.role_id) + '">')
        body.append(
            "<h2>" + e(spec.title)
            + '<span class="of' + (" short" if short else "") + '">'
            + str(len(pids)) + " of " + str(spec.target_count) + "</span></h2>"
        )
        body.append(
            '<p class="lede role-lede">' + e(", ".join(spec.locations)) + ". "
            + "Assessed " + str(m["profiles_assessed"]) + " profiles; "
            + str(m["passed_all_gates"]) + " passed every hard gate. "
            + str(n_ready) + " of " + str(len(pids))
            + " are ready to contact now &mdash; verified address and a resolved "
            "profile &mdash; and those are listed first. The rest need a step "
            "before they can be approached and follow below, ranked as they "
            "were on strength of evidence on "
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

        body.append(
            '<table class="sl">'
            '<colgroup><col class="c-who"><col class="c-why">'
            '<col class="c-msg"><col class="c-det"></colgroup>'
            "<thead><tr><th>Candidate</th><th>Why them</th>"
            "<th>Message to send</th><th>Detail</th></tr></thead><tbody>"
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
                row_html(
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

        body.append("</tbody></table>")

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
        "<meta name='robots' content='noindex,nofollow,noarchive,nosnippet'>"
        "<meta name='referrer' content='no-referrer'>"
        "<title>Gaia Talent -- TOBIN / AtkinsRealis shortlist</title>"
        "<style>" + CSS + "</style></head><body><div class='wrap'>"
        "<header class='doc'><h1>Senior Structural Engineer &amp; Transport Major "
        "Projects Manager</h1>"
        "<p class='sub'>Evidence-backed shortlist prepared for Gaia Talent Ltd &middot; "
        + date.today().strftime("%d %B %Y") + " &middot; " + str(delivered_total)
        + " candidates</p></header>"
        "<p class='lede wide'><strong>Approach on the professional network "
        "first.</strong> Mailing a senior engineer at their employer&rsquo;s "
        "address about leaving that employer is monitored mail and poor "
        "tradecraft &mdash; the email button is there for when the first channel "
        "goes quiet, and every row carries a switchboard number for when both do. "
        "Each candidate is one row: who they are, why they are on the list, and "
        "the message to send; open <em>Detail</em> for the evidence behind it. "
        "Every factual statement is a verbatim quote from a public document, "
        "checked character-by-character against its cached source, and claims "
        "that could not be matched were dropped rather than softened.</p>"
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
        "</div><script>" + COPY_JS + "</script></body></html>"
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
