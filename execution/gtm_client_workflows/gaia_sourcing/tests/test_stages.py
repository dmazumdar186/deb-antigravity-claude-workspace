"""
Stage-level tests for L0 -- the code that decides WHO SHIPS.

`run.py` was at 18% after the last pass, and the untested remainder is not
evenly risky. Roughly half of it is network plumbing (harvest, deepen), but
the other half -- `_persons_and_claims`, `_shortlist`, `_delivery_set`,
`stage_gate`, `stage_validate`, `stage_poolmap` -- is pure, deterministic,
free, and decides exactly which eleven people the client receives and which
numbers appear next to them in the pool map. That half had no tests at all.

Every test here builds a complete run directory on disk and runs the real
stage function against it. Zero network, zero LLM, zero paid calls.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

R1 = ROLE1.role_id
R2 = ROLE2.role_id


# ---------------------------------------------------------------------------
# A complete, minimal run directory
# ---------------------------------------------------------------------------


@pytest.fixture
def R(tmp_path, monkeypatch):
    """`run` with every on-disk path redirected into tmp_path."""
    from gtm_client_workflows.gaia_sourcing import run as mod

    monkeypatch.setattr(mod, "RUN_DIR", tmp_path)
    monkeypatch.setattr(mod, "DOCS", tmp_path / "docs.jsonl")
    monkeypatch.setattr(mod, "LOG_DIR", tmp_path / "logs")
    return mod


def _doc(doc_id: str, text: str, url: str = "https://example.ie/p") -> RawDocument:
    return RawDocument(
        doc_id=doc_id,
        url=url,
        source_type="company_bio",
        fetched_at=date(2026, 8, 19),
        content_text=text,
        http_status=200,
    )


def _person(pid: str, name: str, role_id: str, source: str, **kw) -> dict:
    return {
        "person_id": pid,
        "full_name": name,
        "current_title": kw.get("title"),
        "current_employer": kw.get("employer"),
        "location": kw.get("location"),
        "doc_ids": kw.get("doc_ids", ["d1"]),
        "linkedin_url": kw.get("linkedin_url"),
        "role_id": role_id,
        "source": source,
    }


def _claim(pid: str, dimension: str, assertion: str, quote: str, **kw) -> dict:
    return {
        "claim_id": kw.get("claim_id", pid + "_" + dimension + "_" + quote[:8]),
        "subject_person_id": pid,
        "dimension": dimension,
        "assertion": assertion,
        "evidence_quote": quote,
        "source_doc_id": kw.get("doc_id", "d1"),
        "source_url": kw.get("url", "https://example.ie/p"),
        "confidence": kw.get("confidence", "direct"),
        "quote_verified": True,
    }


# ---------------------------------------------------------------------------
# _persons_and_claims -- the source-aware employer rule
#
# Both halves of this rule reached delivered cards as bugs, in opposite
# directions, and a test that only checks one direction would have passed
# during each of them.
# ---------------------------------------------------------------------------


def test_directory_employer_is_never_overwritten_by_a_stray_sentence(R):
    """A staff directory page belongs to the firm. The firm IS the employer.

    "...is a Director based in the Dublin office" was read as an employer and
    OVERWROTE "Barrett Mahony Consulting Engineers", so a delivered card named
    the person's employer as "Dublin office".
    """
    R.save("extract", {
        "persons": {"rt": _person("rt", "Rouslan Taskov", R1, "company_directory",
                                  employer="Barrett Mahony Consulting Engineers")},
        "claims": [],
        "extracted_doc_ids": ["d1"],
    })
    R.save("validate", {"claims": [
        _claim("rt", "employer", "Rouslan Taskov is a Director based in the "
                                 "Dublin office", "a Director based in the Dublin office"),
    ], "stats": {}})

    persons, _, _ = R._persons_and_claims()

    assert persons["rt"].current_employer == "Barrett Mahony Consulting Engineers"


def test_witness_own_words_beat_the_filename_party(R):
    """An oral-hearing document is named for the party that SUBMITTED it.

    The witness is usually that party's consultant. Susie Coyle's statement
    sits under a TII filename and opens "I am an Associate Director in
    Jacobs". Reading TII as her employer files a consultancy engineer as
    client-side and drops her for being the wrong kind of right person.
    """
    R.save("extract", {
        "persons": {"sc": _person("sc", "Susie Coyle", R2, "acp_witness_statement",
                                  employer="TII")},
        "claims": [],
        "extracted_doc_ids": ["d1"],
    })
    R.save("validate", {"claims": [
        _claim("sc", "employer", "Susie Coyle is an Associate Director in Jacobs.",
               "I am an Associate Director in Jacobs"),
    ], "stats": {}})

    persons, _, _ = R._persons_and_claims()

    assert persons["sc"].current_employer == "Jacobs"


def test_an_unparseable_employer_claim_leaves_the_known_value_alone(R):
    """Failing to parse an employer must not erase the one we already had."""
    R.save("extract", {
        "persons": {"sc": _person("sc", "Susie Coyle", R2, "acp_witness_statement",
                                  employer="TII")},
        "claims": [],
        "extracted_doc_ids": ["d1"],
    })
    R.save("validate", {"claims": [
        _claim("sc", "employer", "She leads the Structures team",
               "She leads the Structures team here"),
    ], "stats": {}})

    persons, _, _ = R._persons_and_claims()

    assert persons["sc"].current_employer == "TII"


def test_inferred_employer_claims_do_not_rewrite_identity(R):
    """I3: an `inferred` claim never renders as fact, so it cannot set identity."""
    R.save("extract", {
        "persons": {"sc": _person("sc", "Susie Coyle", R2, "acp_witness_statement",
                                  employer="TII")},
        "claims": [],
        "extracted_doc_ids": ["d1"],
    })
    R.save("validate", {"claims": [
        _claim("sc", "employer", "Susie Coyle is an Associate Director at Jacobs.",
               "an Associate Director at Jacobs", confidence="inferred"),
    ], "stats": {}})

    persons, _, _ = R._persons_and_claims()

    assert persons["sc"].current_employer == "TII"


# ---------------------------------------------------------------------------
# stage_validate -- dedup, drop-rate alarm, and its deliberate non-caching
# ---------------------------------------------------------------------------


def _two_renders_of_one_page(R) -> None:
    """The same quote for the same person, arriving via two doc_ids.

    ocsc.ie/people and www.ocsc.ie/people are two fetches of one page, and
    Firecrawl output varies enough between renders that claim_id -- a hash of
    (person, doc, quote) -- does not collapse them.
    """
    text = "Brian Murphy is a Chartered Engineer  (CEng MIEI) with the firm."
    R.save_docs([_doc("d1", text, "https://ocsc.ie/people"),
                 _doc("d2", text, "https://www.ocsc.ie/people")])
    R.save("extract", {
        "persons": {"bm": _person("bm", "Brian Murphy", R1, "company_directory",
                                  employer="O'Connor Sutton Cronin",
                                  doc_ids=["d1", "d2"])},
        "claims": [
            _claim("bm", "chartership", "Brian Murphy is chartered.",
                   "Chartered Engineer  (CEng MIEI)", claim_id="c1", doc_id="d1",
                   url="https://ocsc.ie/people"),
            _claim("bm", "chartership", "Brian Murphy is chartered.",
                   "chartered engineer (ceng miei)", claim_id="c2", doc_id="d2",
                   url="https://www.ocsc.ie/people"),
        ],
        "extracted_doc_ids": ["d1", "d2"],
    })


def test_the_same_quote_from_two_renders_counts_once(R):
    """Left alone this printed every bullet twice AND inflated the tier count.

    The primary-signal count decides A/B/C, so one piece of evidence counted
    twice could promote someone to Tier A on a single fact.
    """
    _two_renders_of_one_page(R)

    R.stage_validate()

    out = R.load("validate")
    assert len(out["claims"]) == 1
    assert out["stats"]["duplicates_collapsed"] == 1


def test_validate_recomputes_even_when_its_output_already_exists(R):
    """Not caching this stage is the fix for a real silent-staleness bug.

    validate and gate were skipped as "cached" while extract.json changed
    under them, so a run that had just extracted 174 people gated a pool built
    from 158 -- the sixteen newest, the whole of Role 2, never reached the
    shortlist.
    """
    _two_renders_of_one_page(R)
    R.save("validate", {"claims": [], "stats": {"stale": True}})

    R.stage_validate()

    out = R.load("validate")
    assert out["claims"], "a cached-looking validate.json must not be honoured"
    assert "stale" not in out["stats"]


def test_drop_rate_above_the_ceiling_is_announced(R, capsys):
    """The drop rate is the hallucination metric; crossing the ceiling is loud."""
    R.save_docs([_doc("d1", "A page that says nothing either claim quotes.")])
    R.save("extract", {
        "persons": {"bm": _person("bm", "Brian Murphy", R1, "company_directory")},
        "claims": [
            _claim("bm", "chartership", "Chartered.", "words that are not present",
                   claim_id="c1"),
        ],
        "extracted_doc_ids": ["d1"],
    })

    R.stage_validate()

    assert "DROP RATE ABOVE CEILING" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# stage_gate -- tiering, and the identity write-back the renderer depends on
# ---------------------------------------------------------------------------


def _gateable_role2_candidate(R) -> None:
    body = (
        "I am an Associate Director in Jacobs. I am a Chartered Engineer "
        "(CEng MIEI) with 18 years of experience in civil and transport "
        "infrastructure, based in Cork. I gave evidence at the oral hearing "
        "on the Environmental Impact Assessment Report for the scheme and "
        "prepared the CPO documentation."
    )
    R.save_docs([_doc("d1", body, "https://pleanala.ie/x.pdf")])
    R.save("extract", {
        "persons": {"sc": _person("sc", "Susie Coyle", R2, "acp_witness_statement",
                                  employer="TII", title="Witness")},
        "claims": [
            _claim("sc", "employer", "Susie Coyle is an Associate Director in Jacobs.",
                   "I am an Associate Director in Jacobs", claim_id="c1"),
            _claim("sc", "chartership", "She is chartered with Engineers Ireland.",
                   "I am a Chartered Engineer (CEng MIEI)", claim_id="c2"),
            _claim("sc", "years_experience", "She has 18 years of experience.",
                   "18 years of experience in civil and transport infrastructure",
                   claim_id="c3"),
            _claim("sc", "location", "She is based in Cork.",
                   "based in Cork", claim_id="c4"),
            # The discipline gate reads sector/employer/project claims and the
            # person's title -- not years_experience -- so the transport term
            # has to arrive on a dimension the gate actually looks at.
            _claim("sc", "sector", "She works in transport infrastructure.",
                   "in civil and transport infrastructure", claim_id="c7"),
            _claim("sc", "statutory_process", "She gave oral-hearing evidence.",
                   "I gave evidence at the oral hearing", claim_id="c5"),
            _claim("sc", "statutory_process", "She prepared CPO documentation.",
                   "prepared the CPO documentation", claim_id="c6"),
        ],
        "extracted_doc_ids": ["d1"],
    })


def test_gate_writes_the_corrected_employer_back_to_extract(R):
    """Without the write-back the renderer and the pipeline disagree.

    _persons_and_claims derives the employer from the person's own evidenced
    words, and the gates and the Prospeo lookup both use that corrected value.
    The renderer reads extract.json directly, so a missing write-back printed
    a blank employer for every oral-hearing candidate while the pipeline
    behind it knew perfectly well who they worked for.
    """
    _gateable_role2_candidate(R)
    R.stage_validate()

    R.stage_gate()

    assert R.load("extract")["persons"]["sc"]["current_employer"] == "Jacobs"


def test_gate_tiers_on_the_roles_primary_signal(R):
    """Two direct statutory_process claims is Tier A for Role 2."""
    _gateable_role2_candidate(R)
    R.stage_validate()

    R.stage_gate()

    assert R.load("gate")["sc"]["tier"] == "A"


def test_gate_flags_a_client_side_employer_without_excluding_it(R):
    """SPEC 2.3: the client-side sidebar, not the shortlist, and not a drop."""
    _gateable_role2_candidate(R)
    data = R.load("extract")
    data["persons"]["sc"]["current_employer"] = "Iarnrod Eireann"
    data["claims"] = [c for c in data["claims"] if c["dimension"] != "employer"]
    R.save("extract", data)
    R.stage_validate()

    R.stage_gate()

    assert R.load("gate")["sc"]["client_side"] is True


# ---------------------------------------------------------------------------
# _shortlist / _delivery_set -- ordering, caps, and the adversarial override
# ---------------------------------------------------------------------------


@pytest.fixture
def graded_pool(R):
    """Six Role 1 candidates spanning every tier and both exclusion routes."""
    persons = {}
    gate = {}
    spec = [
        ("a1", "A", 9, False, "EXCLUDED" if False else None),
        ("a2", "A", 4, False, None),
        ("b1", "B", 8, False, None),
        ("c1", "C", 7, False, None),
        ("cs", "A", 9, True, None),        # client-side: never in the 10
        ("ex", "EXCLUDED", 9, False, None),  # failed a hard gate
    ]
    for pid, tier, n, client_side, _ in spec:
        persons[pid] = _person(pid, pid.upper() + " Person", R1, "company_directory",
                               employer="Punch Consulting Engineers")
        gate[pid] = {
            "role_id": R1, "tier": tier, "gates": [], "n_claims": n,
            "client_side": client_side,
        }
    R.save("extract", {"persons": persons, "claims": [], "extracted_doc_ids": []})
    R.save("validate", {"claims": [], "stats": {}})
    R.save("gate", gate)
    return R


def test_shortlist_orders_by_tier_then_evidence_depth(graded_pool):
    order = graded_pool._shortlist()[R1]
    assert order == ["a1", "a2", "b1", "c1"]


def test_shortlist_excludes_gate_failures_and_client_side(graded_pool):
    listed = graded_pool._shortlist()[R1]
    assert "ex" not in listed, "a hard-gate failure must never be shortlisted"
    assert "cs" not in listed, "SPEC 2.3 holds client-side staff out of the 15"


def test_delivery_set_is_capped_at_the_briefs_target_count(graded_pool):
    """Role 1 is a list of ten. Eleven is a different deliverable."""
    graded_pool.save("gate", {
        **graded_pool.load("gate"),
        **{
            "f" + str(i): {"role_id": R1, "tier": "C", "gates": [], "n_claims": 1,
                           "client_side": False}
            for i in range(20)
        },
    })
    data = graded_pool.load("extract")
    for i in range(20):
        data["persons"]["f" + str(i)] = _person(
            "f" + str(i), "Filler " + str(i), R1, "company_directory")
    graded_pool.save("extract", data)

    assert len(graded_pool._delivery_set()[R1]) == ROLE1.target_count


def test_an_adversarial_demotion_reorders_delivery(graded_pool):
    """L8's verdict is what ships, not the pre-critique tier."""
    graded_pool.save("adversarial", {
        "a1": {"person_id": "a1", "role_id": R1, "tier": "C", "gates": [],
               "strengths": [], "unknowns": [], "adversarial_findings": []},
    })

    assert graded_pool._delivery_set()[R1][0] == "a2"


