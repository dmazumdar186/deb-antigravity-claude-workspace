"""
run.py --check (Shortlist Check POC, deliverables/gaia_poc_check/PLAN.md).

Builds a tiny, complete run directory on disk (extract.json/validate.json)
under tmp_path and runs the real `run_check` function against it -- no
stage re-run, no network, no provider call. `core.providers.call_role` is
monkeypatched to raise if anything ever calls it, on top of the spend-meter
assertion `run_check` itself makes, so a regression that reached a paid
call would fail loudly here rather than only in production.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    HardGate, JobSpec, Person, ValidatedClaim,
)

R1 = "role1_senior_structural_engineer"

_BANNED_RE = re.compile(
    r"\b(ai|llm|model|pipeline|automated|platform|system|agent)\b", re.I
)


def _test_spec() -> JobSpec:
    """A tiny two-gate role so PASS / NEAR_MISS / OUT are each reachable
    with one or two claims, without pulling in ROLE1's full seven-gate,
    grade/county-aware brief."""
    return JobSpec(
        role_id=R1,
        title="Test Engineer",
        client="Gaia Talent",
        locations=["Ireland"],
        target_count=5,
        primary_signal_dimension="technical_skill",
        hard_gates=[
            HardGate(gate_id="chartered", description="Chartered with Engineers Ireland",
                      check="chartered"),
            HardGate(gate_id="located_ie", description="Based in the Republic of Ireland",
                      check="located_ie"),
        ],
    )


def _person(pid: str, name: str, employer: str = "Acme Engineering") -> dict:
    return {
        "person_id": pid,
        "full_name": name,
        "current_title": "Engineer",
        "current_employer": employer,
        "location": None,
        "doc_ids": ["d1"],
        "linkedin_url": None,
        "role_id": R1,
        "source": "company_directory",
    }


def _claim(pid: str, cid: str, dimension: str, assertion: str, quote: str) -> dict:
    return {
        "claim_id": cid,
        "subject_person_id": pid,
        "dimension": dimension,
        "assertion": assertion,
        "evidence_quote": quote,
        "source_doc_id": "d1",
        "source_url": "https://example.ie/p",
        "confidence": "direct",
        "quote_verified": True,
    }


@pytest.fixture
def R(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing import run as mod
    from gtm_client_workflows.gaia_sourcing.core import providers

    monkeypatch.setattr(mod, "RUN_DIR", tmp_path)
    spec = _test_spec()
    monkeypatch.setattr(mod, "ROLE1", spec)
    monkeypatch.setattr(mod, "ROLES", {spec.role_id: spec})

    def _no_provider(*args, **kwargs):
        raise AssertionError("--check must never call a provider")

    monkeypatch.setattr(providers, "call_role", _no_provider)
    monkeypatch.setattr(mod, "call_role", _no_provider, raising=False)
    providers.reset_spend()
    return mod


@pytest.fixture
def run_dir(R, tmp_path):
    # Alice: chartered AND located -> PASS.
    # Bob: chartered only -> NEAR_MISS (fails located_ie alone).
    # Carol: neither -> OUT (fails both gates).
    persons = {
        "alice_pass": _person("alice_pass", "Alice Pass"),
        "bob_nearmiss": _person("bob_nearmiss", "Bob Nearmiss"),
        "carol_out": _person("carol_out", "Carol Out"),
    }
    claims = [
        _claim("alice_pass", "c1", "chartership", "Alice is CEng MIEI",
               "Alice is CEng MIEI with Engineers Ireland"),
        _claim("alice_pass", "c2", "location", "Based in Dublin",
               "Alice is based in Dublin, Ireland"),
        _claim("bob_nearmiss", "c3", "chartership", "Bob is CEng MIEI",
               "Bob is CEng MIEI with Engineers Ireland"),
    ]
    (tmp_path / "extract.json").write_text(
        json.dumps({"persons": persons}), encoding="utf-8"
    )
    (tmp_path / "validate.json").write_text(
        json.dumps({"claims": claims}), encoding="utf-8"
    )
    return tmp_path


def _write_input(tmp_path: Path) -> Path:
    p = tmp_path / "input.csv"
    p.write_text(
        "name,employer,title\n"
        "Alice Pass,Acme Engineering,Engineer\n"
        "Bob Nearmiss,Acme Engineering,Engineer\n"
        "Carol Out,Acme Engineering,Engineer\n"
        "Nobody Here,Acme Engineering,Engineer\n",
        encoding="utf-8",
    )
    return p


def test_check_classifies_pass_near_miss_out_and_not_checked(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    out_dir = tmp_path / "out"
    contract = R.run_check(str(input_csv), out_dir)

    by_name = {r["name"]: r for r in contract["rows"]}
    assert by_name["Alice Pass"]["status"] == "PASS"
    assert by_name["Bob Nearmiss"]["status"] == "NEAR_MISS"
    assert by_name["Carol Out"]["status"] == "OUT"
    assert by_name["Nobody Here"]["status"] == "NOT_CHECKED"

    assert contract["summary"]["submitted"] == 4
    assert contract["summary"]["matched"] == 3
    assert contract["summary"]["pass"] == 1
    assert contract["summary"]["near_miss"] == 1
    assert contract["summary"]["out"] == 1
    assert contract["summary"]["not_checked"] == 1


def test_check_never_calls_a_provider(R, run_dir, tmp_path):
    from gtm_client_workflows.gaia_sourcing.core import providers

    input_csv = _write_input(tmp_path)
    assert providers.spend_eur() == 0.0
    R.run_check(str(input_csv), tmp_path / "out")
    assert providers.spend_eur() == 0.0


def test_check_cli_end_to_end_writes_keith_page(R, run_dir, tmp_path, monkeypatch):
    """main()'s --check dispatch must itself render keith/index.html --
    anneal-review HIGH fix 2026-09-11: it used to write only
    check_results.json/check.csv and stop, leaving the page to a separate,
    out-of-band call that could fall out of sync with the JSON it reads."""
    from gtm_client_workflows.gaia_sourcing.core import providers

    input_csv = _write_input(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv", ["run", "--check", str(input_csv), "--check-out", str(out_dir)],
    )
    rc = R.main()
    assert rc == 0
    assert providers.spend_eur() == 0.0

    page_path = out_dir / "keith" / "index.html"
    assert page_path.exists(), "main() --check must write keith/index.html itself"
    html = page_path.read_text(encoding="utf-8")
    assert "<title>Shortlist Check</title>" in html
    # The verdict paragraph is render/check_page.py's own copy, computed
    # from check_results.json -- its presence proves this is a real render
    # of THIS run's output, not a stub or a stale file left over.
    assert 'class="verdict"' in html
    assert (out_dir / "check_results.json").exists()


def test_check_writes_contract_keys(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    out_dir = tmp_path / "out"
    contract = R.run_check(str(input_csv), out_dir)

    on_disk = json.loads((out_dir / "check_results.json").read_text(encoding="utf-8"))
    assert on_disk == contract
    for key in ("campaign", "generated_at", "brief_version", "brief", "input",
                "summary", "rows", "pool", "time_value"):
        assert key in contract
    for key in ("submitted", "matched", "not_checked", "pass", "near_miss",
                "out", "by_rule", "contact"):
        assert key in contract["summary"]
    for row in contract["rows"]:
        for key in ("name", "employer", "title", "status", "failed",
                     "evidence", "contact", "one_line"):
            assert key in row
    for row in contract["pool"]:
        for key in ("name", "employer", "status", "failed_labels"):
            assert key in row


def test_check_csv_has_required_columns(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    out_dir = tmp_path / "out"
    R.run_check(str(input_csv), out_dir)

    lines = (out_dir / "check.csv").read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    for col in ("name", "employer", "title", "status", "reasons",
                "evidence_note", "contact", "linkedin_url"):
        assert col in header
    # 3 matched + 1 not-checked row + header
    assert len(lines) == 5


def test_check_one_lines_never_use_banned_words(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    for row in contract["rows"]:
        assert not _BANNED_RE.search(row["one_line"]), row["one_line"]
    for brief in contract["brief"]:
        for rule in brief["rules"]:
            assert not _BANNED_RE.search(rule["rule_text"]), rule["rule_text"]


def test_check_rule_text_never_leaks_internal_notes():
    """roles.py's HardGate.description is an internal engineering note --
    it carries 'PENDING KEITH MOLONY CALL 2026-09-10', a JD-vs-gate delta
    ('the JD asks 12-18'), and code examples ('e.g. ...'). None of that
    may ever reach _check_rule_text's output, for every gate on BOTH real
    roles (roles.ROLE1/ROLE2, unpatched -- this is the production data the
    leak was actually found in)."""
    from gtm_client_workflows.gaia_sourcing import run as mod
    from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

    date_re = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
    for spec in (ROLE1, ROLE2):
        for gate in spec.hard_gates:
            text = mod._check_rule_text(gate)
            assert "PENDING" not in text, (spec.role_id, gate.gate_id, text)
            assert "JD" not in text, (spec.role_id, gate.gate_id, text)
            assert "e.g." not in text, (spec.role_id, gate.gate_id, text)
            assert not date_re.search(text), (spec.role_id, gate.gate_id, text)


def test_check_rule_text_seniority_ceiling_matches_its_own_label():
    """The label (_check_gate_label_for) and the rule_text
    (_check_rule_text) are both derived from the gate's SAME live params,
    so they can never disagree the way roles.py's static description once
    did for Role 2: the label read 'Senior Engineer ceiling' (computed
    live) while the description underneath still said 'No higher than
    Associate Director' (roles.py's own placeholder wording, stale after
    the global --max-grade override)."""
    from gtm_client_workflows.gaia_sourcing import run as mod

    gate = HardGate(
        gate_id="seniority_ceiling", description="stale placeholder text",
        check="seniority_ceiling",
        params={"max_grade": "senior_engineer", "max_years": 15},
    )
    spec = _test_spec()
    spec.hard_gates = [gate]
    label = mod._check_gate_label_for("seniority_ceiling", spec)
    text = mod._check_rule_text(gate)
    assert label == "Senior Engineer ceiling"
    assert "Senior Engineer" in text
    assert "Associate Director" not in text
    assert "no more than 15 years" in text


def test_check_rule_text_located_ie_names_counties_when_set():
    gate = HardGate(
        gate_id="located_ie", description="stale", check="located_ie",
        params={"counties": ["Cork"]},
    )
    from gtm_client_workflows.gaia_sourcing import run as mod
    text = mod._check_rule_text(gate)
    assert text.endswith("within Cork.")
    assert "project in Ireland" in text  # the "does not count" caveat survives


def test_check_rule_text_discipline_lists_params_not_a_hardcoded_word():
    gate = HardGate(
        gate_id="discipline", description="stale", check="discipline",
        params={"include": ["transport", "highways"]},
    )
    from gtm_client_workflows.gaia_sourcing import run as mod
    text = mod._check_rule_text(gate)
    assert text == "transport, highways as the person's own discipline."


def test_check_pass_row_has_evidence_with_source_url(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    alice = next(r for r in contract["rows"] if r["name"] == "Alice Pass")
    assert alice["evidence"]
    for ev in alice["evidence"]:
        assert ev["quote"]
        assert ev["source_url"]


def test_check_out_row_names_its_failed_rules(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    carol = next(r for r in contract["rows"] if r["name"] == "Carol Out")
    assert len(carol["failed"]) == 2
    for f in carol["failed"]:
        assert f["gate_id"]
        assert f["label"]


def test_check_not_checked_row_has_no_evidence_or_failed(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    nobody = next(r for r in contract["rows"] if r["name"] == "Nobody Here")
    assert nobody["failed"] == []
    assert nobody["evidence"] == []
    assert nobody["contact"] == "unknown"


def test_check_row_person_id_matched_uses_real_pid_unmatched_uses_slug(R, run_dir, tmp_path):
    """A matched row carries the real pool person_id; an unmatched row
    carries the SAME deterministic slug extract.py would mint for that
    name (layers/intake.py::slug_for_unmatched), never a blank or a
    made-up id."""
    from gtm_client_workflows.gaia_sourcing.layers.intake import slug_for_unmatched

    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    by_name = {r["name"]: r for r in contract["rows"]}
    assert by_name["Alice Pass"]["person_id"] == "alice_pass"
    nobody = by_name["Nobody Here"]
    assert nobody["person_id"] == slug_for_unmatched("Nobody Here")
    assert nobody["person_id"] == "nobody_here"


def test_check_role_override(R, run_dir, tmp_path, monkeypatch):
    """--check-role picks a different role for every matched person."""
    from gtm_client_workflows.gaia_sourcing import run as mod

    other = _test_spec()
    other.role_id = "role2_other"
    other.hard_gates = [
        HardGate(gate_id="chartered", description="x", check="chartered"),
    ]
    monkeypatch.setattr(mod, "ROLES", {mod.ROLE1.role_id: mod.ROLE1, other.role_id: other})

    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out", check_role=other.role_id)
    assert [b["role_id"] for b in contract["brief"]] == [other.role_id]
    # Carol has no chartership claim and this brief has ONE gate -> OUT
    # with a single failed gate is impossible under the 2+-fail OUT rule,
    # so a lone-gate brief always yields either PASS or NEAR_MISS.
    carol = next(r for r in contract["rows"] if r["name"] == "Carol Out")
    assert carol["status"] == "NEAR_MISS"


def test_check_unknown_role_raises(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    with pytest.raises(SystemExit):
        R.run_check(str(input_csv), tmp_path / "out", check_role="not_a_real_role")


def test_check_requires_extract_and_validate_cached(R, tmp_path):
    input_csv = _write_input(tmp_path)
    with pytest.raises(SystemExit):
        R.run_check(str(input_csv), tmp_path / "out")


# ---------------------------------------------------------------------------
# Coordinator fix 2026-09-11 -- four items, tested directly against the
# helpers below (unit-level) plus a couple of run_check-level checks.
# ---------------------------------------------------------------------------


def test_resolve_role_alias_by_role_id(R):
    roles = {"role1_x": object(), "role2_y": object()}
    assert R._resolve_role_alias("role1_x", roles) == "role1_x"


def test_resolve_role_alias_by_positional_alias(R):
    roles = {"role1_x": object(), "role2_y": object()}
    assert R._resolve_role_alias("role1", roles) == "role1_x"
    assert R._resolve_role_alias("Role2", roles) == "role2_y"


def test_resolve_role_alias_by_title(R):
    spec = _test_spec()  # title "Test Engineer"
    roles = {spec.role_id: spec}
    assert R._resolve_role_alias("Test Engineer", roles) == spec.role_id
    assert R._resolve_role_alias("test engineer", roles) == spec.role_id


class _FakeSpec:
    def __init__(self, title: str) -> None:
        self.title = title


def test_resolve_role_alias_unresolvable_returns_none(R):
    roles = {"role1_x": _FakeSpec("X")}
    assert R._resolve_role_alias("not a role", roles) is None
    assert R._resolve_role_alias("", roles) is None
    assert R._resolve_role_alias(None, roles) is None


def test_row_role_id_precedence(R):
    roles = {"role1_x": _FakeSpec("X"), "role2_y": _FakeSpec("Y")}
    # --check-role wins over everything.
    assert R._row_role_id("role2", "role1_x", "role1_x", roles) == "role1_x"
    # CSV role column wins over the cached pool role_id.
    assert R._row_role_id("role2", "role1_x", None, roles) == "role2_y"
    # Falls back to the cached pool role_id when the column is absent/
    # unresolvable.
    assert R._row_role_id("", "role1_x", None, roles) == "role1_x"
    assert R._row_role_id("nonsense", "role1_x", None, roles) == "role1_x"


# -- item 3: reason mappings --------------------------------------------


def test_located_ie_reason_outside_republic_from_stamped_location_field(R):
    """A bare `location` field only counts as residence evidence when it
    carries provenance (`location_source` stamped) -- an unstamped value
    is the extraction model's own inference, not a residence statement."""
    person = {"location": "London, UK", "location_source": "firm_default"}
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, []
    )
    assert reason == "Based in London, outside the Republic of Ireland."
    assert bucket == "outside_republic"
    assert evidence == []


