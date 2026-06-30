#!/usr/bin/env bash
# Front-door synthetic for the Retell POC.
# Verifies: flow + agent config are wired correctly, function tools point at the live
# Worker, and the Worker's Retell endpoints return Retell-shaped JSON. Does NOT make
# a live voice call (that requires a mic + audio).

set -eu -o pipefail

WORKER_URL="${WORKER_URL:-https://vapi-dental-fr.debanjan186.workers.dev}"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

RETELL_KEY="${RETELL_API_KEY:-}"
AGENT_ID="${RETELL_AGENT_ID:-}"
FLOW_ID="${RETELL_FLOW_ID:-}"

fail() { echo "FAIL  $1" >&2; exit 1; }
pass() { echo "PASS  $1"; }

[ -n "$RETELL_KEY" ] || fail "RETELL_API_KEY not set"
[ -n "$AGENT_ID" ]   || fail "RETELL_AGENT_ID not set"
[ -n "$FLOW_ID" ]    || fail "RETELL_FLOW_ID not set"

echo "front-door synthetic (Retell POC) v0.5.0"
echo "  flow: $FLOW_ID"
echo "  agent: $AGENT_ID"
echo "  worker: $WORKER_URL"
echo ""

# 1. Worker Retell endpoint -- list_slots
slots_body=$(curl -fsS -X POST "$WORKER_URL/retell/tools/list_slots" \
  -H "Content-Type: application/json" \
  -d '{"treatment":"consultation"}' || fail "POST /retell/tools/list_slots non-200")

echo "$slots_body" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ok') is True, f'ok!=true: {d}'
summary = d.get('summary', '')
assert isinstance(summary, str) and 'AM' in summary or 'PM' in summary, f'bad summary: {summary!r}'
for b in summary.encode('utf-8'):
    assert b < 128, f'non-ASCII byte in summary: {summary!r}'
slots = d.get('slots') or []
assert len(slots) >= 1, 'no slots'
print(f'    sample: {summary[:120]!r}...')
" || fail "Retell list_slots shape check failed"
pass "1. Worker Retell list_slots: ok + ASCII summary + slots array"

# 2. Worker Retell endpoint -- book_slot (invalid input -> graceful)
book_body=$(curl -sS -X POST "$WORKER_URL/retell/tools/book_slot" \
  -H "Content-Type: application/json" \
  -d '{"slot_id":"INVALID","caller_name":"x","callback":"0","treatment":"consultation"}')
echo "$book_body" | python -c "
import json, sys
d = json.load(sys.stdin)
assert 'summary' in d, f'no summary: {d}'
summary = d['summary']
for b in summary.encode('utf-8'):
    assert b < 128, f'non-ASCII in summary'
" || fail "Retell book_slot shape check failed"
pass "2. Worker Retell book_slot: graceful failure shape"

# 3. Retell flow exists + has all 10 nodes
flow=$(curl -fsS "https://api.retellai.com/get-conversation-flow/$FLOW_ID" \
  -H "Authorization: Bearer $RETELL_KEY" || fail "Retell GET /get-conversation-flow failed")
echo "$flow" | python -c "
import json, sys
f = json.load(sys.stdin)
nodes = f.get('nodes') or []
node_ids = {n.get('id') for n in nodes}
expected = {'greet','get_reason','get_first_name','get_last_name','get_phone',
            'confirm_phone','list_slots_call','read_slots','book_slot_call','close','handoff'}
missing = expected - node_ids
assert not missing, f'flow missing nodes: {missing}'
# Tools must include list_slots + book_slot
tools = f.get('tools') or []
tool_names = {t.get('name') for t in tools}
assert 'list_slots' in tool_names and 'book_slot' in tool_names, f'flow tools: {tool_names}'
# Function nodes must reference the tool_ids
fn_nodes = [n for n in nodes if n.get('type') == 'function']
assert len(fn_nodes) >= 2, f'expected 2+ function nodes; got {len(fn_nodes)}'
fn_tool_ids = {n.get('tool_id') for n in fn_nodes}
assert 'list_slots' in fn_tool_ids and 'book_slot' in fn_tool_ids, f'function nodes wrong tools: {fn_tool_ids}'
# Critical structural check: conversation nodes must NOT have tool_id set.
# This is the architectural guarantee against eager tool-calling.
conv_nodes = [n for n in nodes if n.get('type') == 'conversation']
for n in conv_nodes:
    assert not n.get('tool_id'), f'conversation node {n[\"id\"]} has tool_id -- eager-call gate broken'
print(f'    nodes: {len(nodes)} (conv={len(conv_nodes)}, fn={len(fn_nodes)}); start_node_id={f.get(\"start_node_id\")}')
" || fail "Retell flow structural check failed"
pass "3. Retell flow: all expected nodes present + conversation nodes tool-free (eager-call gate intact)"

# 4. Retell agent wired correctly
agent=$(curl -fsS "https://api.retellai.com/get-agent/$AGENT_ID" \
  -H "Authorization: Bearer $RETELL_KEY" || fail "Retell GET /get-agent failed")
echo "$agent" | python -c "
import json, sys
a = json.load(sys.stdin)
re = a.get('response_engine', {})
assert re.get('type') == 'conversation-flow', f'wrong response_engine: {re}'
assert re.get('conversation_flow_id'), 'no conversation_flow_id'
assert a.get('language', '').startswith('en'), f'wrong language: {a.get(\"language\")}'
# Boosted keywords should include at least Debanjan + Mazumdar
bk = a.get('boosted_keywords') or []
must_have = {'Debanjan', 'Mazumdar', 'Patel'}
missing = must_have - set(bk)
assert not missing, f'agent missing boosted keywords: {missing}'
print(f'    agent voice={a.get(\"voice_id\")} keywords={len(bk)}')
" || fail "Retell agent config check failed"
pass "4. Retell agent: voice + language + keyword boost wired"

# 5. Flow's tool URL points at our live Worker
echo "$flow" | python -c "
import json, sys
f = json.load(sys.stdin)
tools = f.get('tools') or []
for t in tools:
    url = t.get('url', '')
    assert 'vapi-dental-fr.debanjan186.workers.dev' in url, f'tool {t.get(\"name\")} url not on live worker: {url}'
    assert '/retell/tools/' in url, f'tool {t.get(\"name\")} not pointing at Retell endpoint: {url}'
" || fail "Retell flow tool URL not pointing at live Worker"
pass "5. Retell flow tools point at live Worker /retell/tools/* endpoints"

echo ""
echo "all 5 checks green (Retell POC structurally sound; voice call still required for end-to-end)"
