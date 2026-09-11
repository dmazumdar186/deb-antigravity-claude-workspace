"""
Tests for run.py's stage_deepen_near_misses.

Zero network, zero LLM: sources.oral_hearing_web.serper_search and
run.cache_fetch and run.extract_from_document are all monkeypatched to
fixture data. Every test builds a complete run directory on disk (extract /
validate / gate) and runs the real stage function against it, same shape as
tests/test_stages.py.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import Claim, RawDocument
from gtm_client_workflows.gaia_sourcing.roles import ROLE1

ROLE_ID = ROLE1.role_id


@pytest.fixture
def R(tmp_path, monkeypatch):
    """`run` with every on-disk path redirected into tmp_path."""
    from gtm_client_workflows.gaia_sourcing import run as mod

    monkeypatch.setattr(mod, "RUN_DIR", tmp_path)
    monkeypatch.setattr(mod, "DOCS", tmp_path / "docs.jsonl")
    monkeypatch.setattr(mod, "LOG_DIR", tmp_path / "logs")
    return mod


def _person_rec(pid: str, name: str, employer: str = "Acme Engineering") -> dict:
    return {
        "person_id": pid,
        "full_name": name,
        "current_title": "Engineer",
        "current_employer": employer,
        "location": None,
        "doc_ids": ["d1"],
        "linkedin_url": None,
        "role_id": ROLE_ID,
        "source": "search_snippet",
    }


def _gate_rec(pid: str, failed: list[str], all_gates: list[str], n_claims: int = 1) -> dict:
    return {
        "role_id": ROLE_ID,
        "tier": "EXCLUDED",
        "gates": [
            {"gate_id": g, "passed": g not in failed, "basis": None, "note": None}
            for g in all_gates
        ],
        "n_claims": n_claims,
        "client_side": False,
    }


def _seed_run(R, gates_by_pid: dict[str, list[str]], all_gates: list[str] | None = None) -> None:
    """Write extract.json / validate.json / gate.json for the given persons.

    `gates_by_pid` maps person_id -> list of FAILED gate ids.
    """
    all_gates = all_gates or ["chartered", "seniority", "discipline", "located_ie"]
    persons = {}
    gate_out = {}
    for i, (pid, failed) in enumerate(gates_by_pid.items()):
        name = "Firstname" + str(i) + " Surname" + str(i)
        persons[pid] = _person_rec(pid, name)
        gate_out[pid] = _gate_rec(pid, failed, all_gates)
    R.save("extract", {"persons": persons, "claims": [], "extracted_doc_ids": []})
    R.save("validate", {"claims": [], "stats": {}})
    R.save("gate", gate_out)


# ---------------------------------------------------------------------------
# No-op when gate.json is absent
# ---------------------------------------------------------------------------


def test_no_op_without_gate_json(R, capsys):
    R.stage_deepen_near_misses()

    out = capsys.readouterr().out
    assert "gate.json missing" in out
    assert not (R.RUN_DIR / "deepen_near_misses.json").exists()


# ---------------------------------------------------------------------------
# Near-miss selection: subset-of-deepen_gates rule
# ---------------------------------------------------------------------------


def test_person_failing_an_extra_gate_is_skipped(R, monkeypatch, capsys):
    # p_ok fails only chartered -- a near-miss.
    # p_both fails chartered + seniority -- both in CONFIG.deepen_gates, still a near-miss.
    # p_extra fails chartered + discipline -- discipline is a real exclusion, skipped.
    _seed_run(R, {
        "p_ok": ["chartered"],
        "p_both": ["chartered", "seniority"],
        "p_extra": ["chartered", "discipline"],
    })

    calls: list[str] = []
    monkeypatch.setattr(R.oral_hearing_web, "serper_search", lambda q, num=10: calls.append(q) or [])

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert set(saved["targets"]) == {"p_ok", "p_both"}
    assert "p_extra" not in saved["targets"]


# ---------------------------------------------------------------------------
# Query budget
# ---------------------------------------------------------------------------


def test_query_budget_is_respected(R, monkeypatch, capsys):
    _seed_run(R, {
        "p1": ["chartered"],
        "p2": ["chartered"],
        "p3": ["chartered"],
    })
    monkeypatch.setattr(R.CONFIG, "deepen_max_queries", 2)

    calls: list[str] = []

    def fake_search(q, num=10):
        calls.append(q)
        return []

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    R.stage_deepen_near_misses()

    assert len(calls) <= 2
    assert "query budget" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Snippet-as-document: kept when it carries a chartership token
# ---------------------------------------------------------------------------


def test_charter_token_in_snippet_is_kept_as_search_snippet_document(R, monkeypatch):
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Firstname0 Surname0, CEng MIEI - Acme Engineering",
            "snippet": "Chartered structural engineer with 10 years experience.",
            "link": "https://example.com/bio/firstname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)
    # Non-LinkedIn fetch: return None so only the snippet document survives.
    monkeypatch.setattr(R, "cache_fetch", lambda url, source_type="other": None)

    captured_claims: list[Claim] = []

    def fake_extract(person, doc, tracker_label="L5"):
        assert doc.source_type == "search_snippet"
        c = Claim(
            claim_id="c_" + person.person_id,
            subject_person_id=person.person_id,
            dimension="chartership",
            assertion=person.full_name + " is CEng MIEI",
            evidence_quote="CEng MIEI - Acme Engineering",
            source_doc_id=doc.doc_id,
            source_url=doc.url,
            confidence="direct",
        )
        captured_claims.append(c)
        return [c], None

    monkeypatch.setattr(R, "extract_from_document", fake_extract)

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert saved["docs_by_pid"].get("p_ok") == 1
    assert len(captured_claims) == 1

    # Folded back and re-gated: chartered now passes.
    new_gate = json.loads((R.RUN_DIR / "gate.json").read_text(encoding="utf-8"))
    gates = {g["gate_id"]: g["passed"] for g in new_gate["p_ok"]["gates"]}
    assert gates["chartered"] is True

    out_log = "deepen_near_misses: 1 of 1 near-misses now pass chartered"
    # Re-run capture via a second stage_gate log check is unnecessary here;
    # docs_by_pid + new_gate above already prove the fold-back worked.


# ---------------------------------------------------------------------------
# Fetched page kept only when both name parts co-occur in the text
# ---------------------------------------------------------------------------


def test_fetched_page_requires_both_name_parts_together(R, monkeypatch):
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Acme Engineering our people",
            "snippet": "Meet our team of engineers.",
            "link": "https://acme.example/bio/firstname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    def fake_fetch_no_match(url, source_type="other"):
        # Two separate, well-under-_MAX_LINE lines so fragment_with_both_names
        # cannot bridge across the line break -- Firstname0 and Surname0
        # never co-occur on the same line or within a tight character window.
        return RawDocument(
            doc_id="d_no_match",
            url=url,
            source_type="other",
            fetched_at=date(2026, 9, 11),
            content_text=(
                "Firstname0 leads the commercial team at Acme Engineering.\n"
                + ("Padding text to push the surname well outside the fragment window. " * 6)
                + "\nA different colleague, Surname0, works in the residential team.\n"
            ),
            http_status=200,
        )

    monkeypatch.setattr(R, "cache_fetch", fake_fetch_no_match)
    extract_calls = []
    monkeypatch.setattr(
        R, "extract_from_document",
        lambda person, doc, tracker_label="L5": (extract_calls.append(doc.doc_id), ([], None))[1],
    )

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert saved["docs_by_pid"].get("p_ok", 0) == 0
    assert extract_calls == []


def test_fetched_page_kept_when_both_names_co_occur(R, monkeypatch):
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Acme Engineering our people",
            "snippet": "Meet our team of engineers.",
            "link": "https://acme.example/bio/firstname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    def fake_fetch_match(url, source_type="other"):
        return RawDocument(
            doc_id="d_match",
            url=url,
            source_type="other",
            fetched_at=date(2026, 9, 11),
            content_text=(
                "Firstname0 Surname0 is a Chartered Structural Engineer (CEng "
                "MIEI) at Acme Engineering with over a decade of design "
                "experience. " * 5
            ),
            http_status=200,
        )

    monkeypatch.setattr(R, "cache_fetch", fake_fetch_match)

    def fake_extract(person, doc, tracker_label="L5"):
        c = Claim(
            claim_id="c_" + person.person_id,
            subject_person_id=person.person_id,
            dimension="chartership",
            assertion=person.full_name + " is CEng MIEI",
            evidence_quote="Chartered Structural Engineer (CEng MIEI) at Acme Engineering",
            source_doc_id=doc.doc_id,
            source_url=doc.url,
            confidence="direct",
        )
        return [c], None

    monkeypatch.setattr(R, "extract_from_document", fake_extract)

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert saved["docs_by_pid"].get("p_ok") == 1

    new_gate = json.loads((R.RUN_DIR / "gate.json").read_text(encoding="utf-8"))
    gates = {g["gate_id"]: g["passed"] for g in new_gate["p_ok"]["gates"]}
    assert gates["chartered"] is True


# ---------------------------------------------------------------------------
# LinkedIn results are never fetched, even when kept as a snippet document
# ---------------------------------------------------------------------------


def test_linkedin_result_never_fetched(R, monkeypatch):
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Firstname0 Surname0 - CEng MIEI - Acme Engineering | LinkedIn",
            "snippet": "Chartered Structural Engineer at Acme Engineering.",
            "link": "https://ie.linkedin.com/in/firstname0surname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    fetch_calls = []

    def fake_fetch(url, source_type="other"):
        fetch_calls.append(url)
        return None

    monkeypatch.setattr(R, "cache_fetch", fake_fetch)
    monkeypatch.setattr(
        R, "extract_from_document",
        lambda person, doc, tracker_label="L5": ([], None),
    )

    R.stage_deepen_near_misses()

    assert fetch_calls == []
    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    # The LinkedIn snippet itself still carries a chartership token, so it is
    # still kept and still counted as a document even though never fetched.
    assert saved["docs_by_pid"].get("p_ok") == 1


# ---------------------------------------------------------------------------
# Identity corroboration (2026-09-11 adversarial-audit fix, item 4): a
# fetched page whose name-window carries no corroborating token (employer or
# discipline) -- or a contradicting profession -- must never be attached.
# ---------------------------------------------------------------------------


def test_a_page_with_no_corroborating_token_is_skipped(R, monkeypatch, capsys):
    """The audit's exhibit: a Porsche sales page for a same-named person."""
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Firstname0 Surname0 - Porsche Centre Dublin",
            "snippet": "Sales team.",
            "link": "https://porschecentredublin.example/team/firstname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    def fake_fetch(url, source_type="other"):
        return RawDocument(
            doc_id="d_porsche",
            url=url,
            source_type="other",
            fetched_at=date(2026, 9, 11),
            content_text=(
                "Firstname0 Surname0 is a Sales Executive at Porsche Centre "
                "Dublin, specialising in the Cayenne and Macan ranges. " * 5
            ),
            http_status=200,
        )

    monkeypatch.setattr(R, "cache_fetch", fake_fetch)
    extract_calls = []
    monkeypatch.setattr(
        R, "extract_from_document",
        lambda person, doc, tracker_label="L5": (extract_calls.append(doc.doc_id), ([], None))[1],
    )

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert saved["docs_by_pid"].get("p_ok", 0) == 0
    assert extract_calls == []
    assert "identity: p_ok skipped" in capsys.readouterr().out


