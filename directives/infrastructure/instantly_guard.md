# Instantly Campaign Guard

## Goal

Keep an Instantly cold-email campaign's bounce rate below the Bounce-Protect threshold without manual babysitting. Each run finds bounces new since the last run, blocklists their domains workspace-wide, MX-screens leads that have not been contacted yet, deletes the ones whose domain cannot receive mail, and writes a dated log.

## Tools/Scripts

| Script | Role |
|---|---|
| `execution/infrastructure/instantly_guard.py` | The guard itself — the cron entry point |
| `execution/infrastructure/instantly_bounce_analysis.py` | Measures what fraction of a campaign's bounces an MX screen can actually catch |
| `tests/test_instantly_guard_unit.py` | Unit + mutation-path coverage (no network) |
| `tests/acceptance_instantly_guard.py` | Live output-acceptance gate against the real campaign |

## Inputs

| Input | Required | Notes |
|---|---|---|
| `campaign_id` (positional) | yes | Instantly campaign UUID |
| `--no-dry-run` | no | Default is DRY RUN. Without this nothing is ever changed. |
| `--api-key-env` | no | Env var holding the key. Default `INSTANTLY_NOTIFIER_API_KEY`. |
| `--env-file` | no | Fallback `.env` to read the key from. Default `./.env`. |
| `--state-file` | no | Default `.instantly_guard_state.json`. A `.lock` sits beside it. |
| `--log-dir` | no | Default `./logs`. |
| `--resolver` | no | `auto` (default) / `system` / `doh`. |
| `--dns-timeout`, `--workers` | no | Default 10s, 10 threads. |
| env: the key named by `--api-key-env` | yes | Read from environment first, then `--env-file`. |

## Outputs

| Output | Where |
|---|---|
| JSON run summary | stdout |
| One-line human summary | stderr (so `\| jq` on stdout stays clean) |
| Dated log, one JSON line per run | `<log-dir>/instantly_guard_<campaign8>_<YYYY-MM-DD>.log` |
| Per-campaign state (`last_run`, `seen_bounce_ids`, `blocklisted_domains`) | `<state-file>` — **not written on a dry run** |
| Remote side effects | blocklist entries created; leads deleted. Both only under `--no-dry-run`. |


## When to run

- **After a campaign trips Bounce Protect** (`status: -2`) — clean before resuming.
- **On a cron**, daily or twice-daily, against any live campaign. The script is idempotent: domains already on the blocklist are detected and skipped, and leads already deleted cannot be re-screened.
- **Before activating a newly-uploaded campaign** — run once in dry-run to see how much of the list is structurally dead.

## Steps

1. `GET /campaigns/{id}` — confirms the campaign exists and reports its status label (Draft / Active / Paused / Completed / Running Subsequences / Accounts Unhealthy / **Bounce Protect** / Account Suspended).
2. `POST /leads/list` with `filter: FILTER_VAL_BOUNCED` — pulls every bounced lead, paginating on `starting_after` / `next_starting_after`.
3. Diffs against `seen_bounce_ids` in the state file to isolate bounces **new since the last run**.
4. Extracts the unique domain from each new bounced address, drops any already known-blocked, and confirms the rest against `GET /block-lists-entries?domains_only=true&search=<domain>` before writing.
5. `POST /block-lists-entries/bulk-create` with `{"bl_values": [...]}` (max 1000 per call). This blocks the domain across **every** campaign in the workspace, not just this one.
6. `POST /leads/list` with `filter: FILTER_VAL_NOT_CONTACTED` — the only population worth screening, since already-contacted leads cannot bounce again.
7. MX-screens each unique domain once (cached, 10-way thread pool) and classifies:
   - `NXDOMAIN` — domain does not exist
   - `NO_MX` — domain exists, no MX record (an A-record check confirms existence before this verdict is issued)
   - `NULL_MX` — MX is `.`, RFC 7505, explicitly refuses all mail
   - `OK` — takes mail
   - `ERROR_*` — the resolver failed. **Never deleted.** See "Resolver failures" below.
8. `DELETE /leads` with `{campaign_id, ids}` for every lead on a `NXDOMAIN` / `NO_MX` / `NULL_MX` domain.
9. Re-pulls the campaign, writes a JSON line to `<log-dir>/instantly_guard_<campaign8>_<YYYY-MM-DD>.log`, and atomically updates the state file.

