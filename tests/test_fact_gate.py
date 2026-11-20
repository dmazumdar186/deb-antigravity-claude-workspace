"""
test_fact_gate.py
description: Tests for execution/gtm_icp_filters/fact_gate.py. Offline tests use a fake fetcher and synthetic companies
             that reproduce each known failure mode of "homepage doesn't mention X" claims (registered mark inside the
             name, agency acronym, product-family name, hidden menu item, linked page, sitemap slug) plus the
             public-record checks. The live regression test re-runs the gate over a labelled claims CSV kept outside
             this public repo (FACT_GATE_REGRESSION_CSV) and asserts every expected verdict.
inputs:  env FACT_GATE_REGRESSION_CSV (optional; live test skipped without it)
outputs: pytest results; live test writes .tmp/fact_gate/regression_test/
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from execution.gtm_icp_filters import fact_gate as fg

ROOT = Path(__file__).resolve().parents[1]


class FakeFetcher(fg.Fetcher):
    """Serves canned responses; anything not canned is unreachable."""

    def __init__(self, gets=None, posts=None, renders=None):
        self.gets, self.posts, self.renders = gets or {}, posts or {}, renders or {}
        self.refresh = self.offline = False

    def get(self, url, ua=fg.UA, timeout=25, tries=3):
        for k, v in self.gets.items():
            if url == k or url.startswith(k.rstrip("*")) and k.endswith("*"):
                return (
                    {"status": 200, "final_url": url, **v}
                    if "status" not in v
                    else {"final_url": url, **v}
                )
        return {"status": 0, "error": "unreachable", "text": ""}

    def post_json(self, url, body, tries=4):
        return self.posts.get(url, {"error": "unreachable"})

    def render(self, urls):
        return {
            u: self.renders.get(u, {"url": u, "error": "unreachable"}) for u in urls
        }


FILLER = " Lorem ipsum company news about surgeons and patients. " * 6


def home(text="", all_text=None, links=(), imgs=(), viewport=True, html=""):
    return {
        "url": "https://www.acme.example/",
        "final_url": "https://www.acme.example/",
        "status": 200,
        "text": text + FILLER,
        "all_text": (all_text if all_text is not None else text) + FILLER,
        "links": list(links),
        "imgs": list(imgs),
        "viewport_meta": viewport,
        "html": html or "<html></html>",
    }


def renders(h):
    return {"https://acme.example/": h}


def nm(product="", agency="", company="Acme Spine"):
    return {
        "claim_type": "site_not_mention",
        "company": company,
        "domain": "acme.example",
        "product": product,
        "agency": agency,
        "claim_text": "the acme.example homepage does not mention it",
    }


# ------------------------------------------------------------ site_not_mention: the four failure modes
def test_catches_registered_mark_inside_name():  # Brand(R)-C style
    f = FakeFetcher(
        renders=renders(
            home("The Zentrix®-C Procedure | A True MIS Stand-Alone Cervical Fusion")
        )
    )
    v = fg.gate_claim(nm("Zentrix-C Cervical Interbody Fusion System"), f)
    assert v["verdict"] == "FALSE" and "Zentrix" in v["evidence_quote"]


def test_catches_agency_acronym():  # "USCG MATOCs" for a U.S. Coast Guard award
    f = FakeFetcher(
        renders=renders(home("Our clients include the VA, US Navy, and USCG MATOCs."))
    )
    v = fg.gate_claim(nm(agency="U.S. Coast Guard", company="Acme Builders"), f)
    assert v["verdict"] == "FALSE" and "USCG" in v["evidence_quote"]


def test_catches_product_family_name():  # "Brand(R) Hip Solutions" for "Brand Acetabular Liners"
    f = FakeFetcher(
        renders=renders(
            home("Explore | Libra(R) Hip Solutions | Featuring a comprehensive range")
        )
    )
    v = fg.gate_claim(nm("Libra Acetabular Liners (Acetabular Liner)"), f)
    assert v["verdict"] == "FALSE"


def test_catches_hidden_menu_item():  # dropdown text not in innerText, only textContent
    h = home(
        "Welcome to Acme",
        all_text="Welcome to Acme TILINK-L | Vantix | ViMax",
        links=[
            {
                "href": "https://www.acme.example/vantix/",
                "text": "Vantix",
                "region": "navfoot",
            }
        ],
    )
    v = fg.gate_claim(
        nm("Vantix Lumbar Decompression Kit"), FakeFetcher(renders=renders(h))
    )
    assert v["verdict"] == "FALSE"


def test_catches_linked_page_only():
    h = home(
        "Welcome to Acme. Products",
        links=[
            {
                "href": "https://www.acme.example/implants",
                "text": "Implants",
                "region": "navfoot",
            }
        ],
    )
    gets = {
        "https://www.acme.example/implants": {
            "text": "<html><body><h1>Our Quorvex cage</h1></body></html>"
        }
    }
    v = fg.gate_claim(
        nm("Quorvex Interbody Cage"), FakeFetcher(gets=gets, renders=renders(h))
    )
    assert v["verdict"] == "FALSE" and v["evidence_url"].endswith("/implants")


def test_catches_sitemap_slug():
    h = home("Welcome to Acme.")
    gets = {
        "https://www.acme.example/sitemap.xml": {
            "text": "<urlset><loc>https://www.acme.example/products/orbix-plate/</loc></urlset>"
        }
    }
    v = fg.gate_claim(
        nm("Orbix Plate System"), FakeFetcher(gets=gets, renders=renders(h))
    )
    assert v["verdict"] == "FALSE" and "orbix" in v["evidence_url"]


def test_passes_true_absence_with_search_evidence():
    h = home(
        "Welcome to Acme. We build cervical fusion systems.",
        links=[
            {
                "href": "https://www.acme.example/about",
                "text": "About",
                "region": "navfoot",
            }
        ],
    )
    gets = {
        "https://www.acme.example/about": {"text": "<p>About us: founded 1999.</p>"}
    }
    v = fg.gate_claim(
        nm("Zentrix-C Cervical Interbody Fusion System"),
        FakeFetcher(gets=gets, renders=renders(h)),
    )
    assert (
        v["verdict"] == "PASS"
        and "0 hits" in v["evidence_quote"]
        and "searched 2 pages" in v["evidence_quote"]
    )


def test_generic_words_do_not_count_as_mention():
    v = fg.gate_claim(
        nm("Zentrix Cervical Plate"),
        FakeFetcher(renders=renders(home("Cervical plate systems."))),
    )
    assert v["verdict"] == "PASS"


def test_unreachable_site_is_unverifiable():
    v = fg.gate_claim(nm("Zentrix Plate"), FakeFetcher())
    assert v["verdict"] == "UNVERIFIABLE"


def test_bot_wall_is_unverifiable():
    h = home("Just a moment... verify you are human")
    h["text"], h["all_text"] = "Just a moment... verify you are human" + " x" * 120, ""
    assert (
        fg.gate_claim(nm("Zentrix Plate"), FakeFetcher(renders=renders(h)))["verdict"]
        == "UNVERIFIABLE"
    )


def test_only_generic_tokens_is_unsupported():
    v = fg.gate_claim(
        nm("Cervical Plate System"), FakeFetcher(renders=renders(home("x")))
    )
    assert v["verdict"] == "UNSUPPORTED"


def test_short_acronym_case_sensitive():  # "gsap" CSS class must not count as GSA
    f = FakeFetcher(renders=renders(home("we use gsap animations and bagsa")))
    assert (
        fg.gate_claim(nm(agency="GSA Public Buildings Service", company="Acme"), f)[
            "verdict"
        ]
        == "PASS"
    )


# ------------------------------------------------------------ openFDA
def fda_get(rec):
    return {
        f"{fg.FDA_API}?search=k_number:K261111": {
            "text": json.dumps({"results": [rec]})
        }
    }


REC = {
    "k_number": "K261111",
    "applicant": "Acme Spine, Inc.",
    "device_name": "Zentrix-C Cervical Interbody Fusion System",
    "decision_date": "2026-08-26",
}


def fda_claim(**k):
    c = {
        "claim_type": "fda_clearance",
        "company": "Acme Spine",
        "k_number": "K261111",
        "product": "Zentrix-C Cervical Interbody Fusion System",
        "date": "2026-08-26",
        "claim_text": "FDA 510(k) clearance K261111 on August 26 for the Zentrix-C",
    }
    c.update(k)
    return c


def test_fda_pass():
    v = fg.gate_claim(fda_claim(), FakeFetcher(gets=fda_get(REC)))
    assert v["verdict"] == "PASS" and "Acme Spine, Inc." in v["evidence_quote"]


def test_fda_wrong_date():
    v = fg.gate_claim(
        fda_claim(date="2026-08-27", claim_text="x"), FakeFetcher(gets=fda_get(REC))
    )
    assert v["verdict"] == "FALSE" and "decision_date" in v["reason"]


def test_fda_wrong_company():
    v = fg.gate_claim(
        fda_claim(company="Globex Medical"), FakeFetcher(gets=fda_get(REC))
    )
    assert v["verdict"] == "FALSE" and "applicant" in v["reason"]


def test_fda_wrong_product():
    v = fg.gate_claim(fda_claim(product="Orbix Plate"), FakeFetcher(gets=fda_get(REC)))
    assert v["verdict"] == "FALSE"


def test_fda_not_found_and_unreachable():
    f = FakeFetcher(
        gets={f"{fg.FDA_API}?search=k_number:K261111": {"status": 404, "text": ""}}
    )
    assert fg.gate_claim(fda_claim(), f)["verdict"] == "FALSE"
    assert fg.gate_claim(fda_claim(), FakeFetcher())["verdict"] == "UNVERIFIABLE"


def test_claim_text_contradicting_fields_is_false():
    v = fg.gate_claim(
        fda_claim(claim_text="FDA clearance on August 25"),
        FakeFetcher(gets=fda_get(REC)),
    )
    assert v["verdict"] == "FALSE" and "claim_text date" in v["reason"]


# ------------------------------------------------------------ USAspending
def award_fetcher(signed="2026-09-24", sub="U.S. Coast Guard"):
    search = {
        "results": [
            {
                "Award ID": "70Z0TEST0011",
                "Recipient Name": "OTHER BUILDERS LLC",
                "generated_internal_id": "G1",
            },
            {
                "Award ID": "70Z0TEST0011",
                "Recipient Name": "ACME BUILDERS CORPORATION",
                "generated_internal_id": "G2",
            },
        ],
        "page_metadata": {"hasNext": False},
    }
    det = {
        "date_signed": signed,
        "recipient": {"recipient_name": "ACME BUILDERS CORPORATION"},
        "awarding_agency": {
            "toptier_agency": {
                "name": "Department of Homeland Security",
                "abbreviation": "DHS",
            },
            "subtier_agency": {"name": sub, "abbreviation": "USCG"},
            "office_agency_name": "CEU OAKLAND(00088)",
        },
    }
    return FakeFetcher(
        posts={fg.AWARD_SEARCH: search},
        gets={fg.AWARD_API.format("G2"): {"text": json.dumps(det)}},
    )


def award_claim(**k):
    c = {
        "claim_type": "federal_award",
        "company": "Acme Builders",
        "award_id": "70Z0TEST0011",
        "agency": "U.S. Coast Guard",
        "date": "2026-09-24",
        "claim_text": "awarded on September 24",
    }
    c.update(k)
    return c


def test_award_shared_piid_picks_matching_recipient():
    v = fg.gate_claim(award_claim(), award_fetcher())
    assert v["verdict"] == "PASS" and "ACME BUILDERS" in v["evidence_quote"]


def test_award_wrong_date_agency_recipient():
    assert (
        fg.gate_claim(award_claim(), award_fetcher(signed="2026-09-23"))["verdict"]
        == "FALSE"
    )
    assert (
        fg.gate_claim(award_claim(agency="NASA"), award_fetcher())["verdict"] == "FALSE"
    )
    assert (
        fg.gate_claim(award_claim(company="Initech Paving"), award_fetcher())["verdict"]
        == "FALSE"
    )


def test_award_unreachable():
    assert fg.gate_claim(award_claim(), FakeFetcher())["verdict"] == "UNVERIFIABLE"


# ------------------------------------------------------------ copyright / viewport
def cr(year):
    return {
        "claim_type": "site_copyright",
        "domain": "acme.example",
        "year": str(year),
        "claim_text": f"reads (c) {year}",
    }


def test_copyright_range_uses_newest_year():
    f = FakeFetcher(
        renders=renders(home("Footer © 2019 - 2022 Acme. All rights reserved."))
    )
    assert fg.gate_claim(cr(2022), f)["verdict"] == "PASS"
    assert fg.gate_claim(cr(2019), f)["verdict"] == "FALSE"


def test_copyright_js_current_year_is_false():
    f = FakeFetcher(renders=renders(home("Copyright 2026 Acme")))
    assert fg.gate_claim(cr(2022), f)["verdict"] == "FALSE"


def test_viewport():
    vp = {
        "claim_type": "site_viewport_missing",
        "domain": "acme.example",
        "claim_text": "no viewport",
    }
    assert (
        fg.gate_claim(vp, FakeFetcher(renders=renders(home("x"))))["verdict"] == "FALSE"
    )
    raw = {"https://www.acme.example/": {"text": "<html><head></head></html>"}}
    assert (
        fg.gate_claim(
            vp, FakeFetcher(gets=raw, renders=renders(home("x", viewport=False)))
        )["verdict"]
        == "PASS"
    )
    raw2 = {
        "https://www.acme.example/": {
            "text": '<meta name="viewport" content="width=device-width">'
        }
    }
    assert (
        fg.gate_claim(
            vp, FakeFetcher(gets=raw2, renders=renders(home("x", viewport=False)))
        )["verdict"]
        == "FALSE"
    )


# ------------------------------------------------------------ driver
def test_unknown_type_fails_closed():
    assert (
        fg.gate_claim({"claim_type": "company_description"}, FakeFetcher())["verdict"]
        == "UNSUPPORTED"
    )


def test_rows_render_only_from_passed_trigger(tmp_path):
    claims = [
        dict(fda_claim(), claim_id="1", row_id="r1", domain="acme.example"),
        dict(
            nm("Zentrix-C Cervical Interbody Fusion System"), claim_id="2", row_id="r1"
        ),
        dict(award_claim(), claim_id="3", row_id="r2", domain="b.example"),
    ]
    h = home("The Zentrix®-C Procedure")
    f = FakeFetcher(gets=fda_get(REC), renders=renders(h))
    s = fg.run(claims, tmp_path, f, quiet=True)
    rows = list(csv.DictReader((tmp_path / "rows.csv").open(encoding="utf-8")))
    assert s["verdicts"] == {"PASS": 1, "FALSE": 1, "UNVERIFIABLE": 1}
    assert [r["row_id"] for r in rows] == ["r1"] and rows[0]["site_facts"] == ""
    rej = list(csv.DictReader((tmp_path / "reject.csv").open(encoding="utf-8")))
    assert all(r["reason"] for r in rej) and any(r["evidence_quote"] for r in rej)


def test_rerun_is_idempotent(tmp_path):
    claims = [dict(fda_claim(), claim_id="1", row_id="r1", domain="acme.example")]
    f = FakeFetcher(gets=fda_get(REC))
    fg.run(claims, tmp_path, f, quiet=True)
    a = (tmp_path / "pass.csv").read_bytes()
    fg.run(claims, tmp_path, f, quiet=True)
    assert (tmp_path / "pass.csv").read_bytes() == a


def test_max_pages_bounds():
    with pytest.raises(SystemExit):
        fg.main(["--claims", "x.csv", "--max-pages", str(fg.MAX_PAGES_CEILING + 1)])


# ------------------------------------------------------------ live regression (labelled CSV outside this repo)
REG = os.environ.get("FACT_GATE_REGRESSION_CSV", "")


@pytest.mark.skipif(
    not REG or not Path(REG).exists(), reason="FACT_GATE_REGRESSION_CSV not set"
)
def test_live_regression_known_false_caught_and_records_pass():
    claims = list(csv.DictReader(open(REG, newline="", encoding="utf-8")))
    out = ROOT / ".tmp/fact_gate/regression_test"
    fg.run(claims, out, fg.Fetcher(), quiet=True)
    got = {
        r["claim_id"]: r
        for r in csv.DictReader((out / "pass.csv").open(encoding="utf-8"))
    }
    got.update(
        {
            r["claim_id"]: r
            for r in csv.DictReader((out / "reject.csv").open(encoding="utf-8"))
        }
    )
    expected = [c for c in claims if c.get("expected")]
    assert sum(c["expected"] == "FALSE" for c in expected) >= 4
    bad = [
        (
            c["claim_id"],
            c["expected"],
            got[c["claim_id"]].get("verdict", "PASS"),
            got[c["claim_id"]].get("reason"),
        )
        for c in expected
        if got[c["claim_id"]].get("verdict", "PASS") != c["expected"]
    ]
    assert not bad, bad


def test_de_novo_called_510k_is_false():
    c = fda_claim(k_number="DEN261111", claim_text="FDA 510(k) clearance DEN261111 on August 26")
    assert fg.gate_claim(c, FakeFetcher())["verdict"] == "FALSE"