def test_an_adversarial_exclusion_removes_the_candidate_entirely(graded_pool):
    graded_pool.save("adversarial", {
        "a1": {"person_id": "a1", "role_id": R1, "tier": "EXCLUDED", "gates": [],
               "strengths": [], "unknowns": [], "adversarial_findings": []},
    })

    assert "a1" not in graded_pool._delivery_set()[R1]


def test_final_tier_falls_back_to_the_gate_when_l8_never_ran(graded_pool):
    """A candidate L8 skipped keeps its gate tier rather than vanishing."""
    gate = graded_pool.load("gate")
    assert graded_pool._final_tier("b1", gate, {}) == "B"
    assert graded_pool._final_tier("b1", gate, {"b1": {"tier": None}}) == "B"


# ---------------------------------------------------------------------------
# stage_poolmap -- the honest denominator (SPEC 2.2)
# ---------------------------------------------------------------------------


@pytest.fixture
def poolmap_input(R):
    persons = {
        "ok": _person("ok", "Passing Person", R2, "acp_witness_statement",
                      employer="Jacobs"),
        "near": _person("near", "Near Miss", R2, "acp_witness_statement",
                        employer="Arup"),
        "far": _person("far", "Far Miss", R2, "acp_witness_statement",
                       employer="Mott MacDonald"),
        "side": _person("side", "Client Side", R2, "acp_witness_statement",
                        employer="Transport Infrastructure Ireland"),
    }
    def g(tier, gates, client_side=False):
        return {"role_id": R2, "tier": tier, "gates": gates, "n_claims": 3,
                "client_side": client_side}

    R.save("extract", {
        "persons": persons,
        "claims": [_claim("ok", "sector", "x", "a quote about sector work")],
        "extracted_doc_ids": [],
    })
    R.save("validate", {"claims": [], "stats": {}})
    R.save("gate", {
        "ok": g("B", [{"gate_id": "chartered", "passed": True, "basis": None,
                       "note": None}]),
        "near": g("EXCLUDED", [
            {"gate_id": "chartered", "passed": True, "basis": None, "note": None},
            {"gate_id": "located_ie", "passed": False, "basis": None, "note": None},
        ]),
        "far": g("EXCLUDED", [
            {"gate_id": "chartered", "passed": False, "basis": None, "note": None},
            {"gate_id": "located_ie", "passed": False, "basis": None, "note": None},
        ]),
        "side": g("A", [{"gate_id": "chartered", "passed": True, "basis": None,
                         "note": None}], client_side=True),
    })
    return R


