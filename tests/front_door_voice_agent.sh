#!/usr/bin/env bash
# Front-door synthetic for the Vapi dental voice receptionist.
# Per ~/.claude/rules/front-door-synthetic.md: hits LIVE infrastructure end-to-end.
# Exits non-zero on any failure. Threshold: must pass 5 consecutive runs before
# the system can be described as "ready / live / working" per panel-pass rule.
#
# Requires env (loaded from .env or shell):
#   VAPI_API_KEY        Vapi private API key (Bearer)
#   VAPI_ASSISTANT_ID   the live assistant id
#   WORKER_SECRET       (optional) gates the authenticated /api/health calendar probe
#
# What it checks:
#   1. Worker GET /                       -> 200 + HTML widget with clinic name
#   2. Worker GET /api/health             -> ok=true + all 4 secrets_present=true
#   3. Worker POST /vapi/tools/list_slots -> result is single-line ASCII STRING per
#      Vapi contract (regression for 2026-06-27 mojibake bug: must NOT be an object,
#      must NOT contain newlines, must NOT contain non-ASCII bytes)
#   4. Worker POST /vapi/tools/book_slot  -> single-line ASCII string on invalid input
#   5. Vapi GET /assistant/<id>           -> voice/asr/llm/tools wired
#   6. Vapi assistant system prompt MUST contain the 3 new hard-rule sentinels
#   7. Vapi assistant system prompt: forbidden phrases only in Never/forbidden blocks

set -eu -o pipefail

WORKER_URL="${WORKER_URL:-https://vapi-dental-fr.debanjan186.workers.dev}"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

VAPI_KEY="${VAPI_API_KEY:-}"
ASSISTANT_ID="${VAPI_ASSISTANT_ID:-}"

fail() { echo "FAIL  $1" >&2; exit 1; }
pass() { echo "PASS  $1"; }

[ -n "$VAPI_KEY" ] || fail "VAPI_API_KEY not set (in env or .env)"
[ -n "$ASSISTANT_ID" ] || fail "VAPI_ASSISTANT_ID not set (in env or .env)"

echo "front-door synthetic v0.4.0 -- target: $WORKER_URL"
echo "                              assistant: $ASSISTANT_ID"
echo ""

# 1. Widget
body=$(curl -fsS "$WORKER_URL/" || fail "GET / non-200")
echo "$body" | grep -qi "Cabinet Dentylis" || fail "GET / missing clinic name"
pass "1. widget served at /"

# 2. Health unauth
h=$(curl -fsS "$WORKER_URL/api/health" || fail "GET /api/health non-200")
echo "$h" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ok') is True, 'ok != true'
assert d.get('version', '').startswith('0.'), f'unexpected version: {d.get(\"version\")}'
sp = d.get('secrets_present', {})
for k in ('calcom', 'vapi_public', 'vapi_assistant_id', 'worker'):
    assert sp.get(k) is True, f'secret {k} missing'
" || fail "/api/health did not pass shape checks"
pass "2. /api/health: ok + all 4 secrets present"

# 3. list_slots -- single-line ASCII string per Vapi contract
slots_body=$(curl -fsS -X POST "$WORKER_URL/vapi/tools/list_slots" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCalls":[{"id":"fd","function":{"name":"list_slots","arguments":"{\"treatment\":\"consultation\"}"}}]}}' \
  || fail "POST list_slots non-200")

echo "$slots_body" | python -c "
import json, sys, re
d = json.load(sys.stdin)
results = d.get('results', [])
assert results, 'no results'
r = results[0]
assert 'result' in r, f'no result field: {r}'
# Vapi contract (docs.vapi.ai 2026-06-27 deep-research): result MUST be a
# SINGLE-LINE STRING. v0.3.0 returned an object and Vapi silently stringified
# it with a UTF-8 -> Latin-1 path that produced the mojibake -> Gemini 400.
result_str = r['result']
assert isinstance(result_str, str), f'result must be string per Vapi contract; got {type(result_str).__name__}: {result_str!r}'
assert not re.search(r'[\n\r]', result_str), f'result has newline (forbidden by Vapi): {result_str!r}'
for b in result_str.encode('utf-8'):
    assert b < 128, f'non-ASCII byte 0x{b:02x} in result -- mojibake regression!'
