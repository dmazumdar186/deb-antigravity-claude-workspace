"""2026-11-16: a zero-candidate run must not touch (blank) the Top Matches tab."""
from unittest import mock

from execution.personal_workflows.job_search_v2.notifier import sheet


def test_zero_candidates_never_opens_sheet():
    with mock.patch.object(sheet, "_open_sheet") as opener:
        n, ok = sheet.refresh_top_matches([], ranked_by_hash={}, dry_run=False)
    assert (n, ok) == (0, True)
    opener.assert_not_called()  # nothing written -> previous rows survive


def test_with_candidates_still_opens_sheet():
    """Positive control: a run WITH candidates must still reach the sheet."""
    job = mock.Mock(content_hash="h1")
    ranked = mock.Mock(score=0.9)
    ranked.tier.value = "A"
    with mock.patch.object(sheet, "_open_sheet", return_value=(None, "no creds")) as opener:
        n, ok = sheet.refresh_top_matches([job], ranked_by_hash={"h1": ranked}, dry_run=False)
    opener.assert_called_once()
    assert (n, ok) == (0, False)
