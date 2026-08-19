"""
Multi-provider structured-output backend.

Why this exists: the Anthropic account is at a zero credit balance
(verified 2026-08-19, HTTP 400 "credit balance is too low"), while the
OpenRouter account holds a small balance and the Gemini free tier is
available. Per the cost-constraint clause in ~/.claude/rules/model-tier.md,
a $0 Anthropic budget routes high-volume work to Gemini 2.5 Flash and keeps
paid capacity for the judgement layers.

The pipeline is designed so this degradation is safe. L5's output is checked
character-by-character by L6 against the source document, so a weaker
extraction model cannot fabricate its way into the deliverable -- it can only
raise the drop rate. Judgement layers (L8 tiering, L11 client-facing copy)
still route to Claude, because their output is not substring-checkable.

Roles, not model names, are what callers ask for.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from .config import secret

# ---------------------------------------------------------------------------
# Role -> (provider, model) routing
# ---------------------------------------------------------------------------

ROLE_EXTRACT = "extract"   # L5: high volume, constrained copy task
ROLE_JUDGE = "judge"       # L8: adversarial critique + tiering
ROLE_MESSAGE = "message"   # L11: goes out under Gaia's name

# Default plan under a zero Anthropic balance.
ROUTING: dict[str, tuple[str, str]] = {
    ROLE_EXTRACT: ("gemini", "gemini-2.5-flash"),
    ROLE_JUDGE: ("openrouter", "anthropic/claude-opus-5"),
    ROLE_MESSAGE: ("openrouter", "anthropic/claude-opus-5"),
}

# Applied by set_plan("anthropic") once the account is funded.
PLANS: dict[str, dict[str, tuple[str, str]]] = {
    "free": {
        ROLE_EXTRACT: ("gemini", "gemini-2.5-flash"),
        ROLE_JUDGE: ("gemini", "gemini-2.5-flash"),
        ROLE_MESSAGE: ("gemini", "gemini-2.5-flash"),
    },
    "hybrid": {
        ROLE_EXTRACT: ("gemini", "gemini-2.5-flash"),
        ROLE_JUDGE: ("openrouter", "anthropic/claude-opus-5"),
        ROLE_MESSAGE: ("openrouter", "anthropic/claude-opus-5"),
    },
    "openrouter": {
        ROLE_EXTRACT: ("openrouter", "anthropic/claude-sonnet-5"),
        ROLE_JUDGE: ("openrouter", "anthropic/claude-opus-5"),
        ROLE_MESSAGE: ("openrouter", "anthropic/claude-opus-5"),
    },
    "anthropic": {
        ROLE_EXTRACT: ("anthropic", "claude-sonnet-5"),
        ROLE_JUDGE: ("anthropic", "claude-opus-5"),
        ROLE_MESSAGE: ("anthropic", "claude-opus-5"),
    },
}


def set_plan(name: str) -> None:
    global ROUTING
    if name not in PLANS:
        raise ValueError("Unknown plan: " + name + ". Options: " + ", ".join(PLANS))
    ROUTING = dict(PLANS[name])


_LOCK = threading.Lock()
_GEMINI_LAST = 0.0
# Free tier is 10 requests/minute. 6.5s nominal spacing keeps a margin, but
# the limiter is ADAPTIVE: a 429 widens the interval permanently for the rest
# of the run, and successes slowly narrow it again. A fixed interval lost 3 of
# 19 documents on the first real run, because retries after a 429 stack on top
# of the normal cadence and re-trip the same limit.
_GEMINI_MIN_INTERVAL = 6.5
_GEMINI_INTERVAL_CEILING = 30.0
_GEMINI_OK_STREAK = 0


def _gemini_penalise() -> None:
    global _GEMINI_MIN_INTERVAL, _GEMINI_OK_STREAK
    with _LOCK:
        _GEMINI_MIN_INTERVAL = min(
            _GEMINI_INTERVAL_CEILING, _GEMINI_MIN_INTERVAL * 1.6
        )
        _GEMINI_OK_STREAK = 0


def _gemini_reward() -> None:
    global _GEMINI_MIN_INTERVAL, _GEMINI_OK_STREAK
    with _LOCK:
        _GEMINI_OK_STREAK += 1
        if _GEMINI_OK_STREAK >= 8 and _GEMINI_MIN_INTERVAL > 6.5:
            _GEMINI_MIN_INTERVAL = max(6.5, _GEMINI_MIN_INTERVAL * 0.85)
            _GEMINI_OK_STREAK = 0


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def _to_gemini_schema(schema: dict) -> dict:
    """Translate a JSON Schema into Gemini's responseSchema dialect."""
    t = schema.get("type", "string")
    out: dict[str, Any] = {"type": t.upper()}
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if t == "object":
        out["properties"] = {
            k: _to_gemini_schema(v) for k, v in schema.get("properties", {}).items()
        }
        req = schema.get("required")
        if req:
            out["required"] = req
    elif t == "array":
        out["items"] = _to_gemini_schema(schema.get("items", {"type": "string"}))
    return out


