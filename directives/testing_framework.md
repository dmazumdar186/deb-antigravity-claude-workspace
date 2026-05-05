# Testing Framework — Production Reliability Standard

This directive defines the mandatory 6-tier testing architecture for every project in this workspace. When the user asks for testing, apply all 6 tiers. No project ships without coverage across every tier.

---

## When to Use

- Any time the user says "add tests", "write tests", "test this", or "make sure this works"
- Before declaring any feature complete
- After any reliability or hardening pass
- When building a new execution script or module

---

## The 6-Tier Testing Architecture

### Tier 1: Sanity Tests (`test_sanity.py`)

**Purpose:** Verify the system is deployable — files exist, configs parse, no secrets leaked.

**Always test:**
- All required files exist (`Path(file).exists()`)
- All config files are valid JSON/YAML (`json.load()`)
- Required keys are present in configs
- `.gitignore` covers sensitive files (`.env`, credentials, temp dirs)
- No hardcoded API keys in source code (scan `*.py` with `.rglob()` for forbidden patterns like `sk-ant-`, `pk_`, etc.)
- Deployment configs are valid (Vercel, Wrangler, redirects)
- All registered execution scripts exist

**Patterns:**
```python
class TestFileExistence:
    def test_config_exists(self):
        assert Path("config/client.json").exists()

class TestNoHardcodedSecrets:
    FORBIDDEN = ["sk-ant-", "pk_", "Bearer "]

    @pytest.mark.parametrize("pattern", FORBIDDEN)
    def test_no_hardcoded_key(self, pattern):
        for py_file in Path("execution").rglob("*.py"):
            assert pattern not in py_file.read_text()
```

---

### Tier 2: Unit Tests (`test_api_payloads.py`, `test_llm_client.py`)

**Purpose:** Test individual functions in isolation — payload construction, parsing, retry logic — with all external calls mocked.

**Always test:**
- **API payload construction:** Build payloads with sample data, verify field mapping, handle missing fields with defaults
- **Response parsing:** Mock API responses, verify correct extraction of data (email, status, etc.)
- **Name parsing:** Edge cases — full name, first only, empty, None, three-part names
- **LLM client retry logic:**
  - Succeeds on first try → no retries
  - 429 Rate Limit → retries with backoff
  - 5xx Server Error → retries with backoff
  - 4xx Client Error (not 429) → does NOT retry
  - Exhausts max retries → raises exception
- **Helper function edge cases:** Empty inputs, None, type mismatches

**Patterns:**
```python
from unittest.mock import patch, MagicMock

class TestParseName:
    def test_full_name(self):
        assert _parse_name("John Smith") == ("John", "Smith")

    def test_none(self):
        assert _parse_name(None) == ("", "")

class TestRetryLogic:
    @patch("modules.llm_client.time.sleep")
    @patch("modules.llm_client._get_client")
    def test_retries_on_429(self, mock_client, mock_sleep):
        mock_client.return_value.chat.completions.create.side_effect = [
            RateLimitError("rate limited", response=mock_resp, body={}),
            mock_success,
        ]
        result = chat_completion(system="test", user_message="test")
        assert result == "success"
        assert mock_sleep.call_count == 1

class TestBuildPayload:
    def test_field_mapping(self):
        lead = {"owner_email": "a@b.com", "business_name": "Acme"}
        payload = _build_lead_payload(lead, field_mapping)
        assert payload["email"] == "a@b.com"
        assert payload["company_name"] == "Acme"
```

---

### Tier 3: Integration Tests (`test_integration.py`, `test_flow_chains.py`)

**Purpose:** Verify modules wire together — imports work, configs load, function calls chain correctly.

**Always test:**
- **Module imports:** Every module in `execution/` imports without error
- **Config loading:** `load_config()` returns dict with required keys
- **Function existence:** All expected functions are callable
- **Flow wiring:** Classification → routing → action chains work end-to-end with mocked dependencies
- **Send flow:** Verify `send_fn` is called for actionable replies, not called for skips
- **Multi-channel delivery:** Report → email + Telegram + Slack (mocked channels)
- **Function signatures:** Use `inspect.signature()` to verify required parameters exist

**Patterns:**
```python
class TestModuleImports:
    def test_auto_reply_imports(self):
        from modules.outputs.auto_reply import handle_reply, should_handoff
        assert callable(handle_reply)

class TestAutoReplySendFlow:
    def test_positive_reply_triggers_send(self):
        mock_send = MagicMock()
        result = handle_reply(positive_reply, config, mock=False, send_fn=mock_send)
        mock_send.assert_called_once()
        assert result["action"] == "auto_reply"

class TestFlowChain:
    @patch("modules.outputs.ghl.route_positive_reply")
    @patch("modules.outputs.telegram.send_notification")
    def test_positive_routes_to_ghl_and_telegram(self, mock_tg, mock_ghl):
        poll_replies(config, mock=True)
        mock_ghl.assert_called()
        mock_tg.assert_called()
```

---

### Tier 4: Mock End-to-End Tests (`test_e2e.py`, `test_pipeline.py`)

**Purpose:** Run the full pipeline in mock mode — verify the entire data flow without external calls.

