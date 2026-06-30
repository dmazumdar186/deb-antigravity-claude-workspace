#!/usr/bin/env bash
# tests/front_door_rag_chatbot.sh
# Front-door synthetic for the RAG chatbot skeleton.
#
# Per ~/.claude/rules/front-door-synthetic.md: this hits the actual ingest + chat
# CLIs end-to-end with a fixture corpus. It is NOT a fixture-only parser test —
# the chat call goes to live Gemini (free tier). On rate-limit / network failure
# the script exits non-zero and stderr names the cause.
#
# Requires: GEMINI_API_KEY in .env.

set -euo pipefail

cd "$(dirname "$0")/.."

STORE="rag_smoke_$(date +%s)"
PYTHON_BIN="${PYTHON_BIN:-py}"

cleanup() {
  rm -f "execution/rag/stores/${STORE}.json" 2>/dev/null || true
}
trap cleanup EXIT

echo "[1/3] Ingest fixture into store: ${STORE}"
"$PYTHON_BIN" execution/rag/ingest.py \
  --source tests/fixtures/rag/sample.md \
  --store "${STORE}" \
  --reset \
  --chunk-size 400

if [ ! -s "execution/rag/stores/${STORE}.json" ]; then
  echo "FAIL: store file empty or missing after ingest." >&2
  exit 1
fi

CHUNK_COUNT=$("$PYTHON_BIN" -c "import json,sys; print(len(json.load(open('execution/rag/stores/${STORE}.json',encoding='utf-8'))))")
if [ "${CHUNK_COUNT}" -lt 3 ]; then
  echo "FAIL: only ${CHUNK_COUNT} chunks ingested; expected >= 3." >&2
  exit 1
fi
echo "  -> ${CHUNK_COUNT} chunks ingested."

echo "[2/3] Chat: founder question"
ANSWER_FOUNDER=$("$PYTHON_BIN" execution/rag/chat.py \
  --store "${STORE}" \
  --question "Who founded Acme Coaching and when?" \
  --max-tokens 200)
echo "  -> ${ANSWER_FOUNDER}"

# Acceptance: the answer must mention the fixture-known founder name AND year.
# This is the output-acceptance gate per ~/.claude/rules/output-acceptance-gate.md
# — asserting on the OUTPUT, not just that the script ran.
if ! echo "${ANSWER_FOUNDER}" | grep -qi "Pritchard"; then
  echo "FAIL: answer does not mention 'Pritchard' (fixture-known founder)." >&2
  exit 1
fi
if ! echo "${ANSWER_FOUNDER}" | grep -q "2019"; then
  echo "FAIL: answer does not mention '2019' (fixture-known founding year)." >&2
  exit 1
fi

echo "[3/3] Chat: off-corpus refusal"
ANSWER_OFF=$("$PYTHON_BIN" execution/rag/chat.py \
  --store "${STORE}" \
  --question "What is the airspeed velocity of an unladen swallow?" \
  --max-tokens 100)
echo "  -> ${ANSWER_OFF}"

# Acceptance: off-corpus questions must be refused, not hallucinated.
if ! echo "${ANSWER_OFF}" | grep -qi "don't have"; then
  echo "FAIL: off-corpus question got an answer instead of a refusal." >&2
  echo "      The RAG system must say 'I don't have that information' for off-corpus queries." >&2
  exit 1
fi

echo ""
echo "PASS: RAG chatbot front-door synthetic green."
