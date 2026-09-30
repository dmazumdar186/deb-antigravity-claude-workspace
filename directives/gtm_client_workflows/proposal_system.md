# Proposal System (tracked, editable client proposals)

## Purpose

Turn the agreed scope, timeline and pricing for a client into a legally usable proposal in the reference format (`deliverables/_samples/proposal-system/`, Siva's build; page order also matches the Nick Saraev PandaDoc template): editable DOCX for Google Docs, plus a tracked HTML copy that pings Telegram on every open.

## When to invoke

- "New proposal for <client>", "send a proposal to", "costing for", or a change list / call transcript that needs to become a signable document.
- First client: GreenJobs / Keith Molony (`proposals/greenjobs-keith-v1.json`).

## Inputs

- `proposals/<slug>.json`: parties, dates, blocks. Every number must trace to the client record (for GreenJobs: `deliverables/greenjobs_redesign_2026-09-22/proposal/keith_costing_brief_2026-09-28.md` and `.tmp/keith_factsheet.md`). Unknowns go in `[square brackets]`, never guessed.
- Env for publishing: `PROPOSAL_WORKER_URL`, `PROPOSAL_PUBLISH_SECRET`. Worker secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PUBLISH_SECRET`.

## Outputs

- `out/<slug>/<slug>.docx|html|md` (gitignored build output); the DOCX copied to `deliverables/<client>/proposal/`.
- A legal review memo next to the DOCX (`LEGAL_REVIEW_<version>.md`): commitments table, number reconciliation, bracketed items, risks.
- Tracked URL `https://<worker>/p/<slug>`; Telegram message per human open.

## Exit criteria

- `build_proposal.py <slug>` exits 0; the DOCX opens; no `[` placeholder remains before sending (grep the `.md`).
- Every EUR figure in the DOCX appears in the legal memo's reconciliation table with a source.
- `GET /health` on the Worker returns `telegram_bound: true`; an incognito open of `/p/<slug>` produces one Telegram message; a refresh within 60 s produces none.

## Scripts (Layer 3)

- `execution/gtm_client_workflows/proposal_system/build_proposal.py`
- `execution/gtm_client_workflows/proposal_system/publish_proposal.py`
- `execution/gtm_client_workflows/proposal_system/worker/` (wrangler)

## Edge cases

- Google Docs cannot notify on open; the tracked link or the pixel URL embedded as a linked image is the only notification path.
- Link previewers (LinkedIn, WhatsApp, Slack, Telegram) fetch the URL when the link is pasted; they are detected by user agent and logged, not pushed.
- Prices are never put in a DM or email (operator rule, 2026-09-28); the proposal document is the only place figures live.
- Keith cannot open claude.ai artifact links; always send a Cloudflare URL.

## Changelog

- 2026-09-30: created. First proposal: GreenJobs v1.0 (rebuild €2,750, migration €6,500, Care €450/mo, Grow €650/mo, bundle credit €1,375).
