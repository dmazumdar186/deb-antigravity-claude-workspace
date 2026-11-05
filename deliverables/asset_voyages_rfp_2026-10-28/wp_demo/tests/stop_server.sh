#!/usr/bin/env bash
# Stops ONLY this suite's Playground servers (ports 9400 and 9410). Other servers on the machine
# (QA runs on other ports) and the zip server on 9401 are left alone.
for pid in $(ps -eo pid=,args= | awk '$2 == "node" && /wp-playground-cli/ && / server / && /--port=(9400|9410)( |$)/ {print $1}'); do
	kill "$pid" 2>/dev/null || true
done
exit 0