def test_located_ie_reason_unstamped_location_field_is_not_evidence(R):
    person = {"location": "London, UK", "location_source": None}
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, []
    )
    assert "Based in" not in reason
    assert bucket == "no_evidence"


def test_located_ie_reason_outside_republic_from_genuine_residence_claim(R):
    """A direct location-dimension claim shaped like an actual residence
    statement ('based in') wins even when the gate's OWN note is the
    absence-shaped 'Irish scheme work only' fallback."""
    person = {"location": "Ireland"}
    claims = [{
        "dimension": "location", "confidence": "direct",
        "evidence_quote": "He is based in London and commutes to Dublin projects.",
        "assertion": "Based in London", "source_url": "https://example.ie/p",
    }]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, claims
    )
    assert reason == "Based in London, outside the Republic of Ireland."
    assert bucket == "outside_republic"
    assert evidence and evidence[0]["quote"] == claims[0]["evidence_quote"]


def test_located_ie_reason_office_quote_is_not_a_residence_statement(R):
    """Coordinator fix 2026-09-11 (second pass): an employment-office
    quote ('joined Barrett Mahony UK in our London office') is residence-
    SHAPED by layers.gates._RESIDENCE_SHAPE_RE (an 'our X office' phrase
    is trusted evidence for the IE side of the gate too), but it states
    where the FIRM has an office, not where the person lives, so it must
    never produce 'Based in London' -- Rouslan Taskov's real shape.
    Adversarial-audit fix item 2: phrased historically, with the year the
    quote itself states."""
    person = {"location": "Ireland"}
    claims = [{
        "dimension": "location", "confidence": "direct",
        "evidence_quote": "In early 2013 he joined Barrett Mahony UK in our London office",
        "assertion": "Joined the London office", "source_url": "https://example.ie/p",
    }]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, claims
    )
    assert reason == "Joined the firm's London office in 2013; no statement of where they live."
    assert bucket == "no_evidence"
    assert len(evidence) == 1


