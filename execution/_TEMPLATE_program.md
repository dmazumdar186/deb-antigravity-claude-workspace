# Program — `<script_name>.py`

Co-located strategy file. Optional. Read by the orchestrator at runtime to decide
HOW to use the script (which mode, which inputs, in what order). Pattern from
Karpathy's `autoresearch` repo.

The Python script itself is deterministic (always does what `--mode` says). This
file is a plain-English plan that the orchestrator agent reads to pick `--mode`,
sequence calls, and handle failures.

## When to run this script

<Bullet list of trigger conditions.>

## Strategy (default)

1. **Discover**: try `--mode cheap` first on a sample. If quality acceptable, batch.
2. **Refine**: bump to `--mode balanced` on the failed/edge rows.
3. **Audit**: spot-check with `--mode premium` on 5% sample.

## Inputs the orchestrator needs to gather

- <name>: <where to source it from>
- <name>: <where to source it from>

## Output destination

- <where the result goes — Sheet, CSV, file path>

## Known edge cases

- <e.g., "domain == empty: skip + log">
- <e.g., "Apollo returns 429: backoff 60s + retry once">

## Cost ceiling

- Hard cap: <e.g., "$5 / run">. If projected cost exceeds, abort with a confirmation prompt.

## Failure mode

- <e.g., "per-row failures don't halt batch; final report shows skipped_count">.
