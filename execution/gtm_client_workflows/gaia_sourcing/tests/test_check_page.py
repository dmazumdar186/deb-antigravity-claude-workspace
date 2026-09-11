"""
Acceptance tests for render/check_page.py (deliverables/gaia_poc_check/PLAN.md
step 6): the Keith page must say which rule each rejected name failed, must
back every PASS with a quote and a source, and must never say the banned
words -- regardless of what the underlying data contains.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.render.check_page import (
    _JS,
    _build,
    banned_words_in,
    render_check_page,
    write_check_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "check_results_sample.json"

# Verbatim strings pulled straight from deliverables/gaia_poc_check/keith_copy.md
# -- every one of these appears character-for-character in that file.
SECTION_HEADINGS = [
    "Your 20 August list, checked.",
    "The ledger",
    "Rules applied, in plain words:",
    "Try any name from your own lists.",
    "What a wrong list costs",
    "How it fits with what you have",
    "What it is not",
    "Why this cannot come from the tools you already pay for",
]


@pytest.fixture
def results() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def page(results) -> str:
    return render_check_page(results)


def test_no_document_wrapper_tags(page):
    lowered = page.lower()
    assert "<!doctype" not in lowered
    assert "<html" not in lowered
    assert "<body" not in lowered
    assert "<head" not in lowered


def test_page_under_400kb(page):
    assert len(page.encode("utf-8")) < 400 * 1024


def test_every_section_heading_present_verbatim(page):
    for heading in SECTION_HEADINGS:
        assert heading in page, f"missing verbatim heading: {heading!r}"


def test_banned_words_absent_from_static_copy(results):
    static_only = dict(results)
    static_only["rows"] = []
    static_only["pool"] = []
    static_only["brief"] = []
    static_only["summary"] = {}
    static_only["campaign"] = ""
    static_only["input"] = {}
    assert banned_words_in(_build(static_only)) == []


def test_render_check_page_raises_valueerror_not_assert(results, monkeypatch):
    # render_check_page must RAISE ValueError (not rely on `assert`, which
    # vanishes under `python -O`) if the static-copy check ever fails.
    import gtm_client_workflows.gaia_sourcing.render.check_page as cp

    monkeypatch.setattr(cp, "banned_words_in", lambda html: ["system"])
    with pytest.raises(ValueError, match="banned word"):
        cp.render_check_page(results)


def test_banned_word_in_caller_data_does_not_raise(results):
    # A firm name, brief title, or campaign id that happens to contain a
    # banned word is real client data, not this module's copy, and must
    # never trip the check (coordinator fix 2026-09-11 item 2).
    poisoned = copy.deepcopy(results)
    poisoned["brief"][0]["title"] = "Systems Integration Engineer"
    poisoned["campaign"] = "agent-systems-pipeline-2026"
    poisoned["rows"][0]["employer"] = "Platform Systems Ltd"
    rendered = render_check_page(poisoned)  # must not raise
    assert "Systems Integration Engineer" in rendered
    assert "Platform Systems Ltd" in rendered


def test_banned_words_helper_catches_whole_words_case_insensitively():
    assert banned_words_in("We run an AI system on this Platform.") == [
        "ai", "platform", "system",
    ]
    # substrings inside longer words must not trip the whole-word check
    assert banned_words_in("Models and agents and pipelines remain untouched.") == []


def test_row_order_matches_ledger_rule(page):
    # PASS, then NEAR MISS, then OUT (Ciaran fails seniority before residence
    # in the priority order), then NOT CHECKED.
    names_in_order = ["Aoife Kinsella", "Barry Nolan", "Ciaran Whelan", "Deirdre Fahy"]
    positions = [page.index(name) for name in names_in_order]
    assert positions == sorted(positions)


def test_out_and_near_miss_rows_carry_their_one_line(results, page):
    for row in results["rows"]:
        if row["status"] in ("OUT", "NEAR_MISS"):
            assert row["one_line"] in page


def test_pass_row_has_blockquote_and_source_href(results, page):
    pass_rows = [r for r in results["rows"] if r["status"] == "PASS"]
    assert pass_rows, "fixture must have at least one PASS row"
    for row in pass_rows:
        for ev in row["evidence"]:
            assert f'&ldquo;{ev["quote"]}&rdquo;' in page
            assert f'href="{ev["source_url"]}"' in page
    assert "<blockquote>" in page


def test_arithmetic_input_ids_present(page):
    assert 'id="tv-minutes"' in page
    assert 'id="tv-names"' in page
    assert 'id="tv-rate"' in page


def test_numbers_render_without_spurious_decimals(page):
    # Fixture assumptions are 15.0 / 40.0 / 45.0 -- whole numbers must not
    # render as "15.0" etc.
    assert 'id="tv-minutes" type="number" min="0" step="1" value="15"' in page
    assert 'id="tv-names" type="number" min="0" step="1" value="40"' in page
    assert 'id="tv-rate" type="number" min="0" step="1" value="45"' in page
    assert '<span class="num tabular" id="tv-hours-week">10</span>' in page
    assert "10.00" not in page
    assert "15.0" not in page
    assert "40.0" not in page
    assert "45.0" not in page


def test_non_whole_hours_keep_two_decimals(page):
    # August list: 13 names * 15 min / 60 = 3.25, not a whole number.
    assert 'data-august-names="13">3.25<' in page


def test_eur_per_month_uses_comma_thousands_separator(page):
    # Fixture: 40 * 15 / 60 = 10 hours/week * 45 = 450/week * 52/12 = 1950.
    assert '<span id="tv-eur-month">1,950</span>' in page


def test_non_http_source_url_never_becomes_a_link(results):
    poisoned = json.loads(json.dumps(results))  # deep copy
    poisoned["rows"][0]["evidence"][0]["source_url"] = "javascript:alert(1)"
    rendered = render_check_page(poisoned)
    # never a clickable link, however the value is written
    assert 'href="javascript' not in rendered.lower()
    assert not re.search(r'<a\b[^>]*href="[^"]*javascript', rendered, re.IGNORECASE)
    # printed as plain escaped text, not suppressed outright
    assert "javascript:alert(1)" in rendered
    # the quote itself must still be present
    assert poisoned["rows"][0]["evidence"][0]["quote"] in rendered


def test_pool_json_round_trips(results, page):
    m = re.search(
        r'<script type="application/json" id="pool-data">(.*?)</script>',
        page,
        re.DOTALL,
    )
    assert m, "pool-data script tag not found"
    embedded = json.loads(m.group(1))
    assert embedded == results["pool"]


def test_contact_labels_rendered_in_words(page):
    # verified / catch_all / guess / unknown all present in the fixture
    assert "email verified" in page
    assert "catch-all domain" in page
    assert "email was a guess" in page


def test_not_checked_line_present_for_unmatched_row(page):
    assert (
        "Not checked yet. A new name takes one working day and comes back "
        "with the same proof lines." in page
    )


def test_write_check_page(tmp_path):
    out = tmp_path / "out" / "index.html"
    written = write_check_page(FIXTURE, out)
    assert written == out
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<title>Shortlist Check</title>" in content


def test_all_evidence_source_urls_present(results, page):
    for row in results["rows"]:
        for ev in row.get("evidence", []):
            assert f'href="{ev["source_url"]}"' in page


def test_how_it_fits_box_three_text_verbatim(page):
    # keith_copy.md, "How it fits with what you have", item 3 -- verbatim
    # (apostrophe rendered as the &rsquo; entity, per the rest of the page).
    assert (
        "Maddie&rsquo;s screener takes over exactly where it does today. A "
        "checked name lands in Recruit CRM as a candidate on the job, with "
        "the proof as a note, and can show in the dashboard Maddie built as "
        "one more column beside her score: checked, with the proof. "
        "Nothing sends on its own; a consultant always makes the call."
    ) in page


# ---------------------------------------------------------------------------
# Coordinator code-review fixes, 2026-09-11
# ---------------------------------------------------------------------------


def test_date_is_derived_from_generated_at_not_hardcoded(results):
    # Change generated_at to a date nowhere close to the original "11
    # September 2026" literal that used to be baked into the copy -- if any
    # hardcoded occurrence survives, this proves it.
    changed = copy.deepcopy(results)
    changed["generated_at"] = "2027-01-05T00:00:00+00:00"
    rendered = render_check_page(changed)
    assert "5 January 2027" in rendered
    assert "11 September 2026" not in rendered
    assert "11 September" not in rendered


def test_format_date_does_not_use_percent_dash_d(results):
    # "%-d" is a glibc strftime extension that raises ValueError on
    # Windows' msvcrt strftime -- the module must not depend on it.
    from gtm_client_workflows.gaia_sourcing.render.check_page import _format_date

    assert _format_date("2026-01-09T00:00:00+00:00") == "9 January 2026"
    # a malformed timestamp must not be double-escaped by the caller: this
    # returns the raw string, and callers apply e() themselves exactly once.
    assert _format_date("not-a-date") == "not-a-date"
    assert _format_date(None) == ""


def test_project_and_brief_lines_are_data_derived(results):
    # Single-role fixture: the Project line is that role's own title, not a
    # separate hardcoded string, and the Brief line is built from that
    # role's own overrides/rules.
    page_html = render_check_page(results)
    role_title = results["brief"][0]["title"]
    assert f"<dt>Project</dt><dd>{role_title}" in page_html
    assert "Senior Engineer grade" in page_html or "no higher than Senior Engineer grade" in page_html


def test_project_line_joins_multiple_brief_titles(results):
    two_role = copy.deepcopy(results)
    second = copy.deepcopy(two_role["brief"][0])
    second["role_id"] = "role2_transport_major_projects_manager"
    second["title"] = "Transport Major Projects Manager"
    two_role["brief"].append(second)
    rendered = render_check_page(two_role)
    assert (
        "Senior Structural Engineer, TOBIN / AtkinsRéalis and "
        "Transport Major Projects Manager" in rendered
    )
    # both roles' rule summaries appear, each labelled by its own title
    assert "Transport Major Projects Manager:" in rendered


def test_emails_default_prefers_assumptions_override(results):
    # item 7: time_value.assumptions.emails_written wins over
    # august_list.emails_to_unplaceable when both are present.
    overridden = copy.deepcopy(results)
    overridden["time_value"]["assumptions"]["emails_written"] = 7
    rendered = render_check_page(overridden)
    assert 'id="tv-emails" type="number" min="0" step="1" value="7"' in rendered
    assert '<span id="tv-aug-emails">7</span>' in rendered


def test_emails_default_falls_back_to_august_list(results):
    # No override present in the base fixture -> falls back to
    # august_list.emails_to_unplaceable (4).
    rendered = render_check_page(results)
    assert 'id="tv-emails" type="number" min="0" step="1" value="4"' in rendered
    assert '<span id="tv-aug-emails">4</span>' in rendered


def test_not_checked_row_one_line_is_the_contract(results, page):
    # item 5: the server-rendered NOT_CHECKED row's own one_line is what the
    # page must show -- assert against that rendered row, not against the
    # JS source's NOT_CHECKED_LINE constant.
    not_checked_rows = [r for r in results["rows"] if r["status"] == "NOT_CHECKED"]
    assert not_checked_rows, "fixture must have a NOT_CHECKED row"
    for row in not_checked_rows:
        assert row["one_line"] in page
        assert (
            row["one_line"]
            == "Not checked yet. A new name takes one working day and comes "
            "back with the same proof lines."
        )


# ---------------------------------------------------------------------------
# JS parity, exercised against a real JS engine (Node) rather than by
# reading the embedded source as text -- see the __CHECK_PAGE_TEST_HOOKS__
# hook at the bottom of check_page._JS.
# ---------------------------------------------------------------------------

_NODE = shutil.which("node")


def _run_js_hooks(calls: str) -> dict:
    """Executes check_page._JS under Node with a minimal `document` stub,
    captures the functions exposed via __CHECK_PAGE_TEST_HOOKS__, runs
    `calls` (a JS expression producing a JSON-serialisable value) against
    them, and returns the parsed result."""
    harness = (
        "globalThis.document = {"
        "  addEventListener: function(){},"
        "  getElementById: function(){ return null; },"
        "  createElement: function(){ return { set textContent(v){ this._t = v; }, "
        "get innerHTML(){ return this._t; } }; }"
        "};\n"
        "var __hooks = null;\n"
        "globalThis.__CHECK_PAGE_TEST_HOOKS__ = function(h){ __hooks = h; };\n"
        + _JS
        + "\nconsole.log(JSON.stringify((function(){ return " + calls + "; })()));\n"
    )
    proc = subprocess.run(
        [_NODE, "-e", harness],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
    )
    assert proc.returncode == 0, f"node harness failed: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(_NODE is None, reason="node not available on this machine")
def test_js_round2_and_eur_rounding_match_python():
    from gtm_client_workflows.gaia_sourcing.render.check_page import _eur, _num

    result = _run_js_hooks(
        "[__hooks.round2(13*15/60), __hooks.formatEur(1949.5), "
        "__hooks.formatEur(0.5), __hooks.formatNum(10), __hooks.formatNum(3.25)]"
    )
    js_round2, js_eur_1949_5, js_eur_0_5, js_num_10, js_num_3_25 = result
    assert js_round2 == 3.25
    assert str(js_eur_1949_5).replace(",", "") == str(_eur(1949.5)).replace(",", "")
    assert str(js_eur_0_5).replace(",", "") == str(_eur(0.5)).replace(",", "")
    assert js_num_10 == _num(10)
    assert js_num_3_25 == _num(3.25)


@pytest.mark.skipif(_NODE is None, reason="node not available on this machine")
def test_js_comma_rule_drops_only_all_post_nominal_tails():
    result = _run_js_hooks(
        "[__hooks.normaliseName('Kate FitzGerald, CEng MIEI'), "
        "__hooks.normaliseName('Smith, John'), "
        "__hooks.splitComma('Smith, John')]"
    )
    dropped, reversed_name, split_result = result
    # "CEng MIEI" is all post-nominal -> the comma tail is dropped entirely
    assert dropped == "kate fitzgerald"
    # "John" is not a post-nominal -> the comma becomes a space, not a drop
    assert reversed_name == "smith john"
    assert split_result == "Smith  John"


@pytest.mark.skipif(_NODE is None, reason="node not available on this machine")
def test_js_normalise_name_matches_python_intake(results):
    from gtm_client_workflows.gaia_sourcing.layers.intake import normalise_name

    names = [row["name"] for row in results["rows"]] + [
        "John Alcaras BSc CEng MIEI", "Michael O'Reilly", "Michael O’Reilly",
        "Anne-Marie Byrne",
    ]
    calls = "[" + ",".join(f"__hooks.normaliseName({json.dumps(n)})" for n in names) + "]"
    js_results = _run_js_hooks(calls)
    py_results = [normalise_name(n) for n in names]
    assert js_results == py_results
