"""
The four source plugins -- where a person's identity is decided.

Every one of these modules turns a filename, a URL slug or a page of text into
a claim about WHO someone is, before any LLM sees them. Get it wrong and the
pipeline does not fail; it confidently attributes a real quote to a person who
does not exist. Two such bugs already shipped into a run:

  - "No.02 - TII - Witness Statement of Aidan Foley.pdf" parsed as a candidate
    named "Witness Statement";
  - a 159k-character brief of evidence with its appendices bound in was
    dropped by a size cap meant to catch 800k hearing bundles -- and that
    person was the only Tier A candidate the transport role had.

Both classes are pinned below. Nothing here touches the network.
"""

from __future__ import annotations

import json

import pytest

from gtm_client_workflows.gaia_sourcing.sources import (
    acp,
    company_bios,
    oral_hearing_web,
    technical_evidence,
)


# ===========================================================================
# acp.py -- reading a person out of a filename
# ===========================================================================


@pytest.mark.parametrize("filename,expected", [
    ("No.02 - TII - Witness Statement of Aidan Foley.pdf", "Aidan Foley"),
    ("Brief of Evidence of Susie Coyle.pdf", "Susie Coyle"),
    ("Statement of Evidence of Mary Kate O'Brien.pdf", "Mary Kate O'Brien"),
    # Leading-name shape, no "of".
    ("Ruadhan MacEoin - Witness Statement.pdf", "Ruadhan MacEoin"),
    # A trailing date must not be read as a name part.
    ("No.11 - IE - Witness Statement - Gerry Healy - 25.9.22.pdf", "Gerry Healy"),
])
def test_a_person_is_read_out_of_the_filename(filename, expected):
    assert acp._person_from_filename(filename) == expected


@pytest.mark.parametrize("filename", [
    # The document type is not a person. Unguarded, this produced a candidate
    # called "Witness Statement".
    "Witness Statement.pdf",
    "Brief of Evidence.pdf",
    "No.09 - TII - Oral Hearing Agenda.pdf",
    # Capitalised phrases that match a Firstname-Lastname shape but are titles.
    "No.14 - TII - Buildings Desk Study.pdf",
    "Documents Received.pdf",
    "No.03 - Railway Order.pdf",
])
def test_a_document_title_is_never_returned_as_a_person(filename):
    assert acp._person_from_filename(filename) is None


@pytest.mark.parametrize("text,expected", [
    ("Aidan Foley", True),
    ("Mary Kate O'Brien", True),
    ("Ruadhan MacEoin", True),
    ("Seán Ó Ríordáin", True),          # fadas must survive
    ("Witness Statement", False),
    ("Buildings Desk Study", False),
    ("Dublin City Council", False),     # organisation, not person
    ("Foley", False),                   # one word is not a name
])
def test_name_shape_recognition(text, expected):
    assert acp._looks_like_name(text) is expected


def test_the_submitting_party_is_read_separately_from_the_witness():
    """The party and the witness are different people, and conflating them
    filed consultancy engineers as client-side."""
    name = "No.02 - TII - Witness Statement of Aidan Foley.pdf"

    assert acp._party_from_filename(name) == "TII"
    assert acp._person_from_filename(name) == "Aidan Foley"


@pytest.mark.parametrize("filename,expected", [
    ("Witness Statement of Aidan Foley.pdf", True),
    ("Brief of Evidence of S Coyle.pdf", True),
    ("Witness Statement of Aidan Foley.docx", False),   # not a PDF
    ("Oral Hearing Agenda.pdf", False),                 # process, not person
    ("Attendance Sheet.pdf", False),
    ("Schedule of Errata.pdf", False),
    ("EIAR Chapter 12 Noise.pdf", False),               # no witness hint
])
def test_person_document_prefilter(filename, expected):
    assert acp._is_person_document(filename) is expected


# ---------------------------------------------------------------------------
# The text-level evidence gate -- filenames are an unreliable prefilter
# ---------------------------------------------------------------------------

QUALIFICATIONS = (
    "My name is Aidan Foley. I am a Chartered Engineer and I have over 26 "
    "years post graduate experience. I graduated from University College "
    "Cork with a BEng in Civil Engineering. "
)


def test_two_independent_first_person_signals_admit_a_statement():
    assert acp.looks_like_evidence_document(QUALIFICATIONS + "x" * 1000) is True