def test_located_ie_reason_office_history_two_office_claims(R):
    """Adversarial-audit fix item 2: two or more office claims read as a
    history -- Rouslan Taskov's real shape (London 2013, Sofia 2016)."""
    person = {"location": "Ireland"}
    claims = [
        {
            "dimension": "location", "confidence": "direct",
            "evidence_quote": "In early 2013 he joined our London office",
            "assertion": "", "source_url": "https://example.ie/p1",
        },
        {
            "dimension": "location", "confidence": "direct",
            "evidence_quote": "In 2016 he established the Sofia office in Bulgaria",
            "assertion": "", "source_url": "https://example.ie/p2",
        },
    ]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, claims
    )
    assert reason == (
        "Office history: London (2013), Sofia (2016); no statement of "
        "where they live."
    )
    assert bucket == "no_evidence"
    assert len(evidence) == 2


def test_located_ie_reason_genuine_residence_wins_over_office_scanned_first(R):
    """Code-review fix 2026-09-11 item d: an office-shaped quote earlier in
    the claim list must not short-circuit before a LATER genuine residence
    statement is seen."""
    person = {"location": "Ireland"}
    claims = [
        {
            "dimension": "location", "confidence": "direct",
            "evidence_quote": "joined our London office in 2013",
            "assertion": "", "source_url": "https://example.ie/p1",
        },
        {
            "dimension": "location", "confidence": "direct",
            "evidence_quote": "He now lives in Belfast with his family.",
            "assertion": "", "source_url": "https://example.ie/p2",
        },
    ]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; irish scheme work only", None, person, claims
    )
    assert reason == "Based in Belfast, outside the Republic of Ireland."
    assert bucket == "outside_republic"


