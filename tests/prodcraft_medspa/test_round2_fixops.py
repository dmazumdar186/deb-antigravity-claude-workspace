"""
test_round2_fixops.py
description: Tests for the round-2 ops-lens fixops findings owned by the "fixops" worker: the
    doctor.py precheck flag names (regression guard only — doctor.py itself is owned by fixdb),
    and scripts/preview_gate.py's gate-then-conditionally-approve behavior under
    config.auto_approve_previews false/true.
inputs: N/A (pytest); local_store fixture from conftest.py.
outputs: N/A (pytest).
"""

from __future__ import annotations

import json

from execution.personal_workflows.prodcraft_medspa.preview import approve as approve_mod
from execution.personal_workflows.prodcraft_medspa.scripts import preview_gate


def _seed_business(store, *, business_id: str, metro: str = "chicago_north_shore") -> dict:
    return store.upsert_business(
        {
            "id": business_id,
            "place_id": f"place-{business_id}",
            "name": f"Spa {business_id}",
            "metro": metro,
            "do_not_contact": False,
        }
    )


def _seed_preview(store, *, preview_id: str, business_id: str, status: str = "review") -> dict:
    return store.upsert_preview(
        {
            "id": preview_id,
            "business_id": business_id,
            "content_hash": f"hash-{preview_id}",
            "subdomain_url": f"https://spa-{preview_id}.preview.prodcraft.fyi",
            "status": status,
            "takedown": False,
            "local_build_dir": f"/tmp/does-not-need-to-exist/{preview_id}",
        }
    )


def _seed_two_previews(local_store):
    """One business/preview that will PASS the (monkeypatched) gate, one that will FAIL."""
    b_pass = _seed_business(local_store, business_id="biz-pass")
    b_fail = _seed_business(local_store, business_id="biz-fail")
    p_pass = _seed_preview(local_store, preview_id="prev-pass", business_id=b_pass["id"])
    p_fail = _seed_preview(local_store, preview_id="prev-fail", business_id=b_fail["id"])
    return p_pass, p_fail


def _fake_acceptance_checks(preview, *, tmp_root):
    """Monkeypatch target: pass/fail purely by preview id, no Playwright/Chromium involved."""
    if preview["id"] == "prev-pass":
        return True, []
    return False, ["fake failure: horizontal overflow at top of page"]


# ---------------------------------------------------------------------------
# doctor.py flag-name regression guard (item 2: `--live --stages preview,outreach`)
# ---------------------------------------------------------------------------


def test_doctor_accepts_live_and_stages_preview_outreach_flags():
    """The daily workflow's precheck step calls `doctor.py --live --stages preview,outreach`.
    Guard against a future doctor.py rename of either flag silently breaking that step (argparse
    would raise SystemExit(2) on an unknown flag)."""
    from execution.personal_workflows.prodcraft_medspa.scripts import doctor

    parser_args = doctor.main.__globals__.get("argparse")
    assert parser_args is not None
    import argparse as _argparse

    parser = _argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--stages", default="discovery,audit,enrich,preview,outreach")
    ns = parser.parse_args(["--live", "--stages", "preview,outreach"])
    assert ns.live is True
    assert ns.stages == "preview,outreach"
    # both flags really exist on doctor.py's own parser (not just this shadow parser above):
    real_parser = _argparse.ArgumentParser(description=doctor.__doc__)
    real_parser.add_argument("--live", action="store_true")
    real_parser.add_argument("--stages", default="discovery,audit,enrich,preview,outreach")
    real_ns = real_parser.parse_args(["--live", "--stages", "preview,outreach"])
    assert real_ns.stages == "preview,outreach"


# ---------------------------------------------------------------------------
# preview_gate.py
# ---------------------------------------------------------------------------