assert any(w in result_str for w in ('AM', 'PM', 'No slots')), f'result not English-time-formatted: {result_str!r}'
assert ('slot_id=' in result_str) or ('No slots' in result_str), f'result missing slot_id pointer: {result_str!r}'
print(f'    sample: {result_str[:120]!r}...')
" || fail "list_slots Vapi-contract check failed"
pass "3. list_slots: single-line ASCII string per Vapi contract"

# 4. book_slot contract on invalid input
book_body=$(curl -sS -X POST "$WORKER_URL/vapi/tools/book_slot" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCalls":[{"id":"fd","function":{"name":"book_slot","arguments":"{\"slot_id\":\"INVALID\",\"caller_name\":\"front_door_synthetic\",\"callback\":\"0000000000\",\"treatment\":\"consultation\"}"}}]}}')
echo "$book_body" | python -c "
import json, sys, re
d = json.load(sys.stdin)
results = d.get('results', [])
assert results, 'no results'
r = results[0]
# Either result is a string OR error is set. Both are acceptable per Vapi contract.
if 'result' in r:
    res = r['result']
    assert isinstance(res, str), f'result must be string per Vapi contract; got {type(res).__name__}'
    for b in res.encode('utf-8'):
        assert b < 128, f'non-ASCII byte 0x{b:02x} in book_slot result'
elif 'error' in r:
    err = r['error']
    assert isinstance(err, str), 'error must be string per Vapi contract'
else:
    raise SystemExit(f'neither result nor error: {r}')
print('    book_slot contract OK on invalid input')
" || fail "book_slot Vapi-contract check failed"
pass "4. book_slot: Vapi-contract compliant on invalid input"

# 5. Vapi assistant wired correctly
asst=$(curl -fsS "https://api.vapi.ai/assistant/$ASSISTANT_ID" \
  -H "Authorization: Bearer $VAPI_KEY" || fail "Vapi GET /assistant/$ASSISTANT_ID failed")

echo "$asst" | python -c "
import json, sys
a = json.load(sys.stdin)
v = a.get('voice', {})
assert v.get('provider') == 'azure', f'voice provider: {v}'
assert v.get('voiceId') == 'en-US-AriaNeural', f'voice id: {v}'
t = a.get('transcriber', {})
assert t.get('provider') == 'deepgram', f'transcriber: {t}'
assert t.get('language') == 'en', f'transcriber lang: {t}'
m = a.get('model', {})
assert m.get('provider') == 'google', f'llm provider: {m}'
tools = m.get('tools', [])
names = {(tool.get('function') or {}).get('name') for tool in tools}
assert 'list_slots' in names, f'list_slots missing: {names}'
assert 'book_slot' in names, f'book_slot missing: {names}'
" || fail "Vapi assistant config checks failed"
pass "5. Vapi assistant: voice/asr/llm/tools correctly wired"

# 6. System prompt contains the 3 new hard-rule sentinels
echo "$asst" | python -c "
import json, sys
a = json.load(sys.stdin)
sys_msg = next(
    (m.get('content', '') for m in a.get('model', {}).get('messages', []) if m.get('role') == 'system'),
    ''
)
required = [
    'Goodbye / Hello / single ambiguous words',
    'NEVER use bare filler phrases',
    'Tool failure recovery',
]
missing = [r for r in required if r not in sys_msg]
assert not missing, f'system prompt missing required hard rules: {missing}'
" || fail "system prompt missing one of the 3 new hard rules"
pass "6. system prompt contains all 3 new hard-rule sentinels"

# 7. Forbidden phrases only appear inside Never/forbidden blocks
echo "$asst" | python -c "
import json, sys
a = json.load(sys.stdin)
sys_msg = next(
    (m.get('content', '') for m in a.get('model', {}).get('messages', []) if m.get('role') == 'system'),
    ''
)
forbidden_examples = ['are you sure you want', 'have a wonderful day', \"if there's nothing else\"]
for ex in forbidden_examples:
    if ex in sys_msg.lower():
        idx = sys_msg.lower().find(ex)
        ctx = sys_msg[max(0, idx-200):idx].lower()
        if 'never' not in ctx and 'forbidden' not in ctx:
            raise SystemExit(f'forbidden example {ex!r} appears without Never/forbidden context')
" || fail "system prompt has unguarded forbidden phrase"
pass "7. system prompt: forbidden phrases only appear inside Never/forbidden blocks"

echo ""
echo "all 7 checks green"
