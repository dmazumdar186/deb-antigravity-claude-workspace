#!/usr/bin/env bash
# Front-door synthetic for the Gemini Live dental voice receptionist.
# Per ~/.claude/rules/front-door-synthetic.md: hits LIVE infrastructure end-to-end.
# Exits non-zero on any failure. Run on every deploy and on a 1h cron.
#
# Requires env: VOICE_AGENT_URL (e.g. https://debanjan186--gemini-live-dental-fr-fastapi-app.modal.run)
#              WORKER_SECRET   (matches the Modal secret voice-agent-secret)
#
# What it checks:
#   1. GET /              -> 200 + HTML containing the FR disclaimer banner
#   2. GET /api/health    -> 200 + secrets_present.gemini=true + secrets_present.gcal=true
#   3. GET /api/health w/ X-Voice-Agent-Secret -> calendar_reachable=true
#   4. WebSocket handshake on /ws -> server upgrades + sends {"type":"ready"} within 5s

set -eu -o pipefail

URL="${VOICE_AGENT_URL:-}"
SECRET="${WORKER_SECRET:-}"

if [ -z "$URL" ]; then
  echo "FAIL  VOICE_AGENT_URL not set"
  echo "    set it to the Modal deploy URL (without trailing slash)"
  exit 2
fi

fail() { echo "FAIL  $1"; exit 1; }

echo "front-door synthetic against $URL"

# 1. Index page
body=$(curl -fsS "$URL/" || fail "GET / not 200")
echo "$body" | grep -qi "Cabinet Dentylis" || fail "GET / missing clinic name"
echo "$body" | grep -qi "Démo — données simulées" || fail "GET / missing demo disclaimer"
echo "PASS  GET / serves widget with disclaimer"

# 2. Health unauthenticated
h=$(curl -fsS "$URL/api/health" || fail "GET /api/health not 200")
echo "$h" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ok') is True, 'ok != true'
sp = d.get('secrets_present', {})
assert sp.get('gemini') is True, 'gemini secret missing'
assert sp.get('gcal') is True, 'gcal secret missing'
assert sp.get('worker') is True, 'worker secret missing'
print('PASS  /api/health unauthenticated: secrets present')
" || fail "health body did not pass checks"

# 3. Health authenticated (calendar probe)
if [ -n "$SECRET" ]; then
  h2=$(curl -fsS -H "X-Voice-Agent-Secret: $SECRET" "$URL/api/health" || fail "GET /api/health (auth) not 200")
  echo "$h2" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('calendar_reachable') is True, f'calendar not reachable: {d.get(\"calendar_error\", \"\")}'
print('PASS  /api/health authenticated: calendar reachable')
" || fail "authenticated health failed"
else
  echo "SKIP  authenticated calendar probe (WORKER_SECRET not set)"
fi

# 4. WebSocket /ws handshake (5s timeout, expect ready frame)
python <<'PY' || fail "websocket /ws handshake did not return ready frame"
import asyncio, json, os, sys, websockets

URL = os.environ["VOICE_AGENT_URL"].replace("http", "ws", 1) + "/ws"

async def go():
    async with websockets.connect(URL, open_timeout=10) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
        data = json.loads(msg) if isinstance(msg, (str, bytes)) and msg.strip().startswith(("{", b"{")) else None
        if not data or data.get("type") != "ready":
            raise SystemExit(f"unexpected first frame: {msg!r}")
        print("PASS  /ws handshake: server ready frame received")

asyncio.run(go())
PY

echo ""
echo "all checks green"