def test_a_lally_chartered_engineers_page_is_accepted(R, monkeypatch):
    """The audit's paired positive case: a genuine engineering-firm bio."""
    _seed_run(R, {"p_ok": ["chartered"]})

    def fake_search(q, num=10):
        return [{
            "title": "Firstname0 Surname0 - Lally Chartered Engineers",
            "snippet": "Our people.",
            "link": "https://lallyengineers.example/team/firstname0",
        }]

    monkeypatch.setattr(R.oral_hearing_web, "serper_search", fake_search)

    def fake_fetch(url, source_type="other"):
        return RawDocument(
            doc_id="d_lally",
            url=url,
            source_type="other",
            fetched_at=date(2026, 9, 11),
            content_text=(
                "Firstname0 Surname0 is a Chartered Structural Engineer with "
                "Lally Chartered Engineers, CEng MIEI. " * 5
            ),
            http_status=200,
        )

    monkeypatch.setattr(R, "cache_fetch", fake_fetch)

    def fake_extract(person, doc, tracker_label="L5"):
        c = Claim(
            claim_id="c_" + person.person_id,
            subject_person_id=person.person_id,
            dimension="chartership",
            assertion=person.full_name + " is CEng MIEI",
            evidence_quote="Chartered Engineer with Lally Chartered Engineers, CEng MIEI",
            source_doc_id=doc.doc_id,
            source_url=doc.url,
            confidence="direct",
        )
        return [c], None

    monkeypatch.setattr(R, "extract_from_document", fake_extract)

    R.stage_deepen_near_misses()

    saved = json.loads((R.RUN_DIR / "deepen_near_misses.json").read_text(encoding="utf-8"))
    assert saved["docs_by_pid"].get("p_ok") == 1
