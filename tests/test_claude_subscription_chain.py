"""Offline tests for the Claude-subscription chain in llm_client (subprocess mocked)."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from execution.modules import llm_client

LIMIT_MSG = "Claude AI usage limit reached|1700000000"


def _ok(text="OK", model="claude-opus-5-5", cost=0.0123):
    return json.dumps({"is_error": False, "result": text, "total_cost_usd": cost,
                       "usage": {"input_tokens": 10, "output_tokens": 2},
                       "modelUsage": {model: {}}})


def _err(msg):
    return json.dumps({"is_error": True, "result": msg})


class FakeRun:
    """Stands in for subprocess.run; outcomes keyed by --model, popped in order."""

    def __init__(self, outcomes):
        self.outcomes = {k: list(v) for k, v in outcomes.items()}
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        model = cmd[cmd.index("--model") + 1]
        out = self.outcomes[model].pop(0)
        rc = 1 if '"is_error": true' in out else 0
        return SimpleNamespace(stdout=out, stderr="", returncode=rc)

    def models(self):
        return [c[c.index("--model") + 1] for c, _ in self.calls]


@pytest.fixture
def env(monkeypatch, tmp_path):
    ledger = tmp_path / "llm_ledger.jsonl"
    monkeypatch.setattr(llm_client, "_LEDGER_PATH", ledger)
    monkeypatch.setattr(llm_client, "_spent_usd", 0.0)
    monkeypatch.setattr(llm_client, "_exhausted", set())
    monkeypatch.setattr(llm_client.shutil, "which", lambda name: "/usr/bin/claude")
    monkeypatch.delenv("CLAUDE_VIA", raising=False)
    monkeypatch.delenv("LLM_BUDGET_USD", raising=False)

    def install(outcomes):
        fake = FakeRun(outcomes)
        monkeypatch.setattr(llm_client.subprocess, "run", fake)
        return fake

    def no_openrouter(*a, **kw):
        raise AssertionError("OpenRouter client must not be used")

    monkeypatch.setattr(llm_client, "_get_client", no_openrouter)
    return SimpleNamespace(ledger=ledger, install=install, monkeypatch=monkeypatch)


def test_opus_success(env):
    fake = env.install({"claude-opus-5-5": [_ok("OK")]})
    assert llm_client.chat_completion("s", "u", model="anthropic/claude-sonnet-5.5") == "OK"
    assert fake.models() == ["claude-opus-5-5"]
    row = json.loads(env.ledger.read_text().splitlines()[0])
    assert row["model"] == "claude-opus-5-5"
    assert row["effort"] == "medium"
    assert row["billing"] == "subscription"
    assert row["cost_usd"] is None
    assert row["notional_usd"] == pytest.approx(0.0123)


def test_opus_limit_falls_to_fable(env):
    fake = env.install({"claude-opus-5-5": [_err(LIMIT_MSG)],
                        "claude-fable-5-1": [_ok("F", "claude-fable-5-1")]})
    assert llm_client.chat_completion("s", "u", model="claude-opus-5-5") == "F"
    assert fake.models() == ["claude-opus-5-5", "claude-fable-5-1"]


def test_opus_and_fable_limit_falls_to_sonnet_high(env):
    fake = env.install({"claude-opus-5-5": [_err("You've hit your limit")],
                        "claude-fable-5-1": [_err("API Error: 529 overloaded")],
                        "claude-sonnet-5-5": [_ok("S", "claude-sonnet-5-5")]})
    assert llm_client.chat_completion("s", "u", model="anthropic/claude-fable-5.1") == "S"
    cmd = fake.calls[-1][0]
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5-5"
    assert cmd[cmd.index("--effort") + 1] == "high"


def test_all_limited_raises(env):
    env.install({"claude-opus-5-5": [_err(LIMIT_MSG)],
                 "claude-fable-5-1": [_err("rate limit exceeded")],
                 "claude-sonnet-5-5": [_err("quota exhausted")]})
    with pytest.raises(llm_client.ClaudeLimitReached):
        llm_client.chat_completion("s", "u", model="claude-sonnet-5-5")


def test_auth_error_raises_without_fallthrough(env):
    fake = env.install({"claude-opus-5-5": [_err("Invalid API key · Please run /login")]})
    with pytest.raises(RuntimeError, match="Claude CLI error") as ei:
        llm_client.chat_completion("s", "u", model="claude-opus-5-5")
    assert not isinstance(ei.value, llm_client.ClaudeLimitReached)
    assert fake.models() == ["claude-opus-5-5"]


def test_bad_json_raises(env):
    env.install({"claude-opus-5-5": ["not json at all"]})
    with pytest.raises(RuntimeError, match="no JSON"):
        llm_client.chat_completion("s", "u", model="claude-opus-5-5")


def test_missing_cli_raises(env):
    env.monkeypatch.setattr(llm_client.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Claude Code CLI not found"):
        llm_client.chat_completion("s", "u", model="claude-opus-5-5")


def test_exhausted_tier_is_sticky(env):
    fake = env.install({"claude-opus-5-5": [_err(LIMIT_MSG)],
                        "claude-fable-5-1": [_ok("1", "claude-fable-5-1"),
                                             _ok("2", "claude-fable-5-1")]})
    llm_client.chat_completion("s", "u", model="claude-opus-5-5")
    assert llm_client.chat_completion("s", "u", model="claude-opus-5-5") == "2"
    assert fake.models() == ["claude-opus-5-5", "claude-fable-5-1", "claude-fable-5-1"]


def test_non_claude_model_goes_to_openrouter(env):
    calls = []
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="gpt"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0),
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: calls.append(kw) or resp)))
    env.monkeypatch.setattr(llm_client, "_get_client", lambda base_url=None: client)
    fake = env.install({})
    assert llm_client.chat_completion("s", "u", model="openai/gpt-6.1") == "gpt"
    assert calls[0]["model"] == "openai/gpt-6.1"
    assert fake.calls == []


def test_escape_hatch_routes_claude_to_openrouter(env):
    calls = []
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="or"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0),
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: calls.append(kw) or resp)))
    env.monkeypatch.setattr(llm_client, "_get_client", lambda base_url=None: client)
    env.monkeypatch.setenv("CLAUDE_VIA", "openrouter")
    fake = env.install({})
    assert llm_client.chat_completion("s", "u", model="anthropic/claude-sonnet-5.5") == "or"
    assert calls[0]["model"] == "anthropic/claude-sonnet-5.5"
    assert fake.calls == []


def test_subscription_calls_skip_budget_guard(env):
    env.monkeypatch.setattr(llm_client, "_spent_usd", 999.0)  # far over any budget
    env.install({"claude-opus-5-5": [_ok("A", cost=50.0), _ok("B", cost=50.0)]})
    assert llm_client.chat_completion("s", "u", model="claude-opus-5-5", budget_usd=1.0) == "A"
    assert llm_client.chat_completion("s", "u", model="claude-opus-5-5", budget_usd=1.0) == "B"
    assert llm_client._spent_usd == 999.0  # notional cost never counted


def test_cli_args(env):
    fake = env.install({"claude-opus-5-5": [_ok()]})
    llm_client.chat_completion("SYS", "the prompt", model="claude-opus-5-5", max_tokens=5)
    cmd, kw = fake.calls[0]
    assert cmd[0] == "/usr/bin/claude" and "-p" in cmd
    assert "the prompt" not in cmd
    assert kw["input"] == "the prompt"
    assert kw["encoding"] == "utf-8" and kw["errors"] == "replace"
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    assert cmd[cmd.index("--effort") + 1] == "medium"
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--system-prompt") + 1] == "SYS"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--strict-mcp-config" in cmd
    assert "--no-session-persistence" in cmd
    assert "--bare" not in cmd


def test_chain_order_is_operator_order():
    assert llm_client.CLAUDE_CHAIN == (
        ("claude-opus-5-5", "medium"),
        ("claude-fable-5-1", "low"),
        ("claude-sonnet-5-5", "high"),
    )


def test_timeout_raises(env):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    env.monkeypatch.setattr(llm_client.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="timed out"):
        llm_client.chat_completion("s", "u", model="claude-opus-5-5")
