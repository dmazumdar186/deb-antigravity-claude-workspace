"""
Output-acceptance gate for the delivered artifact.

Per ~/.claude/rules/output-acceptance-gate.md: assert on the OUTPUT a person
reads, not on whether the pipeline ran. Every check here opens
`deliverables/gaia_2026-08-20/` and asks the question a managing director
would ask in the first minute -- is anyone here from the client's own firm, do
the links go anywhere, does the employer column say a real company, and does
the document admit what it did not find.

Hard-fails with a non-zero exit. Run it before anything is sent:

    py -m gtm_client_workflows.gaia_sourcing.tests.acceptance_gaia
"""

from __future__ import annotations

import csv
import io
import json
import re
import html as html_mod
import sys
from pathlib import Path

from ..core.config import PKG_ROOT, PRIVACY_NOTICE_URL, WORKSPACE_ROOT
from ..roles import ROLE1, ROLE2, is_client_side

OUT = WORKSPACE_ROOT / "deliverables" / "gaia_2026-08-20"
RUN = PKG_ROOT / "run" / "gaia-2026-08-20"

FAILURES: list[str] = []
CHECKS = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print("  PASS  " + name)
        return
    FAILURES.append(name + ((" -- " + detail) if detail else ""))
    print("  FAIL  " + name + ((" -- " + detail) if detail else ""))


