"""Offline tests for llm_client default tier, cost ledger, budget guard and retry policy."""

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from execution.modules import llm_client


def _resp(cost=0.01, pt=100, ct=20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct, cost=cost),
    )


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        o = self.outcomes.pop(0) if self.outcomes else _resp()
        if isinstance(o, Exception):
            raise o
        return o


def _err(cls, code):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return cls("err", response=httpx.Response(code, request=req), body=None)


@pytest.fixture
def env(monkeypatch, tmp_path):
    ledger = tmp_path / "llm_ledger.jsonl"
    monkeypatch.setattr(llm_client, "_LEDGER_PATH", ledger)
    monkeypatch.setattr(llm_client, "_spent_usd", 0.0)
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    monkeypatch.delenv("LLM_BUDGET_USD", raising=False)

    def install(outcomes):
        fake = FakeClient(outcomes)
        monkeypatch.setattr(llm_client, "_get_client", lambda base_url=None: fake)
        return fake

    return SimpleNamespace(ledger=ledger, install=install)


def test_default_model_is_sonnet(env):
    fake = env.install([_resp()])
    llm_client.chat_completion("s", "u")
    assert fake.calls[0]["model"] == "anthropic/claude-sonnet-5.5"
    body = fake.calls[0]["extra_body"]
    assert body["usage"] == {"include": True}
    assert body["reasoning"] == {"effort": "low"}


def test_ledger_row_written(env):
    env.install([_resp(cost=0.0123)])
    llm_client.chat_completion("s", "u")
    rows = [json.loads(line) for line in env.ledger.read_text().splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert r["cost_usd"] == pytest.approx(0.0123)
    assert r["model"] == "anthropic/claude-sonnet-5.5"
    assert r["prompt_tokens"] == 100 and r["completion_tokens"] == 20
    assert r["base_url_host"] == "openrouter.ai"
    assert {"ts", "caller", "latency_ms"} <= set(r)


def test_estimate_when_cost_missing(env):
    env.install([_resp(cost=None, pt=1_000_000, ct=0)])
    llm_client.chat_completion("s", "u")
    assert llm_client._spent_usd == pytest.approx(3.0)


def test_budget_guard_trips_and_stops_calling(env, monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_USD", "0.02")
    fake = env.install([_resp(cost=0.015), _resp(cost=0.015), _resp()])
    llm_client.chat_completion("s", "u")
    llm_client.chat_completion("s", "u")
    with pytest.raises(llm_client.LLMBudgetExceeded, match="LLM_BUDGET_USD"):
        llm_client.chat_completion("s", "u")
    assert len(fake.calls) == 2


def test_budget_kwarg_overrides_env(env):
    fake = env.install([_resp(cost=1.0)])
    llm_client.chat_completion("s", "u", budget_usd=0.5)
    with pytest.raises(llm_client.LLMBudgetExceeded):
        llm_client.chat_completion("s", "u", budget_usd=0.5)
    assert len(fake.calls) == 1


def test_402_not_retried(env):
    fake = env.install([_err(APIStatusError, 402), _resp()])
    with pytest.raises(APIStatusError):
        llm_client.chat_completion("s", "u")
    assert len(fake.calls) == 1


def test_429_retried(env):
    fake = env.install([_err(RateLimitError, 429), _resp()])
    assert llm_client.chat_completion("s", "u") == "ok"
    assert len(fake.calls) == 2
