# Instantly thread read (read-only)

**Goal:** read a lead's full Instantly thread (our sends + their reply) before drafting a response.

**Why a script:** the redteam gate blocks any inline command touching Instantly's emails endpoint
(it cannot tell a GET from a send). A committed, GET-only script is the sanctioned read path.

**Script:** `python3 execution/infrastructure/instantly_thread_read.py [--search <address>] [--campaign-id <id>] [--received-only] [--grep <name>] [--campaign <name substring>]`

Server-side `--search` matches addresses, not display names. To find a person by name:
`--campaign-id <id> --received-only --grep <surname>`, then re-run with `--search <their address>`
for the full thread.

**Inputs:** `INSTANTLY_API_KEY` (env / `.env`).

**Outputs:** `.tmp/instantly_threads/<search>.json` (campaigns + emails, oldest first) and the
thread printed as plain text.

**Edge cases:**
- `/emails` is limited to 20 req/min; the script spaces pages 3.2 s and backs off on 429/5xx.
- Pagination ceiling 20 pages x 100. A search with no hits prints `0 emails` and exits 0.
- If `--campaign` matches no email, all hits for the search are kept (no silent drop).

**Output contract:** read-only. Never add a send/reply call here; replies go through `/redteam`.