def main() -> int:
    html = (OUT / "dossier.html").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(
        (OUT / "candidates.csv").read_text(encoding="utf-8-sig"))))
    text = re.sub(r"<[^>]+>", " ", html)

    print("\n-- Evidence contract (I1/I2) ------------------------------------")
    claims = re.findall(r'<div class="claim">.*?</div>\s*</div>', html, re.S)
    check(bool(claims), "the dossier contains evidence claims", str(len(claims)))
    check(all("<blockquote>" in c for c in claims),
          "every claim shows a verbatim quote")
    check(all('class="src"' in c for c in claims),
          "every claim links the document its quote came from")

    print("\n-- Who is on the list -------------------------------------------")
    employers = [r["current_employer"].strip() for r in rows]
    check(all(e for e in employers), "every candidate has a named employer",
          str([r["full_name"] for r in rows if not r["current_employer"].strip()]))
    # A place or an org-chart position is not an employer. This shipped once.
    bad = [e for e in employers if e.lower() in {
        "dublin", "cork", "ireland", "environment", "metrolink",
        "ireland and the netherlands", "dublin office"}]
    check(not bad, "no place or division in the employer column", str(bad))

    off_limits = [r["full_name"] for r in rows
                  if any(o in r["current_employer"].lower()
                         for o in ("tobin", "atkinsrealis", "atkins realis"))]
    check(not off_limits, "nobody works for the client or its parent",
          str(off_limits))

    side = [r["full_name"] for r in rows if is_client_side(r["current_employer"])]
    check(not side, "no client-side employee counted in the shortlist (SPEC 2.3)",
          str(side))

    print("\n-- Everyone is reachable -----------------------------------------")
    # Six of thirteen cards on the first delivered run were a dead end, and two
    # of those were people the contact stage had never even seen because the
    # renderer recomputed the shortlist and broke ties differently.
    contacts = json.loads((RUN / "contact.json").read_text(encoding="utf-8"))
    delivery = json.loads((RUN / "delivery.json").read_text(encoding="utf-8"))
    shipped = [p for v in delivery.values() for p in v]
    check(len(shipped) == len(rows),
          "the rendered list is the list the pipeline delivered",
          str(len(shipped)) + " vs " + str(len(rows)))
    unenriched = [p for p in shipped if p not in contacts]
    check(not unenriched, "every delivered candidate went through enrichment",
          str(unenriched))
    # Each row must carry at least one clickable way to reach the person.
    # The unit was <article class="card"> until the layout became a four-column
    # table; the property being asserted did not change with it.
    cards = re.split(r'(?=<tr class="r">)', html)[1:]
    # Matches the class PREFIX, because the buttons carry modifiers
    # (cta cta-li / cta cta-em weak). An exact-string check here failed the
    # moment a second button was added, which is the check being brittle
    # rather than the page being wrong.
    routeless = [c for c in cards if not re.search(r'class="cta[ "]', c)]
    check(not routeless, "every card offers a first contact route",
          str(len(routeless)) + " card(s) without one")
    # And the button has to go somewhere.
    hrefless = [c for c in cards
                if not re.search(r'<a class="cta[^"]*" href="[^"]+"', c)]
    check(not hrefless, "every first-contact button is a real link",
          str(len(hrefless)) + " card(s) with a dead button")
    # "Is a real link" was never enough for the email button. Its href was a
    # well-formed mailto: the whole time and the click still did nothing,
    # because the protocol dies wherever no mail client is registered to it.
    # So the clipboard fallback is load-bearing, and these assert it shipped:
    # every email button carries the address it would copy, and the handler
    # that copies it is present in the document.
    em = re.findall(r'<a class="cta cta-em[^>]*>', html)
    silent = [b for b in em if 'data-email="' not in b]
    check(not silent, "every email button carries a copyable address",
          str(len(silent)) + " of " + str(len(em)) + " without one")
    # Kevin wants the list; whoever asks "why" later gets the detail. That
    # only holds while the detail stays glanceable -- the card this replaced
    # ran to ~980 words per person, which is what made the artifact unusable.
    panes = re.findall(r'<div class="det-in">.*?</div>\s*</td></tr>', html, re.S)
    check(len(panes) == len(cards),
          "every candidate row has a detail pane",
          str(len(panes)) + " panes for " + str(len(cards)) + " rows")
    def _visible_words(fragment):
        t = re.sub(r"<[^>]+>", " ", fragment)
        t = re.sub(r"&[a-zA-Z#0-9]+;", " ", t)
        return len([w for w in t.split() if w.strip()])
    over = [n for n in (_visible_words(p) for p in panes) if n > 150]
    check(not over, "no detail pane exceeds 150 words",
          str(len(over)) + " over cap, longest " + str(max(over) if over else 0))
    # The row is the product. If it stops being scannable the redesign failed.
    # Reachability ordering. The client opens this to contact people, so the
    # rows they can act on today come first; interleaving them with rows that
    # need a step makes the reader check every one to find the usable ones.
    for band in re.split(r"<h2>", html)[1:]:
        band_rows = re.split(r'(?=<tr class="r">)', band)[1:]
        if not band_rows:
            continue
        needs = ["cta-em weak" in r or "No email address found" in r
                 or "cta-li weak" in r for r in band_rows]
        # Once the first not-ready row appears, every row after it must also
        # be not-ready -- i.e. the flags are sorted, never interleaved.
        first_gap = needs.index(True) if True in needs else len(needs)
        check(all(needs[first_gap:]),
              "contactable candidates are listed before the rest",
              "row " + str(needs.index(False, first_gap) + 1 if False in needs[first_gap:] else 0)
              + " is contactable but sits below one that is not")

    check(html.count('class="det-btn"') == len(cards),
          "every row offers the details toggle",
          str(html.count('class="det-btn"')) + " for " + str(len(cards)) + " rows")

    check("a.cta-em" in html and "clipboard" in html,
          "the email clipboard fallback shipped with the page",
          "no handler found -- a mailto-only button is a silent no-op "
          "wherever the protocol is unhandled")

    # The deployed copy must be the generated one. A hand-copied site/ is one
    # forgotten step away from serving last week's shortlist while the local
    # file looks correct -- see ~/.claude/rules/live-artifact-acceptance.md,
    # where exactly that went unnoticed for thirteen days.
    site = OUT / "site" / "index.html"
    check(site.exists(), "the deployed page exists", str(site))
    if site.exists():
        check(site.read_text(encoding="utf-8") == html,
              "the deployed page is the generated page, not a stale copy",
              "site/index.html differs from dossier.html")
    for extra in ("robots.txt", "_headers"):
        check((OUT / "site" / extra).exists(),
              "the deployed site ships " + extra, "missing")
    # This page names real people and their employers. Crawlers get told twice.
    # The password gate must ship INSIDE the asset directory. functions/ is
    # resolved by wrangler against the working directory, not against the
    # deployed folder, so a middleware placed in site/functions/ uploads as a
    # dead static file and the site serves unprotected while every local check
    # still passes. That happened once; _worker.js is the shape that ships.
    worker = OUT / "site" / "_worker.js"
    check(worker.exists(), "the deployed site ships its password gate",
          "no _worker.js -- the page would be public")
    if worker.exists():
        src = worker.read_text(encoding="utf-8")
        check("SITE_PASSWORD" in src and "env.ASSETS" in src,
              "the gate reads the secret and serves assets only after it",
              "gate does not reference SITE_PASSWORD / env.ASSETS")
        # An unconfigured deployment must not be an open one.
        check("if (!expected)" in src and "503" in src,
              "the gate fails closed when the secret is missing",
              "missing secret would fall through to serving the page")
        check("constantTimeEqual" in src,
              "the password comparison is constant-time",
              "=== on a secret leaks its prefix through timing")
    check(not (OUT / "site" / "functions").exists(),
          "no functions/ dir inside the asset folder",
          "wrangler resolves functions/ against the CWD; one there never runs")

    check("noindex" in html, "the page asks not to be indexed",
          "no robots meta -- 13 named individuals would be indexable")

    print("\n-- Counts against the brief -------------------------------------")
    r1 = [r for r in rows if r["role"] == ROLE1.role_id]
    r2 = [r for r in rows if r["role"] == ROLE2.role_id]
    check(len(r1) <= ROLE1.target_count,
          "Role 1 does not exceed the brief's " + str(ROLE1.target_count),
          str(len(r1)))
    check(len(r2) <= ROLE2.target_count,
          "Role 2 does not exceed the brief's " + str(ROLE2.target_count),
          str(len(r2)))
    # A SHORTFALL is allowed. Concealing one is not.
    if len(r1) < ROLE1.target_count or len(r2) < ROLE2.target_count:
        check("short" in text.lower() or "shortfall" in text.lower(),
              "a shortfall against the brief is stated on the artifact")

    print("\n-- Presentation --------------------------------------------------")
    check("�" not in html, "no replacement characters on any card",
          str(html.count("�")))
    # An internal field name in client-facing prose is the single thing most
    # likely to make a reader think the document was assembled and never read.
    # One reached a card: "aligning with the primary technical signal of
    # statutory_process". A model that can see the pipeline's dimension keys
    # will occasionally quote one, so this asserts none survive to the page.
    visible = re.sub(r"<(script|style)[^>]*>.*?</>", " ", html, flags=re.S)
    visible = html_mod.unescape(re.sub(r"<[^>]+>", " ", visible))
    idents = sorted(set(re.findall(r"[a-z]+(?:_[a-z]+)+", visible)))
    check(not idents, "no internal field names in client-facing prose",
          "leaked: " + ", ".join(idents))
    # A citation that navigates away costs the reader their place in the list.
    srcs = re.findall(r"<a href=\"[^\"]+\"[^>]*>source</a>", html)
    bad = [a for a in srcs if 'target="_blank"' not in a
           or "noopener" not in a]
    check(not bad, "source citations open in a new tab",
          str(len(bad)) + " of " + str(len(srcs)) + " would hijack the tab")

    external = re.findall(r'<(?:script|link|img)[^>]+(?:src|href)="(https?://[^"]+)"',
                          html)
    check(not external, "no external assets -- opens offline and on a train",
          str(external[:3]))

    print("\n-- Nothing shattered into characters -----------------------------")
    # Two delivered cards rendered their open-questions section as ONE BULLET
    # PER CHARACTER -- 1651 and 1885 of them -- because a model returned the
    # field as a JSON-encoded string and a string is iterable. A list item one
    # character wide is never real content.
    bullets = [re.sub(r"<[^>]+>", "", b).strip()
               for b in re.findall(r"<li[^>]*>(.*?)</li>", html, re.S)]
    singles = [b for b in bullets if len(b) == 1]
    check(not singles, "no single-character bullet anywhere on the page",
          str(len(singles)) + " found")
    short = [b for b in bullets if 0 < len(b) < 3]
    check(not short, "every bullet is long enough to be a sentence",
          str(short[:5]))

    print("\n-- Sources a reader might click ----------------------------------")
    blocked = ("prospeo.io", "rocketreach", "zoominfo", "signalhire",
               "apollo.io", "lusha", "contactout", "leadiq")
    hits = [b for b in blocked if b in html]
    check(not hits, "no lead-database page cited as evidence", str(hits))

    print("\n-- Provenance and legal ------------------------------------------")
    ocr_ids = set()
    docs = RUN / "docs.jsonl"
    if docs.exists():
        for line in docs.read_text(encoding="utf-8").splitlines():
            if '"ocr"' not in line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("text_source") == "ocr":
                ocr_ids.add(rec["doc_id"])
    if ocr_ids:
        check("recovered by OCR" in html,
              "OCR-sourced evidence declares itself on the card")

    if "Outreach drafts withheld" not in html:
        check(PRIVACY_NOTICE_URL in html,
              "outreach cites the privacy notice URL")
        check("reply with the word STOP" in text,
              "every outreach draft carries the opt-out line")

    print("\n-- Pool map honesty ----------------------------------------------")
    for name, spec in (("pool_map_role1.md", ROLE1), ("pool_map_role2.md", ROLE2)):
        pm = (OUT / name).read_text(encoding="utf-8")
        check("assessed" in pm.lower() or "profiles" in pm.lower(),
              name + " states the denominator, not just the delivered count")

    print("\n" + "=" * 66)
    if FAILURES:
        print("ACCEPTANCE FAILED -- " + str(len(FAILURES)) + " of "
              + str(CHECKS) + " checks")
        for f in FAILURES:
            print("   * " + f)
        return 1
    print("ACCEPTANCE PASSED -- " + str(CHECKS) + " checks against the artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
