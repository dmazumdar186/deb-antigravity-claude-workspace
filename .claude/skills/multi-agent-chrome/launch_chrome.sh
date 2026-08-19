#!/bin/bash
# Launch multiple isolated Chrome instances for multi-agent browser automation
# Usage: ./launch_chrome.sh [count]  (default: 5, max: 5)

COUNT=${1:-5}
if [ "$COUNT" -gt 5 ]; then COUNT=5; fi
if [ "$COUNT" -lt 1 ]; then COUNT=1; fi

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE_PORT=9223
DATA_DIR_BASE="/tmp/chrome-agent"

# Kill any existing chrome-agent instances
for i in $(seq 1 5); do
    PORT=$((BASE_PORT + i - 1))
    PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Killing existing process on port $PORT (PID: $PID)"
        kill $PID 2>/dev/null
        sleep 0.5
    fi
done

echo "Launching $COUNT Chrome instances..."

for i in $(seq 1 $COUNT); do
    PORT=$((BASE_PORT + i - 1))
    DATA_DIR="${DATA_DIR_BASE}-${i}"

    mkdir -p "$DATA_DIR"

    "$CHROME_BIN" \
        --remote-debugging-port=$PORT \
        --user-data-dir="$DATA_DIR" \
        --no-first-run \
        --no-default-browser-check \
        --disable-background-networking \
        --disable-sync \
        --window-size=1280,720 \
        --window-position=$((100 + (i-1) * 50)),$((100 + (i-1) * 50)) \
        &>/dev/null &

    echo "  Agent $i: Chrome on port $PORT (data: $DATA_DIR)"
done

echo ""
echo "Waiting for Chrome instances to be ready..."
sleep 3

# Verify all instances are reachable
ALL_OK=true
for i in $(seq 1 $COUNT); do
    PORT=$((BASE_PORT + i - 1))
    if curl -s "http://127.0.0.1:$PORT/json/version" &>/dev/null; then
        echo "  Agent $i (port $PORT): READY"
    else
        echo "  Agent $i (port $PORT): NOT RESPONDING"
        ALL_OK=false
    fi
done

echo ""
if [ "$ALL_OK" = true ]; then
    echo "All $COUNT Chrome instances are ready."
else
    echo "WARNING: Some instances failed to start. Try running again or check for port conflicts."
fi
