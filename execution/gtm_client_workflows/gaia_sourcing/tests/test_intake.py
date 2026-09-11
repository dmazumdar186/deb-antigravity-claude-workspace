"""
layers/intake.py -- name normalisation, CSV/plain-text/iterable loading, and
pool matching (exact / employer tiebreak / ambiguous / none). Pure, no
network, no LLM -- every test here is a plain function call.
"""

from __future__ import annotations

from pathlib import Path

from gtm_client_workflows.gaia_sourcing.layers.intake import (
    IntakeRow,
    load_names,
    load_names_report,
    match_pool,
    normalise_employer,
    normalise_name,
    slug_for_unmatched,
)


# ---------------------------------------------------------------------------
# normalise_name
# ---------------------------------------------------------------------------


def test_normalise_basic():
    assert normalise_name("John Smith") == "john smith"


def test_normalise_oreilly_variants_converge():
    variants = ["Michael O'Reilly", "Michael O’Reilly", "Michael OReilly"]
    normed = {normalise_name(v) for v in variants}
    assert normed == {"michael oreilly"}


def test_normalise_strips_trailing_postnominals():
    assert normalise_name("John Alcaras BSc CEng MIEI") == "john alcaras"


def test_normalise_strips_parenthetical_postnominals():
    assert normalise_name("Kate FitzGerald (BSc CEng)") == "kate fitzgerald"


def test_normalise_strips_postnominals_after_comma():
    assert normalise_name("Kate FitzGerald, CEng MIEI") == "kate fitzgerald"


def test_normalise_hyphens_as_spaces():
    assert normalise_name("Anne-Marie O'Brien") == "anne marie obrien"


def test_normalise_accents_folded():
    assert normalise_name("Seán Ó Ríordáin") == "sean o riordain"


def test_normalise_casefold_and_whitespace_collapse():
    assert normalise_name("  JOHN   SMITH  ") == "john smith"


def test_normalise_empty_and_none():
    assert normalise_name("") == ""
    assert normalise_name(None) == ""


# ---------------------------------------------------------------------------
# load_names -- CSV
# ---------------------------------------------------------------------------


def test_load_names_csv(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text(
        "name,employer,title\nJohn Smith,Acme,Engineer\nJane Doe,Beta,Director\n",
        encoding="utf-8",
    )
    rows = load_names(p)
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]
    assert rows[0].employer == "Acme"
    assert rows[0].title == "Engineer"


def test_load_names_csv_case_insensitive_headers_and_extra_columns(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text(
        "Full_Name,Company,LinkedIn_URL,Notes\n"
        "John Smith,Acme,https://linkedin.com/in/john,ignored\n",
        encoding="utf-8",
    )
    rows = load_names(p)
    assert len(rows) == 1
    assert rows[0].name == "John Smith"
    assert rows[0].employer == "Acme"
    assert rows[0].linkedin_url == "https://linkedin.com/in/john"


def test_load_names_csv_blank_name_rows_dropped(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("name,employer\nJohn Smith,Acme\n,Beta\n  ,Gamma\n", encoding="utf-8")
    rows = load_names(p)
    assert [r.name for r in rows] == ["John Smith"]


# ---------------------------------------------------------------------------
# load_names -- plain text
# ---------------------------------------------------------------------------


def test_load_names_plain_text(tmp_path):
    p = tmp_path / "in.txt"
    p.write_text("John Smith\n\nJane Doe\n  \nBob Jones\n", encoding="utf-8")
    rows = load_names(p)
    assert [r.name for r in rows] == ["John Smith", "Jane Doe", "Bob Jones"]


# ---------------------------------------------------------------------------
# load_names -- iterable
# ---------------------------------------------------------------------------


def test_load_names_iterable_of_strings():
    rows = load_names(["John Smith", "", "Jane Doe"])
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]


def test_load_names_iterable_of_dicts():
    rows = load_names([
        {"name": "John Smith", "employer": "Acme"},
        {"full_name": "Jane Doe", "company": "Beta"},
    ])
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]
    assert rows[0].employer == "Acme"
    assert rows[1].employer == "Beta"


