"""
description: Render the friend's `.github/workflows/job_digest.yml` from their
    profile.yaml — the GitHub Actions cron that runs job_digest daily on THEIR
    account, with THEIR keys, entirely separate from the operator's own
    job-search-daily workflow (pattern reference only; never modified here).
inputs: profile: Profile (digest.hour_local, digest.timezone drive the cron;
    nothing else about the profile affects the workflow text). layout:
    "standalone" (default) renders the workflow for a friend's deployed repo
    (profile.yaml + engine/job_digest/** + engine/requirements.txt, commands
    run as `PYTHONPATH=engine python -m job_digest.cli ...`); "workspace"
    keeps the in-repo module path (`python -m
    execution.personal_workflows.job_digest.cli ...`) for operator testing
    only — never used for a real friend deploy.
outputs: render_workflow(profile, *, minute=13, layout="standalone") -> str —
    a complete workflow YAML document, parseable by yaml.safe_load, containing
    one `schedule` cron pair per distinct UTC-offset group the target
    timezone observes across the year (~40 min apart per group, so a GitHub
    Actions scheduling drop/delay on one fire still has the other).

DST handling: GitHub Actions cron carries no timezone and no relative
"nth weekday of month" semantics, so we can't encode the real transition day
in cron. Instead we sample the target zone's actual UTC offset at hour_local
on the 1st of every month in the current year (ZoneInfo — always correct for
the sampled instant, no hardcoded month tables) and group months by distinct
offset, emitting one cron pair per group with its own `month` field. A zone
with a single offset all year (no DST) gets one ungated pair. This is exact
for the sampled day; a zone whose real transition date falls after the 1st of
its transition month can therefore show that boundary month grouped with the
"wrong" side for part of the month — an accepted, documented edge (see the
YAML comment above the schedule block) rather than a full weekday-aware DST
calendar, which cron cannot express anyway.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .profile_schema import Profile, load_profile

_PAIR_GAP_MINUTES = 40
_DEFAULT_MINUTE = 13
_DEFAULT_LAYOUT = "standalone"


def _utc_offset_minutes(tz: ZoneInfo, year: int, month: int, hour: int) -> int:
    dt = datetime(year, month, 1, hour, 0, tzinfo=tz)
    offset = dt.utcoffset()
    return int(offset.total_seconds() // 60) if offset is not None else 0


def _compress_months(months: list[int]) -> str:
    """[1,2,3,4,11,12] -> '1-4,11-12'. Assumes sorted-ascending 1..12 input; does
    not merge across the Dec/Jan boundary (cron has no wraparound range, so a
    group spanning it is written as two comma-joined ranges instead, which is
    exactly what happens naturally here)."""
    months = sorted(set(months))
    if not months:
        return "*"
    ranges: list[tuple[int, int]] = []
    start = prev = months[0]
    for m in months[1:]:
        if m == prev + 1:
            prev = m
            continue
        ranges.append((start, prev))
        start = prev = m
    ranges.append((start, prev))
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def _to_utc(hour_local: int, minute_local: int, offset_minutes: int) -> tuple[int, int, int]:
    """Return (hour, minute, day_shift): day_shift is -1/0/+1 for whether the
    UTC instant falls on the previous/same/next calendar day vs. the local
    trigger — informational only, since cron's day-of-month/day-of-week
    fields stay wildcarded here and so are unaffected either way."""
    total_local = hour_local * 60 + minute_local
    raw = total_local - offset_minutes
    day_shift = -1 if raw < 0 else (1 if raw >= 1440 else 0)
    total_utc = raw % 1440
    hour, minute = divmod(total_utc, 60)
    return hour, minute, day_shift


def _add_minutes(hour: int, minute: int, add: int) -> tuple[int, int]:
    total = (hour * 60 + minute + add) % 1440
    return divmod(total, 60)


def _cron_pair(hour_local: int, minute_local: int, offset_minutes: int, month_field: str) -> tuple[str, str, int]:
    h1, m1, day_shift = _to_utc(hour_local, minute_local, offset_minutes)
    h2, m2 = _add_minutes(h1, m1, _PAIR_GAP_MINUTES)
    mf = month_field if month_field else "*"
    return (
        f"{m1} {h1} * {mf} *",
        f"{m2} {h2} * {mf} *",
        day_shift,
    )


def _schedule_groups(profile: Profile, minute: int, year: int | None = None) -> list[dict]:
    """One entry per distinct UTC-offset the zone observes across `year`,
    most-positive-offset (summer/DST side) first, each carrying its cron
    pair, month field, raw offset, and day_shift."""
    tz = ZoneInfo(profile.digest.timezone)
    hour_local = profile.digest.hour_local
    year = year if year is not None else datetime.now().year

    offsets = {month: _utc_offset_minutes(tz, year, month, hour_local) for month in range(1, 13)}
    distinct_offsets = sorted(set(offsets.values()), reverse=True)

    groups: list[dict] = []
    for offset in distinct_offsets:
        months = [month for month, o in offsets.items() if o == offset]
        month_field = "" if len(distinct_offsets) == 1 else _compress_months(months)
        c1, c2, day_shift = _cron_pair(hour_local, minute, offset, month_field)
        groups.append(
            {
                "crons": (c1, c2),
                "offset": offset,
                "months": month_field or "*",
                "day_shift": day_shift,
            }
        )
    return groups


def _format_offset(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    hours, minutes = divmod(abs(offset_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}" if minutes else f"UTC{sign}{hours}"


def _render_schedule_block(profile: Profile, minute: int, year: int | None = None) -> str:
    groups = _schedule_groups(profile, minute, year)
    lines = [
        "  schedule:",
        f"    # {profile.digest.timezone} {profile.digest.hour_local:02d}:{minute:02d} local, "
        f"two fires ~{_PAIR_GAP_MINUTES} min apart per offset group below.",
    ]
    for group in groups:
        note = ""
        if group["day_shift"] == -1:
            note = " — UTC time falls on the previous local calendar day; harmless, cron's day fields stay wildcarded"
        elif group["day_shift"] == 1:
            note = " — UTC time falls on the next local calendar day; harmless, cron's day fields stay wildcarded"
        lines.append(f"    # months {group['months']} ({_format_offset(group['offset'])}){note}")
        for cron in group["crons"]:
            lines.append(f'    - cron: "{cron}"')
    if len(groups) > 1:
        lines.append(
            "    # DST groups above are computed by sampling this zone's real UTC offset "
            "(ZoneInfo) at hour_local on the 1st of every month in the current year — exact "
            "for that sampled instant. A zone whose real transition date falls after the 1st "
            "of its transition month can show that boundary month grouped on the wrong side "
            "for the first few days; accepted and documented, not re-derived every render."
        )
    return "\n".join(lines)


def render_workflow(profile: Profile, *, minute: int = _DEFAULT_MINUTE, layout: str = _DEFAULT_LAYOUT, profile_path: str = "profile.yaml") -> str:
    """Return the complete job_digest.yml workflow text for this profile.

    layout="standalone" (default): the friend's deployed repo layout —
    profile.yaml, engine/job_digest/**, engine/requirements.txt at repo root;
    every command is `PYTHONPATH=engine python -m job_digest.cli ...`.
    layout="workspace": this workspace's in-repo module path, for operator
    testing only — never used for a real friend deploy.
    """
    if layout not in ("standalone", "workspace"):
        raise ValueError(f"unknown layout {layout!r}; expected 'standalone' or 'workspace'")

    schedule_block = _render_schedule_block(profile, minute)

    if layout == "standalone":
        install_cmd = "pip install -r engine/requirements.txt"
        run_cmd = f'PYTHONPATH=engine python -m job_digest.cli run {profile_path} --mode "$MODE"'
    else:
        install_cmd = "pip install -r requirements.txt"
        run_cmd = f'python -m execution.personal_workflows.job_digest.cli run {profile_path} --mode "$MODE"'

    return f'''name: job-digest

# Generated by execution/personal_workflows/job_digest/workflow_render.py from
# this repo's profile.yaml. Re-run `<cli> render-workflow profile.yaml`
# after changing digest.hour_local or digest.timezone — edits made directly
# to this file are overwritten on the next render.

"on":
{schedule_block}
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Don't send email / write the sheet — just produce the run summary."
        required: false
        default: false
        type: boolean

concurrency:
  group: job-digest
  cancel-in-progress: false

# Note: GitHub Actions grants permissions per JOB, not per step — there is no
# way to scope `contents: write` to only the state-commit step and
# `issues: write` to only the failure-issue step, so both are declared here
# even though most steps in this job need no write access at all.
permissions:
  contents: write
  issues: write

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          {install_cmd}

      - name: Decode Google service account (if configured)
        env:
          GOOGLE_SERVICE_ACCOUNT_JSON_B64: ${{{{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON_B64 }}}}
        run: |
          if [ -n "$GOOGLE_SERVICE_ACCOUNT_JSON_B64" ]; then
            mkdir -p credentials
            echo "$GOOGLE_SERVICE_ACCOUNT_JSON_B64" | base64 -d > credentials/service_account.json
            python -c "import json; json.load(open('credentials/service_account.json'))"
          else
            echo "GOOGLE_SERVICE_ACCOUNT_JSON_B64 not set — sheet writing will be skipped this run."
          fi

      - name: Run job_digest
        env:
          GMAIL_SMTP_USER: ${{{{ secrets.GMAIL_SMTP_USER }}}}
          GMAIL_SMTP_APP_PASSWORD: ${{{{ secrets.GMAIL_SMTP_APP_PASSWORD }}}}
          SHEETS_SPREADSHEET_ID: ${{{{ secrets.SHEETS_SPREADSHEET_ID }}}}
          GOOGLE_SERVICE_ACCOUNT_PATH: credentials/service_account.json
          GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          FRANCE_TRAVAIL_CLIENT_ID: ${{{{ secrets.FRANCE_TRAVAIL_CLIENT_ID }}}}
          FRANCE_TRAVAIL_CLIENT_SECRET: ${{{{ secrets.FRANCE_TRAVAIL_CLIENT_SECRET }}}}
        run: |
          MODE="live"
          if [ "${{{{ github.event.inputs.dry_run }}}}" = "true" ]; then
            MODE="dry"
          fi
          {run_cmd}

      - name: Commit state back to the repo
        # Skipped on dry runs — a dry run's state dir may be empty/absent and
        # should never be committed as if jobs were actually seen/sent.
        if: always() && github.event.inputs.dry_run != 'true'
        run: |
          git config user.name job-digest-bot
          git config user.email job-digest-bot@users.noreply.github.com
          mkdir -p state
          git add state
          git commit -m "state: $(date -u +%F) [skip ci]" || echo "nothing to commit"
          # The digest has already been sent by this point — a failed push only
          # risks re-emailing the same jobs next run, never losing one. Retry
          # once (a concurrent run's push is a plausible transient cause)
          # before giving up; a second failure is a hard step failure (not a
          # silent warning) so the "Open or bump failure issue" step below
          # fires and a human notices.
          if git pull --rebase --autostash origin ${{{{ github.ref_name }}}} && git push; then
            echo "state push succeeded"
          elif git pull --rebase --autostash origin ${{{{ github.ref_name }}}} && git push; then
            echo "state push succeeded on retry"
          else
            echo "::error::state push failed twice"
            exit 1
          fi

      - name: Upload run artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: job-digest-run-${{{{ github.run_id }}}}
          path: .tmp/job_digest
          if-no-files-found: ignore
          retention-days: 7

      - name: Open or bump failure issue
        if: failure()
        uses: actions/github-script@v7
        env:
          RUN_URL: ${{{{ github.server_url }}}}/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}
        with:
          script: |
            const owner = context.repo.owner;
            const repo = context.repo.repo;
            const runUrl = process.env.RUN_URL;
            const title = "[job-digest] daily run failed";
            const body = [
              `**Run failed at ${{new Date().toISOString()}}**`,
              ``,
              `**Failed run:** ${{runUrl}}`,
              ``,
              `**Exit-code hints:**`,
              `- exit 3 — acceptance gate failed (bad filters or a source misbehaving)`,
              `- exit 5 — SMTP auth failed — rotate the Gmail App Password at https://myaccount.google.com/apppasswords and update the GMAIL_SMTP_APP_PASSWORD secret`,
              `- exit 6 — Google Sheet write failed — check the service account still has editor access`,
              `- no exit code (state push failed twice) — the digest email has already been sent; only the state commit-back to this repo failed, so the next run may re-email today's jobs`,
            ].join("\\n");

            const q = `repo:${{owner}}/${{repo}} is:issue is:open in:title "${{title}}"`;
            const search = await github.rest.search.issuesAndPullRequests({{ q }});
            const existing = (search.data.items || []).find(i => i.title === title);
            if (existing) {{
              await github.rest.issues.createComment({{ owner, repo, issue_number: existing.number, body }});
            }} else {{
              await github.rest.issues.create({{ owner, repo, title, body, labels: ["alarm", "job-digest", "automated"] }});
            }}
'''


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the job_digest GitHub Actions workflow from a profile.")
    parser.add_argument("profile", help="Path to profile.yaml")
    parser.add_argument("--out", default=".github/workflows/job_digest.yml", help="Output workflow path")
    parser.add_argument("--minute", type=int, default=_DEFAULT_MINUTE, help="Minute offset for the first cron fire")
    parser.add_argument(
        "--layout",
        choices=["standalone", "workspace"],
        default=_DEFAULT_LAYOUT,
        help="'standalone' (default) for a friend's deployed repo; 'workspace' for operator testing only",
    )
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    text = render_workflow(profile, minute=args.minute, layout=args.layout)

    from pathlib import Path

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
