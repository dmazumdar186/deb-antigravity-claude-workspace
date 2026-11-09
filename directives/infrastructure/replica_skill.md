# Directive: Replica skill pack (app-clone workflow skills)

Workspace-local SOP for installing [Replica](https://github.com/Jakeschincariol/replica-skill): eleven Claude Code skills that take an app from recon to a rebranded, deployed clean-room clone (`/replica-recon` → `architect` → `design` → `build` → `backend` → `test` → `diff` → `entrepreneur` → `brand` → `launch` → `deploy`). Pure Markdown plus six standard-library Python tools. No service, no ports, no API keys. MIT licensed.

## Goal

One reproducible command that clones/updates the upstream pack, scans every skill folder with SkillSpector, and copies the clean ones into a skills directory. Idempotent: an identical skill is skipped, a re-run converges.

## Inputs

- **None required.** No secrets, no env vars upstream.
- `skillspector` CLI (`uv tool install 'skillspector @ git+https://github.com/NVIDIA/skillspector.git'`); without it the copy aborts.
- Optional env overrides: `REPLICA_SKILL_DIR` (default `$HOME/dev/replica-skill`), `REPLICA_SKILL_REF` (vetted pin `77c9436fb3d18c3d58169efb8caf4fe906b0dc51`, 2026-10-03), `REPLICA_SKILL_TARGET` (default `<repo>/.claude/skills`; `$HOME/.claude/skills` for user-level), `REPLICA_SKILLS` (space-separated subset).

## Tools / scripts

- `execution/infrastructure/setup_replica_skill.sh`
  - `bash execution/infrastructure/setup_replica_skill.sh`: clone/update, scan, copy
  - `--dry-run`: print the plan, change nothing
  - `--uninstall` (alias `--down`): print the `rm -rf` commands for the installed skill folders and the clone. Nothing is deleted automatically (security rule).
- Untrusted reference clone (read-only): `/tmp/ext/Jakeschincariol_replica-skill`. Canonical docs: README "Install".
- Alternative upstream path (namespaced `/replica-skill:replica-recon`): `/plugin marketplace add Jakeschincariol/replica-skill` then `/plugin install replica-skill@replica-skill`.

## How it runs

- Fast-forward-only `git pull` (or `checkout $REPLICA_SKILL_REF`) into the clone.
- For each `replica-*/` folder with a `SKILL.md`: `skillspector scan <dir> --no-llm -f json`; HIGH/CRITICAL or a failed scan aborts; otherwise `cp -R` into `$REPLICA_SKILL_TARGET/<name>/` unless `diff -rq` says it is already identical.
- Nothing upstream is executed. The skills' Python tools run later, on demand, from the skill folder.

## Steps

1. `bash execution/infrastructure/setup_replica_skill.sh --dry-run` to preview.
2. Install `skillspector` if missing (see Inputs).
3. Run it for real. Prefer a subset (`REPLICA_SKILLS="replica-recon replica-entrepreneur"`) or a user-level target; see Edge cases on token cost.
4. Use: `/replica-recon <app URL>`. Each skill reads/writes `replica/` in the current project.
5. Optional upstream self-test (from the clone, not this repo): `python3 -I -m unittest discover -s tests -v`.

## Outputs

- `$REPLICA_SKILL_TARGET/replica-*/` (SKILL.md, templates, `*.py` tools).
- `$REPLICA_SKILL_DIR` upstream clone.

## Edge cases / learnings

- **Vetting (2026-11-09, pin `77c9436`):** every SKILL.md and template read by hand; all Python is stdlib (`argparse csv json re zlib struct math os`), no `subprocess`, `socket`, `urllib`, `eval`/`exec`, no install hooks, no network. Writes only to user-given `--out` paths. SKILL.md bodies tell the agent never to scrape, never handle passwords/live keys and to deploy only on the user's go. SkillSpector was **not** run in the vetting container (CLI install refused there), so the pack was not copied into this repo; the script enforces the scan on the operator's machine.
- **Token cost:** 11 skill descriptions (~4.5k chars) join every model call's prefix once installed in the repo (`.claude/rules/token-economy.md` §1). Install only the skills you will use, or install user-level / as the plugin when actively cloning an app, then uninstall.
- **Legal:** the pack rebuilds features, not assets; `replica-brand`'s sweep and `replica-deploy`'s preflight block launch under the original's name. Trademark checks are screening only; not legal advice.
- **Stale files:** the copy overwrites but does not prune files upstream removed; run `--uninstall` commands then reinstall for a clean tree.
- **Windows:** run from Git Bash or WSL; set `REPLICA_SKILL_DIR` to a Windows-reachable path. Python tools run with `py` locally or `python3` in the cloud.

## Trust record — skillspector scan 2026-11-09 (pin `77c9436`, `--no-llm`)

| Skill | Max | Finding | Verdict |
|---|---|---|---|
| replica-recon, -architect, -design, -build, -backend, -diff | NONE | — | clean |
| replica-brand | MEDIUM | LP3: no `allowed-tools` declared, code reads files | accepted (stdlib file reads only) |
| replica-entrepreneur | MEDIUM | LP3: no `allowed-tools`, file_write + "network" | accepted: `reviews.py` only regex-matches `https?://` strings in a local CSV, no network call |
| replica-deploy | MEDIUM | RP1: unpinned `npx playwright` | accepted (dev dependency in instructions, not an MCP server) |
| replica-launch | **HIGH** | YR4 YARA `mcp_tool_poisoning_metadata`: a literal U+200D in `listing.py:50` | **false positive**: it is the zero-width joiner inside `length()`, which counts emoji ZWJ sequences as one character; no hidden text in any SKILL.md (full repo swept for U+200B-200F, 202A-202E, 2060, 2066-2069, FEFF: only this line and its unit test) |
| replica-test | **HIGH** x2 | AE1 "incomplete referenced artifact analysis" of `e2e.example.spec.ts` (+ 2x RP1 MEDIUM) | **false positive**: the scanner's parser gave up on a 40-line Playwright example (no network beyond `page.goto` on the local dev server, no eval/exec/env access); upstream remediation text itself says partial analysis is not evidence of evasion |

Consequence: `setup_replica_skill.sh` still **aborts** on replica-launch and replica-test because the gate is
strict on HIGH by design. To install the reviewed pack, install the 9 clean/MEDIUM skills with
`REPLICA_SKILLS="replica-recon replica-architect replica-design replica-build replica-backend replica-diff replica-brand replica-entrepreneur replica-deploy"`
and copy the two reviewed ones by hand only after re-checking the diff against `77c9436`.

**Installed 2026-11-09** (operator: "install all 11"): 9 skills via the script with the `REPLICA_SKILLS`
subset above, then `replica-launch` and `replica-test` copied by hand from the clean clone at `77c9436`
(`diff -rq` identical). Upstream MIT licence kept at `docs/reference/third_party/replica-skill-LICENSE`.
Adds ~4.5k chars of skill descriptions to every call; jev skill menu 38 → 49.