def test_poolmap_names_the_candidates_that_missed_by_exactly_one_gate(poolmap_input):
    """"We found nobody" is far less useful than "here is what each was missing".

    A named near-miss list is something the client can act on -- by widening
    the brief, or by asking us to verify the one open point.
    """
    poolmap_input.stage_poolmap()
    near = poolmap_input.load("poolmap")[R2]["near_misses"]

    assert any("Near Miss" in n and "located_ie" in n for n in near)
    assert not any("Far Miss" in n for n in near), "two failures is not a near miss"


def test_poolmap_keeps_client_side_out_of_the_delivered_count(poolmap_input):
    poolmap_input.stage_poolmap()
    m = poolmap_input.load("poolmap")[R2]

    assert m["delivered"] == 1
    assert any("Client Side" in s for s in m["client_side_sidebar"])
    assert not any("Client Side" in n for n in m["near_misses"])


def test_poolmap_counts_every_gate_failure_in_the_exclusion_table(poolmap_input):
    poolmap_input.stage_poolmap()
    reasons = {r["reason"]: r["count"]
               for r in poolmap_input.load("poolmap")[R2]["exclusions"]}

    assert reasons["located_ie"] == 2  # near + far
    assert reasons["chartered"] == 1   # far only


def test_poolmap_denominator_is_everyone_assessed_not_everyone_delivered(poolmap_input):
    """The pool map's job is to be the honest denominator."""
    poolmap_input.stage_poolmap()
    m = poolmap_input.load("poolmap")[R2]

    assert m["profiles_assessed"] == 4
    assert m["passed_all_gates"] == 2  # ok + side; side is sidebarred, not failed
    assert m["delivered"] < m["profiles_assessed"]