## Prerequisites

- An Instantly v2 API key in `.env`, in the workspace that owns the campaign. Default env var: `INSTANTLY_NOTIFIER_API_KEY`; override with `--api-key-env`.
  - **An Instantly API key is scoped to one workspace.** A key from a different workspace returns `404 Campaign not found`, not `401`. If you get a 404 on a campaign ID you know is real, you are holding the wrong key.
  - `INSTANTLY_API_KEY` is Accessory-Masters-scoped and locked per `CLAUDE.local.md` — do not use it here.
- Required scopes: `leads:list`, `leads:delete`, `block_list_entries:create` (or the `all:*` equivalents).
- No third-party packages required. `dnspython` is used when importable and port 53 works; otherwise the script falls back to DNS-over-HTTPS automatically.

## Usage

```bash
# Dry run (the default) — reports would_blocklist / would_delete, changes nothing
py -3.14 execution/infrastructure/instantly_guard.py <campaign-id>

# Apply
py -3.14 execution/infrastructure/instantly_guard.py <campaign-id> --no-dry-run

# Force a resolver backend (auto is default)
py -3.14 execution/infrastructure/instantly_guard.py <campaign-id> --resolver doh

# Custom state + log locations (cron-friendly)
py -3.14 execution/infrastructure/instantly_guard.py <campaign-id> --no-dry-run \
  --state-file .tmp/instantly_cleanup/guard_state.json \
  --log-dir .tmp/instantly_cleanup/logs
```

**Use `py -3.14`, not `py`.** See "Interpreter" below.

## Expected output

```json
{
  "campaign_name": "SMB Acquisition- Other- 170826",
  "campaign_status_label": "Bounce Protect",
  "dry_run": true,
  "bounced_total": 13,
  "bounced_new": 13,
  "domains_to_blocklist": [],
  "resolver_backend": "doh",
  "not_contacted": 117,
  "domains_screened": 104,
  "dns_verdicts": {"OK": 104},
  "dead_leads": 0,
  "would_delete": 0,
  "remaining_leads": 214,
  "api_calls": 19,
  "elapsed_seconds": 24.4
}
```

A one-line human summary goes to stderr so `... | jq` on stdout stays clean.

## Edge Cases

### Resolver failures are not verdicts

`ERROR_TIMEOUT`, `ERROR_SERVFAIL`, `ERROR_RCODE_*`, `ERROR_RESOLVER` mean *the lookup failed*, not *the domain is dead*. They are excluded from `DEAD_VERDICTS` and can never trigger a deletion.

This is load-bearing. On 2026-08-26 a first screening run against this campaign returned `ERROR_TIMEOUT` for **all 186 domains**, including `ups.com`, because the environment blocked outbound port 53. Had timeouts been coded as "no MX", the run would have deleted the entire lead list. The `auto` backend now probes a known-good domain over port 53 before trusting it, and falls back to DNS-over-HTTPS when the probe fails. See `~/.claude/rules/probe-failure-is-not-a-verdict.md`.

### Interpreter

This script is invoked as `py -3.14 <path>`, not `py <path>`. The Windows `py` launcher honours a script's shebang line, so `py script.py` and `py -c` can select **different interpreters** — on this machine, `C:\Python314` vs `pythoncore-3.14-64`. A package installed by `py -m pip` may therefore be missing from the interpreter that actually runs the file. The script no longer hard-depends on `dnspython` for this reason, but pin the interpreter anyway.

### Cloudflare blocks the default User-Agent

Instantly's API sits behind Cloudflare, which returns `403 error code: 1010` to `urllib`'s default UA. The client sends a browser-shaped `User-Agent`; do not remove it.

### Content-Type on bodyless requests

Instantly runs Fastify, which rejects `Content-Type: application/json` with an empty body as `400 FST_ERR_CTP_EMPTY_JSON_BODY`. This silently breaks every `DELETE /leads/{id}`. The client only sets `Content-Type` when a body exists.

### MX screening is not email verification

MX screening catches structurally dead domains. It does **not** catch a non-existent mailbox on a healthy domain — and that is the majority of real bounces.

