# Prospect Evidence Pack (two-check, recipient-eye)

## Purpose

Hand a prospect list to someone who will open every link (an agency founder, a client) only when every company
has survived two independent checks and a screenshot judged as that reader would. Born 2026-11-11 (agency referral
partner): a single-pass list named a company whose site was modern; the operator caught it, not the gate.

## When to invoke

- Any outward message that names a third-party company as a prospect, a "trigger", or "needing a new site/brand".
- Before Prospeo or any paid enrichment: build and spot-check the pack first; enrich only after the counterparty commits.

## Inputs

- Finder report per vertical (`.tmp/<client>/prospects_*.md`): worker brief with tests A–D below.
- Verifier rows `.tmp/<client>/pack/rows/<vertical>.json`: written by a SEPARATE worker that gets names + URLs only
  and must not read the finder's files. Keys: company, url, vertical, hq, size, size_source, trigger_quote,
  trigger_url, trigger_date, markers[], visual_verdict, visual_notes, desk_png, mob_png, finder_status,
  verifier_status, verifier_notes, jev_score.

Tests (both workers): A trigger in a fetched primary source dated inside the window; B hard markers from live HTML
(copyright, CMS/version, viewport, trigger absent); C Playwright screenshots 1440x900 + 390x844 read by the worker,
verdict DATED / MIXED / MODERN (MODERN = reject); D not already the reader's client.

## Outputs

- `pack.html` (cards: link, trigger quote + source + date, markers, verdicts, both screenshots; rejects greyed with reason)
  and `pack.csv`, via `python3 execution/gtm_icp_filters/prospect_evidence_pack.py --dir .tmp/<client>/pack`.

## Exit Criteria

- Every QUALIFIED row: finder_status == verifier_status == "PASS", visual_verdict != "MODERN", trigger_url and
  trigger_quote non-empty, trigger_date inside the window, markers non-empty, both PNGs exist.
- Finder/verifier disagreement = rejected (shown greyed, not deleted).
- Operator has spot-checked two random cards before any outward text uses the list.
- Outward text names only QUALIFIED rows; ranking words ("best", "stand out") only for the top Jev-scored rows.

## Edge cases

- Cookie walls / blank heroes: retry once; a capture artefact is never evidence.
- Copyright rewritten by JS: judge the rendered text, note the source value.
- Acquired companies: note who owns the brand decision (acquirer in-house team = weak).
- Contacts: free pass first (trigger documents, company pages, 510(k) summaries, WebSearch LinkedIn snippets,
  `execution/enrichment/email_mx_verify.py`); published emails only; paid enrichment needs operator approval.