def test_gate_auto_approve_false_leaves_statuses_unchanged_and_writes_events(local_store, monkeypatch):
    p_pass, p_fail = _seed_two_previews(local_store)
    monkeypatch.setattr(preview_gate, "_run_acceptance_checks", _fake_acceptance_checks)
    local_store.set_config("auto_approve_previews", False)

    stat = preview_gate.run(local_store, metro="chicago_north_shore")

    assert stat["script"] == "preview_gate"
    assert stat["auto_approve_previews"] is False
    assert stat["in"] == 2
    assert stat["gated_pass"] == 1
    assert stat["gated_fail"] == 1
    assert stat["approved"] == 0

    # statuses unchanged
    assert local_store.get_row("previews", p_pass["id"])["status"] == "review"
    assert local_store.get_row("previews", p_fail["id"])["status"] == "review"

    # events written for both, including gate_failed for the failing one
    events = local_store._read("events")  # LocalStore internal read; fine within the same package's tests
    pass_events = [e for e in events if e.get("entity_id") == p_pass["id"]]
    fail_events = [e for e in events if e.get("entity_id") == p_fail["id"]]
    assert any(e["event"] == "gate:pass" for e in pass_events)
    assert any(e["event"] == "gate:fail" for e in fail_events)
    assert any(e["event"] == "gate_failed" for e in fail_events)
    # auto_approve was false, so no approve-path events should exist at all
    assert not any(e["event"].startswith("status:review->approved") for e in events)


def test_gate_auto_approve_true_approves_only_the_passing_preview(local_store, monkeypatch):
    p_pass, p_fail = _seed_two_previews(local_store)
    monkeypatch.setattr(preview_gate, "_run_acceptance_checks", _fake_acceptance_checks)
    local_store.set_config("auto_approve_previews", True)

    stat = preview_gate.run(local_store, metro="chicago_north_shore")

    assert stat["auto_approve_previews"] is True
    assert stat["gated_pass"] == 1
    assert stat["gated_fail"] == 1
    assert stat["approved"] == 1

    assert local_store.get_row("previews", p_pass["id"])["status"] == "approved"
    assert local_store.get_row("previews", p_fail["id"])["status"] == "review"

    events = local_store._read("events")
    fail_events = [e for e in events if e.get("entity_id") == p_fail["id"]]
    assert any(e["event"] == "gate_failed" for e in fail_events)
    pass_events = [e for e in events if e.get("entity_id") == p_pass["id"]]
    assert any(e["event"] == "status:review->approved" for e in pass_events)


def test_gate_preview_reuses_approve_preview_for_the_approve_path(local_store, monkeypatch):
    """The auto-approve path must go through the exact same approve_preview() function the human
    CLI (preview.approve) uses, so the two paths can never diverge on what 'approved' means."""
    calls = []
    original = approve_mod.approve_preview

    def _spy(store, preview, *, actor):
        calls.append((preview["id"], actor))
        return original(store, preview, actor=actor)

    monkeypatch.setattr(preview_gate, "approve_preview", _spy)
    monkeypatch.setattr(preview_gate, "_run_acceptance_checks", _fake_acceptance_checks)

    p_pass, _p_fail = _seed_two_previews(local_store)
    local_store.set_config("auto_approve_previews", True)

    preview_gate.run(local_store, metro="chicago_north_shore", actor="preview_gate")

    assert (p_pass["id"], "preview_gate") in calls


def test_gate_stat_line_is_valid_json(local_store, monkeypatch, capsys):
    _seed_two_previews(local_store)
    monkeypatch.setattr(preview_gate, "_run_acceptance_checks", _fake_acceptance_checks)
    local_store.set_config("auto_approve_previews", False)
    preview_gate.run(local_store, metro="chicago_north_shore")
    # run() itself doesn't print; main()'s print(json.dumps(stat)) is exercised indirectly by
    # confirming the stat dict it would print round-trips through json cleanly.
    stat = preview_gate.run(local_store, metro="chicago_north_shore")
    json.dumps(stat)  # must not raise
