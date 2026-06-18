#!/usr/bin/env bash
# Compat shim — 2026-06-18.
#
# The user renamed this file to tests/parser_job_search_v2.sh in commit e420344.
# The cron workflow at .github/workflows/job_search_daily.yml still references
# the OLD name and cannot be updated yet (push refused: PAT lacks `workflow` scope).
# This shim keeps the cron green until the workflow YAML can be updated by an
# operator with the required token scope.
#
# Owed-work: edit job_search_daily.yml to replace this with the TRUE live synthetic
#   `python tests/live_front_door_job_search_v2.py --fetch-floor 5 --nonzero-sources-floor 2 --window 1`
# plus this file's removal once the YAML is updated.
exec bash "$(dirname "$0")/parser_job_search_v2.sh" "$@"