def test_one_stray_first_person_phrase_does_not_qualify():
    """A technical appendix can contain a single such phrase by accident."""
    text = "I graduated from UCC. " + "Technical appendix content. " * 100

    assert acp.looks_like_evidence_document(text) is False


def test_a_fragment_is_not_a_statement():
    assert acp.looks_like_evidence_document(QUALIFICATIONS[:200]) is False


def test_a_full_hearing_bundle_is_rejected():
    """Admitting one would attribute a whole hearing's evidence to whichever
    name appeared first. The non-statements measured 364k to 902k characters."""
    bundle = QUALIFICATIONS + ("Transcript of the oral hearing. " * 30_000)

    assert len(bundle) > acp._BUNDLE_CHARS
    assert acp.looks_like_evidence_document(bundle) is False


def test_one_persons_statement_with_appendices_bound_in_survives():
    """THE regression. The ceiling was briefly 150k, which dropped a 159k
    statement that was one person's evidence with appendices attached -- and
    that person was the only Tier A candidate the transport role had. A size
    cap is a blunt proxy for "is this one person"; it must stay loose enough
    never to overrule the real test."""
    doc = QUALIFICATIONS + ("Appendix A: design calculations. " * 5_000)

    assert 150_000 < len(doc) < acp._BUNDLE_CHARS
    assert acp.looks_like_evidence_document(doc) is True


def test_a_qualifications_section_behind_a_long_preamble_is_still_found():
    """The window was briefly 12k, which missed the qualifications section on
    any document with a title page, a contents list and a scheme description
    in front of it."""
    doc = ("Contents. Scheme description. " * 700) + QUALIFICATIONS

    assert 12_000 < len(doc) < acp._GATE_WINDOW
    assert acp.looks_like_evidence_document(doc) is True


def test_a_second_witness_deep_inside_a_bundle_does_not_rescue_it():
    """Scanning end to end would find first-person language from a dozen
    witnesses and pass everything, so the signals are counted near the start."""
    doc = ("Index of documents. " * 3_000) + QUALIFICATIONS
    assert len(doc) > acp._GATE_WINDOW

    assert acp.looks_like_evidence_document(doc) is False


def test_the_document_names_its_own_author():
    assert acp.name_from_text(QUALIFICATIONS) == "Aidan Foley"


def test_no_name_is_invented_when_the_document_does_not_give_one():
    assert acp.name_from_text("I am a Chartered Engineer with 20 years.") is None


# ---------------------------------------------------------------------------
# Case-page selection
# ---------------------------------------------------------------------------


def _case_page(*hrefs: str) -> bytes:
    return ("<html><body>" + "".join(
        '<a href="' + h + '">doc</a>' for h in hrefs
    ) + "</body></html>").encode("utf-8")


@pytest.fixture
def case(monkeypatch):
    def serve(*hrefs):
        monkeypatch.setattr(acp, "fetch_raw", lambda url, force=False: _case_page(*hrefs))
    return serve


def test_only_pdfs_under_the_document_trees_are_listed(case):
    case(
        "/publicaccess/Case%20Documentation/314724/Witness%20Statement%20of%20Aidan%20Foley.pdf",
        "/en-ie/news/some-article",                       # not a PDF
        "https://external.example.com/other.pdf",         # not a document tree
        "/media/abp/cases/reports/314/r314724.pdf",
    )

    urls = [d.url for d in acp.case_documents("314724")]

    assert len(urls) == 2
    assert all(u.endswith(".pdf") for u in urls)
    assert not any("external.example.com" in u for u in urls)


def test_the_same_document_linked_twice_is_listed_once(case):
    href = "/publicaccess/Case%20Documentation/314724/Witness%20Statement%20of%20Aidan%20Foley.pdf"
    case(href, href)

    assert len(acp.case_documents("314724")) == 1


def test_a_percent_encoded_filename_is_decoded_before_parsing(case):
    case("/publicaccess/Case%20Documentation/314724/"
         "No.02%20-%20TII%20-%20Witness%20Statement%20of%20Aidan%20Foley.pdf")

    doc = acp.case_documents("314724")[0]

    assert doc.person_hint == "Aidan Foley"
    assert doc.party == "TII"


