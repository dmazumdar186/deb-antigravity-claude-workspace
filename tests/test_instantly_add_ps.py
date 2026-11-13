"""Offline tests for execution/infrastructure/instantly_add_ps.py (no API calls)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from execution.infrastructure import instantly_add_ps as m  # noqa: E402


def test_appends_lowercase_ps_to_lowercase_copy():
    body = "<div>hey {{firstName}}, i built a thing.</div><div><br /></div><div>{{RANDOM | want me to? | should i?}}</div>"
    out, act = m.add_ps(body)
    assert act == "added" and out.startswith(body)
    assert out.endswith("<div><br /></div><div>" + m.LINE_LOWER + "</div>")


def test_appends_proper_case_ps_to_sentence_case_copy():
    out, act = m.add_ps("<div>Hi {{firstName}},</div><div><br /></div><div>Want me to run it?</div>")
    assert act == "added" and out.endswith(m.LINE_PROPER + "</div>")
    assert "I'll stop following up." in m.LINE_PROPER and m.LINE_PROPER.startswith("{{RANDOM|P.S.|PS.}} if this isn't ")


def test_swaps_old_optout_pps_and_keeps_guarantee_ps():
    body = ("<div>want an example?</div><div><br /></div><div>ps. if it doesn't halve your deck time, refund.</div>"
            "<div><br /></div><div>pps. if you'd rather not hear from me, just lmk and i'll stop.</div>")
    out, act = m.add_ps(body)
    assert act == "swapped"
    assert "rather not hear from me" not in out and "ps. if it doesn't halve" in out
    assert out.endswith("<div>" + m.LINE_PPS + "</div>")


def test_idempotent_rerun_is_noop():
    out, _ = m.add_ps("<div>Want me to run it?</div>")
    again, act = m.add_ps(out)
    assert act == "kept" and again == out


def test_french_body_untouched():
    body = "<div>Je peux refaire le site web de {{companyName}}.</div><div>Ça vous intéresse ?</div>"
    assert m.add_ps(body) == (body, "french")


def test_spintax_is_balanced_and_line_is_operator_text():
    for line in (m.LINE_LOWER, m.LINE_PROPER, m.LINE_PPS):
        assert line.count("{{") == line.count("}}")
        assert "and i'll stop following up." in line.lower()
    first = m.LINE_LOWER.replace("{{RANDOM|ps.|p.s.}}", "ps.").replace(
        "{{RANDOM|interesting|interesting to you|of interest}}", "interesting").replace(
        "{{RANDOM|please let me know|please just let me know|just let me know}}", "please let me know")
    assert first == "ps. if this isn't interesting, please let me know and i'll stop following up."


def test_new_sequences_counts_every_variant():
    camp = {"sequences": [{"steps": [{"variants": [{"body": "<div>Hi</div>"}, {"body": "<div>hey i</div>"}]},
                                     {"variants": [{"body": "<div>x stop following up</div>"}]}]}]}
    seqs, n = m.new_sequences(camp)
    assert n == {"kept": 1, "swapped": 0, "added": 2, "french": 0}
    assert camp["sequences"][0]["steps"][0]["variants"][0]["body"] == "<div>Hi</div>"  # input not mutated
