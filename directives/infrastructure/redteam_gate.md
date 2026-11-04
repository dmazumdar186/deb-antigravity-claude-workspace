# Red-Team Gate for Outward Text (deterministic layer)

## Goal
No client email, negotiation reply, proposal or offer leaves the workspace unvetted. The operator
trusts outputs without cross-checking, so a misquote is shipped as fact (Asset Voyages, 2026-11:
"paid text alerts up to ≈ €30" when the €30 in the source was the UptimeRobot + AI cost). This
script is the deterministic half: it extracts checkable claims, grounds them against sources, keeps
a pass ledger keyed on the exact wording, and blocks Gmail send/draft tools until that wording passed.
The semantic half (four lens reviewers) is run by agents via `/redteam`.

**Output contract:** the operator receives the vetted draft text only; claim tables, verdict files
and ledger rows are machine state under `.tmp/redteam/` and never go into the email or the reply to
the operator (a waiver line goes to HANDOFF.md only).

## Operator prompts
- "Red team this email" / `/redteam` → ground + 4 lenses + record, then send.
- "Send it as is, skip the red team" → `waive --reason "operator: <their words>"`, paste the waiver line into HANDOFF.md.

## Inputs
- Draft file (`.txt`/`.md` plain; `.html`/`.htm` treated as HTML). Write the exact text you will send.
- Sources: files or directories (recursed; `.md .txt .html .htm .csv .json .eml .yaml .yml`; other
  types, the draft itself, and the state dir are skipped and reported). The thread, quotes, price lists.
- Lens verdict files (one per lens) containing `LENS: <name>`, `VERDICT: PASS|FAIL`, `DRAFT-SHA: <sha12>`.
- Env `REDTEAM_DIR` overrides the state dir (default `.tmp/redteam/`).

## Tools/Scripts
`execution/infrastructure/redteam_gate.py` (stdlib, no network, no LLM):
- `sha --draft PATH` → 12-hex DRAFT-SHA; lens reviewers stamp it.
- `ground --draft PATH --sources P [P ...] [--json]` → claim table; writes `ground/<sha12>.json`.
  Exit 0 all grounded, 1 any ungrounded (overclaims warn only), 2 usage error.
- `record --draft PATH --sources ... --verdicts V [V ...]` → needs 0 ungrounded + PASS from
  counterparty, grounding, downside, reputation, all on the current sha12. Appends to
  `passes.jsonl` (idempotent). Exit 0 recorded/already, 3 refused (every reason printed), 2 usage.
- `waive --draft PATH --reason "operator: ..."` → waiver row + `**Red-team waiver**:` line. Exit 2 if the reason lacks `operator:`.
- `check --file PATH` → exit 0 passed/waived, 3 not.
- `hook` / `post-hook` → Claude Code PreToolUse / PostToolUse handlers, wired through
  `.claude/hooks/redteam-outward-gate.sh pre|post` (settings owned by the orchestrator).

## Steps
1. Write the draft to `.tmp/redteam/drafts/<name>.txt` (exact final wording).
2. `ground` against the thread + source docs. Fix or source every ungrounded claim; reword overclaims.
3. `sha`, then run the four lenses on that text; each writes a verdict file with the sha12.
4. `record`. Any edit to the wording changes the sha: re-ground and re-run the lenses.
5. Send/draft with the same text; the hook allows it.

## Outputs
- `.tmp/redteam/ground/<sha12>.json` — claims with status grounded|ungrounded|overclaim, `weak`, `source` (`relpath:line`), `source_line` (≤160 chars), `hits` (≤5).
- `.tmp/redteam/passes.jsonl` — {sha256, sha12, draft, sources[{path, sha256}], lenses, claims_total, claims_grounded, overclaims, ts, waived[, reason]}.
- `.tmp/redteam/drafts.jsonl` — {draft_id, sha256, sha256s, ts} from `post-hook`.
- Hook: no stdout = allow; PreToolUse deny JSON otherwise.

## What is extracted
Money (€ $ £, EUR/USD/GBP, euros, "30 €", "€30k", "1,200.50", "1 200,50", ranges "€30–50"),
percentages (%, percent, pour cent), number + unit (day/week/month/year/hour/minute/page/user and
jour/semaine/mois/an/heure), dates (ISO, "28 October 2026", "Oct 28", "28/10/2026", French months)
normalised to (day, month, year?), quotes ≥ 3 words in "…" “…” „…“ «…» ‘…’, and the overclaim
lexicon EN+FR (guarantee, always, never, every, all, any, confirms, proven, at no cost, free of
charge, unlimited, 100%, instantly, risk-free, mot pour mot, garanti(e), toujours, jamais, tous/toutes,
aucun, sans frais, gratuit).

## Hook rules (fail-closed)
Gated: Gmail tools ending `send_message`, `reply`, `forward`, `create_draft`, `update_draft` (any
server prefix containing "Gmail"). Every non-empty text field (`body`/`forwardText` plain, `htmlBody`
HTML) must have its normalised sha in `passes.jsonl`, so a passed plain body cannot carry an unvetted
HTML body. `send_message` with only `draftId` is allowed when that draft's latest `drafts.jsonl` row
(written by `post-hook`) is passed. Subject/recipient-only `update_draft`, empty `create_draft` and
comment-less `forward` are allowed. Malformed input, any exception, missing python or a crashing
script → deny. Reasons carry a sha12 and ≤ 60-char excerpt, never the full body.

## Edge Cases (incl. known limits)
- **Context is the grounding lens's job.** Grounding is lexical: "€30" grounds against
  "UptimeRobot Solo + AI ≈ €30/month" even when the draft attributes it to SMS alerts (the Asset
  Voyages case is a regression test asserting exactly this). Every hit's `source_line` (up to 5) is
  reported so the grounding lens can check right-number-wrong-thing.
- `weak: true` = value found only on lines without the claim's marker (currency / % / unit word).
- Ambiguous separators ground on any reading: "1,200" ↔ {1200, 1.2}; "1.200" ↔ {1.2, 1200}.
- Space thousands ("1 200") can merge adjacent numbers ("3 100 users" → 3100).
- ASCII single-quoted quotes ('…') are not extracted (apostrophe ambiguity); bare numbers without a
  currency, %, or unit are not claims; subjects are not gated.
- "all"/"any"/"every" are noisy by design; they warn, they never fail.
- HTML source line numbers refer to the tag-stripped text, not the raw file.
- `.eml` sources are MIME-decoded (headers From/To/Date/Subject + text parts).
- Gmail response shapes vary; `post-hook` takes `draftId` from `update_draft` input, else digs an
  `id` out of the response (dict, JSON string, content blocks, text). No id → no row → a later
  send-by-draftId is denied (fail-closed).
- Waivers are only for an explicit operator instruction; quote it after `operator:`.

## Changelog
- 2026-11-04: created (deterministic layer of the mandatory outward-text red-team gate).