Do not take that on faith, and do not take the numbers below on faith either. `execution/infrastructure/instantly_bounce_analysis.py` measures it for any campaign and writes a JSON artifact:

```bash
py -3.14 execution/infrastructure/instantly_bounce_analysis.py \
  --leads .tmp/instantly_cleanup/leads_raw.json --contacted 101
```

It screens the **bounced** domains — the opposite population from the guard — to answer "would this screen have caught the failures we already know about?"

Measured on this campaign (artifact: `.tmp/instantly_cleanup/bounce_analysis.json`):

| | |
|---|---|
| bounces an MX screen would have caught | **3 of 13** (`emailaeonstaffing.com` NXDOMAIN, `unisub.app` NXDOMAIN, `globaloutsourcing.mn` NO_MX) |
| bounces it would have missed | 10 — valid Google / Outlook / Umbler MX, dead mailbox |

**A clean `dns_verdicts` is not permission to resume.** Verify the addresses.

### Get the denominator right, or the campaign looks unsalvageable when it isn't

Instantly auto-pauses a campaign above **5% of EMAILS SENT**, checked once it has sent at least **200 emails** (default, customisable per workspace — [High Bounce Auto-Pause](https://help.instantly.ai/en/articles/9823139-high-bounce-auto-pause-feature)).

The denominator is emails sent, **not leads contacted**. On a multi-step sequence those differ by the number of steps — this campaign averages 2.08 emails per contacted lead, so a contacted-lead denominator roughly *doubles* the apparent rate. An early version of this analysis used it and concluded the campaign was unrecoverable. It is not.

Pull the real counters from `GET /campaigns/analytics?id=<campaign>` (`emails_sent_count`, `bounced_count`, `contacted_count`) — the script does this for you with `--campaign-id`:

```bash
py -3.14 execution/infrastructure/instantly_bounce_analysis.py \
  --leads .tmp/instantly_cleanup/leads_after_cleanup.json \
  --campaign-id <campaign-id>
```

Measured on this campaign:

| scenario | rate on emails sent | verdict |
|---|---|---|
| now — why it paused | 13 / 210 = **6.19%** | tripped |
| resume as-is | **5.42%** | **RE-TRIPS** |
| resume after verifying the 117 remaining leads | **3.12%** | **CLEARS** |

Projection model, stated so it can be argued with: `projected = (bounces + uncontacted × residual_rate) / (emails_sent + uncontacted × emails_per_lead)`, where `residual_rate` is the share of observed bounces an MX screen cannot catch, and the verified case assumes verification removes ~90% of dead mailboxes. It assumes the uncontacted population behaves like the contacted one — the weakest link in the chain, and why this is a projection, not a promise.

The practical reading: **verification is the unlock, and it is sufficient.** MX screening alone leaves the campaign marginal (5.42% against a 5% ceiling); verifying the remaining addresses puts it comfortably clear.

### Leads may have no lead list

Leads uploaded straight to a campaign have `list_id: null` and no `verification_status`. `GET /lead-lists/{id}/verification-stats` then has nothing to target, and `allow_risky_contacts: false` is inert — it can only exclude leads already flagged Risky or Catch-All, and an unverified lead is flagged neither.

### Concurrent runs are refused

The run holds an advisory lock at `<state-file>.lock`. Two overlapping cron ticks would otherwise both read the same state and the second `save_state()` would silently drop the first's `seen_bounce_ids` / `blocklisted_domains` updates -- the atomic tmp+replace write guards against a torn file, not against that race. A second run exits with a clear FATAL rather than clobbering. A lock older than an hour is assumed to belong to a killed run and is stolen, so one crash cannot wedge the cron permanently.

### An aborted run still writes its log

If a blocklist or delete batch fails partway, real mutations may already have landed. The partial summary is written to the dated log with an `aborted` field before the exception propagates. A destructive action is never invisible -- the log is this tool's whole value proposition, and an early version exited before writing it.

### Dry run does not persist state

By design. `bounced_new` will keep reporting the full bounce count until the first `--no-dry-run` run writes the state file.

## Verify after running

```bash
# The dated log — one JSON line per run
cat logs/instantly_guard_<campaign8>_$(date +%F).log | tail -1

# Confirm a domain actually landed on the blocklist
py -3.14 -c "..."  # GET /block-lists-entries?domains_only=true&search=<domain>

# Re-run in dry-run: a clean campaign reports dead_leads 0 and domains_to_blocklist []
py -3.14 execution/infrastructure/instantly_guard.py <campaign-id>
```

## Exit Criteria

A run is successful when all of the following hold:

- Exit code 0, and the JSON summary carries no `aborted` key.
- `resolver_backend` is `system` or `doh` — never a run where every domain came back `ERROR_*`. A verdict distribution that is ~100% one error class is a failed probe, not a finding; discard it and fix the transport.
- `dns_verdicts` contains at least one `OK`. A screen with zero healthy domains across a real campaign is a transport failure.
- A new JSON line exists in `<log-dir>/instantly_guard_<campaign8>_<date>.log`.
- On `--no-dry-run`: `<state-file>` exists and its `last_run` matches this run, and the `.lock` beside it has been released.
- `deleted` equals `dead_leads`, and every deleted lead's domain verdict is in `NXDOMAIN` / `NO_MX` / `NULL_MX` — never `OK`, never `ERROR_*`.

The campaign is only considered **clean** when a subsequent dry run reports `dead_leads: 0` and `domains_to_blocklist: []`.

Clean is not the same as **resumable**. Resumable additionally requires `instantly_bounce_analysis.py --campaign-id <id>` to report `clears_threshold_after_verification: true` **and** the verification actually to have been done — the projection is not the act. Check the rate on the emails-sent denominator, never on contacted leads.

A third precondition sits outside this tool: the campaign must have sending accounts attached (`email_list` non-empty on the campaign object). A campaign with `email_list: []` will not send no matter how clean its leads are.

## What it deliberately does not do

- **Never** calls `POST /campaigns/{id}/activate`. Resuming a campaign is a human decision that should follow reading the numbers.
- **Never** modifies a campaign setting (`allow_risky_contacts`, `daily_limit`, sequences, sending accounts).
- **Never** deletes a lead on an `OK` or `ERROR_*` domain.
- **Never touches a lead that has already been contacted**, even on a provably dead domain. A contacted lead cannot bounce again, so deleting it destroys send history for zero deliverability gain. The guard screens `FILTER_VAL_NOT_CONTACTED` and then *independently* re-excludes anything with status Completed/Bounced or a populated `timestamp_last_contact` — it trusts the upstream filter for scope, never for safety.

## Provenance of the 2026-08-26 cleanup — read this before trusting the numbers

**The live cleanup on this campaign was NOT performed by this script.** Both facts below are true and they are two separate stories, not one:

1. On 2026-08-26 the campaign was cleaned: 9 domains blocklisted, 10 leads deleted (224 → 214). This was done by **ad-hoc single-use scripts written during that session**, which are not in this repo and were not code-reviewed.
2. `instantly_guard.py` was written in the same session to make that work repeatable. **Its apply path (`--no-dry-run`) has never executed against a live campaign.** Every line in `logs/instantly_guard_*.log` reads `"dry_run": true`. No state file has ever been written.

Two consequences worth knowing:

- **The guard would not have made all 10 deletions.** Its dry run at the time found **6**, not 10. The other 4 (`crownpacificrealty.com`, `tambo22chelsea.com`, `kaizenpartners.com`, `metascapelabs.com`) were already-contacted leads, which the guard excludes by design — see the bullet above. Those 4 were deleted on an explicit operator decision, after being shown labelled as already-contacted. That was a deliberate choice, not a defect, but it is **outside** what this tool will ever do on its own.
- **The apply path's only evidence is mock-fidelity.** `tests/test_instantly_guard_unit.py` drives `run(dry_run=False)` against a fake API and asserts the exact `bl_values` payload and the exact `ids` passed to `DELETE /leads`. That is real coverage of the logic, but it is not a live run. The first real `--no-dry-run` execution should be watched, not cron'd and forgotten.

Surfaced by an independent audit on 2026-08-26 (panel honest-gaps lens + adversarial pipeline auditor, converging separately on the same finding). Recorded here rather than quietly corrected, because "we built a guard" and "the campaign got cleaned" being presented as one story is exactly the kind of drift this directive exists to prevent.