def test_located_ie_reason_project_and_market_mentions_are_not_residence(R):
    """Coordinator fix 2026-09-11 (second pass): 'experience in Ireland,
    UK, Middle East and North African markets' (Michael O'Reilly),
    'projects in Ireland and the UK' (Paul Healy) and 'experience in
    Ireland, the UK and Canada' (Pearse Sutton) are project/market
    mentions, not residence statements -- none may produce 'Based in
    <place>' regardless of which outside place they name."""
    cases = [
        ("no direct residence evidence; irish scheme work only",
         "Michael has extensive experience in Ireland, UK, Middle East "
         "and North African markets.",
         "No statement of where they live was found; only Irish project work."),
        ("Evidence places this candidate outside Ireland.",
         "has been responsible for the successful delivery of a wide "
         "range of structural projects in Ireland and the UK",
         "No statement of where they live was found."),
        ("no direct residence evidence; irish scheme work only",
         "experience in Ireland, the UK and Canada",
         "No statement of where they live was found; only Irish project work."),
    ]
    for note, quote, expected in cases:
        person = {"location": None}
        claims = [{
            "dimension": "location", "confidence": "direct",
            "evidence_quote": quote, "assertion": quote,
        }]
        reason, bucket, evidence = R._check_located_ie_reason(note, None, person, claims)
        assert "Based in" not in reason, (quote, reason)
        assert bucket == "no_evidence"
        assert reason == expected


def test_located_ie_reason_scheme_only_absence(R):
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; Irish scheme work only", None, {}, []
    )
    assert reason == "No statement of where they live was found; only Irish project work."
    assert bucket == "no_evidence"


def test_located_ie_reason_evidence_outside_ireland_note_is_mapped_not_verbatim(R):
    """The gate's own 'Evidence places this candidate outside Ireland.'
    note overclaims when the underlying quote is a project/market mention
    rather than residence -- it must never pass through verbatim."""
    reason, bucket, evidence = R._check_located_ie_reason(
        "Evidence places this candidate outside Ireland.", None, {}, []
    )
    assert reason == "No statement of where they live was found."
    assert bucket == "no_evidence"


def test_located_ie_reason_no_evidence_at_all(R):
    reason, bucket, evidence = R._check_located_ie_reason(
        "No public evidence of an Ireland-based location found.", None, {}, []
    )
    assert reason == "No statement of where they live was found."
    assert bucket == "no_evidence"


def test_located_ie_reason_never_says_not_in_ireland_when_merely_absent(R):
    reason, bucket, evidence = R._check_located_ie_reason(None, None, {}, [])
    assert "not in ireland" not in reason.lower()
    assert reason == "No statement of where they live was found."


def test_located_ie_reason_unrecognised_note_is_unclassified(R):
    """Code-review fix 2026-09-11 item f: a note this mapping doesn't
    recognise is shown verbatim but tallied as its own 'unclassified'
    bucket, never silently folded into 'no_evidence'."""
    reason, bucket, evidence = R._check_located_ie_reason(
        "Some future gate note this mapping has never seen.", None, {}, []
    )
    assert bucket == "unclassified"
    assert reason == "Some future gate note this mapping has never seen."


