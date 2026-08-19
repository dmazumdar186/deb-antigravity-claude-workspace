#!/bin/bash
# Kill all chrome-agent Chrome instances

BASE_PORT=9223

for i in $(seq 1 5); do
    PORT=$((BASE_PORT + i - 1))
    PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Killing Agent $i (port $PORT, PID: $PID)"
        kill $PID 2>/dev/null
    else
        echo "Agent $i (port $PORT): not running"
    fi
done

# Clean up temp data dirs
rm -rf /tmp/chrome-agent-{1,2,3,4,5}
echo "Cleaned up temp data directories."
