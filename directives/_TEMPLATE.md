# <Directive Title>

## Purpose

<One paragraph: what business outcome this enables.>

## When to invoke

<Bullet list of triggering conditions.>

## Inputs

- `<name>`: `<type>` — <description, source>

## Outputs

- `<name>`: `<type>` — <description, destination>

## Exit Criteria (declarative — read this before claiming "done")

Imperative ("call Apollo, then write to Sheet") rots fast. Declarative is durable.
Define DONE as a verifiable predicate, not a sequence of steps.

Example exit criteria for an enrichment directive:
- Google Sheet `<name>` exists with columns `[name, company, email, domain, enrichment_score]`.
- Row count >= `0.8 * input_count` (at most 20% can be skipped).
- No empty `email` cell.
- No row's `enrichment_score < 0.3`.
- Sheet last-modified timestamp within the last 1 hour.

## Scripts (Layer 3)

- `execution/<category>/<name>.py`

## Edge cases

- <e.g., "domain in blocklist: skip + log to .tmp/skipped.csv">.

## Changelog

- YYYY-MM-DD: <what changed>