def _grade_claim(claim_id: str, text: str) -> ValidatedClaim:
    return ValidatedClaim(
        claim_id=claim_id, subject_person_id="p1", dimension="employer",
        assertion=text, evidence_quote=text, source_doc_id="d1",
        source_url="https://example.ie/p", confidence="direct",
        quote_verified=True,
    )


def test_seniority_ceiling_reason_stated_title(R):
    person = Person(person_id="p1", full_name="Test Person", current_title="Director")
    reason, evidence, resolved = R._check_seniority_ceiling_reason(
        "Title 'Director' is above the brief ceiling (senior_engineer)",
        person, [], "Senior Engineer",
    )
    assert reason == "Director grade, above the Senior Engineer ceiling."
    assert evidence == []
    assert resolved is None


def test_seniority_ceiling_reason_empty_title_resolves_grade_from_claim(R):
    """Adversarial-audit fix 2026-09-11 item 1: current_title is None but
    the gate's basis is a claim whose quote plainly states the grade --
    Gerry Healy's real shape ('I am a Senior Associate Director of
    Highways in Jacobs.')."""
    person = Person(person_id="p1", full_name="Gerry Healy", current_title=None)
    claims = [_grade_claim(
        "clm_grade", "I am a Senior Associate Director of Highways in Jacobs."
    )]
    reason, evidence, resolved = R._check_seniority_ceiling_reason(
        "Title '' is above the brief ceiling (senior_engineer)",
        person, claims, "Senior Engineer",
    )
    assert reason == (
        "Associate Director grade, stated in public evidence, above the "
        "Senior Engineer ceiling."
    )
    assert "above the" in reason.lower()  # this IS a positive statement
    assert len(evidence) == 1
    assert evidence[0]["quote"] == claims[0].evidence_quote
    assert resolved == "Associate Director"


def test_seniority_ceiling_reason_empty_title_no_claim_either_never_says_above_the_ceiling(R):
    person = Person(person_id="p1", full_name="Nobody Known", current_title=None)
    reason, evidence, resolved = R._check_seniority_ceiling_reason(
        "Title '' is above the brief ceiling (senior_engineer)",
        person, [], "Senior Engineer",
    )
    assert reason == (
        "Grade not stated anywhere public; cannot be confirmed under the "
        "Senior Engineer ceiling."
    )
    assert "above the" not in reason.lower()
    assert evidence == []


def test_seniority_ceiling_reason_non_grade_note_passed_through(R):
    """A years-evidenced ceiling failure is already a self-contained,
    honest sentence -- shown as the gate wrote it, never reinterpreted as
    a grade statement."""
    person = Person(person_id="p1", full_name="Test Person")
    reason, evidence, resolved = R._check_seniority_ceiling_reason(
        "Evidenced at 26 years' experience, above the 25-year ceiling.",
        person, [], "Senior Engineer",
    )
    assert reason == "Evidenced at 26 years' experience, above the 25-year ceiling."
    assert resolved is None


# -- item 4: contact status ----------------------------------------------


def test_contact_status_contact_json_wins_over_csv(R):
    assert R._check_contact_status({"email_status": "verified"}, "none") == "verified"


def test_contact_status_csv_fallback_when_no_contact_record(R):
    assert R._check_contact_status(None, "verified") == "verified"
    assert R._check_contact_status(None, "catch_all") == "catch_all"
    assert R._check_contact_status(None, "inferred") == "guess"
    assert R._check_contact_status(None, "pattern_guess") == "guess"
    assert R._check_contact_status(None, "none") == "none"
    assert R._check_contact_status(None, "") == "unknown"
    assert R._check_contact_status(None, "garbage") == "unknown"


# -- end to end: role column + contact_status column via a tiny CSV ------


def test_check_role_column_and_contact_status_column_end_to_end(R, run_dir, tmp_path):
    """Bob (role column says 'role1', matching his pool role_id -- a no-op
    override here, but exercises the same code path) gets his CSV
    contact_status honoured because contact.json has no entry for him."""
    input_csv = tmp_path / "input_roles.csv"
    input_csv.write_text(
        "name,employer,title,role,contact_status\n"
        "Alice Pass,Acme Engineering,Engineer,role1,inferred\n"
        "Bob Nearmiss,Acme Engineering,Engineer," + R1 + ",catch_all\n",
        encoding="utf-8",
    )
    contract = R.run_check(str(input_csv), tmp_path / "out")
    by_name = {r["name"]: r for r in contract["rows"]}
    assert by_name["Alice Pass"]["contact"] == "guess"
    assert by_name["Bob Nearmiss"]["contact"] == "catch_all"


# ---------------------------------------------------------------------------
# Code-review fixes 2026-09-11 (Opus pass)
# ---------------------------------------------------------------------------