def test_a_named_document_in_an_oral_hearing_folder_counts_without_the_title(case):
    """ACP does not consistently title these "Witness Statement" -- MetroLink
    files them under "Oral Hearing Documents", the Cork case under "OH
    submission from applicant". Both must match or the richest
    consultancy-authored statements are missed."""
    case("/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "No.02%20-%20TII%20-%20Aidan%20Foley.pdf")

    kept = acp.witness_statements("314724")

    assert [d.person_hint for d in kept] == ["Aidan Foley"]


def test_process_documents_are_dropped_even_inside_an_oral_hearing_folder(case):
    case("/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "Oral%20Hearing%20Agenda.pdf",
         "/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "Attendance%20Sheet.pdf")

    assert acp.witness_statements("314724") == []


def test_a_document_with_no_resolvable_person_is_dropped(case):
    case("/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "EIAR%20Chapter%2012%20Noise.pdf")

    assert acp.witness_statements("314724") == []


def test_an_unreachable_case_page_yields_nothing_rather_than_raising(monkeypatch):
    monkeypatch.setattr(acp, "fetch_raw", lambda url, force=False: None)

    assert acp.case_documents("999999") == []


def test_the_inspector_report_path_is_deterministic():
    assert acp.inspector_report_url("314724").endswith("/reports/314/r314724.pdf")


def test_the_documents_own_name_overrides_the_filename(monkeypatch, case):
    """The filename names the submitting party's document; the text names the
    author. When they disagree, the document's own words win."""
    from datetime import date

    from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument

    # NOTE: the filename must still parse to SOME name. A document whose
    # filename yields nothing is dropped by witness_statements() before it is
    # ever fetched, so name_from_text cannot rescue it -- the filename is the
    # cheap gate that decides what is worth paying to download. That is a
    # deliberate cost boundary, not an oversight, but it does mean an
    # initials-only filename ("... of A Foley.pdf") never reaches the text.
    case("/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "No.02%20-%20TII%20-%20Witness%20Statement%20of%20Adrian%20Foley.pdf")
    monkeypatch.setattr(acp, "fetch", lambda url, source_type="other": RawDocument(
        doc_id="d1", url="https://www.pleanala.ie/x.pdf",
        source_type="acp_witness_statement", fetched_at=date(2026, 8, 19),
        content_text=QUALIFICATIONS + "x" * 1000, http_status=200,
    ))

    harvested = acp.harvest("314724")

    assert [d.person_hint for d, _ in harvested] == ["Aidan Foley"]


def test_a_document_that_fails_the_text_gate_never_reaches_extraction(
    monkeypatch, case
):
    from datetime import date

    from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument

    case("/publicaccess/Case%20Documentation/314724/Oral%20Hearing%20Documents/"
         "Witness%20Statement%20of%20Aidan%20Foley.pdf")
    monkeypatch.setattr(acp, "fetch", lambda url, source_type="other": RawDocument(
        doc_id="d1", url="https://www.pleanala.ie/x.pdf",
        source_type="acp_witness_statement", fetched_at=date(2026, 8, 19),
        content_text="A technical appendix with no qualifications section. " * 40,
        http_status=200,
    ))

    assert acp.harvest("314724", verify_text=True) == []


@pytest.mark.parametrize("link,expected", [
    ("https://www.pleanala.ie/publicaccess/Case%20Documentation/314724/x.pdf", "314724"),
    ("https://www.pleanala.ie/anbordpleanala/media/abp/cases/reports/302/r302885.pdf",
     "302885"),
    ("https://www.pleanala.ie/en-ie/news/article", None),
])
def test_case_discovery_reads_the_number_out_of_a_search_result(
    monkeypatch, link, expected
):
    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"organic": [{"link": link}]}

    import requests

    monkeypatch.setattr(acp, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Resp())

    found = acp.discover_cases_serper(["q"])

    assert found == ([expected] if expected else [])


def test_a_search_outage_leaves_the_seed_cases_intact(monkeypatch):
    import requests

    monkeypatch.setattr(acp, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(requests, "post",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError("down")))

    assert acp.discover_cases_serper(["q"]) == []


# ===========================================================================
# company_bios.py -- reading a person out of a URL
# ===========================================================================


@pytest.mark.parametrize("url,expected", [
    ("https://www.ocsc.ie/our-people/brian-murphy", "Brian Murphy"),
    ("https://www.punch.ie/team/mary-kate-obrien/", "Mary Kate Obrien"),
    # Section pages, not people.
    ("https://www.ocsc.ie/our-people/", None),
    ("https://www.ocsc.ie/about/our-team", None),
    ("https://www.ocsc.ie/services/structural-engineering", None),
    ("https://www.ocsc.ie/people/murphy", None),  # single token is not a name
])
def test_a_name_is_read_out_of_a_profile_slug(url, expected):
    assert company_bios._name_from_slug(url) == expected


@pytest.mark.parametrize("title,expected", [
    ("Brian Murphy | O'Connor Sutton Cronin", "Brian Murphy"),
    ("Mary O'Brien - Associate Director", "Mary O'Brien"),
    ("", None),
])
def test_a_name_is_read_out_of_a_page_title(title, expected):
    assert company_bios._name_from_title(title) == expected


BIO = ("Brian Murphy is an Associate Director and a Chartered Engineer "
       "(CEng MIEI) with eighteen years of experience. " * 3)


def test_a_profile_page_reads_as_a_bio():
    assert company_bios.looks_like_bio(BIO) is True


def test_a_page_with_no_professional_grade_is_not_a_bio():
    assert company_bios.looks_like_bio("Our practice was founded in 1972. " * 40) is False


def test_a_stub_page_is_not_a_bio():
    assert company_bios.looks_like_bio("Brian Murphy, CEng") is False


def test_a_people_index_listing_forty_engineers_is_not_one_persons_profile():
    """An index page concentrates many grades; a profile concentrates one."""
    index = "Senior Engineer CEng MIEI. " * 60

    assert company_bios.looks_like_bio(index) is False


@pytest.fixture
def firm() -> company_bios.Firm:
    return company_bios.Firm(slug="ocsc", name="O'Connor Sutton Cronin",
                             domain="ocsc.ie", people_paths=["/people/"])


def _page(*hrefs: str) -> bytes:
    return ("<html>" + "".join('<a href="' + h + '">x</a>' for h in hrefs)
            + "</html>").encode("utf-8")


def test_a_people_index_is_discovered_from_the_navigation(monkeypatch, firm):
    """Hardcoded paths matched only 1 of 18 firms: every CMS names this page
    differently (/team, /our-people, /about/people, /who-we-are ...)."""
    monkeypatch.setattr(company_bios, "fetch_raw", lambda url, force=False: _page(
        "/services/", "/our-people/", "/contact/"))

    found = company_bios.find_people_indexes(firm)

    assert found == ["https://www.ocsc.ie/our-people/"]


def test_index_discovery_stays_on_the_firms_own_domain(monkeypatch, firm):
    monkeypatch.setattr(company_bios, "fetch_raw", lambda url, force=False: _page(
        "https://www.linkedin.com/company/x/people/", "/our-team/"))

    assert company_bios.find_people_indexes(firm) == ["https://www.ocsc.ie/our-team/"]


def test_vacancy_pages_never_become_candidates(monkeypatch, firm):
    """The first search-based run returned mostly "senior-structural-engineer"
    VACANCY pages, which would have entered the pipeline as fake people."""
    monkeypatch.setattr(company_bios, "fetch_raw", lambda url, force=False: _page(
        "/people/brian-murphy", "/careers/people/senior-structural-engineer",
        "/jobs/people/graduate-engineer"))

    urls = [b.url for b in company_bios.crawl_people_index(firm)]

    assert urls == ["https://www.ocsc.ie/people/brian-murphy"]


def test_profile_crawling_ignores_links_off_the_firms_domain(monkeypatch, firm):
    monkeypatch.setattr(company_bios, "fetch_raw", lambda url, force=False: _page(
        "/people/brian-murphy", "https://awards.example.com/people/brian-murphy"))

    urls = [b.url for b in company_bios.crawl_people_index(firm)]

    assert urls == ["https://www.ocsc.ie/people/brian-murphy"]


def test_the_client_and_its_parent_are_absent_from_the_sourcing_list():
    """Off-limits: no TOBIN or AtkinsRealis engineer anywhere in the output."""
    blob = " ".join(f.name.lower() + " " + f.domain.lower() for f in company_bios.FIRMS)

    for banned in company_bios.OFF_LIMITS_FIRMS:
        assert banned not in blob


def test_every_firm_is_uniquely_identified():
    slugs = [f.slug for f in company_bios.FIRMS]
    domains = [f.domain for f in company_bios.FIRMS]

    assert len(slugs) == len(set(slugs))
    assert len(domains) == len(set(domains))
    assert all(f.name and f.domain and "." in f.domain for f in company_bios.FIRMS)


def test_no_firm_domain_carries_a_scheme_or_a_path():
    """These are concatenated onto "https://www." -- a scheme here yields a
    URL that silently 404s for the whole firm."""
    for f in company_bios.FIRMS:
        assert "//" not in f.domain and "/" not in f.domain


# ===========================================================================
# oral_hearing_web.py -- breadth across scheme sites
# ===========================================================================


def _serper(monkeypatch, organic: list[dict]):
    class Resp:
        def read(self):
            return json.dumps({"organic": organic}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(oral_hearing_web, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(oral_hearing_web.urllib.request, "urlopen",
                        lambda req, timeout=None: Resp())


def test_a_search_outage_degrades_coverage_without_killing_the_run(monkeypatch, capsys):
    monkeypatch.setattr(oral_hearing_web, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(oral_hearing_web.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(OSError("down")))

    assert oral_hearing_web.serper_search("q") == []
    assert "serper failed" in capsys.readouterr().out, (
        "a silently-empty source must be distinguishable from an empty result set"
    )


def test_discovery_keeps_only_irish_evidence_pdfs(monkeypatch):
    _serper(monkeypatch, [
        {"link": "https://www.n6galwaycityringroad.ie/oh/Brief-of-Evidence-Mary-Ryan.pdf",
         "title": "Brief of Evidence"},
        {"link": "https://www.gov.uk/inquiry/proof-of-evidence-john-smith.pdf",
         "title": "Proof of Evidence"},                       # not Irish
        {"link": "https://www.pleanala.ie/news/witness-statement-of-x",
         "title": "Witness Statement of X"},                  # not a PDF
        {"link": "https://www.corkcity.ie/reports/traffic-counts.pdf",
         "title": "Traffic counts"},                          # not evidence
    ])

    found = oral_hearing_web.discover(["q"])

    assert [d.url for d in found] == [
        "https://www.n6galwaycityringroad.ie/oh/Brief-of-Evidence-Mary-Ryan.pdf"
    ]


@pytest.mark.parametrize("url,expected", [
    ("https://x.ie/oh/Witness-Statement-of-Aidan-Foley.pdf", "Aidan Foley"),
    ("https://x.ie/oh/Brief_of_Evidence_Mary_Ryan.pdf", "Mary Ryan"),
    ("https://x.ie/oh/witness%20statement%20of%20sean%20murphy.pdf", "Sean Murphy"),
    ("https://x.ie/oh/EIAR-Chapter-12.pdf", None),
])
def test_a_name_is_read_out_of_an_evidence_url(url, expected):
    assert oral_hearing_web._name_from_url(url) == expected


# ===========================================================================
# technical_evidence.py -- the Role 1 tier ceiling
# ===========================================================================


def _tech_results(monkeypatch, organic: list[dict]):
    monkeypatch.setattr(technical_evidence, "serper_search",
                        lambda query, num=8: organic)


def test_both_queries_quote_the_candidates_name():
    """An unquoted Irish name returns the whole country."""
    qs = technical_evidence._queries("Brian Murphy", "Punch Consulting Engineers")

    assert len(qs) == 2
    assert all('"Brian Murphy"' in q for q in qs)
    assert any("Punch Consulting Engineers" in q for q in qs)


def test_a_candidate_with_no_known_employer_still_gets_a_technical_query():
    qs = technical_evidence._queries("Brian Murphy", None)

    assert len(qs) == 1
    assert "Eurocode" in qs[0]


def test_a_result_that_never_mentions_the_surname_is_about_someone_else(monkeypatch):
    _tech_results(monkeypatch, [
        {"link": "https://www.engineersjournal.ie/2024/eurocode-design",
         "title": "Eurocode design in practice",
         "snippet": "A study of EN 1992 detailing by another author."},
    ])

    assert technical_evidence.discover_for("bm", "Brian Murphy", None) == []


def test_a_result_with_the_surname_but_no_technical_content_is_skipped(monkeypatch):
    _tech_results(monkeypatch, [
        {"link": "https://www.someblog.com/post",
         "title": "Brian Murphy joins the golf club",
         "snippet": "Brian Murphy was elected captain."},
    ])

    assert technical_evidence.discover_for("bm", "Brian Murphy", None) == []


def test_a_recognised_publisher_qualifies_on_the_surname_alone(monkeypatch):
    """A bylined Engineers Journal article is worth fetching even when the
    snippet is 160 characters of nothing."""
    _tech_results(monkeypatch, [
        {"link": "https://www.engineersjournal.ie/2024/author-brian-murphy",
         "title": "By Brian Murphy", "snippet": "Brian Murphy writes."},
    ])

    found = technical_evidence.discover_for("bm", "Brian Murphy", None)

    assert [d.url for d in found] == [
        "https://www.engineersjournal.ie/2024/author-brian-murphy"
    ]


def test_a_lead_database_is_refused_at_discovery(monkeypatch):
    """39 of 52 technical-evidence claims came from sources that must never be
    cited. A managing director who clicks prospeo.io and finds a scraped
    contact record has watched the dossier's whole promise collapse."""
    _tech_results(monkeypatch, [
        {"link": "https://prospeo.io/c/barrett-mahony-consulting-engineers",
         "title": "Brian Murphy", "snippet": "Brian Murphy structural design Eurocode"},
    ])

    assert technical_evidence.discover_for("bm", "Brian Murphy", None) == []


def _rawdoc(text: str, url: str = "https://www.engineersjournal.ie/a"):
    from datetime import date

    from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument

    return RawDocument(doc_id="d1", url=url, source_type="other",
                       fetched_at=date(2026, 8, 19), content_text=text,
                       http_status=200)


def test_the_surname_must_appear_in_the_page_body_not_only_the_snippet(monkeypatch):
    """Otherwise the claim is attributed to someone the document never names."""
    body = "The transfer structure was designed to Eurocode EN 1992-1-1. " * 20
    monkeypatch.setattr(technical_evidence, "fetch",
                        lambda url, source_type="other": _rawdoc(body))
    doc = technical_evidence.TechDoc(url="https://www.engineersjournal.ie/a",
                                     person_id="bm", full_name="Brian Murphy")

    assert technical_evidence.harvest([doc]) == []


def test_a_page_naming_the_person_and_the_design_code_survives(monkeypatch):
    body = ("Brian Murphy designed the transfer structure to Eurocode "
            "EN 1992-1-1, modelled in Tekla. " * 20)
    monkeypatch.setattr(technical_evidence, "fetch",
                        lambda url, source_type="other": _rawdoc(body))
    doc = technical_evidence.TechDoc(url="https://www.engineersjournal.ie/a",
                                     person_id="bm", full_name="Brian Murphy")

    assert len(technical_evidence.harvest([doc])) == 1


def test_a_page_naming_the_person_with_no_technical_term_is_not_evidence(monkeypatch):
    body = "Brian Murphy has joined the firm as an Associate Director. " * 20
    monkeypatch.setattr(technical_evidence, "fetch",
                        lambda url, source_type="other": _rawdoc(body))
    doc = technical_evidence.TechDoc(url="https://www.engineersjournal.ie/a",
                                     person_id="bm", full_name="Brian Murphy")

    assert technical_evidence.harvest([doc]) == []


def test_a_thin_page_is_not_fetched_into_the_evidence_set(monkeypatch):
    monkeypatch.setattr(technical_evidence, "fetch",
                        lambda url, source_type="other": _rawdoc("Brian Murphy Eurocode"))
    doc = technical_evidence.TechDoc(url="https://www.engineersjournal.ie/a",
                                     person_id="bm", full_name="Brian Murphy")

    assert technical_evidence.harvest([doc]) == []


def test_the_staff_directory_we_already_read_is_not_re_harvested():
    """Re-finding ocsc.ie/people via search adds no information, costs a second
    extraction, and produces duplicate claims that inflate the tier count."""
    for url in ("https://www.ocsc.ie/people", "https://www.punch.ie/our-team/",
                "https://www.dbfl.ie/team"):
        assert technical_evidence._BLOCKED_SOURCE.search(url)