**Always test:**
- **Pipeline completion:** Runs to completion with `mock=True`, no exceptions
- **State management:** State file created, is valid JSON, checkpoint/resume works
- **Classification routing:** Each input type → expected action (handoff, auto_reply, skip)
- **Delay ranges:** Auto-reply delays within configured min/max
- **Report generation:** Metrics structure, positive values, formatted output (HTML, Telegram, Slack)
- **Message formatting:** Telegram messages truncated to limit, missing fields handled gracefully
- **Data structure:** All outputs have required keys, correct types

**Patterns:**
```python
class TestReplyClassifier:
    def test_hot_positive_phone_number(self, config):
        result = classify_mock("Call me at 713-555-0888")
        assert result == "hot_positive"

class TestAutoReply:
    def test_positive_generates_reply(self, config):
        reply = {"body": "interested", "classification": "positive", ...}
        result = handle_reply(reply, config, mock=True)
        assert result["action"] == "auto_reply"
        assert "reply_text" in result
        assert 120 <= result["delay_seconds"] <= 420

class TestPipelineIntegration:
    def test_full_pipeline_mock(self, config, tmp_path):
        run_pipeline(config, output_dir=str(tmp_path), mock=True)
        assert (tmp_path / "pipeline_state.json").exists()
```

---

### Tier 5: Monkey / Chaos Tests (`test_monkey.py`)

**Purpose:** Feed garbage into every public function — None, empty, wrong types, huge inputs, unicode, special chars.

**Always test every public function with:**
- `None` input
- Empty string `""`
- Integer where string expected (verify raises `TypeError` or `AttributeError`)
- Very long string (5000+ repetitions)
- Unicode with emoji (`"intéressé 🤝"`)
- Special characters (`"!@#$%^&*(){}[]"`)
- Whitespace only (`"   \t\n  "`)
- Empty dict `{}`
- Dict with None values
- Dict with numeric values where strings expected
- Empty list `[]`
- List of empty dicts `[{}]`
- All-duplicate list

**Patterns:**
```python
class TestClassifyEdgeCases:
    def test_none_input(self):
        assert classify_mock(None) == "neutral"

    def test_integer_raises(self):
        with pytest.raises(AttributeError):
            classify_mock(12345)

    def test_very_long_string(self):
        result = classify_mock("interested " * 5000)
        assert result in VALID_CLASSES

class TestFormatEdgeCases:
    def test_empty_dict(self):
        msg = format_output({})
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_none_values(self):
        msg = format_output({"name": None, "email": None})
        assert isinstance(msg, str)
```

---

### Tier 6: Real LLM / Production Path Tests (`test_ai_guard_rails.py`, `test_classifier_reliability.py`, `test_reply_classifier.py`)

**Purpose:** Test with real LLM calls to verify guard rails hold, classifier accuracy, and output reliability. **Gated by API key** — these skip gracefully when no key is available.

**Always test:**

#### 6a. Guard Rails (deterministic checks on LLM output)
- No exclamation marks in output
- Word count under configured max (e.g., 60)
- Sentence count under configured max (e.g., 3)
- No dollar amounts in output
- No forbidden phrases (AI, automation, specific valuations)
- No "never-say" phrases from config
- Hot leads trigger handoff, not auto-reply
- Objection matching returns relevant response without violating rules

#### 6b. Classifier Golden Set (data-driven, parametrized)
- Define `SAMPLE_REPLIES` as module-level list of dicts with `body`, `expected`, and optional `accept` (list of acceptable answers)
- Parametrize with `ids` for readable output: `@pytest.mark.parametrize("case", SAMPLE_REPLIES, ids=[...])`
- Mock-compatible cases (first N) test the mock path
- All cases test the real LLM path (skipped without API key)
- Flexible assertions: `result in case.get("accept", [case["expected"]])`

#### 6c. Classifier Reliability (3x consistency)
- Run each case 3 times, measure consistency
- `pytest.xfail()` for marginal reliability (70-100% but not perfect)
- `pytest.fail()` for poor reliability (<70%)
- Print summary report with per-case breakdown

#### 6d. Malformed LLM Output Handling
- Monkeypatch `chat_completion` to return edge cases: `"positive."`, `" positive\n"`, `"POSITIVE"`, `"The answer is positive"`, `""`, `"maybe"`
- Verify parsing extracts the correct class or defaults to neutral