def _call_gemini(
    model: str, system: str, user: str, tool: dict, max_tokens: int, temperature: float
) -> tuple[Optional[dict], dict]:
    global _GEMINI_LAST
    with _LOCK:
        wait = _GEMINI_MIN_INTERVAL - (time.time() - _GEMINI_LAST)
        if wait > 0:
            time.sleep(wait)
        _GEMINI_LAST = time.time()

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?key="
        + secret("GEMINI_API_KEY")
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "responseSchema": _to_gemini_schema(tool["input_schema"]),
        },
    }
    data = _post_json(url, payload, {"Content-Type": "application/json"})
    usage = data.get("usageMetadata", {})
    stats = {
        "input_tokens": usage.get("promptTokenCount", 0),
        "output_tokens": usage.get("candidatesTokenCount", 0),
        "cache_read_tokens": usage.get("cachedContentTokenCount", 0),
        "cache_write_tokens": 0,
    }
    cands = data.get("candidates") or []
    if not cands:
        return None, stats
    parts = cands[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        return None, stats
    try:
        return json.loads(text), stats
    except json.JSONDecodeError:
        # Truncated JSON (hit maxOutputTokens). Dropped, never repaired:
        # a partially-parsed claim list is how invented data gets in.
        return None, stats


# ---------------------------------------------------------------------------
# OpenRouter (Anthropic models, tool-use)
# ---------------------------------------------------------------------------


def _call_openrouter(
    model: str, system: str, user: str, tool: dict, max_tokens: int, temperature: float
) -> tuple[Optional[dict], dict]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool["input_schema"],
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
    }
    data = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        payload,
        {
            "Authorization": "Bearer " + secret("OPENROUTER_API_KEY"),
            "Content-Type": "application/json",
        },
    )
    u = data.get("usage", {}) or {}
    stats = {
        "input_tokens": u.get("prompt_tokens", 0),
        "output_tokens": u.get("completion_tokens", 0),
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    choices = data.get("choices") or []
    if not choices:
        return None, stats
    msg = choices[0].get("message", {})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        if fn.get("name") == tool["name"]:
            try:
                return json.loads(fn.get("arguments") or "{}"), stats
            except json.JSONDecodeError:
                return None, stats
    return None, stats


# ---------------------------------------------------------------------------
# Anthropic direct
# ---------------------------------------------------------------------------


_ANTHROPIC_CLIENT: Any = None


def _anthropic_client() -> Any:
    """One long-lived client with a generous timeout.

    Constructing a client per call opens a fresh TLS connection every time,
    which is what produced intermittent APIConnectionError on long
    directory-extraction requests. Connection reuse removes that class of
    transient failure.
    """
    global _ANTHROPIC_CLIENT
    with _LOCK:
        if _ANTHROPIC_CLIENT is None:
            import anthropic

            _ANTHROPIC_CLIENT = anthropic.Anthropic(
                api_key=secret("ANTHROPIC_API_KEY"),
                timeout=300.0,
                max_retries=2,
            )
    return _ANTHROPIC_CLIENT


def _call_anthropic(
    model: str, system: str, user: str, tool: dict, max_tokens: int, temperature: float
) -> tuple[Optional[dict], dict]:
    client = _anthropic_client()
    # `temperature` is DEPRECATED on the Claude 5 family and returns HTTP 400
    # ("`temperature` is deprecated for this model"). SPEC.md section 4 asks
    # for temperature=0 to make tiering reproducible; that guarantee now rests
    # on the model default plus forced tool use, so the determinism check in
    # the test suite matters more, not less.
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    u = resp.usage
    stats = {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
    for block in resp.content:
        if getattr(block, "type", "") == "tool_use" and block.name == tool["name"]:
            return dict(block.input), stats
    return None, stats


_BACKENDS = {
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "anthropic": _call_anthropic,
}

# Per-provider EUR pricing per MTok. Gemini free tier is genuinely 0 within
# quota; recorded as 0 so the cost ceiling reflects real spend.
PRICE_EUR: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.0, "output": 0.0},
    "anthropic/claude-sonnet-5": {"input": 1.84, "output": 9.20},
    "anthropic/claude-opus-5": {"input": 4.60, "output": 23.00},
    "claude-sonnet-5": {"input": 1.84, "output": 9.20},
    "claude-opus-5": {"input": 4.60, "output": 23.00},
}


def cost_eur(model: str, stats: dict) -> float:
    """Cache-aware, per ~/.claude/rules/python-hardening.md rule 4.

    Cache reads and writes were counted at zero while the Anthropic backend
    was collecting both, so every cached call understated its own cost. Under
    prompt caching that is most of the input on a long extraction run, and a
    ceiling fed by an understated number is not a ceiling.
    """
    p = PRICE_EUR.get(model)
    if p is None:
        p = {"input": 4.60, "output": 23.00}  # unknown: assume dearest
    inp = p["input"]
    return (
        stats.get("input_tokens", 0) * inp
        + stats.get("output_tokens", 0) * p["output"]
        + stats.get("cache_read_tokens", 0) * p.get("cache_read", inp * 0.1)
        + stats.get("cache_write_tokens", 0) * p.get("cache_write", inp * 1.25)
    ) / 1_000_000


