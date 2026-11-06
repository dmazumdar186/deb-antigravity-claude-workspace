#!/usr/bin/env bash
# Stops ONLY this suite's Playground servers (ports 9400 and 9410). Other servers on the machine
# (QA runs on other ports) and the zip server on 9401 are left alone.
P="${WP_PORT:-9400}"; A="${ALT_PORT:-9410}"
for pid in $(ps -eo pid=,args= | awk -v P="$P" -v A="$A" '$2 == "node" && /wp-playground-cli/ && / server / && $0 ~ ("--port=(" P "|" A ")( |$)") {print $1}'); do
	kill "$pid" 2>/dev/null || true
done
exit 0
