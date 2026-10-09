"""Unit tests for instantly_campaign_cleanup (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "execution" / "infrastructure"))
from instantly_campaign_cleanup import (  # noqa: E402
    bounced_domains, is_engaged, read_csv_column, select_deletions,
)


def test_allowlist_filtering_case_insensitive():
    leads = [{"id": "1", "email": "Keep@A.com"}, {"id": "2", "email": "drop@b.com"},
             {"id": "3"}, {"id": "4", "email": ""}]
    doomed, spared = select_deletions(leads, {"keep@a.com"}, set())
    assert [lead["id"] for lead in doomed] == ["2"] and spared == 0


def test_also_remove_overrides_allowlist():
    doomed, _ = select_deletions([{"id": "1", "email": "x@a.com"}], {"x@a.com"}, {"x@a.com"})
    assert len(doomed) == 1


def test_spare_replied_and_interested():
    leads = [{"id": "1", "email": "r@b.com", "reply_count": 2},
             {"id": "2", "email": "i@b.com", "lt_interest_status": 1},
             {"id": "3", "email": "n@b.com", "lt_interest_status": -1},
             {"id": "4", "email": "z@b.com", "reply_count": 0}]
    doomed, spared = select_deletions(leads, set(), set())
    assert spared == 2 and [lead["id"] for lead in doomed] == ["3", "4"]
    assert not is_engaged({"lt_interest_status": "bad"})


def test_csv_and_domains(tmp_path):
    f = tmp_path / "k.csv"
    f.write_text("email,status\nA@X.com,valid\n,\n", encoding="utf-8")
    assert read_csv_column(f, "Email") == {"a@x.com"}
    assert bounced_domains({"a@x.com", "b@X.com", "@bad.com"}) == ["x.com"]