def test_load_names_dedupes_preserving_order():
    rows = load_names(["John Smith", "john   smith", "Jane Doe", "John Smith"])
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]


# ---------------------------------------------------------------------------
# match_pool
# ---------------------------------------------------------------------------


def _persons(*specs):
    return {
        pid: {"full_name": name, "current_employer": employer}
        for pid, name, employer in specs
    }


def test_match_pool_exact():
    rows = [IntakeRow(name="John Smith")]
    persons = _persons(("john_smith", "John Smith", "Acme"))
    matches = match_pool(rows, persons)
    assert len(matches) == 1
    assert matches[0].how == "exact"
    assert matches[0].person_id == "john_smith"


def test_match_pool_oreilly_variant_matches_cache_curly_quote():
    rows = [IntakeRow(name="Michael O'Reilly")]
    persons = _persons(("michael_o_reilly", "Michael O’Reilly", "OCSC"))
    matches = match_pool(rows, persons)
    assert matches[0].how == "exact"
    assert matches[0].person_id == "michael_o_reilly"


def test_match_pool_employer_tiebreak():
    rows = [IntakeRow(name="John Smith", employer="Acme Engineering")]
    persons = _persons(
        ("john_smith_1", "John Smith", "Acme Engineering Ltd"),
        ("john_smith_2", "John Smith", "Beta Consulting"),
    )
    matches = match_pool(rows, persons)
    assert matches[0].how == "employer_tiebreak"
    assert matches[0].person_id == "john_smith_1"


def test_match_pool_ambiguous_no_employer():
    rows = [IntakeRow(name="John Smith")]
    persons = _persons(
        ("john_smith_1", "John Smith", "Acme"),
        ("john_smith_2", "John Smith", "Beta"),
    )
    matches = match_pool(rows, persons)
    assert matches[0].how == "ambiguous"
    assert matches[0].person_id is None
    assert set(matches[0].candidates) == {"john_smith_1", "john_smith_2"}


def test_match_pool_ambiguous_employer_matches_more_than_one():
    rows = [IntakeRow(name="John Smith", employer="Consulting")]
    persons = _persons(
        ("john_smith_1", "John Smith", "Acme Consulting"),
        ("john_smith_2", "John Smith", "Beta Consulting"),
    )
    matches = match_pool(rows, persons)
    assert matches[0].how == "ambiguous"
    assert matches[0].person_id is None


def test_match_pool_none():
    rows = [IntakeRow(name="Nobody Here")]
    persons = _persons(("john_smith", "John Smith", "Acme"))
    matches = match_pool(rows, persons)
    assert matches[0].how == "none"
    assert matches[0].person_id is None
    assert matches[0].candidates == []


# ---------------------------------------------------------------------------
# Code-review fixes 2026-09-11
# ---------------------------------------------------------------------------


def test_normalise_name_comma_tail_all_postnominal_is_dropped():
    # item j: "Kate FitzGerald, CEng MIEI" -- every tail token is a
    # post-nominal, so the tail is dropped, same as before this fix.
    assert normalise_name("Kate FitzGerald, CEng MIEI") == "kate fitzgerald"


def test_normalise_name_comma_tail_not_all_postnominal_is_kept():
    # item j: "Smith, John" -- the tail ("John") is not a post-nominal, so
    # the comma is treated as a word boundary and BOTH parts survive.
    assert normalise_name("Smith, John") == "smith john"


def test_normalise_name_comma_variant_names_never_collapse_in_dedupe():
    rows = load_names(["Smith, John", "Smith, Jane"])
    assert [r.name for r in rows] == ["Smith, John", "Smith, Jane"]


