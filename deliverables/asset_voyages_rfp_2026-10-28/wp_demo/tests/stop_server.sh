#!/usr/bin/env bash
# Stops the local Playground server(s). The zip server on 9401 is left running.
for pid in $(ps -eo pid=,args= | awk '$2 == "node" && /wp-playground-cli/ && / server / {print $1}'); do
	kill "$pid" 2>/dev/null || true
done
exit 0
