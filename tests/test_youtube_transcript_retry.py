"""Transcript-fetch retry/backoff tests for youtube_video_analyzer.

Audit gap: transcript fetch had no retry on transient YouTube errors
(RequestBlocked / IpBlocked / YouTubeRequestFailed / HTTPError). A single
429 used to abort the whole batch.

These tests monkeypatch youtube_transcript_api at module level and shrink
TRANSCRIPT_BASE_BACKOFF_S so the retry path runs in milliseconds.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.video import youtube_video_analyzer as mod  # noqa: E402


@pytest.fixture(autouse=True)
def _shrink_backoff(monkeypatch):
    # Make all sleeps no-ops so tests run instantly.
    monkeypatch.setattr(mod, "TRANSCRIPT_BASE_BACKOFF_S", 0.0)
    # mod imports `time` and `random` inside fetch_transcript via `import time`;
    # patch the global time.sleep to be a no-op.
    import time as _t
    monkeypatch.setattr(_t, "sleep", lambda _s: None)


def _fixture_fetched():
    """A minimal "fetched" object that the new API code-path consumes."""
    seg = SimpleNamespace(start=0.0, duration=1.0, text="hello")
    return [seg, SimpleNamespace(start=1.0, duration=1.0, text="world")]


def _patch_api(monkeypatch, side_effects):
    """Replace YouTubeTranscriptApi with a MagicMock whose `.fetch(...)` call
    consumes `side_effects` in order. Each element is either a value to return
    or an exception class instance to raise.
    """
    from youtube_transcript_api import YouTubeTranscriptApi as RealApi
    api_inst = MagicMock()
    api_inst.fetch.side_effect = side_effects
    fake_cls = MagicMock(return_value=api_inst)
    monkeypatch.setattr("youtube_transcript_api.YouTubeTranscriptApi", fake_cls)
    return api_inst


def test_transcript_success_first_try(monkeypatch):
    api = _patch_api(monkeypatch, [_fixture_fetched()])
    entries = mod.fetch_transcript("abc123")
    assert len(entries) == 2
    assert entries[0]["text"] == "hello"
    assert api.fetch.call_count == 1


def test_transcript_retries_on_request_blocked(monkeypatch):
    from youtube_transcript_api._errors import RequestBlocked
    api = _patch_api(monkeypatch, [RequestBlocked("abc123"), _fixture_fetched()])
    entries = mod.fetch_transcript("abc123")
    assert len(entries) == 2
    assert api.fetch.call_count == 2


def test_transcript_retries_on_ip_blocked(monkeypatch):
    from youtube_transcript_api._errors import IpBlocked
    api = _patch_api(monkeypatch, [IpBlocked("abc123"), _fixture_fetched()])
    entries = mod.fetch_transcript("abc123")
    assert len(entries) == 2
    assert api.fetch.call_count == 2


def test_transcript_retries_on_youtube_request_failed(monkeypatch):
    from youtube_transcript_api._errors import YouTubeRequestFailed
    # Construct via __new__ to dodge the version-dependent __init__ signature.
    err = YouTubeRequestFailed.__new__(YouTubeRequestFailed)
    err.video_id = "abc123"
    api = _patch_api(monkeypatch, [err, _fixture_fetched()])
    entries = mod.fetch_transcript("abc123")
    assert len(entries) == 2
    assert api.fetch.call_count == 2


def test_transcript_exhausts_after_max_attempts(monkeypatch):
    from youtube_transcript_api._errors import RequestBlocked
    api = _patch_api(monkeypatch, [
        RequestBlocked("abc123"),
        RequestBlocked("abc123"),
        RequestBlocked("abc123"),
    ])
    with pytest.raises(SystemExit) as exc_info:
        mod.fetch_transcript("abc123")
    assert "exhausted" in str(exc_info.value)
    assert "3 attempts" in str(exc_info.value)
    assert api.fetch.call_count == mod.TRANSCRIPT_MAX_ATTEMPTS


def test_transcript_no_retry_on_no_transcript_found(monkeypatch):
    from youtube_transcript_api._errors import NoTranscriptFound
    api = _patch_api(monkeypatch, [NoTranscriptFound("abc123", ["en"], None)])
    with pytest.raises(SystemExit) as exc_info:
        mod.fetch_transcript("abc123")
    assert "No captions available" in str(exc_info.value)
    # No retry — captions definitively don't exist.
    assert api.fetch.call_count == 1


def test_transcript_no_retry_on_transcripts_disabled(monkeypatch):
    from youtube_transcript_api._errors import TranscriptsDisabled
    api = _patch_api(monkeypatch, [TranscriptsDisabled("abc123")])
    with pytest.raises(SystemExit) as exc_info:
        mod.fetch_transcript("abc123")
    assert "No captions available" in str(exc_info.value)
    assert api.fetch.call_count == 1


def test_transcript_no_retry_on_video_unavailable(monkeypatch):
    from youtube_transcript_api._errors import VideoUnavailable
    api = _patch_api(monkeypatch, [VideoUnavailable("abc123")])
    with pytest.raises(SystemExit) as exc_info:
        mod.fetch_transcript("abc123")
    assert "unavailable" in str(exc_info.value)
    assert api.fetch.call_count == 1


def test_transcript_empty_result_raises(monkeypatch):
    api = _patch_api(monkeypatch, [[]])
    with pytest.raises(SystemExit) as exc_info:
        mod.fetch_transcript("abc123")
    assert "Empty transcript" in str(exc_info.value)