def test_load_names_csv_first_last_name_pair(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text(
        "First Name,Last Name,Employer\nJohn,Smith,Acme\nJane,Doe,Beta\n",
        encoding="utf-8",
    )
    rows = load_names(p)
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]


def test_load_names_csv_first_last_name_pair_underscored_headers(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("first_name,last_name\nJohn,Smith\n", encoding="utf-8")
    rows = load_names(p)
    assert rows[0].name == "John Smith"


def test_load_names_csv_first_last_ignored_when_full_name_column_present(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text(
        "Full Name,First Name,Last Name\nJohn Q Smith,John,Smith\n",
        encoding="utf-8",
    )
    rows = load_names(p)
    assert rows[0].name == "John Q Smith"


def test_load_names_csv_widened_employer_and_title_aliases(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text(
        "Candidate Name,Current Company,Job Title\n"
        "John Smith,Acme Ltd,Senior Engineer\n",
        encoding="utf-8",
    )
    rows = load_names(p)
    assert rows[0].name == "John Smith"
    assert rows[0].employer == "Acme Ltd"
    assert rows[0].title == "Senior Engineer"


def test_load_names_csv_organisation_and_organization_aliases(tmp_path):
    for i, header in enumerate(("Organisation", "Organization", "Company Name")):
        p = tmp_path / ("in" + str(i) + ".csv")
        p.write_text(
            "name," + header + "\nJohn Smith,Acme Ltd\n", encoding="utf-8",
        )
        rows = load_names(p)
        assert rows[0].employer == "Acme Ltd"


def test_load_names_csv_empty_fieldname_from_trailing_comma_is_ignored(tmp_path):
    # item k: a trailing comma in the header row gives csv.DictReader an
    # empty-string fieldname -- must never be used as a column key.
    p = tmp_path / "in.csv"
    p.write_text("name,employer,\nJohn Smith,Acme,\n", encoding="utf-8")
    rows = load_names(p)
    assert rows[0].name == "John Smith"
    assert rows[0].employer == "Acme"


def test_normalise_employer_no_postnominal_stripping():
    # item l: normalise_employer must NOT run the name pipeline's
    # post-nominal/comma logic -- "Smith, Jones & Co" keeps both halves.
    assert normalise_employer("Smith, Jones & Co") == "smith jones co"


def test_normalise_employer_accent_and_case_folding():
    # Accents fold; apostrophes become a space (no O'Reilly-style fold --
    # that is name-specific behaviour normalise_employer deliberately
    # does not carry, per item l).
    assert normalise_employer("O’Connór Sutton Cronin") == "o connor sutton cronin"


def test_match_pool_tiebreak_uses_normalise_employer_not_normalise_name():
    # A comma-bearing employer name must not be truncated by the name
    # pipeline's post-nominal-tail logic during the tiebreak.
    rows = [IntakeRow(name="John Smith", employer="Smith, Jones & Co")]
    persons = _persons(
        ("john_smith_1", "John Smith", "Smith, Jones & Co Engineering"),
        ("john_smith_2", "John Smith", "Beta Consulting"),
    )
    matches = match_pool(rows, persons)
    assert matches[0].how == "employer_tiebreak"
    assert matches[0].person_id == "john_smith_1"


def test_load_names_report_counts_duplicates_dropped():
    rows, dropped = load_names_report(["John Smith", "john   smith", "Jane Doe"])
    assert [r.name for r in rows] == ["John Smith", "Jane Doe"]
    assert dropped == 1


def test_load_names_report_zero_duplicates():
    rows, dropped = load_names_report(["John Smith", "Jane Doe"])
    assert dropped == 0


def test_slug_for_unmatched_differs_for_non_identical_spellings():
    # item m: the docstring promises a shared id only for a BYTE-IDENTICAL
    # spelling -- two spellings of the same real person still slug
    # differently, because this is a slug function, not identity
    # resolution.
    assert slug_for_unmatched("Mike O'Reilly") != slug_for_unmatched("Michael O'Reilly")
