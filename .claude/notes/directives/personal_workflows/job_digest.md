# Notes

- [technical] LinkedIn guest API geoIds verified live 2026-09-06 for FR, DE, AT, BE, NL, GB, CH, IN, SG, CA; US relies on a state-abbreviation regex in registry.py because guest results use "City, ST" strings.
- [learned] A live `preview` for a Sales Manager FR+DE profile fetched 345 jobs in ~5 min (LinkedIn FR 93, DE 96, WTTJ FR 104, Hellowork 35, RemoteOK 17; France Travail 0 without keys) and kept 13 relevant rows; run preview at most once per hour.
- [learned] A bare "Remote" location was classified HYBRID by the ported remote detector, silently dropping every RemoteOK/WeWorkRemotely job — location string is now checked before description text.
- [learned] Marking jobs seen before a confirmed email send burns jobs on the second daily cron fire; state is marked only for digest rows after a real SMTP send.
- [pattern] Acceptance gate must be an independent implementation (own tokenizer/alias match), otherwise it is a tautology of the filters and exit 3 is dead.
- [constraint] The friend's repo layout is engine/job_digest + engine/requirements.txt + PYTHONPATH=engine; the shipped zip excludes tests/ so fixtures live in job_digest/fixtures/.
- [constraint] A Claude subscription does not provide an ANTHROPIC_API_KEY; unattended runs default to the heuristic ranker.
- [pattern] scripts/package_job_digest.py refuses to build if any bundled file contains operator personal data (blocklist scan) — keep it that way for anything shared outside the workspace.