def test_check_never_mutates_module_level_roles(tmp_path, monkeypatch):
    """item b: run_check builds a LOCAL deep copy of ROLES -- the
    module-level ROLE1/ROLE2 objects the rest of the pipeline shares must
    be unchanged after a --check invocation, override flags included."""
    from gtm_client_workflows.gaia_sourcing import run as mod
    from gtm_client_workflows.gaia_sourcing.core import providers
    from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

    monkeypatch.setattr(mod, "RUN_DIR", tmp_path)

    def _no_provider(*a, **k):
        raise AssertionError("--check must never call a provider")

    monkeypatch.setattr(providers, "call_role", _no_provider)
    providers.reset_spend()

    persons = {"alice_pass": _person("alice_pass", "Alice Pass")}
    persons["alice_pass"]["role_id"] = ROLE1.role_id
    claims = [
        _claim("alice_pass", "c1", "chartership", "Alice is CEng MIEI",
               "Alice is CEng MIEI with Engineers Ireland"),
    ]
    (tmp_path / "extract.json").write_text(json.dumps({"persons": persons}), encoding="utf-8")
    (tmp_path / "validate.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")

    def snapshot():
        return json.dumps(
            [g.model_dump() for g in ROLE1.hard_gates]
            + [g.model_dump() for g in ROLE2.hard_gates],
            sort_keys=True, default=str,
        )

    before = snapshot()
    input_csv = tmp_path / "in.csv"
    input_csv.write_text("name\nAlice Pass\n", encoding="utf-8")
    mod.run_check(
        str(input_csv), tmp_path / "out", max_grade="senior_engineer",
        max_years=15, strict_location=True,
    )
    assert snapshot() == before, "run_check must never mutate ROLE1/ROLE2 in place"


def test_check_summary_duplicates_dropped(R, run_dir, tmp_path):
    input_csv = tmp_path / "in.csv"
    input_csv.write_text(
        "name,employer\nAlice Pass,Acme Engineering\nalice   pass,Acme Engineering\n",
        encoding="utf-8",
    )
    contract = R.run_check(str(input_csv), tmp_path / "out")
    assert contract["summary"]["duplicates_dropped"] == 1
    assert contract["summary"]["submitted"] == 1


def test_check_summary_duplicates_dropped_zero_when_none(R, run_dir, tmp_path):
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    assert contract["summary"]["duplicates_dropped"] == 0


def test_residence_split_sums_to_located_ie_by_rule(R, run_dir, tmp_path):
    """item f: outside_republic + no_evidence + unclassified must always
    equal by_rule['located_ie'] -- every located_ie failure lands in
    exactly one bucket."""
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    residence = contract["summary"]["residence"]
    total = (
        residence["outside_republic"] + residence["no_evidence"]
        + residence["unclassified"]
    )
    assert total == contract["summary"]["by_rule"].get("located_ie", 0)


def test_synthetic_not_client_reason_when_client_side_but_gate_passed(R, tmp_path):
    """item g: is_client_side() and the not_client GATE's off-limits-
    employer list are different checks -- a client-side person (Transport
    Infrastructure Ireland) whose employer never appears on the
    not_client gate's own off-limits list still reads OUT, and must name
    a rule rather than an empty failed[] list."""
    persons = {
        "dave_client": _person(
            "dave_client", "Dave Client", employer="Transport Infrastructure Ireland"
        ),
    }
    claims = [
        _claim("dave_client", "c1", "chartership", "Dave is CEng MIEI",
               "Dave is CEng MIEI with Engineers Ireland"),
        _claim("dave_client", "c2", "location", "Based in Dublin",
               "Dave is based in Dublin, Ireland"),
    ]
    (tmp_path / "extract.json").write_text(json.dumps({"persons": persons}), encoding="utf-8")
    (tmp_path / "validate.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")
    input_csv = tmp_path / "in.csv"
    input_csv.write_text(
        "name,employer\nDave Client,Transport Infrastructure Ireland\n", encoding="utf-8",
    )
    contract = R.run_check(str(input_csv), tmp_path / "out")
    dave = contract["rows"][0]
    assert dave["status"] == "OUT"
    assert any(f["gate_id"] == "not_client" for f in dave["failed"])
    reason = next(f["reason"] for f in dave["failed"] if f["gate_id"] == "not_client")
    assert reason == "Currently employed by the client."


def test_not_checked_one_line_exact_wording(R, run_dir, tmp_path):
    """item i: exact match with render/check_page.py's own JS constant."""
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    nobody = next(r for r in contract["rows"] if r["name"] == "Nobody Here")
    assert nobody["one_line"] == (
        "Not checked yet. A new name takes one working day and comes "
        "back with the same proof lines."
    )


