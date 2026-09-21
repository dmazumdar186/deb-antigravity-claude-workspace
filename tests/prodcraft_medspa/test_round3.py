"""Round-3 regression tests found by the coordinator's own day-4 mock run (2026-09-17).

Three bugs the lens sub-agents missed because nobody drafted a touch 2 end to end:
1. daily_queue skipped every touch>=2 row as "already drafted" because state_machine copies the
   previous touch's draft_subject onto the new row (the "Re:" threading source).
2. state_machine.redraft left draft_body in place, so a redrafted row was skipped the same way.
3. The needs_operator_input park flag never cleared after the operator recorded notes.loom_url.
"""
from __future__ import annotations

import json
from datetime import date

from execution.personal_workflows.prodcraft_medspa.outreach import daily_queue, state_machine

from tests.prodcraft_medspa.test_outreach import (  # noqa: E402
    FakeSettings,
    _make_business,
    _make_outreach_row,
    _make_preview,
    sender_configured,  # noqa: F401  (fixture)
)


def _notes(row: dict) -> dict:
    n = row.get("notes") or {}
    return json.loads(n) if isinstance(n, str) else dict(n)


def _touch2_row(store, business, preview, *, notes=None, draft_body=None):
    """A touch-2 row exactly as state_machine._create_next_touch leaves it: queued, due today,
    draft_subject inherited from touch 1, no draft_body."""
    return _make_outreach_row(
        store,
        business_id=business["id"],
        touch=2,
        status="queued",
        preview_id=preview["id"],
        next_touch_at=date(2026, 9, 20).isoformat(),
        draft_subject="noticed something on the site",
        draft_body=draft_body,
        notes=notes,
    )


def test_touch2_row_with_inherited_subject_is_drafted(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _touch2_row(sender_configured, business, preview)

    stats = daily_queue.run_daily_queue(sender_configured, settings, today=date(2026, 9, 20), mock=True, create_drafts=True, variant="auto")

    assert stats["drafted"] == 1, stats
    after = sender_configured.get_row("outreach", row["id"])
    assert after["status"] == "drafted"
    assert after["draft_body"]
    assert "[[LOOM URL]]" in after["draft_body"]  # no Loom recorded yet: placeholder stays, send.py parks it
    assert after["draft_subject"].startswith("Re: ")


def test_redraft_clears_body_and_keeps_subject(sender_configured):
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _make_outreach_row(
        sender_configured,
        business_id=business["id"],
        touch=2,
        status="drafted",
        preview_id=preview["id"],
        draft_subject="Re: noticed something on the site",
        draft_body="rendered body",
        gmail_draft_id="draft-1",
    )
    state_machine.redraft(sender_configured, row["id"], "operator recorded the Loom walkthrough")
    after = sender_configured.get_row("outreach", row["id"])
    assert after["status"] == "queued"
    assert after["draft_body"] is None
    assert after["gmail_draft_id"] is None
    assert after["draft_subject"] == "Re: noticed something on the site"


def test_parked_flag_self_clears_once_loom_url_recorded(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    parked = _touch2_row(sender_configured, business, preview, notes={"needs_operator_input": True})
    assert daily_queue._needs_operator_input(parked) is True

    # Operator records the Loom URL: the park flag no longer applies to the render path.
    notes = _notes(parked)
    notes["loom_url"] = "https://www.loom.com/share/abc123"
    sender_configured.update_row("outreach", parked["id"], {"notes": json.dumps(notes)})
    refreshed = sender_configured.get_row("outreach", parked["id"])
    assert daily_queue._needs_operator_input(refreshed) is False

    stats = daily_queue.run_daily_queue(sender_configured, settings, today=date(2026, 9, 20), mock=True, create_drafts=True, variant="auto")
    assert stats["drafted"] == 1, stats
    after = sender_configured.get_row("outreach", parked["id"])
    assert "loom.com/share/abc123" in after["draft_body"]
    assert "[[LOOM URL]]" not in after["draft_body"]
    assert _notes(after).get("needs_operator_input") is False


def test_lint_parked_row_stays_parked_even_with_loom_url(sender_configured):
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _touch2_row(
        sender_configured,
        business,
        preview,
        notes={
            "needs_operator_input": True,
            "lint_fail_count": daily_queue.LINT_FAIL_LIMIT,
            "loom_url": "https://www.loom.com/share/abc123",
        },
    )
    assert daily_queue._needs_operator_input(row) is True
