"""
Tests for integrations/recruit_crm.py::check_row_to_payload / check_note --
day 2 decision (a), deliverables/gaia_poc_check/PLAN.md "Day 2 decisions":
the check's output becomes the "Checked" column in Recruit CRM. Zero
network -- these two functions are pure and take a check_results.json row
(see run.py::run_check ~line 3808-4110 for the row shape).
"""

from __future__ import annotations

from datetime import date

from gtm_client_workflows.gaia_sourcing.integrations import recruit_crm as rc


def _row(**overrides) -> dict:
    row = {
        "name": "John Alcaras BSc CEng MIEI",
        "employer": "Punch Consulting Engineers",
        "title": "Senior Engineer",
        "status": "NEAR_MISS",
        "failed": [
            {"gate_id": "seniority_ceiling", "label": "Seniority ceiling",
             "reason": "Evidenced at 26 years' experience, above the 25-year ceiling."},
        ],
        "evidence": [
            {"dimension": "chartership", "quote": "John Alcaras is CEng MIEI.",
             "source_url": "https://example.ie/p1"},
        ],
        "contact": "verified",
        "one_line": "Everything else passes; over the seniority ceiling by one year.",
        "brief_version": "role1_senior_structural_engineer@abc1234",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# check_row_to_payload
# ---------------------------------------------------------------------------


def test_payload_never_carries_an_email_even_when_contact_is_verified():
    payload = rc.check_row_to_payload(_row(contact="verified"))
    assert "email" not in payload


def test_payload_name_is_split_and_postnominals_are_stripped():
    payload = rc.check_row_to_payload(_row())
    assert payload["first_name"] == "John"
    assert payload["last_name"] == "Alcaras"


def test_payload_custom_fields_status_wording_near_miss():
    payload = rc.check_row_to_payload(_row(status="NEAR_MISS"))
    assert payload["custom_fields"]["Shortlist Check"] == "NEAR MISS"


def test_payload_custom_fields_status_wording_not_checked():
    payload = rc.check_row_to_payload(_row(status="NOT_CHECKED", name="Nobody Here"))
    assert payload["custom_fields"]["Shortlist Check"] == "NOT CHECKED"


def test_payload_custom_fields_status_wording_pass_and_out():
    assert rc.check_row_to_payload(_row(status="PASS"))["custom_fields"]["Shortlist Check"] == "PASS"
    assert rc.check_row_to_payload(_row(status="OUT"))["custom_fields"]["Shortlist Check"] == "OUT"


def test_payload_custom_fields_carry_one_line_and_brief_version():
    row = _row()
    payload = rc.check_row_to_payload(row)
    assert payload["custom_fields"]["Shortlist Check line"] == row["one_line"]
    assert payload["custom_fields"]["Shortlist Check brief"] == row["brief_version"]


def test_payload_source_defaults_to_prodcraft_shortlist_check():
    payload = rc.check_row_to_payload(_row())
    assert payload["candidate_source"] == "Prodcraft Shortlist Check"


def test_payload_carries_title_and_employer_from_the_row_only():
    row = _row(title="Associate Director", employer="TOBIN Consulting Engineers")
    payload = rc.check_row_to_payload(row)
    assert payload["position"] == "Associate Director"
    assert payload["current_organization"] == "TOBIN Consulting Engineers"


# ---------------------------------------------------------------------------
# check_note
# ---------------------------------------------------------------------------


def test_note_contains_every_failed_reason():
    row = _row(failed=[
        {"gate_id": "seniority_ceiling", "label": "Seniority ceiling", "reason": "Over the cap."},
        {"gate_id": "located_ie", "label": "Based in the Republic", "reason": "No residence evidence."},
    ])
    note = rc.check_note(row, row["brief_version"], date(2026, 9, 13))
    assert "Over the cap." in note
    assert "No residence evidence." in note
    assert "Seniority ceiling" in note
    assert "Based in the Republic" in note


def test_note_says_none_when_nothing_failed():
    row = _row(status="PASS", failed=[])
    note = rc.check_note(row, row["brief_version"], date(2026, 9, 13))
    assert "Rules failed:" in note
    assert "none" in note.lower()


def test_note_carries_up_to_three_evidence_quotes_and_source():
    row = _row(evidence=[
        {"dimension": "chartership", "quote": "Quote one.", "source_url": "https://a.ie"},
        {"dimension": "location", "quote": "Quote two.", "source_url": "https://b.ie"},
        {"dimension": "years_experience", "quote": "Quote three.", "source_url": "https://c.ie"},
        {"dimension": "extra", "quote": "Quote four (dropped).", "source_url": "https://d.ie"},
    ])
    note = rc.check_note(row, row["brief_version"], date(2026, 9, 13))
    assert "Quote one." in note and "https://a.ie" in note
    assert "Quote two." in note
    assert "Quote three." in note
    assert "Quote four (dropped)." not in note


def test_not_checked_row_note_says_no_proof():
    row = _row(status="NOT_CHECKED", evidence=[], name="Nobody Here")
    note = rc.check_note(row, row["brief_version"], date(2026, 9, 13))
    assert "no proof" in note.lower()


def test_note_carries_the_contact_label():
    note = rc.check_note(_row(contact="guess"), "role1@abc1234", date(2026, 9, 13))
    assert "Contact: guess" in note


def test_note_carries_the_art14_line_verbatim():
    from gtm_client_workflows.gaia_sourcing.core.config import PRIVACY_NOTICE_URL

    note = rc.check_note(_row(), "role1@abc1234", date(2026, 9, 13))
    assert (
        "Art. 14 notice: " + PRIVACY_NOTICE_URL + " -- collected 2026-09-13 "
        "from public sources; outreach must include it."
    ) in note


def test_note_status_line_uses_crm_facing_wording():
    note = rc.check_note(_row(status="OUT"), "role1@abc1234", date(2026, 9, 13))
    assert "OUT" in note.splitlines()[0]
    assert "NEAR MISS" not in note.splitlines()[0]