def test_not_checked_one_line_ambiguous_appends_sentence(R, tmp_path):
    persons = {
        "j1": _person("j1", "John Smith", employer="Acme"),
        "j2": _person("j2", "John Smith", employer="Beta"),
    }
    (tmp_path / "extract.json").write_text(json.dumps({"persons": persons}), encoding="utf-8")
    (tmp_path / "validate.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    input_csv = tmp_path / "in.csv"
    input_csv.write_text("name\nJohn Smith\n", encoding="utf-8")
    contract = R.run_check(str(input_csv), tmp_path / "out")
    row = contract["rows"][0]
    assert row["one_line"] == (
        "Not checked yet. A new name takes one working day and comes back "
        "with the same proof lines. Two people share this name."
    )


def _ceiling_spec(role_id: str) -> JobSpec:
    return JobSpec(
        role_id=role_id, title="X", client="Gaia Talent", locations=["Ireland"],
        target_count=5, primary_signal_dimension="technical_skill",
        hard_gates=[
            HardGate(gate_id="seniority_ceiling", description="x",
                      check="seniority_ceiling",
                      params={"max_grade": "principal_or_associate", "max_years": 18}),
        ],
    )


def test_brief_overrides_carry_source_tags(R):
    """item a: each override param is tagged with WHERE it came from --
    'cli' for an explicit flag, 'check_default' for Role 1's promised-
    brief default, 'brief_default' for an untouched roles.py baseline."""
    local_roles = {"role1_x": _ceiling_spec("role1_x"), "role2_y": _ceiling_spec("role2_y")}
    sources = R._apply_check_overrides(
        local_roles, max_grade="director", max_years=None, min_years=None,
        counties=None, strict_location=False, lenient_location=False,
        role1_id="role1_x",
    )
    role1_overrides = R._brief_overrides_in_force(local_roles["role1_x"], sources["role1_x"])
    role2_overrides = R._brief_overrides_in_force(local_roles["role2_y"], sources["role2_y"])
    # max_grade was passed explicitly -> "cli" for BOTH roles (flags are
    # global, per _apply_brief_overrides' existing semantics).
    assert role1_overrides["max_grade"] == {"value": "director", "source": "cli"}
    assert role2_overrides["max_grade"] == {"value": "director", "source": "cli"}
    # max_years was NOT passed -> Role 1 gets the check_default (15),
    # Role 2 keeps roles.py's own baseline (18, untouched -- brief_default).
    assert role1_overrides["max_years"] == {"value": 15, "source": "check_default"}
    assert role2_overrides["max_years"] == {"value": 18, "source": "brief_default"}


def test_apply_check_overrides_role1_only_default_when_no_flags(R):
    """item a/2: with no explicit flags at all, Role 1 defaults to the
    promised brief (senior_engineer/15/strict); Role 2 is untouched."""
    local_roles = {"role1_x": _ceiling_spec("role1_x"), "role2_y": _ceiling_spec("role2_y")}
    R._apply_check_overrides(
        local_roles, max_grade=None, max_years=None, min_years=None,
        counties=None, strict_location=False, lenient_location=False,
        role1_id="role1_x",
    )
    role1_gate = local_roles["role1_x"].hard_gates[0]
    role2_gate = local_roles["role2_y"].hard_gates[0]
    assert role1_gate.params["max_grade"] == "senior_engineer"
    assert role1_gate.params["max_years"] == 15
    assert role2_gate.params["max_grade"] == "principal_or_associate"
    assert role2_gate.params["max_years"] == 18


def test_near_miss_one_line_states_actual_reason_not_generic_template(R, run_dir, tmp_path):
    """Coordinator fix 2026-09-11 (third pass): the NEAR_MISS one_line
    states the single failed rule's own reason, lower-cased at the front
    (proper nouns/grade words kept capitalised), trailing full stop
    dropped, '; everything else passes.' appended -- never the old
    generic 'Near miss: only X missing.' template."""
    input_csv = _write_input(tmp_path)
    contract = R.run_check(str(input_csv), tmp_path / "out")
    bob = next(r for r in contract["rows"] if r["name"] == "Bob Nearmiss")
    assert bob["status"] == "NEAR_MISS"
    reason = bob["failed"][0]["reason"]
    assert bob["one_line"] == "Near miss: " + reason[0].lower() + reason[1:-1] + "; everything else passes."
    assert "Near miss: only" not in bob["one_line"]


def test_lower_first_unless_grade_word_keeps_grade_words_capitalised(R):
    assert R._lower_first_unless_grade_word(
        "Evidenced at 26 years' experience, above the 25-year ceiling."
    ) == "evidenced at 26 years' experience, above the 25-year ceiling."
    assert R._lower_first_unless_grade_word(
        "Director grade, stated in public evidence, above the Associate "
        "Director ceiling."
    ) == (
        "Director grade, stated in public evidence, above the Associate "
        "Director ceiling."
    )
    assert R._lower_first_unless_grade_word(
        "Associate Director grade, above the Senior Engineer ceiling."
    ) == "Associate Director grade, above the Senior Engineer ceiling."
    assert R._lower_first_unless_grade_word("") == ""


# ---------------------------------------------------------------------------
# Second adversarial audit, 2026-09-11
# ---------------------------------------------------------------------------


def _seniority_spec(role_id: str) -> JobSpec:
    return JobSpec(
        role_id=role_id, title="X", client="Gaia Talent", locations=["Ireland"],
        target_count=5, primary_signal_dimension="technical_skill",
        hard_gates=[
            HardGate(gate_id="seniority", description="x", check="seniority_years",
                      params={"min_years": 8}),
        ],
    )


def test_failed_rec_attaches_basis_claim_evidence_for_years_ceiling_failure(R):
    """item 1: Gerry Healy's real shape -- a seniority_ceiling failure via
    the YEARS-evidenced branch (not the grade branch) still carries a
    basis claim, and it must land in the row's evidence, generalised
    across every gate rather than hand-added per branch."""
    from gtm_client_workflows.gaia_sourcing.core.contracts import GateResult

    spec = _ceiling_spec("role1_x")
    person_obj = Person(person_id="p1", full_name="Gerry Healy", current_title=None)
    claim = _grade_claim(
        "clm_years", "I confirm that I have over 26 years post graduate experience"
    ).model_copy(update={"dimension": "years_experience"})
    g = GateResult(
        gate_id="seniority_ceiling", passed=False, basis="clm_years",
        note="Evidenced at 26 years' experience, above the 25-year ceiling.",
    )
    rec, bucket, extra_evidence, resolved_title = R._check_failed_rec(
        g, spec, {}, [claim.model_dump()], person_obj, [claim],
    )
    assert rec["reason"] == "Evidenced at 26 years' experience, above the 25-year ceiling."
    assert len(extra_evidence) == 1
    assert extra_evidence[0]["quote"] == claim.evidence_quote


def test_failed_rec_generalised_basis_evidence_for_any_gate(R):
    """item 1, generalised: a discipline-gate failure's basis claim also
    lands in evidence, not just seniority_ceiling/located_ie."""
    from gtm_client_workflows.gaia_sourcing.core.contracts import GateResult

    spec = _ceiling_spec("role1_x")
    person_obj = Person(person_id="p1", full_name="Test Person")
    claim = _grade_claim("clm_disc", "Qualified town planner").model_copy(
        update={"dimension": "sector"}
    )
    g = GateResult(
        gate_id="discipline", passed=False, basis="clm_disc",
        note="Evidence indicates an excluded discipline: town planner",
    )
    rec, bucket, extra_evidence, resolved_title = R._check_failed_rec(
        g, spec, {}, [claim.model_dump()], person_obj, [claim],
    )
    assert len(extra_evidence) == 1
    assert extra_evidence[0]["quote"] == claim.evidence_quote


def test_passed_with_note_appears_in_row_and_one_line_suffix(R, tmp_path):
    """item 2: a gate that passed WITH a note (a confirm-on-first-call
    caveat) is surfaced on the row, and a NEAR_MISS one_line names how
    many such notes exist."""
    persons = {"eve_note": _person("eve_note", "Eve Note")}
    claims = [
        _claim("eve_note", "c1", "employer", "Works on an Irish scheme",
               "Eve worked on the N6 Galway scheme in Ireland"),
    ]
    (tmp_path / "extract.json").write_text(json.dumps({"persons": persons}), encoding="utf-8")
    (tmp_path / "validate.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")
    input_csv = tmp_path / "in.csv"
    input_csv.write_text("name\nEve Note\n", encoding="utf-8")
    # --lenient-location, explicit: --check's own Role-1 "no flags"
    # default otherwise forces require_direct_evidence -- this test wants
    # the scheme-fallback PASS-with-note path, not that stricter default.
    contract = R.run_check(str(input_csv), tmp_path / "out", lenient_location=True)
    row = contract["rows"][0]
    assert row["status"] == "NEAR_MISS"  # fails chartered only; located_ie passes with a note
    assert len(row["passed_with_note"]) == 1
    assert row["passed_with_note"][0]["gate_id"] == "located_ie"
    assert row["one_line"].endswith("everything else passes, 1 with a note.")


def test_check_rule_text_located_ie_pass_with_note_wording():
    """item 2: Role 2's exact wording when treat_unknown_as is
    pass_with_note."""
    gate = HardGate(
        gate_id="located_ie", description="stale", check="located_ie",
        params={"counties": ["Cork"], "treat_unknown_as": "pass_with_note"},
    )
    from gtm_client_workflows.gaia_sourcing import run as mod
    text = mod._check_rule_text(gate)
    assert text == (
        "Lives in the Republic of Ireland, within Cork; until the rule is "
        "set, Irish scheme or client work is accepted with a "
        "confirm-on-first-call note."
    )


def test_located_ie_reason_scheme_only_employer_basis_says_firms_office(R):
    """item 3: an employer/office-shaped basis claim -> firm's Irish
    office, never generic 'Irish project work' (Pat Brady's real shape)."""
    claims = [{
        "claim_id": "c1", "dimension": "employer", "confidence": "direct",
        "evidence_quote": "first joined the Cork office of Horganlynch in 1990",
        "assertion": "Joined the Cork office", "source_url": "https://example.ie/p",
    }]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; Irish scheme work only", "c1", {}, claims,
    )
    assert reason == "No statement of where they live was found; only the firm's Irish office."
    assert bucket == "no_evidence"
    assert evidence and evidence[0]["quote"] == claims[0]["evidence_quote"]