class CostCeilingExceeded(RuntimeError):
    """The run has spent its budget and must stop rather than continue.

    Distinct from every other failure in the pipeline because it must NOT be
    contained per-item: `run_all` degrades by one item on an ordinary error,
    which for a budget breach would mean quietly burning the rest of the
    stage one contained failure at a time.
    """


_SPEND_LOCK = threading.Lock()
_SPEND_EUR = 0.0


def spend_eur() -> float:
    with _SPEND_LOCK:
        return _SPEND_EUR


def reset_spend() -> None:
    global _SPEND_EUR
    with _SPEND_LOCK:
        _SPEND_EUR = 0.0


def _record_spend(amount: float) -> float:
    global _SPEND_EUR
    with _SPEND_LOCK:
        _SPEND_EUR += amount
        return _SPEND_EUR


def call_role(
    role: str,
    system: str,
    user: str,
    tool: dict,
    max_tokens: int = 8000,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> tuple[Optional[dict], dict]:
    """Dispatch a structured-output call by ROLE. Returns (result, meta)."""
    provider, model = ROUTING[role]
    backend = _BACKENDS[provider]
    last: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            result, stats = backend(model, system, user, tool, max_tokens, temperature)
            if provider == "gemini":
                _gemini_reward()
            spent = cost_eur(model, stats)
            total = _record_spend(spent)
            meta = {
                "provider": provider,
                "model": model,
                "cost_eur": spent,
                "run_total_eur": total,
                **stats,
            }
            # SPEC.md section 14. The ceiling was declared in RunConfig and
            # enforced nowhere: the only CostTracker lived in core/llm.py,
            # which nothing imported. Every layer dutifully appended its cost
            # metadata to a RUN_COST list that nothing ever read, so a runaway
            # loop would have been invisible until the invoice arrived.
            from .config import CONFIG

            if total > CONFIG.max_cost_eur:
                raise CostCeilingExceeded(
                    "Run cost EUR " + format(total, ".2f") + " exceeds the "
                    "ceiling of EUR " + format(CONFIG.max_cost_eur, ".2f")
                    + ". Raise RunConfig.max_cost_eur deliberately, or find "
                    "the loop that is spending it."
                )
            return result, meta
        except urllib.error.HTTPError as exc:
            last = exc
            code = exc.code
            if code in (429, 500, 502, 503, 529):
                if code == 429 and provider == "gemini":
                    _gemini_penalise()
                    # Honour the server's own advice when it supplies one.
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        delay = float(retry_after) if retry_after else 0.0
                    except (TypeError, ValueError):
                        delay = 0.0
                    time.sleep(max(delay, min(90, 2 ** attempt * 12)))
                else:
                    time.sleep(min(60, 2 ** attempt * 5))
                continue
            body = b""
            try:
                body = exc.read()[:300]
            except Exception:
                pass  # error body is diagnostic only; absence must not mask `exc`
            raise RuntimeError(
                "LLM " + provider + "/" + model + " HTTP " + str(code) + ": "
                + body.decode("utf-8", errors="replace")
            ) from exc
        except CostCeilingExceeded:
            # Never retried and never wrapped. The generic handler below would
            # otherwise sleep and retry a budget breach three times, then
            # re-raise it as an ordinary RuntimeError that run_all contains
            # per-item -- turning "stop, you are over budget" into "spend the
            # rest of the stage one contained failure at a time".
            raise
        except Exception as exc:
            last = exc
            # A 400 is a permanent contract error (bad schema, deprecated
            # parameter). Retrying it three times just triples the latency
            # of a failure that will never succeed.
            status = getattr(exc, "status_code", None)
            if status == 400 or "invalid_request_error" in str(exc):
                raise RuntimeError(
                    "LLM " + provider + "/" + model + " rejected the request: "
                    + str(exc)[:300]
                ) from exc
            time.sleep(2 ** attempt)
            continue

    raise RuntimeError(
        "LLM role '" + role + "' failed after " + str(max_retries)
        + " attempts: " + repr(last)
    )


def anthropic_is_funded() -> bool:
    """Cheapest possible probe of whether the Anthropic account has credit.

    A 1-token request costs effectively nothing and returns HTTP 400 with
    'credit balance is too low' when the account is empty. Used to upgrade
    the routing plan automatically once a top-up lands, so the operator does
    not have to remember to flip a flag.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=secret("ANTHROPIC_API_KEY", required=False))
        client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "."}],
        )
        return True
    except Exception as exc:
        text = str(exc).lower()
        if "credit balance" in text or "too low" in text:
            return False
        # Any other failure (bad key, network) is also "cannot use Anthropic".
        # Logged by the caller rather than swallowed silently.
        return False


def autoselect_plan(verbose: bool = True) -> str:
    """Pick the best routing plan the current credentials can actually pay for."""
    if anthropic_is_funded():
        set_plan("anthropic")
        chosen = "anthropic"
    else:
        set_plan("hybrid")
        chosen = "hybrid"
    if verbose:
        print("[providers] plan=" + chosen)
        for role, (prov, model) in ROUTING.items():
            print("            " + role + " -> " + prov + "/" + model)
    return chosen
