"""Unit tests for job_search_v2.normalizer.browser_fetch.

No real browser required: playwright's sync_playwright is monkeypatched with
a fake, or exercised only through the "playwright missing" / "launch failed"
paths, which never touch a real browser.
"""
from __future__ import annotations

import sys
import types

import pytest

from execution.personal_workflows.job_search_v2.normalizer import browser_fetch as bf


# ---------------------------------------------------------------------------
# browser_available()
# ---------------------------------------------------------------------------


def test_browser_available_true_when_playwright_importable():
    # playwright is installed in this sandbox.
    assert bf.browser_available() is True


def test_browser_available_false_when_playwright_missing(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright":
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert bf.browser_available() is False


# ---------------------------------------------------------------------------
# make_browser_fetcher() — playwright not importable at all
# ---------------------------------------------------------------------------


def test_make_browser_fetcher_yields_none_when_sync_playwright_import_fails(monkeypatch):
    # Simulate `from playwright.sync_api import sync_playwright` raising by
    # making the submodule import itself fail.
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with bf.make_browser_fetcher() as fetch:
        assert fetch is None


# ---------------------------------------------------------------------------
# make_browser_fetcher() — fake sync_playwright, launch failure
# ---------------------------------------------------------------------------


class _FakePlaywrightCtx:
    def __init__(self, launch_should_fail=False):
        self.launch_should_fail = launch_should_fail
        self.stopped = False
        self.chromium = types.SimpleNamespace(launch=self._launch)
        self.launch_kwargs = None

    def _launch(self, **kwargs):
        self.launch_kwargs = kwargs
        if self.launch_should_fail:
            raise RuntimeError("no browser binary")
        return _FakeBrowser()

    def stop(self):
        self.stopped = True


class _FakeBrowser:
    def __init__(self):
        self.closed = False
        self.contexts = []

    def new_context(self, **kwargs):
        ctx = _FakeContext(**kwargs)
        self.contexts.append(ctx)
        return ctx

    def close(self):
        self.closed = True


class _FakeContext:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self.pages = []

    def new_page(self):
        page = _FakePage()
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


class _FakeResponse:
    def __init__(self, status):
        self.status = status


class _FakePage:
    def __init__(self, status=200, html="<html>ok</html>", fail_goto=False, final_url=None):
        self.status = status
        self.html = html
        self.fail_goto = fail_goto
        self._final_url = final_url
        self.closed = False
        self.default_timeout = None
        self.waited_ms = None
        self.goto_calls = []

    def set_default_timeout(self, ms):
        self.default_timeout = ms

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append((url, wait_until, timeout))
        if self.fail_goto:
            raise RuntimeError("navigation timeout")
        self._final_url = self._final_url or url
        return _FakeResponse(self.status)

    def wait_for_timeout(self, ms):
        self.waited_ms = ms

    def content(self):
        return self.html

    @property
    def url(self):
        return self._final_url

    def close(self):
        self.closed = True


def _install_fake_sync_playwright(monkeypatch, ctx: _FakePlaywrightCtx):
    fake_module = types.SimpleNamespace(sync_playwright=lambda: types.SimpleNamespace(start=lambda: ctx))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_module)
    # Make `import playwright` (the package) resolve too, so
    # `from playwright.sync_api import sync_playwright` succeeds.
    monkeypatch.setitem(sys.modules, "playwright", types.SimpleNamespace(sync_api=fake_module))


def test_make_browser_fetcher_yields_none_on_launch_failure(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=True)
    _install_fake_sync_playwright(monkeypatch, ctx)
    with bf.make_browser_fetcher() as fetch:
        assert fetch is None
    assert ctx.stopped is True  # cleaned up even though launch failed


def test_make_browser_fetcher_success_fetches_and_cleans_up(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=False)
    _install_fake_sync_playwright(monkeypatch, ctx)

    captured_browser = {}
    real_launch = ctx._launch
    ctx.chromium.launch = lambda **kw: captured_browser.setdefault("b", real_launch(**kw)) or captured_browser["b"]

    with bf.make_browser_fetcher() as fetch:
        assert fetch is not None
        status, html, final_url = fetch("https://weworkremotely.com/remote-jobs/example")
        assert status == 200
        assert html == "<html>ok</html>"
        assert final_url == "https://weworkremotely.com/remote-jobs/example"

    # Browser + playwright driver were both torn down on exit.
    assert captured_browser["b"].closed is True
    assert ctx.stopped is True


def test_make_browser_fetcher_new_context_per_url_and_closed(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=False)
    _install_fake_sync_playwright(monkeypatch, ctx)

    captured_browser = {}
    real_launch = ctx._launch
    ctx.chromium.launch = lambda **kw: captured_browser.setdefault("b", real_launch(**kw)) or captured_browser["b"]

    with bf.make_browser_fetcher() as fetch:
        fetch("https://a.example.com/1")
        fetch("https://a.example.com/2")

    browser = captured_browser["b"]
    assert len(browser.contexts) == 2
    assert all(c.closed for c in browser.contexts)
    assert all(len(c.pages) == 1 for c in browser.contexts)  # new page per URL
    assert all(p.closed for c in browser.contexts for p in c.pages)


def test_make_browser_fetcher_fetch_failure_returns_none_status(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=False)
    _install_fake_sync_playwright(monkeypatch, ctx)

    # Monkeypatch the fake browser's new_context to return a context whose
    # page.goto() raises, simulating a navigation timeout.
    real_launch = ctx._launch

    def launch_with_failing_page(**kwargs):
        browser = real_launch(**kwargs)
        orig_new_context = browser.new_context

        def new_context(**ctx_kwargs):
            context = orig_new_context(**ctx_kwargs)
            orig_new_page = context.new_page

            def new_page():
                page = orig_new_page()
                page.fail_goto = True
                return page

            context.new_page = new_page
            return context

        browser.new_context = new_context
        return browser

    ctx.chromium.launch = launch_with_failing_page

    with bf.make_browser_fetcher() as fetch:
        assert fetch is not None
        status, html, final_url = fetch("https://example.com/broken")
        assert status is None
        assert html == ""
        assert final_url == "https://example.com/broken"


def test_make_browser_fetcher_passes_executable_path_env(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=False)
    _install_fake_sync_playwright(monkeypatch, ctx)
    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

    with bf.make_browser_fetcher() as fetch:
        assert fetch is not None

    assert ctx.launch_kwargs.get("executable_path") == "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    assert ctx.launch_kwargs.get("headless") is True


def test_make_browser_fetcher_insecure_tls_env_toggles_ignore_https_errors(monkeypatch):
    ctx = _FakePlaywrightCtx(launch_should_fail=False)
    _install_fake_sync_playwright(monkeypatch, ctx)
    monkeypatch.setenv("JOB_SEARCH_V2_INSECURE_TLS", "1")
    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM_PATH", raising=False)

    captured = {}
    real_launch = ctx._launch

    def launch_capture(**kwargs):
        browser = real_launch(**kwargs)
        orig_new_context = browser.new_context

        def new_context(**ctx_kwargs):
            captured.update(ctx_kwargs)
            return orig_new_context(**ctx_kwargs)

        browser.new_context = new_context
        return browser

    ctx.chromium.launch = launch_capture

    with bf.make_browser_fetcher() as fetch:
        fetch("https://example.com/1")

    assert captured.get("ignore_https_errors") is True
    assert captured.get("locale") == "fr-FR"