**Patterns:**
```python
import os
HAS_API_KEY = bool(os.environ.get("OPENROUTER_API_KEY"))
SKIP_REASON = "OPENROUTER_API_KEY not set"

@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestGuardRailsReal:
    def test_no_exclamation_marks(self, config):
        result = handle_reply(positive_reply, config, mock=False)
        assert "!" not in result["reply_text"]

    def test_max_words(self, config):
        result = handle_reply(positive_reply, config, mock=False)
        assert len(result["reply_text"].split()) <= config["auto_reply"]["max_words"]

SAMPLE_REPLIES = [
    {"body": "Call me at 713-555-0888", "expected": "hot_positive", "mock_compat": True},
    {"body": "Not interested, remove me", "expected": "negative", "mock_compat": True},
    {"body": "Out of office until Monday", "expected": "neutral", "mock_compat": True},
    {"body": "Tell me more about the process", "expected": "positive", "mock_compat": True},
    {"body": "If the price is right, I'd consider", "expected": "positive",
     "accept": ["positive", "neutral"], "mock_compat": False},
]

class TestMockClassifier:
    @pytest.mark.parametrize("case", [c for c in SAMPLE_REPLIES if c["mock_compat"]],
                             ids=[c["body"][:40] for c in SAMPLE_REPLIES if c["mock_compat"]])
    def test_mock(self, case):
        assert classify_mock(case["body"]) == case["expected"]

class TestMalformedOutput:
    CASES = [
        ("positive.", "positive"),
        (" positive\n", "positive"),
        ("POSITIVE", "positive"),
        ("The answer is positive", "positive"),
        ("", "neutral"),
        ("maybe", "neutral"),
    ]

    @pytest.mark.parametrize("raw,expected", CASES, ids=[c[0] or "empty" for c in CASES])
    def test_malformed(self, monkeypatch, raw, expected):
        monkeypatch.setattr(llm_module, "chat_completion", lambda **kw: raw)
        assert classify(body="test", model="test") == expected
```

---

## Cross-Cutting Rules

### Private Function Convention
Any function that produces output requiring post-processing (truncation, stripping, guard rails) MUST be private (`_prefix`). Only the public wrapper that applies all guard rails is importable. Test that direct imports of the private name from external code raise `ImportError`.

### Defense-in-Depth Post-Processing
LLM output goes through a pipeline of deterministic checks — each tested independently:
1. Word count truncation (prefer sentence boundary)
2. Dollar amount stripping (remove incoherent fragments)
3. Exclamation mark replacement
4. Sentence count enforcement
5. Forbidden phrase check

### Data-Driven Test Design
- Define test data as module-level constants (`SAMPLE_REPLIES`, `SAMPLE_LEADS`)
- Use `@pytest.mark.parametrize` with `ids` for readable output
- Support multi-valued `accept` lists for ambiguous cases
- Share data across test files via import

### API Key Gating
```python
import os
HAS_API_KEY = bool(os.environ.get("YOUR_API_KEY"))

@pytest.mark.skipif(not HAS_API_KEY, reason="API key not set")
class TestRealPath:
    ...
```

### Config Fixture
```python
@pytest.fixture
def config():
    config_path = Path(__file__).parent.parent / "config" / "client.json"
    with open(config_path) as f:
        return json.load(f)
```

### Mock Path / Real Path
Every function that calls an external API must support `mock=True` for fast deterministic tests and `mock=False` for real path verification.

---

## Test File Naming Convention

| File | Tier | Purpose |
|------|------|---------|
| `test_sanity.py` | 1 | File existence, config validity, secret scan |
| `test_api_payloads.py` | 2 | Payload construction, response parsing |
| `test_llm_client.py` | 2 | Retry logic, error handling |
| `test_integration.py` | 3 | Module imports, config loading, function wiring |
| `test_flow_chains.py` | 3 | Flow chains with mocked dependencies |
| `test_e2e.py` | 4 | Full pipeline mock runs |
| `test_pipeline.py` | 4 | Classification routing, report generation |
| `test_monkey.py` | 5 | Garbage inputs, edge cases, chaos |
| `test_ai_guard_rails.py` | 6 | Real LLM guard rail enforcement |
| `test_classifier_reliability.py` | 6 | 3x reliability measurement |
| `test_reply_classifier.py` | 6 | Golden set + malformed output |
| `test_variant_generator.py` | 2+4 | A/B variant logic (unit + mock E2E) |

---

## Running Tests

```bash
# Full suite (all tiers, ~5 min with LLM calls)
py -m pytest tests/ -v --tb=short

# Fast suite (tiers 1-5 only, ~10 sec)
py -m pytest tests/ -v --tb=short -k "not Real and not Reliability"

# Guard rails only (tier 6a)
py -m pytest tests/test_ai_guard_rails.py -v --tb=long

# Classifier golden set (tier 6b)
py -m pytest tests/test_reply_classifier.py -v --tb=short

# Reliability check (tier 6c)
py -m pytest tests/test_classifier_reliability.py -v --tb=long

# Monkey tests only (tier 5)
py -m pytest tests/test_monkey.py -v --tb=short
```

---

## Checklist: Before Declaring a Feature Complete

- [ ] Tier 1: Sanity tests pass (files exist, config valid, no secrets)
- [ ] Tier 2: Unit tests cover all helpers, parsers, payload builders, retry logic
- [ ] Tier 3: Integration tests verify imports, config, flow wiring
- [ ] Tier 4: Mock E2E tests run full pipeline without external calls
- [ ] Tier 5: Monkey tests cover every public function with garbage inputs
- [ ] Tier 6: Real LLM tests verify guard rails hold, classifier accuracy, reliability
- [ ] All public LLM-output functions are private (`_prefix`) with guard-railed wrappers
- [ ] Full suite: `py -m pytest tests/ -v --tb=short` — 0 failures