# ---------------------------------------------------------------------------
# Paid stages -- cached-unless-forced, and per-candidate failure containment
# ---------------------------------------------------------------------------


def test_a_cached_paid_stage_is_not_re_bought(graded_pool, monkeypatch):
    """A crash in stage 7 must not re-buy stages 1-6."""
    from gtm_client_workflows.gaia_sourcing.layers import contact as contact_layer

    def explode(*a, **kw):
        raise AssertionError("a cached stage must not call the paid API")

    monkeypatch.setattr(contact_layer, "enrich", explode)
    graded_pool.save("contact", {"already": "bought"})

    graded_pool.stage_contact()

    assert graded_pool.load("contact") == {"already": "bought"}


def test_force_re_buys_a_cached_stage(graded_pool, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.core.contracts import ContactRecord
    from gtm_client_workflows.gaia_sourcing.layers import contact as contact_layer

    monkeypatch.setattr(
        contact_layer, "enrich",
        lambda person, *a, **kw: ContactRecord(person_id=person.person_id),
    )
    graded_pool.save("contact", {"already": "bought"})

    graded_pool.stage_contact(force=True)

    assert "already" not in graded_pool.load("contact")


def test_one_failed_enrichment_does_not_cost_the_stage(graded_pool, monkeypatch):
    """Losing one candidate's email must not lose the other nine."""
    from gtm_client_workflows.gaia_sourcing.core.contracts import ContactRecord
    from gtm_client_workflows.gaia_sourcing.layers import contact as contact_layer

    def flaky(person, *a, **kw):
        if person.person_id == "b1":
            raise RuntimeError("prospeo exploded")
        return ContactRecord(person_id=person.person_id)

    monkeypatch.setattr(contact_layer, "enrich", flaky)

    graded_pool.stage_contact()

    out = graded_pool.load("contact")
    assert "b1" not in out
    assert {"a1", "a2", "c1"} <= set(out)


def test_a_non_compliant_draft_is_dropped_never_patched(graded_pool, monkeypatch):
    """I6 is a hard gate. A patched legal notice is the failure it prevents."""
    from gtm_client_workflows.gaia_sourcing.layers import messages as messages_layer

    seq = messages_layer.assemble("note", "subject", "body", "follow up")
    monkeypatch.setattr(messages_layer, "draft", lambda *a, **kw: seq)
    monkeypatch.setattr(
        messages_layer, "compliance_ok",
        lambda s: (False, ["Art. 14 notice missing from the email body."]),
    )

    graded_pool.stage_messages()

    assert graded_pool.load("messages") == {}


def test_a_compliant_draft_survives(graded_pool, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.layers import messages as messages_layer

    seq = messages_layer.assemble("note", "subject", "body", "follow up")
    monkeypatch.setattr(messages_layer, "draft", lambda *a, **kw: seq)

    graded_pool.stage_messages()

    assert set(graded_pool.load("messages")) == {"a1", "a2", "b1", "c1"}


def test_movability_failure_drops_one_candidate_not_the_stage(graded_pool, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.core.contracts import MovabilitySignal
    from gtm_client_workflows.gaia_sourcing.layers import movability as mov

    def flaky(person, *a, **kw):
        if person.person_id == "a1":
            raise RuntimeError("judge unavailable")
        return MovabilitySignal(person_id=person.person_id)

    monkeypatch.setattr(mov, "assess", flaky)

    graded_pool.stage_movability()

    out = graded_pool.load("movability")
    assert "a1" not in out and len(out) == 3


def test_adversarial_reviews_more_candidates_than_it_delivers(graded_pool, monkeypatch):
    """L8 runs on the shortlist, not the final ten.

    A candidate demoted out of the delivery set still needed reviewing to be
    demoted, so the critique budget is deliberately wider than the deliverable.
    """
    from gtm_client_workflows.gaia_sourcing.core.contracts import Evaluation
    from gtm_client_workflows.gaia_sourcing.layers import adversarial as adv

    seen: list[str] = []

    def fake(person, claims, spec, corpus, gate_results, tier):
        seen.append(person.person_id)
        return Evaluation(person_id=person.person_id, role_id=spec.role_id,
                          tier=tier, gates=gate_results)

    monkeypatch.setattr(adv, "critique", fake)

    graded_pool.stage_adversarial()

    assert set(seen) == {"a1", "a2", "b1", "c1"}
    assert "cs" not in seen and "ex" not in seen


# ---------------------------------------------------------------------------
# L12 wiring -- which URL gets checked for whom
# ---------------------------------------------------------------------------


def test_linkcheck_prefers_the_profile_url_and_falls_back_to_linkedin(
    graded_pool, monkeypatch
):
    from gtm_client_workflows.gaia_sourcing.layers import linkcheck as lc

    data = graded_pool.load("extract")
    data["persons"]["a1"]["profile_url"] = "https://punch.ie/team/a1"
    graded_pool.save("extract", data)
    graded_pool.save("contact", {
        "a1": {"person_id": "a1", "linkedin_url": "https://linkedin.com/in/a1"},
        "a2": {"person_id": "a2", "linkedin_url": "https://linkedin.com/in/a2"},
    })

    checked: dict[str, str | None] = {}

    def fake(pid, name, profile, evidence):
        checked[pid] = profile
        return lc.LinkReport(person_id=pid, checks=[])

    monkeypatch.setattr(lc, "check_person", fake)

    graded_pool.stage_linkcheck()

    assert checked["a1"] == "https://punch.ie/team/a1"
    assert checked["a2"] == "https://linkedin.com/in/a2"
    assert checked["c1"] is None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def cli(R, monkeypatch):
    """`main()` with every stage replaced by a recorder and no provider probe."""
    ran: list[str] = []
    monkeypatch.setattr(R, "STAGES", {
        name: (lambda force=False, _n=name: ran.append(_n))
        for name in R.ORDER
    })
    monkeypatch.setattr(R, "autoselect_plan", lambda verbose=True: "hybrid")
    return R, ran


def test_from_stage_runs_that_stage_and_everything_after(cli, monkeypatch):
    R, ran = cli
    monkeypatch.setattr("sys.argv", ["run", "--from-stage", "contact"])

    assert R.main() == 0
    assert ran == R.ORDER[R.ORDER.index("contact"):]


def test_a_comma_list_runs_exactly_those_stages_in_order(cli, monkeypatch):
    R, ran = cli
    monkeypatch.setattr("sys.argv", ["run", "--stage", "validate, gate ,poolmap"])

    R.main()
    assert ran == ["validate", "gate", "poolmap"]


def test_stage_all_runs_the_whole_order(cli, monkeypatch):
    R, ran = cli
    monkeypatch.setattr("sys.argv", ["run", "--stage", "all"])

    R.main()
    assert ran == R.ORDER


@pytest.mark.parametrize("argv", [
    ["run", "--stage", "harvest_r3"],
    ["run", "--from-stage", "harvest_r3"],
])
def test_an_unknown_stage_name_fails_loudly(cli, monkeypatch, argv):
    """A typo must stop the run, not silently do nothing and report success."""
    R, _ = cli
    monkeypatch.setattr("sys.argv", argv)

    with pytest.raises(SystemExit) as exc:
        R.main()
    assert "Unknown stage" in str(exc.value)


def test_the_provider_plan_is_chosen_before_any_stage_runs(cli, monkeypatch):
    """Without this every extraction routed to free-tier Gemini at 6.5s spacing
    despite a funded Anthropic account -- a 30-minute stage that takes six."""
    R, ran = cli
    order: list[str] = []
    monkeypatch.setattr(R, "autoselect_plan",
                        lambda verbose=True: order.append("plan") or "anthropic")
    monkeypatch.setattr(R, "STAGES", {"gate": lambda force=False: order.append("gate")})
    monkeypatch.setattr(R, "ORDER", ["gate"])
    monkeypatch.setattr("sys.argv", ["run", "--stage", "gate"])

    R.main()
    assert order == ["plan", "gate"]


# ---------------------------------------------------------------------------
# The docs store
# ---------------------------------------------------------------------------


def test_docs_survive_a_non_ascii_body(R):
    """Irish names are the whole corpus. A cp1252 write would corrupt them."""
    R.save_docs([_doc("d1", "Michael O’Reilly, Iarnród Éireann")])

    assert "O’Reilly" in R.load_docs()["d1"].content_text


def test_an_unparseable_document_line_loses_one_document_not_the_store(R):
    R.save_docs([_doc("d1", "first")])
    with R.DOCS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"doc_id": "d2", "url": "not-a-url"}) + "\n")
    R.save_docs([_doc("d3", "third")])

    assert set(R.load_docs()) == {"d1", "d3"}