def test_located_ie_reason_scheme_only_project_basis_says_irish_project_work(R):
    """item 3: a project/statutory_process basis claim keeps the existing
    'Irish project work' wording."""
    claims = [{
        "claim_id": "c2", "dimension": "project", "confidence": "direct",
        "evidence_quote": "worked on the N6 Galway City Ring Road scheme",
        "assertion": "Worked on N6 scheme", "source_url": "https://example.ie/p",
    }]
    reason, bucket, evidence = R._check_located_ie_reason(
        "no direct residence evidence; Irish scheme work only", "c2", {}, claims,
    )
    assert reason == "No statement of where they live was found; only Irish project work."
    assert bucket == "no_evidence"


def test_seniority_floor_unverified_years_suffix(R):
    """item 5: factual suffix when a years claim exists in extract.json
    but never survived L6 quote validation."""
    reason = R._check_seniority_floor_reason(
        "No public evidence of 10+ years' experience found.", True,
    )
    assert reason == (
        "No stated years-of-experience figure was found (the check does "
        "not infer years from join dates). (a years figure exists in the "
        "source but could not be verified character by character)"
    )


def test_seniority_floor_no_suffix_when_verified_or_absent(R):
    reason = R._check_seniority_floor_reason(
        "No public evidence of 10+ years' experience found.", False,
    )
    assert "years figure exists" not in reason


def test_run_check_unverified_years_end_to_end(R, tmp_path, monkeypatch):
    """item 5, end to end: extract.json carries a years_experience claim
    for this person that never made it into validate.json."""
    from gtm_client_workflows.gaia_sourcing import run as mod

    spec = _seniority_spec(R1)
    monkeypatch.setattr(mod, "ROLE1", spec)
    monkeypatch.setattr(mod, "ROLES", {spec.role_id: spec})

    persons = {"sam_unverified": _person("sam_unverified", "Sam Unverified")}
    extract_data = {
        "persons": persons,
        "claims": [{
            "claim_id": "yc1", "subject_person_id": "sam_unverified",
            "dimension": "years_experience", "assertion": "Over 20 years",
            "evidence_quote": "a phrase that never validated",
            "source_doc_id": "d1", "source_url": "https://example.ie/p",
            "confidence": "direct",
        }],
    }
    (tmp_path / "extract.json").write_text(json.dumps(extract_data), encoding="utf-8")
    (tmp_path / "validate.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    input_csv = tmp_path / "in.csv"
    input_csv.write_text("name\nSam Unverified\n", encoding="utf-8")
    contract = mod.run_check(str(input_csv), tmp_path / "out")
    row = contract["rows"][0]
    seniority_fail = next(f for f in row["failed"] if f["gate_id"] == "seniority")
    assert seniority_fail["reason"].endswith(
        "(a years figure exists in the source but could not be verified "
        "character by character)"
    )
