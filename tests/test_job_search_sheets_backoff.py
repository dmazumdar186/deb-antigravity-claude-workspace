"""Prove the Sheets 429 safeguard fires (2026-11-16): the client job_search_v2
uses must retry a 429 and succeed, not raise APIError on the first quota hit."""
from unittest import mock

import pytest

gspread = pytest.importorskip("gspread")
from gspread.http_client import BackOffHTTPClient  # noqa: E402
from google.auth.credentials import AnonymousCredentials  # noqa: E402


class _Resp:
    def __init__(self, code):
        self.status_code = code
        self.ok = code < 400
        self.text = "{}"
        self.reason = "x"

    def json(self):
        return {"error": {"code": self.status_code, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}


def test_backoff_client_retries_429_then_succeeds():
    responses = [_Resp(429), _Resp(429), _Resp(200)]
    client = BackOffHTTPClient(auth=AnonymousCredentials())
    client.session = mock.Mock()
    client.session.request.side_effect = lambda *a, **k: responses.pop(0)
    with mock.patch("time.sleep") as slept:
        r = client.request("get", "https://sheets.googleapis.com/v4/spreadsheets/x")
    assert r.status_code == 200
    assert slept.call_count == 2  # backed off twice, then succeeded


def test_plain_client_would_have_raised_on_429():
    """Negative control: the old default client fails on the first 429."""
    from gspread.http_client import HTTPClient
    client = HTTPClient(auth=AnonymousCredentials())
    client.session = mock.Mock()
    client.session.request.return_value = _Resp(429)
    with pytest.raises(gspread.exceptions.APIError):
        client.request("get", "https://sheets.googleapis.com/v4/spreadsheets/x")


def test_job_search_call_sites_use_backoff_client():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("execution/personal_workflows/job_search_v2/notifier/sheet.py",
                "tests/acceptance_job_search_v2.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "http_client=gspread.BackOffHTTPClient" in src, rel
        assert "gspread.authorize(creds)" not in src, rel
